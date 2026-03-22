# AutomatizAI SaaS v5.0 — MD Asesorías Limitada

## Empresa Operadora
- **Razón Social:** MD Asesorías Limitada
- **Producto:** AutomatizAI.cl — Plataforma SaaS de agentes IA para PYMEs chilenas
- **Rol de Claude:** Asistente de desarrollo + Gestor de pipeline de ventas

## Stack Técnico
- **Frontend:** Vanilla HTML/JS modular → Vercel (ecosistema-ai-v50.vercel.app / automatizai.cl)
- **Backend:** FastAPI Python 3.11 + uvicorn → Railway
- **Database:** Supabase PostgreSQL con RLS + Auth (organization_id como tenant)
- **AI:** Anthropic Claude SDK (claude-sonnet-4-6-20251001 por defecto)
- **Pagos:** Stripe (pendiente — cuenta empresa en trámite)

## Estructura del Proyecto
```
backend/
  main.py              → FastAPI app principal
  agents.py            → AgentOrchestrator + agentes IA (Financiero, RH, Legal)
  operator_tools.py    → Herramientas AgenteOperador (cross-tenant, solo MD Asesorías)
  billing.py           → Stripe billing router
  financial_tools.py   → Herramientas financieras
  core/
    auth.py            → JWT auth + get_current_user
    database.py        → Supabase client

frontend/
  supabase_schema.sql  → Schema completo PostgreSQL
  supabase/
    migrations/        → Migraciones aplicadas
    leads_migration.sql → Leads table enhancement
```

## Schema de Leads (tabla public.leads)
```sql
id              BIGINT PRIMARY KEY
organization_id UUID (FK organizations)
name            TEXT
email           TEXT
phone           TEXT
message         TEXT          -- Mensaje del formulario web
status          TEXT          -- 'Nuevo' | 'Contactado' | 'Cotizado' | 'Ganado' | 'Perdido'
source          TEXT          -- 'Web' (formulario automatizai.cl)
notes           JSONB []      -- Historial de notas/interacciones
assigned_to     TEXT          -- Nombre del responsable
project_description TEXT      -- Descripción del proyecto del lead
last_interaction TIMESTAMPTZ
created_at      TIMESTAMPTZ
```

## Funnel de Ventas (estados de leads)
1. **Nuevo** → Lead recién llegado del formulario web
2. **Contactado** → Se hizo primer contacto (email/llamada)
3. **Cotizado** → Se envió propuesta comercial
4. **Ganado** → Cerrado y en onboarding
5. **Perdido** → Descartado con motivo

## Planes y Precios AutomatizAI
- **Starter:** 2 UF/mes — 1 agente, datos básicos, soporte email
- **Empresa:** 3.5 UF/mes — 3 agentes, módulos completos, soporte prioritario
- **Enterprise:** 10 UF/mes — agentes ilimitados, integraciones custom, soporte 24/7
- **Trial:** Gratis 14 días (acceso Empresa)

## Comandos Clave
```bash
# Backend (Railway)
cd backend && uvicorn main:app --reload   # local
railway up                                # deploy

# Frontend (Vercel)
vercel --prod                             # deploy frontend

# DB
supabase db push                         # aplicar migraciones
```

## Patrones Prohibidos
- NO commitear secrets o API keys
- NO modificar backend/venv/
- NO usar console.log en código de producción
- NO exponer SUPABASE_SERVICE_ROLE_KEY al frontend

## Organization ID MD Asesorías (para queries de leads)
Variable de entorno: ADMIN_ORG_ID o consultar tabla organizations WHERE name = 'MD Asesorías Limitada'
