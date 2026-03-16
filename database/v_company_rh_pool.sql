-- v_company_rh_pool
-- Vista para AgenteRH: expone métricas de RH por organización y empresa.
-- Como organizations no tiene columnas RH, retorna valores por defecto razonables.
-- AgenteRH hace merge con pool_de_datos del request (línea 1261 agents.py), así que
-- si el cliente no ha cargado datos RH reales, el agente usa los datos del request.
-- Ejecutar en Supabase SQL Editor.

CREATE OR REPLACE VIEW public.v_company_rh_pool AS
SELECT
    o.id                                    AS organization_id,
    o.name                                  AS empresa,
    o.plan_type,
    o.status,
    -- Métricas RH con defaults razonables (cliente puede actualizar via settings)
    COALESCE((o.settings->>'n_empleados')::int,      5)     AS n_empleados,
    COALESCE((o.settings->>'headcount_ratio')::float, 1.0)  AS headcount_ratio,
    COALESCE((o.settings->>'enps_score')::float,     30.0)  AS enps_score,
    COALESCE((o.settings->>'tasa_rotacion')::float,   0.10) AS tasa_rotacion,
    COALESCE((o.settings->>'engagement_score')::float, 0.7) AS engagement_score,
    -- Conteo de transacciones laborales (tipo 'sueldo', 'honorario', 'remuneracion')
    COALESCE(labor.total_remuneraciones, 0)                  AS total_remuneraciones_mes,
    COALESCE(labor.n_pagos,              0)                  AS n_pagos_laborales_mes
FROM public.organizations o
LEFT JOIN (
    SELECT
        organization_id,
        COUNT(*)                                             AS n_pagos,
        SUM(ABS(amount))                                     AS total_remuneraciones
    FROM public.transactions
    WHERE
        DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        AND (
            LOWER(category)    LIKE '%sueldo%'      OR
            LOWER(category)    LIKE '%honorario%'   OR
            LOWER(category)    LIKE '%remuner%'     OR
            LOWER(description) LIKE '%sueldo%'      OR
            LOWER(description) LIKE '%honorario%'
        )
    GROUP BY organization_id
) labor ON labor.organization_id = o.id;
