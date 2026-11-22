# Prompt para Claude Code: revisión visual, prueba de interacción de todas las pantallas y correcciones de maquetación

Trabajo sin supervisión (lo lanza Cristian con `tools\tandas\lanzar_prompt.ps1 -Nombre revision_visual`). Todo en español: informes, commits, comentarios y mensajes. Usa siempre el código local de `C:\Users\tecni\Documents\codigo_autoclave`. No supongas nada sin leer el código.

## Objetivo

Revisar visualmente TODAS las pantallas, modales, paneles y diálogos QML del Software de Autoclave, encontrar textos o controles que se sobreponen, se tapan, se recortan, se salen de la pantalla o de su cuadro, están desalineados o no tienen contraste, y corregir los que sean ajustes de maquetación. Además, operar las pantallas como lo haría un usuario (tocar botones, deslizar, escribir con los teclados en pantalla, abrir y cerrar modales, navegar por todo el menú) y entregar un informe de lo que funciona y lo que falla. Lo que cambie el contenido, el comportamiento o la información mostrada queda para decisión de Cristian.

Excepción para esta primera vez, autorizada por Cristian: se permite abrir ventanas visibles (plataforma `windows`) para la etapa B2 (íconos) y para la etapa E (interacción). Todo lo demás sigue en offscreen.

## Herramienta

Usa la skill `revision-visual-pantallas` (invócala con la herramienta Skill antes de empezar y síguela). Si no está disponible, sigue este resumen: capturas con `tests/banco/hor_capturas.py --plataforma offscreen` (nunca la plataforma `windows`, que abre ventana), detectores de `tests/helpers/textos_caben_qml.py` y «fuera del lienzo» en `resumen_<tema>.json`, y revisión visual de cada PNG con la herramienta Read (recortando y ampliando con Pillow cuando haga falta detalle).

Limitaciones de offscreen, que no son hallazgos: `MultiEffect` no se dibuja (los íconos `IconoColor` pueden salir vacíos) y los componentes animados (`DeslizadorInicio`, `CirculoFaseLiquido`) cambian según el instante. En esta tanda los íconos se verifican con la pasada visible de la etapa B2.

## Reglas de trabajo

- Rama `revision-visual` creada desde `dev`. No toques los archivos sin seguimiento de otros planes (`planeacion_registro_carga.md`, `prompt_claude_code_registro_carga.md`).
- Lleva `docs/informes/revision_visual/estado.md` (paso → Hecho/Pendiente, último commit) al día después de cada commit; al reanudar, sigue desde el primer paso pendiente.
- Máximo 4 subagentes a la vez. Los subagentes no corren la suite completa. Un solo revisor independiente, en la etapa E.
- Ventanas visibles solo en las etapas B2 y E; en el resto, todo proceso Qt con `QT_QPA_PLATFORM=offscreen`.
- Sin merge a `dev` y sin compilar la entrega: Cristian confirma visualmente antes.

## Etapa A: detector automático de solapes

1. Crea `tests/helpers/solapes_qml.py` con una función JS reutilizable (estilo de `textos_caben_qml.py` y de `volcarGeometria` en `tests/banco/resp_geometria_igual.py`) que recorra los ítems visibles (visible y opacity > 0, dentro de la ventana) y reporte el tipo `solape`: dos elementos con contenido (Text con texto no vacío, Image/IconoColor con fuente, controles con objectName o MouseArea habilitada) cuyos rectángulos en coordenadas de la ventana se intersectan más de 4 px en ambos ejes, que no son ancestro y descendiente entre sí y que no están recortados por un clip. Excluye: un texto sobre su propio fondo (los Rectangle no cuentan como contenido), los ítems dentro de componentes animados, y lo que queda debajo de un modal o panel visible que lo cubre a propósito (cuenta solo la capa superior). Cada problema lleva clase, objectName, texto (40 caracteres), rectángulo de cada elemento y área de intersección.
2. Intégralo en `tests/banco/hor_capturas.py` (y en `tests/banco/i4_truncado_banco.py` si es directo) para que `resumen_<tema>.json` incluya los `solape`.
3. Prueba automática `tests/test_rv_solapes_qml.py` con un QML mínimo offscreen: dos Text encimados → 1 solape; texto dentro de su Rectangle → 0; elemento tapado por un modal visible → 0; dos Text en un ítem con clip que los separa → 0.
4. Commit: «RV etapa A: detector de solapes en las capturas».

## Etapa B: inventario y capturas base

