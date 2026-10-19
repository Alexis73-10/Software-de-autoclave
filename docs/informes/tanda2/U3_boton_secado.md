# U3 — Menú Principal: botón de agregar tiempo de secado

Instrucción: `instruccion_claude_code_tanda_2.md` §2 U3.

## Resultado: no hay botón que retirar

No existe ningún botón ni acción para agregar tiempo de secado. **No se cambió código** (no se inventa un botón).

Dónde se buscó:
- `ui_qml/qml/Pantallas/MenuPrincipal.qml` líneas 242–257: la tarjeta `tarjetaSecado` ("TIEMPO ADICIONAL DE SECADO / Programa seleccionado") ya es **informativa**.
  - `interactiva: false`: no responde al toque ni se ve presionada (`TarjetaMenu.qml:38`).
  - `flechaVisible: false`.
  - No tiene `onPulsada`.
  - El `TODO(MP-11)` de la línea 242 explica que "tiempo adicional de secado" sería un parámetro nuevo por programa que no existe.
- `ui_qml/bridge/resumen_sistema.py:213-217`: `tiempoSecado` devuelve siempre "—" (`dominio.SIN_DATO`) y no lee ningún parámetro.
- `TarjetaMenu.qml` y `TarjetaResumen.qml`: sin acciones de secado.
- Búsqueda en todo `ui_qml`, `ui_pyside` y `ui` de `mas.svg`, `mas_circulo`, `tiempo_adicional`, `tiempoAdicional`, `agregar_tiempo` y `secado_extra`: sin resultados (solo `programas.svg`, que no es esto).
- `PantallaCicloEnCurso.qml` / `GraficaCiclo.qml`: el único botón con "tiempos" es el desplegable de duración de fases de la gráfica, no agrega tiempo.

Captura del Menú Principal (offscreen, con la barra inferior ya de U2): `docs/informes/tanda2/U3_menu_principal.png`. La tarjeta en cuestión es la de aro naranja (fila 2, derecha), sin flecha y con "—". Los iconos de las tarjetas no se dibujan en el render offscreen (efecto de color); en el equipo sí.

## Interpretación y pendiente

Es probable que Cristian vea la tarjeta como un botón, porque tiene el mismo aspecto que las tarjetas que sí abren algo.

**PENDIENTE (decisión de producto):** elegir una de estas opciones:
- (a) retirar la tarjeta;
- (b) dejarla como dato (p. ej. "TIEMPO DE SECADO" con `secado.tiempo_secado` del programa seleccionado);
- (c) dejarla como está.

Cualquiera de las tres cambia el texto o el valor mostrado, que la instrucción pide no tocar; por eso no se hizo.

## Pruebas

Sin cambios de código; la suite no cambia por U3.
