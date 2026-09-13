# Roadmap de App Gastos

## Próximos pasos de Viajes

- Métricas derivadas del odómetro real: ingresos por km, costo estimado de combustible y km promedio por jornada.

## Arquitectura / mantenibilidad

- Mantener las reglas de `docs/ENGINEERING_GUIDELINES.md` en cada release.
- Continuar extrayendo integraciones y lógica de dominio fuera de páginas PySide6.
- Reducir gradualmente responsabilidades de `app/db.py` mediante repositorios por dominio cuando se hagan cambios en esas áreas, evitando un refactor masivo de alto riesgo.
- Agregar tests de regresión junto con cada migración relevante.

## Sincronización fuera de casa

- Backend HTTPS desplegable.
- Base remota/sincronizable con migración segura desde SQLite.
- Autenticación por usuario/dispositivo.
- Resolución de conflictos y cola offline.

## Producto Windows

- Icono propio e instalador.
- Auto-update opcional.
- Build/release automatizado.

## Automatización financiera

- Mejorar conciliación de Mercado Pago.
- Conciliar automáticamente tickets con débitos.
- Movimientos divididos entre múltiples categorías.
