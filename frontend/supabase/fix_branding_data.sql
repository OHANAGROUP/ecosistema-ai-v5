-- =====================================================================
-- FIX DE BRANDING (V3 - REPARADO) - MD ASESORIAS LTDA
-- Ejecutar en Supabase SQL Editor
-- Resuelve: ERROR: violations check constraint "organizations_plan_type_check"
-- =====================================================================

-- 1. ASEGURAR QUE LAS COLUMNAS DE BRANDING EXISTAN
ALTER TABLE public.organizations 
  ADD COLUMN IF NOT EXISTS rut TEXT,
  ADD COLUMN IF NOT EXISTS address TEXT,
  ADD COLUMN IF NOT EXISTS phone TEXT,
  ADD COLUMN IF NOT EXISTS email TEXT,
  ADD COLUMN IF NOT EXISTS logo_url TEXT,
  ADD COLUMN IF NOT EXISTS plan_type TEXT DEFAULT 'trial',
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

-- 2. INSERTAR O ACTUALIZAR LOS DATOS DE LA ORGANIZACIÓN
-- 'trial' es un valor seguro para el check constraint.
INSERT INTO public.organizations (id, name, rut, address, phone, email, status, logo_url, plan_type)
VALUES (
    '0e431197-711a-4f12-8ca9-e2ecbf7f91ed', 
    'MD ASESORIAS LTDA', 
    '76.123.456-7', 
    'Avenida Siempre Viva 123, Santiago', 
    '+56 9 1234 5678', 
    'contacto@mdasesorias.cl', 
    'active',
    'https://automatizai.cl/assets/img/don_alpa.png',
    'trial'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    rut = EXCLUDED.rut,
    address = EXCLUDED.address,
    phone = EXCLUDED.phone,
    email = EXCLUDED.email,
    logo_url = EXCLUDED.logo_url,
    status = EXCLUDED.status,
    plan_type = EXCLUDED.plan_type;

-- 3. VERIFICACIÓN: Mostrar resultado
SELECT id, name, rut, status, logo_url 
FROM public.organizations 
WHERE id = '0e431197-711a-4f12-8ca9-e2ecbf7f91ed';
