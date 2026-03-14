"""
operator_tools.py — Herramientas del AgenteOperador
=====================================================
Scope exclusivo: MD Asesorías Limitada (ADMIN_ORG_ID).
Lectura cross-tenant con service role key.

Tools:
  get_client_overview()      → estado de todas las organizaciones
  get_mrr_summary()          → MRR, trials, conversión
  get_trial_pipeline()       → trials activos con scoring de riesgo
  get_churn_risks()          → clientes pagados con señales de fuga
  get_stack_costs()          → costos Anthropic (auto) + stack (manual)
  get_margin_per_client()    → ingreso plan vs costo API por cliente
  get_system_health()        → salud del sistema últimas 24h/7d
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from supabase import create_client, Client as SupabaseClient

logger = logging.getLogger("operator_tools")

SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Precios de planes en UF
PLAN_PRICES_UF: dict[str, float] = {
    "starter":    2.0,
    "empresa":    3.5,
    "enterprise": 10.0,
    "trial":      0.0,
}

DEFAULT_UF_CLP  = 38_000
DEFAULT_USD_CLP = 950

# Costos Anthropic claude-sonnet-4-6 por token
_INPUT_COST_PER_TOKEN  = 3.0  / 1_000_000   # $3  / MTok
_OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000   # $15 / MTok
_AVG_INPUT_TOKENS      = 1_500
_AVG_OUTPUT_TOKENS     =   500


# ── Dataclasses de respuesta ──────────────────────────────────────────────────

@dataclass
class ClientStatus:
    org_id:                    str
    name:                      str
    plan_type:                 str
    status:                    str
    trial_days_remaining:      Optional[int]
    days_since_last_activity:  Optional[float]
    total_agent_cycles:        int
    cycles_last_7d:            int
    registered_at:             str


@dataclass
class MRRSummary:
    paying_clients:        int
    trial_clients:         int
    total_clients:         int
    mrr_uf:                float
    mrr_clp:               int
    new_paying_30d:        int
    new_trials_30d:        int
    trial_conversion_rate: Optional[float]


@dataclass
class TrialStatus:
    org_id:                str
    name:                  str
    trial_days_remaining:  int
    cycles_last_7d:        int
    risk_level:            str   # HIGH / MEDIUM / LOW


@dataclass
class ChurnRisk:
    org_id:                    str
    name:                      str
    plan_type:                 str
    days_since_last_activity:  float
    risk_reason:               str
    risk_level:                str  # HIGH / MEDIUM / LOW


@dataclass
class StackCosts:
    anthropic_usd:   float
    anthropic_clp:   int
    railway_clp:     int
    supabase_clp:    int
    vercel_clp:      int
    resend_clp:      int
    total_clp:       int
    automation_note: str   # indica qué costos son auto vs manuales


@dataclass
class ClientMargin:
    org_id:        str
    name:          str
    plan_type:     str
    revenue_uf:    float
    revenue_clp:   int
    api_cost_clp:  int
    margin_clp:    int
    margin_pct:    float


@dataclass
class SystemHealth:
    total_cycles_24h:      int
    failed_cycles_24h:     int
    avg_confidence_7d:     float
    orgs_with_issues_24h:  int
    status:                str   # HEALTHY / DEGRADED / CRITICAL


@dataclass
class ToolCallLog:
    tool_name:   str
    duration_ms: int
    rows:        int
    source:      str = "supabase"


# ── Clase principal ───────────────────────────────────────────────────────────

class OperatorTools:
    """
    Herramientas privilegiadas del AgenteOperador.
    Lee datos de TODAS las organizaciones (cross-tenant).
    Requiere SUPABASE_SERVICE_ROLE_KEY.
    Solo instanciar desde AgenteOperador con org_id == ADMIN_ORG_ID.
    """

    def __init__(self, supabase_service: Optional[SupabaseClient] = None):
        if supabase_service:
            self._db = supabase_service
        else:
            self._db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        self._logs:    list[ToolCallLog] = []
        self._uf_clp:  int = self._load_config_int("uf_clp_value",  DEFAULT_UF_CLP)
        self._usd_clp: int = self._load_config_int("usd_clp_value", DEFAULT_USD_CLP)

    # ── Config helpers ────────────────────────────────────────────────────────

    def _load_config_int(self, key: str, default: int) -> int:
        try:
            r = (
                self._db.table("operator_stack_config")
                .select("value_int")
                .eq("key", key)
                .single()
                .execute()
            )
            return r.data.get("value_int") or default if r.data else default
        except Exception:
            return default

    def _load_manual_costs(self) -> dict[str, int]:
        services = {"railway": 0, "supabase": 0, "vercel": 0, "resend": 0}
        try:
            rows = (
                self._db.table("operator_stack_config")
                .select("service_name,monthly_cost_clp")
                .execute()
                .data or []
            )
            for row in rows:
                svc = (row.get("service_name") or "").lower()
                if svc in services:
                    services[svc] = row.get("monthly_cost_clp") or 0
        except Exception:
            pass
        return services

    def _track(self, tool_name: str, t0: float, rows: int) -> None:
        self._logs.append(ToolCallLog(
            tool_name=tool_name,
            duration_ms=int((time.time() - t0) * 1000),
            rows=rows,
        ))

    @staticmethod
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    # ── Tools ─────────────────────────────────────────────────────────────────

    def get_client_overview(self) -> list[ClientStatus]:
        """Todas las organizaciones: plan, estado, actividad y trial restante."""
        t0 = time.time()
        try:
            orgs = (
                self._db.table("organizations")
                .select("id,name,plan_type,status,trial_end,created_at")
                .execute()
                .data or []
            )

            # Actividad de agentes por org
            acts_raw = (
                self._db.table("agent_decisions")
                .select("organization_id,created_at")
                .execute()
                .data or []
            )
            now         = datetime.now(timezone.utc)
            cutoff_7d   = now - timedelta(days=7)
            last_act:   dict[str, str] = {}
            cycles_7d:  dict[str, int] = {}
            total_cyc:  dict[str, int] = {}

            for a in acts_raw:
                oid = a["organization_id"]
                ts  = a["created_at"]
                total_cyc[oid] = total_cyc.get(oid, 0) + 1
                if oid not in last_act or ts > last_act[oid]:
                    last_act[oid] = ts
                dt = self._parse_dt(ts)
                if dt and dt > cutoff_7d:
                    cycles_7d[oid] = cycles_7d.get(oid, 0) + 1

            result: list[ClientStatus] = []
            for o in orgs:
                oid = o["id"]

                # Días trial restantes
                trial_days = None
                te = self._parse_dt(o.get("trial_end"))
                if te:
                    trial_days = max(0, (te - now).days)

                # Días sin actividad
                days_inactive = None
                la = self._parse_dt(last_act.get(oid))
                if la:
                    days_inactive = round((now - la).total_seconds() / 86400, 1)

                result.append(ClientStatus(
                    org_id=oid,
                    name=o["name"],
                    plan_type=o.get("plan_type", "unknown"),
                    status=o.get("status", "unknown"),
                    trial_days_remaining=trial_days,
                    days_since_last_activity=days_inactive,
                    total_agent_cycles=total_cyc.get(oid, 0),
                    cycles_last_7d=cycles_7d.get(oid, 0),
                    registered_at=o.get("created_at", ""),
                ))

            self._track("get_client_overview", t0, len(result))
            return result

        except Exception as e:
            logger.error(f"[operator] get_client_overview: {e}")
            self._track("get_client_overview", t0, 0)
            return []

    def get_mrr_summary(self) -> Optional[MRRSummary]:
        """MRR actual, clientes pagando, trials, nuevos este mes, tasa conversión."""
        t0 = time.time()
        try:
            orgs = (
                self._db.table("organizations")
                .select("plan_type,status,created_at")
                .execute()
                .data or []
            )

            now        = datetime.now(timezone.utc)
            cutoff_30d = now - timedelta(days=30)

            paying  = [o for o in orgs if o["plan_type"] not in ("trial",) and o["status"] == "active"]
            trials  = [o for o in orgs if o["plan_type"] == "trial" and o["status"] == "active"]
            churned = [o for o in orgs if o["status"] in ("cancelled", "churned")]

            mrr_uf  = sum(PLAN_PRICES_UF.get(o["plan_type"], 0.0) for o in paying)
            mrr_clp = int(mrr_uf * self._uf_clp)

            def is_recent(o: dict) -> bool:
                dt = self._parse_dt(o.get("created_at"))
                return dt is not None and dt > cutoff_30d

            new_paying_30d = sum(1 for o in paying if is_recent(o))
            new_trials_30d = sum(1 for o in trials if is_recent(o))

            total_outcomes = len(paying) + len(churned)
            conv_rate = round(len(paying) / total_outcomes, 2) if total_outcomes > 0 else None

            result = MRRSummary(
                paying_clients=len(paying),
                trial_clients=len(trials),
                total_clients=len(orgs),
                mrr_uf=round(mrr_uf, 1),
                mrr_clp=mrr_clp,
                new_paying_30d=new_paying_30d,
                new_trials_30d=new_trials_30d,
                trial_conversion_rate=conv_rate,
            )
            self._track("get_mrr_summary", t0, len(orgs))
            return result

        except Exception as e:
            logger.error(f"[operator] get_mrr_summary: {e}")
            self._track("get_mrr_summary", t0, 0)
            return None

    def get_trial_pipeline(self) -> list[TrialStatus]:
        """Trials activos con días restantes y scoring de riesgo de no conversión."""
        t0 = time.time()
        try:
            clients = self.get_client_overview()
            result: list[TrialStatus] = []

            for c in clients:
                if c.plan_type != "trial" or c.status != "active":
                    continue
                if c.trial_days_remaining is None:
                    continue

                # Scoring de riesgo
                risk = "LOW"
                if c.trial_days_remaining <= 2:
                    risk = "HIGH"
                elif c.trial_days_remaining <= 5 and c.cycles_last_7d == 0:
                    risk = "HIGH"
                elif c.cycles_last_7d == 0:
                    risk = "MEDIUM"
                elif c.days_since_last_activity is not None and c.days_since_last_activity > 3:
                    risk = "MEDIUM"

                result.append(TrialStatus(
                    org_id=c.org_id,
                    name=c.name,
                    trial_days_remaining=c.trial_days_remaining,
                    cycles_last_7d=c.cycles_last_7d,
                    risk_level=risk,
                ))

            result.sort(key=lambda x: x.trial_days_remaining)
            self._track("get_trial_pipeline", t0, len(result))
            return result

        except Exception as e:
            logger.error(f"[operator] get_trial_pipeline: {e}")
            self._track("get_trial_pipeline", t0, 0)
            return []

    def get_churn_risks(self, inactivity_days: int = 7) -> list[ChurnRisk]:
        """Clientes pagados con señales de churn: inactividad o sin uso de agentes."""
        t0 = time.time()
        try:
            clients = self.get_client_overview()
            result: list[ChurnRisk] = []

            for c in clients:
                if c.status != "active" or c.plan_type == "trial":
                    continue

                reasons: list[str] = []
                risk = "LOW"

                if c.days_since_last_activity is not None:
                    if c.days_since_last_activity > 14:
                        reasons.append(f"Sin actividad {int(c.days_since_last_activity)} días")
                        risk = "HIGH"
                    elif c.days_since_last_activity > inactivity_days:
                        reasons.append(f"Baja actividad ({int(c.days_since_last_activity)} días)")
                        risk = "MEDIUM"

                if c.cycles_last_7d == 0 and c.total_agent_cycles > 0:
                    reasons.append("No usó agentes esta semana")
                    if risk == "LOW":
                        risk = "MEDIUM"

                if c.total_agent_cycles == 0:
                    reasons.append("Nunca ejecutó un ciclo de agente")
                    if risk == "LOW":
                        risk = "MEDIUM"

                if not reasons:
                    continue

                result.append(ChurnRisk(
                    org_id=c.org_id,
                    name=c.name,
                    plan_type=c.plan_type,
                    days_since_last_activity=c.days_since_last_activity or 0.0,
                    risk_reason="; ".join(reasons),
                    risk_level=risk,
                ))

            result.sort(key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x.risk_level])
            self._track("get_churn_risks", t0, len(result))
            return result

        except Exception as e:
            logger.error(f"[operator] get_churn_risks: {e}")
            self._track("get_churn_risks", t0, 0)
            return []

    def get_stack_costs(self) -> Optional[StackCosts]:
        """
        Costos operacionales del mes en curso.
        Anthropic: estimación automática desde agent_tool_log.
        Resto: configuración manual en operator_stack_config.
        """
        t0 = time.time()
        try:
            now         = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Llamadas Anthropic este mes desde agent_tool_log
            calls_this_month = 0
            exact_input_tokens  = 0
            exact_output_tokens = 0
            try:
                logs = (
                    self._db.table("agent_tool_log")
                    .select("input_tokens,output_tokens")
                    .gte("executed_at", month_start.isoformat())
                    .execute()
                    .data or []
                )
                calls_this_month = len(logs)

                # Usar tokens exactos si están disponibles, si no: estimación
                for row in logs:
                    exact_input_tokens  += row.get("input_tokens")  or _AVG_INPUT_TOKENS
                    exact_output_tokens += row.get("output_tokens") or _AVG_OUTPUT_TOKENS

            except Exception:
                pass

            anthropic_usd = round(
                exact_input_tokens  * _INPUT_COST_PER_TOKEN +
                exact_output_tokens * _OUTPUT_COST_PER_TOKEN,
                4
            )
            anthropic_clp = int(anthropic_usd * self._usd_clp)

            manual = self._load_manual_costs()
            missing = [k for k, v in manual.items() if v == 0]

            total_clp = (
                anthropic_clp
                + manual["railway"]
                + manual["supabase"]
                + manual["vercel"]
                + manual["resend"]
            )

            note = f"Anthropic: automático ({calls_this_month} llamadas). "
            if missing:
                note += f"Sin configurar: {', '.join(missing)} — actualizar en operator_stack_config."

            result = StackCosts(
                anthropic_usd=anthropic_usd,
                anthropic_clp=anthropic_clp,
                railway_clp=manual["railway"],
                supabase_clp=manual["supabase"],
                vercel_clp=manual["vercel"],
                resend_clp=manual["resend"],
                total_clp=total_clp,
                automation_note=note,
            )
            self._track("get_stack_costs", t0, calls_this_month)
            return result

        except Exception as e:
            logger.error(f"[operator] get_stack_costs: {e}")
            self._track("get_stack_costs", t0, 0)
            return None

    def get_margin_per_client(self) -> list[ClientMargin]:
        """Margen por cliente: ingreso plan − costo API Anthropic asignado este mes."""
        t0 = time.time()
        try:
            clients      = self.get_client_overview()
            now          = datetime.now(timezone.utc)
            month_start  = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Tokens por org este mes
            api_by_org: dict[str, tuple[int, int]] = {}  # org_id → (input, output)
            try:
                logs = (
                    self._db.table("agent_tool_log")
                    .select("organization_id,input_tokens,output_tokens")
                    .gte("executed_at", month_start.isoformat())
                    .execute()
                    .data or []
                )
                for row in logs:
                    oid = row["organization_id"]
                    inp = row.get("input_tokens")  or _AVG_INPUT_TOKENS
                    out = row.get("output_tokens") or _AVG_OUTPUT_TOKENS
                    prev = api_by_org.get(oid, (0, 0))
                    api_by_org[oid] = (prev[0] + inp, prev[1] + out)
            except Exception:
                pass

            result: list[ClientMargin] = []
            for c in clients:
                if c.plan_type == "trial":
                    continue

                revenue_uf  = PLAN_PRICES_UF.get(c.plan_type, 0.0)
                revenue_clp = int(revenue_uf * self._uf_clp)

                inp, out    = api_by_org.get(c.org_id, (0, 0))
                api_usd     = inp * _INPUT_COST_PER_TOKEN + out * _OUTPUT_COST_PER_TOKEN
                api_clp     = int(api_usd * self._usd_clp)

                margin_clp  = revenue_clp - api_clp
                margin_pct  = round(margin_clp / revenue_clp * 100, 1) if revenue_clp > 0 else 0.0

                result.append(ClientMargin(
                    org_id=c.org_id,
                    name=c.name,
                    plan_type=c.plan_type,
                    revenue_uf=revenue_uf,
                    revenue_clp=revenue_clp,
                    api_cost_clp=api_clp,
                    margin_clp=margin_clp,
                    margin_pct=margin_pct,
                ))

            result.sort(key=lambda x: x.margin_pct)
            self._track("get_margin_per_client", t0, len(result))
            return result

        except Exception as e:
            logger.error(f"[operator] get_margin_per_client: {e}")
            self._track("get_margin_per_client", t0, 0)
            return []

    def get_system_health(self) -> Optional[SystemHealth]:
        """Salud del sistema: ciclos de agentes últimas 24h, errores, confianza 7d."""
        t0 = time.time()
        try:
            now       = datetime.now(timezone.utc)
            cut_24h   = (now - timedelta(hours=24)).isoformat()
            cut_7d    = (now - timedelta(days=7)).isoformat()

            decisions = (
                self._db.table("agent_decisions")
                .select("organization_id,confidence,health_status,created_at")
                .gte("created_at", cut_7d)
                .execute()
                .data or []
            )

            recent    = [d for d in decisions if d["created_at"] >= cut_24h]
            total_24h = len(recent)

            def is_failed(d: dict) -> bool:
                conf = d.get("confidence")
                return (conf is not None and conf < 0.3) or d.get("health_status") in ("ERROR", "REFUSE")

            failed_24h         = sum(1 for d in recent if is_failed(d))
            orgs_with_issues   = len({d["organization_id"] for d in recent if is_failed(d)})

            confs_7d   = [d["confidence"] for d in decisions if d.get("confidence") is not None]
            avg_conf   = round(sum(confs_7d) / len(confs_7d), 3) if confs_7d else 0.0

            fail_rate  = failed_24h / total_24h if total_24h > 0 else 0.0
            if fail_rate > 0.30 or avg_conf < 0.50:
                status = "CRITICAL"
            elif fail_rate > 0.10 or avg_conf < 0.70:
                status = "DEGRADED"
            else:
                status = "HEALTHY"

            result = SystemHealth(
                total_cycles_24h=total_24h,
                failed_cycles_24h=failed_24h,
                avg_confidence_7d=avg_conf,
                orgs_with_issues_24h=orgs_with_issues,
                status=status,
            )
            self._track("get_system_health", t0, len(decisions))
            return result

        except Exception as e:
            logger.error(f"[operator] get_system_health: {e}")
            self._track("get_system_health", t0, 0)
            return None

    # ── Audit log helpers ─────────────────────────────────────────────────────

    def get_logs(self) -> list[ToolCallLog]:
        return self._logs.copy()

    def get_logs_as_dicts(self) -> list[dict]:
        return [vars(l) for l in self._logs]
