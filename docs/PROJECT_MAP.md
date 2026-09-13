# Mapa rápido del proyecto — v0.39.21

## Quiero cambiar…

| Necesidad | Archivo/capa principal |
|---|---|
| Sidebar / navegación / privacidad / escala | `app/main_window.py` |
| Paleta y API de tema | `app/theme.py` + `app/theme_tokens.py` |
| QSS, bordes, selección y tamaños visuales | `app/style_rules.py` |
| Layouts responsive reutilizables | `app/layouts.py` |
| Selector de fecha global | `app/date_picker.py` |
| Semana de Viajes/Extras/KM | `app/work_calendar.py` |
| Diálogos compartidos | `app/dialog_modules/` (fachada `app/dialogs.py`) |
| Cuentas / tarjetas | `app/repositories/accounts.py` + UI correspondiente |
| Categorías / jerarquía | `app/pages/categories.py` + `app/pages/category_tiles.py` + `app/repositories/categories.py` |
| Movimientos | `app/pages/transactions.py` + `app/repositories/transactions.py` |
| Análisis | `app/pages/statistics.py` + `app/repositories/analytics.py` |
| Cuotas | `app/pages/installments.py` + `app/repositories/installments.py` |
| Presupuestos / recurrentes | UI + `app/repositories/planning.py` |
| Importaciones / cola de revisión | `app/pages/imports.py` + `app/repositories/import_queue.py` |
| Historial mensual importado | `app/repositories/history.py` |
| Viajes / navegación semanal | `app/pages/viajes.py` |
| Formularios Viajes / Extras / odómetro | `app/pages/viajes_dialogs.py` |
| Campos y tarifas configurables | `app/pages/work_config.py` + `app/repositories/work_config.py` |
| Persistencia de Viajes/Extras/KM | `app/repositories/work_tracking.py` |
| Jornadas plegables Viajes | `app/pages/viajes_widgets.py` |
| Jornadas plegables Extras | `app/pages/extras_widgets.py` |
| Resumen mensual de trabajo | `app/pages/work_monthly.py` |
| Herramienta por zonas (Flex) | `app/pages/flex.py` + `app/repositories/flex.py` |
| Esquema SQLite / coordinación de migraciones | `app/schema.py` + `app/db.py` |
| Mercado Pago | `app/mercadopago.py` |
| Normalización de importes y cuotas | `app/amounts.py` |
| Validación HTTP y límite de vinculación | `app/mobile_server.py` + `app/mobile_security.py` |
| Versión | `app/constants.py` (`APP_VERSION`) |
| Auditor de arquitectura | `scripts/audit_architecture.py` |
| Smoke test gráfico | `scripts/check_app.py` |
| Validación automatizada | `scripts/validate_project.py` |
| Scripts Windows / builds | `scripts/windows/` |

## Flujos principales

**Guardar viaje**: `TripDialog` → `ViajesPage` → `Database` → `WorkTrackingMixin` → SQLite.

**Campos/tarifas de Viajes**: `WorkCustomizationDialog` → `Database` → `WorkConfigMixin`.

**KM reales**: `MileageWeekDialog` → `Database.set_work_day_mileage()` → `WorkTrackingMixin` → resumen semanal/mensual.

**Categorías multinivel**: `CategoriesPage` / selector → `Database` → `CategoryRepositoryMixin`; mover cambia `parent_id`, no IDs históricos.

**Análisis**: `AnalysisPage` → `Database` → `AnalyticsMixin` → drill-down UI.

**Responsividad global**: `app/layouts.py` + `docs/RESPONSIVE_UI.md`.

**Tema**: páginas/widgets usan object names/tokens → `style_rules.py`; no redefinir selectores localmente sin necesidad.

**Validación release**: `scripts/audit_architecture.py` → `compileall` → `unittest` → smoke gráfico de `start.bat` en Windows.
