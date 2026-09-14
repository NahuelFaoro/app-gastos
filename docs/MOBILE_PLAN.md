# Desarrollo móvil Android e iPhone

La versión independiente está en mobile/: IndexedDB local, service worker y OCR Tesseract.js/PDF.js con modelos locales. No consulta Python. web/ conserva el cliente anterior dependiente de la PC.

Implementado en 0.1.0: movimientos, ingresos, transferencias con centavos enteros, cuentas, categorías, viajes, extras, kilometraje, Flex, respaldo JSON validado y OCR de imágenes/PDF con revisión previa. Interfaz adaptable e instalación PWA por HTTPS.

Pruebas: persistencia al recargar sin red, cambios de viajes, OCR PNG/PDF sin solicitudes externas y tamaños 320/390/768/1280 en Chromium.

Pendiente: pruebas físicas Android/Safari, tickets reales y rendimiento; importador de escritorio, cuotas y recurrentes; sincronización opcional con autenticación y resolución de conflictos. Hoy cada teléfono tiene datos independientes.

Ver mobile/README.md para instalación, límites, respaldos y publicación.

Publicado: https://app-gastos-movil.pages.dev/

El despliegue HTTPS también pasó recarga offline, persistencia, viajes y OCR PNG/PDF sin red. La caché normaliza respuestas redirigidas para compatibilidad con Cloudflare Pages.

## Móvil 0.2 / Desktop 0.39.31

Traslado del catálogo ilustrado y las secciones principales. Nuevos módulos desktop-ui, work-ui y planning. Exportación explícita desde Desktop, validada con el modelo móvil en pruebas sobre una base temporal. La importación reemplaza la copia móvil con confirmación; no envía datos a Internet.

No es todavía equivalencia integral: quedan importadores bancarios/Excel, reglas avanzadas de tarifas e interfaces de ajuste/histórico. La sincronización automática está diseñada en SYNC_DESIGN.md pero no está implementada ni activa.

## Móvil 0.3.0

Dashboard alineado con la estructura de escritorio: saldo disponible, resumen mensual con resultado y comparación anterior, cuentas, distribución de gastos por categoría principal (incluye descendientes y sin categoría), flujo de seis meses, actividad reciente y cuotas activas. Los gráficos incluyen leyenda e importes accesibles; no dependen de servicios externos.

Navegación por mes en Dashboard/Movimientos y por semana/mes en Viajes, Extras y Flex, con flechas, fecha y regreso a hoy. Catálogo visual de 82 iconos con búsqueda, paleta y vista previa. Campos de tarjeta condicionales y contraste del tema claro corregidos. Sin cambios de esquema ni sincronización automática.

Verificación: 12 pruebas de modelo/calendario/agregación; scripts check_mobile_desktop, check_mobile_refinements y check_mobile, incluyendo anchos 320/390/768/1280, edición, períodos entre años, persistencia y OCR PNG/PDF offline en Chromium. Queda pendiente validación física en Safari/iPhone y Android.

## Móvil 0.4.0

Movimientos incorpora búsqueda inmediata, filtros por fechas/cuenta/categoría jerárquica/importes, todo el historial, orden, totales filtrados, detalle plegable y "Usar como nuevo" sin copiar identidades ni referencias de cuotas/recurrentes. Renderiza 50 movimientos por tanda.

Viajes: campos personalizados con resumen funcional, casillas que guardan directamente, activar/ocultar/reordenar desde Personalizar. Flex: tarifas con vigencia e historial, fecha explícita de registro y resta de una unidad de lotes importados. Exportación Desktop conserva todas las tarifas. Categorías permite elegir un destino compatible y excluye sus descendientes; formularios móviles usan teclado numérico y tamaños de texto legibles sin zoom automático.

Sincronización: el usuario eligió cuentas individuales. Se prepara Supabase Auth; falta su cuenta/proyecto y la integración de clientes. cloud/supabase contiene el esquema preliminar y mobile/sync-merge.mjs la conciliación de cambios, probada aisladamente. NO hay conexión, credenciales ni envío automático de datos. Ver cloud/README.md.

Pruebas: 18 casos de modelo, filtros, tarifas y conciliación; exportación con SQLite temporal; navegadores de prueba verifican pantallas 320–1280, filtros, campos, Flex, persistencia y OCR offline. No sustituye pruebas en dispositivos físicos.
