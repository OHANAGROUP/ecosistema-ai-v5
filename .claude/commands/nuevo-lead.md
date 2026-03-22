Procesa el lead con ID $ARGUMENTS (o el lead más reciente si no se especifica ID).

Pasos:

1. Obtener datos del lead desde Supabase:
```sql
SELECT id, name, email, phone, message, status, source, created_at, notes
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND ($ARGUMENTS IS NULL OR id = $ARGUMENTS::bigint)
ORDER BY created_at DESC
LIMIT 1;
```

2. Usar el agente sales-qualifier para analizar el lead y asignar score BANT+.

3. Basándose en el score:
   - Score 8-10 (HOT): Usa el agente lead-manager para preparar email de contacto inmediato y propuesta preliminar
   - Score 6-7 (WARM): Usa el agente lead-manager para preparar email de bienvenida + caso de uso relevante
   - Score 4-5 (COOL): Prepara email de bienvenida estándar con enlace al trial
   - Score 1-3 (COLD): Agrega a secuencia de nurturing, sin acción inmediata urgente

4. Crear borrador de email de primer contacto en Gmail con el agente lead-manager.

5. Actualizar el lead en Supabase:
   - Cambiar status de 'Nuevo' a 'Contactado'
   - Agregar nota con score, categoría y acción tomada:
```sql
SELECT public.append_lead_note(
  <id>,
  '{"fecha": "<now>", "accion": "primer-contacto", "score": <score>, "categoria": "<HOT/WARM/COOL/COLD>", "plan_sugerido": "<plan>", "agente": "lead-manager"}'::jsonb
);
UPDATE public.leads SET status = 'Contactado', last_interaction = NOW() WHERE id = <id>;
```

6. Crear recordatorio en Google Calendar para el seguimiento según la categoría:
   - HOT: Seguimiento en 2 horas
   - WARM: Seguimiento en 24 horas
   - COOL: Seguimiento en 3 días
   - COLD: Seguimiento en 7 días

7. Mostrar resumen de lo ejecutado.
