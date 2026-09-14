# Desarrollo móvil para Android e iPhone

Recomendación: evolucionar web/ a una PWA independiente antes de empaquetarla para tiendas. La interfaz PySide6 no se convierte automáticamente en una app de teléfono.

## Situación actual

web/app.js consulta la API Python de la PC. Los movimientos y el OCR dependen del servidor local encendido. service-worker.js almacena recursos de interfaz, pero excluye /api/: eso no implementa edición offline ni sincronización. El HTTP de red local tampoco basta para una PWA instalable completa en teléfonos: el despliegue necesita un contexto seguro HTTPS. No publicar directamente mobile_server.py en Internet.

## Etapas propuestas (pendientes de implementación)

1. Reutilizar el diseño web y preparar navegación táctil para ambos sistemas. Separar el acceso a datos de las vistas.
2. Guardar datos en IndexedDB, agregar exportación/importación de respaldo y comprobar funcionamiento sin PC. Definir identificadores y migraciones antes de sincronizar.
3. Probar OCR de imágenes en el dispositivo con Tesseract.js y modelos locales. Medir tickets reales y teléfonos de gama baja. PDF requiere convertir páginas a imágenes por separado. No asumir la misma precisión ni velocidad que RapidOCR de escritorio.
4. Distribuir por HTTPS como PWA, con manifest, iconos y caché versionada. El alojamiento estático puede estar separado de los datos financieros, que permanecen locales.
5. Agregar sincronización opcional con autenticación, cifrado en tránsito, separación de usuarios, resolución de conflictos y revocación. Esto requiere backend; una cuota gratuita de hosting no garantiza costo cero a cualquier escala.
6. Evaluar Capacitor si se necesitan tiendas o integraciones nativas. Es open source; las cuentas y requisitos de distribución de cada tienda son independientes del framework.

## Fuentes oficiales consultadas

- Instalación PWA Android/iOS: https://web.dev/learn/pwa/installation
- Capacitor: https://capacitorjs.com/docs
- OCR en navegador: https://github.com/naptha/tesseract.js
- Distribución Apple: https://developer.apple.com/support/compare-memberships/

No se implementó todavía la versión independiente ni se publicó un servicio en este cambio.
