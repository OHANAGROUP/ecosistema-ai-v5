-- ════════════════════════════════════════════════════════════════
-- AgenteOperador — Migración SQL
-- MD Asesorías Limitada · AgentOS v5.0
-- Ejecutar en: Supabase SQL Editor
-- ════════════════════════════════════════════════════════════════

-- ── 1. Tabla de configuración de costos del stack ────────────────
CREATE TABLE IF NOT EXISTS operator_stack_config (
    key             TEXT PRIMARY KEY,
    service_name    TEXT,
    monthly_cost_clp INTEGER NOT NULL DEFAULT 0,
    value_int       INTEGER,
    value_text      TEXT,
    notes           TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Filas iniciales (costos en $0 = pendiente de configurar)
INSERT INTO operator_stack_config (key, service_name, monthly_cost_clp, notes) VALUES
    ('railway',  'Railway',  0, 'Backend hosting Railway — actualizar mensualmente en CLP'),
    ('supabase', 'Supabase', 0, 'Database Supabase — actualizar mensualmente en CLP'),
    ('vercel',   'Vercel',   0, 'Frontend hosting Vercel — actualizar mensualmente en CLP'),
    ('resend',   'Resend',   0, 'Servicio email Resend — actualizar mensualmente en CLP')
ON CONFLICT (key) DO NOTHING;

-- UF en CLP — actualizar manualmente cada mes
INSERT INTO operator_stack_config (key, value_int, notes) VALUES
    ('uf_clp_value', 38000, 'Valor UF en CLP — actualizar el 1ro de cada mes')
ON CONFLICT (key) DO NOTHING;

-- USD en CLP — actualizar manualmente
INSERT INTO operator_stack_config (key, value_int, notes) VALUES
    ('usd_clp_value', 950, 'Valor USD en CLP — referencia para costos Anthropic')
ON CONFLICT (key) DO NOTHING;

-- ── 2. RLS: solo service_role puede acceder ──────────────────────
ALTER TABLE operator_stack_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "no_public_access_operator_config" ON operator_stack_config;
CREATE POLICY "no_public_access_operator_config"
    ON operator_stack_config
    FOR ALL
    TO anon, authenticated
    USING (false);

-- ── 3. Vista: resumen de clientes ────────────────────────────────
CREATE OR REPLACE VIEW v_operator_clients AS
SELECT
    o.id                                                        AS org_id,
    o.name,
    o.plan_type,
    o.status,
    o.trial_end,
    o.created_at                                                AS registered_at,
    EXTRACT(DAY FROM (now() - o.created_at))::int               AS days_since_register,

    -- Días restantes de trial (null si no aplica)
    CASE
        WHEN o.trial_end IS NOT NULL AND o.trial_end > now()
        THEN GREATEST(0, EXTRACT(DAY FROM (o.trial_end - now()))::int)
        ELSE NULL
    END                                                         AS trial_days_remaining,

    -- Actividad de agentes
    COUNT(ad.id)::int                                           AS total_agent_cycles,
    COUNT(ad.id) FILTER (
        WHERE ad.created_at > now() - INTERVAL '7 days'
    )::int                                                      AS cycles_last_7d,
    MAX(ad.created_at)                                          AS last_agent_activity,

    -- Días sin actividad
    CASE
        WHEN MAX(ad.created_at) IS NOT NULL
        THEN ROUND(EXTRACT(EPOCH FROM (now() - MAX(ad.created_at))) / 86400, 1)
        ELSE NULL
    END                                                         AS days_since_last_activity

FROM organizations o
LEFT JOIN agent_decisions ad ON ad.organization_id = o.id
GROUP BY o.id, o.name, o.plan_type, o.status, o.trial_end, o.created_at;

-- ── 4. Vista: resumen MRR ────────────────────────────────────────
CREATE OR REPLACE VIEW v_operator_mrr AS
WITH plan_prices (plan_type, uf_monthly) AS (
    VALUES
        ('starter'::text,    2.0),
        ('empresa'::text,    3.5),
        ('enterprise'::text, 10.0),
        ('trial'::text,      0.0)
),
uf_rate AS (
    SELECT COALESCE(
        (SELECT value_int FROM operator_stack_config WHERE key = 'uf_clp_value'),
        38000
    ) AS clp
)
SELECT
    COUNT(*)                                                    AS total_orgs,
    COUNT(*) FILTER (
        WHERE o.plan_type <> 'trial' AND o.status = 'active'
    )                                                           AS paying_clients,
    COUNT(*) FILTER (
        WHERE o.plan_type = 'trial' AND o.status = 'active'
    )                                                           AS trial_clients,
    COUNT(*) FILTER (
        WHERE o.status IN ('cancelled', 'churned')
    )                                                           AS churned_clients,

    -- MRR en UF
    COALESCE(SUM(pp.uf_monthly) FILTER (
        WHERE o.plan_type <> 'trial' AND o.status = 'active'
    ), 0)                                                       AS mrr_uf,

    -- MRR en CLP
    COALESCE(SUM(pp.uf_monthly * ur.clp) FILTER (
        WHERE o.plan_type <> 'trial' AND o.status = 'active'
    ), 0)::bigint                                               AS mrr_clp,

    -- Nuevos este mes
    COUNT(*) FILTER (
        WHERE o.plan_type <> 'trial'
          AND o.status = 'active'
          AND o.created_at > date_trunc('month', now())
    )                                                           AS new_paying_30d,
    COUNT(*) FILTER (
        WHERE o.plan_type = 'trial'
          AND o.created_at > date_trunc('month', now())
    )                                                           AS new_trials_30d

FROM organizations o
LEFT JOIN plan_prices pp ON pp.plan_type = o.plan_type
CROSS JOIN uf_rate ur;

-- ── 5. Vista: costos Anthropic por organización ──────────────────
-- Nota: estimación basada en llamadas a tools (1500 tokens input + 500 output avg)
-- Para costos exactos: almacenar usage.input_tokens en agent_tool_log (mejora futura)
CREATE OR REPLACE VIEW v_operator_api_costs AS
SELECT
    organization_id,
    COUNT(*)                                                    AS total_tool_calls,
    COUNT(*) FILTER (
        WHERE executed_at > date_trunc('month', now())
    )                                                           AS calls_this_month,
    AVG(duration_ms)::int                                       AS avg_duration_ms,

    -- Estimación costo input: 1500 tokens × $3/MTok
    ROUND(
        COUNT(*) FILTER (WHERE executed_at > date_trunc('month', now()))
        * 1500 * 3.0 / 1000000, 4
    )                                                           AS estimated_input_cost_usd,

    -- Estimación costo output: 500 tokens × $15/MTok
    ROUND(
        COUNT(*) FILTER (WHERE executed_at > date_trunc('month', now()))
        * 500 * 15.0 / 1000000, 4
    )                                                           AS estimated_output_cost_usd,

    -- Total estimado USD
    ROUND(
        COUNT(*) FILTER (WHERE executed_at > date_trunc('month', now()))
        * (1500 * 3.0 + 500 * 15.0) / 1000000, 4
    )                                                           AS total_cost_usd,

    MAX(executed_at)                                            AS last_call_at

FROM agent_tool_log
GROUP BY organization_id;

-- ── 6. Vista: salud del sistema ──────────────────────────────────
CREATE OR REPLACE VIEW v_operator_system_health AS
SELECT
    COUNT(*)                                                    AS total_decisions,
    COUNT(*) FILTER (
        WHERE created_at > now() - INTERVAL '24 hours'
    )                                                           AS decisions_24h,
    COUNT(*) FILTER (
        WHERE created_at > now() - INTERVAL '24 hours'
          AND (confidence < 0.3 OR health_status IN ('ERROR', 'REFUSE'))
    )                                                           AS failed_24h,
    ROUND(AVG(confidence) FILTER (
        WHERE created_at > now() - INTERVAL '7 days'
          AND confidence IS NOT NULL
    )::numeric, 3)                                              AS avg_confidence_7d,
    COUNT(DISTINCT organization_id) FILTER (
        WHERE created_at > now() - INTERVAL '24 hours'
          AND (confidence < 0.3 OR health_status IN ('ERROR', 'REFUSE'))
    )                                                           AS orgs_with_issues_24h

FROM agent_decisions;

-- ── 7. Columna input_tokens en agent_tool_log (mejora de precisión) ─
ALTER TABLE agent_tool_log
    ADD COLUMN IF NOT EXISTS input_tokens  INTEGER,
    ADD COLUMN IF NOT EXISTS output_tokens INTEGER;

COMMENT ON COLUMN agent_tool_log.input_tokens  IS 'Tokens input reales de Anthropic — almacenar desde usage.input_tokens';
COMMENT ON COLUMN agent_tool_log.output_tokens IS 'Tokens output reales de Anthropic — almacenar desde usage.output_tokens';
