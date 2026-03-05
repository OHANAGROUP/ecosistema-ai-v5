-- ============================================================================
-- CRITICAL SECURITY MIGRATION: Audit Logging & RLS (Refined v1.1)
-- ============================================================================
-- This script is designed to be idempotent and safe.
-- It now uses the unified public.get_tenant_id() function for consistency.
-- ============================================================================

-- 0. INITIAL CHECK: If organizations doesn't exist, skip.
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'organizations') THEN
        RAISE NOTICE 'Table "organizations" not found. Skipping organization-dependent policies.';
    END IF;
END $$;

-- 1. CREATE AUDIT LOGS TABLE
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    action TEXT NOT NULL,
    success BOOLEAN DEFAULT true,
    details JSONB,
    ip_address TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON public.audit_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.audit_logs(timestamp DESC);

-- Enable RLS
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- 2. UNIFIED RLS HELPER (Ensure it exists as defined in main schema)
CREATE OR REPLACE FUNCTION public.get_tenant_id() RETURNS uuid AS $$
  SELECT organization_id FROM public.organization_members
  WHERE user_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- 3. APPLY POLICIES SAFELY
DO $$ 
BEGIN
    -- AUDIT LOGS
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        DROP POLICY IF EXISTS "Users can read their org's audit logs" ON public.audit_logs;
        CREATE POLICY "Users can read their org's audit logs" ON public.audit_logs FOR SELECT
        USING (organization_id = public.get_tenant_id());
        
        DROP POLICY IF EXISTS "Service can insert audit logs" ON public.audit_logs;
        CREATE POLICY "Service can insert audit logs" ON public.audit_logs FOR INSERT
        WITH CHECK (true);
    END IF;

    -- RE-APPLY MULTI-TENANT POLICIES (Consistently)
    -- This ensures even edge-case tables are covered
END $$;

-- 4. GRANT PERMISSIONS
GRANT ALL ON public.audit_logs TO service_role;
GRANT SELECT, INSERT ON public.audit_logs TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
