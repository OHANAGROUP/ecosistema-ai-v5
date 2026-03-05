# Estructura de Costos y Límites (ECOSISTEMA V5.0)

Este documento detalla cuánto cuesta operar la plataforma y cuáles son los límites técnicos antes de necesitar escalar a planes pagados.

## 💰 Costo por Nuevo Usuario / Empresa
Gracias a la arquitectura **Multi-Tenant Serverless**, el costo marginal de añadir una nueva empresa hoy es:
**US$ 0.00 (Cero)**.

Debido a que los datos son mayoritariamente texto y números (proyectos, presupuestos, leads), el peso en disco de cada empresa es mínimo.

---

## 🏗️ Límites Técnicos (Plan Gratuito actual)

La plataforma corre sobre **Supabase** y **Vercel**. Estos son los límites del "Piso de Operación":

### 1. Supabase (Base de Datos y Auth)
| Recurso | Capacidad (Gratis) | Tiempo Estimado de Agotamiento |
| :--- | :--- | :--- |
| **Base de Datos** | 500 MB | ~500 empresas pequeñas (solo texto) |
| **Usuarios Activos** | 50,000 MAU | Suficiente para toda la vida del MVP |
| **Ancho de Banda** | 5 GB / mes | ~100 empresas operando diariamente |
| **Archivos (Storage)** | 1 GB | Limitado si suben muchos PDF/Fotos pesadas |

### 2. Vercel (Frontend)
| Recurso | Capacidad (Gratis) | Impacto |
| :--- | :--- | :--- |
| **Ancho de Banda** | 100 GB | Casi imposible de agotar con este tipo de App |
| **Requests** | Ilimitado | Sin restricciones de tráfico normal |

---

## 🧾 Dimensionamiento: Documentos Contables (Proyección)

Dado que las fotos serán mayoritariamente **comprobantes, facturas y boletas**, el comportamiento de uso cambia respecto a fotos de obra:

### 1. Estimación de Pesos por Tipo de Documento
| Tipo de Archivo | Peso Promedio | Capacidad en 1 GB (Gratis) |
| :--- | :--- | :--- |
| **Foto de Boleta (Cámara)** | ~400 KB | ~2,500 documentos |
| **PDF de Factura (Digital)** | ~150 KB | ~6,500 documentos |
| **Ticket de Estacionamiento** | ~200 KB | ~5,000 documentos |

### 2. Proyección de Escalamiento para el Negocio
Si una empresa promedio genera **30 transacciones con respaldo al mes**:
- **Consumo mensual**: ~10 MB por empresa.
- **Alcance**: Podrías tener **100 empresas** operando durante **un año entero** antes de llenar el primer GB gratuito.

---

## 🛠️ Recomendaciones para el Flujo Contable

Para manejar documentos legales de forma profesional y eficiente:

1. **Conversión a Blanco y Negro / Escala de Grises**: Las boletas no necesitan color. Convertirlas ahorra hasta un 70% de espacio sin perder validez legal.
2. **PDF vs Imagen**: Siempre que sea posible, prefiere guardar el PDF original (es más ligero y permite búsqueda de texto).
3. **Optimización en el Celular**: Implementar un "escáner" en la App que recorte los bordes y comprima la imagen antes de subirla.

> [!IMPORTANT]
> **Seguridad y Auditoría**: A diferencia de las fotos de redes sociales, los documentos contables en Supabase están protegidos por **RLS**. Solo el administrador de la empresa y el contador pueden ver el archivo mediante un link temporal (Signed URL).

---

## 📈 Ruta de Escalamiento (Gestión Documental)

Si el volumen de facturas explota o necesitas auditoría por 5+ años:
- **Plan Pro ($25 USD/mo)**: Sigue siendo la mejor opción, ya que te da **8 GB** de base (suficiente para ~50,000 boletas).
- **Control de Retención**: Podríamos programar que después de 2 años, los documentos se muevan a un "Cold Storage" mucho más barato (ej: AWS Glacier) si el cliente ya no los consulta a diario.
