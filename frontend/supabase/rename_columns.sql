-- Renombrar columnas para que coincidan con core.js
-- Ejecuta esto en Supabase SQL Editor

-- =====================================================
-- PROJECTS TABLE - Renombrar columnas
-- =====================================================
ALTER TABLE public.projects 
RENAME COLUMN id TO "ID";

ALTER TABLE public.projects 
RENAME COLUMN name TO "Nombre";

ALTER TABLE public.projects 
RENAME COLUMN code TO "Codigo";

ALTER TABLE public.projects 
RENAME COLUMN client TO "Cliente";

ALTER TABLE public.projects 
RENAME COLUMN budget TO "Presupuesto";

ALTER TABLE public.projects 
RENAME COLUMN status TO "Estado";

ALTER TABLE public.projects 
RENAME COLUMN start_date TO "FechaInicio";

ALTER TABLE public.projects 
RENAME COLUMN end_date TO "FechaTermino";

ALTER TABLE public.projects 
RENAME COLUMN responsible TO "Responsable";

-- Agregar columnas faltantes en projects
ALTER TABLE public.projects 
ADD COLUMN IF NOT EXISTS "GastoReal" NUMERIC DEFAULT 0;

ALTER TABLE public.projects 
ADD COLUMN IF NOT EXISTS "Margen" NUMERIC DEFAULT 0;

ALTER TABLE public.projects 
ADD COLUMN IF NOT EXISTS "PorcentajeAvance" NUMERIC DEFAULT 0;

-- =====================================================
-- TRANSACTIONS TABLE - Renombrar columnas
-- =====================================================
ALTER TABLE public.transactions 
RENAME COLUMN id TO "ID";

ALTER TABLE public.transactions 
RENAME COLUMN date TO "Fecha";

ALTER TABLE public.transactions 
RENAME COLUMN type TO "Tipo";

ALTER TABLE public.transactions 
RENAME COLUMN category TO "Categoría";

ALTER TABLE public.transactions 
RENAME COLUMN amount TO "Monto";

ALTER TABLE public.transactions 
RENAME COLUMN description TO "Descripción";

ALTER TABLE public.transactions 
RENAME COLUMN status TO "Estado";

-- Agregar columnas faltantes en transactions
ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "SubCategoría" TEXT;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "Moneda" TEXT DEFAULT 'CLP';

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "Timestamp" TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "ProyectoID" TEXT;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "DocumentoID" TEXT;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "RendicionID" TEXT;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "IVA" NUMERIC DEFAULT 0;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "Retencion" NUMERIC DEFAULT 0;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "Total" NUMERIC DEFAULT 0;

ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS "Usuario" TEXT;

-- =====================================================
-- Verificación
-- =====================================================
-- Ejecuta esto después para verificar:
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_schema = 'public' AND table_name = 'projects'
-- ORDER BY ordinal_position;
