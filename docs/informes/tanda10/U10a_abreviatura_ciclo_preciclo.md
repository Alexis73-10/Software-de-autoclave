# U10a — Abreviatura automática en Ciclo y Preciclo (D10-1.1, 1.2, 1.3 y 1.5)

Rama `tanda-10-u10a`, desde `tanda-10` (f73acf6, contiene e391ffe). Sin push.
Revierte en parte D8-5.4: solo las claves de la sección `abrev` pueden abreviar.

## Qué se hizo, por punto

| Punto | Estado |
|---|---|
| D10-1.1 componente | Hecho: `src/autoclave/ui_qml/qml/Componentes/TextoAjustable.qml` |
| D10-1.2 convención de claves | Hecho: sección `abrev.*` con la misma ruta que el texto completo; `test_v8b_textos.py` ajustado |
| D10-1.3 tarjeta de parámetros y sensores | Hecho en `PantallaPreciclo.qml` y `PantallaCicloEnCurso.qml` (las 3 etiquetas de parámetros y las 9 `ciclo.entrada_corta_*`) |
| D10-1.5 prueba (estas dos pantallas) | Hecho: `tests/test_u10a_textos_caben_qml.py` sobre la revisión genérica `tests/textos_caben_qml.py` |
| Capturas antes/después | Hecho: 24 PNG en `docs/informes/tanda10/capturas/u10a/` |

### D10-1.1 `TextoAjustable.qml`

Es un `Text` de una línea (sin `elide` ni `maximumLineCount`) con:

- `textoCompleto`, `textoAbreviado`, `anchoDisponible` (px reales de la pantalla);
- o, en vez de los dos textos, `clave`: toma el completo de `<clave>` y el abreviado de
  `abrev.<clave>` si existe (`I18n.existe`); sin abreviatura, siempre muestra el completo;
- mide el completo con `TextMetrics` (misma fuente) y muestra el abreviado solo si el completo
  supera `anchoDisponible`;
- expone `anchoCompleto`, `usaAbreviado` y `desborda` (= lo mostrado, completo o abreviado,
  no cabe). `desborda` no recorta nada: lo detecta la prueba.

Uso para U10b: `TextoAjustable { clave: "seccion.clave"; anchoDisponible: <px>; font...; x; y }`.
No fija `width` (el ancho del ítem es el del texto mostrado).

### D10-1.2 Convención: sección `abrev`

`abrev.<ruta del texto completo>`, p. ej. `abrev.ciclo.temp_ester` ↔ `ciclo.temp_ester`.
Por qué esta y no `<seccion>.<clave>_abrev`:

1. un solo prefijo exento de D8-5.4 (igual que `ticket_ciclo.`), sin listas de excepciones;
2. la clave completa se obtiene quitando `abrev.`, así la prueba exige mecánicamente que exista;
3. el componente la deriva de `clave` sin que cada pantalla nombre dos claves;
4. no se confunde con claves reales que terminen en `_abrev` (la prueba prohíbe cualquier otra
   forma de `abrev` en el catálogo).

La sección va en es.json y en.json justo antes de `ticket_ciclo` (no al final, donde otras
ramas agregan secciones, para reducir choques al unir).

`tests/test_v8b_textos.py`:
- `_PREFIJOS_CON_ABREVIATURAS = ("ticket_ciclo.", "abrev.")`: las dos pruebas de abreviaturas
  de D8-5.4 eximen esas claves; el resto del catálogo sigue con D8-5.4 igual;
- nuevo `test_toda_abreviatura_tiene_su_texto_completo[es|en]`: cada `abrev.X` no vacía,
  `X` existe como texto en ese idioma y la abreviatura no es más larga que el completo;
- nuevo `test_las_abreviaturas_usan_una_sola_convencion`.

`tests/test_i18n.py`: familia dinámica `"abrev."` (el componente arma `"abrev." + clave`).

### D10-1.3 Tarjeta de parámetros y sensores

En las dos pantallas el componente interno `Etiqueta` pasa a ser un `TextoAjustable` con
`lx`, `bl` y `limite` (x del divisor derecho de su columna, px del mockup):
`anchoDisponible = m(limite - lx - margenEtiqueta)`, con `margenEtiqueta = 4` px del mockup.
Límites: 222.2, 410.3, 598.5 y `c0 + 188.2` para las entradas (c0 = 598.5, 786.7, 974.8;
la última termina en el borde de la tarjeta, 1163). No cambió ninguna posición ni tamaño de
fuente. Las propiedades `textos.tempEster/tiempoEst/tiempoSec` quedan declaradas pero ya no las
usa la tarjeta (se dejaron para no tocar más de lo necesario).

### D10-1.5 Prueba automática

`tests/textos_caben_qml.py` (no la recoge pytest) carga una pantalla sola, offscreen, en un
subproceso, con un puente falso y en el idioma pedido, y recorre TODOS los `Text` visibles sin
conocer la pantalla. Falla un texto si:

