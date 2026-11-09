# Tanda horizontal: informe

Rama `horizontal` desde `dev` (839f7a66), sin merge ni push (el merge lo decide Cristian). Entrega no compilada. Prompt: `docs/mis_plans/prompt_claude_code_horizontal.md`, con la corrección de alcance de Cristian (9-nov): **el vertical no se elimina**; el software soporta las dos orientaciones según la pantalla.

## Resumen

- **Criterio de orientación.** Cada ventana raíz (`Main.qml`, `InstalacionVentana.qml`, `ReposoInstalacionVentana.qml`, `NuevoUsuarioHost.qml`) fija `Escala.horizontal = Escala.esHorizontal(width, height)` (ancho >= alto) sobre su propio tamaño. `app.py` no cambió: pone cada ventana a pantalla completa en el monitor elegido (`setGeometry(pantalla.geometry())` + `showFullScreen`), así que el tamaño de la ventana es el de su monitor tal como lo tiene configurado Windows (orientación incluida). Hay un proceso por pantalla, cada una decide la suya. Si Windows gira el monitor, la ventana a pantalla completa cambia de tamaño y el binding cambia de lienzo en el acto (prueba `tests/test_hor_escala_orientacion.py`: por defecto y con alto > ancho, lienzo 1200x1920 y factor 1; 1920x1200 y 960x600, lienzo 1920x1200; cuadrada, horizontal; al volver a vertical, vertical). Las pruebas que arman su propia ventana no fijan `horizontal` (vale false): siguen verticales.
- **Lienzo.** `Tema/Escala.qml` conserva el vertical (`anchoVertical/altoVertical` 1200/1920) y agrega el horizontal (`anchoHorizontal/altoHorizontal` 1920/1200); `anchoDiseno/altoDiseno` dan el vigente. `factor` y `altoLienzo` mantienen su fórmula. `AreaFija` centra 1920x1200 en horizontal.
- **Vertical intacto.** Toda diferencia de disposición está condicionada a `Escala.horizontal` (ternarios con la expresión original exacta, `Binding ... when`, `State`, o `Grid { columns: Escala.horizontal ? 2 : 1 }` que en vertical da las mismas posiciones que la `Column` que reemplaza). Evidencia: (1) `tests/banco/hor_vertical_igual.py` captura todos los escenarios a 1200x1920 con un worktree de dev y con la rama y compara píxel a píxel (fuera de la franja del reloj): resultado en `vertical_igual.json` (ver «Verificación»); (2) los grupos B y C volcaron además la geometría (x, y, ancho, alto, texto, letra) de cada ítem visible a 1200x1920 en dev y en la rama: idéntica; (3) la suite completa con las pruebas verticales existentes sin modificar ninguna.
- **Mismos px.** Las pantallas que calculaban su escala con el ancho (`width / 1196`) usan en horizontal la del lienzo vertical (`Escala.px(1200) / 1196`): mismas letras, botones, márgenes y colores; solo cambia la disposición.
- **Fuera del QML:** solo `tests/` y `docs/`. Nada en backend, control, alarmas, rutas, controladores, `ui_pyside`, ticket, PDF ni correo. Sin `Canvas`, `Particles` ni `Effects` nuevos; sin colores fuera de `Tema/` (sin colores nuevos).
- **Inventario** de pantallas y componentes con sus medidas verticales y la disposición horizontal: `inventario.md`.

## Commits

