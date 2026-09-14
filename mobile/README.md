# App Gastos Móvil 0.2.0

Versión independiente para Android e iPhone. Se publica como archivos estáticos HTTPS y se instala desde el navegador. No necesita la PC ni un servidor Python.

## Primer uso

Abrí el enlace con Internet y esperá que Ajustes indique disponibilidad sin conexión. La primera descarga incluye el OCR en español. Android: Instalar aplicación / Agregar a pantalla principal. Safari de iPhone: Compartir → Agregar a pantalla de inicio. Luego probá en modo avión.

Incluye movimientos, ingresos, transferencias, cuentas, categorías, viajes, extras, kilometraje, Flex y respaldo JSON. OCR de imágenes y PDF escaneados procesado en el dispositivo, con borrador para revisar antes de guardar. Límite: 20 MB y 10 páginas por PDF.

Los datos quedan en IndexedDB de este navegador/dispositivo. Exportá respaldos desde Ajustes: borrar datos del sitio o perder el teléfono puede borrar registros. No hay sincronización. Los respaldos son de esta versión móvil; permite importar el JSON generado por Desktop → Móvil → Exportar datos para el teléfono. Incluye cuotas y recurrentes con registro de vencimientos. No abre archivos SQLite directamente. Trabajo no acredita automáticamente importes en cuentas.

## Desarrollo

- `python scripts/vendor_mobile.py`: dependencias fijadas, licencias y hashes.
- `python scripts/package_mobile.py`: caché versionada y ZIP estático en dist.
- Publicar `dist/AppGastos_Movil_0.2.0_WEB.zip` en Cloudflare Pages. Nunca publicar la base del escritorio.
- Servidor de pruebas: `python -m http.server 8767 --bind 127.0.0.1 --directory mobile`.
- `node --test tests/mobile_model.test.mjs`: pruebas de modelo.
- `node scripts/check_mobile.cjs`: persistencia, viajes, tamaños y OCR PNG/PDF offline. Requiere Playwright/Chrome y fixtures sintéticos build/mobile-receipt.png y .pdf. BASE_URL permite probar un despliegue en perfil vacío.

Validado automáticamente en Chromium. Pendiente validar instalación, rendimiento y tickets reales en Android e iPhone físicos.

## Cobertura del traslado

Navegación Desktop, 82 iconos ilustrados, categorías jerárquicas, cuentas de distintos tipos, análisis, calendario, cuotas, recurrentes, presupuestos, comprobantes pendientes y herramientas agrupadas por día. Los datos de 0.1 se conservan.

La copia del escritorio conserva un snapshot de las tablas financieras para no descartar metadatos todavía sin editor móvil. No incorpora credenciales. Siguen pendientes equivalencia completa de tarifas personalizadas, importadores bancarios/Excel, gestión de ajustes, algunas vistas históricas y sincronización automática. No usar el JSON como sustituto de un respaldo SQLite.

### Actualización 0.3.0
Dashboard con la estructura de escritorio, gráficos locales, navegación de meses y semanas anteriores y selector visual de iconos. Los datos existentes se conservan. Para recibir la actualización, abrir con Internet, cerrar todas las ventanas de la app y volver a abrir. Ajustes muestra la versión instalada.
