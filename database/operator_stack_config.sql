-- operator_stack_config
-- Configuración manual de costos del stack para AgenteOperador.
-- Ejecutar en Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS public.operator_stack_config (
    id               BIGSERIAL PRIMARY KEY,
    key              TEXT,                    -- para parámetros de configuración (uf_clp_value, usd_clp_value)
    value_int        INTEGER,                 -- valor entero del parámetro
    service_name     TEXT,                    -- para costos de servicios (railway, supabase, vercel, resend)
    monthly_cost_clp INTEGER DEFAULT 0,      -- costo mensual en CLP
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Solo MD Asesorías (ADMIN_ORG_ID) puede leer/escribir esta tabla
ALTER TABLE public.operator_stack_config ENABLE ROW LEVEL SECURITY;

-- No RLS policy pública — solo service role key puede acceder (bypass RLS)
-- El operador usa SUPABASE_SERVICE_ROLE_KEY, que bypasea RLS automáticamente.

-- ── Parámetros de conversión de moneda ────────────────────────────────────────
INSERT INTO public.operator_stack_config (key, value_int)
VALUES
    ('uf_clp_value',  38000),   -- 1 UF en CLP (actualizar mensualmente)
    ('usd_clp_value', 950)      -- 1 USD en CLP (actualizar según tipo de cambio)
ON CONFLICT DO NOTHING;

-- ── Costos mensuales del stack (en CLP) ───────────────────────────────────────
-- Vercel Pro:   $20 USD/mes  → ~$19.000 CLP
-- Supabase Pro: $25 USD/mes  → ~$23.750 CLP
-- Railway:      ~$10 USD/mes → ~$9.500 CLP
-- Resend:       plan free por ahora → $0
INSERT INTO public.operator_stack_config (service_name, monthly_cost_clp)
VALUES
    ('railway',  9500),
    ('supabase', 23750),
    ('vercel',   19000),
    ('resend',   0)
ON CONFLICT DO NOTHING;
