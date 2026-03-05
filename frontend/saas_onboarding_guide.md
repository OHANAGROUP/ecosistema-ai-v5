# Guía de Onboarding SaaS - Fase 2

Este documento detalla el flujo para entregar el MVP a nuevas empresas y cómo funciona la creación de cuentas en la arquitectura Multi-Tenant.

## 🚀 Flujo de Registro (Automatizado)

No necesitas crear usuarios manualmente en Supabase. El sistema está diseñado para que sea **Self-Service**:

1. **URL de Registro**: El nuevo cliente accede a `tu-app.vercel.app/register.html`.
2. **Formulario**: Ingresa el Nombre de la Empresa, su Email y Contraseña.
3. **Magia en la Base de Datos**: Al momento de crearse el usuario en Supabase, se ejecutan automáticamente los siguientes pasos:
    - Se crea un registro único en la tabla `organizations`.
    - Se vincula al usuario como **Administrador** de esa organización.
    - Se le asigna un `organization_id` único que aislará sus datos de los de otros clientes.

## 📦 Entrega a Clientes

Para entregar el producto a una nueva constructora o empresa:

1. **Envío de Link**: Simplemente envíales el link de registro.
2. **Validación**: Una vez registrados, ellos entrarán a un dashboard vacío, listo para que carguen sus propios proyectos y transacciones.
3. **Aislamiento Total**: Aunque usen la misma base de datos, las políticas de seguridad (RLS) que reparamos aseguran que **NUNCA** vean los datos de ALPA ni de otras empresas.

## 🛠️ Acciones Recomendadas para Fase 2

- [ ] **Personalización de Marca**: Podemos añadir un logo de la empresa cliente en su dashboard basándonos en su `organization_id`.
- [ ] **Gestión de Usuarios**: El administrador de la empresa cliente podrá invitar a sus propios colaboradores (esto requiere una vista de "Equipo").
- [ ] **Pruebas de Estrés**: Crear una cuenta de prueba (`test@constructora.cl`) para verificar que el aislamiento funciona al 100%.

> [!NOTE]
> Tu cuenta actual (`ppalomino@hotmail.com`) ya está vinculada a la organización portadora de los datos de ALPA. Los nuevos usuarios tendrán sus propias organizaciones vacías por defecto.
