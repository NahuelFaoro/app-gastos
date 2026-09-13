# v0.39.18 — Hub de Herramientas compacto en monitores anchos

- Herramientas deja de repartir Flex y Viajes sobre todo el ancho del viewport: ambos accesos viven en un bloque central acotado.
- Las tarjetas pasan a expandirse dentro de columnas de ancho consistente, manteniendo una separación corta y equilibrada incluso en 2K/4K.
- El texto informativo queda alineado y limitado al mismo ancho visual del bloque de herramientas.
- Se conserva el apilado responsive en ventanas compactas/verticales y el relayout diferido del primer render.

# v0.39.17 — Smoke determinista y normalización de fuente Qt

- Se elimina del bloqueo de arranque la comprobación de superposición basada en `QRect`: Qt puede conservar geometrías provisionales iguales para hijos de páginas todavía no activas.
- El smoke navega primero a Herramientas y valida que Flex/Viajes ocupen celdas distintas del `QGridLayout`, una condición determinista e independiente del backend gráfico.
- Se agrega `app/qt_runtime.py` para garantizar un `pointSizeF()` positivo antes de construir widgets/iconos; corrige el warning `QFont::setPointSize: Point size <= 0 (-1)`.
- Se añade una regresión específica para impedir que el smoke vuelva a depender de `mapTo()/intersects()` sobre geometrías temporales.
- Validación local: **71 pruebas automáticas**, `compileall`, auditoría de arquitectura, `scripts.validate_project` y apertura de base compatible.

# v0.39.16 — Smoke test de Herramientas sin falso positivo

- Corrige la verificación preventiva de Herramientas: ya no compara geometrías locales antes de que Qt ejecute el primer layout real.
- El smoke test fuerza un ciclo real de `show/layout` con `WA_DontShowOnScreen`, por lo que valida la pantalla inicial sin mostrar ninguna ventana.
- La comprobación de superposición ahora mapea ambas tarjetas al mismo contenedor y verifica intersección real.
- Se conserva la grilla responsive de Herramientas y el despliegue local de Categorías introducidos en v0.39.15.

# v0.39.15 — Estabilidad del primer render y categorías sin refresh completo

- Herramientas reemplaza el `FlowLayout` del home por una grilla responsive explícita y relayout diferido con la geometría real del `QStackedWidget`.
- Las tarjetas de Herramientas quedan acotadas verticalmente y el smoke test comprueba que no se superpongan en el primer render.
- `FlowLayout` deja de usar `isVisible()` para filtrar widgets durante el layout: sólo omite elementos ocultados explícitamente con `isHidden()`, evitando perder geometría cuando el ancestro todavía no fue mostrado.
- Categorías materializa cada subárbol una vez por refresh estructural; desplegar/contraer sólo alterna visibilidad de filas ya existentes.
- Los cambios estructurales en Categorías conservan el scroll y bloquean repaints durante la reconstrucción para evitar saltos/flicker.
- Búsqueda y cambio Gastos/Ingresos reinician el scroll al inicio de forma intencional.
- Validación: **69 pruebas automáticas**, `compileall`, auditoría de arquitectura y `scripts.validate_project` en verde.

# v0.39.14 — Hotfix de dependencias del refactor y auditoría de nombres globales

- Se corrige el `NameError: add_months is not defined` al registrar compras en cuotas desde el smoke test de Windows.
- Se restauran imports auxiliares que habían quedado implícitos al extraer dominios desde el antiguo `db.py`: `add_months`, `month_bounds`, `monthrange`, `CATEGORY_COLORS`, `json`, `sqlite3`, `date` y `Any` donde corresponde.
- Se corrigen dos referencias residuales `_week_start(...)` del servidor móvil para usar la fuente compartida `week_start(...)`.
- El auditor de arquitectura ahora usa `symtable` para detectar nombres globales utilizados sin importarlos/definirlos; este tipo de error no lo detecta `compileall`.
- Se agrega una suite runtime específica que ejecuta compra en cuotas, compromisos mensuales, calendario diario, presupuestos, staging de importaciones, historial y análisis.
- Compatibilidad sobre base existente validada sin cambios de esquema ni IDs.
- Validación: **65 pruebas automáticas**, `compileall`, auditoría estructural y `scripts.validate_project` en verde.

# v0.39.13 — Refactor de arquitectura, aislamiento de dominios y guardas anti-regresión

