"""
financial_tools.py
==================
Motor de verdad del AgenteFinanciero.

Principio fundamental: el LLM nunca genera números.
Las tools traen datos reales desde la DB; el LLM solo interpreta.

Cada tool:
  - Ejecuta una query SQL pre-escrita y auditada (nunca generada por el LLM)
  - Retorna un dataclass tipado (nunca dicts libres)
  - Loguea su ejecución en agent_tool_log (audit trail inmutable)
  - Declara explícitamente cuando no hay datos suficientes (None / lista vacía)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from supabase import Client as SupabaseClient

log = logging.getLogger("financial_tools")

# ── Umbrales (configurables por org en el futuro) ─────────────────────────────
MARGIN_ALERT_THRESHOLD   = 0.15   # Alerta si desviación de margen > 15%
OC_ANOMALY_THRESHOLD     = 0.20   # Alerta si precio OC > historial × 1.20
OVERDUE_MIN_DAYS         = 1      # Considerar vencido desde día 1
CASHFLOW_HORIZON_DAYS    = 90     # Proyección de flujo a 90 días


# ── Output Schemas (tipados, nunca dicts libres) ──────────────────────────────

@dataclass
class ProjectMargin:
    project_id:            str
    project_name:          str
    cliente:               str
    presupuesto_ofertado:  float
    costo_comprometido:    float
    costo_ejecutado:       float
    margen_estimado_pct:   Optional[float]   # None si no hay presupuesto
    margen_real_pct:       Optional[float]   # None si no hay presupuesto
    desviacion_pct:        Optional[float]   # None si datos insuficientes
    alerta:                bool
    data_source:           str = "v_project_margins"


@dataclass
class OverduePayment:
    id:                       str
    proyecto_id:              str
    cliente:                  str
    descripcion:              str
    monto:                    float
    fecha_emision:            Optional[str]
    fecha_vencimiento:        Optional[str]
    dias_vencido:             int
    historial_dias_promedio:  Optional[float]   # None si no hay historial
    n_pagos_historicos:       int
    data_source:              str = "v_overdue_payments"


@dataclass
class OcAnomaly:
    oc_id:                        str
    oc_numero:                    Optional[str]
    proveedor:                    str
    item_descripcion:             str
    categoria:                    Optional[str]
    precio_actual:                float
    precio_historico_promedio:    float
    desviacion_pct:               float
    n_oc_historial:               int
    estado:                       str
    requiere_aprobacion:          bool = True
    data_source:                  str  = "v_oc_price_anomalies"


@dataclass
class CashflowWeek:
    periodo:               str
    periodo_inicio:        str
    ingresos_esperados:    float
    egresos_esperados:     float
    saldo_neto:            float
    es_deficit:            bool
    n_docs_ingreso:        int
    n_docs_egreso:         int
    data_source:           str = "v_cashflow_projection"


@dataclass
class BudgetPartida:
    partida:              str
    monto_presupuestado:  Optional[float]
    monto_ejecutado:      float
    variacion_pct:        Optional[float]
    en_alerta:            bool


@dataclass
class BudgetVsActual:
    project_id:           str
    project_name:         str
    partidas:             list[BudgetPartida]
    total_presupuestado:  Optional[float]
    total_ejecutado:      float
    variacion_total_pct:  Optional[float]
    partidas_en_alerta:   list[str]
    data_source:          str = "v_budget_vs_actual"


@dataclass
class ToolCallLog:
    tool_name:       str
    inputs:          dict
    outputs_summary: str
    rows_returned:   int
    executed_at:     str
    duration_ms:     int
    data_source:     str
    error:           Optional[str] = None


# ── FinancialTools ────────────────────────────────────────────────────────────

class FinancialTools:
    """
    Motor de verdad del AgenteFinanciero.

    REGLA ABSOLUTA: ningún método calcula ni estima valores que no vengan
    directamente de la base de datos. Si los datos no existen, retorna
    None o lista vacía — nunca un valor estimado.
    """

    def __init__(self, supabase: SupabaseClient, organization_id: str):
        self.supabase        = supabase
        self.organization_id = organization_id
        self._logs: list[ToolCallLog] = []

    # ── Utilidades internas ───────────────────────────────────────────────────

    def _now_ms(self) -> datetime:
        return datetime.now(timezone.utc)

    def _elapsed_ms(self, t0: datetime) -> int:
        return int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    def _log(
        self, tool: str, inputs: dict, rows: int,
        summary: str, ms: int, source: str, error: str | None = None
    ) -> None:
        self._logs.append(ToolCallLog(
            tool_name=tool, inputs=inputs, outputs_summary=summary,
            rows_returned=rows, executed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=ms, data_source=source, error=error,
        ))
        if error:
            log.warning(f"[financial_tools:{tool}] ERROR — {error}")
        else:
            log.info(f"[financial_tools:{tool}] {rows} filas — {summary} ({ms}ms)")

    def get_logs(self) -> list[ToolCallLog]:
        return list(self._logs)

    def get_logs_as_dicts(self) -> list[dict]:
        return [
            {
                "tool_name":       l.tool_name,
                "inputs":          l.inputs,
                "outputs_summary": l.outputs_summary,
                "rows_returned":   l.rows_returned,
                "executed_at":     l.executed_at,
                "duration_ms":     l.duration_ms,
                "data_source":     l.data_source,
                "error":           l.error,
            }
            for l in self._logs
        ]

    def persist_logs(self, cycle_id: str) -> None:
        """Persiste el audit trail en agent_tool_log (append-only)."""
        if not self._logs:
            return
        try:
            rows = [
                {
                    "organization_id": self.organization_id,
                    "cycle_id":        cycle_id,
                    "tool_name":       l.tool_name,
                    "inputs":          l.inputs,
                    "outputs_summary": l.outputs_summary,
                    "rows_returned":   l.rows_returned,
                    "data_source":     l.data_source,
                    "duration_ms":     l.duration_ms,
                    "executed_at":     l.executed_at,
                }
                for l in self._logs
            ]
            self.supabase.table("agent_tool_log").insert(rows).execute()
        except Exception as exc:
            log.warning(f"[financial_tools] persist_logs error: {exc}")

    # ── Tool 1: Márgenes por Proyecto ─────────────────────────────────────────

    def get_project_margins(
        self, project_id: str | None = None
    ) -> list[ProjectMargin]:
        """
        Retorna el margen real vs ofertado por proyecto.
        Fuente: v_project_margins (projects + ordenes_compra + transactions).
        NUNCA estima — si faltan datos retorna None en los campos afectados.
        """
        t0 = self._now_ms()
        inputs = {"project_id": project_id, "organization_id": self.organization_id}
        try:
            q = (
                self.supabase.table("v_project_margins")
                .select("*")
                .eq("organization_id", self.organization_id)
            )
            if project_id:
                q = q.eq("project_id", project_id)
            rows = (q.execute().data or [])

            margins: list[ProjectMargin] = []
            for r in rows:
                ofertado     = float(r.get("presupuesto_ofertado") or 0)
                comprometido = float(r.get("costo_comprometido")   or 0)
                ejecutado    = float(r.get("costo_ejecutado")      or 0)

                m_est  = (ofertado - comprometido) / ofertado if ofertado > 0 else None
                m_real = (ofertado - ejecutado)    / ofertado if ofertado > 0 else None
                desv   = (m_real - m_est) if (m_real is not None and m_est is not None) else None
                alerta = (desv is not None and abs(desv) > MARGIN_ALERT_THRESHOLD)

                margins.append(ProjectMargin(
                    project_id           = str(r.get("project_id", "")),
                    project_name         = str(r.get("project_name", "")),
                    cliente              = str(r.get("cliente", "")),
                    presupuesto_ofertado = ofertado,
                    costo_comprometido   = comprometido,
                    costo_ejecutado      = ejecutado,
                    margen_estimado_pct  = round(m_est,  4) if m_est  is not None else None,
                    margen_real_pct      = round(m_real, 4) if m_real is not None else None,
                    desviacion_pct       = round(desv,   4) if desv   is not None else None,
                    alerta               = alerta,
                ))

            alertas = sum(1 for m in margins if m.alerta)
            ms = self._elapsed_ms(t0)
            self._log(
                "get_project_margins", inputs, len(margins),
                f"{len(margins)} proyectos | {alertas} en alerta de margen",
                ms, "v_project_margins"
            )
            return margins

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_project_margins", inputs, 0, "", ms, "v_project_margins", str(exc))
            return []

    # ── Tool 2: CxC Vencidas ──────────────────────────────────────────────────

    def get_overdue_payments(
        self, days_threshold: int = OVERDUE_MIN_DAYS
    ) -> list[OverduePayment]:
        """
        Retorna estados de pago vencidos con contexto del cliente.
        Fuente: v_overdue_payments.
        Si no hay vencidos: retorna lista vacía (nunca inventa deuda).
        """
        t0 = self._now_ms()
        inputs = {"days_threshold": days_threshold, "organization_id": self.organization_id}
        try:
            rows = (
                self.supabase.table("v_overdue_payments")
                .select("*")
                .eq("organization_id", self.organization_id)
                .gte("dias_vencido", days_threshold)
                .order("monto", desc=True)
                .execute()
                .data or []
            )

            payments = [
                OverduePayment(
                    id                      = str(r.get("id", "")),
                    proyecto_id             = str(r.get("proyecto_id", "")),
                    cliente                 = str(r.get("cliente", "")),
                    descripcion             = str(r.get("descripcion", "")),
                    monto                   = float(r.get("monto") or 0),
                    fecha_emision           = r.get("fecha_emision"),
                    fecha_vencimiento       = r.get("fecha_vencimiento"),
                    dias_vencido            = int(r.get("dias_vencido") or 0),
                    historial_dias_promedio = (
                        float(r["historial_dias_promedio"])
                        if r.get("historial_dias_promedio") is not None else None
                    ),
                    n_pagos_historicos      = int(r.get("n_pagos_historicos") or 0),
                )
                for r in rows
            ]

            total_monto = sum(p.monto for p in payments)
            ms = self._elapsed_ms(t0)
            self._log(
                "get_overdue_payments", inputs, len(payments),
                f"{len(payments)} vencidos | Total: ${total_monto:,.0f} CLP",
                ms, "v_overdue_payments"
            )
            return payments

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_overdue_payments", inputs, 0, "", ms, "v_overdue_payments", str(exc))
            return []

    # ── Tool 3: Anomalías de OC ───────────────────────────────────────────────

    def get_oc_anomalies(
        self, oc_id: str | None = None
    ) -> list[OcAnomaly]:
        """
        Detecta OC con precio superior al histórico del mismo ítem/proveedor.
        Requiere mínimo 3 OC históricas para evitar falsos positivos.
        Si no hay historial suficiente: retorna lista vacía.
        """
        t0 = self._now_ms()
        inputs = {"oc_id": oc_id, "organization_id": self.organization_id}
        try:
            q = (
                self.supabase.table("v_oc_price_anomalies")
                .select("*")
                .eq("organization_id", self.organization_id)
                .order("desviacion_pct", desc=True)
            )
            if oc_id:
                q = q.eq("oc_id", oc_id)
            rows = (q.execute().data or [])

            anomalies = [
                OcAnomaly(
                    oc_id                     = str(r.get("oc_id", "")),
                    oc_numero                 = r.get("oc_numero"),
                    proveedor                 = str(r.get("proveedor", "")),
                    item_descripcion          = str(r.get("item_descripcion", "")),
                    categoria                 = r.get("categoria"),
                    precio_actual             = float(r.get("precio_actual") or 0),
                    precio_historico_promedio = float(r.get("precio_historico_promedio") or 0),
                    desviacion_pct            = float(r.get("desviacion_pct") or 0),
                    n_oc_historial            = int(r.get("n_oc_historial") or 0),
                    estado                    = str(r.get("estado", "")),
                    requiere_aprobacion       = True,
                )
                for r in rows
            ]

            ms = self._elapsed_ms(t0)
            self._log(
                "get_oc_anomalies", inputs, len(anomalies),
                f"{len(anomalies)} anomalías de precio detectadas",
                ms, "v_oc_price_anomalies"
            )
            return anomalies

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_oc_anomalies", inputs, 0, "", ms, "v_oc_price_anomalies", str(exc))
            return []

    # ── Tool 4: Proyección de Flujo de Caja ───────────────────────────────────

    def get_cashflow_projection(
        self, days_ahead: int = CASHFLOW_HORIZON_DAYS
    ) -> list[CashflowWeek]:
        """
        Proyección semanal basada 100% en documentos pendientes reales.
        Si no hay documentos futuros: retorna lista vacía (no estima).
        """
        t0 = self._now_ms()
        inputs = {"days_ahead": days_ahead, "organization_id": self.organization_id}
        try:
            cutoff = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date().isoformat()
            rows = (
                self.supabase.table("v_cashflow_projection")
                .select("*")
                .eq("organization_id", self.organization_id)
                .lte("periodo_inicio", cutoff)
                .order("periodo_inicio")
                .execute()
                .data or []
            )

            weeks = [
                CashflowWeek(
                    periodo            = str(r.get("periodo", "")),
                    periodo_inicio     = str(r.get("periodo_inicio", "")),
                    ingresos_esperados = float(r.get("ingresos_esperados") or 0),
                    egresos_esperados  = float(r.get("egresos_esperados")  or 0),
                    saldo_neto         = float(r.get("saldo_neto")         or 0),
                    es_deficit         = float(r.get("saldo_neto") or 0) < 0,
                    n_docs_ingreso     = int(r.get("n_documentos_ingreso") or 0),
                    n_docs_egreso      = int(r.get("n_documentos_egreso")  or 0),
                )
                for r in rows
            ]

            deficit_weeks = [w.periodo for w in weeks if w.es_deficit]
            ms = self._elapsed_ms(t0)
            self._log(
                "get_cashflow_projection", inputs, len(weeks),
                f"{len(weeks)} semanas | Déficit en: {deficit_weeks or 'ninguna'}",
                ms, "v_cashflow_projection"
            )
            return weeks

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_cashflow_projection", inputs, 0, "", ms, "v_cashflow_projection", str(exc))
            return []

    # ── Tool 5: Presupuestado vs Real ─────────────────────────────────────────

    def get_budget_vs_actual(
        self, project_id: str
    ) -> Optional[BudgetVsActual]:
        """
        Compara presupuesto vs costo ejecutado por partida.
        Retorna None si no hay datos — nunca una estimación.
        """
        t0 = self._now_ms()
        inputs = {"project_id": project_id, "organization_id": self.organization_id}
        try:
            rows = (
                self.supabase.table("v_budget_vs_actual")
                .select("*")
                .eq("organization_id", self.organization_id)
                .eq("project_id", project_id)
                .execute()
                .data or []
            )

            if not rows:
                ms = self._elapsed_ms(t0)
                self._log("get_budget_vs_actual", inputs, 0, "datos_insuficientes", ms, "v_budget_vs_actual")
                return None

            partidas: list[BudgetPartida] = []
            total_ejecutado = 0.0

            for r in rows:
                ejecutado    = float(r.get("monto_ejecutado") or 0)
                presupuestado = (
                    float(r["monto_presupuestado"])
                    if r.get("monto_presupuestado") is not None else None
                )
                var_pct = (
                    round((ejecutado - presupuestado) / presupuestado, 4)
                    if presupuestado and presupuestado > 0 else None
                )
                en_alerta = (var_pct is not None and abs(var_pct) > 0.20)
                total_ejecutado += ejecutado

                partidas.append(BudgetPartida(
                    partida             = str(r.get("partida", "")),
                    monto_presupuestado = presupuestado,
                    monto_ejecutado     = ejecutado,
                    variacion_pct       = var_pct,
                    en_alerta           = en_alerta,
                ))

            alertas = [p.partida for p in partidas if p.en_alerta]
            project_name = str(rows[0].get("project_name", "")) if rows else ""
            ms = self._elapsed_ms(t0)
            self._log(
                "get_budget_vs_actual", inputs, len(partidas),
                f"{len(partidas)} partidas | {len(alertas)} en alerta: {alertas}",
                ms, "v_budget_vs_actual"
            )

            return BudgetVsActual(
                project_id          = project_id,
                project_name        = project_name,
                partidas            = partidas,
                total_presupuestado = None,   # requiere quotes para completar
                total_ejecutado     = total_ejecutado,
                variacion_total_pct = None,   # no calculable sin presupuesto por partida
                partidas_en_alerta  = alertas,
            )

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_budget_vs_actual", inputs, 0, "", ms, "v_budget_vs_actual", str(exc))
            return None

    # ── Tool 6: Resumen ejecutivo (para contexto del agente) ──────────────────

    def get_executive_summary(self) -> dict:
        """
        Carga el pool financiero agregado desde v_company_financial_pool.
        Usado como contexto inicial antes de análisis detallado.
        """
        t0 = self._now_ms()
        inputs = {"organization_id": self.organization_id}
        try:
            result = (
                self.supabase.table("v_company_financial_pool")
                .select("*")
                .eq("organization_id", self.organization_id)
                .maybe_single()
                .execute()
            )
            data = result.data or {}
            ms = self._elapsed_ms(t0)
            self._log(
                "get_executive_summary", inputs, 1 if data else 0,
                f"margen={data.get('margen_bruto_pct')} | proyectos={data.get('proyectos_activos')}",
                ms, "v_company_financial_pool"
            )
            return data

        except Exception as exc:
            ms = self._elapsed_ms(t0)
            self._log("get_executive_summary", inputs, 0, "", ms, "v_company_financial_pool", str(exc))
            return {}