1. `abreviatura_no_cabe`: es un `TextoAjustable` y lo mostrado (`implicitWidth`) supera su
   `anchoDisponible`;
2. `desborda_su_caja`: `Text` sin ajuste de línea, sin elide y sin reducción de fuente con
   `implicitWidth > width`;
3. `sale_del_cuadro`: su tinta se sale del `Rectangle` visible más pequeño que contiene su punto
   de inicio (aunque sea hermano y no padre, como en estas tarjetas);
4. `cruza_divisor`: su tinta cruza una línea vertical visible (Rectangle de 4 px o menos de ancho).

`tests/test_u10a_textos_caben_qml.py`: Preciclo y Ciclo × es/en × 1024x1638 (resolución del
banco CAP9) y 1200x1920 (lienzo), con valores de longitud real (134.0, 3.5, 15, 134.2, -100.0)
y las 9 entradas en 3 pasos de 3. Comprueba: sin avisos QML, ningún problema de los 4 tipos,
6 etiquetas ajustables por paso, completo si cabe / abreviado si no, y las 12 etiquetas
recorridas. Más una prueba del componente solo (completo, abreviado, `desborda` con y sin
abreviatura, y por `clave`).

Antes del cambio la revisión genérica encontraba 17 problemas en es y 10 en en por pantalla
(a 1024 px), todos en la tarjeta (`cruza_divisor` y `sale_del_cuadro`); nada fuera de ella.

Para U10b: agregar casos (pantalla, puente, pasos) a esa revisión; `revisar()` ya devuelve
`ajustables` (completo, abreviado, mostrado, anchos) para armar la tabla del informe, y
`tests/u10a_capturas.py` muestra cómo capturar con los mismos pasos.

## Tabla de textos abreviados

Iguales en Preciclo y Ciclo en curso (misma geometría). "Se abrevia" = en las dos resoluciones
probadas, salvo donde se indica. Anchos en px a 1200 (completo / disponible).