- Persistencia separada por dominios en `app/repositories/`; `app/db.py` queda como fachada/coordinador y baja a ~500 líneas.
- El esquema SQLite base se mueve a `app/schema.py`; migraciones y seeds quedan coordinados explícitamente e idempotentes.
- Los diálogos monolíticos se dividen en `app/dialog_modules/` detrás de la fachada estable `app/dialogs.py`.
- La semana de trabajo se centraliza en `app/work_calendar.py`: una sola regla lunes-domingo para Viajes, Extras, kilometraje y resúmenes.
- Tema dividido en `theme.py`, `theme_tokens.py` y `style_rules.py`; se eliminan redefiniciones QSS que podían hacer impredecible una corrección visual.
- Acciones repetidas de configuración pasan a componentes compartidos para conservar geometría, colores y estados en Campos, Tarifas y Zonas.
- Constructores y coordinadores grandes se subdividen en helpers de responsabilidad única, reduciendo acoplamiento entre bloques de UI.
- Dependencias pesadas/opcionales se importan de forma diferida en flujos que no las necesitan durante el arranque normal.
- `APP_VERSION` se convierte en fuente única de versión para la app, lanzador y builds.
- Nuevo auditor estructural: bloquea SQL en páginas, calendario duplicado, QSS redefinido, imports relativos inválidos, ciclos internos de imports y regresiones de modularidad.
- Se corrige durante el refactor un import/indentación residual del módulo de cuentas antes de publicar la build.
- Validación: 62 pruebas automáticas, `compileall`, auditoría de arquitectura y `scripts.validate_project` en verde.

# v0.39.12 — Hotfix visual de Análisis, KM y acciones de configuración

- Análisis deja de conservar el layout narrow construido con el tamaño provisional de Qt durante el arranque; al mostrarse se reconstruye con el viewport real.
- El porcentaje queda en el eje geométrico central mediante mitades laterales simétricas que ignoran `sizeHint`.
- `KM reales` muestra el valor principal en una sola línea, evitando cortes como `220.0` / `km`.
- Personalizar Viajes y Tarifas reemplazan los botones circulares de v0.39.11 por rectángulos compactos de 40×34 px con radio de 10 px.
- El tacho destructivo usa fondo/borde rojo pastel e icono `#FF7586`; el estado deshabilitado mantiene un rojo atenuado visible.
- Configurar zonas adopta el mismo lenguaje visual sin perder el botón de eliminación de zonas.
- Suite ampliada a 55 pruebas automáticas.

# v0.39.11 — Acciones circulares y editor de zonas corregido

- Personalizar Viajes: los controles de subir/bajar y eliminar pasan a botones realmente circulares mediante máscara elíptica, evitando que reglas globales del tema vuelvan a cuadrarlos.
- El ícono de tacho se renderiza explícitamente con el rojo pastel `#FF7586`, el mismo tono semántico usado para gastos en modo oscuro; el fondo queda neutral y el rojo aparece como acento.
- Configurar zonas: identidad compacta en tres columnas, bloque de vigencia más claro y mayor altura útil para el listado.
- Cada zona usa switch `Activa`, controles de orden verticales y un botón circular de eliminar con el mismo lenguaje visual de Personalizar.
- Se permite eliminar zonas nuevas o existentes sin entregas. Si una zona tiene entregas históricas, la eliminación se bloquea y se indica desactivarla para no perder historial.
- La barra inferior reúne Agregar zona / Cancelar / Guardar en una sola línea para evitar que la lista quede recortada.
- Suite ampliada a 54 pruebas automáticas.

# v0.39.10 — Corrección de arranque y OCR integrado

- Se corrige el smoke test de Viajes/Extras para validar 7 jornadas (lunes a domingo) en lugar del contrato viejo de 5 días.
- `start.bat` vuelve a instalar y comprobar automáticamente RapidOCR, ONNX Runtime y PyMuPDF junto con las dependencias normales.
- El escáner ya no deriva al instalador OCR separado: si falta el motor, indica volver a ejecutar `start.bat`.
- Se agrega una prueba de regresión para impedir que el verificador vuelva a quedar desfasado respecto de la semana de 7 días.

# v0.39.9 — Jerarquía visual, fines de semana y pulido de herramientas

