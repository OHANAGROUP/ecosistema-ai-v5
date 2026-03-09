# Estrategia de Actualización Segura (SaaS)

Esta guía explica cómo podemos mejorar la plataforma ALPA sin interrumpir el trabajo de tus clientes actuales. El secreto está en la **separación de ambientes**.

## 1. Ambientes de Trabajo 🏗️

Para un SaaS profesional, dividimos el sistema en 3 "viviendas" separadas:

| Ambiente | Propósito | ¿Quién lo ve? | URL Ejemplo |
| :--- | :--- | :--- | :--- |
| **Desarrollo (Local)** | Hacer pruebas locas y breaking changes. | Tú y yo (en VS Code). | `localhost:8080` |
| **Staging (Vercel Preview)** | Probar las mejoras en un link real antes de lanzarlas. | Tú (para aprobar cambios). | `alpa-staging.vercel.app` |
| **Producción (Live)** | El sistema estable que usan los clientes. | Tus Clientes. | `alpa-saas.vercel.app` |

---

## 2. Flujo de Mejora Continua 🔄

Cuando quieras agregar una función (ej: "Módulo de Reportes Pro"):

1. **Crear una Rama (Branch)**: En Git, creamos una rama paralela llamada `feature-reports`.
2. **Despliegue de Prueba**: Subimos esa rama a Vercel. Vercel nos dará un link **único** solo para esa mejora. 
3. **Validación**: Tú entras a ese link, pruebas que todo funcione bien y que no afecte nada más.
4. **Fusión (Merge)**: Una vez aprobado, el código se "fusiona" con la versión principal (`master`) y se actualiza el sitio oficial para todos en segundos.

---
- [x] Fix Auth Bridge in `agentes/index.html` (Token extraction from Parent)
- [x] Unified `vercel.json` at root + Global Cache Bust (`v=4.1.0`)
- [x] Final Ecosystem URL Strategy (`/ecosistema`)
- [ ] Verify AI Cycle 200 OK after entering new Dashboard
- [ ] User confirmation of 404-free access

---

## 3. Seguridad de Base de Datos 🗄️

¿Qué pasa si cambiamos la base de datos?
- **Cambios Aditivos solamente**: Nunca borramos columnas que los clientes estén usando. Si necesitamos una nueva función, **agregamos** columnas nuevas. Las versiones viejas del programa simplemente ignorarán lo nuevo, y las nuevas lo aprovecharán.
- **Migraciones en Staging**: Antes de aplicar un cambio SQL en Producción, lo corremos en una base de datos de prueba idéntica.

---

## 4. Control de Caché (Versionado) 🏷️

Para evitar que los clientes vean errores por tener "archivos viejos" guardados en su navegador:
- Usamos la variable `VERSION` en `config.js`.
- Al subir una mejora, cambiamos de `v3.1.8` a `v3.1.9`.
- Esto "obliga" a todos los navegadores a descargar el código nuevo al instante, eliminando errores de sincronización.

---

> [!IMPORTANT]
> **Con esta estrategia, el riesgo de "echar a perder" el programa de un cliente es prácticamente 0%.** Es la misma metodología que usan empresas como Facebook o Slack para actualizarse diario sin que nadie lo note.
