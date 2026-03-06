-- =====================================================================
-- FIX DE PERSISTENCIA SAAS v5.0 — Ejecutar en Supabase SQL Editor
-- Fecha: 2026-03-06 | Cuenta: ppalomin@hotmail.com
-- =====================================================================

-- 1. AGREGAR COLUMNAS DE BRANDING FALTANTES EN ORGANIZATIONS
ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS address TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS email TEXT,
  ADD COLUMN IF NOT EXISTS website TEXT,
  ADD COLUMN IF NOT EXISTS logo_url TEXT,
  ADD COLUMN IF NOT EXISTS plan_type TEXT DEFAULT 'trial',
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS trial_end TIMESTAMPTZ;

-- 2. CREAR TABLA QUOTES (COTIZACIONES) — Faltaba en el schema
CREATE TABLE IF NOT EXISTS public.quotes (
    id TEXT PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    quote_number TEXT,
    client_name TEXT,
    client_email TEXT,
    total_amount NUMERIC(15, 2) DEFAULT 0,
    status TEXT DEFAULT 'Borrador',
    data JSONB DEFAULT '{}'::jsonb,   -- Full quote JSON payload
    timeline JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quotes_org ON public.quotes(organization_id);

-- 3. AJUSTE DE COLUMNAS EN LA TABLA PROJECTS (snake_case completo)
-- El schema actual ya tiene columnas snake_case (id, name, code, etc.).
-- BUT core.js hace upsert con CamelCase => se añaden alias/columnas alternativas:
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS "ID" TEXT,           -- Alias CamelCase para compat
  ADD COLUMN IF NOT EXISTS "Nombre" TEXT,
  ADD COLUMN IF NOT EXISTS "Codigo" TEXT,
  ADD COLUMN IF NOT EXISTS "Cliente" TEXT,
  ADD COLUMN IF NOT EXISTS "Presupuesto" NUMERIC(15, 2),
  ADD COLUMN IF NOT EXISTS "Estado" TEXT,
  ADD COLUMN IF NOT EXISTS "FechaInicio" DATE,
  ADD COLUMN IF NOT EXISTS "FechaTermino" DATE,
  ADD COLUMN IF NOT EXISTS "PorcentajeAvance" NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS "Responsable" TEXT,
  ADD COLUMN IF NOT EXISTS "CentroCostoID" TEXT;

-- 4. AJUSTE DE COLUMNAS EN LA TABLA TRANSACTIONS (snake_case completo)
-- El schema actual tiene date, type, category, amount, description, cost_center.
-- core.js hace upsert con Fecha, Tipo, Categoría, Monto, Descripción, Usuario, Estado
ALTER TABLE public.transactions
  ADD COLUMN IF NOT EXISTS "ID" TEXT,
  ADD COLUMN IF NOT EXISTS "Fecha" DATE,
  ADD COLUMN IF NOT EXISTS "Tipo" TEXT,
  ADD COLUMN IF NOT EXISTS "Categoría" TEXT,
  ADD COLUMN IF NOT EXISTS "Monto" NUMERIC(15, 2),
  ADD COLUMN IF NOT EXISTS "Descripción" TEXT,
  ADD COLUMN IF NOT EXISTS "Usuario" TEXT,
  ADD COLUMN IF NOT EXISTS "Estado" TEXT DEFAULT 'Pendiente',
  ADD COLUMN IF NOT EXISTS source_of_funds TEXT DEFAULT 'company',
  ADD COLUMN IF NOT EXISTS reimbursement_status TEXT DEFAULT 'not_applicable';

-- 5. TABLA AGENT_ALERTS SI NO EXISTE (para el sistema HITL)
CREATE TABLE IF NOT EXISTS public.agent_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    agent_id TEXT,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    confidence NUMERIC(5,2) DEFAULT 0,
    status TEXT DEFAULT 'pending',   -- pending | approved | rejected | snoozed
    action TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    actioned_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alerts_org ON public.agent_alerts(organization_id);

-- 6. TABLA TRIALS SI NO EXISTE (para el funnel de lead → trial)
CREATE TABLE IF NOT EXISTS public.trials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    company TEXT,
    session_token TEXT,
    status TEXT DEFAULT 'active',
    trial_end TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '14 days'),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. HABILITAR RLS EN NUEVAS TABLAS
ALTER TABLE public.quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_alerts ENABLE ROW LEVEL SECURITY;

-- 8. POLÍTICAS RLS PARA NUEVAS TABLAS
CREATE POLICY IF NOT EXISTS "Multi-tenant access" ON public.quotes
FOR ALL USING (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

CREATE POLICY IF NOT EXISTS "Multi-tenant access" ON public.agent_alerts
FOR ALL USING (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- =====================================================================
-- VERIFICACIÓN: Debería retornar las tablas corregidas
-- =====================================================================
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
