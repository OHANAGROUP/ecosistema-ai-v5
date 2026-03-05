# AgentOS v5.0 — Ecosistema de Inteligencia Operativa 🚀

**AgentOS v5.0** es un ERP inteligente para empresas de construcción e ingeniería, con una capa de **agentes autónomos de nivel 5** que orquesta acciones correctivas, detecta fraudes complejos, aprueba presupuestos y garantiza cumplimiento regulatorio en tiempo real.

**URL en producción:** https://saas-experimental-con-ecosistema-v5.vercel.app
**Repositorio:** https://github.com/OHANAGROUP/ecosistema-ai-v5

---

## 🏗️ Arquitectura General

```
Frontend (Vercel / Static)
    ├── landing.html         ← Landing pública de captación
    ├── index.html           ← App principal (autenticada)
    ├── onboarding.html      ← Flujo de onboarding
    ├── register.html        ← Registro de cuentas
    └── modules/             ← 11 módulos ERP
          ├── dashboard/
          ├── agentes/
          ├── contabilidad/
          ├── cotizador/
          ├── inventario/
          ├── leads/
          ├── ordenes/
          ├── directorio/
          ├── estados_pago/
          ├── auditoria/
          └── manager/

Backend (FastAPI · Railway)
    ├── main.py              ← API hardened v5.0.1-prd-secure
    ├── agents.py            ← Orquestador + Agentes IA (52 KB)
    ├── core/
    │     ├── auth.py        ← JWT + tenant isolation
    │     ├── database.py    ← Supabase client
    │     └── email_service.py ← Resend integration
    ├── billing/             ← Planes, upgrades, suscripciones
    └── learning/            ← Sistema RLHF / aprendizaje continuo

Base de Datos (Supabase · PostgreSQL v5.0.5)
    ├── Esquema snake_case unificado
    ├── Row Level Security (RLS) en todas las tablas
    ├── Audit logs centralizados
    └── Prisma ORM v5.10.0 (multi-schema: public + auth)
```

---

## 🤖 Arquitectura de Agentes (Hub & Spoke)

1. **Agente Director (Orquestador Lvl 5)**: Ingiere datos, triangula con SII y delega a especialistas.
2. **Agentes Especialistas**:
   - **Financiero**: Costos, desvíos presupuestarios, lucro cesante.
   - **RR.HH.**: Control de staff, seguros, conflictos de interés.
   - **Legal**: Auditoría de contratos, cumplimiento Ley 21.600.
3. **Agente Árbitro (HITL)**: Evalúa coherencia entre especialistas. Ante paradojas, escala a supervisión humana.

### Componentes Core
- **SK-VAL (MJ-01)**: Validador semántico de datos antes de procesar.
- **Memory Bus (MJ-05)**: Bus asíncrono de comunicación entre agentes.
- **TaxTools / BankTools / LegalTools**: Function Calling para triangulación SII/ERP/bancos.
- **Learning System**: Ciclo RLHF — cada hallazgo se convierte en regla persistente.
- **Groq Fallback**: Resiliencia ante rate limits de Gemini con fallback automático a Groq.

---

## 🛡️ Seguridad (Hardening Activo)

| Control | Estado |
|---|---|
| Row Level Security (RLS) | ✅ Activo — aislamiento por `organization_id` |
| JWT Secret ≥ 64 chars | ✅ Validado en startup |
| Audit Logging | ✅ Tabla `audit_logs` en Supabase |
| Rate Limiting | ✅ Middleware activo |
| Security Headers | ✅ X-Frame-Options, HSTS, CSP, X-XSS |
| Request Size Limit | ✅ Máx 5 MB |
| CORS Whitelist | ✅ Solo dominio Vercel + localhost dev |
| Docs desactivados en prod | ✅ `/docs` y `/redoc` solo en dev |

---

## 🚀 Endpoints API Principales

```
POST   /api/v1/auth/register         → Registro org + trial 14 días
POST   /api/v1/trials/register       → Trial rápido (público)
POST   /api/v1/agents/cycle          → Inicia ciclo de agentes [JWT]
GET    /api/v1/agents/cycle/{id}     → Estado del ciclo [JWT]
GET    /api/v1/agents/health         → Health check público
POST   /api/v1/agents/feedback       → APROBAR/RECHAZAR decisión [JWT]
GET    /api/v1/agents/signals        → Señales activas [JWT]
POST   /api/v1/alerts/{id}/action    → Acción sobre alerta HITL [JWT]
/api/v1/billing/*                    → Router de billetería [JWT]
```

---

## 📦 Instalación y Desarrollo

```bash
# Requisitos: Node.js 18+ y Python 3.10+
npm run install:all

# Desarrollo local
npm run dev              # Frontend en http://localhost:3000
cd backend && uvicorn main:app --reload  # Backend en :8000
```

### Variables de entorno requeridas (backend/.env)
```
SUPABASE_URL=
SUPABASE_KEY=
JWT_SECRET=         # Mínimo 64 caracteres
ENVIRONMENT=        # production | development
RESEND_API_KEY=     # Opcional — emails de bienvenida
FRONTEND_URL=       # URL del frontend en Vercel
```

---

## 🧪 Suite de Tests

```bash
# Tests de estrés por escenario
python -m backend.tests.phantom_addendum_test   # Addendum fantasma
python -m backend.tests.omega_test              # Omega Level (extremo)
python -m backend.tests.director_test           # Orquestación Director
```

---

## 📊 Estado del Sistema (v5.0.5)

| Componente | Estado |
|---|---|
| Migración SQL v5.0.5 | ✅ Aplicada |
| RLS multi-tenant | ✅ Verificado |
| Prisma DB sync | ✅ `npx prisma db pull` completado |
| Usuario admin@alpa.cl | ✅ Activo en Root Org |
| Trial system | ✅ Token único + 14 días + email welcome |
| Alert persistence (HITL) | ✅ `agent_alerts` + acciones persistidas |
| Dashboard health panel | ✅ Budget, spending, semáforo |
| Soft delete transacciones | ✅ Estado "Anulada" + strikethrough UI |

---

*AgentOS v5.0: De la auditoría reactiva a la inteligencia operativa autónoma.*
