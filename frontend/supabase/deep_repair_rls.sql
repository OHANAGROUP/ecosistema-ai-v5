-- ALPA DEEP REPAIR - Supabase RLS & Permissions
-- Fixes Error 406 (Not Acceptable) and 403 (Forbidden) during migration

-- 1. Fix the Tenant ID helper to be ultra-robust (Checking both JWT and auth.users)
CREATE OR REPLACE FUNCTION public.get_tenant_id() RETURNS uuid AS $$
BEGIN
    RETURN (
        COALESCE(
            nullif(auth.jwt() -> 'app_metadata' ->> 'organization_id', ''),
            nullif(auth.jwt() -> 'user_metadata' ->> 'organization_id', ''),
            (SELECT (raw_user_meta_data ->> 'organization_id') FROM auth.users WHERE id = auth.uid())
        )
    )::uuid;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- 2. Allow users to register/initialize their organization record
-- This unblocks the ensureOrganization() logic in core.js
DROP POLICY IF EXISTS "Users can create their own organization" ON public.organizations;
CREATE POLICY "Users can create their own organization"
ON public.organizations FOR INSERT
WITH CHECK (id = public.get_tenant_id() OR NOT EXISTS (SELECT 1 FROM public.organizations WHERE id = public.get_tenant_id()));

-- 3. Allow viewing organizations Assigned to the user
DROP POLICY IF EXISTS "Users can view their own organization" ON public.organizations;
CREATE POLICY "Users can view their own organization"
ON public.organizations FOR SELECT
USING (id = public.get_tenant_id());

-- 4. Unblock schema visibility (Fix 406 Not Acceptable)
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Make sure RLS is definitively ON for all tables
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

-- 5. Force specific policy refresh for major tables
DROP POLICY IF EXISTS "Users can manage their organization's projects" ON public.projects;
CREATE POLICY "Users can manage their organization's projects"
ON public.projects FOR ALL USING (organization_id = public.get_tenant_id()) WITH CHECK (organization_id = public.get_tenant_id());

DROP POLICY IF EXISTS "Users can manage their organization's transactions" ON public.transactions;
CREATE POLICY "Users can manage their organization's transactions"
ON public.transactions FOR ALL USING (organization_id = public.get_tenant_id()) WITH CHECK (organization_id = public.get_tenant_id());

-- 6. Membership Self-Repair
-- Ensures the current user is an admin of the organization ID in their metadata
DO $$
DECLARE
    cur_user_id UUID := auth.uid();
    cur_org_id UUID;
BEGIN
    -- Get org id from current user metadata
    SELECT (raw_user_meta_data ->> 'organization_id')::uuid INTO cur_org_id
    FROM auth.users 
    WHERE id = cur_user_id;

    IF cur_org_id IS NOT NULL THEN
        -- Ensure organization exists (even if hidden or just created)
        INSERT INTO public.organizations (id, name)
        VALUES (cur_org_id, 'Empresa de ' || cur_user_id)
        ON CONFLICT (id) DO NOTHING;

        -- Ensure user is member/admin
        INSERT INTO public.organization_members (organization_id, user_id, role)
        VALUES (cur_org_id, cur_user_id, 'admin')
        ON CONFLICT (organization_id, user_id) DO NOTHING;
    END IF;
END $$;

-- Verification View
CREATE OR REPLACE VIEW public.debug_auth_status WITH (security_invoker = true) AS 
SELECT 
  auth.uid() as current_user_id,
  public.get_tenant_id() as identified_org_id,
  (SELECT count(*) FROM public.organization_members WHERE user_id = auth.uid()) as membership_count;
