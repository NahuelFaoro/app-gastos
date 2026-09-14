# Desarrollo móvil Android e iPhone

La versión independiente está en mobile/: IndexedDB local, service worker y OCR Tesseract.js/PDF.js con modelos locales. No consulta Python. web/ conserva el cliente anterior dependiente de la PC.

Implementado en 0.1.0: movimientos, ingresos, transferencias con centavos enteros, cuentas, categorías, viajes, extras, kilometraje, Flex, respaldo JSON validado y OCR de imágenes/PDF con revisión previa. Interfaz adaptable e instalación PWA por HTTPS.

Pruebas: persistencia al recargar sin red, cambios de viajes, OCR PNG/PDF sin solicitudes externas y tamaños 320/390/768/1280 en Chromium.

Pendiente: pruebas físicas Android/Safari, tickets reales y rendimiento; importador de escritorio, cuotas y recurrentes; sincronización opcional con autenticación y resolución de conflictos. Hoy cada teléfono tiene datos independientes.

Ver mobile/README.md para instalación, límites, respaldos y publicación.

Publicado: https://app-gastos-movil.pages.dev/

El despliegue HTTPS también pasó recarga offline, persistencia, viajes y OCR PNG/PDF sin red. La caché normaliza respuestas redirigidas para compatibilidad con Cloudflare Pages.
