# Validación v0.39.20

## Revisión visual v0.39.20

- Capturas Qt con datos genéricos verificadas en escritorio y ventana angosta; grilla probada a 1500, 768 y 430 px.
- Análisis alterna 420 → 1500 → 800 → 420 → 1500 px y comprueba el centro del porcentaje y el borde derecho del importe.
- Flex compara geometría con 0 y 123 envíos y subtotal de siete cifras; el contador conserva su posición.
- Extra recibe teclado real mediante QTest y persiste cantidad 27.
- Navegación, búsqueda, drop sobre iconos y drop hacia la raíz conservan IDs y movimientos.
- Las capturas locales se generan definiendo APPGASTOS_UI_CAPTURE=dist/ui-review al ejecutar tests/test_ui_folder_runtime.py; no se suben imágenes ni bases personales.
- Dos tests estructurales del árbol plegable se retiraron porque esa vista fue reemplazada; cuatro tests de comportamiento Qt cubren los nuevos contratos.

## Comprobaciones ejecutadas (2026-09-13)

- `python -m scripts.validate_project`: auditoría de arquitectura, compilación y **87 pruebas automáticas OK**.
- `python -m scripts.check_app`: **APP_GASTOS_SMOKE_OK** usando PySide6 nativo y una base temporal.
- Pruebas HTTP reales sobre loopback: vinculación, lectura y escritura autenticadas, límite de intentos, JSON/tamaños inválidos y rechazo previo a lectura sin autenticación.
- Regresiones monetarias: redondeo a centavos, entradas no finitas, cuotas que suman el total, proyección consistente y rechazo atómico de planes inválidos.
- Reapertura de base temporal: conserva valores históricos con más de dos decimales y cuota base existente. Esta entrega no cambia el esquema; no se abrió la base personal del usuario.

`start.bat` obtiene APP_VERSION y ejecuta el smoke una vez por versión; para esta entrega usa `.smoke_v0.39.20`.

El smoke verifica construcción, layouts y diálogos. No equivale a una revisión visual manual completa ni a una prueba del acceso desde un teléfono físico. No se verificaron llamadas reales a Mercado Pago ni OCR con comprobantes personales. Tampoco se generó un ejecutable de distribución.

## Antes de distribuir un ejecutable

1. Ejecutar `python -m scripts.validate_project` y `python -m scripts.check_app`.
2. Revisar visualmente según `docs/RESPONSIVE_UI.md`.
3. Probar sobre una copia representativa de una base anterior y conservar su backup.
4. Actualizar changelog y documentación; compilar con los scripts de Windows.

## Regresiones cubiertas

- Drag & drop normal no crea filas: mueve el `parent_id`; si detecta una copia vacía homónima dejada por una build anterior en el destino, elimina únicamente esa copia vacía y conserva el ID/datos del nodo real.
- La grilla de Categorías retira inmediatamente los widgets viejos después de mover, evitando duplicados visuales fantasma.
- Viajes no usa `FlowLayout` para las tres acciones superiores ni para el resumen semanal: guardar Personalizar reconstruye una grilla estable y uniforme.
- El chip de filtro de Viajes vive fuera de la fila del buscador y no puede superponerse.
- Tarifas de Nuevo viaje separan cantidad, tarifa unitaria/opción y total calculado.
- Análisis usa un ranking ancho (hasta 1500 px), una sola línea en escritorio y una columna fija de porcentaje.
- Dashboard centra “Este mes” respecto de toda la tarjeta; Cuentas vuelve a repartir el resumen en 4/2/1 columnas.
- Categorías soportan profundidad arbitraria, movimiento entre ramas y rutas completas sin perder `category_id`.
- Análisis agrega descendientes profundos y ordena hojas por importe/fecha.
- Tipos extendidos de campos de Viajes persisten texto largo, email/teléfono, número, dinero y listas de opciones.
- Las páginas con breakpoints antiguos usan el modo responsive compartido para monitores verticales.
- Tarjeta pagada/positiva se muestra como 0 y no infla patrimonio.
- Viajes conservan 1 fila = 1 viaje y Flex suma paradas.
- Odómetro real semanal/mensual y encadenado entre jornadas.
- Campos personalizados persisten y participan de búsqueda.
- Campos ocultos o eliminados visualmente no destruyen historial ya usado.
- Campos base pueden renombrarse, ocultarse y reordenarse manteniendo su tipo interno.
- Tarifas por unidad y opción calculan precio correctamente.
- Zonas pueden reordenarse; las zonas sin entregas pueden eliminarse y las usadas quedan protegidas para preservar historial.
- Migración v0.38 mantiene Viajes y elimina el antiguo sistema de ruteo.
- No se empaquetan seeds de viajes personales.
- OCR pesado permanece en un manifiesto separado, pero `start.bat` lo instala y valida por defecto.
- Reglas de estructura evitan imports circulares conocidos.
- Imports relativos se validan estáticamente para detectar módulos inexistentes antes del runtime.
- Nombres globales usados sin import/definición se detectan estáticamente con `symtable`, evitando `NameError` tardíos después de mover métodos entre módulos.
- El auditor rechaza SQL dentro de páginas, hardcodes semanales duplicados y selectores QSS redefinidos.

- Herramientas no depende de `FlowLayout` para sus dos accesos principales y fuerza una pasada con la geometría real del viewport.
- `FlowLayout` no descarta widgets por visibilidad heredada de un ancestro oculto.
- En v0.39.20 abrir carpetas sustituye el despliegue de ramas; los refresh estructurales conservan scroll y la navegación explícita lo reinicia.


## Hotfix v0.39.2

Se agregó una prueba estructural para garantizar que `FlowLayout.addWidget` acepte `stretch` y `alignment`, evitando incompatibilidades con componentes reutilizables.

## v0.39.17

No modifica el esquema de datos. El smoke de Herramientas deja de bloquear el arranque por geometrías provisionales y pasa a validar estructura de grilla después de activar realmente la página. La normalización de fuente Qt evita tamaños tipográficos indefinidos en Windows.