- Análisis: porcentaje centrado geométricamente en las tarjetas del ranking.
- Categorías: árbol plegable por rama, conservando drag & drop, edición y búsqueda con autoexpansión.
- Viajes/Kilometraje: semana completa de lunes a domingo; sábado y domingo participan en carga, tarjetas, filtros y resúmenes.
- Personalizar Viajes: flechas de orden en vertical, botones redondeados y rojo destructivo pastel alineado con el tema.
- Tarifas: superficies neutrales en lugar del tinte verdoso heredado.
- Zonas: diálogo de edición reorganizado con campos etiquetados y filas de tarifa más claras.
- Selector de categorías: secciones plegables por categoría principal y tiles compactos para reducir desplazamiento.
- Validación: 51 pruebas automáticas.

# v0.39.8 — Correcciones visuales sobre capturas reales

- Viajes: el resumen semanal usa una grilla estable; guardar Personalizar ya no puede estirar una métrica ni reordenar la cabecera.
- Viajes: el filtro activo ocupa su propia fila y no se superpone con el buscador.
- Nuevo viaje: la tarifa se presenta como Cantidad / Tarifa / Total calculado, sin números sueltos ni controles ambiguos.
- Dashboard: “Este mes” queda centrado respecto de toda la tarjeta, independientemente de la fecha mostrada a la derecha.
- Análisis: ranking más largo en escritorio, filas de una sola línea y porcentaje sobre un eje fijo.
- Cuentas: se recupera el espaciado amplio del resumen en escritorio, con reflow 4/2/1 columnas según ancho.
- Categorías: el drag & drop queda protegido contra emisiones repetidas y, si una versión anterior dejó una copia vacía con el mismo nombre dentro del destino, repetir el arrastre la retira de forma segura antes de mover el nodo real.

# v0.39.7 — Rehecho de la última tanda con corrección del drag & drop

- Categorías: mover por arrastre ahora hace un único `UPDATE parent_id`; no crea ni copia categorías.
- Categorías: reconstrucción visual sincrónica después de mover para evitar filas fantasma/duplicadas.
- Categorías: duplicar sigue creando un nodo independiente sin movimientos ni descendientes.
- Selector de categoría padre: navegador jerárquico visual en lugar del combo de rutas largas.
- Análisis: tarjetas realmente más anchas y porcentaje sobre un eje fijo.
- Viajes: tres acciones superiores en un layout no envolvente, buscador ancho, métricas de altura uniforme y resumen diario centrado sin clipping de chips.
- Zonas y Dashboard: sólo los centrados puntuales pedidos.

# v0.39.4 — Hotfix de stylesheet

- Corrige el `NameError: danger is not defined` que bloqueaba el smoke test al construir el stylesheet.
- Los botones destructivos reutilizan el color semántico `negative`, ya definido por el tema.
- Agrega una prueba estática que valida que el f-string principal de `build_stylesheet()` no utilice variables inexistentes.
- La suite completa pasa 34 pruebas automáticas, `compileall` y `validate_project`.

# v0.39.3 — Categorías multinivel, drill-down de Análisis y personalización funcional

- La release parte explícitamente de **v0.39.2**; no incorpora el rediseño descartado de v0.40.0.
- Categorías con profundidad arbitraria, movimiento entre ramas y rutas completas sin romper movimientos históricos.
- Iconos de categoría opcionalmente bicolor 50/50 mediante `secondary_color` y `IconBadge` compartido.
- Nuevo movimiento puede crear una categoría/subcategoría desde el propio selector y continuar la carga.
- Análisis conserva la navegación dentro de la pantalla: desciende por subcategorías y en hojas muestra movimientos ordenables por mayor/menor importe o más/menos recientes.
- Ranking de Análisis más compacto, centrado y con porcentaje en la zona media de cada tarjeta.
- Viajes centra `Kilometraje`, `Nuevo viaje` y `Personalizar` encima de la navegación semanal; búsqueda acotada y responsive.
- Personalizar Viajes incorpora controles reales para Sí/No, texto corto/largo, número, importe, email, teléfono y listas de opciones.
- `Activo`/`Mostrar en resumen` usan switches; reordenamiento y eliminación usan controles visuales dedicados.
- Tarifas de Viajes usan inputs separados para opción y precio, eliminando formatos manuales tipo `Zona = 6990`.
- Breakpoints aislados de Movimientos, Calendario, Ajustes, Recurrentes, Móvil, Cuotas e Importaciones se alinean con `responsive_mode`.
- Se amplía la cobertura de rutas completas/bicolor en Movimientos, Recurrentes, Dashboard, Importaciones y Cuotas.
- Suite de regresión ampliada a 33 pruebas automáticas.