1. Compara las pantallas de `src/autoclave/ui_qml/qml/Pantallas/`, los componentes que se muestran como modal, panel o diálogo (`Componentes/`) y los estados relevantes (sin datos, sin conexión, modo prueba, alarmas activas, teclado abierto, ciclo en curso, fin de ciclo) contra los escenarios de `tests/banco/hor_escenarios_a..e.py`. Agrega los escenarios que falten, con datos de ejemplo verosímiles y textos largos en inglés donde existan. Deja la lista en `docs/informes/revision_visual/inventario.md`.
2. Captura todo en `docs/informes/revision_visual/base/<WxH>_<idioma>/`: tamaños 1200x1920 y 1920x1200, temas claro y oscuro, idiomas es y en. Además `tests/banco/i4_truncado_banco.py` (1024 × 1638) en es y en, con captura. Lanza los procesos largos en segundo plano.
3. Commit del inventario, los escenarios nuevos y los `resumen_*.json` (las PNG también, en la carpeta del informe).

### B2: pasada visible para íconos

Repite las capturas de 1200x1920 y 1920x1200, tema claro y oscuro, idioma es, con `--plataforma windows`, en `docs/informes/revision_visual/base_windows/`. Úsala solo para revisar íconos, sombras y efectos que offscreen no dibuja (íconos ausentes, deformados, de color equivocado o sin contraste en el tema oscuro).

## Etapa C: revisión y hallazgos

1. Lee todos los `resumen_*.json` y revisa visualmente TODAS las PNG con la lista de la skill: texto sobre texto o bajo un control, controles encimados, modales, teclado y paneles que no cubren o tapan un campo, contenido cortado en bordes, columnas desalineadas, espaciado irregular, contraste en oscuro y claro, textos en inglés que rompen el diseño, zonas táctiles pequeñas, y diferencias de posición entre claro/oscuro, es/en y vertical/horizontal del mismo escenario. Puedes repartir los grupos de escenarios entre hasta 4 subagentes; cada uno devuelve hallazgos con evidencia, y tú los consolidas sin duplicados.
2. Escribe `docs/informes/revision_visual/hallazgos.md`, sin tablas, un hallazgo por entrada RV-NN con: pantalla y escenario, tamaño, tema, idioma, qué se ve, evidencia (PNG y zona en píxeles), origen (detector y tipo, o visual), componente QML probable (archivo y línea), severidad (ALTA si tapa información de seguridad, alarmas, NO ABRIR, valores del ciclo o un control operativo; MEDIA si afecta la lectura; BAJA si es estética) y categoría:
   - **Categoría 1, corrección de maquetación:** se arregla con anclas, Layouts, tamaños, márgenes, z, wrapMode, fontSizeMode/minimumPixelSize o el valor oscuro de un color en `Tema/Colores.qml`, sin cambiar qué se muestra.
   - **Categoría 2, decisión de Cristian:** cambiar o abreviar un texto o una clave i18n, quitar, mover o agregar elementos, cambiar la posición o el tamaño de un control operativo o de seguridad (deslizadores de inicio y cancelar, CONFIRMAR, paro, botones de puerta, filas de alarma), cambiar un valor claro de `Colores.qml`, o cualquier cosa que toque lógica, backend o un controlador Python.
   - **Falso positivo:** con el motivo.
3. Commit: «RV etapa C: hallazgos».

## Etapa D: correcciones de categoría 1

1. Corrige solo la categoría 1, de mayor a menor severidad, agrupando por componente. Reglas del proyecto que rigen siempre:
   - Colores solo en `Tema/Colores.qml`; los valores claros no cambian (`tests/test_tema_oscuro.py`); alarmas iguales en los dos temas; contraste WCAG de los pares de la paleta.
   - Textos largos: bajar la letra (`fontSizeMode`/`HorizontalFit` con mínimo legible), nunca `elide` (D8-5.4, `tests/test_v8b_textos.py`).
   - No cambies objectNames, propiedades públicas, señales ni textos; QML solo dibuja (la lógica sigue en `ui_qml/domain` y los puentes).
   - Respeta la geometría fijada por el mockup donde CLAUDE.md la cita (barra inferior de Ciclo en curso: celda derecha de x 800 al borde, margen 12 px; deslizador de cancelar 235 × 88 px; lupa 56 × 56).
   - Si una corrección deja de ser solo maquetación al implementarla, detente en ese hallazgo, pásalo a la categoría 2 y sigue con el siguiente.
2. Después de cada grupo: recaptura los escenarios afectados en todas las combinaciones de tamaño, tema e idioma, compara antes y después leyendo las PNG, corre las pruebas relacionadas (`tests/test_tema_oscuro.py`, `test_v8a_textos.py`, `test_v8b_textos.py`, `test_u10a_textos_caben_qml.py`, `test_u10b_textos_caben_qml.py`, `test_t21_textos_caben_qml.py`, `test_hor_*`, `test_rv_solapes_qml.py` y las de la pantalla tocada) y haz commit «RV etapa D: RV-NN, RV-MM (componente)». Si una prueba fija la geometría anterior a propósito, no la cambies: el hallazgo pasa a la categoría 2.

