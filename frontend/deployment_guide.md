# Guía de Acceso y Despliegue: ECOSISTEMA V5.0

Tienes 3 formas de compartir la aplicación con tus colegas, dependiendo de dónde estén ellos física y técnicamente.

## Opción 1: Servidor Local (Recomendado) - ¡SIN ERRORES!
Si ves avisos de "Tracking Prevention" o errores de seguridad al abrir los archivos, es porque el navegador bloquea funciones avanzadas en archivos locales (`file:///`).

**Cómo arreglarlo:**
1.  **VS Code:** Instala la extensión **"Live Server"**. Luego, haz clic derecho en `index.html` y selecciona "Open with Live Server".
2.  **Python:** Si tienes Python instalado, abre una terminal en la carpeta y escribe:
    `python -m http.server 8080`
3.  **Acceso:** Abre `http://localhost:8080`. Esto eliminará todos los avisos de seguridad y permitirá que el sistema guarde datos correctamente.

---

## Opción 2: Red Local (Compartir con Colegas)
Si quieres que otros en tu oficina vean la app:
1.  Usa los métodos del punto anterior.
2.  Dile a tus colegas que abran: `http://[TU-IP]:8080` (ej: `http://192.168.1.5:8080`).

*Nota: Tu computador debe permanecer encendido.*

---

## Opción 2: Demostración Remota (Internet)
Si quieres mostrarlo a alguien que **NO está en tu oficina** (ej: cliente remoto), puedes usar una herramienta de "Túnel" temporal.

**Recomendado: Ngrok**
1.  Descarga [Ngrok](https://ngrok.com/download).
2.  Abre otra terminal y ejecuta:
    ```powershell
    ngrok http 8080
    ```
3.  Te dará una URL pública (ej: `https://a1b2-c3d4.ngrok.io`).
4.  Comparte ese link. Funciona en cualquier parte del mundo mientras tu PC esté encendido.

---

## Opción 3: Despliegue Profesional (SaaS Real)
Para que la app funcione **24/7 sin depender de tu computador**, debes subirla a la nube.

**Proveedores Gratuitos Recomendados:**
1.  **Vercel** (Ideal para este tipo de apps)
2.  **Netlify**
3.  **GitHub Pages**

**Pasos para Vercel (Ejemplo):**
1.  Instala Vercel CLI: `npm i -g vercel`
2.  Ejecuta: `vercel`
3.  Sigue las instrucciones (Enter, Enter, Enter...)
4.  Te dará una URL final `https://saas-alpa-unificado.vercel.app`.

---

## 🎨 Branding y Multi-Tenant (V3.0)
La nueva versión del Hub permite gestionar múltiples empresas (ALPA, VAJ, DIBELL) desde un solo lugar.

**Para configurar una nueva empresa:**
1. Edita `SHARED/config.js`.
2. Agrega el nuevo perfil de empresa en el objeto `tenants`.
3. Los módulos heredarán automáticamente los estilos mediante el `branding-engine.js`.

---

## 🔒 Nota sobre Seguridad
Actualmente, el login valida contra una lista local o Google Script.
- Si usas la **Opción 1**, es seguro dentro de tu red local.
- Si usas la **Opción 3** (Nube), asegúrate de que el backend de Google SDK/Apps Script permita peticiones desde el nuevo dominio.
- **Auditoría V3.1**: Se han centralizado las configuraciones para evitar la fuga de URLs de backend en archivos individuales.
