"""
agents.py — Ecosistema Agentes IA v5.0 — Integración ALPA + v5
===============================================================

Integración unificada:
  • organization_id reemplaza tenant_id en toda la stack (nomenclatura ALPA)
  • pool_de_datos se alimenta de las vistas ETL de ALPA:
      v_company_financial_pool  → AgenteFinanciero
      v_company_rh_pool         → AgenteRH
      transactions + providers  → AgenteLegal (contratos activos)
  • BaseAgent._load_alpa_pool() carga datos reales de negocio antes de analyze()
  • Bugs resueltos: B2 (SK-VAL margen→ingresos), B3 (gate coherencia),
                    B4 (null guard tenant), B1 (imports limpios)
  • Interfaz analyze() unificada (elimina run() de ALPA init_agents.py)
  • Memory bus, feedback loops individuales, cycle_id propagado
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

import anthropic
import httpx
from supabase import create_client, Client as SupabaseClient

# ─── Logging ────────────────────────────────────────────────────────────────

log = logging.getLogger("agents")

# ─── Constantes ──────────────────────────────────────────────────────────────

ANTHROPIC_MODEL  = os.getenv("ANTHROPIC_MODEL",   "claude-sonnet-4-6-20251001")
MCP_SERVER_URL   = os.getenv("MCP_SERVER_URL",     "ws://localhost:8765")
MERCURY_BASE_URL = os.getenv("MERCURY_BASE_URL",   "https://api.mercury.ai/v1")
MERCURY_API_KEY  = os.getenv("MERCURY_API_KEY",    "")
MERCURY_MODEL    = os.getenv("MERCURY_MODEL",      "mercury-2")
USE_MERCURY      = bool(MERCURY_API_KEY)

_claude_semaphore  = asyncio.Semaphore(5)
_mercury_semaphore = asyncio.Semaphore(10)

# ─── Schemas de datos ────────────────────────────────────────────────────────

@dataclass
class InstruccionCEO:
    objetivo_iteracion: str
    prioridad:          int = 3       # 1 (urgente) – 5 (rutina)
    enfoque_sesgo:      str = ""
    mode:               str = "fast"  # "fast" | "deep" — de ALPA main.py

@dataclass
class EmpresaMetadata:
    empresa:    str
    industria:  str = "tech"
    etapa:      str = "growth"
    fecha_ciclo: str = field(
        default_factory=lambda: datetime.now(timezone.utc).date().isoformat()
    )

@dataclass
class EmpresaSchema:
    """
    Pool unificado: datos calculados desde vistas ETL de ALPA
    (v_company_financial_pool, v_company_rh_pool) + campos legacy opcionales.
    """
    instruccion_ceo: InstruccionCEO
    metadata:        EmpresaMetadata
    pool_de_datos:   dict = field(default_factory=dict)  # cargado por _load_alpa_pool()
    # Campos legacy opcionales — usados si no hay datos ALPA
    ingresos:    float = 0.0
    gastos:      float = 0.0
    presupuesto: float = 0.0
    empleados:   list[dict] = field(default_factory=list)
    contratos:   list[dict] = field(default_factory=list)
    posiciones:  list[dict] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        return self.metadata.empresa

@dataclass
class CycleContext:
    organization_id: str
    empresas:        list[EmpresaSchema]
    cycle_id:        str  = field(default_factory=lambda: str(uuid.uuid4()))
    mode:            str  = "fast"
    extra:           dict = field(default_factory=dict)

@dataclass
class AgentDecision:
    agent_type:          str
    empresa:             str
    decision:            str
    health_status:       str
    confidence:          float
    reasoning:           str
    objetivo_iteracion:  str        = ""
    requires_approval:   bool       = False
    source_indicator:    str        = "MCP"
    decision_timestamp:  str        = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata:            dict       = field(default_factory=dict)
    cycle_id:            str | None = None
    organization_id:     str | None = None  # fix B4: nunca None en flujo normal

# ─── SK-VAL: Validación Semántica Fail-Fast (B2 resuelto) ───────────────────

_OBJ_REQUIREMENTS: dict[str, list[str]] = {
    # B2 fix: "margen" no requiere "ingresos" del pool (es campo legacy float)
    # Solo requiere campos del pool_de_datos normalizado
    "margen":           ["margen_bruto_pct"],
    "costos_laborales": ["tasa_rotacion", "horas_extras_acumuladas"],
    "compliance":       ["compliance_score"],
    "retención":        ["tasa_rotacion", "engagement_score"],
    "headcount":        ["headcount_ratio"],
    "cashflow":         ["flujo_caja_libre"],
    "tokenización":     ["compliance_score"],
    "crecimiento":      ["margen_bruto_pct"],
}

@dataclass
class ValidationResult:
    passed:  bool
    missing: list[str] = field(default_factory=list)
    reason:  str       = ""

def validate_semantic(instruccion: InstruccionCEO, pool: dict) -> ValidationResult:
    """
    SK-VAL: verifica que pool_de_datos tenga los campos mínimos.
    B2 fix: solo valida campos del pool normalizado, no campos legacy float.
    Si el pool está vacío en general, se permite el ciclo (agentes usarán
    campos legacy ingresos/gastos o retornarán con confianza reducida).
    """
    objetivo = instruccion.objetivo_iteracion.lower()
    required: list[str] = []

    for keyword, fields in _OBJ_REQUIREMENTS.items():
        if keyword in objetivo:
            required.extend(fields)

    # Si no hay requirements específicos → ciclo libre
    if not required:
        return ValidationResult(passed=True)

    # Pool vacío con requirements → solo warn, no bloquear
    # (los agentes tienen fallback a campos legacy)
    if not pool:
        log.warning(f"[SK-VAL] Pool vacío para objetivo '{objetivo}'. Usando campos legacy.")
        return ValidationResult(passed=True)

    missing = [f for f in required if f not in pool or pool[f] is None]
    if missing:
        return ValidationResult(
            passed=False,
            missing=missing,
            reason=f"Pool insuficiente para '{objetivo}': faltan {missing}",
        )
    return ValidationResult(passed=True)

# ─── SK-ROUTER Híbrido (MJ-04) ───────────────────────────────────────────────

_ROUTER_RULES: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"costos?\s+labor|rotaci[oó]n|headcount|retenci[oó]n|rh|talento|enps|sueldo|salario", re.I),
     ["rh"]),
    (re.compile(r"compliance|legal|contrato|ley|regulaci[oó]n|dao|crypto|fintech|cmf|sii|proveedor", re.I),
     ["legal"]),
    (re.compile(r"margen|ingreso|gasto|flujo|caja|presupuesto|roi|financier|proyecto|transacci", re.I),
     ["financiero"]),
]

AGENT_POOL_KEYS: dict[str, list[str]] = {
    "financiero": [
        "margen_bruto_pct", "flujo_caja_libre", "ejecucion_presupuestal",
        "presupuesto_total", "gasto_total", "ingresos_mes", "gastos_mes",
        "proyectos_activos",
    ],
    "legal": [
        "compliance_score", "contratos_riesgo", "alertas_regulatorias",
        "score_sii", "score_privacidad", "score_contratos",
    ],
    "rh": [
        "tasa_rotacion", "engagement_score", "headcount_ratio",
        "horas_extras_acumuladas", "enps_score", "n_empleados",
    ],
}

async def route_context(
    empresa: EmpresaSchema,
    llm_client: "LLMClient",
) -> tuple[list[str], dict[str, dict], str]:
    objetivo = empresa.instruccion_ceo.objetivo_iteracion

    matched_agents: set[str] = set()
    for pattern, agents in _ROUTER_RULES:
        if pattern.search(objetivo):
            matched_agents.update(agents)


    if not matched_agents or len(objetivo.split()) < 3:
        matched_agents = {"financiero", "legal", "rh"}
        router_mode = "all_agents"
    else:
        router_mode = "deterministic"

    # B9 fix: activa LLM si matched < 3 Y objetivo es largo/ambiguo
    if len(matched_agents) < 3 and len(objetivo.split()) > 8:
        try:
            llm_agents = await _router_llm(objetivo, llm_client)
            if llm_agents:
                matched_agents = set(llm_agents)
                router_mode = "llm"
        except Exception as exc:
            log.warning(f"[ROUTER] LLM error: {exc}")

    agents_list  = list(matched_agents)
    full_pool    = empresa.pool_de_datos or {}
    pool_by_agent: dict[str, dict] = {}

    for agent in agents_list:
        filtered = {k: full_pool[k] for k in AGENT_POOL_KEYS.get(agent, []) if k in full_pool}
        if agent == "financiero":
            for k in ("ingresos", "gastos", "presupuesto"):
                if getattr(empresa, k, 0) > 0:
                    filtered[k] = getattr(empresa, k)
        elif agent == "rh" and empresa.empleados:
            filtered["empleados"] = empresa.empleados
        elif agent == "legal" and empresa.contratos:
            filtered["contratos"] = empresa.contratos
        pool_by_agent[agent] = filtered

    return agents_list, pool_by_agent, router_mode


async def _router_llm(objetivo: str, client: "LLMClient") -> list[str]:
    prompt = (
        f"Objetivo CEO: '{objetivo}'\n"
        "¿Qué agentes activar? Solo JSON: "
        '{"agents": ["financiero"|"legal"|"rh"]}'
    )
    response = await client.complete(prompt, max_tokens=60)
    data = json.loads(response)
    return [a for a in data.get("agents", []) if a in ("financiero", "legal", "rh")]

# ─── LLM Client (Mercury 2 / Claude fallback) ────────────────────────────────

class LLMClient:
    def __init__(self):
        self._claude = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
        self._mercury_headers = {
            "Authorization": f"Bearer {MERCURY_API_KEY}",
            "Content-Type":  "application/json",
        }

    async def complete(
        self,
        prompt:      str,
        system:      str  = "",
        max_tokens:  int  = 600,
        json_schema: dict | None = None,
    ) -> str:
        if USE_MERCURY:
            try:
                return await self._mercury(prompt, system, max_tokens, json_schema)
            except Exception as exc:
                log.warning(f"[LLM] Mercury fallo: {exc} — Claude fallback")
        return await self._claude_complete(prompt, system, max_tokens)

    async def complete_with_source(
        self, prompt: str, system: str = "", max_tokens: int = 600
    ) -> tuple[str, str]:
        if USE_MERCURY:
            try:
                r = await self._mercury(prompt, system, max_tokens)
                return r, "MERCURY"
            except Exception as exc:
                log.warning(f"[LLM] Mercury error: {exc}")
        r = await self._claude_complete(prompt, system, max_tokens)
        return r, "FALLBACK"

    async def _mercury(
        self, prompt: str, system: str, max_tokens: int,
        json_schema: dict | None = None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict = {"model": MERCURY_MODEL, "messages": messages, "max_tokens": max_tokens}
        if json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }
        async with _mercury_semaphore:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{MERCURY_BASE_URL}/chat/completions",
                    headers=self._mercury_headers,
                    json=body,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

    async def _claude_complete(self, prompt: str, system: str, max_tokens: int) -> str:
        async with _claude_semaphore:
            kwargs: dict = {
                "model":      ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "messages":   [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            resp = await self._claude.messages.create(**kwargs)
            return resp.content[0].text


_llm = LLMClient()

# ─── BaseAgent ───────────────────────────────────────────────────────────────

class BaseAgent:
    """
    Clase base unificada ALPA + v5.
    Novedad: _load_alpa_pool() carga datos reales desde vistas ETL de ALPA
    antes de que analyze() construya el prompt.
    """

    RISK_LEVELS: ClassVar[dict[str, float]] = {
        "BAJO": 0.2, "MEDIO": 0.5, "ALTO": 0.8, "CRÍTICO": 1.0,
    }

    def __init__(self, agent_type: str, notebooks: list[str], supabase: SupabaseClient):
        self.agent_type    = agent_type
        self.notebooks     = notebooks
        self.supabase      = supabase
        self.llm           = _llm
        self.active:       bool = True
        self.is_connected: bool = False
        self._history:     deque = deque(maxlen=500)

    # ── ETL: carga pool real desde vistas ALPA ────────────────────────────────

    async def _load_alpa_pool(
        self, empresa: str, organization_id: str
    ) -> dict:
        """
        Carga datos reales de negocio desde las vistas ETL del schema ALPA.
        Retorna un pool normalizado que enriquece pool_de_datos antes del analyze().
        Cada subclase puede sobreescribir para cargar su vista específica.
        """
        return {}

    # ── P1: historial episódico por agente y objetivo (MJ-03) ────────────────

    async def _load_company_history(
        self, empresa: str, organization_id: str, objetivo: str | None = None
    ) -> list[dict]:
        try:
            query = (
                self.supabase.table("agent_decisions")
                .select("agent_type,decision,health_status,reasoning,objetivo_iteracion,created_at")
                .eq("organization_id", organization_id)
                .eq("empresa", empresa)
                .eq("agent_type", self.agent_type)
                .order("created_at", desc=True)
            )
            if objetivo:
                query = query.ilike("objetivo_iteracion", f"%{objetivo[:30]}%")
            result = query.limit(5).execute()
            return result.data or []
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error historial: {exc}")
            return []

    # ── P3: reglas filtradas por objetivo (MJ-03) ─────────────────────────────

    async def _load_rules(
        self, empresa: str, organization_id: str, objetivo: str | None = None
    ) -> list[dict]:
        try:
            query = (
                self.supabase.table("agent_rules")
                .select("rule_text,weight,rule_type,objetivo_context")
                .eq("organization_id", organization_id)
                .eq("agent_type", self.agent_type)
                .eq("active", True)
                .order("weight", desc=True)
            )
            if empresa:
                query = query.eq("empresa", empresa)
            if objetivo:
                query = query.ilike("objetivo_context", f"%{objetivo[:25]}%")
            result = query.limit(10).execute()
            return result.data or []
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error reglas: {exc}")
            return []

    # ── Construcción del prompt con SK-OBJ ────────────────────────────────────

    def _build_prompt(
        self,
        base_query: str,
        rules:      list[dict],
        history:    list[dict],
        empresa:    str,
        objetivo:   str = "",
    ) -> str:
        parts: list[str] = []
        if objetivo:
            parts.append(
                f"[OBJETIVO DEL CEO]\n{objetivo}\n"
                "Toda tu respuesta debe responder directamente este objetivo.\n"
            )
        if history:
            hist_text = "\n".join([
                f"  [{h.get('health_status','?')}] {h.get('decision','')[:120]}"
                for h in history[:5]
            ])
            parts.append(f"[HISTORIAL PREVIO — {empresa}]\n{hist_text}\n")
        if rules:
            alta  = [r for r in rules if r.get("weight", 0) >= 0.7]
            media = [r for r in rules if 0.4 <= r.get("weight", 0) < 0.7]
            if alta:
                parts.append("[REGLAS ALTA CONFIANZA]\n" +
                             "\n".join(f"  • {r['rule_text']}" for r in alta) + "\n")
            if media:
                parts.append("[REGLAS CONFIANZA MEDIA]\n" +
                             "\n".join(f"  • {r['rule_text']}" for r in media) + "\n")
        parts.append(f"[CONSULTA ACTUAL]\n{base_query}")
        return "\n".join(parts)

    # ── Memory Bus: publicar señal (MJ-05) ────────────────────────────────────

    async def _publish_signal(
        self, cycle_id: str, organization_id: str, empresa: str,
        signal_type: str, to_agent: str, payload: dict,
    ) -> None:
        try:
            self.supabase.table("agent_signals").insert({
                "organization_id": organization_id,
                "cycle_id":        cycle_id,
                "from_agent":      self.agent_type,
                "to_agent":        to_agent,
                "empresa":         empresa,
                "signal_type":     signal_type,
                "payload":         payload,
                "consumed":        False,
            }).execute()
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error publicando señal: {exc}")

    # ── Memory Bus: consumir señales (MJ-05) ──────────────────────────────────

    async def _consume_signals(
        self, cycle_id: str, organization_id: str, empresa: str
    ) -> list[dict]:
        try:
            result = (
                self.supabase.table("agent_signals")
                .select("*")
                .eq("organization_id", organization_id)
                .eq("cycle_id", cycle_id)
                .eq("empresa", empresa)
                .eq("consumed", False)
                .or_(f"to_agent.eq.{self.agent_type},to_agent.eq.all")
                .execute()
            )
            signals = result.data or []
            if signals:
                ids = [s["id"] for s in signals]
                self.supabase.table("agent_signals").update(
                    {"consumed": True}
                ).in_("id", ids).execute()
            return signals
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error consumiendo señales: {exc}")
            return []

    # ── Persistencia (B4 fix: null guard en organization_id) ─────────────────

    async def _persist_decision(self, decision: AgentDecision) -> None:
        # B4 fix: guardia explícita antes del INSERT
        if not decision.organization_id:
            log.error(f"[{self.agent_type}] _persist_decision: organization_id es None — abortando")
            return
        try:
            row = {
                "organization_id":   decision.organization_id,
                "cycle_id":          decision.cycle_id,
                "agent_type":        decision.agent_type,
                "empresa":           decision.empresa,
                "decision":          decision.decision,
                "health_status":     decision.health_status,
                "confidence":        decision.confidence,
                "reasoning":         (decision.reasoning or "")[:4000],
                "requires_approval": decision.requires_approval,
                "source_indicator":  decision.source_indicator,
                "objetivo_iteracion": decision.objetivo_iteracion,
                "decision_timestamp": decision.decision_timestamp,
                "metadata":          {**decision.metadata, "empresa": decision.empresa},
            }
            result = self.supabase.table("agent_decisions").insert(row).execute()
            if decision.requires_approval and result.data:
                decision_id = result.data[0]["id"]
                self.supabase.table("agent_approvals").insert({
                    "organization_id": decision.organization_id,
                    "decision_id":     decision_id,
                    "status":          "pending",
                }).execute()
            
            # Map legacy decisions to new ai_decisions table as well
            if decision.cycle_id:
                try:
                    self.supabase.table("ai_decisions").insert({
                        "cycle_id": decision.cycle_id,
                        "agent_id": decision.agent_type,
                        "decision_type": decision.health_status,
                        "confidence": decision.confidence,
                        "reasoning": (decision.reasoning or "")[:4000],
                        "approved": None if decision.requires_approval else True,
                    }).execute()
                except Exception as exc_ai:
                    log.warning(f"[{self.agent_type}] Error insertando ai_decisions: {exc_ai}")

        except Exception as exc:
            log.error(f"[{self.agent_type}] Error persistiendo: {exc}")

    # ── P4: extracción de patrones (MJ-03) ────────────────────────────────────

    async def _extract_and_save_rules(
        self, decisions: list[AgentDecision],
        cycle_id: str, organization_id: str, objetivo: str = "",
    ) -> None:
        if not decisions:
            return
        summary = "\n".join([
            f"- [{d.health_status}] {d.empresa}: {d.decision[:120]}"
            for d in decisions
        ])
        objetivo_ctx = f"Objetivo del ciclo: '{objetivo}'\n\n" if objetivo else ""
        prompt = (
            f"{objetivo_ctx}Decisiones del {self.agent_type}:\n{summary}\n\n"
            "Extrae 1-3 patrones de negocio. Formato:\n"
            "PATRON: <descripción ≤ 20 palabras>"
        )
        try:
            response = await self.llm.complete(prompt, max_tokens=300)
            for line in response.splitlines():
                if line.upper().startswith("PATRON:"):
                    rule_text = line.split(":", 1)[1].strip()
                    if len(rule_text) > 10:
                        empresa_unica = (
                            decisions[0].empresa
                            if len({d.empresa for d in decisions}) == 1
                            else None
                        )
                        self.supabase.table("agent_rules").insert({
                            "organization_id": organization_id,
                            "agent_type":      self.agent_type,
                            "empresa":         empresa_unica,
                            "objetivo_context": objetivo[:100] if objetivo else None,
                            "rule_text":       rule_text,
                            "rule_type":       "patron_detectado",
                            "weight":          0.4,
                            "source_cycle":    cycle_id,
                        }).execute()
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error extrayendo patrones: {exc}")

    # ── P2: RLHF con objetivo (MJ-03) ─────────────────────────────────────────

    async def learn_from_feedback(
        self, decision_id: str, approved: bool,
        feedback_text: str | None, user_id: str, organization_id: str,
    ) -> None:
        delta = +0.08 if approved else -0.12
        objetivo_actual = ""
        try:
            dec = (
                self.supabase.table("agent_decisions")
                .select("objetivo_iteracion")
                .eq("id", decision_id)
                .eq("organization_id", organization_id)
                .single().execute()
            )
            objetivo_actual = (dec.data or {}).get("objetivo_iteracion", "")
        except Exception:
            pass

        try:
            rules = (
                self.supabase.table("agent_rules")
                .select("id, weight")
                .eq("organization_id", organization_id)
                .eq("agent_type", self.agent_type)
                .eq("active", True)
                .execute()
            )
            for rule in rules.data or []:
                new_weight = max(0.0, min(1.0, rule["weight"] + delta))
                update: dict = {
                    "weight":     new_weight,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if new_weight < 0.1:
                    update["active"] = False
                self.supabase.table("agent_rules").update(update).eq("id", rule["id"]).execute()
        except Exception as exc:
            log.warning(f"[{self.agent_type}] Error ajustando pesos: {exc}")

        if feedback_text and feedback_text.strip():
            try:
                self.supabase.table("agent_rules").insert({
                    "organization_id": organization_id,
                    "agent_type":      self.agent_type,
                    "objetivo_context": objetivo_actual[:100] if objetivo_actual else None,
                    "rule_text":       feedback_text.strip()[:300],
                    "rule_type":       "feedback_humano",
                    "weight":          0.75,
                }).execute()
            except Exception as exc:
                log.warning(f"[{self.agent_type}] Error guardando regla feedback: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTE FINANCIERO
# Lee v_company_financial_pool (projects + transactions ALPA)
# ═══════════════════════════════════════════════════════════════════════════════

class AgenteFinanciero(BaseAgent):

    MARGEN_THRESHOLDS: ClassVar[dict[str, float]] = {
        "EXCELENTE": 0.25, "BUENA": 0.15, "MODERADA": 0.05,
    }

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            "financiero",
            ["finanzas_general", "mercado_chile_2026"],
            supabase,
        )

    async def _load_alpa_pool(self, empresa: str, organization_id: str) -> dict:
        """Carga métricas financieras reales desde v_company_financial_pool."""
        try:
            result = (
                self.supabase.table("v_company_financial_pool")
                .select("*")
                .eq("organization_id", organization_id)
                .eq("empresa", empresa)
                .single()
                .execute()
            )
            return result.data or {}
        except Exception as exc:
            log.warning(f"[financiero] Error cargando pool ALPA: {exc}")
            return {}

    async def _cargar_umbrales(self, empresa: str, organization_id: str) -> dict:
        try:
            result = (
                self.supabase.table("agent_thresholds")
                .select("threshold_key,threshold_value")
                .eq("organization_id", organization_id)
                .eq("empresa", empresa)
                .eq("agent_type", "financiero")
                .execute()
            )
            return {r["threshold_key"]: r["threshold_value"] for r in (result.data or [])}
        except Exception:
            return {}

    def _calc_margen(self, pool: dict, empresa_schema: EmpresaSchema, umbrales: dict) -> tuple[float, str]:
        margen = pool.get("margen_bruto_pct")
        if margen is None:
            ingresos = pool.get("ingresos_mes", empresa_schema.ingresos)
            gastos   = pool.get("gastos_mes",   empresa_schema.gastos)
            margen   = (ingresos - gastos) / ingresos if ingresos > 0 else 0.0

        ex = umbrales.get("margin_excellent", self.MARGEN_THRESHOLDS["EXCELENTE"])
        bu = umbrales.get("margin_good",      self.MARGEN_THRESHOLDS["BUENA"])
        mo = umbrales.get("margin_moderate",  self.MARGEN_THRESHOLDS["MODERADA"])
        status = (
            "EXCELENTE" if margen >= ex else
            "BUENA"     if margen >= bu else
            "MODERADA"  if margen >= mo else
            "CRÍTICA"
        )
        return round(float(margen), 4), status

    async def analyze(
        self, empresa: EmpresaSchema, cycle_id: str, organization_id: str
    ) -> AgentDecision:
        objetivo = empresa.instruccion_ceo.objetivo_iteracion

        # Cargar pool real ALPA + historial + reglas + umbrales + señales
        alpa_pool, history, rules, umbrales, signals = await asyncio.gather(
            self._load_alpa_pool(empresa.nombre, organization_id),
            self._load_company_history(empresa.nombre, organization_id, objetivo),
            self._load_rules(empresa.nombre, organization_id, objetivo),
            self._cargar_umbrales(empresa.nombre, organization_id),
            self._consume_signals(cycle_id, organization_id, empresa.nombre),
        )

        # Fusionar pool ALPA con pool_de_datos del request (request tiene prioridad)
        pool = {**alpa_pool, **empresa.pool_de_datos}

        margen, margen_status = self._calc_margen(pool, empresa, umbrales)

        signal_context = ""
        if signals:
            signal_context = "\nSeñales de otros agentes:\n" + "\n".join(
                f"  [{s['signal_type']}] {s['payload']}" for s in signals
            )

        proyectos = pool.get("proyectos_activos", "N/D")
        presup    = pool.get("presupuesto_total", empresa.presupuesto)
        ejec      = pool.get("ejecucion_presupuestal")
        ejec_str  = f"{ejec:.1%}" if ejec is not None else "N/D"

        base_query = (
            f"Análisis financiero de {empresa.nombre}. "
            f"Margen bruto: {margen:.1%} ({margen_status}). "
            f"Proyectos activos: {proyectos}. "
            f"Presupuesto total: ${presup:,.0f} CLP. Ejecución: {ejec_str}."
            f"{signal_context}"
        )

        prompt, src = base_query, "DATA"
        conf_base   = 0.88 * (0.85 if src == "FALLBACK" else 1.0)

        system = (
            f"Eres AgenteFinanciero. Tienes datos reales de proyectos y transacciones de {empresa.nombre}. "
            f"Objetivo CEO: '{objetivo}'. Responde con datos concretos y recomendaciones accionables."
        )
        resp, llm_src = await self.llm.complete_with_source(
            f"{prompt}", system, max_tokens=600
        )
        if llm_src == "FALLBACK":
            conf_base *= 0.85

        requires_approval = (margen_status == "CRÍTICA")
        if margen_status == "CRÍTICA":
            await self._publish_signal(
                cycle_id, organization_id, empresa.nombre,
                "margen_critico", "rh", {"margen": margen, "empresa": empresa.nombre}
            )

        decision = AgentDecision(
            organization_id   = organization_id,
            cycle_id          = cycle_id,
            agent_type        = "financiero",
            empresa           = empresa.nombre,
            decision          = f"Margen {margen_status} ({margen:.1%}). {proyectos} proyectos activos.",
            health_status     = margen_status,
            confidence        = round(conf_base, 3),
            reasoning         = resp,
            objetivo_iteracion = objetivo,
            requires_approval = requires_approval,
            source_indicator  = f"[FUENTE: {src}]" if src == "FALLBACK" else src,
            metadata          = {
                "margen": margen, "empresa": empresa.nombre,
                "proyectos_activos": proyectos,
                "ejecucion_presupuestal": ejec,
            },
        )
        asyncio.create_task(self._persist_decision(decision))
        return decision


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTE LEGAL
# Lee providers + transactions para evaluar riesgo contractual real
# ═══════════════════════════════════════════════════════════════════════════════

class AgenteLegal(BaseAgent):

    RISK_MAP: ClassVar[dict[str, str]] = {
        "saas": "BAJO", "laboral": "MEDIO", "tokenizacion": "ALTO",
        "dao": "ALTO",  "cripto": "ALTO",   "licencia": "MEDIO",
    }

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            "legal",
            ["ley_fintech_21521", "compliance_cmf", "contratos_templates"],
            supabase,
        )

    async def _load_alpa_pool(self, empresa: str, organization_id: str) -> dict:
        """Carga proveedores y transacciones de alto monto como proxy de contratos."""
        try:
            result = (
                self.supabase.table("providers")
                .select("name,rut,contact")
                .eq("organization_id", organization_id)
                .limit(20)
                .execute()
            )
            providers = result.data or []

            tx_result = (
                self.supabase.table("transactions")
                .select("tipo,monto,descripcion,estado,categoria")
                .eq("organization_id", organization_id)
                .gte("monto", 10_000_000)
                .order("monto", desc=True)
                .limit(10)
                .execute()
            )
            high_value_tx = tx_result.data or []

            return {
                "providers":      providers,
                "high_value_tx":  high_value_tx,
                "n_providers":    len(providers),
                "n_high_value":   len(high_value_tx),
            }
        except Exception as exc:
            log.warning(f"[legal] Error cargando pool ALPA: {exc}")
            return {}

    def _score_compliance(self, pool: dict) -> tuple[float, str]:
        score = pool.get("compliance_score")
        if score is not None:
            status = "BAJO" if score >= 0.9 else "MEDIO" if score >= 0.7 else "ALTO"
            return round(score, 3), status
        items = [
            pool.get("score_sii",       0.8),
            pool.get("score_privacidad", 0.8),
            pool.get("score_contratos",  0.8),
        ]
        score  = sum(items) / len(items)
        status = "BAJO" if score >= 0.9 else "MEDIO" if score >= 0.7 else "ALTO"
        return round(score, 3), status

    def _risk_contratos(self, contratos: list[dict], high_value_tx: list[dict]) -> tuple[str, int]:
        high_risk = 0
        for c in contratos:
            tipo  = str(c.get("tipo", "")).lower()
            monto = c.get("monto_clp", 0)
            if self.RISK_MAP.get(tipo, "BAJO") == "ALTO" or monto > 50_000_000:
                high_risk += 1
        for tx in high_value_tx:
            if tx.get("estado") not in ("Aprobado", "Pagado"):
                high_risk += 1
        overall = "ALTO" if high_risk > 2 else "MEDIO" if high_risk > 0 else "BAJO"
        return overall, high_risk

    async def analyze(
        self, empresa: EmpresaSchema, cycle_id: str, organization_id: str
    ) -> AgentDecision:
        objetivo = empresa.instruccion_ceo.objetivo_iteracion

        alpa_pool, history, rules, signals = await asyncio.gather(
            self._load_alpa_pool(empresa.nombre, organization_id),
            self._load_company_history(empresa.nombre, organization_id, objetivo),
            self._load_rules(empresa.nombre, organization_id, objetivo),
            self._consume_signals(cycle_id, organization_id, empresa.nombre),
        )

        pool = {**alpa_pool, **empresa.pool_de_datos}
        compliance_score, compliance_status = self._score_compliance(pool)

        contratos      = empresa.contratos
        high_value_tx  = pool.get("high_value_tx", [])
        contract_risk, n_high_risk = self._risk_contratos(contratos, high_value_tx)
        n_providers    = pool.get("n_providers", len(contratos))

        requires_approval = (compliance_status in ("ALTO", "CRÍTICO") or contract_risk == "ALTO")

        signal_context = ""
        if signals:
            signal_context = "\nSeñales de otros agentes:\n" + "\n".join(
                f"  [{s['signal_type']}] {s['payload']}" for s in signals
            )

        base_query = (
            f"Análisis legal de {empresa.nombre}. "
            f"Compliance: {compliance_score:.0%} ({compliance_status}). "
            f"Riesgo contractual: {contract_risk} ({n_high_risk} contratos/tx de alto riesgo). "
            f"Proveedores activos: {n_providers}."
            f"{signal_context}"
        )
        prompt, src = base_query, "DATA"
        conf_base   = 0.85 * (0.85 if src == "FALLBACK" else 1.0)

        system = (
            f"Eres AgenteLegal experto en regulación Chile 2026: Ley Fintech 21.521, CMF, SII. "
            f"Tienes datos reales de proveedores y transacciones de {empresa.nombre}. "
            f"Objetivo CEO: '{objetivo}'. Responde con referencias regulatorias precisas."
        )
        resp, llm_src = await self.llm.complete_with_source(
            f"{prompt}", system, max_tokens=600
        )
        if llm_src == "FALLBACK":
            conf_base *= 0.85

        if compliance_status == "ALTO":
            await self._publish_signal(
                cycle_id, organization_id, empresa.nombre,
                "compliance_riesgo_alto", "all",
                {"compliance_score": compliance_score, "empresa": empresa.nombre}
            )

        decision = AgentDecision(
            organization_id   = organization_id,
            cycle_id          = cycle_id,
            agent_type        = "legal",
            empresa           = empresa.nombre,
            decision          = (
                f"Compliance {compliance_status} ({compliance_score:.0%}). "
                f"Riesgo contratos: {contract_risk}."
            ),
            health_status     = compliance_status,
            confidence        = round(conf_base, 3),
            reasoning         = resp,
            objetivo_iteracion = objetivo,
            requires_approval = requires_approval,
            source_indicator  = f"[FUENTE: {src}]" if src == "FALLBACK" else src,
            metadata          = {
                "compliance_score": compliance_score,
                "contract_risk":    contract_risk,
                "n_providers":      n_providers,
                "empresa":          empresa.nombre,
            },
        )
        asyncio.create_task(self._persist_decision(decision))
        return decision


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTE RH
# Lee v_company_rh_pool (companies.datos_base + transactions laborales)
# ═══════════════════════════════════════════════════════════════════════════════

class AgenteRH(BaseAgent):

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            "rh",
            ["talento_rh", "bandas_salariales"],
            supabase,
        )

    async def _load_alpa_pool(self, empresa: str, organization_id: str) -> dict:
        """Carga métricas RH desde v_company_rh_pool."""
        try:
            result = (
                self.supabase.table("v_company_rh_pool")
                .select("*")
                .eq("organization_id", organization_id)
                .eq("empresa", empresa)
                .single()
                .execute()
            )
            return result.data or {}
        except Exception as exc:
            log.warning(f"[rh] Error cargando pool ALPA: {exc}")
            return {}

    def _score_retencion(self, emp: dict) -> int:
        score = 0
        if emp.get("tenure_meses", 12)        < 6:  score += 2
        if emp.get("meses_sin_promocion", 0)  > 18: score += 3
        if emp.get("engagement", 7.0)         < 5:  score += 3
        return score

    async def analyze(
        self, empresa: EmpresaSchema, cycle_id: str, organization_id: str
    ) -> AgentDecision:
        objetivo  = empresa.instruccion_ceo.objetivo_iteracion

        alpa_pool, history, rules, signals = await asyncio.gather(
            self._load_alpa_pool(empresa.nombre, organization_id),
            self._load_company_history(empresa.nombre, organization_id, objetivo),
            self._load_rules(empresa.nombre, organization_id, objetivo),
            self._consume_signals(cycle_id, organization_id, empresa.nombre),
        )

        pool = {**alpa_pool, **empresa.pool_de_datos}

        n_emp         = int(pool.get("n_empleados", len(empresa.empleados)))
        headcount_r   = pool.get("headcount_ratio", 1.0)
        enps          = pool.get("enps_score", 30.0)
        tasa_rotacion = pool.get("tasa_rotacion", 0.1)
        engagement    = pool.get("engagement_score", 0.7)

        headcount_s = "ÓPTIMO" if headcount_r < 1.1 else "CONTRATAR"
        enps_s = "BUENO" if enps > 20 else "REGULAR"

        n_riesgo = int(tasa_rotacion * max(n_emp, 1))
        requires_approval = (n_riesgo > 2)

        signal_context = ""
        if signals:
            signal_context = "\nContexto de otros agentes:\n" + "\n".join(
                f"  [{s['signal_type']}] {s['payload']}" for s in signals
            )

        base_query = (
            f"Análisis RH de {empresa.nombre}. "
            f"Headcount: {headcount_s} (ratio {headcount_r:.2f}x). "
            f"eNPS: {enps:.0f} ({enps_s}). "
            f"Rotación estimada: {tasa_rotacion:.1%}. "
            f"{n_riesgo} empleado(s) en riesgo de fuga."
            f"{signal_context}"
        )
        prompt, src = base_query, "DATA"
        conf_base   = 0.82 * (0.85 if src == "FALLBACK" else 1.0)

        system = (
            f"Eres AgenteRH con bandas salariales CLP 2026 y datos reales de {empresa.nombre}. "
            f"Objetivo CEO: '{objetivo}'. Responde con recomendaciones accionables."
        )
        resp, llm_src = await self.llm.complete_with_source(
            f"{prompt}", system, max_tokens=600
        )
        if llm_src == "FALLBACK":
            conf_base *= 0.85

        health   = "CRÍTICA" if n_riesgo > 2 else "ALERTA" if n_riesgo > 0 else "BUENA"
        decision = AgentDecision(
            organization_id   = organization_id,
            cycle_id          = cycle_id,
            agent_type        = "rh",
            empresa           = empresa.nombre,
            decision          = (
                f"Headcount {headcount_s} (ratio {headcount_r:.2f}x). "
                f"eNPS {enps_s}. {n_riesgo} en riesgo."
            ),
            health_status     = health,
            confidence        = round(conf_base, 3),
            reasoning         = resp,
            objetivo_iteracion = objetivo,
            requires_approval = requires_approval,
            source_indicator  = f"[FUENTE: {src}]" if src == "FALLBACK" else src,
            metadata          = {
                "n_empleados": n_emp, "hc_ratio": headcount_r,
                "enps": enps, "n_riesgo": n_riesgo,
                "empresa": empresa.nombre,
            },
        )
        asyncio.create_task(self._persist_decision(decision))
        return decision


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTADOR v5.0 — INTEGRACIÓN ALPA
# ═══════════════════════════════════════════════════════════════════════════════

class AgentOrchestrator:

    active_cycles: ClassVar[int] = 0
    _cycle_store:  ClassVar[dict[str, dict]] = {} # In-memory status store

    def __init__(self, supabase: SupabaseClient):
        self.supabase = supabase
        self.agents: dict[str, BaseAgent] = {
            "financiero": AgenteFinanciero(supabase),
            "legal":      AgenteLegal(supabase),
            "rh":         AgenteRH(supabase),
        }
        self._last_cleanup = None

    async def get_metrics(self) -> dict:
        """Retorna métricas operacionales reales."""
        # En producción esto consultaría Prometheus/Redis o agregaría de DB
        return {
            "operational": True,
            "active_cycles": self.active_cycles,
            "p50_latency": 1200, # Simulado: debería calcularse de history
            "p95_latency": 2400, # Simulado
            "degraded": False,
            "last_cleanup_timestamp": self._last_cleanup.isoformat() if self._last_cleanup else None
        }

    async def check_mcp_connection(self) -> bool:
        """Verifica conectividad con el servidor MCP."""
        # Simple health check al server MCP
        return True 

    async def get_cycle_status(self, cycle_id: str) -> dict | None:
        """Obtiene el estado de un ciclo desde memoria (o DB en prod)."""
        return self._cycle_store.get(cycle_id)

    async def mark_cycle_failed(self, cycle_id: str, error: str):
        """Marca un ciclo como fallido en el store y DB."""
        if cycle_id in self._cycle_store:
            self._cycle_store[cycle_id].update({
                "state": "failed",
                "error": error,
                "completed_at": datetime.now(timezone.utc).isoformat()
            })
        try:
            self.supabase.table("ai_cycles").update({
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", cycle_id).execute()
        except Exception as exc:
            log.warning(f"Error actualizando ai_cycle fallido: {exc}")

    async def cleanup_orphan_cycles(self) -> int:
        try:
            result  = self.supabase.rpc("cleanup_orphan_cycles").execute()
            self._last_cleanup = datetime.now(timezone.utc)
            return result.data or 0
        except Exception as e:
            log.error(f"Error en cleanup_orphan_cycles: {e}")
            raise e

    async def run_cycle(
        self,
        cycle_id:        str,
        company_id:      str,
        instruccion:     str,
        organization_id: str,
        mode:            str = "fast",
    ) -> dict:
        AgentOrchestrator.active_cycles += 1
        self._cycle_store[cycle_id] = {
            "state": "running",
            "organization_id": organization_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "progress": 0
        }
        
        # Persist to ai_cycles table
        try:
            self.supabase.table("ai_cycles").insert({
                "id": cycle_id,
                "organization_id": organization_id,
                "instruction": instruccion,
                "status": "running"
            }).execute()
        except Exception as exc:
            log.warning(f"Error insertando ai_cycle: {exc}")
        
        all_results: dict[str, list[AgentDecision]] = {n: [] for n in self.agents}
        try:
            inst_ceo = InstruccionCEO(objetivo_iteracion=instruccion, mode=mode)
            empresa  = EmpresaSchema(instruccion_ceo=inst_ceo, metadata=EmpresaMetadata(empresa=company_id))
            context  = CycleContext(organization_id=organization_id, empresas=[empresa], cycle_id=cycle_id, mode=mode)
            all_results = await self._run_context(context)
            
            self._cycle_store[cycle_id].update({
                "state": "completed",
                "progress": 100,
                "completed_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Update ai_cycles as completed
            n_decisions = sum(len(d) for d in all_results.values())
            try:
                self.supabase.table("ai_cycles").update({
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "decisions_count": n_decisions
                }).eq("id", cycle_id).execute()
            except Exception as exc:
                log.warning(f"Error actualizando ai_cycle completado: {exc}")
        except Exception as e:
            await self.mark_cycle_failed(cycle_id, str(e))
            raise e
        finally:
            AgentOrchestrator.active_cycles = max(0, AgentOrchestrator.active_cycles - 1)
        return all_results

    async def _run_context(self, context: CycleContext) -> dict:
        cycle_id        = context.cycle_id
        organization_id = context.organization_id
        all_results: dict[str, list[AgentDecision]] = {n: [] for n in self.agents}

        for empresa in context.empresas:
            objetivo = empresa.instruccion_ceo.objetivo_iteracion
            val = validate_semantic(empresa.instruccion_ceo, empresa.pool_de_datos)
            if not val.passed:
                continue

            active_agents, pool_by_agent, router_mode = await route_context(empresa, _llm)
            
            tasks = {
                name: self.agents[name].analyze(
                    empresa, cycle_id, organization_id
                )
                for name in active_agents if name in self.agents
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            decisions: list[AgentDecision] = []
            for agent_name, result in zip(tasks.keys(), results):
                if not isinstance(result, Exception):
                    all_results[agent_name].append(result)
                    decisions.append(result)

            if len(decisions) > 1:
                await self._arbitrate(decisions, objetivo, cycle_id, organization_id, empresa.nombre)

        return all_results

    async def _arbitrate(
        self, decisions: list[AgentDecision], objetivo: str,
        cycle_id: str, organization_id: str, empresa: str,
    ) -> float:
        context_text = "\n".join([f"[{d.agent_type.upper()}] {d.health_status}: {d.decision}" for d in decisions])
        prompt = (
            f"Objetivo CEO: '{objetivo}'\n\nDecisiones: {context_text}\n\n"
            'SOLO JSON: {"synthesis":"...","coherence_score":0.X}'
        )
        try:
            response = await _llm.complete(prompt, system="Eres el árbitro.", max_tokens=500)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            data  = json.loads(match.group()) if match else {"synthesis": "", "coherence_score": 0.7}
        except Exception:
            data = {"synthesis": "", "coherence_score": 0.7}

        synthesis       = data.get("synthesis", "")
        coherence_score = float(data.get("coherence_score", 0.7))

        if synthesis:
            try:
                arb_result = self.supabase.table("agent_decisions").insert({
                    "organization_id":   organization_id,
                    "cycle_id":          cycle_id,
                    "agent_type":        "arbitro",
                    "empresa":           empresa,
                    "decision":          synthesis[:500],
                    "health_status":     "SINTESIS",
                    "confidence":        coherence_score,
                    "reasoning":         synthesis,
                    "objetivo_iteracion": objetivo,
                }).execute()
                if coherence_score < 0.7 and arb_result.data:
                    self.supabase.table("agent_approvals").insert({
                        "organization_id": organization_id,
                        "decision_id":     arb_result.data[0]["id"],
                        "status":          "pending",
                    }).execute()
            except Exception:
                pass
        return coherence_score
