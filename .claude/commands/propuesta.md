Genera una propuesta comercial para el lead $ARGUMENTS usando el agente proposal-generator.

Pasos:

1. Obtener datos completos del lead:
```sql
SELECT id, name, email, phone, message, notes, project_description, status,
  NOW() - created_at AS antiguedad
FROM public.leads
WHERE organization_id = (SELECT id FROM public.organizations WHERE name = 'MD Asesorías Limitada')
  AND id = $ARGUMENTS::bigint;
```

2. Si el lead no está en estado 'Contactado' o 'Cotizado', advertir al usuario antes de continuar.

3. Usar el agente proposal-generator para:
   a. Analizar el perfil completo del lead (mensaje, notas previas, industria detectada)
   b. Seleccionar el plan más adecuado
   c. Generar la propuesta comercial personalizada
   d. Crear borrador de email con la propuesta en Gmail

4. Actualizar el lead:
```sql
UPDATE public.leads
SET status = 'Cotizado', last_interaction = NOW()
WHERE id = $ARGUMENTS::bigint;

SELECT public.append_lead_note(
  $ARGUMENTS::bigint,
  '{"fecha": "<now>", "accion": "propuesta-generada", "agente": "proposal-generator"}'::jsonb
);
```

5. Mostrar preview de la propuesta generada y confirmar si se desea enviar el borrador.
