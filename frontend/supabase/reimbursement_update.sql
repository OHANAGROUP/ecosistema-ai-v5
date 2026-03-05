-- ALPA Hub: Actualización para sistema de reembolsos de socios
-- Añade soporte para rastrear el origen de los fondos y el estado de reembolso

-- 1. Añadir columna source_of_funds (Origen de Fondos)
-- 'company' (defecto), 'pablo', 'alexis'
ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS source_of_funds TEXT DEFAULT 'company';

-- 2. Añadir columna reimbursement_status (Estado de Reembolso)
-- 'not_applicable' (defecto para gastos de empresa), 'pending' (para gastos de socios), 'reimbursed'
ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS reimbursement_status TEXT DEFAULT 'not_applicable';

-- 3. Comentario para documentación
COMMENT ON COLUMN public.transactions.source_of_funds IS 'Origen de los fondos: company, pablo, o alexis';
COMMENT ON COLUMN public.transactions.reimbursement_status IS 'Estado del reembolso: not_applicable, pending, o reimbursed';

-- 4. (Opcional) Migrar datos existentes
UPDATE public.transactions 
SET source_of_funds = 'company', reimbursement_status = 'not_applicable'
WHERE source_of_funds IS NULL;
