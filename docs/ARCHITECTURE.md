# Arquitectura — App Gastos v0.39.27

Las reglas permanentes de calidad están en `docs/ENGINEERING_GUIDELINES.md` y el contrato visual en `docs/RESPONSIVE_UI.md`.

## Principio general

La UI presenta y coordina; los repositorios persisten y validan; las integraciones externas quedan aisladas; las reglas compartidas (tema, calendario, layouts) tienen una sola fuente de verdad. Una pantalla no debe conocer SQL ni duplicar reglas de dominio.

## Capas

1. **UI (`app/pages/`, `app/dialog_modules/`, `app/widgets.py`)**: PySide6, interacción y presentación. No contiene SQL.
2. **Fachadas compartidas (`app/dialogs.py`, `app/db.py`)**: mantienen APIs estables mientras delegan en módulos de dominio.
3. **Persistencia (`app/repositories/`, `app/schema.py`)**: consultas SQLite, validación, migraciones y agregados por dominio.
4. **Integraciones (`app/mercadopago.py`, escáner/importadores)**: servicios externos y parsing especializado, cargados de forma diferida cuando es posible.
5. **Infraestructura (`app/layouts.py`, `app/theme.py`, `app/theme_tokens.py`, `app/style_rules.py`, `app/date_picker.py`, `app/work_calendar.py`)**: reglas reutilizables de UI y calendario.

## Shell

- `main.py`: inicialización.
- `app/main_window.py`: shell, navegación, privacidad, tema y escala; la construcción está dividida en helpers para evitar un constructor monolítico.
- `app/constants.py`: defaults y `APP_VERSION`, única fuente de versión.
- `app/layouts.py`: `FlowLayout` y modos `wide / compact / narrow`.
- `app/date_picker.py`: selector de fecha compartido.

## Tema

- `app/theme.py`: API pública (`build_palette`, `build_stylesheet`).
- `app/theme_tokens.py`: resolución de paleta/tokens semánticos.
- `app/style_rules.py`: catálogo QSS declarativo.

El auditor rechaza selectores QSS redefinidos dentro del catálogo para evitar que una regla posterior anule silenciosamente otra.

## Persistencia

`app/db.py` conserva la clase `Database` para compatibilidad con todas las páginas, pero delega comportamiento por mixins/repositorios:

- `accounts.py`
- `analytics.py`
- `categories.py`
- `flex.py`
- `history.py`
- `import_queue.py`
- `installments.py`
- `planning.py`
- `transactions.py`
- `work_config.py`
- `work_tracking.py`

`app/schema.py` contiene el esquema base. `Database.initialize()` coordina migraciones idempotentes, seeds genéricos y caches; las vistas no ejecutan SQL.

## Diálogos

`app/dialogs.py` es una fachada muy pequeña que reexporta `app/dialog_modules/`. Los módulos están separados por dominio (`accounts`, `categories`, `transactions`, `planning`, `import_review`, `visual`) para que editar un formulario no obligue a modificar un archivo central enorme.

## Calendario de trabajo

`app/work_calendar.py` define la semana lunes-domingo, nombres de días, inicio/fin y etiquetas. Viajes, Extras, kilometraje y resúmenes consumen esta regla compartida; no deben usar `range(7)` ni `timedelta(days=6)` locales para definir la semana.

## Viajes configurable

`work_trips`: una fila = un viaje. `stop_count` = paradas. Los checks históricos (`bulky`, `rain`, `flex`, `own_client`) permanecen por compatibilidad, mientras presentación/orden/visibilidad salen de `work_field_definitions`. Campos nuevos se guardan en `work_trip_field_values`.

Tipos de UI: `check`, `text`, `long_text`, `number`, `money`, `email`, `phone`, `choice`. En espacio reducido los datos configurables se muestran como tarjetas/chips/bloques, nunca como columnas ilimitadas.

### Tarifas

- `work_rate_schemes`: tarifa por unidad o por opción.
- `work_rate_options`: opciones con precio.
- `work_trips.calculated_price`: snapshot del cálculo.

`Cobrado` sigue siendo independiente del cálculo de tarifa.

## Kilometraje

Sólo existe kilometraje real por odómetro (`work_day_mileage`). Inicio/final se encadenan con la última lectura válida y sábado/domingo participan de la misma semana y de los resúmenes.

## Categorías

`categories.parent_id` es recursivo, sin profundidad artificial. Consultas centrales construyen rutas y descendientes; mover un nodo conserva sus IDs y movimientos. `secondary_color` permite iconos bicolor y `IconBadge` centraliza su representación.

La gestión visual está en `app/pages/categories.py` y sus componentes en `app/pages/category_tiles.py`. Cada categoría principal ocupa un `CategoryPanel` con filas indentadas; varias ramas pueden desplegarse en el lugar sin navegación. Las columnas independientes evitan huecos por diferencias de altura. La búsqueda incluye ancestros y expande el contexto sin alterar el estado guardado de expansión. `CategoryPanel.apply_visibility` sólo alterna visibilidad: no reconstruye la página. El botón ↑ delega el movimiento al padre del contenedor actual; los drops delegan a `Database.move_category`. Movimientos y extracciones se encolan para finalizar el evento antes de retirar widgets.

## Datos y privacidad

La base vive en `%APPDATA%\AppGastos\app_gastos.db`, fuera de la carpeta de la versión. Instalar/extraer otra release no reemplaza datos. Tokens como Mercado Pago se guardan en `keyring`.

## Calidad automática

`scripts/audit_architecture.py` complementa tests funcionales y detecta patrones que históricamente generaron regresiones: SQL en páginas, reglas semanales duplicadas, QSS redefinido, imports relativos que apuntan fuera o a módulos inexistentes y crecimiento accidental de capas críticas.

## Importes y acceso móvil (v0.39.19)

`app/amounts.py` centraliza normalización decimal ROUND_HALF_UP a dos decimales y cálculo de última cuota. Los repositorios de movimientos/cuotas convierten a float sólo para conservar la API y el esquema existente. No se reescriben valores históricos al inicializar la base; otras áreas aún usan REAL/float.

`app/mobile_security.py` mantiene un límite global en memoria, protegido por lock, de cinco intentos de vinculación cada 60 segundos. Las solicitudes protegidas se autentican antes de leer su cuerpo. POST/PUT requieren un objeto JSON válido, Content-Length y Content-Type application/json. La vinculación acepta como máximo 1024 bytes; las demás solicitudes mantienen el límite de 20 MB. Cada socket tiene timeout de 15 segundos.

El token móvil y el código siguen en los ajustes de SQLite, a diferencia del token de Mercado Pago almacenado en keyring. El servidor sigue siendo HTTP local; estas defensas no lo convierten en un backend público. Ver `docs/TECHNICAL_REVIEW.md`.
