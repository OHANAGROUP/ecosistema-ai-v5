-- Migration: Update Leads Table for SaaS Funnel
-- Description: Adds missing columns for notes, assignment, and defines helper functions.

-- 1. Add missing columns
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS notes JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS assigned_to TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS project_description TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS last_interaction TIMESTAMPTZ DEFAULT NOW();

-- 2. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_assigned_to ON public.leads(assigned_to);

-- 3. Database Function: append_lead_note
-- Safe appending of notes without race conditions on the array
CREATE OR REPLACE FUNCTION public.append_lead_note(
    lead_id BIGINT, 
    note JSONB
) 
RETURNS JSONB 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
DECLARE
    updated_notes JSONB;
BEGIN
    UPDATE public.leads
    SET 
        notes = (COALESCE(notes, '[]'::jsonb) || note),
        last_interaction = NOW()
    WHERE id = lead_id
    RETURNING notes INTO updated_notes;
    
    RETURN updated_notes;
END;
$$;

-- 4. Database Function: assign_lead
-- Logic to assign a lead and update status if it was 'New'
CREATE OR REPLACE FUNCTION public.assign_lead(
    lead_id BIGINT, 
    user_name TEXT
) 
RETURNS VOID 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.leads
    SET 
        assigned_to = user_name,
        -- If status is 'new', move to 'Contactado' or kept as is? 
        -- Usually assignment implies someone is looking at it. 
        -- Let's keep status manual unless it is 'new', then maybe 'contactado' is too aggressive.
        -- Let's just update the timestamp.
        updated_at = NOW()
    WHERE id = lead_id;
END;
$$;

-- 5. Database Function: get_funnel_stats
-- Returns counts for the funnel dashboard
CREATE OR REPLACE FUNCTION public.get_funnel_stats(org_id UUID)
RETURNS JSONB 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total', COUNT(*),
        'new', COUNT(*) FILTER (WHERE status = 'Nuevo'),
        'contacted', COUNT(*) FILTER (WHERE status = 'Contactado'),
        'quoted', COUNT(*) FILTER (WHERE status = 'Cotizado'),
        'won', COUNT(*) FILTER (WHERE status = 'Ganado'),
        'lost', COUNT(*) FILTER (WHERE status = 'Perdido')
    ) INTO result
    FROM public.leads
    WHERE organization_id = org_id;
    
    RETURN result;
END;
$$;
