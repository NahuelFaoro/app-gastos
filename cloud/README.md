# Cuentas y sincronización: integración en preparación

Proveedor elegido para la implementación: Supabase Auth, con usuarios separados.
La app estática continúa en Cloudflare. Esta carpeta NO activa ni sube datos.

Falta crear/seleccionar el proyecto Supabase y configurar correo de autenticación.
No compartir una clave `service_role` o `sb_secret_...` con la app ni con testers.
La URL del proyecto y una clave pública son suficientes para el cliente; la
autorización de acceso la controla PostgreSQL con `auth.uid()`.

`supabase/001_private_sync.sql` define una copia privada por usuario y una función
atómica con revisión esperada, idempotencia de reintentos inmediatos y límite de
10 MB. El documento solo lo puede leer su propietario. No hay escritura directa
desde clientes ni endpoints anónimos. Hay que verificar políticas y concurrencia
en el proyecto real antes de conectar las bases locales.

`mobile/sync-merge.mjs` prepara la conciliación entre base común, copia local y
remota. Las ediciones independientes se combinan; edición simultánea y borrado
contra edición se devuelven como conflictos explícitos. El resultado debe pasar
`validate()` antes de aplicarse: relaciones incompatibles (por ejemplo borrar una
cuenta mientras otro dispositivo agrega un gasto) requieren revisión adicional.

Pendientes antes de activar: inicio de sesión y recuperación, almacenamiento de
sesión separado por usuario, integración transaccional con IndexedDB y SQLite,
mapeo estable de identidades de escritorio, pantalla de conflictos, respaldo antes
de vincular, pruebas de aislamiento entre dos usuarios y ensayo con datos ficticios.

Documentación oficial:
- https://supabase.com/docs/guides/auth
- https://supabase.com/docs/guides/database/postgres/row-level-security