# v0.39.2 — Hotfix de verificación responsive

- Corrige el `NameError` de `Qt.AlignmentFlag` en Viajes importando `Qt` explícitamente desde `PySide6.QtCore`.
- Agrega una prueba estática que falla si cualquier módulo usa `Qt.*` sin importar `Qt`.
- Corrige la firma de `FlowLayout.addWidget` para que acepte `stretch` y `alignment` como los layouts estándar de Qt.
- Evita el crash del formulario Viajes/Tarifas durante el smoke test de v0.39.0.
- El smoke test ahora imprime el traceback completo si encuentra un error, en vez de ocultarlo detrás del mensaje genérico.
- Agrega una prueba estructural específica para evitar que esta incompatibilidad vuelva a introducirse.

# v0.39.0 — Responsive global, herramientas configurables y Análisis renovado

- Se formaliza un contrato responsive global (`wide`, `compact`, `narrow`) para escritorio horizontal, vertical y ventanas angostas.
- Viajes transforma filas en tarjetas compactas cuando falta ancho; campos configurables nunca generan columnas ilimitadas.
- Nuevo **Personalizar Viajes**: renombrar/ocultar checks base y agregar campos `check`, texto, número o importe.
- Nuevo sistema de tarifas de Viajes: por unidad (`20 km × tarifa`) o por opción (`Zona 2 = precio`), con total guardado por viaje y acción para copiarlo a Cobrado.
- Flex/Zonas permite renombrar herramienta/unidad, editar/reordenar zonas y conserva historial de tarifas.
- Métricas compartidas pasan a ancho natural, wrap y alineación centrada para evitar grandes superficies vacías.
- Análisis se rediseña inspirado en Gestor de gastos: Gastos/Ingresos, período, barra apilada, total central y ranking de categorías con porcentaje/importe.
- Corrección de patrimonio: una tarjeta pagada con saldo técnico positivo se muestra en 0 y no se suma como activo.
- Nuevas instalaciones eliminan seeds personales: categorías y tarifas iniciales son genéricas y Viajes empieza vacío.
- OCR se separa de las dependencias base. `build_share.bat` genera una build LITE sin RapidOCR/ONNX/PyMuPDF para reducir fuertemente el ZIP compartible.
- Se agregan pruebas para patrimonio, campos dinámicos, tarifas configurables y orden de zonas.

# v0.38.0 — Kilometraje únicamente por odómetro real

- Se elimina por completo la funcionalidad activa de kilometraje estimado por direcciones/API.
- Viajes ya no muestra ni guarda kilómetros calculados por recorrido.
- Se retiran los botones de cálculo, columnas de KM estimados, configuración/API key de Ajustes y servicios de ruteo.
- El resumen semanal y mensual conserva exclusivamente **KM reales**, calculados con odómetro inicial/final.
- La migración v0.38 limpia de bases existentes las columnas y el cache que pertenecían a la integración retirada.
- El encadenado de odómetro entre jornadas se mantiene sin cambios.
- Tests, smoke test, arquitectura, mapa del proyecto y documentación se actualizan para reflejar una única fuente de kilometraje.

# v0.37.3 — Hotfix de import relativo y validación estructural

- Corrige `app/date_picker.py`: al moverse a la raíz del paquete `app`, su import correcto es `from .constants import MONTHS`; el import anterior intentaba subir por encima del paquete y bloqueaba el arranque.
- `scripts.check_app` importa ahora el selector compartido directamente desde `app.date_picker`, evitando depender del wrapper de compatibilidad de `app.pages`.
- Se agregan pruebas estáticas que rechazan imports relativos que intenten salir del paquete `app` y dependencias de `app.dialogs` hacia `app.pages`.
- La validación completa queda en 17 pruebas automáticas más compilación sintáctica.

# v0.37.2 — Hotfix de arranque y selector de fecha compartido

- Corrige el `ImportError` por dependencia circular introducido al globalizar el nuevo calendario en v0.37.1.
- El selector de fecha reutilizable se mueve de `app/pages/` a `app/date_picker.py`, una capa común que puede ser usada por diálogos y páginas sin ciclos de importación.
- Se mantiene un módulo de compatibilidad mínimo en `app/pages/work_date_picker.py` para no romper referencias antiguas.
- El calendario nuevo sigue siendo el selector estándar en Movimientos, Estadísticas, Importaciones, Flex y Viajes.

