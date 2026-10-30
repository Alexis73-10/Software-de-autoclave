# Plan de commits — P1 (F0, cierre de la fase B)

Fecha: 12-oct-2026 · Estado: **para aprobación, sin ningún commit hecho**. Rama `dev`, sin push.

## 0. Diferencias entre el prompt P1 y lo que hay en el árbol

Antes de commitear necesito que decidas estos puntos. No elegí por mi cuenta.

| # | Lo que dice P1 | Lo que hay en el código | Propuesta |
|---|---|---|---|
| C-1 | 4 commits: (a) E0/E1, (b) fase B, (c) ARR-01, (d) docs. | Falta la **intro de arranque** (`planeacion_animacion_arranque.md`, hecha en esta sesión): `IntroArranque.qml`, `progreso_arranque.py`, PNG, `tools/generar_assets_arranque.py`, bloques de `Main.qml`, `app.py`, `es.json`, `Colores.qml` y 2 pruebas. ARR-01 depende de ella: `Reposo.qml` usa el token `Colores.textoFechaReposo` y una prueba de ARR-01 es de la intro. | Agregar el commit **(b2) intro de arranque** entre (b) y (c). |
| C-2 | En `catalogo_alarmas.md` y `planeacion_arranque_y_modo_sin_bd.md`, separar con `git add -p` los bloques de E0/E1 de los de la fase B. | Los dos son documentación y P1 los pone en (d). En el catálogo, el diff no previo a la fase B no es de E0/E1: es la renumeración y las §8–§9 de la Parte A de alarmas. En el plan, lo no previo son tus ediciones de D-E. | Ambos archivos **completos en (d)**, sin separar, porque ningún bloque de código depende de ellos. Si prefieres el catálogo dividido (fase B / resto), lo separo dentro de (d) en dos commits. |
| C-3 | Probar cada commit con `git stash --keep-index`. | `--keep-index` no guarda los archivos sin versionar. Al probar (a), seguirían presentes `backend/arranque/`, las pruebas de la fase B y las de la intro, y la suite no probaría ese commit solo. Con `--include-untracked` se guardarían ~60 archivos de trabajo sin commit, con riesgo si algo falla a mitad. | Probar cada commit en un **`git worktree` aislado** (`git worktree add <tmp> <commit>`), con `PYTHONPATH=<tmp>/src`. La instalación editable es una ruta en `.pth`, así que el `PYTHONPATH` tiene prioridad (lo verifico antes con `import autoclave; autoclave.__file__`). Prueba exactamente el commit y no toca el árbol de trabajo. |
| C-4 | En `context.py`, separar con `git add -p`. | La fase B reescribió `BackendContext` completo: `add -p` no puede dejar en (a) el constructor viejo con los bloques E0/E1. | Para (a), construyo la versión intermedia (HEAD + los 5 bloques E0/E1, idéntica a la que había antes de la fase B) y la paso al índice con `git hash-object -w` + `git update-index --cacheinfo`, sin tocar el archivo en disco. Lo mismo para `Arranque.qml` y `test_intro_arranque_qml.py` en (b2) (ver §2). |
| C-5 | (d) "planes, informes y catálogo". | Sin versionar hay docs de **otros trabajos**: firmware 1.5 / E6, fin de ciclo y puertas, sistema de alarmas Parte A (su spec y su plan están en la rama `alarmas-parte-a`, sin unir) y `analisis_sistema_alarmas.md`. | En (d) solo los docs de estos commits (lista en §1). Los demás quedan fuera, igual que `.claude/`, `docs/catalogo_alarmas.2026-09-18.bak.md` y `src/autoclave/images/icono autoclave.jpg`. |

## 1. Commits, en orden

