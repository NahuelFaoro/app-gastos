# Validación v0.39.17

Antes de publicar:

1. `python -m compileall app main.py scripts tests`
2. `python scripts/audit_architecture.py`
3. `python -m unittest discover -s tests -v`
4. `python -m scripts.validate_project`
5. Prueba de compatibilidad desde v0.39.14 y una base temporal representativa de versiones anteriores.
6. Smoke gráfico en Windows mediante `start.bat`.
7. Revisión responsive según `docs/RESPONSIVE_UI.md`.

`start.bat` usa `.smoke_v0.39.17` y ejecuta `python -m scripts.check_app` una vez antes de abrir la base real.

## Estado de esta entrega

- **71 pruebas automáticas**: OK.
- `compileall`: OK.
- `scripts.validate_project`: OK.
- Compatibilidad de base representativa anterior → **v0.39.17** y apertura de una base representativa anterior: OK; no hay cambios de esquema financiero ni de IDs de datos existentes.
- El smoke gráfico quedó actualizado para instalaciones nuevas limpias y ahora crea sus propios datos genéricos dentro de una base temporal.

El entorno de construcción de esta conversación no dispone de PySide6 ni acceso de red para instalarlo, por lo que el smoke gráfico nativo no puede ejecutarse aquí. En Windows, `start.bat` lo ejecuta automáticamente antes de abrir datos reales y bloquea el arranque si encuentra un error de construcción.

## Regresiones cubiertas

- Drag & drop normal no crea filas: mueve el `parent_id`; si detecta una copia vacía homónima dejada por una build anterior en el destino, elimina únicamente esa copia vacía y conserva el ID/datos del nodo real.
- El árbol de Categorías retira inmediatamente los widgets viejos después de mover, evitando duplicados visuales fantasma.
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
- Expandir/contraer Categorías no llama al refresh completo ni reinicia el scrollbar.


## Hotfix v0.39.2

Se agregó una prueba estructural para garantizar que `FlowLayout.addWidget` acepte `stretch` y `alignment`, evitando incompatibilidades con componentes reutilizables.

## v0.39.17

No modifica el esquema de datos. El smoke de Herramientas deja de bloquear el arranque por geometrías provisionales y pasa a validar estructura de grilla después de activar realmente la página. La normalización de fuente Qt evita tamaños tipográficos indefinidos en Windows.