## Etapa E: prueba de interacción (pantallas en uso)

### E1. Seguridad del entorno (obligatorio antes de tocar nada)

- Nunca se conecta al hardware real. Antes de empezar comprueba que 192.168.3.7:502 no responde (`Test-NetConnection 192.168.3.7 -Port 502`). Si responde, no uses el backend real: solo el simulador, y anótalo en el informe.
- Backend: primero el simulador (`python -m autoclave.simulador`, en 127.0.0.1:8001; ver `ui_qml/lanzar.py`). Revisa qué rutas responde de verdad y cuáles no. Para los flujos que el simulador no cubre (inicio y cancelación de ciclo con la máquina de estados real, modo prueba, Entradas/Salidas, usuarios), puedes usar el backend real SOLO apuntado al simulador Modbus `tests/helpers/m31_simulado.py` en 127.0.0.1, con la configuración del enlace cambiada únicamente en la copia de trabajo descrita abajo. Si no puedes garantizar que el backend real no sale de 127.0.0.1, no lo uses y deja esos flujos como «no probados».
- Datos aislados: trabaja en un worktree aparte (`git worktree add --detach ..\codigo_autoclave_rv revision-visual`, porque la rama ya está en uso en el repositorio principal; el arnés y los cambios se editan y se confirman en la rama, y el worktree solo se actualiza con `git checkout --detach revision-visual` para ejecutar) con su propia copia de `data/`. No modifiques la `data/` del repositorio principal (base de datos, usuarios, perfil, calibración, programas). Al terminar, el repositorio principal debe quedar igual que antes en todo lo que no sea la rama.
- Variables: `AUTOCLAVE_REINICIO_PC=0` siempre.
- Prohibido accionar, aunque estén en pantalla: Apagar equipo, Reiniciar PC o reiniciar el software con apagado del sistema, Instalación/Setup y asistente de instalación sobre datos reales, restaurar respaldos sobre `data/` real, configurar módulo, Red del módulo E/S, cambiar fecha, hora o zona horaria de Windows, scripts de `tools/estacion/`, envío real de correo (si la pantalla de correo se prueba, solo con el servidor de correo vacío o inválido y sin destinatarios reales) e impresión física. Estos controles se reportan como «no accionados por seguridad», con su captura.

### E2. Arnés de interacción

Crea `tests/banco/rv_interaccion.py` que levante la UI completa (las dos pantallas, puerta 1 y 2, como `ui_qml/lanzar.py`) en ventanas visibles a 1200x1920 contra el backend de E1 y la opere con eventos reales de ratón/toque y teclado de `QTest` (presionar, mover y soltar en las coordenadas de ventana del centro visible del control, buscado por objectName o texto). No llames slots ni cambies propiedades directamente para simular un toque: el objetivo es comprobar que el control recibe el toque donde se ve. Después de cada paso: espera a que la pantalla se estabilice, guarda una captura (`grabWindow`) en `docs/informes/revision_visual/interaccion/<flujo>/NN_<paso>.png`, registra las advertencias del motor QML, los errores del log de la UI y del backend, y verifica el resultado esperado (pantalla o modal que debe aparecer, texto, estado en `/status`).

Si un toque en el centro de un control no llega a ese control (lo recibe otro ítem que lo tapa), es un hallazgo de solape de la etapa C.

### E3. Flujos a probar (como mínimo)

Para cada flujo, en es y en, tema claro (y oscuro en los que la etapa C dejó dudas):
1. Arranque: intro, barra de progreso y llegada al Menú Principal o al Reposo.
2. Login correcto e incorrecto, bloqueo por intentos, cerrar sesión, cambio de contraseña voluntario.
3. Menú Principal: cada tarjeta lleva a su pantalla y se puede volver.
4. Preciclo: selector de programa desplegable, modal de operador (con y sin operadores activos), puerta con y sin actuador, deslizador de inicio (arrastre completo, arrastre incompleto que debe regresar, deslizador oculto en modo prueba).
5. Ciclo en curso: barra de fases, gráfica (cursor con un dedo, zoom con dos dedos, lupa que restablece), campana y tarjeta de alarmas con su detalle, deslizador de cancelar (completo e incompleto), fin de ciclo con panel, «Ver gráfica», CONFIRMAR con su modal y regreso.
6. Opciones: cada sección, sus filtros, campos numéricos y alfanuméricos con el teclado en pantalla (escribir, borrar, cancelar, confirmar, valor fuera de rango rechazado), guardar y comprobar que el valor quedó; Usuarios (crear, cambiar rol, desactivar, eliminar con su modal); Bitácora con filtros y calendario; Parámetros del ciclo de un programa; Reasignación hasta el diálogo de Aplicar sin aplicar; Entradas/Salidas en modo prueba solo contra el simulador Modbus; selector de idioma, unidades y tema.
7. Historial y Reportes: vistas Día, Semana, Mes y Año, calendario por programa, detalle de un ciclo, selector de destino sin enviar.
8. Standby/Reposo: entrada por inactividad y salida al tocar.
9. Pantalla 2 siguiendo a la pantalla 1 (idioma, tema, unidades) y comportamiento sin conexión con el backend detenido a mitad de una pantalla.

