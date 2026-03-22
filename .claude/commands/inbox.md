Revisa el pipeline de leads de AutomatizAI.cl. Ejecuta los siguientes pasos:

1. Consulta en Supabase todos los leads activos agrupados por status:
```sql
SELECT
  status,
  COUNT(*) as cantidad,
  MIN(created_at) as mas_antiguo,
  MAX(created_at) as mas_reciente,
  COUNT(*) FILTER (WHERE last_interaction < NOW() - INTERVAL '24 hours') as sin_actividad_24h
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND status NOT IN ('Ganado', 'Perdido')
GROUP BY status
ORDER BY CASE status
  WHEN 'Nuevo' THEN 1
  WHEN 'Contactado' THEN 2
  WHEN 'Cotizado' THEN 3
  ELSE 4
END;
```

2. Lista los leads 'Nuevo' que aún no han sido contactados:
```sql
SELECT id, name, email, phone, message, created_at,
  NOW() - created_at AS tiempo_espera
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND status = 'Nuevo'
ORDER BY created_at ASC;
```

3. Muestra un resumen visual del pipeline con:
   - Conteo por etapa
   - Alertas de leads urgentes (Nuevo > 4h sin contacto)
   - Leads que necesitan seguimiento hoy

4. Para cada lead 'Nuevo' encontrado, usa el agente sales-qualifier para calificarlo.

5. Sugiere las 3 acciones más prioritarias para hacer ahora.
