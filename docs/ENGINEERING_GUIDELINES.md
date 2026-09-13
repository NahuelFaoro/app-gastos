# Reglas de ingeniería de App Gastos

Estas reglas son permanentes para futuras actualizaciones.

## Objetivos

- Código fácil de leer meses después sin recordar cómo se desarrolló.
- Cambios localizados: modificar Viajes no debe romper Movimientos, por ejemplo.
- Datos compatibles entre versiones.
- UI responsiva y consistente.
- Evitar deuda técnica por velocidad de implementación.

## Python

- Type hints en interfaces públicas y lógica no trivial.
- Docstrings para clases/funciones cuya responsabilidad no sea obvia por el nombre.
- Comentarios explican **por qué**, no repiten lo que hace una línea.
- Funciones cortas y con una responsabilidad concreta.
- Evitar duplicación; extraer helpers cuando una regla aparece en más de un lugar.
- Validar datos en el límite de la capa que los recibe.
- No capturar `Exception` salvo en bordes de UI/integraciones donde el error deba convertirse en mensaje al usuario.

## UI / PySide6

- La responsividad es un requisito permanente: toda mejora debe funcionar en `wide`, `compact` y `narrow`, incluyendo monitores verticales.
- Usar los breakpoints compartidos de `app/layouts.py`; no inventar umbrales locales salvo una justificación documentada.
- Datos configurables nunca deben convertirse en columnas ilimitadas: en espacio reducido usar tarjetas, chips o bloques verticales.
- Métricas de contenido corto deben conservar ancho natural y alineación centrada; evitar superficies enormes sin información.
- Páginas coordinan UI; no contienen SQL ni HTTP.
- Diálogos reutilizables viven fuera de la página principal cuando crecen.
- Operaciones de red lentas se ejecutan fuera del hilo gráfico.
- Ventanas y diálogos deben funcionar en resoluciones/escala diferentes.
- Evitar medidas fijas innecesarias; preferir layouts y límites razonables.
- Enter debe tener un comportamiento explícito y seguro.

## Organización del proyecto

- La raíz debe conservar sólo archivos necesarios para ejecutar/identificar el proyecto.
- Documentación técnica en `docs/`; utilidades de desarrollo en `scripts/`; pruebas en `tests/`.
- Una página que acumule dominios diferentes debe dividirse antes de convertirse en un archivo monolítico.
- Componentes genéricos (layouts/widgets/servicios) deben vivir fuera de páginas concretas cuando puedan reutilizarse.
- `docs/PROJECT_MAP.md` debe mantenerse alineado con cualquier movimiento importante de archivos.

## SQLite

- Toda tabla/campo nuevo debe tener migración transparente.
- Migraciones idempotentes.
- Foreign keys activas.
- Datos financieros, Viajes y Extras pueden compartir archivo SQLite, pero no tablas conceptualmente mezcladas.
- Backup/restauración debe seguir incluyendo todo dato persistente.

## Integraciones externas

- Cliente HTTP separado de la UI.
- Endpoints y autenticación encapsulados.
- Timeouts obligatorios.
- Errores externos se convierten en excepciones/mensajes de dominio comprensibles.
- Tokens/API keys en `keyring`, no en el repo ni en SQLite.
- Diseñar una interfaz que permita sustituir el proveedor.

## Antes de empaquetar

1. `python -m compileall app main.py scripts`
2. `python -m unittest discover -s tests -v`
3. Probar migración desde la versión anterior.
4. Actualizar `docs/CHANGELOG.md`, `docs/VALIDATION.md`, `docs/ARCHITECTURE.md` cuando cambie arquitectura.
5. En Windows, `start.bat` ejecuta el smoke gráfico una vez por versión.
6. Revisar el contrato de `docs/RESPONSIVE_UI.md` en cada pantalla modificada.