# v0.37.1 — Ajuste visual general, calendario global y rutas más confiables

- El nuevo selector de fecha se aplica también a Movimientos, Estadísticas, Importaciones, Flex y demás formularios que antes abrían el calendario nativo chico/inusable.
- El resumen mensual de Viajes elimina el texto grande `paradas Flex` y pasa a mostrar las semanas como tarjetas con chips, alineadas visualmente con las jornadas diarias.
- La selección de filas de Viajes deja de usar el resaltado nativo con líneas azules: ahora se marca con un fondo sutil y un segundo clic la des-selecciona.
- OpenRouteService ahora prioriza resultados de Argentina y valida recorridos absurdos antes de guardarlos, evitando estimaciones incoherentes de cientos de kilómetros por una dirección mal resuelta.

- Rediseño del selector `Ir a`: diálogo grande, centrado, con navegación explícita de mes/año y sin cambiar la fecha hasta confirmar.
- Selección de filas de Viajes más clara: sin foco azul nativo, selección sutil y segundo clic para deseleccionar.
- Extras adopta la misma estética de jornadas plegables que Viajes.
- Nuevo botón **Este mes** con resumen mensual y desglose semanal de Viajes, Paradas, Bulto, Lluvia, Flex, Cliente propio, km reales, km estimados y Cobrado.
- El resumen mensual recorta semanas que cruzan de mes para no duplicar días.
- Ajustes incorpora guía explícita para obtener la **Basic Key** de OpenRouteService y acceso directo al login/panel.
- `Presupuestos` se elimina de la navegación y se retira su página PySide6; el esquema legado queda sólo por compatibilidad de bases antiguas.
- Se separan nuevos componentes en `work_date_picker.py`, `extras_widgets.py` y `work_monthly.py` para evitar agrandar archivos monolíticos.
- Se corrige nuevamente la aplicación en caliente del zoom de UI desde Ajustes.

# v0.36.0 — Resumen compacto, Flex por paradas y jornadas visuales

- El contador **Flex** suma las paradas de cada viaje Flex: 1 viaje con 5 destinos = 5 Flex.
- **Viajes** mantiene las paradas como información secundaria destacada dentro de la misma métrica.
- Las métricas semanales usan ancho natural y un `FlowLayout`: Bulto/Lluvia/Flex ya no se estiran innecesariamente y sólo saltan de fila cuando falta ancho real.
- Se reemplaza el árbol visual de jornadas por **tarjetas de día plegables**. Cerradas muestran día, fecha, viajes, paradas y kilómetros; las columnas aparecen únicamente al desplegar.
- Los encabezados diarios dejan de depender del ancho de la columna Cliente, eliminando textos truncados como `3 parad...`.
- En **Kilometraje real**, el KM final de una jornada se propone automáticamente como KM inicial de la siguiente, sin sobrescribir correcciones manuales.
- El encadenado de odómetro también funciona entre semanas (por ejemplo viernes → lunes) buscando el último cierre previo disponible.
- El selector **Herramientas** usa tarjetas compactas con ancho limitado en lugar de superficies que ocupan toda la pantalla.
- La raíz del proyecto se simplifica: documentación en `docs/`, diagnóstico/validación en `scripts/` y utilidades Windows en `scripts/windows/`.
- Nuevo `app/layouts.py` para infraestructura responsive reutilizable.
- Mercado Libre Flex se extrae de `tools.py` a `app/pages/flex.py`; el hub de Herramientas queda dedicado sólo a navegación.
- Smoke test y documentación actualizados a la nueva estructura.

# v0.35.0 — Kilometraje real + estimado y refuerzo de arquitectura

- Rediseño de **Herramientas**: accesos compactos y clickeables, sin tarjetas gigantes ni botones desperdiciando altura.
- **Paradas** deja de ser un filtro/tarjeta independiente y pasa a mostrarse dentro de la métrica Viajes.
- Nuevo registro de **kilómetros reales** por odómetro inicial/final de lunes a viernes.
- Resumen semanal y encabezados diarios muestran kilómetros reales cuando la jornada está cerrada.
- Integración con **OpenRouteService** para kilómetros estimados a partir de Origen + Paradas, respetando el orden cargado.
- Cálculo individual desde Nuevo/Editar viaje y cálculo en lote de viajes faltantes de la semana.
- Geocodificación cacheada en SQLite para reducir llamadas externas y acelerar recorridos repetidos.
- API key de OpenRouteService almacenada mediante `keyring`; se configura desde Ajustes.
- Separación explícita entre km reales (`work_day_mileage`) y km estimados (`work_trips.estimated_km`).
- Nuevo paquete `app/services/` para aislar integraciones externas de la UI.
- Documentación nueva: `docs/ENGINEERING_GUIDELINES.md`, `docs/PROJECT_MAP.md`, `docs/WORK_TRACKING.md`.
- Suite `unittest` para Viajes, odómetro, cache y cliente de ruteo.
- Smoke test de Windows actualizado a v0.35.0.