- `501a63f2` feat(ui): lienzo horizontal 1920x1200 junto al vertical, elegido por la orientación de la pantalla (base)
- `05ad5093` test(banco): hor_capturas admite escenarios por grupo (hor_escenarios_*.py)
- `f6a1d6d2` test(ui): la orientación del lienzo sigue el tamaño real de la ventana raíz
- `598a6313` feat(ui): Preciclo y Ciclo en curso en horizontal (dos columnas, gráfica a la derecha)
- `a9806c4f` feat(ui): modales, diálogos, panel del equipo y teclados en horizontal
- `04df7ade` feat(ui): Menú principal, Historial, Detalle de ciclo y Reportes en horizontal
- `981a1de7` feat(ui): intro, asistente de instalación y pantallas de sesión en horizontal
- `5fc6035e` feat(ui): Opciones y todas sus secciones en horizontal
- `54a133fb` test(banco): hor_capturas revisa desbordes de tinta (texto y cuadro); inventario horizontal
- `c8115488` fix(ui): sesión y asistente horizontales sin textos cortados y con contraste en oscuro
- `6e0b1d1f` fix(ui): teclado numérico y modales horizontales sin textos montados ni encogidos
- `64fc1016` fix(ui): Preciclo y Ciclo en curso horizontales sin textos fuera de su cuadro y chevrón visible en oscuro
- `4d347f5a` fix(ui): contraste en oscuro de Reportes, calendario e Historial horizontales
- `f03ea458` fix(ui): Opciones horizontal sin textos encogidos y con contraste en oscuro de botones y chips
- `3814b476` docs(horizontal): capturas horizontales (claro y oscuro) y comparación del vertical contra dev
- (cierre) docs(horizontal): informe, estado y CERRADO

## Herramientas nuevas

- `tests/banco/hor_capturas.py`: capturas a 1920x1200 (o el tamaño que se pida) en claro y oscuro, es o en, con revisión automática por escenario: la de `tests/helpers/textos_caben_qml.py` (recortado, encogido, sale del cuadro, cruza divisor, no cabe al mínimo, desborda alto), ítems fuera del lienzo y, desde la ronda 2, `desbordesTexto` (tinta del Text contra su caja, `tinta_ancho`/`tinta_alto`, y contra el Rectangle visible que lo contiene, `sale_del_padre`). Escenarios base en el guion y por grupo en `tests/banco/hor_escenarios_{a..e}.py` (≈130 en total). `--raiz` captura otro árbol (dev) para comparar.
- `tests/banco/hor_vertical_igual.py`: la comparación vertical rama contra dev.
- Pruebas horizontales nuevas (`tests/test_hor_*.py`): orientación; disposición por grupo (A sesión e instalación, B preciclo y ciclo, C menú y reportes, D opciones, E modales y teclado); desbordes de texto en es/en con los textos más largos y contraste WCAG de los pares corregidos (A, B, C, D, E).

## Pruebas existentes

No se modificó ninguna prueba existente (las de layout vertical siguen fijando 1200x1920 y pasan). Lo horizontal se prueba aparte. Los arneses de `qml/Pruebas/` solo ganaron el binding de orientación (con su tamaño vertical por defecto siguen verticales).

## Pantallas cubiertas

Las 26 pantallas de `qml/Pantallas` y los componentes con medidas verticales, con el detalle por pantalla en `inventario.md`:

- **Intro y arranque:** IntroArranque, Reposo (sin cambio: ya recortaba el fondo centrado) y BarraReinicioBackend.
- **Asistente de instalación:** Instalacion, con los 9 pasos más el resultado.
- **Sesión:** Login, CambioClave y NuevoUsuario.
- **Preciclo** (las dos puertas) y **Ciclo en curso**, con PanelFinCiclo, BarraFases, GraficaCiclo, la pantalla completa de la gráfica y el zoom ZOM.
- **Menú principal**, con sus ventanas flotantes (Último ciclo, Mantenimiento, Ciclos hoy, Historial y el Detalle de ciclo) y **Reportes** (dashboard, calendario y panel del día).
- **Opciones** y sus 15 secciones: Parámetros del ciclo y del equipo, Usuarios, Fecha y hora, Información del sistema, Bitácora, Calibración atmosférica y de sensor, Conectividad, Respaldo, Entradas/Salidas, Mantenimiento, Avanzadas, Manejo de ciclos y Reasignación. Bitácora, Avanzadas, Manejo de ciclos y Reasignación no necesitaron cambios de disposición: su contenido toma el ancho.
- **Modales y diálogos:** PanelModal, PanelNotificaciones, PanelEquipo, ModalConfirmacion, ModalOperador, DialogoConfirmacion y VentanaDetalleAlarma.
- **Teclados en pantalla:** PanelTeclado y los teclados alfanumérico y numérico.