| Pantalla | Clave | Idioma | Completo | Abreviado | ¿Se abrevia? |
|---|---|---|---|---|---|
| Preciclo, Ciclo | `ciclo.temp_ester` | es | Temperatura de esterilización | Temp. ester. | Sí (178 / 103) |
| Preciclo, Ciclo | `ciclo.temp_ester` | en | Sterilization temperature | Steril. temp. | Sí (151 / 103) |
| Preciclo, Ciclo | `ciclo.tiempo_est` | es | Tiempo de esterilización | Tiempo ester. | Sí (145 / 97) |
| Preciclo, Ciclo | `ciclo.tiempo_est` | en | Sterilization time | Steril. time | Sí (102 / 97) |
| Preciclo, Ciclo | `ciclo.tiempo_sec` | es | Tiempo de secado | Tiempo secado | Sí (110 / 101) |
| Preciclo, Ciclo | `ciclo.tiempo_sec` | en | Drying time | Drying time | No (cabe; abreviatura = completo) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_camara` | es | Temperatura de cámara | Temp. cámara | Sí (146 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_camara` | en | Chamber temperature | Chamber temp. | Sí (137 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_2_camara` | es | Temperatura de cámara 2 | Temp. cámara 2 | Sí (156 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_2_camara` | en | Chamber temperature 2 | Chamber temp. 2 | Sí (147 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_referencia` | es | Temperatura de referencia | Temp. referencia | Sí (160 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_referencia` | en | Reference temperature | Reference temp. | Sí (141 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_drenaje` | es | Temperatura de drenaje | Temp. drenaje | Sí (146 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_drenaje` | en | Drain temperature | Drain temp. | Sí (113 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_drenaje_camara` | es | Temperatura de drenaje de cámara | Temp. dren. cám. | Sí (213 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_temp_drenaje_camara` | en | Chamber drain temperature | Chbr. drain temp. | Sí (171 / 111) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_camara` | es / en | Presión / Pressure | (sin abreviatura) | No (cabe) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_chaqueta` | es | Presión de chaqueta | Pres. chaq. | Sí (124 / 85) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_chaqueta` | en | Jacket pressure | Jacket press. | Sí (94 / 85) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_empaque_1` | es | Presión de empaque 1 | Pres. emp. 1 | Sí (133 / 85) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_empaque_1` | en | Gasket pressure 1 | Gskt. press. 1 | Sí (104 / 85) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_empaque_2` | es | Presión de empaque 2 | Pres. emp. 2 | Sí (135 / 85) |
| Preciclo, Ciclo | `ciclo.entrada_corta_pres_empaque_2` | en | Gasket pressure 2 | Gskt. press. 2 | Sí (106 / 85) |

El abreviado más justo: «Chbr. drain temp.» (106 / 111 a 1200; 91 / 94.7 a 1024).

## Capturas

`docs/informes/tanda10/capturas/u10a/U10a_<antes|despues>_<Preciclo|Ciclo>_<es|en>_grupo<1-3>.png`,
1024x1638 (banco CAP9), 24 en total. Grupo 1: cámara, cámara 2, referencia; grupo 2: drenaje,
drenaje de cámara, presión; grupo 3: chaqueta, empaque 1, empaque 2. Regenerar con
`PYTHONPATH=<worktree>/src python -X utf8 tests/u10a_capturas.py <antes|despues>`
(las de «antes» se tomaron sobre 6ac482c con las pantallas aún sin cambiar).

## Commits

- `6ac482c` feat(tanda10-u10a): TextoAjustable y sección abrev del catálogo (D10-1.1, D10-1.2)
- (siguiente) feat(tanda10-u10a): tarjeta de Preciclo y Ciclo con TextoAjustable y prueba D10-1.5,
  capturas e informe

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a2244476aed3f12f6\src\autoclave\__init__.py`
(PYTHONPATH al `src` del worktree).

| Prueba | Resultado |
|---|---|
| `tests/test_u10a_textos_caben_qml.py` (nueva) | 41 passed |
| `tests/test_v8b_textos.py` + `tests/test_i18n.py` | 90 passed |
| `tests/test_o3_entradas_mostradas_qml.py` (ajustada, ver abajo) | 9 passed |
| `test_o3_entradas_mostradas.py`, `test_pantalla_ciclo_en_curso_qml.py`, `test_pantalla_ciclo.py`, `test_b1_barra_preciclo_ciclo_qml.py`, `test_s2b_d8_2_15_textos_catalogo_qml.py`, `test_s2b_d8_2_16_carga_no_esteril_qml.py`, `test_cancelacion_ciclo_en_curso_qml.py`, `test_navegacion_ciclo_en_curso.py`, `test_t7_avisos_qml.py`, `test_t2_p6_dialogo_estado_seguro.py`, `test_s9_login_y_causa_qml.py` | 90 passed (con O3 antes de ajustarla: 3 fallos esperados, ver abajo) |
| `test_main_menu_principal_qml.py`, `test_navegacion_sesion_qml.py`, `test_u1_seguridad_navegacion_qml.py`, `test_u2_navegacion_qml.py`, `test_n8_cerrar_sesion_qml.py`, `test_b6_selector_ciclo_ui.py` | 36 passed |

`test_o3_entradas_mostradas_qml.py` esperaba las etiquetas completas a 1200 px
(«Temperatura de cámara», «Presión de chaqueta»...), que ahora no caben y salen abreviadas;
se cambió a las abreviaturas. No se corrió la suite completa (regla 8 del brief).

## DECISIONES SIN CONFIRMAR

1. Convención `abrev.<ruta completa>` (razones arriba).
2. Margen de 4 px del mockup antes del divisor (el divisor mide 2 px centrados en `cx`).
3. Abreviaturas distintas de las sugeridas en D10-1.3, porque las sugeridas no caben o porque
   cabe una más clara: es «Temp. referencia» (en vez de «Temp. ref.»), «Temp. dren. cám.»
   («Temp. dren. cámara» mide 121 > 111), «Pres. chaq.» («Pres. chaqueta» 90 > 85),
   «Pres. emp. 1/2» («Pres. empaque 1» 99 > 85); en «Reference temp.» (en vez de «Ref. temp.»),
   «Chamber temp. 2», «Chbr. drain temp.» (sin sugerencia; «Chamber drain temp.» 130 > 111),
   «Gskt. press. 1/2» («Gasket press. 1» 87 > 85).
4. `ciclo.entrada_corta_pres_camara` sin abreviatura (cabe en todas las resoluciones). En inglés
   `abrev.ciclo.tiempo_sec` = «Drying time», igual al completo, porque las claves deben existir en
   los dos idiomas.
5. Se probaron 1024x1638 y 1200x1920. Como `fuente()` redondea el tamaño de letra a entero, a
   otros anchos la proporción texto/columna cambia un poco; si el equipo tiene otra resolución,
   agregarla a `RESOLUCIONES` en `tests/textos_caben_qml.py`.

## PREGUNTAS PARA CRISTIAN

- ¿Son aceptables «Chbr.» y «Gskt.» en inglés? La alternativa es mover la etiqueta de presión
  (hoy empieza 26 px más a la derecha que la de temperatura por el icono) para ganar ancho, lo que
  cambia el diseño del mockup.

## Pendientes (U10b)

- Barrido de las demás pantallas (D10-1.4) con `tests/textos_caben_qml.py`, incluidos la fila
  CIC-10 de la tarjeta de alarmas de Preciclo y la traducción de sus filas (no se tocó).

## Puntos de choque

`src/autoclave/i18n/es.json` y `en.json` (sección nueva `abrev`, antes de `ticket_ciclo`),
`tests/test_v8b_textos.py`, `tests/test_i18n.py` (familia `abrev.`),
`PantallaPreciclo.qml`, `PantallaCicloEnCurso.qml`, `tests/test_o3_entradas_mostradas_qml.py`.
Sin cambios en `app.py`, `doble_pantalla.py`, lógica de ciclo, puertas ni estado seguro.