Si un flujo no se puede reproducir con el backend disponible, déjalo «no probado» con el motivo; no lo simules forzando el estado desde el código.

### E4. Hallazgos de interacción

Agrega a `hallazgos.md` las entradas RVI-NN con: flujo y paso, qué se hizo, qué se esperaba, qué pasó, evidencia (capturas y fragmento de log), severidad (ALTA si afecta seguridad, ciclo, alarmas o un control operativo; MEDIA si impide completar una tarea; BAJA si es menor) y categoría. Solo son categoría 1 los problemas de maquetación (un control tapado, fuera de la pantalla o con zona de toque desplazada); se corrigen con las reglas de la etapa D y se vuelven a probar con el arnés. Cualquier falla de funcionamiento (el botón no hace nada, hace otra cosa, el backend responde con error, un texto o valor equivocado, una pantalla que se cuelga) es categoría 2: no se corrige, se documenta con lo necesario para reproducirla y la causa probable (archivo y línea) si la encuentras leyendo el código.

Commit: «RV etapa E: prueba de interacción».

## Etapa F: verificación

1. Recaptura todo (las mismas combinaciones de la etapa B, offscreen) en `docs/informes/revision_visual/final/` y compara con `base/`: cada hallazgo corregido debe desaparecer y no puede aparecer ningún problema nuevo (detectores y revisión visual). Si aparece, corrígelo o revierte el cambio que lo causó.
2. Corre la suite completa una vez (`pytest` con `QT_QPA_PLATFORM=offscreen`). Registra el resultado.
3. Un subagente revisor independiente, que no participó en las correcciones, revisa el diff de la rama contra `dev` y las PNG de antes y después, buscando: información de seguridad que quede tapada, menos visible o con menos contraste, controles operativos movidos, textos cambiados y reglas del proyecto incumplidas. Corrige lo que encuentre o pásalo a la categoría 2.
4. Si algún hallazgo ALTA tapaba información de seguridad, agrega su entrada en `docs/riesgos/registro_riesgos.md` (HAZ-RV-NN, estado y control) y la trazabilidad que corresponda.

## Etapa G: informes

Dos informes en español, sin tablas.

`docs/informes/revision_visual/R_interaccion.md`: entorno usado (simulador, backend real con Modbus simulado o no, y por qué), flujos probados con resultado (funciona / falla / no probado / no accionado por seguridad), cada RVI-NN con sus pasos para reproducirlo y enlaces a las capturas, advertencias QML y errores de log agrupados, y la lista de lo que queda por probar en la estación real con los táctiles.

`docs/informes/revision_visual/R_informe.md`:
- Resumen: escenarios revisados, combinaciones, hallazgos por severidad y categoría.
- Corregidos: cada RV-NN con el cambio hecho (archivo) y las PNG de antes y después.
- Pendientes de decisión de Cristian: preguntas numeradas, una por hallazgo de categoría 2, con tu recomendación concreta.
- Falsos positivos descartados y por qué.
- Pruebas: suite completa, pruebas nuevas, resultado del revisor.
- Limitaciones: lo que debe verse en la pantalla real de la estación (táctiles, escalado, brillo).

## Cierre

1. Actualiza `CLAUDE.md` con una sección breve «Revisión visual (RV)» (detector de solapes, escenarios nuevos, arnés de interacción, informes).
2. Quita el worktree de la etapa E (`git worktree remove`) después de copiar las capturas e informes a la rama, y comprueba que la `data/` del repositorio principal no cambió.
3. Último commit en la rama `revision-visual`, sin merge a `dev`.
4. Escribe `docs/informes/revision_visual/CERRADO.txt` con la fecha, el último commit, el resultado de la suite y la línea: «No se compiló la entrega ni se unió a dev». Si te detiene un bloqueo que necesite a Cristian, escríbelo igual con `BLOQUEADO:` y el motivo en la primera línea.