# v0.34.0 — Paradas, cliente propio y UI responsiva

- **Viajes** vuelve al criterio `1 fila = 1 viaje`. La multiplicidad ahora se expresa como **Paradas** (direcciones del recorrido), no como “cantidad de viajes” dentro de la fila.
- Nuevo contador **Paradas** en el resumen semanal, con filtro rápido para inspeccionar viajes de múltiples paradas.
- Nueva etiqueta estructurada **Cliente propio**, visible en el formulario, en la tabla y en el resumen semanal.
- Migración automática: los datos históricos convierten el viejo `trip_count` en `stop_count` cuando corresponde, preservando la información previa.
- La tabla diaria de viajes ahora muestra columnas **Paradas** y **Propio**, con mejor alineación visual para Bulto/Lluvia/Flex.
- Se rediseñaron los diálogos de **Nuevo viaje** y **Nuevo extra**: centrado automático, scroll interno, mejor uso del espacio y apertura adaptada al tamaño de pantalla.
- El selector de fecha pasa a un calendario grande personalizado, evitando los incrementos accidentales de año/día al hacer clic sobre el campo.
- El zoom/escala de interfaz ahora se aplica **en el momento**, sin cerrar y reabrir App Gastos.
- Enter en los formularios guarda el cambio en lugar de cerrar silenciosamente sin aplicar modificaciones.

# v0.33.1 — Cantidad real de viajes por entrada

- Cada registro de **Viajes** incorpora `Cantidad de viajes` (1–99).
- Una sola fila puede representar varios recorridos del mismo cliente. Ejemplo: un mismo cliente, Flex, cantidad 5.
- El contador semanal **Viajes** suma la cantidad real de recorridos y ya no simplemente la cantidad de filas.
- Los contadores clickeables **Bulto**, **Lluvia** y **Flex** también suman la cantidad real de viajes representados por cada entrada.
- La lista diaria agrega una columna **Viajes** para que se vea inmediatamente cuándo una entrada representa 2, 5, etc. recorridos.
- Los desplegables de Lunes a Viernes muestran el total real de viajes del día, incluso cuando están agrupados en menos registros.
- Se distingue en el resumen entre **viajes** y **registros** para evitar confusión.
- Migración automática desde v0.33.0: textos inequívocos como `5 Flex` o `Flex 5` se convierten una sola vez en `Cantidad = 5 + Flex`, dejando Detalles limpio.
- La migración es idempotente y no vuelve a modificar registros editados por el usuario.
- Se actualizaron comentarios, docstrings, documentación de arquitectura y smoke tests.

# v0.33.0 — Herramientas, Viajes por día y Extras

- **Viajes** deja de ocupar una entrada propia del menú lateral y pasa a vivir dentro de **Herramientas** junto a **Flex**.
- Nueva pantalla inicial de **Herramientas** para elegir entre `Mercado Libre Flex` y `Viajes`.
- En Viajes, **Flex** pasa a ser una condición estructurada igual que **Bulto** y **Lluvia**.
- Migración automática de los viajes históricos que tenían `FLEX` en Detalles o `(flex)` en el cliente.
- Nuevo contador semanal **Flex** y filtros clickeables para Bulto, Lluvia y Flex.
- La lista semanal se reorganiza por **Lunes, Martes, Miércoles, Jueves y Viernes**, cada día como desplegable.
- **Servicios** se reemplaza por **Extras** para registrar trabajo con aplicaciones, horas e ingresos.
- Refactor del módulo Viajes en archivos separados con documentación y smoke test.

# v0.32.0 — Gestión semanal de Viajes

- Nueva gestión semanal de viajes con histórico persistente.
- Alta, edición y eliminación con cliente, origen, múltiples destinos, fecha, bulto, lluvia, detalles y cobrado.
- Migración inicial de los 83 viajes + 1 servicio del Excel de planificación.
