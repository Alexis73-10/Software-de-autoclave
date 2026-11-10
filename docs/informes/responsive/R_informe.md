# Tanda responsive: informe

Rama `responsive` desde `dev` (d89577eb, merge de la tanda horizontal). Sin merge ni push: lo decide Cristian. Entrega no compilada. Prompt: `docs/mis_plans/prompt_claude_code_responsive.md`, con la **decisión de Cristian recibida durante la tanda (10-nov)**: la interfaz se ajusta a la pantalla, **sin barras ni franjas** (negras ni del color de fondo) a los lados ni arriba o abajo, en cualquier proporción y escala de Windows. Esa decisión reemplazó la propuesta por defecto del prompt (franjas laterales y `AreaFija` centrada).

Diagnóstico previo (sobre dev, sin tocar código): `diagnostico.md`.

## Resumen

- **Regla de proyección** (`Tema/Escala.qml`, una sola implementación; las 4 raíces y los arneses solo enlazan):
  - `factor = factorPara(ancho, alto) = min(ancho / anchoDiseno, alto / altoDiseno)` con el lienzo de la orientación de ese mismo tamaño (vertical 1200x1920, horizontal 1920x1200). Es el **factor único** de letras, íconos, botones y zonas táctiles: nada se deforma.
  - `anchoLienzo = anchoLienzoPara(ancho, alto) = ancho / factor` y `altoLienzo = altoLienzoPara(ancho, alto) = alto / factor` (nunca menores que los de diseño): el lienzo mide **siempre** lo mismo que la ventana. Lo que sobra en un eje lo reparten las pantallas.
  - Tamaño inválido (0, negativo, NaN, infinito): factor 1 y lienzo de diseño (antes, con 0x0, factor 0 y `altoLienzo` NaN).
  - `Escala.dpr` (de `Screen.devicePixelRatio` de cada raíz), `escalaFisica = factor x dpr`, `escalaFisicaMinima` 0,5 y `soportado()`, y `margenTactil(lado)` para las zonas táctiles.
  - A 1200x1920 y 1920x1200 al 100 % da exactamente factor 1 y el lienzo de diseño.
- **AreaFija llena el lienzo** (antes centraba un área de diseño y dejaba franjas).
- **Reparto del espacio sobrante** (solo anclajes y posiciones, sin cambiar tamaños de diseño ni textos; ver tabla por pantalla).
- **Zonas táctiles mínimas**: 136 `MouseArea` de clic, 13 con margen propio y 2 `TapHandler` se extienden de forma invisible hasta min(44 px físicos, su tamaño de diseño). Margen 0 a escala física 1 o más.
- **Escala de Windows**: se compensa (la interfaz ocupa la misma fracción de la pantalla física a 100–200 %); no se fija ninguna política ni variable (ya es `PassThrough`).
- **Dos pantallas**: no hay defecto (un proceso y un motor por pantalla; singletons por motor): no se refactorizó `Escala`.
- **Defecto de la tanda horizontal corregido**: al girar de horizontal a vertical en caliente, el nombre del programa de Preciclo y Ciclo en curso conservaba el ancho del horizontal (`Binding on width { when: hz }` restauraba un valor fijo) y se salía de su caja.
- 1200x1920 y 1920x1200 al 100 %: **idénticos a dev** (ver «Verificación»).

## Commits

- `871d4a5a` feat(ui): regla única de proyección del lienzo en Escala (factorPara, altoLienzoPara, dpr)
- `bfe05c80` docs(responsive): diagnóstico de dev a 19 tamaños
- `1335a9d5` feat(ui): interfaz sin franjas en cualquier proporción y zonas táctiles mínimas
- `1f906975` fix(ui): nombre del programa sin ancho fijo tras girar de horizontal a vertical en caliente
- (cierre) docs(responsive): informe, capturas, comparaciones, estado y CERRADO

## Reparto del espacio sobrante, por pantalla (DECISIÓN SIN CONFIRMAR en los detalles)

El principio «sin barras» está decidido; lo que crece en cada pantalla es propuesta:

| Pantalla | Lienzo más ancho | Lienzo más alto |
|---|---|---|
| Horizontal, todas (Preciclo, Ciclo en curso, Menú, Opciones, Reportes, sesión, asistente, modales) | Ya repartían con el marco del horizontal (`anchoMarco = ancho / escala`): columna derecha (alarmas, gráfica, resumen) y barras a lo ancho; cabecera con campana y engranaje a la derecha | Cabecera arriba, barra inferior abajo, tarjetas principales a todo el alto (Preciclo, Ciclo en curso); Menú, Opciones y Reportes ya eran de alto flexible |
| Preciclo (vertical) | Tarjeta principal, línea del ciclo, tarjeta de alarmas y barra inferior a todo el ancho; cabecera a los bordes; bloque de ciclo y parámetros (tamaño fijo) centrado; INICIAR y RECONOCER FALLA a la derecha | Tarjeta de alarmas más alta; botones y barra abajo |
| Ciclo en curso (vertical) | Tarjeta, gráfica (y panel de fin de ciclo), barra de progreso y barra inferior a lo ancho; bloque de ciclo, fases, parámetros y relojes centrado | La gráfica absorbe el alto (como antes) |
| Menú (vertical) | Las cuatro tarjetas y las cuatro del Resumen se estiran a lo ancho entre los márgenes de 54 (posiciones proporcionales); título y casa centrados; barra a lo ancho | Como antes (el resumen baja a la mitad del sobrante) |
| Opciones (vertical) | Tarjeta, título y contenido de la sección a lo ancho | Como antes |
| Reportes (vertical) | Contenido y barra a lo ancho | Como antes (desplazable) |
| Login, CambioClave, NuevoUsuario, asistente | Tarjeta a lo ancho; barra flotante con su escala de diseño | Tarjeta a todo el alto, contenido arriba (como su diseño), barra abajo |
| Reposo e intro | Fondo recortado a la ventana (PreserveAspectCrop); logo, reloj y barra de arranque con su tamaño de diseño, centrados | Ídem |
| BarraSuperior y EncabezadoMenu | A todo el ancho del lienzo; íconos al borde derecho | — |

Alternativas no implementadas (para decidir): en Preciclo vertical ancho, repartir también las columnas del bloque de ciclo y de parámetros (hoy centradas con su ancho de diseño); en Login/CambioClave muy altos, centrar el formulario en el alto de la tarjeta.

## Tabla de tamaños

A cualquier escala de Windows la escala física es la misma que al 100 % (el factor se divide por la escala y el lienzo es el mismo). Con escala de Windows se verificaron además 1920x1080 y 1080x1920 a 125, 150 y 200 % (capturas) y 1920x1080 @150 %, 1200x1920 @125 %, 2560x1440 @200 % y 1080x1920 @175 % (prueba «sin barras»).

| Tamaño físico | Orientación | Factor (100 %) | Lienzo (px de diseño) | Escala física | Soportado | Capturas y prueba «sin barras» |
|---|---|---|---|---|---|---|
| 1024x600 | horizontal | 0.500 | 2048 x 1200 | 0.500 | sí | sí (claro y oscuro) |
| 1280x720 | horizontal | 0.600 | 2133 x 1200 | 0.600 | sí | diagnóstico de dev y pruebas de la regla |
| 1366x768 | horizontal | 0.640 | 2134 x 1200 | 0.640 | sí | diagnóstico de dev y pruebas de la regla |
| 1440x900 | horizontal | 0.750 | 1920 x 1200 | 0.750 | sí | diagnóstico de dev y pruebas de la regla |
| 1600x900 | horizontal | 0.750 | 2133 x 1200 | 0.750 | sí | diagnóstico de dev y pruebas de la regla |
| 1600x1200 | horizontal | 0.833 | 1920 x 1440 | 0.833 | sí | sí (claro y oscuro) |
| 1920x1080 | horizontal | 0.900 | 2133 x 1200 | 0.900 | sí | sí (claro y oscuro) |
| 1920x1200 | horizontal | 1.000 | 1920 x 1200 | 1.000 | sí | sí (claro y oscuro) |
| 2560x1080 | horizontal | 0.900 | 2844 x 1200 | 0.900 | sí | sí (claro y oscuro) |
| 2560x1440 | horizontal | 1.200 | 2133 x 1200 | 1.200 | sí | diagnóstico de dev y pruebas de la regla |
| 600x1024 | vertical | 0.500 | 1200 x 2048 | 0.500 | sí | sí (claro y oscuro) |
| 720x1280 | vertical | 0.600 | 1200 x 2133 | 0.600 | sí | diagnóstico de dev y pruebas de la regla |
| 768x1024 | vertical | 0.533 | 1440 x 1920 | 0.533 | sí | diagnóstico de dev y pruebas de la regla |
| 1080x1920 | vertical | 0.900 | 1200 x 2133 | 0.900 | sí | sí (claro y oscuro) |
| 1080x2560 | vertical | 0.900 | 1200 x 2844 | 0.900 | sí | sí (claro y oscuro) |
| 1200x1600 | vertical | 0.833 | 1440 x 1920 | 0.833 | sí | sí (claro y oscuro) |
| 1200x1920 | vertical | 1.000 | 1200 x 1920 | 1.000 | sí | sí (claro y oscuro) |
| 1440x2560 | vertical | 1.200 | 1200 x 2133 | 1.200 | sí | diagnóstico de dev y pruebas de la regla |

