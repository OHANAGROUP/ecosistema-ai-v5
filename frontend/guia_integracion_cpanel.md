# Guía Paso a Paso: Integración de Formulario en CPanel

Según la imagen de tu Administrador de Archivos, aquí tienes los pasos exactos para conectar tu web con el nuevo **Embudo de Ventas**.

## Paso 1: Localizar el archivo
En tu CPanel, dentro de la carpeta `public_html`, busca el archivo **`contact.html`**.

## Paso 2: Abrir el Editor
1. Haz clic derecho sobre `contact.html`.
2. Selecciona **"Edit"** (o "Editar").

## Paso 3: Insertar el Código del Formulario
Busca el lugar donde quieras que aparezca el formulario y pega el código de nuestro template. Lo más importante es la lógica de envío al final:

### Código de Conexión (Javascript)
Copia esto dentro de las etiquetas `<script>` de tu `contact.html`:

```javascript
document.getElementById('lead-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const btn = e.target.querySelector('button');
    const originalText = btn.innerHTML;
    btn.innerText = 'Enviando...';
    btn.disabled = true;

    const leadData = {
        action: 'create_lead', 
        type: 'ALPA_NEW_LEAD',
        name: document.getElementById('name').value,
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value,
        project: document.getElementById('project').value,
        source: 'WEB_FORM_CPANEL'
    };

    // ENVÍO A TU SAAS UNIFICADO (Google Script)
    const SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbyl2PbBpYNQKQ-v1dBWROf2nGkynDG3jRgxIU_s1bokSY3kOhxUPtjmn25GCNdml8rZng/exec';

    fetch(SCRIPT_URL, {
        method: 'POST',
        redirect: 'follow',
        headers: {
            'Content-Type': 'text/plain;charset=utf-8',
        },
        body: JSON.stringify(leadData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success' || data.result === 'success') {
             // Ocultar formulario y mostrar mensaje de éxito
             document.getElementById('lead-form').style.display = 'none';
             if(document.getElementById('success-msg')) {
                 document.getElementById('success-msg').classList.remove('hidden');
                 document.getElementById('success-msg').style.display = 'block';
             } else {
                 alert("¡Solicitud enviada con éxito! ALPA construcciones te contactará.");
                 window.location.reload();
             }
        } else {
             alert('Hubo un problema: ' + data.message);
             btn.innerHTML = originalText;
             btn.disabled = false;
        }
    })
    .catch(err => {
        console.error("Error:", err);
        alert('Error de conexión. Intente nuevamente.');
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
});
```

## Paso 4: Guardar Cambios
Haz clic en el botón **"Save Changes"** en la esquina superior derecha del editor de CPanel.

---

## ¿Qué pasará ahora?
1. El cliente llena el formulario en tu web (`alpacons.cl`).
2. Los datos viajan a tu Google Sheet central.
3. Al abrir tu **Cotizador en Vercel**, el sistema detectará el nuevo registro y te avisará con la notificación naranja para que lo metas al **Embudo de Ventas**.

> [!TIP]
> Si quieres que usemos exactamente el diseño de tu web actual, puedes enviarme el código de tu `contact.html` y yo te lo devuelvo ya modificado y listo para pegar.
