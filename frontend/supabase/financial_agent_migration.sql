-- ============================================================================
-- FINANCIAL AGENT MIGRATION v1.0
-- Motor de verdad del AgenteFinanciero — vistas ETL + audit trail
-- Ejecutar en Supabase SQL Editor
-- ============================================================================

-- ── 1. AUDIT TRAIL: agent_tool_log ──────────────────────────────────────────
-- Registro inmutable de cada tool call ejecutada por el agente.
-- NUNCA se actualiza — solo INSERT.

CREATE TABLE IF NOT EXISTS public.agent_tool_log (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    cycle_id         TEXT,
    tool_name        TEXT NOT NULL,
    inputs           JSONB DEFAULT '{}'::jsonb,
    outputs_summary  TEXT,
    rows_returned    INT  DEFAULT 0,
    data_source      TEXT,
    duration_ms      INT,
    executed_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_log_org     ON public.agent_tool_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_tool_log_cycle   ON public.agent_tool_log(cycle_id);
CREATE INDEX IF NOT EXISTS idx_tool_log_tool    ON public.agent_tool_log(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_log_time    ON public.agent_tool_log(executed_at DESC);

ALTER TABLE public.agent_tool_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Org members read tool log"
    ON public.agent_tool_log FOR SELECT
    USING (organization_id = public.get_tenant_id());

-- ── 2. COLUMNAS ADICIONALES EN agent_decisions ──────────────────────────────
-- Extender la tabla existente con lineage de datos y confianza estructurada.

ALTER TABLE public.agent_decisions
    ADD COLUMN IF NOT EXISTS tool_calls_log  JSONB    DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS data_sources    JSONB    DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS confidence_level TEXT    DEFAULT 'MEDIUM'
        CHECK (confidence_level IN ('HIGH','MEDIUM','LOW','REFUSE')),
    ADD COLUMN IF NOT EXISTS trigger_type    TEXT     DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS null_fields     JSONB    DEFAULT '[]'::jsonb;

-- ── 3. TABLA ordenes_compra ──────────────────────────────────────────────────
-- Si no existe una tabla específica de OC, la creamos normalizada.

CREATE TABLE IF NOT EXISTS public.ordenes_compra (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    oc_numero        TEXT,
    proyecto_id      TEXT,
    proveedor        TEXT,
    item_descripcion TEXT,
    categoria        TEXT,
    monto_neto       NUMERIC(15,2) DEFAULT 0,
    iva              NUMERIC(15,2) DEFAULT 0,
    monto_total      NUMERIC(15,2) DEFAULT 0,
    estado           TEXT DEFAULT 'borrador'
        CHECK (estado IN ('borrador','pendiente','aprobada','rechazada','anulada','pagada')),
    fecha_emision    DATE,
    fecha_vencimiento DATE,
    solicitado_por   TEXT,
    aprobado_por     TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oc_org      ON public.ordenes_compra(organization_id);
CREATE INDEX IF NOT EXISTS idx_oc_proyecto ON public.ordenes_compra(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_oc_estado   ON public.ordenes_compra(estado);
CREATE INDEX IF NOT EXISTS idx_oc_fecha    ON public.ordenes_compra(fecha_emision DESC);

ALTER TABLE public.ordenes_compra ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Org members manage OC"
    ON public.ordenes_compra FOR ALL
    USING (organization_id = public.get_tenant_id())
    WITH CHECK (organization_id = public.get_tenant_id());

-- ── 4. TABLA estados_de_pago ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.estados_de_pago (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    ep_numero        TEXT,
    proyecto_id      TEXT,
    cliente          TEXT,
    descripcion      TEXT,
    monto_neto       NUMERIC(15,2) DEFAULT 0,
    iva              NUMERIC(15,2) DEFAULT 0,
    monto_total      NUMERIC(15,2) DEFAULT 0,
    estado           TEXT DEFAULT 'borrador'
        CHECK (estado IN ('borrador','emitido','enviado','vencido','pagado','anulado')),
    fecha_emision    DATE,
    fecha_vencimiento DATE,
    fecha_pago       DATE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ep_org      ON public.estados_de_pago(organization_id);
CREATE INDEX IF NOT EXISTS idx_ep_proyecto ON public.estados_de_pago(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_ep_estado   ON public.estados_de_pago(estado);
CREATE INDEX IF NOT EXISTS idx_ep_venc     ON public.estados_de_pago(fecha_vencimiento);

ALTER TABLE public.estados_de_pago ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Org members manage EP"
    ON public.estados_de_pago FOR ALL
    USING (organization_id = public.get_tenant_id())
    WITH CHECK (organization_id = public.get_tenant_id());

-- ── 5. VIEW: v_project_margins ───────────────────────────────────────────────
-- Margen real por proyecto: presupuesto vs costo comprometido vs ejecutado.
-- Fuente: projects + ordenes_compra + estados_de_pago

DROP VIEW IF EXISTS public.v_project_margins CASCADE;
CREATE OR REPLACE VIEW public.v_project_margins AS
SELECT
    p.organization_id,
    COALESCE(p."ID", p.id::TEXT)                AS project_id,
    COALESCE(p."Nombre", p.name, '')            AS project_name,
    COALESCE(p."Cliente", p.client, '')         AS cliente,
    COALESCE(p."Estado", p.status, '')          AS estado,
    COALESCE(p."Presupuesto", p.budget, 0)      AS presupuesto_ofertado,
    -- Costo comprometido: OC aprobadas/pendientes no pagadas
    COALESCE(
        (SELECT SUM(oc.monto_total)
         FROM public.ordenes_compra oc
         WHERE oc.organization_id = p.organization_id
           AND oc.proyecto_id = COALESCE(p."ID", p.id::TEXT)
           AND oc.estado IN ('pendiente','aprobada')
        ), 0
    )                                            AS costo_comprometido,
    -- Costo ejecutado: OC pagadas + transacciones de gasto
    COALESCE(
        (SELECT SUM(oc.monto_total)
         FROM public.ordenes_compra oc
         WHERE oc.organization_id = p.organization_id
           AND oc.proyecto_id = COALESCE(p."ID", p.id::TEXT)
           AND oc.estado = 'pagada'
        ), 0
    ) + COALESCE(
        (SELECT SUM(ABS(t."Monto"))
         FROM public.transactions t
         WHERE t.organization_id = p.organization_id
           AND t."ProyectoID" = COALESCE(p."ID", p.id::TEXT)
           AND t."Tipo" IN ('Gasto','Factura','Pago')
           AND t."Estado" NOT IN ('Anulado','Rechazado')
        ), 0
    )                                            AS costo_ejecutado
FROM public.projects p
WHERE p.organization_id IS NOT NULL;

-- ── 6. VIEW: v_overdue_payments ──────────────────────────────────────────────
-- Estados de pago vencidos con días de mora y contexto del cliente.

DROP VIEW IF EXISTS public.v_overdue_payments CASCADE;
CREATE OR REPLACE VIEW public.v_overdue_payments AS
WITH historial_clientes AS (
    -- Tiempo promedio de pago por cliente (basado en EP históricos pagados)
    SELECT
        organization_id,
        cliente,
        AVG(EXTRACT(DAY FROM (fecha_pago - fecha_emision))) AS dias_promedio_pago,
        COUNT(*)                                             AS n_pagos_historicos
    FROM public.estados_de_pago
    WHERE estado = 'pagado'
      AND fecha_pago IS NOT NULL
      AND fecha_emision IS NOT NULL
    GROUP BY organization_id, cliente
)
SELECT
    ep.id,
    ep.organization_id,
    ep.proyecto_id,
    ep.cliente,
    ep.descripcion,
    ep.monto_total                                              AS monto,
    ep.fecha_emision,
    ep.fecha_vencimiento,
    GREATEST(0,
        EXTRACT(DAY FROM NOW() - ep.fecha_vencimiento::TIMESTAMPTZ)
    )::INT                                                      AS dias_vencido,
    hc.dias_promedio_pago                                       AS historial_dias_promedio,
    hc.n_pagos_historicos
FROM public.estados_de_pago ep
LEFT JOIN historial_clientes hc
    ON hc.organization_id = ep.organization_id
   AND hc.cliente = ep.cliente
WHERE ep.estado IN ('emitido','enviado','vencido')
  AND ep.fecha_vencimiento IS NOT NULL
  AND ep.fecha_vencimiento < CURRENT_DATE;

-- ── 7. VIEW: v_oc_price_anomalies ────────────────────────────────────────────
-- Detecta OC con precio mayor al histórico del mismo ítem/proveedor.
-- Solo alerta si hay ≥ 3 OC históricas (evita falsos positivos).

DROP VIEW IF EXISTS public.v_oc_price_anomalies CASCADE;
CREATE OR REPLACE VIEW public.v_oc_price_anomalies AS
WITH historial_precios AS (
    SELECT
        organization_id,
        proveedor,
        item_descripcion,
        AVG(monto_neto)    AS precio_historico_promedio,
        STDDEV(monto_neto) AS precio_stddev,
        COUNT(*)           AS n_oc_historial
    FROM public.ordenes_compra
    WHERE estado NOT IN ('rechazada','anulada')
      AND monto_neto > 0
    GROUP BY organization_id, proveedor, item_descripcion
    HAVING COUNT(*) >= 3
)
SELECT
    oc.id                                        AS oc_id,
    oc.organization_id,
    oc.oc_numero,
    oc.proveedor,
    oc.item_descripcion,
    oc.categoria,
    oc.monto_neto                                AS precio_actual,
    hp.precio_historico_promedio,
    hp.n_oc_historial,
    ROUND(
        (oc.monto_neto - hp.precio_historico_promedio)
        / NULLIF(hp.precio_historico_promedio, 0),
        4
    )                                            AS desviacion_pct,
    oc.estado,
    oc.fecha_emision
FROM public.ordenes_compra oc
JOIN historial_precios hp
    ON  hp.organization_id  = oc.organization_id
    AND hp.proveedor        = oc.proveedor
    AND hp.item_descripcion = oc.item_descripcion
WHERE oc.estado IN ('borrador','pendiente')
  AND oc.monto_neto > hp.precio_historico_promedio * 1.20;

-- ── 8. VIEW: v_cashflow_projection ───────────────────────────────────────────
-- Proyección semanal de flujo de caja basada en documentos pendientes.
-- SOLO documentos reales — nunca estimaciones.

DROP VIEW IF EXISTS public.v_cashflow_projection CASCADE;
CREATE OR REPLACE VIEW public.v_cashflow_projection AS
WITH ingresos AS (
    SELECT
        organization_id,
        DATE_TRUNC('week', fecha_vencimiento::TIMESTAMPTZ) AS semana,
        SUM(monto_total)                                    AS monto,
        COUNT(*)                                            AS n_docs
    FROM public.estados_de_pago
    WHERE estado IN ('emitido','enviado')
      AND fecha_vencimiento >= CURRENT_DATE
      AND fecha_vencimiento <= CURRENT_DATE + INTERVAL '90 days'
    GROUP BY organization_id, DATE_TRUNC('week', fecha_vencimiento::TIMESTAMPTZ)
),
egresos AS (
    SELECT
        organization_id,
        DATE_TRUNC('week', fecha_vencimiento::TIMESTAMPTZ) AS semana,
        SUM(monto_total)                                    AS monto,
        COUNT(*)                                            AS n_docs
    FROM public.ordenes_compra
    WHERE estado IN ('aprobada')
      AND fecha_vencimiento >= CURRENT_DATE
      AND fecha_vencimiento <= CURRENT_DATE + INTERVAL '90 days'
    GROUP BY organization_id, DATE_TRUNC('week', fecha_vencimiento::TIMESTAMPTZ)
),
todas_semanas AS (
    SELECT organization_id, semana FROM ingresos
    UNION
    SELECT organization_id, semana FROM egresos
)
SELECT
    ts.organization_id,
    TO_CHAR(ts.semana, 'YYYY-MM-DD')      AS periodo,
    ts.semana                              AS periodo_inicio,
    COALESCE(i.monto, 0)                   AS ingresos_esperados,
    COALESCE(e.monto, 0)                   AS egresos_esperados,
    COALESCE(i.monto, 0) - COALESCE(e.monto, 0) AS saldo_neto,
    COALESCE(i.n_docs, 0)                  AS n_documentos_ingreso,
    COALESCE(e.n_docs, 0)                  AS n_documentos_egreso
FROM todas_semanas ts
LEFT JOIN ingresos i ON i.organization_id = ts.organization_id AND i.semana = ts.semana
LEFT JOIN egresos  e ON e.organization_id = ts.organization_id AND e.semana = ts.semana
ORDER BY ts.organization_id, ts.semana;

-- ── 9. VIEW: v_budget_vs_actual ──────────────────────────────────────────────
-- Presupuestado (desde quotes) vs ejecutado (desde OC+transacciones) por partida.

DROP VIEW IF EXISTS public.v_budget_vs_actual CASCADE;
CREATE OR REPLACE VIEW public.v_budget_vs_actual AS
WITH ejecutado_por_partida AS (
    SELECT
        organization_id,
        proyecto_id,
        COALESCE(categoria, 'Sin categoría') AS partida,
        SUM(monto_total)                      AS monto_ejecutado
    FROM public.ordenes_compra
    WHERE estado NOT IN ('rechazada','anulada')
    GROUP BY organization_id, proyecto_id, COALESCE(categoria, 'Sin categoría')
)
SELECT
    e.organization_id,
    e.proyecto_id                           AS project_id,
    COALESCE(p."Nombre", p.name, '')        AS project_name,
    e.partida,
    NULL::NUMERIC                           AS monto_presupuestado,  -- poblado desde quotes
    e.monto_ejecutado,
    NULL::NUMERIC                           AS variacion_pct         -- calculado en Python
FROM ejecutado_por_partida e
LEFT JOIN public.projects p
    ON  (p."ID" = e.proyecto_id OR p.id::TEXT = e.proyecto_id)
    AND  p.organization_id = e.organization_id;

-- ── 10. VIEW: v_company_financial_pool (actualizada) ─────────────────────────
-- Vista ETL principal que alimenta el agente con métricas agregadas.

DROP VIEW IF EXISTS public.v_company_financial_pool CASCADE;
CREATE OR REPLACE VIEW public.v_company_financial_pool AS
SELECT
    p.organization_id,
    o.name                                              AS empresa,
    COUNT(DISTINCT p."ID")                              AS proyectos_activos,
    SUM(COALESCE(p."Presupuesto", p.budget, 0))         AS presupuesto_total,
    -- Margen bruto calculado desde proyectos
    CASE
        WHEN SUM(COALESCE(p."Presupuesto", p.budget, 0)) > 0
        THEN ROUND(
            (SUM(COALESCE(p."Presupuesto", p.budget, 0)) - SUM(COALESCE(p."GastoReal", 0)))
            / NULLIF(SUM(COALESCE(p."Presupuesto", p.budget, 0)), 0),
            4
        )
        ELSE NULL
    END                                                 AS margen_bruto_pct,
    -- Ejecución presupuestal
    CASE
        WHEN SUM(COALESCE(p."Presupuesto", p.budget, 0)) > 0
        THEN ROUND(
            SUM(COALESCE(p."GastoReal", 0))
            / NULLIF(SUM(COALESCE(p."Presupuesto", p.budget, 0)), 0),
            4
        )
        ELSE NULL
    END                                                 AS ejecucion_presupuestal,
    -- Ingresos del mes: EP pagados en los últimos 30 días
    COALESCE(
        (SELECT SUM(ep.monto_total)
         FROM public.estados_de_pago ep
         WHERE ep.organization_id = p.organization_id
           AND ep.estado = 'pagado'
           AND ep.fecha_pago >= CURRENT_DATE - INTERVAL '30 days'
        ), 0
    )                                                   AS ingresos_mes,
    -- Gastos del mes: OC pagadas en los últimos 30 días
    COALESCE(
        (SELECT SUM(oc.monto_total)
         FROM public.ordenes_compra oc
         WHERE oc.organization_id = p.organization_id
           AND oc.estado = 'pagada'
           AND oc.fecha_emision >= CURRENT_DATE - INTERVAL '30 days'
        ), 0
    )                                                   AS gastos_mes,
    NOW()                                               AS calculado_en
FROM public.projects p
JOIN public.organizations o ON o.id = p.organization_id
WHERE p.organization_id IS NOT NULL
  AND COALESCE(p."Estado", p.status, '') NOT IN ('cerrado','cancelado','archivado')
GROUP BY p.organization_id, o.name;
