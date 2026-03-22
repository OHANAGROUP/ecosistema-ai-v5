Ejecuta los seguimientos pendientes del pipeline de AutomatizAI.cl usando el agente follow-up-agent.

Pasos:

1. Detectar todos los leads que necesitan seguimiento hoy:
```sql
SELECT
  id, name, email, phone, status, message, notes,
  last_interaction,
  NOW() - last_interaction AS tiempo_sin_actividad,
  CASE
    WHEN status = 'Nuevo' AND last_interaction < NOW() - INTERVAL '4 hours' THEN 'URGENTE - Sin primer contacto'
    WHEN status = 'Contactado' AND last_interaction < NOW() - INTERVAL '3 days' THEN 'Follow-up requerido'
    WHEN status = 'Contactado' AND last_interaction < NOW() - INTERVAL '7 days' THEN 'Follow-up #2 urgente'
    WHEN status = 'Cotizado' AND last_interaction < NOW() - INTERVAL '2 days' THEN 'Confirmar cotización'
    WHEN status = 'Cotizado' AND last_interaction < NOW() - INTERVAL '5 days' THEN 'Follow-up cotización urgente'
    ELSE 'Seguimiento programado'
  END AS tipo_accion
FROM public.leads
WHERE
  organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND status NOT IN ('Ganado', 'Perdido')
  AND (
    (status = 'Nuevo' AND last_interaction < NOW() - INTERVAL '4 hours')
    OR (status = 'Contactado' AND last_interaction < NOW() - INTERVAL '3 days')
    OR (status = 'Cotizado' AND last_interaction < NOW() - INTERVAL '2 days')
  )
ORDER BY last_interaction ASC;
```

2. Para cada lead encontrado, usar el agente follow-up-agent para:
   a. Determinar en qué paso de la secuencia está (revisar notes)
   b. Generar el email de seguimiento apropiado
   c. Crear borrador en Gmail
   d. Actualizar last_interaction y agregar nota en leads

3. Crear eventos en Google Calendar para los próximos seguimientos necesarios.

4. Mostrar resumen:
   - N leads procesados
   - N borradores de email creados
   - N recordatorios en Calendar
   - Lista de leads con acción urgente pendiente
