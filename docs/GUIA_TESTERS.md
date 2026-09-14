# App Gastos 0.39.27 — prueba para Windows de 64 bits

## Abrir la app

1. Descargá AppGastos_v0.39.27_TESTERS_OCR.zip.
2. Hacé clic derecho → Extraer todo. No abras el programa desde adentro del ZIP.
3. Abrí la carpeta AppGastos y ejecutá AppGastos.exe. Conservá la carpeta _internal junto al ejecutable.

No necesitás instalar Python. Esta versión incluye el motor OCR y sus modelos locales. El primer análisis puede tardar más mientras carga el motor.

La aplicación no está firmada digitalmente; Windows puede mostrar una advertencia de editor desconocido. Verificá que recibiste el archivo de la persona que te invitó a probarlo.

## Datos de prueba

El paquete no trae la base del desarrollador. Cada persona comienza con su propia base en %APPDATA%\AppGastos\app_gastos.db. Si ya usaste App Gastos en esa cuenta de Windows, se abre la base existente. Usá comprobantes y movimientos ficticios para las pruebas.

## Qué probar

- Crear cuentas, categorías y movimientos; editar y borrar datos de prueba.
- Mover categorías, deshacer y comprobar que no se dupliquen.
- Cargar un ticket en imagen y un PDF escaneado desde Por revisar. Revisar el resultado antes de guardarlo: OCR puede equivocarse.
- Registrar viajes, kilómetros y consultar semana/mes.
- Personalizar campos y tarifas; probar distintos tamaños de ventana y estilos de iconos.
- Cerrar y abrir para comprobar que se guardó todo.

## Cómo reportar un problema

Mandale a quien te pasó la app: versión 0.39.27, qué hiciste, qué esperabas, qué ocurrió y una captura. Indicá tu versión de Windows y la escala de pantalla. Si aparece un error, el registro está en %APPDATA%\AppGastos\app_gastos_errors.log; revisalo antes de compartirlo porque puede incluir rutas o datos de documentos.

## Actualizaciones

Extraé cada nueva versión en una carpeta nueva. Los datos están fuera del ejecutable y se conservan. Antes de actualizar, guardá una copia desde la función de backup de la app.
