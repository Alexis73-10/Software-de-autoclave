# Tanda responsive: diagnóstico

Diagnóstico del paso 1, hecho sobre el árbol de `dev` (worktree desligado en `b7f969f8`, que para la interfaz es igual a d89577eb: dev solo sumó la versión) **antes de editar código**. Herramienta: `tests/banco/resp_capturas.py`, que reutiliza los ≈150 escenarios de la tanda horizontal (`hor_capturas.py` y `hor_escenarios_*.py`) y les agrega tres revisiones (zonas táctiles en px físicos, letra mínima en px físicos y rectángulo del lienzo). Las pantallas de alto fijo se cargan dentro de `AreaFija`, como en `Main.qml` (el guion horizontal las ponía directo en el lienzo, lo que solo da lo mismo cuando el lienzo mide exactamente el de diseño).

## Tabla por tamaño (dev, 100 %, ≈150 escenarios en tema claro)

Columnas: factor de `Escala`; rectángulo del lienzo dentro de la ventana; franjas que dejaba la regla de dev; problemas de texto (recortado, encogido, sale del cuadro, cruza divisor, desborda) o ítems fuera de la ventana que el MISMO escenario no tiene en el tamaño de diseño de su orientación (1920x1200 o 1200x1920: los de diseño son falsos positivos conocidos de la tanda horizontal); zonas táctiles visibles y habilitadas con el lado menor bajo 44 px físicos (suma por escenario); letra visible más chica.
| Tamaño (físico, 100 %) | Factor | Lienzo en la ventana (x, y, ancho, alto) | Franjas | Problemas de texto o «fuera» nuevos | Zonas táctiles < 44 px físicos | Letra mínima (px físicos) |
|---|---|---|---|---|---|---|
| 1024x600 | 0.500 | [32.0, 0.0, 960.0, 600.0] | laterales de 32 px | 14 | 263 | 6 |
| 1280x720 | 0.600 | [64.0, 0.0, 1152.0, 720.0] | laterales de 64 px | 9 | 138 | 7 |
| 1366x768 | 0.640 | [69.0, 0.0, 1228.8, 768.0] | laterales de 69 px | 16 | 98 | 8 |
| 1440x900 | 0.750 | [0.0, 0.0, 1440.0, 900.0] | no | 4 | 34 | 9 |
| 1600x900 | 0.750 | [80.0, 0.0, 1440.0, 900.0] | laterales de 80 px | 4 | 34 | 9 |
| 1920x1080 | 0.900 | [96.0, 0.0, 1728.0, 1080.0] | laterales de 96 px | 0 | 11 | 11 |
| 1920x1200 | 1.000 | [0.0, 0.0, 1920.0, 1200.0] | no | 0 | 10 | 12 |
| 2560x1440 | 1.200 | [128.0, 0.0, 2304.0, 1440.0] | laterales de 128 px | 15 | 10 | 14 |
| 2560x1080 | 0.900 | [416.0, 0.0, 1728.0, 1080.0] | laterales de 416 px | 0 | 11 | 11 |
| 1024x768 | 0.533 | [0.0, 0.0, 1024.0, 768.0] | lienzo 1440 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 18 | 208 | 6 |
| 1280x1024 | 0.667 | [0.0, 0.0, 1280.0, 1024.0] | lienzo 1536 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 9 | 94 | 8 |
| 600x1024 | 0.500 | [0.0, 0.0, 600.0, 1024.0] | lienzo 2048 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 16 | 295 | 6 |
| 720x1280 | 0.600 | [0.0, 0.0, 720.0, 1280.0] | lienzo 2133 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 7 | 153 | 7 |
| 768x1366 | 0.640 | [0.0, 0.0, 768.0, 1366.0] | lienzo 2134 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 18 | 100 | 8 |
| 900x1440 | 0.750 | [0.0, 0.0, 900.0, 1440.0] | no | 10 | 35 | 9 |
| 1080x1920 | 0.900 | [0.0, 0.0, 1080.0, 1920.0] | lienzo 2133 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 3 | 11 | 11 |
| 1200x1920 | 1.000 | [0.0, 0.0, 1200.0, 1920.0] | no | 0 | 10 | 12 |
| 1440x2560 | 1.200 | [0.0, 0.0, 1440.0, 2560.0] | lienzo 2133 de alto (AreaFija: franjas arriba y abajo en las de alto fijo) | 20 | 10 | 14 |
| 768x1024 | 0.533 | [64.0, 0.0, 640.0, 1024.0] | laterales de 64 px | 30 | 215 | 6 |

