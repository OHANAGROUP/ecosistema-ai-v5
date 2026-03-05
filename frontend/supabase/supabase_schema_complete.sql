-- ============================================================
-- ALPA SaaS + Ecosistema Agentes IA — Schema Unificado v5.0
-- VERSION: 5.0.5 (TOTAL REPAIR: Columns + Reset)
-- ============================================================

-- 0. EMERGENCY COLUMN REPAIR
DO $$ 
DECLARE
    t_name TEXT;
    table_list TEXT[] := ARRAY[
        'clients', 'providers', 'inventory', 'projects', 'transactions', 
        'leads', 'companies', 'agent_cycles', 'agent_decisions', 
        'agent_approvals', 'agent_rules', 'agent_signals', 
        'agent_thresholds', 'agent_usage_log'
    ];
BEGIN
    -- Create organizations first if it doesn't exist
    CREATE TABLE IF NOT EXISTS public.organizations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name TEXT NOT NULL,
        slug TEXT UNIQUE,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    FOREACH t_name IN ARRAY table_list
    LOOP
        -- If table exists, ensure organization_id exists
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = t_name) THEN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = t_name AND column_name = 'organization_id') THEN
                EXECUTE format('ALTER TABLE public.%I ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE', t_name);
            END IF;
        END IF;
    END LOOP;
END $$;

-- 1. NUCLEAR RESET (Optional but recommended for consistency)
DROP VIEW IF EXISTS public.pending_approvals CASCADE;
DROP VIEW IF EXISTS public.agent_knowledge CASCADE;
DROP VIEW IF EXISTS public.v_company_financial_pool CASCADE;
DROP VIEW IF EXISTS public.v_company_rh_pool CASCADE;

-- Re-create the tables with correct structure
CREATE TABLE IF NOT EXISTS public.organizations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    slug                TEXT UNIQUE,
    settings            JSONB DEFAULT '{}'::jsonb,
    plan                TEXT NOT NULL DEFAULT 'starter' CHECK (plan IN ('starter','growth','enterprise')),
    max_companies       INT  NOT NULL DEFAULT 5,
    max_cycles_per_day  INT  NOT NULL DEFAULT 2,
    stripe_customer_id  TEXT,
    billing_email       TEXT,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.organization_members (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner','ceo','analyst','member','viewer')),
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

CREATE OR REPLACE FUNCTION public.get_tenant_id() RETURNS uuid AS $$
  SELECT organization_id FROM public.organization_members
  WHERE user_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Redefine business tables to ensure organization_id is properly keyed
DO $$ 
DECLARE
    t_name TEXT;
BEGIN
    FOR t_name IN SELECT unnest(ARRAY['clients','providers','inventory','projects','transactions','leads','companies']) LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=t_name) THEN
             -- Add column and FK if not exists (redundant but safe)
             IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name=t_name AND column_name='organization_id') THEN
                 EXECUTE format('ALTER TABLE public.%I ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE', t_name);
             END IF;
        END IF;
    END LOOP;
END $$;

-- Final consistency check for Agent tables
CREATE TABLE IF NOT EXISTS public.agent_cycles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id     UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'running',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RE-APPLY POLICIES (This is where it usually fails if column is missing)
DO $$ 
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS svc_all_%s ON public.%s', t, t);
        EXECUTE format('CREATE POLICY svc_all_%s ON public.%s FOR ALL TO service_role USING (true) WITH CHECK (true)', t, t);
    END LOOP;
END $$;

-- Auth Policies (Individual applications)
-- Only proceed if columns exist
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='id') THEN
        DROP POLICY IF EXISTS auth_orgs ON organizations;
        CREATE POLICY auth_orgs ON public.organizations FOR SELECT TO authenticated USING (id = public.get_tenant_id());
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='projects' AND column_name='organization_id') THEN
        DROP POLICY IF EXISTS auth_projects ON projects;
        CREATE POLICY auth_projects ON public.projects FOR ALL TO authenticated USING (organization_id = public.get_tenant_id()) WITH CHECK (organization_id = public.get_tenant_id());
    END IF;

    -- Repeat for others...
END $$;

-- ============================================================
-- VALUE LOOP v1.0 — Trial Enforcement + Alert Persistence
-- ============================================================

-- TABLE: trials (backend enforcement real del trial)
CREATE TABLE IF NOT EXISTS public.trials (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    name            TEXT,
    company         TEXT,
    trial_start     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trial_end       TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '14 days',
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','expired','converted','cancelled')),
    session_token   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT trials_email_unique UNIQUE (email)
);

ALTER TABLE public.trials ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS svc_all_trials ON public.trials;
CREATE POLICY svc_all_trials ON public.trials FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Auto-expire trials via scheduled function (call from cron or daily job)
CREATE OR REPLACE FUNCTION public.expire_trials() RETURNS void AS $$
    UPDATE public.trials
    SET status = 'expired', updated_at = NOW()
    WHERE status = 'active' AND trial_end < NOW();
$$ LANGUAGE sql SECURITY DEFINER;

-- TABLE: agent_alerts (persistencia de alertas IA + acciones del usuario)
CREATE TABLE IF NOT EXISTS public.agent_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    cycle_id        UUID,
    agent_id        TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'media'
                        CHECK (severity IN ('critica','alta','media','baja')),
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    confidence      NUMERIC(5,2) DEFAULT 0.75,
    metadata        JSONB DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','snoozed')),
    action_by       TEXT,
    action_at       TIMESTAMPTZ,
    action_comment  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.agent_alerts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS svc_all_agent_alerts ON public.agent_alerts;
CREATE POLICY svc_all_agent_alerts ON public.agent_alerts FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS tenant_agent_alerts ON public.agent_alerts;
CREATE POLICY tenant_agent_alerts ON public.agent_alerts FOR ALL TO authenticated
    USING (organization_id = public.get_tenant_id())
    WITH CHECK (organization_id = public.get_tenant_id());

CREATE INDEX IF NOT EXISTS idx_agent_alerts_org ON public.agent_alerts(organization_id);
CREATE INDEX IF NOT EXISTS idx_agent_alerts_status ON public.agent_alerts(status);
CREATE INDEX IF NOT EXISTS idx_agent_alerts_created ON public.agent_alerts(created_at DESC);

-- TABLE: onboarding_events (tracking activación por cohorte)
CREATE TABLE IF NOT EXISTS public.onboarding_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    event           TEXT NOT NULL,
    step            INT,
    completed       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.onboarding_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS svc_all_onboarding_events ON public.onboarding_events;
CREATE POLICY svc_all_onboarding_events ON public.onboarding_events FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS tenant_onboarding_events ON public.onboarding_events;
CREATE POLICY tenant_onboarding_events ON public.onboarding_events FOR ALL TO authenticated
    USING (organization_id = public.get_tenant_id());

-- VIEW: activation_funnel (para medir onboarding por organización)
CREATE OR REPLACE VIEW public.v_activation_funnel AS
SELECT
    organization_id,
    COUNT(DISTINCT CASE WHEN event = 'identidad_completada' THEN id END) > 0 AS paso_identidad,
    COUNT(DISTINCT CASE WHEN event = 'primer_proyecto' THEN id END) > 0      AS paso_proyecto,
    COUNT(DISTINCT CASE WHEN event = 'directorio_base' THEN id END) > 0      AS paso_directorio,
    COUNT(DISTINCT CASE WHEN event = 'primer_scan_ia' THEN id END) > 0       AS paso_ia,
    MIN(created_at) AS primera_actividad
FROM public.onboarding_events
GROUP BY organization_id;
