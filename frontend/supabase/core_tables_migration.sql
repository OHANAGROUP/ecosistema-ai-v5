-- ════════════════════════════════════════════════════════════════
-- Migración Base — Tablas Core AgentOS v5.0
-- Ejecutar PRIMERO, antes de financial_agent_migration.sql
-- ════════════════════════════════════════════════════════════════

-- ── 1. Columnas faltantes en organizations ───────────────────────
ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS owner_email  TEXT,
    ADD COLUMN IF NOT EXISTS owner_name   TEXT,
    ADD COLUMN IF NOT EXISTS trial_start  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS plan_type    TEXT NOT NULL DEFAULT 'trial',
    ADD COLUMN IF NOT EXISTS status       TEXT NOT NULL DEFAULT 'active';

-- Backfill trial_start donde es null (usar created_at como fallback)
UPDATE organizations
SET trial_start = created_at
WHERE trial_start IS NULL AND trial_end IS NOT NULL;

-- ── 2. Tabla leads (captura desde CTA upgrade y formulario web) ──
-- Schema alineado con lo que espera core.js y el módulo CRM
CREATE TABLE IF NOT EXISTS leads (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name                TEXT NOT NULL,
    email               TEXT NOT NULL,
    phone               TEXT,
    project_description TEXT,
    message             TEXT,
    origin              TEXT DEFAULT 'landing',
    organization_id     TEXT,
    status              TEXT DEFAULT 'Nuevo',
    assigned_to         TEXT DEFAULT 'Sin Asignar',
    notes               JSONB DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Si la tabla ya existe con columnas antiguas (nombre, empresa, etc.), agregar las que faltan
ALTER TABLE leads ADD COLUMN IF NOT EXISTS name                TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone               TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS project_description TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS message             TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS origin              TEXT DEFAULT 'landing';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS organization_id     TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS status              TEXT DEFAULT 'Nuevo';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to         TEXT DEFAULT 'Sin Asignar';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS notes               JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_leads_org       ON leads (organization_id);
CREATE INDEX IF NOT EXISTS idx_leads_status    ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_created   ON leads (created_at DESC);

-- Backfill: migrar columnas antiguas si existen (protegido — falla silencioso si no existen)
DO $$
BEGIN
    UPDATE leads SET name    = nombre  WHERE name    IS NULL AND nombre  IS NOT NULL;
EXCEPTION WHEN undefined_column THEN NULL; END $$;
DO $$
BEGIN
    UPDATE leads SET message = mensaje WHERE message IS NULL AND mensaje IS NOT NULL;
EXCEPTION WHEN undefined_column THEN NULL; END $$;
DO $$
BEGIN
    UPDATE leads SET origin  = source  WHERE origin = 'landing' AND source IS NOT NULL
      AND source NOT IN ('landing');
EXCEPTION WHEN undefined_column THEN NULL; END $$;

-- RLS: permitir insert público (formulario web externo sin auth)
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Enable public insert for leads" ON leads;
CREATE POLICY "Enable public insert for leads"
    ON leads FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS "Users can manage their organization leads" ON leads;
CREATE POLICY "Users can manage their organization leads"
    ON leads FOR ALL TO authenticated
    USING (organization_id = (auth.jwt() ->> 'organization_id'))
    WITH CHECK (organization_id = (auth.jwt() ->> 'organization_id'));

-- ── 3. Tabla audit_logs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type      TEXT NOT NULL,
    user_id         TEXT,
    organization_id TEXT,
    resource_type   TEXT,
    resource_id     TEXT,
    action          TEXT,
    success         BOOLEAN DEFAULT true,
    details         JSONB,
    ip_address      TEXT,
    timestamp       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org     ON audit_logs (organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event   ON audit_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ts      ON audit_logs (timestamp DESC);

-- ── 4. Tabla agent_signals (inter-agent communication) ──────────
CREATE TABLE IF NOT EXISTS agent_signals (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    cycle_id        TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    empresa         TEXT,
    signal_type     TEXT NOT NULL,
    target_agent    TEXT DEFAULT 'all',
    payload         JSONB DEFAULT '{}',
    consumed        BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_cycle ON agent_signals (cycle_id);
CREATE INDEX IF NOT EXISTS idx_signals_org   ON agent_signals (organization_id);

-- ── 5. Tabla agent_decisions (columnas de audit trail) ───────────
-- NOTA: estas columnas son agregadas por financial_agent_migration.sql
-- con defaults y CHECK constraints correctos. No duplicar aquí.

-- ── 6. Tabla onboarding_events ───────────────────────────────────
CREATE TABLE IF NOT EXISTS onboarding_events (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    organization_id TEXT NOT NULL,
    user_id         TEXT,
    event           TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_org ON onboarding_events (organization_id);

-- ── 7. RLS básico para tablas sensibles ──────────────────────────
ALTER TABLE audit_logs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_signals    ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_events ENABLE ROW LEVEL SECURITY;

-- Solo el backend (service role) accede — bloquear acceso público
DROP POLICY IF EXISTS "service_only_audit" ON audit_logs;
CREATE POLICY "service_only_audit"
    ON audit_logs FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "service_only_signals" ON agent_signals;
CREATE POLICY "service_only_signals"
    ON agent_signals FOR ALL TO anon, authenticated USING (false);

-- onboarding: usuarios ven solo su org
DROP POLICY IF EXISTS "own_org_onboarding" ON onboarding_events;
CREATE POLICY "own_org_onboarding"
    ON onboarding_events FOR SELECT TO authenticated
    USING (organization_id = (auth.jwt() ->> 'organization_id'));

-- ── 8. Índices de performance en agent_decisions ─────────────────
CREATE INDEX IF NOT EXISTS idx_decisions_org_created
    ON agent_decisions (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_decisions_cycle
    ON agent_decisions (cycle_id);
