# Sincronización por cuenta · beta 0.5.0

Proyecto: vqngomcfkijfjydzqebz. Alojamiento móvil: https://app-gastos-movil.pages.dev/.
El esquema `001_private_sync.sql` está instalado. La clave incluida en los clientes
es publicable; el acceso a cada copia requiere la sesión del propietario y RLS.

## Primer uso

1. En Móvil → Ajustes, crear una cuenta y confirmar el correo. Esta cuenta de la
   aplicación es distinta de la cuenta administradora del dashboard de Supabase.
2. Reiniciar Desktop (0.39.32), abrir Móvil e iniciar sesión con esa misma cuenta.
3. Activar primero la sincronización en Desktop para publicar la base existente.
   La aplicación solicita confirmación y crea un respaldo SQLite antes de hacerlo.
4. En el teléfono, iniciar sesión y activar sincronización. Recibe la copia de la
   cuenta; la copia local sin cuenta permanece separada.

Móvil sincroniza tras editar, al recuperar conexión y cada minuto mientras está
visible. Desktop revisa cada minuto mientras está abierto. Con Desktop apagado,
el teléfono sigue funcionando y enviando cambios a Supabase. No se promete
ejecución de la PWA en segundo plano cuando el sistema operativo la suspende.

## Correo pendiente para testers

El SMTP personalizado aún no está configurado. El servicio predeterminado de
Supabase solo envía correos a miembros del proyecto y tiene límites muy bajos.
Por ahora probar con el email del administrador. Para habilitar altas de amigos,
configurar SMTP en Authentication → Emails → SMTP Settings y verificar entrega
real de confirmación y recuperación. No desactivar la confirmación de email.
Referencia: https://supabase.com/docs/guides/auth/auth-smtp

## Conflictos y límites de la beta

Las ediciones independientes se combinan por identificador. Si dos dispositivos
cambian el mismo registro, se detiene la sincronización y se elige una copia
completa, conservando respaldos. No es una resolución campo por campo.
Los respaldos móviles anteriores pueden descargarse en Ajustes; Desktop los
guarda en `backups` junto a su base, incluyendo la copia remota al resolver.

Se sincronizan cuentas, categorías, movimientos, planes, presupuestos, viajes,
extras, kilometrajes, campos y Flex. El snapshot conserva además los datos
exclusivos de Desktop; recibir históricos/importadores/configuraciones exclusivas
de otra base Desktop se bloquea para evitar una restauración parcial. Esta beta
no reemplaza una restauración SQLite completa al cambiar de PC.

Validación: pruebas de modelos y mezcla; dos navegadores con autenticación y
servidor simulados; adaptador SQLite con bases temporales; OCR sin conexión;
aislamiento RLS de dos usuarios sintéticos probado en SQL con rollback y cero
copias restantes. Falta comprobar entrega real de correo y dispositivos físicos.
