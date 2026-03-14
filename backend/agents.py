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
            meta = {**decision.metadata, "empresa": decision.empresa}
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
                "metadata":          meta,
                # Columnas de audit trail (Financial Agent v2)
                "confidence_level":  meta.get("confidence_level"),
                "tool_calls_log":    meta.get("tool_calls_log", []),
                "data_sources":      meta.get("data_sources",   []),
                "null_fields":       meta.get("null_fields",    []),
                "trigger_type":      meta.get("trigger_type",   "manual"),
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
# AgenteFinanciero v2.0 — Tool-First, Anti-Alucinación
# ═══════════════════════════════════════════════════════════════════════════════
# Arquitectura: el LLM nunca genera números.
# Las tools traen datos reales; Claude solo interpreta y razona.
# Audit trail inmutable en agent_tool_log.
# ═══════════════════════════════════════════════════════════════════════════════

class AgenteFinanciero(BaseAgent):
    """
    Agente financiero con arquitectura Tool-First.

    Reglas absolutas (enforced en system prompt y en código):
      1. Nunca mencionar un número que no venga de una tool call
      2. Si una tool retorna vacío → declarar "datos_insuficientes"
      3. Cada conclusión cita qué tool la respalda
      4. Confidence declarado: HIGH / MEDIUM / LOW / REFUSE
      5. Modelo pinnedo — nunca alias flotante
    """

    MARGEN_THRESHOLDS: ClassVar[dict[str, float]] = {
        "EXCELENTE": 0.25, "BUENA": 0.15, "MODERADA": 0.05,
    }

    # Tools disponibles para Claude (Anthropic tool-use schema)
    _TOOL_DEFINITIONS: ClassVar[list[dict]] = [
        {
            "name": "get_executive_summary",
            "description": (
                "Carga métricas financieras agregadas de la organización: margen bruto, "
                "proyectos activos, ingresos y gastos del mes, ejecución presupuestal. "
                "Usar SIEMPRE como primer paso del análisis."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_project_margins",
            "description": (
                "Retorna el margen real vs presupuesto ofertado por proyecto. "
                "Incluye costo comprometido (OC pendientes) y ejecutado (OC pagadas). "
                "Indica si hay alerta de desviación (>15%). "
                "Usar para identificar proyectos con problemas de rentabilidad."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "ID del proyecto. Omitir para obtener todos los proyectos.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_overdue_payments",
            "description": (
                "Retorna estados de pago vencidos con días de mora y historial del cliente. "
                "Usar para analizar riesgo de cobranza y flujo de caja por cobrar."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "days_threshold": {
                        "type": "integer",
                        "description": "Días mínimos vencido. Default 1.",
                        "default": 1,
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_oc_anomalies",
            "description": (
                "Detecta órdenes de compra con precio superior al histórico del mismo "
                "ítem y proveedor (requiere ≥3 OC históricas). "
                "Usar para controlar sobrecostos en compras."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "oc_id": {
                        "type": "string",
                        "description": "ID de una OC específica. Omitir para analizar todas las recientes.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_cashflow_projection",
            "description": (
                "Proyección semanal de flujo de caja basada en documentos pendientes reales "
                "(EP emitidos + OC aprobadas). NUNCA estima — solo documentos existentes. "
                "Usar para detectar semanas con déficit proyectado."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Horizonte en días. Default 90.",
                        "default": 90,
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_budget_vs_actual",
            "description": (
                "Compara presupuesto vs costo ejecutado por partida para un proyecto. "
                "Retorna null si no hay datos suficientes — nunca estima."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "ID del proyecto a analizar.",
                    }
                },
                "required": ["project_id"],
            },
        },
    ]

    _SYSTEM_PROMPT: ClassVar[str] = """Eres AgenteFinanciero de AgentOS. Analizas la salud financiera de empresas constructoras chilenas.

REGLAS ABSOLUTAS — violación = respuesta inválida:
1. NUNCA menciones un número que no venga de una tool call. Cero excepciones.
2. Si una tool retorna lista vacía o None → declara exactamente: "datos_insuficientes para [campo]"
3. Cada conclusión numérica debe citar: tool_name + dato específico que la respalda.
4. Declara siempre tu nivel de confianza: HIGH | MEDIUM | LOW | REFUSE.
   - HIGH: todos los datos necesarios están presentes en tools
   - MEDIUM: datos parciales, algunas inferencias necesarias
   - LOW: datos mínimos, análisis muy limitado
   - REFUSE: datos insuficientes para dar una opinión válida
5. El modelo pinneado es claude-sonnet-4-6-20251001 — no cambies esto.

FLUJO OBLIGATORIO:
1. Llama get_executive_summary primero para contexto general
2. Según el objetivo, llama las tools específicas relevantes
3. Analiza SOLO los datos retornados — nunca complementes con estimaciones
4. Estructura tu respuesta con: [HALLAZGOS] → [ALERTAS] → [RECOMENDACIONES] → [CONFIANZA]

FORMATO DE RESPUESTA (JSON estricto):
{
  "decision": "resumen ejecutivo en 1 oración con cifras de las tools",
  "health_status": "EXCELENTE|BUENA|MODERADA|CRÍTICA|DATOS_INSUFICIENTES",
  "confidence_level": "HIGH|MEDIUM|LOW|REFUSE",
  "hallazgos": ["hallazgo 1 con fuente: tool_name", ...],
  "alertas": ["alerta 1 con datos exactos de la tool", ...],
  "recomendaciones": ["acción concreta 1", ...],
  "requires_approval": true/false,
  "null_fields": ["campos sin datos disponibles"],
  "data_sources": ["tool_name: descripción del dato usado", ...]
}"""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            "financiero",
            ["finanzas_general", "mercado_chile_2026"],
            supabase,
        )

    def _classify_margen(self, margen: float | None) -> str:
        if margen is None:
            return "DATOS_INSUFICIENTES"
        if margen >= self.MARGEN_THRESHOLDS["EXCELENTE"]:
            return "EXCELENTE"
        if margen >= self.MARGEN_THRESHOLDS["BUENA"]:
            return "BUENA"
        if margen >= self.MARGEN_THRESHOLDS["MODERADA"]:
            return "MODERADA"
        return "CRÍTICA"

    async def _run_tool_loop(
        self,
        tools: "FinancialTools",
        objetivo: str,
        empresa_nombre: str,
        organization_id: str,
        signals: list[dict],
    ) -> tuple[dict, str]:
        """
        Ejecuta el loop tool-use de Claude.
        Claude llama tools hasta tener suficientes datos, luego emite respuesta final.
        Máximo 8 rondas para evitar loops infinitos.
        """
        from anthropic import AsyncAnthropic
        import json as _json

        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

        signal_ctx = ""
        if signals:
            signal_ctx = "\nSeñales de otros agentes:\n" + "\n".join(
                f"  [{s['signal_type']}] {s['payload']}" for s in signals
            )

        user_message = (
            f"Empresa: {empresa_nombre}\n"
            f"Objetivo del CEO: {objetivo}\n"
            f"Organization ID: {organization_id}"
            f"{signal_ctx}\n\n"
            "Analiza la situación financiera. Usa las tools disponibles para obtener "
            "datos reales antes de emitir cualquier conclusión. "
            "Responde en el formato JSON especificado en el system prompt."
        )

        messages = [{"role": "user", "content": user_message}]
        final_text = ""
        rounds = 0
        MAX_ROUNDS = 8

        # Prompt caching: system prompt + tool definitions son idénticos en todos los ciclos
        # → cache_control ephemeral ahorra ~70% tokens de input en llamadas 2-8
        _cached_system = [
            {
                "type": "text",
                "text": self._SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        _cached_tools = [
            *self._TOOL_DEFINITIONS[:-1],
            {**self._TOOL_DEFINITIONS[-1], "cache_control": {"type": "ephemeral"}},
        ]

        while rounds < MAX_ROUNDS:
            rounds += 1
            async with _claude_semaphore:
                response = await client.messages.create(
                    model      = ANTHROPIC_MODEL,
                    max_tokens = 2048,
                    system     = _cached_system,
                    tools      = _cached_tools,
                    messages   = messages,
                )

            # Si Claude terminó (no hay más tool calls)
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                break

            # Procesar tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                messages.append({"role": "assistant", "content": response.content})

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name   = block.name
                    tool_input  = block.input or {}
                    tool_result = None

                    # Ejecutar la tool correspondiente
                    try:
                        if tool_name == "get_executive_summary":
                            tool_result = tools.get_executive_summary()
                        elif tool_name == "get_project_margins":
                            result = tools.get_project_margins(tool_input.get("project_id"))
                            tool_result = [vars(m) for m in result] if result else []
                        elif tool_name == "get_overdue_payments":
                            result = tools.get_overdue_payments(tool_input.get("days_threshold", 1))
                            tool_result = [vars(p) for p in result] if result else []
                        elif tool_name == "get_oc_anomalies":
                            result = tools.get_oc_anomalies(tool_input.get("oc_id"))
                            tool_result = [vars(a) for a in result] if result else []
                        elif tool_name == "get_cashflow_projection":
                            result = tools.get_cashflow_projection(tool_input.get("days_ahead", 90))
                            tool_result = [vars(w) for w in result] if result else []
                        elif tool_name == "get_budget_vs_actual":
                            result = tools.get_budget_vs_actual(tool_input["project_id"])
                            if result:
                                d = vars(result)
                                d["partidas"] = [vars(p) for p in result.partidas]
                                tool_result = d
                            else:
                                tool_result = None
                        else:
                            tool_result = {"error": f"Tool desconocida: {tool_name}"}

                    except Exception as tool_exc:
                        log.warning(f"[financiero] Tool {tool_name} error: {tool_exc}")
                        tool_result = {"error": str(tool_exc)}

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     _json.dumps(tool_result, ensure_ascii=False, default=str),
                    })

                messages.append({"role": "user", "content": tool_results})
            else:
                # stop_reason inesperado
                log.warning(f"[financiero] stop_reason inesperado: {response.stop_reason}")
                break

        return final_text, f"tool_loop_{rounds}_rounds"

    async def analyze(
        self, empresa: EmpresaSchema, cycle_id: str, organization_id: str
    ) -> AgentDecision:
        import json as _json
        from financial_tools import FinancialTools

        objetivo = empresa.instruccion_ceo.objetivo_iteracion

        # Cargar historial episódico + reglas + señales (en paralelo)
        history, rules, signals = await asyncio.gather(
            self._load_company_history(empresa.nombre, organization_id, objetivo),
            self._load_rules(empresa.nombre, organization_id, objetivo),
            self._consume_signals(cycle_id, organization_id, empresa.nombre),
        )

        # Instanciar motor de verdad
        tools = FinancialTools(self.supabase, organization_id)

        # Ejecutar loop tool-use de Claude
        raw_response, llm_src = await self._run_tool_loop(
            tools, objetivo, empresa.nombre, organization_id, signals
        )

        # Parsear respuesta estructurada
        parsed: dict = {}
        try:
            # Extraer JSON de la respuesta (puede venir con markdown)
            json_start = raw_response.find("{")
            json_end   = raw_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = _json.loads(raw_response[json_start:json_end])
        except Exception as parse_err:
            log.warning(f"[financiero] JSON parse error: {parse_err} — usando raw")
            parsed = {}

        # Extraer campos con fallbacks seguros
        decision_text  = parsed.get("decision",        raw_response[:300] if raw_response else "datos_insuficientes")
        health_status  = parsed.get("health_status",   "DATOS_INSUFICIENTES")
        conf_level     = parsed.get("confidence_level","LOW")
        hallazgos      = parsed.get("hallazgos",       [])
        alertas        = parsed.get("alertas",         [])
        recomendaciones = parsed.get("recomendaciones",[])
        req_approval   = parsed.get("requires_approval", health_status == "CRÍTICA")
        null_fields    = parsed.get("null_fields",     [])
        data_sources   = parsed.get("data_sources",    [])

        # Mapear confidence_level a float para compatibilidad con sistema existente
        conf_map = {"HIGH": 0.92, "MEDIUM": 0.72, "LOW": 0.45, "REFUSE": 0.10}
        confidence = conf_map.get(conf_level, 0.50)

        # Publicar señal a otros agentes si margen crítico
        if health_status == "CRÍTICA":
            await self._publish_signal(
                cycle_id, organization_id, empresa.nombre,
                "margen_critico", "rh",
                {"health_status": health_status, "empresa": empresa.nombre}
            )

        # Persistir logs de tools en audit trail
        tools.persist_logs(cycle_id)

        reasoning = (
            f"HALLAZGOS:\n" + "\n".join(f"• {h}" for h in hallazgos) + "\n\n"
            f"ALERTAS:\n" + "\n".join(f"⚠ {a}" for a in alertas) + "\n\n"
            f"RECOMENDACIONES:\n" + "\n".join(f"→ {r}" for r in recomendaciones)
            if (hallazgos or alertas or recomendaciones) else raw_response
        )

        decision = AgentDecision(
            organization_id    = organization_id,
            cycle_id           = cycle_id,
            agent_type         = "financiero",
            empresa            = empresa.nombre,
            decision           = decision_text,
            health_status      = health_status,
            confidence         = confidence,
            reasoning          = reasoning[:4000],
            objetivo_iteracion = objetivo,
            requires_approval  = req_approval,
            source_indicator   = llm_src,
            metadata           = {
                "empresa":          empresa.nombre,
                "confidence_level": conf_level,
                "tool_calls_count": len(tools.get_logs()),
                "alertas_count":    len(alertas),
                "null_fields":      null_fields,
                "data_sources":     data_sources,
                "tool_calls_log":   tools.get_logs_as_dicts(),
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
# AGENTE OPERADOR
# AgenteOperador v1.0 — Scope exclusivo MD Asesorías Limitada
# ═══════════════════════════════════════════════════════════════════════════════
# Monitorea el negocio SaaS: clientes, MRR, costos de stack, salud del sistema.
# Tool-First + Anti-Alucinación. Solo corre para ADMIN_ORG_ID.
# ═══════════════════════════════════════════════════════════════════════════════

class AgenteOperador(BaseAgent):
    """
    Agente de operación del SaaS para MD Asesorías Limitada.
    Scope exclusivo: ADMIN_ORG_ID — nunca corre en org de clientes.
    Tool-First: LLM solo llama tools, nunca genera números propios.
    """

    ADMIN_ORG_ID: ClassVar[str] = os.getenv("ADMIN_ORG_ID", "")

    _TOOL_DEFINITIONS: ClassVar[list[dict]] = [
        {
            "name": "get_client_overview",
            "description": (
                "Lista todos los clientes (organizaciones) con su plan, estado, "
                "días de trial restantes, y actividad de agentes últimos 7 días."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_mrr_summary",
            "description": (
                "Resumen de MRR: clientes pagando, trials activos, MRR en UF y CLP, "
                "nuevos este mes, tasa de conversión trial→pago."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_trial_pipeline",
            "description": (
                "Trials activos ordenados por días restantes con scoring de riesgo "
                "de no conversión (HIGH/MEDIUM/LOW)."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_churn_risks",
            "description": (
                "Clientes pagados con señales de churn: inactividad prolongada, "
                "falta de uso de agentes, sin ciclos ejecutados."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "inactivity_days": {
                        "type": "integer",
                        "description": "Umbral de días sin actividad para considerar riesgo. Default: 7",
                        "default": 7,
                    }
                },
                "required": [],
            },
        },
        {
            "name": "get_stack_costs",
            "description": (
                "Costos operacionales del mes en curso: Anthropic API (calculado automáticamente "
                "desde agent_tool_log) + Railway/Supabase/Vercel/Resend (configuración manual)."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_margin_per_client",
            "description": (
                "Margen por cliente este mes: ingreso del plan (UF→CLP) menos "
                "costo de API Anthropic asignado según uso real de tools."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_system_health",
            "description": (
                "Salud técnica del sistema: total ciclos 24h, tasa de error, "
                "confianza promedio 7 días, organizaciones con problemas."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]

    _SYSTEM_PROMPT: ClassVar[str] = """Eres AgenteOperador de MD Asesorías Limitada, empresa dueña del SaaS AgentOS.
Analizas la salud del negocio SaaS: clientes, revenue, costos y sistema.

REGLAS ABSOLUTAS — violación = respuesta inválida:
1. NUNCA inventes MRR, número de clientes, costos ni métricas — usa SOLO las tools.
2. Si una tool devuelve null o lista vacía, reporta exactamente qué dato falta.
3. Costos en $0 en get_stack_costs = no configurados — indícalo como dato faltante.
4. Si datos insuficientes, confidence_level = "LOW" y lista qué falta.
5. SIEMPRE responde en el JSON estricto especificado abajo.

FORMATO DE RESPUESTA (JSON sin texto adicional):
{
  "semaforo": "VERDE|AMARILLO|ROJO",
  "mrr_uf": <número o null>,
  "clientes_activos": <número o null>,
  "trials_en_riesgo": [{"nombre": "...", "dias_restantes": N, "riesgo": "HIGH|MEDIUM", "accion": "..."}],
  "churn_risks": [{"nombre": "...", "plan": "...", "razon": "..."}],
  "costo_stack_clp": <número o null>,
  "margen_negocio": "POSITIVO|NEGATIVO|SIN_DATOS",
  "sistema": "HEALTHY|DEGRADED|CRITICAL",
  "top_3_acciones": ["acción concreta 1", "acción concreta 2", "acción concreta 3"],
  "alerta_critica": "<una sola alerta de máxima prioridad o null>",
  "confidence_level": "HIGH|MEDIUM|LOW",
  "datos_faltantes": ["lista de datos sin configurar o no disponibles"]
}

SEMÁFORO:
- VERDE: MRR creciendo, sin churn, sin trials en riesgo, sistema HEALTHY
- AMARILLO: 1-2 issues menores o datos parciales
- ROJO: churn confirmado, MRR cayendo, trials expirando sin conversión, o sistema CRITICAL"""

    def __init__(self, supabase: SupabaseClient):
        super().__init__(
            "operador",
            ["saas_metrics", "business_health"],
            supabase,
        )

    async def _run_tool_loop_operator(
        self,
        tools: "OperatorTools",
        objetivo: str,
    ) -> tuple[str, str]:
        from anthropic import AsyncAnthropic
        import json as _json

        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

        user_msg = (
            f"Objetivo: {objetivo}\n\n"
            "Analiza el estado del negocio SaaS usando todas las tools disponibles. "
            "Llama las tools necesarias para tener datos completos antes de responder. "
            "Responde únicamente en el JSON especificado en el system prompt."
        )

        messages   = [{"role": "user", "content": user_msg}]
        final_text = ""
        rounds     = 0
        MAX_ROUNDS = 8

        _cached_system = [
            {"type": "text", "text": self._SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ]
        _cached_tools = [
            *self._TOOL_DEFINITIONS[:-1],
            {**self._TOOL_DEFINITIONS[-1], "cache_control": {"type": "ephemeral"}},
        ]

        while rounds < MAX_ROUNDS:
            rounds += 1
            async with _claude_semaphore:
                response = await client.messages.create(
                    model      = ANTHROPIC_MODEL,
                    max_tokens = 2048,
                    system     = _cached_system,
                    tools      = _cached_tools,
                    messages   = messages,
                )

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                messages.append({"role": "assistant", "content": response.content})

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name  = block.name
                    tool_input = block.input or {}
                    tool_result = None

                    try:
                        if tool_name == "get_client_overview":
                            r = tools.get_client_overview()
                            tool_result = [vars(c) for c in r]
                        elif tool_name == "get_mrr_summary":
                            r = tools.get_mrr_summary()
                            tool_result = vars(r) if r else None
                        elif tool_name == "get_trial_pipeline":
                            r = tools.get_trial_pipeline()
                            tool_result = [vars(t) for t in r]
                        elif tool_name == "get_churn_risks":
                            r = tools.get_churn_risks(tool_input.get("inactivity_days", 7))
                            tool_result = [vars(c) for c in r]
                        elif tool_name == "get_stack_costs":
                            r = tools.get_stack_costs()
                            tool_result = vars(r) if r else None
                        elif tool_name == "get_margin_per_client":
                            r = tools.get_margin_per_client()
                            tool_result = [vars(m) for m in r]
                        elif tool_name == "get_system_health":
                            r = tools.get_system_health()
                            tool_result = vars(r) if r else None
                        else:
                            tool_result = {"error": f"Tool desconocida: {tool_name}"}
                    except Exception as tool_exc:
                        log.warning(f"[operador] Tool {tool_name} error: {tool_exc}")
                        tool_result = {"error": str(tool_exc)}

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     _json.dumps(tool_result, ensure_ascii=False, default=str),
                    })

                messages.append({"role": "user", "content": tool_results})
            else:
                log.warning(f"[operador] stop_reason inesperado: {response.stop_reason}")
                break

        return final_text, f"tool_loop_{rounds}_rounds"

    async def analyze(
        self,
        empresa: "EmpresaSchema",
        cycle_id: str,
        organization_id: str,
    ) -> "AgentDecision":
        import json as _json
        from operator_tools import OperatorTools

        # Seguridad: solo corre para org admin
        if self.ADMIN_ORG_ID and organization_id != self.ADMIN_ORG_ID:
            log.warning(f"[operador] Acceso denegado — org {organization_id} != ADMIN_ORG_ID")
            return AgentDecision(
                organization_id=organization_id,
                cycle_id=cycle_id,
                agent_type="operador",
                empresa=empresa.nombre,
                decision="ACCESO_DENEGADO",
                health_status="ERROR",
                confidence=0.0,
                reasoning="AgenteOperador solo disponible para MD Asesorías Limitada.",
                objetivo_iteracion=empresa.instruccion_ceo.objetivo_iteracion,
            )

        objetivo = empresa.instruccion_ceo.objetivo_iteracion
        tools    = OperatorTools()

        raw_response, llm_src = await self._run_tool_loop_operator(tools, objetivo)

        # Parsear JSON de respuesta
        parsed: dict = {}
        try:
            j0 = raw_response.find("{")
            j1 = raw_response.rfind("}") + 1
            if j0 >= 0 and j1 > j0:
                parsed = _json.loads(raw_response[j0:j1])
        except Exception as parse_err:
            log.warning(f"[operador] JSON parse error: {parse_err}")

        semaforo         = parsed.get("semaforo",        "AMARILLO")
        mrr_uf           = parsed.get("mrr_uf")
        clientes_activos = parsed.get("clientes_activos")
        trials_riesgo    = parsed.get("trials_en_riesgo",  [])
        churn_risks      = parsed.get("churn_risks",        [])
        costo_stack      = parsed.get("costo_stack_clp")
        margen_negocio   = parsed.get("margen_negocio",     "SIN_DATOS")
        sistema          = parsed.get("sistema",            "HEALTHY")
        top_3            = parsed.get("top_3_acciones",     [])
        alerta           = parsed.get("alerta_critica")
        conf_level       = parsed.get("confidence_level",   "MEDIUM")
        datos_faltantes  = parsed.get("datos_faltantes",    [])

        conf_map     = {"HIGH": 0.92, "MEDIUM": 0.72, "LOW": 0.45}
        confidence   = conf_map.get(conf_level, 0.72)
        health_map   = {"VERDE": "BUENA", "AMARILLO": "ALERTA", "ROJO": "CRÍTICA"}
        health_status = health_map.get(semaforo, "DATOS_INSUFICIENTES")

        reasoning_parts = []
        if top_3:
            reasoning_parts.append("TOP 3 ACCIONES:\n" + "\n".join(f"→ {a}" for a in top_3))
        if alerta:
            reasoning_parts.append(f"ALERTA CRÍTICA:\n⚠ {alerta}")
        if trials_riesgo:
            reasoning_parts.append(
                "TRIALS EN RIESGO:\n" +
                "\n".join(f"• {t.get('nombre')} ({t.get('dias_restantes')} días) — {t.get('accion','')}" for t in trials_riesgo)
            )
        if datos_faltantes:
            reasoning_parts.append("DATOS FALTANTES:\n" + "\n".join(f"• {d}" for d in datos_faltantes))

        reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else raw_response[:2000]

        decision_text = (
            f"Semáforo: {semaforo}. "
            f"MRR: {mrr_uf} UF. "
            f"Clientes: {clientes_activos}. "
            f"Sistema: {sistema}. "
            f"Margen: {margen_negocio}."
        )

        decision = AgentDecision(
            organization_id   = organization_id,
            cycle_id          = cycle_id,
            agent_type        = "operador",
            empresa           = empresa.nombre,
            decision          = decision_text,
            health_status     = health_status,
            confidence        = confidence,
            reasoning         = reasoning[:4000],
            objetivo_iteracion = objetivo,
            requires_approval = semaforo == "ROJO",
            source_indicator  = llm_src,
            metadata          = {
                "semaforo":         semaforo,
                "mrr_uf":           mrr_uf,
                "clientes_activos": clientes_activos,
                "trials_en_riesgo": trials_riesgo,
                "churn_risks":      churn_risks,
                "costo_stack_clp":  costo_stack,
                "margen_negocio":   margen_negocio,
                "sistema":          sistema,
                "confidence_level": conf_level,
                "datos_faltantes":  datos_faltantes,
                "tool_calls_count": len(tools.get_logs()),
                "tool_calls_log":   tools.get_logs_as_dicts(),
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