En la ronda 2 se agregaron dos pedidos de Cristian: corregir los textos que se salían de su cuadro y los contrastes del modo oscuro. Lo que se hizo está en las secciones siguientes, por grupo.

## Ronda 2a: textos que se salían de su cuadro

Método:
- Revisión automática nueva (`desbordesTexto` en `hor_capturas.py`) de los ≈130 escenarios, en es y en, en claro y oscuro.
- Revisión a ojo de todas las capturas, grupo por grupo.
- Prueba nueva por grupo con los textos más largos en es y en: `test_hor_a_desbordes_contraste.py`, `test_hor_b_textos_contraste_qml.py`, `test_hor_c_textos_contraste.py`, `test_hor_d_desbordes_qml.py` y `test_hor_e_desbordes.py`.

Criterio aplicado:
- Primero bajar la letra con `fontSizeMode` y `minimumPixelSize: Escala.fuenteMinima`, partiendo en líneas donde convenga, sin `elide`.
- Si no alcanzaba, dar más lugar a la caja.
- No hizo falta acortar ningún texto: no se agregó ni se cambió ninguna clave i18n.

Después de las correcciones, la corrida final (es en claro y oscuro, y en en claro) solo deja falsos positivos conocidos:
- «Confirmar cruza divisor 1352»: la tecla del teclado tapa el divisor de la barra que queda debajo.
- `chevronFila` de FilaAcordeon: también aparece en vertical; es el chevrón girado.
- Textos tapados por una capa superpuesta: la pantalla completa de la gráfica, el modal de estado seguro y la leyenda bajo el desplegable «Tiempos».

Los resúmenes de esa corrida están en `capturas/resumen_*.json`.

## Ronda 2b: contraste en modo oscuro

Cumplen la §8 de la paleta: 4,5:1 en texto normal y 3:1 en texto grande y elementos gráficos.

- **Colores:** no se agregó ninguno; se usan tokens que ya existían y que en claro valen lo mismo.
- **Pruebas:** cada par corregido está en una prueba nueva (`test_hor_*_contraste*`, con las funciones de `test_tema_oscuro.py`), y `test_tema_oscuro.py` pasa sin cambios.
- **Vertical oscuro:** todos los pares corregidos son preexistentes allí. Por la regla de Cristian (no cambiar el oscuro vertical), la corrección se aplica solo en horizontal y el vertical queda **pendiente de decisión**. El detalle de cada par, con su razón antes y después, está en las tablas por grupo.

### Grupo A (sesión y asistente)

Textos:
- Asistente, `inst_teclado_clave` (es/en): «INSTALACIÓN DEL EQUIPO» / «EQUIPMENT INSTALLATION», el indicador de pasos y «Paso 8 de 9 · Contraseñas» / «Step 8 of 9 · Passwords» se veían cortados al subir la página sobre el teclado (los recortaba el contenedor). Ahora `tituloInstalacion`, `indicadorPasos` y `subtituloPaso` se ocultan (opacidad 0) mientras la página está subida (en vertical el desplazamiento vale 0). Sin reducción ni texto corto.
- Resto (es/en, claro/oscuro, revisión automática y a ojo): sin desbordes. Queda el falso positivo «Confirmar / Confirm cruza divisor 1352» (divisor de la barra flotante bajo el teclado).

