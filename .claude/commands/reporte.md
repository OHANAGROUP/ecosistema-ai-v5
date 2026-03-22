Genera el reporte del pipeline de ventas de AutomatizAI.cl para $ARGUMENTS (opciones: "hoy", "semana", "mes" — por defecto "hoy").

Pasos:

1. Obtener estadísticas generales del funnel:
```sql
SELECT
  status,
  COUNT(*) as cantidad,
  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as nuevos_7d,
  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as nuevos_30d,
  AVG(EXTRACT(EPOCH FROM (last_interaction - created_at))/3600)::int as horas_promedio_en_etapa
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
GROUP BY status
ORDER BY CASE status
  WHEN 'Nuevo' THEN 1 WHEN 'Contactado' THEN 2
  WHEN 'Cotizado' THEN 3 WHEN 'Ganado' THEN 4 WHEN 'Perdido' THEN 5
END;
```

2. Tasa de conversión por etapa:
```sql
WITH funnel AS (
  SELECT
    COUNT(*) FILTER (WHERE status != 'Nuevo') as contactados,
    COUNT(*) FILTER (WHERE status IN ('Cotizado','Ganado')) as cotizados,
    COUNT(*) FILTER (WHERE status = 'Ganado') as ganados,
    COUNT(*) as total
  FROM public.leads
  WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
    AND created_at >= NOW() - INTERVAL '30 days'
)
SELECT
  total,
  contactados,
  ROUND(100.0 * contactados / NULLIF(total,0), 1) as tasa_contacto_pct,
  cotizados,
  ROUND(100.0 * cotizados / NULLIF(contactados,0), 1) as tasa_cotizacion_pct,
  ganados,
  ROUND(100.0 * ganados / NULLIF(cotizados,0), 1) as tasa_cierre_pct
FROM funnel;
```

3. Leads nuevos en el período:
```sql
SELECT id, name, email, source, created_at, status
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND created_at >= CASE
    WHEN '$ARGUMENTS' = 'semana' THEN NOW() - INTERVAL '7 days'
    WHEN '$ARGUMENTS' = 'mes' THEN NOW() - INTERVAL '30 days'
    ELSE NOW() - INTERVAL '24 hours'
  END
ORDER BY created_at DESC;
```

4. Presentar reporte con:
   - Resumen ejecutivo en 3 bullets (qué está bien, qué necesita atención, acción prioritaria)
   - Tabla del funnel con conversiones
   - Lista de leads nuevos del período
   - Alertas: leads urgentes sin atender, leads estancados más de 7 días
   - Proyección de ingresos si los leads 'Cotizado' cierran (calcular en UF según plan probable)
