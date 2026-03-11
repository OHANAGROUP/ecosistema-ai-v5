-- Ejecutar en Supabase SQL Editor

CREATE TABLE IF NOT EXISTS sprint_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    title TEXT NOT NULL,
    description TEXT,
    section TEXT NOT NULL,
    completed BOOLEAN DEFAULT false,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- RLS
ALTER TABLE sprint_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_sprint_tasks"
ON sprint_tasks
FOR ALL
USING (
    organization_id IN (
        SELECT organization_id 
        FROM organization_members 
        WHERE user_id = auth.uid()
    )
);

-- Índices
CREATE INDEX idx_sprint_tasks_org ON sprint_tasks(organization_id);
CREATE INDEX idx_sprint_tasks_section ON sprint_tasks(section);
