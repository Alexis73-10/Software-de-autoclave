# Instrucción maestra para Claude Code — Tanda 17: hallazgos de la instalación I (sin supervisión)

> Se lanza con `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_tanda.ps1 -Tanda 17` (`claude -p`, se relanza si se corta). Siempre REANUDA desde `docs/informes/tanda17/estado.md`.

## Alcance y fuentes
- Fuente de verdad, COMPLETA: `docs/mis_plans/decisiones_tanda_17.md`. Prevalece sobre O11/D11-7 y sobre SAF-01 de S9.
- Alcance:
  - INS-01 y INS-02;
  - SON-01;
  - PRC-01;
  - ESG-01 y ESG-02;
  - MPR-01;
  - ALM-01;
  - VER-08 y UI-VER;
  - BIT-01 a BIT-05;
  - EST-06 y EST-07;
  - A1: la falla preexistente que bloqueó la entrega de la tanda 16.
- Prioridad: velocidad, sin sacrificar seguridad (código Clase C).

## Modo de ejecución
- La sesión principal hace A0, A1, F, I, K, L y Z.
- **Hasta 4 subagentes a la vez**, en V (solo lectura), P (worktree y rama propia) y R (solo lectura).
- Los subagentes no corren la suite completa: solo sus pruebas y las de los módulos que tocan.
- La sesión principal corre la suite completa con `pytest tests -n auto`. Lo que falle solo en paralelo se repite en serie y cuenta como verde si pasa en serie (anotado).

## 0. Reglas
1. Rama `tanda-17` desde `dev`.
   - Estado en `docs/informes/tanda17/estado.md` (tabla `| Etapa | Estado | Nota |`), al día después de cada commit, con el último commit.
   - Informe único: `docs/informes/tanda17/R17_informe.md`.
   - Índice: `docs/informes/informe_tanda_<fecha>_t17.md`.
2. Git:
   - Nunca `main`, `--force`, `git add -A`, `git push --delete`, `git branch -D` ni reescritura del historial. No toques los stash.
   - No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, `_suites_t11/`.
   - Prefijos: `feat(t17)`, `fix(t17)`, `test(t17)`, `docs(t17)`.
3. Pruebas:
   - Prohibido borrar, saltar (`skip`/`xfail`) o relajar una prueba existente.
   - Única excepción: actualizar la aserción de una prueba que fija un comportamiento que esta tanda cambia por decisión de Cristian (O11 → SON-01; SAF-01 → ESG-02; eventos retirados de BIT; filtros de la bitácora; `app.version`; `Delay PT10S`). La decisión se cita en un comentario.
   - Cada prueba tocada va al informe.
4. Prohibido:
   - hardware o puertos COM;
   - firmware;
   - **ejecutar `.ps1`, el Setup o la herramienta de táctiles**;
   - escribir en el registro de Windows o cambiar la zona horaria de esta máquina;
   - instalar software del sistema;
   - borrar archivos sin seguimiento de git;
   - leer o imprimir el archivo de secretos de activación.

   Autorizado:
   - `tools/entrega/compilar_entrega.py` en K;
   - compilar el Setup con ISCC solo para comprobar la sintaxis (sin instalar), si el script de entrega lo permite por separado.
5. Todo temporizador nuevo usa `time.monotonic()`. Presión siempre en kPa absolutos.
6. Textos visibles en español e inglés, con el mecanismo i18n existente. Los textos del Setup van en `[CustomMessages]` `es.`/`en.`.
7. Ante ambigüedad: lo más seguro y reversible, anotado como «DECISIÓN SIN CONFIRMAR». Todo en español.

## 1. Etapas

### A0. Precondición (sesión principal)
1. `git merge-base --is-ancestor tanda-16 dev`. Si falla: fila `| A0 | Esperando | <motivo> |` y TERMINA.
2. Si `git status --porcelain --untracked-files=no` no está vacío:
   - si `git diff --ignore-cr-at-eol --quiet` confirma que solo hay diferencias de fin de línea (caso conocido tras el cierre de la tanda 16), restaura esos archivos con `git checkout -- <archivo>` y lo anota;
   - si hay cambios reales: `| A0 | Esperando | cambios sin commit: <lista> |` y TERMINA.
3. Rama `tanda-17`.
4. Commit `docs(t17)` con `decisiones_tanda_17.md`, esta instrucción y el prompt.
5. Línea base (recolectadas y resultado) en `docs/informes/tanda17/base_suite.txt`.

