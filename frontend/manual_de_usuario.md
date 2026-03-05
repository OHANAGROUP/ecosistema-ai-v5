# Manual de Usuario: ECOSISTEMA V5.0

Bienvenido al sistema de gestión unificada de ALPA SpA. Este manual le guiará a través de las funcionalidades clave, con ejemplos prácticos paso a paso para maximizar el uso de su nueva plataforma.

## 1. Acceso al Sistema

Para ingresar, utilice las credenciales asignadas según su rol. El sistema cuenta con roles diferenciados para proteger la información sensible.

### Credenciales de Acceso Local
| Rol | Usuario | Password | Acceso Principal |
| :--- | :--- | :--- | :--- |
| **Administrador** | `admin@alpaconstruccioneingenieria.cl` | `admin123` | Control Total, Todos los Módulos |
| **Ventas** | `ventas@alpaconstruccioneingenieria.cl` | `alpa2026` | Cotizador, Dashboard |
| **Compras** | `adquisiciones@alpaconstruccioneingenieria.cl` | `alpa2026` | Ordenes de Compra, Inventario |
| **Bodega** | `bodega@alpaconstruccioneingenieria.cl` | `alpa2026` | Inventario (Lectura/Escritura) |
| **Gerencia** | `gerencia@alpaconstruccioneingenieria.cl` | `alpa2026` | Visión Global (Solo Lectura en ciertos módulos) |

> [!IMPORTANT]
> Si utiliza la versión en la nube (Vercel), asegúrese de tener conexión a Internet. Para la versión local, verifique que el servicio `npm start` esté activo en el servidor.

---

## 2. Visión General del Dashboard

Al ingresar, aterrizará en el **Dashboard Central**. Este panel es su "Torre de Control".

**¿Qué información obtendré aquí?**
*   **KPIs Financieros (Ingresos vs Gastos):** Monitorice en tiempo real el flujo de caja.
*   **Saldo Disponible:** Dinero real disponible tras descontar gastos.
*   **IVA por Pagar:** Proyección automática del impuesto a pagar el día 20 del mes siguiente.
*   **Gráficos:** Evolución de flujo de caja y distribución de gastos por centro de costo.

---

## 3. Módulo de Contabilidad

Este es el corazón financiero. Registre aquí todo movimiento para mantener las cuentas claras.

### Ejemplo Virtual: Registrar una Factura de Compra
Escenario: Compramos materiales de construcción a "Sodimac" por $500.000 + IVA.

1.  Vaya a la pestaña **Transacciones**.
2.  Haga clic en **"Nueva Transacción"**.
3.  Complete el formulario con estos datos:
    *   **Tipo**: `Gasto`
    *   **Categoría**: `Materiales de Construcción`
    *   **Monto Neto**: `500000` (El sistema calcula automáticamente el IVA $95.000 y Total $595.000)
    *   **Tipo Doc**: `Factura`
    *   **RUT Emisor**: `76.123.456-7` (Sodimac)
    *   **Adjunto**: Puede subir una foto de la factura (se guarda en Drive).
4.  Presione **Guardar**.

### Informes Disponibles
*   **Libro de Compras (SII):** En la pestaña "Reportes", puede generar un PDF listo con todas las facturas recibidas del mes, totalizando el crédito fiscal IVA.
*   **Rendiciones de Gastos:** Informe detallado de gastos realizados por empleados sujetos a reembolso.

---

## 4. Módulo Cotizador (Generador de Ventas)

Cree propuestas profesionales en segundos. Olvide los Word/Excel desordenados.

### Ejemplo Virtual: Crear Cotización para un Edificio
Escenario: Cotizamos instalación eléctrica para "Inmobiliaria Horizonte".

1.  Navegue a **Cotizador** en el menú lateral.
2.  El sistema genera automáticamente el folio `ALPA-2026-001`.
3.  **Cliente**: Seleccione "Inmobiliaria Horizonte" del buscador (o créelo al vuelo).
4.  **Proyecto**: Ingrese "Habilitación Torre A".
5.  **Agregar Items**:
    *   *Item 1*: "Tableros Eléctricos", Cant: 2, Precio: 1.500.000
    *   *Item 2*: "Cableado Estructurado", Cant: 1 (Gl), Precio: 800.000