## Zonas táctiles (DECISIÓN SIN CONFIRMAR)

- Mínimo: **min(44 px físicos, el tamaño de diseño de la zona)**. El tope en el tamaño de diseño garantiza que a 1200x1920 y 1920x1200 al 100 % nada cambie (casilla «Recordar usuario» y enlace «¿Olvidó su contraseña?» del Login miden 27 px de diseño: siguen así; agrandarlos también ahí es decisión aparte).
- Cómo: margen invisible (`anchors.margins` negativo de la `MouseArea`, o `margin` del `TapHandler`), calculado por `Escala.margenTactil(lado)` con el lado real en px lógicos y `Escala.dpr`. El dibujo no cambia.
- Dónde: toda `MouseArea` de clic con `anchors.fill` que no lee la posición del puntero (sin `mouse.x/y`, arrastre, rueda ni `hover`): 136 (135 por guion y la de los campos de NuevoUsuario a mano); las 13 que ya tenían margen propio (campana, engranaje, ojos de contraseña, volver) suman el mínimo a su zona ampliada; los 2 `TapHandler` del Login. No se tocaron las de arrastre o posición (deslizador INICIAR, cursor y zoom de la gráfica, deslizador de cancelar): miden ≥ 44 px físicos a escala 0,5.
- Efecto lateral aceptado: a escala física < 1 dos zonas vecinas ampliadas pueden solaparse; gana la de arriba (orden de dibujo). Pendiente de banco con los táctiles.

## Tamaño mínimo soportado (DECISIÓN SIN CONFIRMAR)

- **Escala física 0,5**: 1024x600 en horizontal y 600x1024 en vertical (px físicos), a cualquier escala de Windows. Ahí: zonas táctiles ≥ 44 px físicos (o su tamaño de diseño), sin texto recortado ni fuera de la ventana (prueba), letra mínima ≈ 6 px físicos en las etiquetas de 12 px de diseño de Preciclo (legibilidad pendiente de banco).
- Por debajo no hay piso: el lienzo se sigue achicando entero (nada queda fuera de la pantalla; `Escala.soportado()` lo informa). No se subió `fuenteMinima` (subirla haría que los textos que se reducen dejaran de caber).

## Escala de Windows (DPI)

Ver `diagnostico.md`. La ventana a pantalla completa recibe su tamaño en px lógicos; con el factor sobre ese tamaño, la interfaz ocupa la misma fracción de la pantalla física a 100, 125, 150, 175 y 200 % (escala física constante). La escala se **compensa**, no agranda la interfaz. Diferencia residual: `Escala.fuente()` redondea a px lógicos enteros, así que a 150 % la letra va de 1,5 en 1,5 px físicos. No se fijó `setHighDpiScaleFactorRoundingPolicy` en `app.py`/`exe_unico.py`: Qt 6 ya usa `PassThrough` (DECISIÓN SIN CONFIRMAR: fijarlo explícitamente solo blindaría contra un cambio futuro de Qt).

## Pruebas nuevas