### A1. Falla preexistente (sesión principal, antes de F)
1. Diagnostica `tests/test_ver_entrega.py::test_historial_entrada_debajo_de_la_marca` (R16 §8, rota desde la entrega 1.0.0-alpha.1).
2. Corrige la causa: el historial `docs/versiones/HISTORIAL_VERSIONES.md` o el código de `compilar_entrega.py`. La prueba no se relaja.
3. Revisa también las 3 pruebas que fallan solo en paralelo (R16) y deja anotado si `compilar_entrega.py` las corre en paralelo. Si el script exige la suite en verde, debe poder pasar.
4. Commit `fix(t17)`.

### V. Verificaciones (hasta 4 subagentes de solo lectura, sin commits; archivo:línea en el informe)
- **V-01 · Rutas de datos:** todo uso de `%ProgramData%`, `{commonappdata}`, `raiz_datos_exe`, `app_root`, `carpeta_datos` y rutas fijas `C:\` en `src/`, `tools/instalador/`, `tools/estacion/`, `packaging/` y `tools/entrega/`.
  - ¿`instalador_exe.py` se usa todavía en la entrega? Si no, se deja y se anota.
- **V-02 · Setup:** páginas, `[Tasks]`, `[Run]`, `[UninstallDelete]`, la "instalación limpia", el log de la estación, cómo se llaman los pasos de `tools/estacion` y cómo se reporta el fallo del 06. Dónde y con qué `Delay` se crea la tarea de arranque.
- **V-03 · Sondas y estado seguro:**
  - dónde se deja de leer o publicar una sonda No en uso (O11);
  - el registro del ciclo (`cycle_logger`, `db_manager`) y qué guarda por sonda;
  - dónde se activa CIC-10 y con qué motivos;
  - `salidas_prueba_seguridad` y sus llamadores.
  - qué salidas llevan vacío al empaque (`desbloqueo_puerta_N`, `bomba_vacio` vía `AdvancedDoor.vacio_on`, u otras), qué sensor confirma "puerta cerrada" por cada puerta instalada y dónde se puede apagar una salida del modo prueba en el mismo tick (ESG-02).
- **V-04 · UI y bitácora:**
  - escritor central de `audit_log`;
  - llamadas a `_auditar` de los eventos de BIT;
  - **cómo cuenta el bloqueo de usuario los intentos fallidos** (BIT-03);
  - cómo se sabe que la instalación no ha terminado;
  - filtros de `OpcionesBitacora.qml` y su endpoint;
  - todos los usos de `app.version`/`version:`;
  - las listas de alarmas (Preciclo, campana, Ciclo en curso) y `FilaAlarma.qml`;
  - el `Flow` de `OpcionesParametrosCiclo.qml` y la lista de Manejo de ciclos;
  - la cabecera de `OpcionesEntradasSalidas.qml`.

Con V, la sesión principal escribe en `estado.md` la **tabla de propiedad de archivos** de P: un dueño por archivo. Lo compartido lo hace la sesión principal en F o I.

### F. Fundaciones (sesión principal, un commit por punto)
- **F1. Contrato de la ruta de datos (INS-02):** en `utils/resources.raiz_datos_exe`, el orden de resolución de las decisiones (registro → regla anterior → carpeta del .exe), con pruebas del registro simulado (sin tocar el registro real). Constantes compartidas: clave `HKLM\SOFTWARE\Especifika\Autoclave`, valores `RutaPrograma`/`RutaDatos`, subcarpetas `programa`/`datos`.
- **F2. Bitácora central (BIT-01 a 04):**
  - lista `EVENTOS_REGISTRADOS` y desvío al logger de los retirados en el escritor de `audit_log`;
  - supresión mientras la instalación esté en curso;
  - evento `equipo_instalado`;
  - categorías de BIT-05 (tabla evento → categoría en `core/runtime/bitacora.py`);
  - corrección del contador de bloqueo si V-04 muestra que depende de `login_fallido`.
  - Pruebas: bloqueo idéntico tras N intentos; ninguna fila durante la instalación; una sola `equipo_instalado`.
- **F3. Textos:** claves i18n nuevas (es/en) de toda la tanda: "(monitoreo)", el selector de programas, la ventana emergente de alarmas, los filtros y el calendario, la cabecera del modo prueba, las categorías y `equipo_instalado`. Se retira `app.version`.

### P. Implementación en paralelo (4 subagentes, `isolation: worktree`)
Cada subagente:
- trabaja en la rama `tanda-17-<s>`, creada desde `tanda-17` después de F;
- toca solo sus archivos de la tabla;
- deja los textos nuevos que falten en `docs/informes/tanda17/i18n/<s>.json`;
- pone sus pruebas en `tests/test_t17_<s>*.py`, con el marcador `req`;
- hace commit en su rama;
- responde en español con: archivos tocados, pruebas nuevas y tocadas, DECISIONES SIN CONFIRMAR y **pruebas manuales pendientes**.

**s1 · Setup y ruta de datos** (`tools/instalador/autoclave.iss`, `estacion_setup.ps1`, las rutas de `tools/estacion/_comun.ps1`, `instalador_exe.py` si se usa, y los demás usos de V-01 que no sean de s2):
- INS-01: página de zona horaria, aplicación con `tzutil` en `ssPostInstall`, `/ZONA=`.
- INS-02:
  - página de unidad (solo discos fijos, espacio mínimo, preselección);
  - disposición `X:\Especifika\Autoclave\{programa,datos}`;
  - ACL explícitas sin herencia;
  - clave de registro en la vista de 64 bits;
  - actualización con la unidad fija;
  - bloqueo ante una instalación en la disposición anterior;
  - "instalación limpia" y desinstalador sobre `datos`.
- Pruebas: las de Python sobre el contrato y, sobre el `.iss`, las que existan para el Setup (por ejemplo, pruebas de texto o estructura del `.iss`, si las hay).

**s2 · Estación: táctiles y arranque** (`tools/estacion/06_*.ps1`, `03_tarea_autoclave.ps1`, `tools/instalador/tarea_arranque.ps1`, `exe_unico.py`, módulo nuevo de la herramienta de táctiles, la señal de "primer cuadro" del lado QML si V lo permite sin pisar a s4; si no, la hace la sesión principal en I):
- EST-06:
  - camino de respaldo con `Autoclave.exe --rol asociar-tactiles`, con ctypes, Raw Input y Digimon;
  - respaldo y reversión;
  - mensajes;
  - el fallo no corta la estación.
  - Prueba unitaria del armado de los valores Digimon con datos simulados.
- EST-07: `PT0S`, cubierta Win32 inmediata con cierre por señal o tope y fallo silencioso. Prueba de que el lanzador abre la cubierta antes de importar PySide (orden de llamadas con dobles).

**s3 · Backend: sondas, estado seguro y modo prueba** (`core/runtime/sensores_ciclo.py`, `core/managers/gestion_programas.py`, `backend/rutas/programas.py` para las entradas, `ui_qml/domain/entradas_mostradas.py`, el registro del ciclo, `state_machine/estado_seguro.py`, `core/runtime/salidas_prueba_seguridad.py`, `backend/rutas/io.py` y el endpoint de la bitácora con rango y usuarios):
- SON-01 completo, salvo el QML.
- ESG-01.
- ESG-02: se retiran los bloqueos del estado seguro y se implementan las protecciones permanentes 1–3 del modo prueba, incluido el apagado en el mismo tick. `aire_atmosferico_prueba` queda intacto.
- Backend de BIT-05.
- Pruebas: sonda No en uso leída, registrada, sin ticket y sin alarma; CIC-10 no se activa por presión sin lectura y sí por los demás motivos; en modo prueba con presión vigente no quedan los bloqueos del estado seguro y sin presión sí; puerta y desbloqueo rechazados con la cámara presurizada, en vacío o sin lectura; `vapor_camara` rechazada con una puerta abierta o sin lectura, y apagada si la puerta se abre con la salida encendida.

**s4 · Interfaz QML** (pantallas y componentes de: Parámetros del ciclo, Manejo de ciclos, Entradas/Salidas, listas de alarmas y su ventana emergente, Bitácora con desplegables y calendario, barra inferior, `ui_pyside/main_window.py`, controladores de esas pantallas, `info_equipo.py` para VER-08):
- PRC-01, con un componente reutilizable.
- MPR-01.
- ALM-01.
- UI-VER.
- BIT-05 en la UI, con un componente de calendario reutilizable.
- El rótulo "(monitoreo)" de SON-01.
- VER-08.
- Pruebas QML y de controlador con el patrón existente.

### I. Integración (sesión principal)
1. Une las ramas en `tanda-17` con `--no-ff`, en el orden s3, s1, s2, s4. Los conflictos se resuelven conservando las dos intenciones y se anotan.
2. Fragmentos i18n en `es.json`/`en.json`; `tools/claves_sin_uso_i18n.py` sin claves huérfanas nuevas.
3. Compilación de comprobación del Setup (ISCC, sin instalar), si es posible.
4. Suite completa en verde. Recolectadas = base + nuevas.

### R. Revisión (4 subagentes de solo lectura, uno por área)
Cada uno revisa `git diff dev...tanda-17 -- <rutas del área>`.

Prompt común: «Es código de seguridad Clase C de un autoclave. Busca:
- programa modificable por un usuario estándar (ACL heredadas de la raíz de la unidad);
- rutas que sigan en `%ProgramData%`;
- actualización que cambie de unidad o pierda datos;
- `tzutil` sin verificación;
- sonda No en uso que entre al control, a las fallas, al ticket o que genere alarma;
- estado seguro que avance sin presión;
- modo prueba sin bloqueos cuando NO hay presión vigente;
- puerta, desbloqueo o vacío al empaque permitidos con la cámara presurizada;
- `vapor_camara` permitida o que siga encendida con una puerta abierta;
- aire atmosférico desbloqueado con la cámara presurizada;
- bloqueo de usuario que cambie al retirar `login_fallido`;
- eventos de seguridad perdidos en la bitácora;
- la cubierta de arranque que pueda dejar la pantalla negra para siempre;
- valores Digimon mal formados;
- reloj de pared en temporizadores;
- pruebas que pasan sin probar lo que dicen.

No ejecutes la suite completa. Responde en español con hallazgos `V17-<s>-xx` (archivo:línea, severidad alta/media/baja, motivo) o "sin hallazgos".»

Corrige los hallazgos válidos (commit) y repite la suite. Un hallazgo alto sin corregir bloquea K.

### K. Unión y entrega (suite en verde, sin hallazgos altos)
1. Ejecuta `git checkout dev` y `git merge --no-ff tanda-17 -m "Merge tanda-17 en dev"`, y luego la suite completa.
2. Commit `docs(t17)` en `dev`: actualiza `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md` (existe desde la tanda 16).
   - Marca como corregidos los hallazgos de esta tanda.
   - Agrega las protecciones permanentes del modo prueba (ESG-02) y las DECISIONES SIN CONFIRMAR de ESG-02.1, EST-06/07 y ALM-01.
   - Agrega la **lista de pruebas manuales en el PC de prueba**: zona horaria, unidad D:, ACL de `programa`, actualización, bloqueo de la disposición anterior, táctiles sin MultiDigitizer y cubierta de arranque.
   - Uso previsto: igual que la alpha.1, sin uso clínico.
3. `python tools/entrega/compilar_entrega.py --con-generador`.

Si falla la unión o la suite: `git merge --abort` o revert del merge, estado `Bloqueada` con el motivo, y pasa a L.

Si falla la entrega: el script deshace su commit. Anota el paso y pasa a L.

No hagas push de `dev` ni de etiquetas: el comando de push que imprime el script va al informe.

### L. Limpieza (sin agentes activos)
- Quita los worktrees de `.claude/worktrees/` sin cambios sin commit y ejecuta `git worktree prune`.
- `git branch -d` de las ramas `tanda-16*`, `tanda-17-*` y `worktree-agent-*` unidas a `dev`.

### Z. Cierre (OBLIGATORIO)
- **CLAUDE.md:**
  - ruta de datos y disposición del Setup (INS-02);
  - zona horaria (INS-01);
  - sondas No en uso en monitoreo (SON-01, reemplaza la nota O11);
  - ESG-01 y ESG-02 (reemplaza SAF-01 de S9 en la sección del modo prueba, si está);
  - bitácora central (BIT);
  - arranque (EST-07).
- **Hoja de banco** (`docs/mis_plans/hoja_pruebas_banco/` y `hoja_pruebas_banco_equipo_pruebas.md`, más su generador): sección "Instalación y estación" con las pruebas manuales de K y las verificaciones de SON-01, ESG-01/02, MPR-01, ALM-01 y BIT.
- **Informe R17:**
  - A1;
  - V-01 a V-04;
  - tabla de propiedad;
  - etapas;
  - pruebas tocadas;
  - tabla evento → categoría;
  - hallazgos de R;
  - K (versión, SHA-256 y comando de push);
  - L;
  - evaluación IEC 62304: solicitud de cambio, peligros nuevos o actualizados (ESG-02, INS-02 ACL, BIT-03) y regresión;
  - DECISIONES SIN CONFIRMAR;
  - pruebas manuales pendientes.
- Push de `tanda-17` (solo la rama).
- Índice cuya **primera línea** diga: «Tanda 17: hallazgos instalación I — suite N passed (base M), unida a dev: sí/no, entrega: 1.0.0-alpha.N / no.»
- `docs/informes/tanda17/CERRADO.txt` (fecha, commit del merge, resultado de la suite, versión entregada) y fila `| Z | Hecha | … |` en `estado.md`.
