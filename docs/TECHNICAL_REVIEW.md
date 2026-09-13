# Revisión técnica — v0.39.19

## Interpretación del producto

App de escritorio de finanzas personales con registro configurable de trabajo de reparto. Python/PySide6 presenta la UI; SQLite conserva datos locales. La interfaz web móvil usa esa misma base a través de la PC. No existe sincronización remota independiente de la computadora.

## Precisión monetaria

El esquema utiliza REAL y varios cálculos/agregados utilizan float. La v0.39.19 introduce Decimal en la entrada de movimientos y en cálculos de cuotas, con redondeo ROUND_HALF_UP a centavos. Por ejemplo, 2.675 se guarda como 2.68; una compra de 2.01 en dos cuotas genera 1.01 y 1.00. La proyección y la generación usan la misma función. Se rechazan planes nuevos cuya última cuota resultaría cero o negativa.

Esto no constituye una migración general a precisión decimal: saldos, importaciones directas, tarifas, históricos y agregaciones SQL todavía deben revisarse. Los valores históricos no se redondean ni se reescriben al abrir una base. Los planes existentes conservan su cuota base.

Una migración completa requiere inventariar todos los campos monetarios, separar dinero de cantidades/tarifas con precisión diferente, definir límites y una política explícita para fracciones de centavo históricas, y migrar a centavos enteros mediante copia de respaldo. Deben verificarse saldos, totales, proyecciones, importaciones y restauración antes/después, manteniendo IDs y relaciones. No conviene convertir indiscriminadamente todos los campos REAL: también representan odómetros y cantidades.

## Acceso móvil

Se agregaron límite global de cinco intentos de vinculación cada 60 segundos, validación estricta de objetos JSON, rechazo de números JSON no finitos, tamaños máximos y timeout de socket de 15 segundos. Las rutas protegidas autentican antes de leer cuerpos. El límite también cuenta intentos exitosos y solicitudes inválidas; los dispositivos ya vinculados continúan funcionando durante el bloqueo. El límite se reinicia al crear una nueva instancia del servidor.

El servicio sigue escuchando en la red local mediante HTTP. El código y el token compartido siguen persistidos en SQLite; generar un nuevo código no revoca dispositivos ya vinculados. El transporte no está cifrado y el servidor no ofrece aislamiento por usuario ni protección completa contra denegación de servicio. Debe usarse en una red de confianza y no exponerse directamente a Internet.

Para acceso remoto faltan HTTPS, autenticación y revocación por dispositivo, almacenamiento de credenciales fuera de la base exportable, límites de concurrencia, despliegue supervisado y un diseño de sincronización/conflictos. Poner HTTPS delante del servidor actual no resuelve por sí solo estos requisitos.

## Organización y entrega

El proyecto conserva la división UI/repositorios/integraciones, auditoría estructural y pruebas de regresión. GitHub guarda el código; no sustituye un respaldo de la base personal. El repositorio privado excluye bases, credenciales, entorno Python y compilaciones.
