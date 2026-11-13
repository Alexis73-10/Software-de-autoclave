# Prompt: interfaz QML responsiva a la resolución y la escala de Windows

Trabajo sin supervisión posible con `tools\tandas\lanzar_prompt.ps1 -Nombre responsive`. Rama `responsive` desde `dev` limpio (con la tanda horizontal ya unida, merge `d89577eb`). Entrega no compilada. Informe en `docs/informes/responsive/R_informe.md`; `estado.md` al día tras cada commit; al terminar, `CERRADO.txt` (ver CLAUDE.md).

## Contexto

La tanda horizontal (`docs/informes/horizontal/R_informe.md`, `docs/mis_plans/prompt_claude_code_horizontal.md`) dejó dos lienzos fijos de diseño: vertical 1200×1920 (5:8) y horizontal 1920×1200 (8:5), elegidos por `Escala.horizontal` (`Escala.esHorizontal(ancho, alto)`, fijado por las raíces `Main`, `InstalacionVentana`, `ReposoInstalacionVentana` y `NuevoUsuarioHost` con el tamaño real de su ventana). Hoy `Escala.factor = min(ancho / anchoDiseno, alto / altoDiseno)` y `altoLienzo = max(altoDiseno, alto / factor)` (Main.qml, ~líneas 255–266). Solo se ha probado con las dos proporciones exactas 5:8 y 8:5, a 1× de escala de Windows.

## Objetivo

Que la interfaz se vea y se use bien con **cualquier resolución, proporción y escala de Windows** (100 %, 125 %, 150 %, 175 %, 200 %…), en las dos orientaciones, **sin rediseñar el contenido** y **sin cambio funcional**. El lienzo de diseño sigue siendo el de la tanda horizontal; esta tanda cambia cómo se proyecta ese lienzo sobre la pantalla real y cómo se comporta cuando la proporción no coincide.

## Fuera de alcance

- Rediseñar las pantallas o cambiar sus textos, colores o `objectName`.
- `ui_pyside` (AutoclaveSettings.exe) salvo `NuevoUsuarioHost`, que ya sigue la misma regla.
- Backend, control, alarmas, actuadores, ticket, PDF y correo.
- Cambiar la selección de pantalla de `app.py` ni la orientación que decide Windows.

## Decisiones ya tomadas (Cristian)

1. **Una sola pantalla de diseño por orientación**, no un diseño nuevo por tamaño: el responsive es de escalado y de reparto del espacio sobrante, no de rediseño.
2. **El vertical queda idéntico al de `dev`** a 1200×1920 y 100 %; lo mismo el horizontal a 1920×1200 y 100 % (comparación píxel a píxel con `tests/banco/hor_vertical_igual.py` y `hor_capturas.py`). Cualquier cambio visible en esas dos medidas exactas es un defecto.

## Decisiones que NO están tomadas: proponer, implementar la propuesta por defecto y marcar `DECISIÓN SIN CONFIRMAR` en el informe

- **Proporciones distintas del lienzo** (p. ej. 16:9, 4:3, 21:9, 3:2): **decidido por Cristian (10-nov): sin barras ni franjas** (ni negras ni del color de fondo) a los lados ni arriba/abajo. La interfaz se ajusta realmente al tamaño: el lienzo de diseño es la referencia de tamaños y el espacio sobrante se reparte reescalando, con un lienzo lógico flexible en los dos ejes (`anchoLienzo` y `altoLienzo` = tamaño real / factor). Textos, íconos y zonas táctiles escalan con el factor único y nunca se deforman; lo que se estira son contenedores, fondos, barras, listas, columnas, gráficas y espacios. `AreaFija` y todo lo que hoy centra contenido de tamaño fijo dejando franjas pasa a llenar el área disponible; los fondos cubren siempre toda la ventana. Lo único «sin confirmar» es qué crece en cada pantalla, no el principio.
- **Tamaño mínimo soportado** (p. ej. 1024×600 horizontal, 600×1024 vertical): por debajo, el lienzo se reduce hasta una letra mínima (`Escala.fuenteMinima`) y zonas táctiles no menores que un valor mínimo en píxeles físicos; proponer los valores (guía: 44–48 px físicos para el dedo).
- **Escala de Windows (DPI):** decidir si el factor debe compensar o respetar `devicePixelRatio` (Qt 6 ya entrega píxeles lógicos). Verificar con `QT_SCALE_FACTOR` y `QT_ENABLE_HIGHDPI_SCALING`/`QT_SCALE_FACTOR_ROUNDING_POLICY` cómo se comporta hoy con 125 % y 150 % (probablemente el lienzo ya es en píxeles lógicos y solo cambia la resolución efectiva); no tocar variables de entorno globales del equipo, solo documentar y, si hace falta, fijar la política de redondeo en `app.py`/`exe_unico.py` (justificado).
- **Cambio de resolución, escala u orientación en caliente:** las ventanas deben reaccionar sin reiniciar (cambia el tamaño de la ventana y los `Binding` de `Escala` la siguen); verificar también el cambio de monitor entre las dos pantallas del equipo.
- **Dos pantallas con orientaciones o resoluciones distintas** (la pantalla 1 y la 2 pueden diferir): `Escala` es un singleton compartido por proceso; hoy `Escala.horizontal` y `factor` lo fijan varias raíces. Comprobar si las dos ventanas viven en el mismo proceso/motor QML (entonces el singleton se pisa) o en procesos distintos, y proponer la solución (p. ej. propiedades de escala por ventana en lugar de singleton global) solo si hay un defecto real; documentar el hallazgo con evidencia antes de refactorizar.

