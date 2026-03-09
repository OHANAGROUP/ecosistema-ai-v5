-- ==========================================
-- ECOSISTEMA IA V5.0 - SCHEMA INITIALIZATION
-- ==========================================

-- Tabla de ciclos de IA
CREATE TABLE IF NOT EXISTS ai_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    instruction TEXT,
    status TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    decisions_count INTEGER DEFAULT 0
);

-- Habilitar RLS para Ciclos
ALTER TABLE ai_cycles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuarios ven ciclos de su organización" ON ai_cycles
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Service Role full access to ai_cycles" ON ai_cycles
    FOR ALL USING (true);


-- Tabla de decisiones de IA
CREATE TABLE IF NOT EXISTS ai_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id UUID REFERENCES ai_cycles(id) ON DELETE CASCADE,
    agent_id TEXT,
    decision_type TEXT,
    confidence FLOAT,
    reasoning TEXT,
    approved BOOLEAN,
    feedback_comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar RLS para Decisiones
ALTER TABLE ai_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuarios ven decisiones de sus ciclos" ON ai_decisions
    FOR SELECT USING (
        cycle_id IN (
            SELECT id FROM ai_cycles WHERE organization_id IN (
                SELECT organization_id FROM organization_members 
                WHERE user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Service Role full access to ai_decisions" ON ai_decisions
    FOR ALL USING (true);


-- Tabla de métricas de agentes
CREATE TABLE IF NOT EXISTS ai_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    metric_name TEXT,
    metric_value FLOAT,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar RLS para Métricas
ALTER TABLE ai_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuarios ven métricas de su org" ON ai_metrics
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members 
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Service Role full access to ai_metrics" ON ai_metrics
    FOR ALL USING (true);