6.  Verifique el Total calculado automáticamente.
7.  **Acciones Finales**:
    *   Haga clic en **"Guardar en Drive"** para respaldar el JSON.
    *   Haga clic en **"Imprimir"** para generar el PDF oficial con firma y logo corporativo.

### Informes
*   **PDF de Cotización**: Documento formal con validez comercial.
*   **Historial**: Consulte cotizaciones pasadas y recupérelas con un clic para editar.

---

## 5. Módulo Ordenes de Compra (OC)

Formalice sus pedidos a proveedores para controlar costos *antes* de gastar.

### Ejemplo Virtual: Pedido de EPPs
Escenario: Necesitamos 10 Cascos y 10 Pares de Botas.

1.  Vaya a **Ordenes de Compra**.
2.  Folio automático `ALPA-OC-2026-001`.
3.  **Proveedor**: Seleccione "Seguridad Industrial Ltda".
4.  **Agregar Items**:
    *   "Casco Seguridad Blanco", 10 un, $5.000 c/u.
    *   "Botas de Seguridad T42", 10 par, $25.000 c/u.
5.  **Enviar**: Al guardar, el sistema le preguntará si desea **"Registrar Compromiso de Gasto"**. Si acepta, este monto aparecerá en Contabilidad como un gasto "proyectado" o pendiente, ayudando a no gastar el dinero dos veces.

---

## 6. Módulo de Inventario

Controle sus activos y materiales críticos.

### Ejemplo Virtual: Ingreso de Herramientas Nuevas
1.  En el módulo **Inventario**, presione **"Nuevo Item"**.
2.  **SKU**: Genere uno o use el del fabricante (ej: `TAL-BOSCH-01`).
3.  **Nombre**: "Taladro Percutor Bosch".
4.  **Stock Inicial**: 5.
5.  **Unidad**: "Unid".
6.  **Alerta**: El sistema marcará en **Rojo** si el stock baja de 5 unidades (Stock Crítico), avisándole visualmente en el panel superior.

### Reportes
*   **Valorizado de Inventario**: Vea cuánto dinero tiene invertido en bodega en tiempo real (visite la tarjeta "Valorizado" en el encabezado).

---

## 7. Gestión de Prospectos (CRM)

Administre las solicitudes que llegan desde su sitio web y conviértalas en oportunidades de negocio.

### Flujo de Venta (Embudo)
Cada prospecto pasa por estados definidos para medir la salud de su proceso comercial:
*   **Nuevo**: Solicitud recién ingresada desde la web.
*   **Contactado**: Ya se estableció el primer contacto con el cliente.
*   **Cotizado**: Se le ha enviado una propuesta formal.
*   **Ganado**: El cliente aceptó y se convertirá en Proyecto.
*   **Perdido**: El cliente declinó la propuesta.

### Gestión de Bitácora
En el detalle de cada prospecto, utilice el cuadro de texto para registrar cada interacción (llamadas, correos, visitas). Esto genera un historial compartido para que todo el equipo sepa en qué estado está la negociación.

### Asignación
Puede asignar prospectos a diferentes miembros del equipo (Ventas, Gerencia, etc.) para asegurar que ninguno quede sin atención.

---

## 8. Preguntas Frecuentes

**¿Qué pasa si se corta internet?**
El sistema guarda datos temporalmente en su navegador (Local Storage). Sin embargo, para sincronizar con Google Drive y que otros vean los cambios, necesita reconectar.

**¿Puedo borrar una factura emitida por error?**
Por seguridad y auditoría, las transacciones no se borran permanentemente. Debe usar la opción "Anular", lo que dejará un registro (trazabilidad) de quién y por qué se anuló la operación.

**¿Cómo exporto mis datos?**
En cada módulo (Cotizador, Ordenes), tiene un botón **"Exportar JSON"** para guardar una copia de seguridad completa en su computador.

---
*Generado por Asistente IA - ALPA Unificado v1.0*