Datos: `analisis_claro.json` de `python tests/banco/resp_capturas.py --raiz <worktree de dev> --destino <dir>` y `--analizar <dir>` (la carpeta de capturas de dev no se versiona: 19 tamaños x ≈150 escenarios).

## Defectos encontrados en dev, por tipo y pantalla

1. **Franjas** (todas las pantallas): en horizontal más ancho que 8:5 (16:9, 21:9: 96 px por lado a 1920x1080 y 416 a 2560x1080) y en vertical más ancho que 5:8 (3:4: 64 px por lado a 768x1024), franjas laterales del color de la ventana. En vertical más alto que 5:8 (9:16) las pantallas de alto fijo (Reposo, Preciclo, Login, CambioClave, NuevoUsuario, asistente; `AreaFija`) quedaban centradas con franjas arriba y abajo (p. ej. 96 px arriba y 96 abajo a 1080x1920); en horizontal más alto que 8:5 (4:3, 5:4), lo mismo. Ciclo en curso, Menú, Opciones y Reportes ya tenían alto flexible.
2. **Pantallas que escalan con el ancho en vertical** (Menú, Opciones, Reportes, Preciclo, Ciclo en curso, barra flotante de Login/CambioClave/NuevoUsuario, intro): con un lienzo más ancho que el de diseño su escala crecería más que `Escala.factor` y el contenido se saldría por abajo (visto al probar la regla nueva a 1200x1600: el Menú y los botones de Preciclo quedaban fuera). En dev no se veía porque el lienzo vertical nunca era más ancho que 1200.
3. **Redondeo de la letra en tamaños chicos** (≈3 a 30 casos por tamaño, la mayoría en Reportes): `Escala.fuente()` redondea a px enteros y con factor 0,5–0,64 la letra queda hasta un 6 % más grande que su caja proporcional: «576 / 600» de Reportes encogido; «Temperatura de referencia» de la leyenda de la gráfica, «09:28» de Mantenimiento, «INICIANDO» del deslizador y «Cancelando…» del botón deslizante salen de su cuadro; «Enviar correo de prueba» y «+ Agregar destinatario» de Conectividad. Los «fuera» de Reportes son secciones del contenido desplazable (fuera de la vista del Flickable, falso positivo de la revisión).
4. **Zonas táctiles** (todas las pantallas con controles chicos): a escala física 0,5 (1024x600, 600x1024) hay 263 y 295 zonas bajo 44 px físicos; las más comunes: ojo de mostrar contraseña (28), «Tiempos» y pantalla completa de la gráfica (29), filas de alarma (36), campos de formulario (41), casilla «Recordar usuario» y enlace «¿Olvidó su contraseña?» (14; ya bajo 44 a 1920x1200: 27), interruptores (35), filtros Día/Semana/Mes (30), casillas del Historial (28–38), botones de Reportes (32). A 1920x1200 y 1200x1920 solo la casilla y el enlace de Login (27).
5. **Letra mínima**: a escala física 0,5 la letra más chica (etiquetas de 12 px de diseño de Preciclo, «Temp. ester.») queda en 6 px físicos; a 0,6 en 7; a 0,75 en 9.
6. **Ventana sin geometría**: con 0x0 el factor era 0 y `altoLienzo` NaN (0/0); sin efecto visible (la ventana nace con 600x960), pero la regla debe cubrirlo.

## Cambio de decisión (Cristian, 10-nov)

El prompt proponía franjas cuando sobra ancho y AreaFija centrada cuando sobra alto. Cristian decidió lo contrario: **sin barras ni franjas** en ninguna proporción; el contenido llena toda la ventana. Lo que sigue en el informe (`R_informe.md`) aplica esa decisión.

## Dos pantallas y el singleton `Escala`

**Hallazgo: no hay defecto.** Evidencia:

