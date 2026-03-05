-- =====================================================
-- LEADS TABLE ENHANCEMENT MIGRATION
-- =====================================================

-- 1. ADD MISSING COLUMNS
ALTER TABLE public.leads 
ADD COLUMN IF NOT EXISTS notes JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS assigned_to TEXT DEFAULT 'Sin Asignar',
ADD COLUMN IF NOT EXISTS project_description TEXT;

-- 2. UPDATE RLS FOR PUBLIC SUBMISSIONS
-- We need to allow the public contact form to insert leads
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

-- Policy for internal users (Managers)
DROP POLICY IF EXISTS "Users can manage their organization's leads" ON public.leads;
CREATE POLICY "Users can manage their organization's leads"
ON public.leads FOR ALL
USING (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- Policy for Public Contact Form (Insert Only)
DROP POLICY IF EXISTS "Enable public insert for leads" ON public.leads;
CREATE POLICY "Enable public insert for leads"
ON public.leads FOR INSERT
WITH CHECK (true); 

-- 3. ENSURE AUDIT METADATA
ALTER TABLE public.leads 
ALTER COLUMN created_at SET DEFAULT NOW();

-- 4. VERIFICATION
-- SELECT * FROM public.leads LIMIT 5;
