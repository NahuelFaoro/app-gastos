# Sincronización Desktop ↔ Móvil

Estado: propuesta técnica; NO activada. Cloudflare Pages publica archivos y no almacena los registros de los usuarios. La exportación JSON actual es un traspaso manual, no sincronización.

## Comportamiento esperado

Cada usuario tiene un espacio privado y puede vincular PC, Android e iPhone. Ambos clientes trabajan con su copia local. Al conectarse envían los cambios pendientes y reciben los del servidor. La PC apagada no impide trabajar en el móvil; al abrirla recupera los cambios.

## Servicio propuesto

Un Worker con D1 en la misma cuenta Cloudflare, bajo las cuotas gratuitas mientras alcancen. Autenticación de usuarios independiente del acceso al panel Cloudflare. Cada petición valida sesión y pertenencia al espacio. No se comparte una clave global en JavaScript, y cada tester tiene datos separados.

Cada entidad necesita UUID estable, revisión del servidor y marca de borrado. Las referencias SQLite numéricas permanecen locales, con tabla de correspondencias. No usar fechas de dispositivo para resolver conflictos: el reloj puede estar desajustado.

Protocolo previsto: intercambio paginado de operaciones con identificador idempotente; envío con revisión base; respuesta de conflicto si cambió la misma entidad; recepción por cursor monotónico. Aplicar cada lote de manera atómica junto con su cursor. Si falla, volver a enviar la misma operación sin duplicarla. Al mover una categoría se actualiza su padre, nunca se crea una copia.

## Antes de activarlo

- Unificar las reglas de cuotas, tipos de cuenta, históricos, campos y tarifas personalizados. La interfaz móvil 0.2 amplía cobertura pero no tiene equivalencia completa con todos los repositorios Python.
- Asegurar respaldo local y prueba de restauración antes del primer emparejamiento.
- Probar edición simultánea, reintentos, borrados, pérdida de red, conflictos y revocación de un dispositivo.
- Elegir autenticación y alcance de cifrado; definir recuperación de acceso.
- Pedir al usuario la activación concreta antes de subir su información financiera. La autorización previa para publicar archivos estáticos no autoriza publicar su base.

Límites oficiales consultados: https://developers.cloudflare.com/d1/platform/pricing/ y https://developers.cloudflare.com/workers/platform/limits/

## Decisión de autenticación (0.4)
El usuario eligió iniciar sesión con una cuenta en cada dispositivo. Se propone Supabase Auth y se espera la creación de su cuenta/proyecto. El esquema preliminar está en cloud/supabase y la conciliación pura en mobile/sync-merge.mjs. La propuesta inicial Worker/D1 queda reemplazada para autenticación y almacenamiento privado. Ningún cliente se conecta aún: siguen pendientes integración de sesiones, mapeo SQLite, pantalla de conflictos y pruebas de políticas en el backend real.
