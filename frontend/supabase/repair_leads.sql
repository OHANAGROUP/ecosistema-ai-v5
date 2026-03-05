-- ALPA SAAS - Lead Data Repair Script
-- Purpose: Recover leads sent to wrong Org ID and fix "Sin Nombre" placeholders

-- 1. Migrate leads from the incorrect Org ID to ALPA SPA
UPDATE public.leads
SET organization_id = '6f6e0016-cff7-48ad-8910-836dedf7d127'
WHERE organization_id = '6fbc0841-8693-4a6c-939e-4c7407887e07';

-- 2. Repair "Sin Nombre" using email if available
UPDATE public.leads
SET name = split_part(email, '@', 1)
WHERE (name = 'Sin Nombre' OR name IS NULL OR name = '')
AND email IS NOT NULL 
AND email LIKE '%@%';

-- 3. Sync project_description from message if project_description is empty
UPDATE public.leads
SET project_description = message
WHERE (project_description IS NULL OR project_description = '')
AND (message IS NOT NULL AND message != '');

-- 4. Verification Check
-- SELECT id, name, email, origin, organization_id, project_description 
-- FROM public.leads 
-- WHERE organization_id = '6f6e0016-cff7-48ad-8910-836dedf7d127'
-- ORDER BY created_at DESC;
