# Builds para compartir

## Build LITE recomendada

Ejecutar en Windows:

`scripts\windows\build_share.bat`

Genera `dist\AppGastos_v0.39.17_LITE.zip` con la aplicación de escritorio completa salvo OCR local pesado.

El ZIP grande usado durante desarrollo incluía OpenCV, RapidOCR, ONNX Runtime, PyMuPDF y NumPy. Sólo esos componentes representaban más de 100 MB comprimidos en la build anterior. La build LITE los excluye, además de módulos Qt que App Gastos no utiliza (`QtQml`, `QtQuick`, `QtPdf`, `QtWebEngine`).

La build LITE conserva finanzas, cuentas, análisis, herramienta por zonas, Viajes, Extras, kilometraje real, Mercado Pago, Excel y backups.

El tamaño final exacto depende de la versión de Python/PySide6 instalada en Windows. PySide6 sigue aportando decenas de MB, por lo que no se promete un límite concreto de Discord hasta medir el ZIP generado en esa máquina.

## OCR opcional

Para desarrollo normal:

`scripts\windows\install_ocr.bat`

Build completa con OCR embebido:

`scripts\windows\build_windows_full.bat`

Esta variante es deliberadamente más pesada y no es la recomendada para enviar por mensajería.

## Datos personales

El ejecutable no contiene la base de datos del usuario. Los datos reales viven en `%APPDATA%\AppGastos\app_gastos.db`.

Las instalaciones nuevas usan defaults genéricos y no incluyen viajes/clientes históricos del desarrollo. Compartir el ZIP generado no comparte la base SQLite del equipo que lo compiló.