1. **Un proceso por pantalla.** `exe_unico.py` (rol lanzador) arma `_cmd_propio("--rol", "ui", "--door", str(p), "--screen", str(m)) for p, m in pantallas` y lanza cada uno con `subprocess.Popen`; en desarrollo `ui_qml/doble_pantalla.py` hace lo mismo con `python -m autoclave.ui_qml.app --door N --screen I`.
2. **Un motor y una raíz por proceso.** `ui_qml/app.py` (`main`, `_abrir_instalacion` y `_abrir_reposo_instalacion`) crea un solo `QQmlApplicationEngine` y carga una sola raíz (`Main.qml`, `InstalacionVentana.qml` o `ReposoInstalacionVentana.qml`), que pone en pantalla completa en su monitor con `setScreen` + `setGeometry(pantalla.geometry())` + `showFullScreen`.
3. **Los singletons QML son por motor.** Prueba `tests/test_resp_dpi_y_ventanas.py::test_dos_motores_no_comparten_escala`: dos motores en el MISMO proceso, con ventanas de 1200x1920 y 1280x720, dan cada uno su `Escala` (vertical factor 1 y horizontal factor 0,6). Ni siquiera el caso de dos motores en un proceso (el `QQuickWidget` de `NuevoUsuarioHost` en AutoclaveSettings, que además es otro proceso lanzado por `LanzadorAjustes` con `Popen`) comparte el singleton.
4. Dentro de una ventana, solo su raíz escribe `Escala.horizontal`, `factor`, `altoLienzo` (y ahora `dpr`); ninguna pantalla los escribe (búsqueda de `target: Escala`: solo las 4 raíces y los arneses de `qml/Pruebas/`, además de un archivo suelto `_prueba_i4_truncado_45148.qml`, versionado, que fija `factor` para una prueba antigua).

Por eso **no se refactoriza el singleton**: con pantallas de distinta orientación o resolución, cada proceso calcula la suya. Lo único que se hizo es que `factorPara`/`altoLienzoPara` calculen la orientación con el mismo tamaño que reciben (antes el factor dependía de `Escala.horizontal`, que se enlaza aparte: durante un giro había un instante en que el factor se calculaba con el lienzo de la orientación anterior; sin efecto visible, porque los bindings se vuelven a evaluar en el mismo ciclo, pero ahora no existe ese estado intermedio).

## Escala de Windows (DPI)

- Qt 6 escala siempre por DPI y en este equipo de desarrollo la política de redondeo vigente es `PassThrough` (`QGuiApplication.highDpiScaleFactorRoundingPolicy()`; la pantalla de este equipo está a 125 %: 1920x1080 físicos, `geometry()` 1536x864, `devicePixelRatio` 1,25). `app.py` no fija ninguna política ni variable.
- La ventana a pantalla completa recibe su tamaño en px **lógicos** (físicos / escala). Como el factor es `min(ancho / anchoDiseno, alto / altoDiseno)` sobre ese tamaño lógico, el lienzo ocupa **la misma fracción de la pantalla física** a 100, 125, 150, 175 o 200 %: la escala de Windows se compensa, no agranda la interfaz (`escalaFisica = factor x dpr` constante; prueba `test_la_escala_de_windows_se_compensa`, con `QT_SCALE_FACTOR` solo en el entorno del subproceso). Lo que cambia con la escala es la nitidez (más px físicos por px de diseño) y el redondeo de la letra: `Escala.fuente()` redondea a px lógicos enteros (`pixelSize` es entero), así que a 150 % la letra va de 1,5 en 1,5 px físicos (p. ej. «Temp. ester.» de Preciclo a 1920x1080: 11 px físicos al 100 % y 10,5 al 150 %).
- `PassThrough` es lo correcto para esta regla (con `Round` Qt redondearía 125 % a 100 % y 150 % a 200 %, y la ventana cambiaría de tamaño lógico, no de tamaño físico: el resultado en pantalla sería el mismo salvo nitidez). **No se fija la política en `app.py` ni en `exe_unico.py`**: ya es la de Qt 6 por defecto y fijarla no cambia nada (DECISIÓN SIN CONFIRMAR: si se quisiera blindar contra un cambio de Qt, `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` antes de crear la aplicación).
- Las capturas a 125/150/200 % se simulan con `QT_SCREEN_SCALE_FACTORS` en el entorno del subproceso de captura (`QT_ENABLE_HIGHDPI_SCALING=1`, `QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough`); a 100 %, `QT_ENABLE_HIGHDPI_SCALING=0`. No se tocó ninguna variable de entorno del equipo.

## Cambio en caliente

- Resolución, escala u orientación: Windows cambia la geometría de la ventana a pantalla completa; los `Binding` de las raíces (`factorPara(width, height)`, `altoLienzoPara`, `esHorizontal`, `Screen.devicePixelRatio`) la siguen sin reiniciar. Prueba `test_resp_escala_regla.py::test_las_raices_siguen_el_tamano_en_caliente` (Main, Reposo de instalación y asistente: 1200x1920 → 1920x1200 → 1280x720 → 720x1280 → 1600x1200 → 1920x1200).
- Cambio de monitor: `app.py` fija el monitor al arrancar (`setScreen`); si Windows mueve la ventana a otro monitor (p. ej. al desconectar uno), la ventana a pantalla completa toma el tamaño y la escala del nuevo y los bindings lo siguen (`Screen.devicePixelRatio` es por ventana). Pendiente de banco con los monitores reales.