## Pasos

1. **Diagnóstico** (`docs/informes/responsive/diagnostico.md`), sin editar código: con los arneses de `tests/banco/` capturar todas las pantallas a 11 tamaños (1024×600, 1280×720, 1366×768, 1440×900, 1600×900, 1920×1080, 1920×1200, 2560×1440 y sus giros 600×1024, 720×1280, 1200×1920, etc.) y a escalas de ventana equivalentes a 100/125/150/200 %; listar por pantalla los defectos (desborde, recorte, franjas, zonas táctiles pequeñas, texto bajo el mínimo, solapes, elementos fuera de la pantalla). Confirmar o descartar el problema del singleton con dos ventanas.
2. **Regla de proyección** en `Tema/Escala.qml` (y los `Binding` de las 4 raíces): una sola implementación (`factor`, `altoLienzo`, y si hace falta `anchoLienzo`) para las dos orientaciones, con la política decidida arriba. Las funciones puras y constantes viven en `Escala.qml`; las raíces solo enlazan.
3. **Reparto del espacio sobrante** en las pantallas y componentes que lo necesiten (`AreaFija`, `BarraSuperior`, barras inferiores, paneles con columnas, listados, gráfica, teclado en pantalla): solo anclajes, `Layout` y márgenes; nunca cambiar tamaños de diseño ni textos. Textos: regla D8-5.4 (letra baja hasta `Escala.fuenteMinima`, sin `elide`).
4. **Zonas táctiles mínimas** en píxeles físicos para botones, interruptores, casillas, filas de listas y el deslizador de inicio; sin cambiar su tamaño a 1920×1200 / 1200×1920.
5. **Pruebas.** Nuevas `tests/test_resp_*.py`: la regla de `Escala` (tabla de tamaños y escalas → `factor`, `altoLienzo`, orientación, sin saltos ni NaN con ventana de 0×0 o muy pequeña), desbordes de texto y de contenedor en los tamaños de la tabla, zonas táctiles mínimas, y que a 1200×1920 y 1920×1200 nada cambió. No modificar pruebas existentes salvo que fijen el singleton de forma incompatible (justificar en el informe). Suite completa verde; si una prueba ajena falla (en `dev` hay 16 fallas preexistentes: c2_programas_persistentes, q1_r1p3, t12_*, t17_copia_programa, t29_descompresion, t28_a14_m3, v8b descripciones), anotarla sin ocultarla.
6. **Capturas** por pantalla en 6 tamaños representativos (claro y oscuro) en `docs/informes/responsive/capturas/` y script `tests/banco/resp_capturas.py`; reutilizar los arneses de la tanda horizontal.
7. **Cierre.** Informe con lo hecho, la tabla de tamaños soportados, lo pendiente de banco (monitores y escalas reales de la estación, táctiles, giro del monitor con la app abierta, dos pantallas con distinta resolución) y las `DECISIÓN SIN CONFIRMAR`. Merge a `dev` solo si la suite pasa y las comparaciones de 1200×1920 y 1920×1200 salen idénticas; escribir `CERRADO.txt`.

## Restricciones

- Diff solo en `src/autoclave/ui_qml/` (QML y, si el hallazgo del singleton o la política de DPI lo exige, `app.py`/`exe_unico.py` con justificación), `tests/` y `docs/`.
- Colores solo en `Tema/` (`tests/test_tema_oscuro.py`); sin `Canvas`, `Particles` ni `Effects` nuevos.
- Los cambios de tipo de contenedor de la tanda horizontal (`Column` → `Grid`, `ListView` → `GridView`) no se revierten.
- Si un tamaño no puede cumplir (p. ej. 1024×600 con la pantalla de Opciones sin desplazar), no inventar: anotarlo con captura y opciones.

## Hecho cuando

Todas las pantallas se ven y se usan, sin recortes, deformaciones ni barras/franjas (el contenido llena toda la ventana; hay una prueba automática de cobertura del 100 %), en los tamaños de la tabla y a 100–200 % de escala, en las dos orientaciones y los dos temas; 1200×1920 y 1920×1200 idénticos a `dev`; el cambio de resolución, escala u orientación en caliente se refleja sin reiniciar; suite verde; informe y capturas entregados.
