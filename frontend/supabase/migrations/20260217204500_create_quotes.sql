-- Migration: Create Quotes Table for Sales Funnel
-- Description: Adds quotes table to store proposals and link them to leads.

-- 1. Create Quotes Table
CREATE TABLE IF NOT EXISTS public.quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    quote_number TEXT NOT NULL,
    lead_id BIGINT REFERENCES public.leads(id) ON DELETE SET NULL,
    project_id TEXT, -- Can link to projects table ID (which is text based on schema)
    client_name TEXT,
    client_email TEXT,
    total_amount NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'Borrador', -- Borrador, Enviada, Aceptada, Rechazada
    data JSONB DEFAULT '{}'::jsonb, -- Stores full JSON of items, conditions, etc.
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    timeline JSONB DEFAULT '[]'::jsonb -- Stores history of status changes
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_quotes_org ON public.quotes(organization_id);
CREATE INDEX IF NOT EXISTS idx_quotes_lead ON public.quotes(lead_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON public.quotes(status);
CREATE INDEX IF NOT EXISTS idx_quotes_email ON public.quotes(client_email);

-- 3. RLS Policies
ALTER TABLE public.quotes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their organization's quotes"
ON public.quotes FOR ALL
USING (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- 4. Funnel Stats Function Update (Optional, can just query table)
-- We can reuse the get_funnel_stats but targeting quotes + leads if needed.
-- For now, frontend does the aggregation.

-- 5. Trigger for Updated At
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_quotes_modtime
    BEFORE UPDATE ON public.quotes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