Contraste (preexistente en el vertical oscuro, pendiente de decisión: en vertical los recuadros siguen sin `color`, blancos también en oscuro; en horizontal se aplica con `Binding on color { when: raiz.hz }`; en claro el valor es el mismo #FFFFFF):

| Pantalla y elemento | Fondo oscuro antes → después | Texto | Razón antes → después |
|---|---|---|---|
| NuevoUsuario: recuadros de los 4 campos | #FFFFFF → `fondoCampo` #1E2A38 | `textoPrimario` #E9EEF4 | 1,16 → 12,3 |
| NuevoUsuario: recuadros de los 4 campos (guía) | #FFFFFF → `fondoCampo` | `textoGuia` #8C98A7 | 2,9 → 5,0 |
| NuevoUsuario: recuadro y lista de Rol | #FFFFFF → `fondoCampo` | `textoPrimario` | 1,16 → 12,3 |
| NuevoUsuario: botón Cancelar | #FFFFFF → `fondoTarjeta` #152130 | `textoPrimario` | 1,16 → 13,6 |
| CambioClave: recuadros de los 3 campos | #FFFFFF → `fondoCampo` | `textoPrimario` | 1,16 → 12,3 |

Prueba: `tests/test_hor_a_desbordes_contraste.py` (Login con ayuda y aviso sin base de datos, CambioClave, NuevoUsuario y los 9 pasos del asistente más el resultado, con datos largos, es/en, claro/oscuro: tinta dentro de la caja y de la ventana; colores de los recuadros en oscuro y blancos en claro; WCAG con las funciones de test_tema_oscuro). `hor_vertical_igual` igual en los 12 escenarios afectados; 277 pruebas pasan.

### Grupo B (Preciclo y Ciclo en curso)

Textos (condicionado a `Escala.horizontal`):
- Preciclo, botón RECONOCER FALLA / ACKNOWLEDGE FAULT: en inglés no cabía ni al mínimo (caja 156, tinta 165); en español solo bajaba la letra. Más lugar: en horizontal el botón crece 100 px hacia la izquierda (`caja [745,1616,402,110]`, `textoX` 880, `circuloX` 766; en FALLA el deslizador de inicio no se muestra, no se pisan). Cabe a 17 px en los dos idiomas.
- Nombre del programa en Preciclo y Ciclo en curso (es/en): un nombre largo cruzaba los divisores del recuadro «Programa» (uno de 48 caracteres no cabía en una línea ni al mínimo). En horizontal va en hasta 2 líneas con la letra ajustada al recuadro (464 x 84), sin bajar del mínimo y sin `elide`, aplicado con `Binding … when: raiz.hz` (un primer intento con ternarios movía el nombre en vertical: lo detectó `hor_vertical_igual`). Un nombre corto se ve igual.
- Sin claves i18n nuevas. Falsos positivos que quedan: «Pressure» en b_ciclo_tiempos (leyenda bajo el desplegable abierto); «kPa», «35», «10», «Time (min)» en pantalla completa y «Volver/Back» bajo el modal (tapados por la capa superior); `chevronFila` (igual en vertical).

Contraste:

| Pantalla y elemento | Antes (oscuro) | Después | Razón antes → después |
|---|---|---|---|
| Gráfica, chevrón del botón «Tiempos» | `Image` de relleno negro sobre `fondoTarjeta` #152130 | `IconoColor` (`chevronTiempos`) con `Colores.textoNegro` (#E9EEF4 en oscuro; negro en claro) | 1,29 → 13,9 |

Preexistente en el vertical oscuro, pendiente de decisión (el vertical no se tocó). Resto de pares revisados (fases pendientes 4,69, `textoGuia` 5,54, indicador de entrega, píldoras, barra): cumplen.

Prueba: `tests/test_hor_b_textos_contraste_qml.py` (es/en, fuentes reales: ningún texto de Preciclo en FALLA ni de Ciclo en curso pasa su caja; RECONOCER FALLA cabe; el programa largo queda entre los divisores; chevrón ≥ 3:1 en oscuro y negro en claro; fallaba antes de las correcciones). 759 pruebas de estas pantallas pasan. `hor_vertical_igual`: estáticos idénticos (difieren solo los animados); volcado de geometría a 1200x1920 contra dev idéntico salvo la hora.

### Grupo C (Menú, Historial, Reportes)

Textos:
- Ventana de Mantenimiento («PRÓXIMO MANTENIMIENTO» / «NEXT MAINTENANCE») y CERRAR / CLOSE del panel «Ver todas» de alarmas: no se salían; el revisor los medía contra la tarjeta o el divisor que quedan detrás del velo. En horizontal la tarjeta de `VentanaFlotante.qml` y la de `ListaAlarmasPeriodo.qml` llevan `clip: Escala.horizontal` (todo su contenido cabe: sin cambio visible).
- Reportes, vista Año, en inglés: «No data from the previous period» baja de 16 a ≈15 px (`HorizontalFit` con mínimo, paso a), no se recorta.
- Ningún `tinta_ancho`, `tinta_alto`, `sale_del_padre`, `no_cabe_al_minimo` ni `desborda_alto`; revisión a ojo es/en, claro/oscuro.

Contraste (oscuro, solo horizontal; sin colores nuevos, tokens existentes):

| Pantalla y elemento | Antes (oscuro) | Ahora (oscuro) | Claro |
|---|---|---|---|
| Reportes, ícono Inicio (`Image` → `IconoColor`) | trazo #231F20 sobre #152130, ≈1,1 | `iconoBarraMenu` #E9EEF4, ≈14 | #231F20, igual |
| Reportes, ícono Salir (`Image` → `IconoColor`) | trazo #000 sobre #152130, ≈1,1 | `textoNegro` #E9EEF4, ≈14 | #000000, igual |
| Calendario, borde punteado «Sin operación» y borde «No ejecutado» (`MesMiniatura.colorTema`, `bordeCampo`) | `bordeCampo` #33445A sobre #152130, ≈1,6 | `iconoCampo` #8C98A7, ≈6 | #CCCCCC, igual |
| Historial, casillas de marcar (`ListaCiclos`) | `bordeDivisor` #2A3746 sobre #152130, ≈1,3 | `iconoCampo` #8C98A7, ≈6 | en horizontal pasa de #E6E6E6 a #CCCCCC (un poco más oscuro); el vertical claro no cambia |

Las cuatro son preexistentes en el vertical oscuro, pendientes de decisión (no se tocaron en vertical).

Prueba: `tests/test_hor_c_textos_contraste.py` (9: es/en a 1920x1200, sin elide y tinta dentro de la caja en Menú, sus 4 ventanas, el detalle de Ciclos hoy e Historial y Reportes recorrido entero en mes, día, año, ciclo abierto y fallo; íconos pintados; WCAG antes bajo el mínimo y después sobre él, claro igual). `hor_vertical_igual`: igual en los 19 escenarios; 168 pruebas existentes pasan.

### Grupo D (Opciones)

Textos (por ajuste de línea; sin textos cortos ni claves nuevas):
- Entradas/Salidas, nombres de canal en las tarjetas de 3 por fila (es: «Descompresión chaqueta», «Aire atmosférico cámara», «Atrapamiento puerta 1»...; en: «Jacket decompression», «Chamber atmospheric air», «Heat exchanger water»...): la letra se achicaba hasta un 22 %. En horizontal el nombre pasa a dos líneas a tamaño completo (`wrapMode: WordWrap`, `fontSizeMode: FixedSize`). Detalle: «Desbloqueo puerta 1» deja el «1» solo en la segunda línea.
- Parámetros del equipo › Chaqueta, títulos de fila («Tiempo límite de aislamiento de cámara», «Aislamientos de cámara permitidos»): en horizontal el título ocupa el 64 % de la fila (antes 60 %; el valor baja de 36 % a 30 %) y pasa a dos líneas.

Contraste (oscuro, solo horizontal): el texto blanco (`textoSobreAccion`) sobre rellenos que en oscuro son claros pasa a `Colores.fondoTarjeta` (blanco en claro: claro idéntico; #152130 en oscuro):

| Pantalla | Elemento | Relleno | Antes → después |
|---|---|---|---|
| Calibración atmosférica | Cancelar | `peligroTexto` | 2,78 → 5,86 |
| Calibración atmosférica | Descartar | `textoSecundario` | 2,13 → 7,63 |
| Calibración de sensor | Restaurar último / por defecto | `menuNaranja` | 2,04 → 7,95 |
| Entradas/Salidas | Salir del modo prueba, botón de apagar | `peligroTexto` | 2,78 → 5,86 |
| Reasignación | Descartar | `textoSecundario` | 2,13 → 7,63 |
| Reasignación | Restaurar fábrica | `menuNaranja` | 2,04 → 7,95 |
| Reasignación | Aplicar | `peligroTexto` | 2,78 → 5,86 |
| Respaldo | chip «Válido» | `menuVerde` | 2,27 → 7,16 |

Preexistentes en el vertical oscuro (siguen en blanco), pendientes de decisión. También preexistente en claro: blanco sobre `menuNaranja` da 2,17 (no se tocó: el claro debe quedar igual a dev). Sin colores nuevos (test_tema_oscuro exige el origen de cada color nuevo en sus tablas). Se dejaron: blanco sobre `accionPrimario` oscuro (3,24, vale para texto de 24 px o más) y deshabilitados (opacidad 0,4, fuera de WCAG).

`hor_escenarios_d.py`: el doble responde `/language`, `/theme`, `/units` y `/printer/config` (sin eso los selectores de Configuración de la máquina salían deshabilitados: defecto del doble, no de la pantalla).

Pruebas: `tests/test_hor_d_desbordes_qml.py` (Opciones con datos en horizontal, es/en, 17 vistas: tinta dentro del ancho y del alto de su caja) y `tests/test_hor_d_contraste.py` (WCAG de cada par y claro sin cambio). `hor_vertical_igual` en los 34 escenarios del grupo y las 6 secciones sueltas: idénticos salvo d_fecha_hora (reloj con segundos). 26 archivos de pruebas existentes: 740 pasan.

### Grupo E (modales y teclados)

Textos (condicionado a `Escala.horizontal`):
- Teclado numérico con el valor vacío (es/en): la unidad («°C», «kPa»), alineada a la línea base del valor, se montaba sobre «Rango: …». En horizontal el valor muestra un espacio cuando está vacío (preexistente en el vertical, pendiente de decisión). `TecladoNumerico.qml`.
- Botón de acción de `ModalConfirmacion` (en): «Confirm without safe conditions» se encogía (caja 431 contra 433). En horizontal el relleno pasa de 32 a 64 (más lugar, sin reducir); igual en `ModalOperador.qml`.
- Sin textos cortos ni claves i18n nuevas. Queda el falso positivo `cruza_divisor 1352` en CONFIRMAR.

Contraste: ningún par de los modales, paneles y teclados bajo su mínimo; nada corregido. Observaciones: texto blanco sobre `accionPrimario` oscuro da 3,24 (vale como texto grande, 26 px SemiBold); filas de ModalOperador en oscuro: `fondoSutil` contra la tarjeta 1,01 (en claro 1,08), la fila se reconoce por su texto, que cumple; preexistente en el vertical, pendiente de decisión (un borde de fila de 3:1 pediría un color nuevo).

Pruebas: `tests/test_hor_e_desbordes.py` (ModalConfirmacion forzada, ModalOperador con nombre largo, DialogoConfirmacion de apagado con cámara no segura, PanelEquipo con 17 filas y mensajes de apagado, PanelNotificaciones, VentanaDetalleAlarma con textos largos y los dos teclados, es/en: tinta dentro de su caja y de su recuadro; textos del encabezado del teclado sin solaparse; falla sin el arreglo del numérico) y `tests/test_hor_e_contraste.py` (11 pares en oscuro con su mínimo WCAG). `hor_vertical_igual`: ninguno distinto; 223 pruebas pasan.

## Verificación

**Suite completa** (`pytest tests -n 8`): 12404 pasan, 16 fallan, 11 saltadas y 15 xfail.
- Las 16 fallas son las mismas que en `dev` (839f7a66, misma corrida: 12310 pasan, 16 fallan) y ninguna es de la interfaz:
  - test_c2_programas_persistentes
  - test_q1_r1p3_rango_calentamiento::test_hay_10_perfiles
  - test_t12_c07_c13_json::test_son_los_10_programas
  - test_t12_v12_ventana_referencia_en_cero (×3)
  - test_t17_copia_programa[estabilizacion]
  - test_t29_descompresion_fin_modo_solido (×6)
  - test_t28_a14_m3_brecha (×2)
  - test_v8b_textos::test_descripciones_citan_nombres_visibles_de_parametros
- Las 94 pruebas de más que pasan son las horizontales nuevas.
- En una corrida intermedia falló una vez `test_t26_arq_retencion::test_main_con_espera_no_arranca_al_escuchar` (SystemExit 75, puerto del backend ocupado con 8 procesos en paralelo). Pasó sola y en la corrida final; la rama no toca el backend.

**Efecto lateral preexistente:** la suite reescribe `src/autoclave/cycles/user/*.json` (marcas de migración `migrado_t28_m3`/`migrado_cri`) y deja `.bak` y `fabrica_vistos.lst` ignorados. Esos archivos se restauraron y no van en ningún commit.

**Vertical idéntico:** `vertical_igual.json` compara 132 escenarios a 1200x1920, rama contra dev.
- 117 salen idénticos píxel a píxel.
- Los 15 distintos tienen animación o reloj (intro, reposo, ciclo en curso animado, brillo del deslizador, reloj con segundos de Fecha y hora). `vertical_dev_contra_dev.json` muestra que esos mismos 15 también difieren entre dos corridas de dev contra sí mismo, así que la diferencia no viene de la rama.
- Además, los grupos B y C compararon la geometría ítem por ítem a 1200x1920 en dev y en la rama: idéntica.

**Capturas:** `capturas/` trae 48 pantallas y estados en claro y oscuro (96 PNG a 1920x1200). El conjunto completo, ≈130 escenarios en es/en y claro/oscuro, se regenera con `python tests/banco/hor_capturas.py --temas claro oscuro [--idioma en]`.

## Cambios de estructura en vertical sin efecto visible (para revisión)

Para no duplicar lógica, algunos contenedores cambiaron de tipo. En vertical dan las mismas posiciones, comprobado con capturas y pruebas:

| Pantalla | Antes | Ahora |
|---|---|---|
| Login, CambioClave | Columna con un espaciador de 60 | GridLayout de 1 columna con rowSpacing 60 |
| Instalacion | Página directa; tres `Column` | Página dentro de un Item con Translate 0; las tres `Column` pasan a `Grid` de 1 columna |
| DetalleCiclo | Fila de datos en `Row` | `Grid` (4 columnas en vertical) |
| Reportes | Columna | `Grid` (1 columna en vertical) |
| Opciones: riel | `Column` | `Grid` de 1 columna |
| Opciones: parámetros del ciclo | `ListView` | `GridView` con celda del mismo alto |
| Opciones: temperatura y presión de E/S | `Column` | `Flow` |
| Opciones: ventanas de ajuste | Columna directa | Columna dentro de un `Flickable` (en vertical no desplaza) |
| PanelEquipo | Fila de `ListView` | Componente en línea `FilaEquipo`, compartido con la vista en dos columnas |

## DECISIÓN SIN CONFIRMAR

**Criterio de orientación**
- Una pantalla cuadrada (ancho = alto) se toma como horizontal.
- NuevoUsuarioHost, el QQuickWidget de AutoclaveSettings (ui_pyside, que no se tocó), sigue la misma regla: si ese widget es más ancho que alto, ahora muestra la disposición horizontal de NuevoUsuario.

**Ciclo en curso**
- La gráfica queda angosta: ≈687 px de ancho y ≈496 de trazado, más alta que en vertical. Para verla grande está la pantalla completa, a todo el ancho.
- Alternativa: dar a la gráfica su ancho natural (1129) y rehacer la columna izquierda en ≈700 px. Daría ≈1060 de alto y no cabe en 848.
- La píldora de fin de ciclo va en la columna izquierda.

**Preciclo**
- Queda un hueco entre los parámetros (y 633) y los botones (y 894), porque los botones siguen sobre la barra como en vertical. Opción: subirlos bajo los parámetros.
- RECONOCER FALLA gana 100 px de ancho en horizontal.
- El nombre de programa largo va en hasta 2 líneas.

**Menú y Reportes**
- El reparto de columnas de Reportes.
- La ventana de Mantenimiento centrada a 1128.
- Historial y Ciclos hoy siguen cambiando el listado por el detalle, como en vertical: no se ponen lado a lado.

**Opciones**
- El riel plegado va en dos columnas de iconos, en lugar de un panel fijo con nombres: con nombres, 11 entradas no caben en 698 de alto.
- Conectividad queda en 60/40 por el detalle de FilaInterruptor.
- En E/S, los nombres de canal pasan a dos líneas («Desbloqueo puerta 1» deja el «1» solo en la segunda).

**Sesión e instalación**
- NuevoUsuario en 3 columnas, con campos de 449 en lugar de 707.
- Login con márgenes de 40 y 20.
- En la activación, serie y código en la misma fila.
- El resumen en 2 columnas.
- La página del asistente sube sobre el teclado, y mientras está subida se ocultan el título y el paso.

**Teclado**
- En horizontal el margen de arriba y abajo baja de 24 a 9 para cumplir TEC-D06 (45 %) sin achicar teclas. Alternativa: relajar al ≈47,5 % solo en horizontal.
- El encabezado queda pegado a la izquierda. Opción: alinearlo junto a las teclas.

**Modales**
- ModalOperador queda en una columna con desplazamiento.
- PanelEquipo va en dos columnas: los valores muy largos bajan de letra.

**Contraste**
- Todos los pares corregidos se corrigieron solo en horizontal. En el vertical oscuro siguen igual, pendientes de decisión:
  - campos de NuevoUsuario y CambioClave
  - chevrón de «Tiempos»
  - íconos de la barra de Reportes
  - bordes del calendario
  - casillas del Historial
  - 8 botones y chips de Opciones con texto blanco sobre relleno claro
  - valor vacío del teclado numérico
- En las casillas del Historial, el horizontal claro pasa de #E6E6E6 a #CCCCCC (el vertical claro no cambia).
- Siguen abiertos, igual en vertical:
  - blanco sobre `menuNaranja` en claro, 2,17:1
  - blanco sobre `accionPrimario` en oscuro, 3,24:1; vale solo como texto grande
  - filas de ModalOperador contra la tarjeta, 1,01:1, que se reconocen por su texto

## No cupo sin desplazar

- La segunda fila de grupos de Información del sistema. Opción: columnas tipo mampostería.
- Reportes: es un desplazable largo, como en vertical.
- Ventanas de ajuste de Parámetros: desplazables.

## Sin verificar

- El resumen del asistente en modo automatización con las 16 filas: el arnés `Pruebas/PruebaInstalacion.qml` no trae `calcularModelo` ni `normalizarOriginal`. Estimado en ≈576 de ≈607 de alto útil.

## Pendiente de banco

- Orientación física del monitor y su rotación en Windows: comprobar que, al girar el monitor con la aplicación abierta, la ventana a pantalla completa cambia de tamaño y la disposición la sigue, en las dos pantallas.
- Táctiles reales en horizontal, contando la asociación de táctiles del paso 06 con el monitor girado.
- Gesto de dos dedos y cursor del zoom sobre la gráfica angosta de Ciclo en curso y sobre la del detalle.
- Teclado sobre los campos de Login, CambioClave, NuevoUsuario, el asistente y las ventanas de ajuste.
- Botones de la columna de datos del detalle de ciclo.
- Desplazamiento de las ventanas de ajuste.
- Legibilidad de la leyenda de la gráfica, que baja a ≈16 px con nombres largos.
- La intro en el monitor girado.
