# AgentOS v5.0 Reload - Ecosistema de Inteligencia Operativa 🚀

**AgentOS v5.0** es la evolución final de ECOSISTEMA V5.0, transformada en una plataforma de agentes autónomos de **Nivel 5**. No solo audita datos financieros, sino que orquesta acciones correctivas, detecta fraudes complejos y garantiza el cumplimiento regulatorio en tiempo real.

## 🏗️ Arquitectura de Agentes (Hub & Spoke)

El sistema opera bajo un modelo de orquestación jerárquica:

1.  **Agente Director (Orquestador Lvl 5)**: Punto de entrada único. Ingiere datos, triangula con fuentes externas (SII) y delega a los especialistas.
2.  **Agentes Especialistas**:
    *   **Financiero**: Análisis de costos, desvíos presupuestarios y lucro cesante.
    *   **Recursos Humanos**: Control de staff, cumplimiento de seguros y detección de conflictos de interés.
    *   **Legal**: Auditoría de contratos y cumplimiento de normativas (específicamente la **Ley 21.600**).
3.  **Agente Árbitro (Consenso & HITL)**: Evalúa la coherencia entre especialistas. Ante paradojas (ej. Financiero OK vs Legal ILEGAL), reduce el score de confianza y gatilla la intervención humana (Human-in-the-loop).

## 🛠️ Componentes Core

-   **SK-VAL (MJ-01)**: Validador semántico que garantiza que los agentes trabajen solo sobre datos íntegros y sensibles.
-   **Memory Bus (MJ-05)**: Bus de comunicación asíncrona que permite "cross-talk" entre agentes para detectar riesgos interdisciplinarios.
-   **Action Tools (Function Calling)**:
    *   `TaxTools`: Triangulación SII vs ERP.
    *   `BankTools`: Arbitraje bancario autónomo para saneamiento de sobregiros.
    *   `LegalTools`: Verificación de cumplimiento previsional (F30).
-   **Prisma ORM**: Capa de persistencia moderna con soporte para múltiples esquemas (`public`, `auth`) y seguridad tipada.
-   **Hardened Security**: Aislamiento multi-tenant mediante RLS (Row Level Security) y auditoría centralizada.
-   **Learning System (P2/RLHF)**: Ciclo de retroalimentación que convierte cada hallazgo en una regla de negocio persistente.

## 🚀 Cómo ejecutar el proyecto

### Requisitos previos
- Node.js y Python 3.10+
- Acceso a Supabase (URL y Key en `.env`)

### Instalación rápida
```bash
npm run install:all
```

### Suite de Pruebas de Estrés (Stress Tests)
Para validar el sistema en escenarios críticos, utiliza los scripts de test especializados:
- **Phantom Addendum**: `python -m backend.tests.phantom_addendum_test`
- **Omega Level (Dificultad Extrema)**: `python -m backend.tests.omega_test`
- **Director Orchestration**: `python -m backend.tests.director_test`

## 📊 Dashboard de Valor (ROI)
El sistema rastrea el ahorro generado mes a mes mediante el `savings_tracker`, permitiendo al CEO visualizar el retorno de inversión directo de la inteligencia artificial.

---
*AgentOS v5.0: De la auditoría reactiva a la inteligencia operativa autónoma.*
