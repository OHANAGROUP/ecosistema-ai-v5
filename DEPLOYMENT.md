# Guía de Despliegue - ECOSISTEMA V5.0

Esta guía detalla los pasos para desplegar la plataforma en un entorno de producción usando **Vercel** para el frontend/backend y **Supabase** para la base de datos.

## 1. Pre-requisitos
- Cuenta en [Vercel](https://vercel.com).
- Cuenta en [Supabase](https://supabase.com).
- [Stripe CLI](https://stripe.com/docs/stripe-cli) (opcional, para pruebas de pagos).

## 2. Variables de Entorno Requeridas

Debes configurar estas variables en el panel de Vercel (Settings -> Environment Variables):

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_URL` | URL de tu proyecto en Supabase. |
| `SUPABASE_ANON_KEY` | La 'anon public' key de Supabase. |
| `SUPABASE_SERVICE_ROLE_KEY` | La 'service_role' key (mantener secreta). |
| `JWT_SECRET` | Una cadena aleatoria larga para firmar tokens. |
| `ENVIRONMENT` | Establecer a `production`. |
| `STRIPE_SECRET_KEY` | Tu Secret Key de Stripe. |

## 3. Pasos de Despliegue

1. **Conectar Repositorio:** Vincula tu repo de GitHub a un nuevo proyecto en Vercel.
2. **Framework Preset:** Vercel debería detectar automáticamente el proyecto o usar `Other`.
3. **Configurar `vercel.json`:** Ya está incluido en la raíz y orquestará la API `/api` y los estáticos en `/`.
4. **Deploy:** Click en **Deploy**.

## 4. Configuración de Supabase
Asegúrate de ejecutar los scripts de migración en el SQL Editor de Supabase:
1. `backend/scripts/migrations/document_sequences.sql`
2. `backend/scripts/monitoring_views.sql`

---
*Documentación generada por Antigravity AI - v5.0.1-prd*
