# App Gastos v0.39.21

Aplicación de finanzas personales con herramientas de trabajo integradas.

## Ejecutar

Abrí **`start.bat`**. La primera ejecución crea/actualiza `.venv`, instala las dependencias base **y el motor OCR** si faltan, y ejecuta un smoke test preventivo antes de abrir tus datos reales.

La base principal se guarda en `%APPDATA%\AppGastos\app_gastos.db`, fuera de la carpeta del programa. Cambiar de versión no elimina tus datos.

## Qué cambia en v0.39.21

- Categorías muestra paneles por categoría principal, distribuidos en columnas responsive sin huecos entre paneles de distintas alturas.
- Los hijos se despliegan en el lugar, con sangría; se pueden revisar varias ramas simultáneamente sin entrar/salir de carpetas.
- Cada subcategoría tiene un botón ↑ para sacarla un nivel con un clic. El arrastre entre filas visibles permite cambiarla de grupo; el destino superior permite hacerla principal.
- La búsqueda conserva los ancestros de cada resultado y muestra su contexto.
- Desplegar/contraer conserva los widgets y no reconstruye la página. Sin cambios de esquema ni de IDs históricos.

## Base v0.39

- Contrato responsive global para escritorio horizontal, monitor vertical y ventanas angostas.
- Viajes usa tarjetas en modo compacto/narrow para evitar tablas ilegibles.
- Tarifas configurables de Viajes: por unidad (`cantidad × tarifa`) o por opción (`Zona 2 → precio`).
- La herramienta por zonas/Flex permite cambiar nombre, singular/plural, zonas, orden y tarifas.
- Análisis se rediseña alrededor de período + distribución + ranking de categorías, inspirado en la referencia móvil del proyecto.
- Tarjetas de crédito pagadas no se convierten en activos ni inflan el patrimonio.
- Instalaciones nuevas parten de datos genéricos; no se distribuyen viajes/clientes históricos del desarrollo.
- OCR vuelve a formar parte de la instalación normal iniciada por `start.bat`; el manifiesto pesado se mantiene separado sólo para organizar dependencias y builds.

## Estructura de la carpeta

La raíz se mantiene deliberadamente corta:

- `app/` — código de la aplicación.
- `docs/` — arquitectura, changelog, mapa del proyecto y reglas técnicas.
- `scripts/` — diagnóstico, validación, instalación y compilación.
- `tests/` — pruebas automáticas.
- `web/` — interfaz móvil/web.
- `main.py` — punto de entrada.
- `requirements.txt` — dependencias base.
- `requirements-ocr.txt` — dependencias pesadas de OCR, instaladas automáticamente por `start.bat`.
- `start.bat` — lanzador normal de Windows.

Para entender el proyecto, empezá por **`docs/PROJECT_MAP.md`**, después **`docs/ARCHITECTURE.md`** y **`docs/RESPONSIVE_UI.md`**.

## Viajes

- 1 fila = 1 viaje.
- Cada destino cuenta como una **parada**.
- Un viaje Flex suma tantas unidades Flex como paradas tenga.
- El kilometraje se registra únicamente mediante **odómetro real**.
- Campos base y personalizados pueden adaptarse al trabajo de cada persona.
- Ocultar un campo no borra el dato histórico de viajes ya cargados.
- Las tarifas calculadas son independientes de `Cobrado`; se pueden copiar cuando corresponda.

## Build liviana para compartir

En Windows ejecutá:

`scripts\windows\build_share.bat`

Genera `dist\AppGastos_v0.39.21_LITE.zip`. Excluye el motor OCR local (RapidOCR/ONNX/PyMuPDF), que era la principal causa del tamaño de las builds anteriores.

La build completa con OCR sigue disponible mediante `scripts\windows\build_windows_full.bat`.

## Validación

La entrega ejecuta compilación sintáctica, pruebas unitarias, auditoría y compatibilidad de base. El smoke gráfico nativo se ejecuta automáticamente en Windows desde `start.bat` antes de abrir los datos reales. Detalles en `docs/VALIDATION.md`.