- `tests/test_resp_escala_regla.py` (30): tabla de 20 tamaños x 5 escalas → factor, ancho y alto del lienzo, orientación, escala física constante; tamaños de diseño exactos; 0x0, negativos, NaN, infinito y ventanas muy chicas sin NaN; continuidad sin saltos; `margenTactil`; las 4 raíces solo enlazan la regla y su lienzo mide la ventana; las raíces reales siguen el tamaño en caliente.
- `tests/test_resp_dpi_y_ventanas.py` (4): la escala de Windows se compensa (QT_SCALE_FACTOR 1–2 en el subproceso); un proceso y un motor por pantalla; dos motores no comparten `Escala`.
- `tests/test_resp_sin_barras.py` (43): **criterio «sin barras»**: la ventana se pinta de un color centinela (magenta puro) y en la captura no queda ningún px de ese color (el contenido cubre el 100 % de la ventana, bordes incluidos) en 4:3, 16:10, 16:9 y 21:9 en las dos orientaciones, en 1024x600 / 600x1024 y en 1920x1080 @150 %, 1200x1920 @125 %, 2560x1440 @200 % y 1080x1920 @175 %; nada fuera de la ventana; ningún desborde de texto nuevo respecto al tamaño de diseño; zonas táctiles mínimas; lienzo de diseño exacto a 1200x1920 y 1920x1200. Excepciones justificadas en la prueba: «encogido» (D8-5.4 lo permite), secciones del desplazable de Reportes (contenido que sigue al desplazar, igual en dev) y un residual (leyenda de la gráfica a 1024x600, ver «Pendiente»).
- `tests/test_resp_giro_en_caliente.py` (16): cuatro arneses (Ciclo en curso, Menú, asistente, teclado numérico) llevados en caliente de horizontal a vertical, de vertical a horizontal, por tres resoluciones y a vertical ancho: la geometría de todo lo visible queda igual que abiertos directamente en el tamaño final. Encontró el defecto del nombre del programa (corregido).
- Herramientas (no son pruebas): `tests/banco/resp_capturas.py` (capturas a tamaños y escalas con las revisiones de zonas táctiles, letra mínima, lienzo y centinela; `--analizar`), `resp_igual_dev.py` (comparación por píxel contra dev con dev contra dev), `resp_geometria_igual.py` (comparación de la geometría de cada ítem contra dev), `resp_hojas.py` (hojas de contacto y miniaturas).

## Pruebas existentes

No se modificó ninguna prueba existente. Los arneses de `qml/Pruebas/` ganaron los `Binding` de `dpr` y `anchoLienzo` y usan `factorPara`/`anchoLienzoPara`/`altoLienzoPara`; `hor_capturas.py` y `hor_vertical_igual.py` no se tocaron (siguen sirviendo contra dev).

## Verificación

**1200x1920 y 1920x1200 al 100 % iguales a dev** (árbol de dev en un worktree desligado; ≈132 escenarios de la tanda horizontal por tamaño, tema claro):

- **Geometría** (`tests/banco/resp_geometria_igual.py`, `geometria_igual_<WxH>.json`): clase, objectName, posición, tamaño, texto y letra de cada ítem visible, rama contra dev, sin los subárboles con animación continua (deslizador INICIAR y círculos de fase) ni los contenedores anónimos que agrega la rama (que a estos tamaños miden la pantalla y no dibujan). **1200x1920: 131 de 132 iguales; 1920x1200: 128 de 132.** Las diferencias son solo el reloj con segundos de Fecha y hora (2), la cuenta regresiva de la píldora «Alarmas (2) · 30 s / 29 s» (1) y la intro animada (que cambia también entre dos corridas de dev).
- **Píxel a píxel** (`tests/banco/resp_igual_dev.py`, `igual_dev_<WxH>_claro.json`; ignora la franja del reloj y < 190 como `hor_vertical_igual.py`, y captura dev dos veces): **1200x1920: 119 idénticos y 13 que cambian también entre dos corridas de dev** (animación o reloj); **1920x1200: 122 idénticos, 10 animados y 1 distinto, `d_fecha_hora`** (el reloj con segundos: la geometría confirma que lo único distinto es el texto «HH:MM:SS»).
- Lección de la tanda: en una corrida con el equipo cargado, la comparación por píxel atribuyó a «zona animada» un cambio real (el nombre del programa de Preciclo en vertical quedó corrido por un `implicitWidth` sin `id`, corregido en 1f906975); la geometría lo detectó. Por eso la herramienta de píxeles ya no da por buenas esas zonas y la evidencia principal es la geometría.

**Suite completa** (`pytest tests -n 8`, con `PYTHONPATH=<worktree>\src`): **12497 pasan, 16 fallan, 11 saltadas, 15 xfail** (11 min 51 s). Las 16 fallas son exactamente las 16 preexistentes de dev listadas en el prompt (c2_programas_persistentes, q1_r1p3 test_hay_10_perfiles, t12_c07_c13_json, t12_v12_ventana_referencia_en_cero x3, t17_copia_programa[estabilizacion], t29_descompresion_fin_modo_solido x6, t28_a14_m3_brecha x2, v8b descripciones); ninguna es de la interfaz. Las ≈93 pruebas de más son las nuevas `test_resp_*`. En una corrida intermedia falló una vez `test_v8b_textos::test_qml_no_recorta_textos_con_puntos_suspensivos` (FileNotFoundError: un archivo QML temporal de otra prueba en paralelo desapareció mientras la prueba listaba la carpeta); pasó sola y en la corrida final.

