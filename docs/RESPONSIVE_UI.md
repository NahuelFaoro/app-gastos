# Contrato responsive de App Gastos

La responsividad es una regla de plataforma, no una corrección puntual de cada pantalla.

## Modos compartidos

`app/layouts.py` define `responsive_mode(width, height)`:

- **wide**: escritorio horizontal con espacio suficiente.
- **compact**: ventana mediana o monitor vertical ancho.
- **narrow**: ventana angosta / monitor vertical donde una tabla horizontal deja de ser usable.

Las páginas nuevas deben usar estos modos en lugar de inventar breakpoints aislados.

## Reglas visuales permanentes

1. Ningún dato configurable puede generar una cantidad ilimitada de columnas.
2. En `narrow`, tablas densas se transforman en tarjetas, chips o bloques verticales.
3. Métricas cortas conservan ancho natural y se centran; no se estiran sólo para rellenar la pantalla.
4. Textos importantes usan `wordWrap` cuando pueden crecer por configuración o traducción.
5. Controles secundarios pueden ocultarse o moverse en pantallas angostas, pero nunca la acción principal.
6. Un cambio de escala de UI debe conservar la jerarquía y no producir ventanas fuera de pantalla.
7. Toda herramienta configurable debe seguir viéndose correctamente después de renombrar campos o agregar campos nuevos.

## Checklist para una pantalla nueva

- Probar mentalmente/visualmente en 1920×1080, 2560×1440 y 768×1360.
- Revisar textos largos y valores monetarios grandes.
- Revisar zoom de UI alto.
- Evitar `setFixedWidth` salvo iconos/botones deliberadamente compactos.
- Preferir `FlowLayout`, `QBoxLayout` que cambie dirección o tarjetas compactas.
- Asegurar que selección, edición y doble clic sigan siendo claros en ambos modos.

## Cobertura v0.39.13

Además de Dashboard, Cuentas, Análisis, Viajes y Flex, las páginas Movimientos, Calendario, Ajustes, Recurrentes, Móvil, Cuotas e Importaciones usan `responsive_mode(width, height)` para que un monitor vertical active el layout compacto aunque su ancho supere un breakpoint histórico.

Los selectores y configuradores dinámicos deben envolver controles con `FlowLayout` o cambiar dirección; agregar nuevas categorías, campos u opciones nunca puede obligar a ensanchar la ventana.