### (a) E0/E1 y buzer — `feat(e0-e1): lecturas inválidas, perfil por equipo, paro NC y vigencia de DI`
Código (completos):
- `config/calibration.yaml`
- `core/runtime/status.py`
- `devices/buzer/buzer.py`
- `devices/io/set_io.py`
- `devices/paro_emergencia/paro_emergencia.py`
- `devices/puertas/door_factory.py`
- `devices/puertas/simple_door.py`
- `devices/pump/pump.py`
- `installation/profile.py`
- `installation/storage.py`
- `installation/wizard.py`
- `protocols/serial_link.py`
- `services/domain/loop/control_loop.py`
- `simulador/servidor.py`
- `state_machine/state_machine.py`
- `state_machine/states/ciclo.py`
- `state_machine/states/falla.py`
- `state_machine/states/hibernacion.py`
- `state_machine/states/preparacion.py`
- `state_machine/states/preparado.py`
- `ui_pyside/views/entrdas_salidas/io_temp.py`
- `ui_pyside/views/params_ciclo/params_ciclo.py`

Nuevos:
- `core/runtime/lectura.py`
- `installation/cambio_perfil.py`
- `tools/declarar_entradas_suministro.py`
- `tools/declarar_sondas_temperatura.py`

Pruebas modificadas:
- `test_ciclo_drenaje`, `test_control_loop_f0`, `test_control_loop_set_active_cycle`, `test_control_loop_test_mode`
- `test_preparacion_ejecutor_paralelo`, `test_preparado_suministro`, `test_puertas_fallas_endpoints`, `test_sin_temp_chaqueta`

Pruebas nuevas:
- `test_adenda_decisiones`, `test_adenda_enlace_paro`, `test_adenda_estados`, `test_adenda_herramientas_perfil`, `test_declarar_entradas_suministro`
- `test_e0_lecturas_invalidas`
- `test_e1_apertura_automatica_sin_actuador`, `test_e1_integracion_inicio_ciclo`, `test_e1_paro_emergencia_nc`, `test_e1_puertas_perfil`, `test_e1_simple_door_lectura_invalida`, `test_e1_supply_inputs`, `test_e1_supply_inputs_loop_status`

Archivos mixtos, solo los bloques E0/E1:
- `backend/context.py` (versión intermedia, C-4): import de `entradas_no_monitoreadas`/`sondas_no_vigiladas`, función `avisar_entradas_no_monitoreadas()`, su llamada en el constructor, `SetOutput(..., profile=self.profile)` y `ControlLoop(..., profile=self.profile)`.
- `backend/server.py` (`add -p`), hunks:
  - `@@ -19,0 +23`: import de `entradas_no_monitoreadas`/`sondas_no_vigiladas`.
  - `@@ -585`: quita `drenaje_camara`.
  - `@@ -631`: `entradas_no_monitoreadas`/`sondas_no_vigiladas` en `/status`.
  - `@@ -1273`: `_rechazar_si_sin_datos_vigentes`.
  - `@@ -1288` y `@@ -1391`: sus dos llamadas en el modo prueba.

Mensaje: cubre E0 (CR-FC-01), E1-1 a E1-5, adenda A-1 a A-9 y D-16, `temp_drenaje` en la posición 4 y los temporizadores del buzzer con `time.monotonic()`.

### (b) Fase B — `feat(arranque): backend por etapas con GET /arranque (ARR-01 del plan de arranque, BAR-01, D-E)`
- Nuevo: `backend/arranque/` (`__init__`, `registro`, `secuencia`, `sin_bd`).
- `backend/context.py`: el resto (de la versión intermedia a la actual).
- `backend/server.py`, hunks restantes:
  - `@@ -14`: imports de arranque.
  - `@@ -42`/`-44`: apagado tolerante.
  - `@@ -51`/`-53`: registro, compuerta 503, `/arranque` y 503 sin BD.
  - `@@ -267`: aviso de paro fuera del import.
  - `@@ -1014`: `/cycle/start` sin BD.
- `backend/main.py`, `devices/factory/factory.py` (`build_serial`/`build_doors_cfg`) y `core/managers/cycle_manager.py` (`errores_carga`).
- Pruebas: `test_backend_autenticacion.py` (los 3 ajustes) y las nuevas `test_registro_arranque`, `test_secuencia_arranque`, `test_endpoint_arranque` y `test_arranque_sin_tarjeta`.