**Efecto lateral preexistente**: la suite reescribe `src/autoclave/cycles/user/*.json`; se restauraron con `git checkout` antes de cada commit y no van en ninguno.


## Capturas

`capturas/` (≈21 MB):

- `hoja_<WxH>_<tema>.png`: hoja de contacto con 22 pantallas y estados (intro, reposo, login con y sin teclado, cambio de clave, nuevo usuario, asistente, Preciclo con alarmas y en falla, Ciclo en curso con la gráfica, fin fallido y pantalla completa, modal de paro, Menú, Historial, Ciclos hoy con el detalle, Reportes mes y día, Opciones, Entradas/Salidas, Información del sistema, teclado numérico) en 4:3 (1600x1200, 1200x1600), 16:10 (1920x1200, 1200x1920), 16:9 (1920x1080, 1080x1920), 21:9 (2560x1080, 1080x2560) y el mínimo (1024x600, 600x1024), en claro y oscuro; y a 1920x1080 y 1080x1920 con escala de Windows 125, 150 y 200 % (`_a_1.25`, `_a_1.5`, `_a_2`, claro).
- `<WxH>/<tema>_<escenario>.png`: cada una de esas pantallas, reducida a 480 px de lado mayor, en 6 tamaños representativos (1600x1200, 1920x1080, 2560x1080, 1200x1600, 1080x1920, 1024x600), claro y oscuro.
- La ventana se pinta de magenta (centinela del criterio «sin barras»): en las capturas de pantallas completas no aparece; solo se ve detrás de los arneses que muestran una sección de Opciones o un teclado solos (en la aplicación siempre van sobre una pantalla con fondo; igual a 1920x1200).
- Se regeneran con `python tests/banco/resp_capturas.py --tamanos ... --temas claro oscuro --destino <dir>` y `python tests/banco/resp_hojas.py <dir> docs/informes/responsive/capturas --lado 480 --hoja 240 --escenarios ...` (conjunto completo: ≈132 escenarios por tamaño).

Revisión automática de las capturas finales (`--analizar`, claro): ninguna pantalla completa con ventana sin cubrir en ningún tamaño ni escala; zonas táctiles bajo 44 px físicos solo la casilla y el enlace del Login (27 px de diseño, iguales a 1920x1200); problemas de texto nuevos respecto al tamaño de diseño: «encogido» de Reportes («576 / 600», permitido), secciones del desplazable de Reportes (contenido fuera de la vista), la leyenda de la gráfica a 1024x600 (residual) y 4 «sale del cuadro» de 1–6 px: Mantenimiento a 1080x1920 (también en dev: el revisor mide contra la tarjeta tapada por el velo), «Atrás» del asistente con el teclado abierto y «0» de un eje en la gráfica a pantalla completa a 1200x1600, «›» de Parámetros del equipo a 600x1024 (estos tres probablemente del mismo tipo, sin revisar a ojo: pendientes). Letra mínima: 6 px físicos a escala física 0,5; 10–11 a 0,8–0,9; 12 a 1.


## Pendiente de banco

- Monitores y escalas reales de la estación (resolución física, 100–200 %), en las dos orientaciones.
- Táctiles reales con las zonas ampliadas a escala física < 1 (solapes entre vecinas).
- Giro del monitor con la aplicación abierta y cambio de monitor (desconectar uno): las pruebas lo simulan cambiando el tamaño de la ventana.
- Dos pantallas con distinta resolución, escala u orientación a la vez.
- Legibilidad de la letra mínima (≈ 6 px físicos a 1024x600).

## Pendiente de decisión / residuales

- **Leyenda de la gráfica** (preexistente, O3): su letra solo baja (`tam` decrece cuando no cabe) y nunca vuelve a subir; tras un giro o cambio de resolución puede quedar con otra letra que abierta de cero, y a 1024x600 queda 1–2 px larga por el redondeo. Corregirlo (reiniciar `tam` al cambiar el espacio) cambiaría la leyenda a 1200x1920 respecto a dev (hoy queda en 14 desde la carga), por eso no se tocó.
- Redondeo de la letra (`Escala.fuente`): a escalas distintas de 1 un texto justo puede quedar 1–2 px más largo que su caja proporcional o bajar 1–2 px con `fontSizeMode`; usar `floor` en lugar de `round` fuera de factor 1 lo evitaría, pero cambia el tamaño de letra en las pruebas existentes a 1024 px de ancho.
- Las del resto del informe marcadas DECISIÓN SIN CONFIRMAR.
