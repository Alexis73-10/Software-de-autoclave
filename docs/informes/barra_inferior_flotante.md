# Informe — Barra inferior flotante y ajustes de Parámetros del ciclo (20-oct-2026)

Rama `tanda-4`, sin commit (cambios en el árbol de trabajo para revisión visual).

## Pruebas
- Línea base antes de empezar: no se corrió la suite completa por separado; el subconjunto i18n/opciones/parámetros pasaba antes de los cambios.
- Al terminar: **4022 pasan, 1 omitida, 3 xfail, 0 fallos** (suite completa).

## A. Barra inferior flotante (instruccion_claude_code_barra_inferior_flotante.md)

| Pantalla | Cambio |
|---|---|
| `Login.qml` (T1) | `BarraInferiorMenu` sale del `pie` de la tarjeta y pasa a ser hija de la pantalla, con la misma colocación que Opciones (x = 34, 171 desde abajo, lienzo 1196). Conserva `barraInferiorLogin`, `inicioActivo: true`, señales y versión. |
| `CambioClave.qml` (T2) | `BarraInferior` (4 iconos) reemplazada por `BarraInferiorMenu` flotante `barraInferiorCambioClave`; `atrasHabilitado`/`inicioActivo` = `!control.ocupado`. Quitados `historial` y `mantenimiento`. |
| `NuevoUsuario.qml` (T3) | Barra dibujada a mano reemplazada por `BarraInferiorMenu` flotante `barraInferiorNuevoUsuario` (Atrás → `pulsarAtras()`, Inicio → `pulsarInicio()`, ambos ya confirman el descarte). |

En las tres, el alto de la tarjeta pasa a `raiz.height - 176 - 201·(ancho/1196)`: deja la barra (139) con los márgenes de Opciones (32 abajo y 30 entre la tarjeta y la barra).

`Componentes/BarraInferior.qml` queda **sin usos** en pantallas; no se borró.

Pruebas: nuevo `tests/test_barra_inferior_flotante_qml.py`, que carga cada pantalla real a 1200×1920 y comprueba que la barra existe, está debajo de la tarjeta y fuera de ella, en la posición de Opciones; que Atrás e Inicio emiten su señal; y que ninguna tarjeta conserva `pie`. Ninguna prueba existente buscaba `botonAtrasNuevoUsuario`, así que no hubo que modificar ninguna.

Verificación visual (T5): **no se capturaron pantallas**, así que falta la comparación con la referencia.

**DECISIÓN SIN CONFIRMAR:** `Instalacion.qml`, Preciclo y Ciclo en curso no se tocaron (§4 de la instrucción).

Revertir: `git checkout -- src/autoclave/ui_qml/qml/Pantallas/{Login,CambioClave,NuevoUsuario}.qml` (ojo: esos archivos ya tenían otros cambios sin commit de la tanda) y borrar la prueba nueva.

## B. Opciones › Parámetros del ciclo

- **Descripción de cada parámetro:** los 94 parámetros de los perfiles tienen una descripción corta en `es.json`/`en.json` (`parametros_desc.<sección>.<clave>`).
- **Última modificación:** usuario, fecha y hora (dd/mm/aaaa hh:mm, del `audit_log`). Si nunca se modificó, se muestra «sin cambios».
- Las dos aparecen **solo en la tarjeta de ajuste** que se abre al tocar el parámetro, al final de la tarjeta y separadas por una línea. La tarjeta es más alta y tiene más espacio entre elementos. El listado no cambia.
- **Modo de descompresión:** en vez del teclado numérico ahora hay un botón por modo y, debajo, el nombre y qué hace el modo elegido (`descompresion_modos.<n>`).
  - **DECISIÓN SIN CONFIRMAR:** los botones van del mínimo al máximo del catálogo, **0 a 5**, no 1 a 4: el código actual implementa los modos 0 (natural) y 5 (enfriamiento con escape lento), y una carga líquida exige el modo 4 o 5. Para limitarlo a 1–4 habría que cambiar el catálogo y los perfiles (es un cambio de comportamiento).
- Calibraciones: la pantalla ya mostraba la última calibración (usuario y fecha); no se cambió.
- **Pendiente:** el resto de parámetros del equipo (configuración de mantenimiento, impresora, etc.) se auditan, pero la pantalla todavía no muestra quién los modificó por última vez.
- Pruebas: `test_i18n.py` (familias `parametros_desc.` y `descompresion_modos.`, que comprueba que cada parámetro de los perfiles tiene su descripción) y `test_i18n_linea_base.py` (claves nuevas sin referencia vieja).
- Las traducciones al inglés son nuevas y nadie las ha revisado.
