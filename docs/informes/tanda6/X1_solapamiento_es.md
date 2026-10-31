# X1 — Solapamiento en OPCIONES › Entradas/Salidas

Rama: `tanda-6-x1` (desde `tanda-6`). Fecha: 21-oct-2026.

## Síntoma
Cristian vio la lista de Entradas ("Aire comprimido DI 01", "Presión de agua DI 02", "○ INACTIVO") dibujada bajo los botones "Activar" de Salidas.

## Causa encontrada
1. **Varias OPCIONES vivas en la misma ventana (reproducida).** `Main.abrirConfiguracion()` siempre hacía `pila.push(opcionesComp)`. El recorrido OPCIONES → Menú (engranaje) → "Iniciar sesión" con la sesión ya abierta apilaba otra OPCIONES encima de la anterior. La prueba offscreen con `Main.qml` real dio **4 instancias de OPCIONES** tras repetir el recorrido 3 veces (`[4, 1, 1, 0]`).
2. **La pantalla de E/S no tenía fondo** (`Item` transparente). Si dos instancias quedan visibles a la vez en la misma zona, por ejemplo durante una transición del `StackView` o cuando dos pantallas comparten el área, la de abajo (en Entradas, el segmento por defecto) se ve a través de la de arriba (en Salidas). Esto produce exactamente lo que vio Cristian. La captura `capturas/X1_antes_dos_instancias.png` lo muestra con el QML anterior.
3. **Estructura frágil:** Entradas y Salidas compartían un solo `Flow` con dos `Repeater`, cuyo modelo alternaba entre la lista y `[]`. En la prueba offscreen no se pudo reproducir que los delegados quedaran sin destruir. Aun así, era la única estructura en la que tarjetas de ambos segmentos podían coexistir en el mismo contenedor.

DECISIÓN SIN CONFIRMAR: no se pudo reproducir el caso exacto con las dos ventanas en dos pantallas. La causa 1 queda probada; que haya sido la que vio Cristian es la explicación más probable, no una certeza.

## Corrección
- `Main.qml`: nueva función `irAOpciones(reemplazar)`. Si ya hay una OPCIONES en la pila (`pila.find` por `objectName: "pantallaOpciones"`), vuelve a ella con `pila.pop(previa)` y conserva su sección. Si no la hay, hace push o replace como antes. La usan `abrirConfiguracion`, el login correcto y el cambio de clave.
- `OpcionesEntradasSalidas.qml`:
  - fondo opaco (`fondoOpacoES`);
  - una página `Flickable` por segmento (`paginaEntradas`, `paginaSalidas`, `paginaTemperatura`, `paginaPresion`), cada una con su propio `Repeater` sobre un modelo fijo y mostrada solo con `visible`. Una página oculta ya no puede dibujar en otra.
  - Temperatura y Presión usan el componente común `TarjetaSensor`, que recibe el `tipo` explícito y ya no lo lee de `raiz.segmento`.
- No hay textos visibles nuevos, así que no hubo cambios de i18n. No se tocó lógica de ciclo, de puertas ni de seguridad.

## Revisión del mismo patrón
- **Temperatura/Presión:** compartían un `Repeater` con un modelo ternario. Corregido con el mismo cambio.
- **Parámetros del ciclo** (`OpcionesParametrosCiclo.qml`): ya usa un contenedor por vista (`programa`/`seccion`/`sensores`/`entradas`) con `visible` y modelos fijos. No se cambió. La duplicación de instancias queda cubierta por la corrección de `Main.qml`.
- **Opciones.qml:** cada sección está en su propio `Loader`, con `active` exclusivo. Correcto.

## Pruebas
`tests/test_x1_una_instancia_opciones_qml.py` (offscreen):
- `Main.qml` real: login → E/S → (Menú → Iniciar sesión) ×3 deja **una** OPCIONES y **una** E/S, visibles, en la misma sección. Fallaba antes de la corrección (`[4,1,1,0]`).
- 40 cambios rápidos de segmento (al final, solo Entradas↔Salidas) con una lectura en medio: nunca hay tarjetas de otro segmento visibles; existen las 4 páginas y el fondo opaco; no hay avisos de QML.

## Capturas (`docs/informes/tanda6/capturas/`, offscreen 1100×1400)
- `X1_antes_dos_instancias.png`: QML anterior, dos instancias superpuestas; se ven las Entradas a través de Salidas.
- `X1_despues_dos_instancias.png`: mismo montaje con el QML nuevo; solo se ve Salidas.
- `X1_despues_{entradas,salidas,temperatura,presion}.png`.

Las capturas no ejercitan el modo prueba ni la vuelta a Opciones con el backend real. La prueba de instancias sí cubre la vuelta a Opciones.
