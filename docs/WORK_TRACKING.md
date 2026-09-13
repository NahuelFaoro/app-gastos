# Gestión de trabajo — Viajes y Extras

## Viajes

Cada registro representa un viaje. Los destinos se guardan por separado y su cantidad define `stop_count`.

Las métricas semanales son:

- **Viajes**: cantidad de registros.
- **Paradas**: suma de destinos/paradas.
- **Bulto** y **Lluvia**: cantidad de viajes marcados.
- **Flex**: cantidad de paradas pertenecientes a viajes Flex.
- **Cliente propio**: cantidad de viajes marcados como propios.
- **Cobrado**: suma de importes registrados.
- **KM reales**: diferencia entre odómetro inicial y final de las jornadas completas.

## Kilometraje real

El kilometraje se registra únicamente mediante el odómetro de la moto. `work_day_mileage` guarda `odometer_start` y `odometer_end` por fecha.

Cuando existe un cierre anterior, la UI puede proponerlo como inicio de la jornada siguiente. Una corrección manual no se pisa automáticamente.

No se calcula distancia a partir de direcciones ni se consume ningún servicio externo de mapas.

## Resumen mensual

**Este mes** muestra los totales del mes y un desglose visual por semana: viajes, paradas, Bulto, Lluvia, Flex, Cliente propio, KM reales y Cobrado.

## Extras

Extras registra jornadas de aplicaciones como PedidosYa/Rappi/Uber con aplicación, fecha, horas, pedidos/viajes, importe y detalles.