Mensaje: cubre BAR-01, D-1 a D-8 de la propuesta, D-E (`ARR_SIN_ES`), puerto enlazado antes del serial, códigos `ARR_*` y provisional sin BD (409 en `/cycle/start`, `OPERANDO_SIN_BD`).

### (b2) Intro de arranque — `feat(ui-qml): intro de arranque "del vapor a la precisión" con progreso simulado (ARR-03 provisional)` *(C-1)*
- Nuevos: `qml/Pantallas/IntroArranque.qml`, `bridge/progreso_arranque.py`, `assets/fondos/halo_arranque.png`, `assets/fondos/voluta_vapor.png`, `tools/generar_assets_arranque.py`, `tests/test_progreso_arranque.py` y `tests/test_intro_arranque_qml.py`. Esta última en la versión con `hay("Arranque")` (C-4); (c) la cambia a `Reposo`.
- `qml/Main.qml` (`add -p`): hunks `@@ -44` (propiedades) y `@@ -253` (Loader de la intro y capa `alarmaArranque`).
- `ui_qml/app.py`, `assets/textos/es.json` y `qml/Tema/Colores.qml`, completos.
- `qml/Pantallas/Arranque.qml`: solo `color: Colores.textoFechaReposo` (C-4; en disco el archivo ya no existe).
- `docs/diseno/referencias/intro_arranque_preview.mp4` (1,3 MB, referencia visual del plan). Si prefieres no versionar el video, queda fuera.

### (c) Renombrado ARR-01 — `refactor(ui-qml): Arranque.qml → Reposo.qml (ARR-01 de la animación)`
- Borra `Pantallas/Arranque.qml` y agrega `Pantallas/Reposo.qml` (git lo verá como renombrado).
- `qml/Main.qml`: hunks `@@ -69` (comentario) y `@@ -260` (instancia `Reposo {`).
- `Componentes/FondoApp.qml` (comentario).
- Las 7 pruebas: `test_intro_arranque_qml`, `test_main_menu_principal_qml`, `test_navegacion_ciclo_en_curso`, `test_navegacion_sesion_qml`, `test_opciones_qml`, `test_reconocer_falla` y `test_ui_qml_app`.

### (d) Documentación — `docs: arranque por etapas, barra real, intro, E0/E1 y catálogo de alarmas`
- `docs/catalogo_alarmas.md` y `docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md` completos (C-2).
- `docs/mis_plans/planeacion_protocolo_serial_esp32.md` (D-02).
- Planes nuevos: `planeacion_barra_arranque_real.md`, `prompts_barra_arranque.md`, `planeacion_animacion_arranque.md`, `instruccion_claude_code_e0_e1.md` e `instruccion_claude_code_e0_e1_adenda.md`.
- Informes nuevos: `informe_e0_e1.md`, `informe_animacion_arranque.md`, `propuesta_fase_b_arranque_backend.md`, `informe_fase_b_arranque_backend.md`, `informe_fase_b_cierre.md` y este plan.
- Fuera (C-5): `instruccion_claude_code_e6_firmware.md`, `planeacion_firmware_1_5.md`, `planeacion_fin_de_ciclo_y_puertas.md`, `informe_verificaciones_fin_de_ciclo.md`, `analisis_sistema_alarmas.md`, `docs/superpowers/{specs,plans}/…sistema-alarmas-parte-a…`, el `.bak` del catálogo, `.claude/` y el `.jpg`.

Todos los mensajes terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 2. Verificación después de cada commit
1. `git worktree add <scratchpad>/wt <commit>`.
2. `PYTHONPATH=<wt>/src python -m pytest -q tests` desde `<wt>`. Antes compruebo que `autoclave.__file__` apunta al worktree.
3. Debe pasar sin fallos. Si un commit intermedio falla porque dos bloques no se pueden separar, **paro y te digo cuáles son**, sin forzar nada.
4. `git worktree remove`. El árbol de trabajo principal no se toca en ningún momento.
5. Al final, `git status` debe mostrar solo lo que dejé fuera a propósito (C-5).

Duración estimada: ~10 min de suite por commit, ~50 min en total.
