-- agent_tool_log
-- Registro de llamadas a la API de Anthropic por organización.
-- Usado por operator_tools.py para calcular costos reales de Anthropic.
-- Ejecutar en Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS public.agent_tool_log (
    id              BIGSERIAL PRIMARY KEY,
    organization_id UUID        NOT NULL,
    agent_type      TEXT,                       -- 'financiero', 'legal', 'rh', 'operador'
    tool_name       TEXT,                       -- nombre de la tool llamada
    input_tokens    INTEGER     DEFAULT 0,      -- tokens de entrada
    output_tokens   INTEGER     DEFAULT 0,      -- tokens de salida
    cycle_id        TEXT,                       -- cycle_id del agente
    executed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para queries frecuentes de operator_tools
CREATE INDEX IF NOT EXISTS idx_agent_tool_log_org_date
    ON public.agent_tool_log (organization_id, executed_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_tool_log_date
    ON public.agent_tool_log (executed_at DESC);

-- RLS: cada org solo ve sus propios logs
ALTER TABLE public.agent_tool_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation" ON public.agent_tool_log
    FOR ALL USING (
        organization_id = (
            SELECT (auth.jwt() -> 'user_metadata' ->> 'organization_id')::uuid
        )
    );
