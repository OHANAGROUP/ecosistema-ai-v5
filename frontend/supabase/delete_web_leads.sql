-- SCRIPT PARA BORRAR LEADS DE LA WEB
-- Úsalo para limpiar duplicados o leads de prueba generados por el formulario.

-- 1. VERIFICAR antes de borrar (recomendado)
-- SELECT count(*) FROM leads 
-- WHERE origin IN ('WEB_EXTERNA_V3', 'WEB_FORM_BACKUP', 'Web', 'Web Lead', 'WEB_EXTERNA', 'WEB_FORM_TEMPLATE');

-- 2. EJECUTAR BORRADO
-- ADVERTENCIA: Esta acción es irreversible. Asegúrate de haber verificado antes.

DELETE FROM leads 
WHERE origin IN (
    'WEB_EXTERNA_V3', 
    'WEB_FORM_BACKUP', 
    'Web', 
    'Web Lead', 
    'WEB_EXTERNA', 
    'WEB_FORM_TEMPLATE'
);

-- Opcional: Borrar solo de una organización específica si tienes varias
-- DELETE FROM leads 
-- WHERE organization_id = '6f6e0016-cff7-48ad-8910-836dedf7d127' -- Alpa SPA
-- AND origin IN ('WEB_EXTERNA_V3', 'WEB_FORM_BACKUP', 'Web');
