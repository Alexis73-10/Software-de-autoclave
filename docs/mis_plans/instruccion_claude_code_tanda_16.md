# Instrucción maestra para Claude Code — Tanda 16 combinada (sin supervisión)

> Se lanza con `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_tanda.ps1 -Tanda 16` (`claude -p`, que se relanza si se corta). Siempre REANUDA desde `docs/informes/tanda16/estado.md`.

## Alcance y fuentes

Fuentes de verdad, COMPLETAS:
- `docs/mis_plans/decisiones_tanda_16.md` (prevalece);
- `docs/mis_plans/planeacion_control_vapor_chaqueta.md` (VCH);
- `docs/mis_plans/planeacion_tanda_14_pendientes.md` (P1–P8 y P10; P9 ya está hecho).

Alcance:
- tanda 14: P1–P8 y P10;
- VCH completo;
- D-CHQ;
- DEU-01;
- PRG-01.

Prioridad: velocidad, sin sacrificar seguridad (código Clase C).

## Modo de ejecución
- La sesión principal hace A0, F, I, K, L y Z.
- **Hasta 5 subagentes a la vez:**
  - en V (solo lectura);
  - en P (código, cada uno en su worktree y su rama);
  - en R (solo lectura).
- Los subagentes NO corren la suite completa: solo sus pruebas y las de los módulos que tocan.
- La sesión principal sí corre la suite completa, con `pytest tests -n auto`. Lo que falle solo en paralelo se repite en serie.

## 0. Reglas
1. Rama `tanda-16` desde `dev`.
   - Estado en `docs/informes/tanda16/estado.md` (tabla `| Etapa | Estado | Nota |`), actualizado después de cada commit, con el último commit.
   - Informe único: `docs/informes/tanda16/R16_informe.md`.
   - Índice: `docs/informes/informe_tanda_<fecha>_t16.md`.
2. Git:
   - Nunca `main`, `--force`, `git add -A`, `git push --delete`, `git branch -D` ni reescritura del historial. No toques los stash.
   - No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, `_suites_t11/`.
   - Prefijos de commit: `feat(t16)`, `fix(t16)`, `test(t16)`, `docs(t16)`.
3. Pruebas:
   - Prohibido borrar, saltar (`skip`/`xfail`) o relajar una prueba existente.
   - Solo se permiten dos cosas:
     1. fijar en modo cámara las pruebas de las dos fases y de CICLO (D13);
     2. actualizar una aserción que cambia por una decisión de la tanda 14 (P1, P3, P5, P6, P7), citando la decisión en un comentario.
   - Cada prueba tocada va al informe.
4. Prohibido:
   - hardware o puertos COM;
   - firmware;
   - ejecutar `.ps1` o el Setup;
   - instalar software del sistema;
   - borrar archivos sin seguimiento de git;
   - leer o imprimir el archivo de secretos de activación.

   Autorizado: `tools/entrega/compilar_entrega.py` en K (solo compila).
5. Todo temporizador nuevo usa `time.monotonic()`. Presión siempre en kPa absolutos. Psat/Tsat solo con `autoclave.core.runtime.steam`.
6. Textos visibles en español e inglés, con el mecanismo i18n existente (catálogo de alarmas, `motivos_fase`, `i18n/es.json` y `en.json`).
7. Ante ambigüedad: lo más seguro y reversible, anotado como «DECISIÓN SIN CONFIRMAR». Todo en español: código nuevo, informes y commits.

## 1. Etapas

### A0. Precondición (sesión principal)
Deben cumplirse:
- `git merge-base --is-ancestor tanda-15 dev`;
- `git merge-base --is-ancestor versionado dev`;
- `git status --porcelain --untracked-files=no` vacío.

Si falla algo: fila `| A0 | Esperando | <qué falta> |` y TERMINA.

Si pasa:
1. Rama `tanda-16`.
2. Commit `docs(t16)` con los tres documentos fuente, esta instrucción y el prompt.
3. Línea base: pruebas recolectadas y resultado de la suite en `docs/informes/tanda16/base_suite.txt`.

### V. Verificaciones (hasta 5 subagentes de solo lectura, sin commits)
Cada verificación anota archivo:línea en el informe.
- **V-01:** función del perfil que dice si la salida `vapor_chaqueta` está habilitada y el sensor `pres_chaqueta` asignado. Si no existe, se creará en F3, en `autoclave/installation/profile.py`, junto a `entrada_requerida`.
- **V-02:** si FALLO (`protocolo_fallo.py`), cancelación y paro de emergencia cierran `vapor_camara` y `vapor_chaqueta`.
- **V-03:** dónde se definen, migran y muestran en la UI los parámetros de programa y los de equipo (`global_params.json`).
- **V-04:**
  - pruebas que asumen `vapor_camara` como actuador;
  - pruebas que cambian con P1, P3, P5, P6 o P7.
- **V-05:**
  - todos los usos de `FONDO_ESCALA`, suministro, `PRESION_ALIVIO_CAMARA` y `PRESION_ALIVIO_CHAQUETA` (DEU-01);
  - dónde se publican las lecturas vivas (P7);
  - dónde se asignan los roles de sensor y dónde arranca el ciclo (PRG-01);
  - pantalla final, historial, ticket, PDF y correo, para P4.

Con V, la sesión principal escribe en `estado.md` la **tabla de propiedad de archivos** de la etapa P: cada archivo tiene un solo dueño. Un archivo que necesiten dos subagentes lo trabaja la sesión principal en F o en I.

### F. Fundaciones (sesión principal, un commit por punto, antes de lanzar P)
Fijan los contratos para que los subagentes no se pisen.

**F1. Parámetros de equipo** en `global_params.json`, con lectores que recortan al rango y usan el defecto si falta o no es numérico (mismo patrón que `_pausa_max_s`). Pruebas de recorte y defecto.
- VCH: `timeout_aislamiento_camara`, `max_aislamientos_camara`, `ventana_aislamientos_camara`.
- `presion_max_chaqueta_control`, según D-CHQ: defecto 375, rango 300 a `presion_alivio_chaqueta − 10`.
- DEU-01: los 4 límites, con su regla de coherencia.

**F2. Alarmas y textos.** Con los siguientes números libres del catálogo, y con textos es/en y entrada en `motivos_fase` donde aplique:
- dos FALLO de aislamiento (VCH §4.5);
- FALLO por tope de reinicios de exposición (P5);
- aviso no bloqueante de VCH-CHQ;
- el código de PRG-01 si hace falta (D-PRG-1).

Además, las claves i18n de los parámetros nuevos.

**F3. Módulos compartidos**, con sus pruebas unitarias:
- `DebounceAcumulado` (P6: confirma con N s acumulados dentro de una ventana de M s, monotónico).
- El componente de aislamiento VCH-AIS (por ejemplo `cycle_phases/aislamiento_camara.py`):
  - estado;
  - salida con histéresis y 3 s sostenidos;
  - duración del aislamiento en curso;
  - historial en ventana móvil.
- La función de modo chaqueta/cámara de V-01.

**F4. Contratos en el estado del ciclo** (`ciclo.py` y el objeto de estado, solo lo mínimo):
- `estado.aislamiento_camara`: una instancia por ciclo. Se crea y reinicia en `CicloState.reset()` para que el historial cubra las dos fases.
- `estado.inhibir_vapor_chaqueta` (bool): lo escribe CICLO y lo leen las fases antes de encender.
- `estado.no_conforme` y `estado.motivo_no_conforme`: se publican desde la bandera `_no_conforme` existente.
- `estado.modo_vapor` (`"chaqueta"`/`"camara"`, o `None` fuera de ciclo).

**F5.** `testpaths = ["tests"]` en `pyproject.toml`.

### P. Implementación en paralelo (5 subagentes, `isolation: worktree`)
Cada subagente:
- trabaja en la rama `tanda-16-<s>`, creada desde `tanda-16` después de F;
- toca solo sus archivos de la tabla de propiedad;
- no edita `i18n/*.json` ni el catálogo de alarmas: los textos nuevos los deja en `docs/informes/tanda16/i18n/<s>.json` (`{"es": {...}, "en": {...}}`) y la sesión principal los une en I;
- pone sus pruebas en `tests/test_t16_<s>.py`, con el marcador `req`;
- hace commit en su rama;
- responde en español con: archivos tocados, pruebas nuevas y tocadas, y DECISIONES SIN CONFIRMAR.

**s1 · ESTERILIZACION** (`esterilizacion.py`):
- VCH E: modo, actuador, aislamiento con `p_control_max`/`histeresis_cierre_camara` en lugar del techo de RECUPERACION y del techo de PWM (solo en modo chaqueta), `vapor_camara` ON en cada tick sin aislamiento, sin lectura → `vapor_chaqueta` OFF y `vapor_camara` abierta, COMPLETADO/FALLO → ambas OFF.
- Respeta `estado.inhibir_vapor_chaqueta`.
- P5: tope de reinicios.
- P6: `DebounceAcumulado` en las 4 fallas, en C-03 y en la confirmación de excursión de C-13.
- SAF-05.
- P8: la excursión con pérdida de lectura.
- FALLOs del aislamiento.
- F0 y la exposición siguen durante el aislamiento.
- Modo cámara: sin cambios, salvo los de P5, P6 y SAF-05.

**s2 · CALENTAMIENTO y plausibilidad** (`calentamiento.py` y el publicador de lecturas vivas de V-05):
- VCH C: modo registrado en el log, `controla_vapor_chaqueta`, `vapor_camara` ON, actuador `vapor_chaqueta`, aislamiento con `p_techo`, `_apagar_salidas()` sin cerrar `vapor_camara` en COMPLETADO en modo chaqueta.
- Respeta `inhibir_vapor_chaqueta`.
- P3.
- P7, con log del valor crudo una vez por episodio.

**s3 · CICLO** (`states/ciclo.py`, `protocolo_fallo.py`, rutas de cancelación y paro):
- VCH Q: `_mantener_chaqueta()` no actúa sobre `vapor_chaqueta` mientras la fase tenga `controla_vapor_chaqueta`, salvo SUM-06 y el corte; retoma al terminar ESTERILIZACIÓN.
- Corte único D-CHQ/SAF-09: `P_chaqueta ≥ presion_max_chaqueta_control` → `vapor_chaqueta` OFF siempre. En modo chaqueta, además, el aviso VCH-CHQ. Sin lectura en modo chaqueta → OFF.
- El corte prevalece en el mismo tick: CICLO fija `inhibir_vapor_chaqueta` antes de `fase.update()` y vuelve a forzar OFF después.
- `_registrar_consigna_chaqueta()` dentro de `try`.
- Correcciones de V-02.
- Puerta de inicio de ciclo de PRG-01, si está en sus archivos.

**s4 · PROGRAMAS Y LÍMITES** (`catalogo_parametros.py`, `cycle_manager.py`, `cycles/factory/*.json`, `cycles/user/*.json`, `rutas/programas.py` y UI de parámetros):
- P1: regla de coherencia y mensaje con el mínimo; programas de fábrica de 134 °C con 15.
- P2: migración, condicionada según D-14.2.
- Parámetros de programa nuevos: `histeresis_cierre_camara` en `calentamiento` y `esterilizacion`, y `max_reinicios_exposicion`. Van en los programas de fábrica, en la migración (solo agrega la clave) y en la UI.
- DEU-01:
  - todo lo que usa las constantes lee los límites del equipo;
  - UI de Parámetros del equipo con los límites y los parámetros VCH, con auditoría;
  - `errores_coherencia`/`errores_programa` con los valores del equipo.
- PRG-01 al asignar roles.

**s5 · NO CONFORME visible** (rutas de estado e historial, QML de la pantalla final y del historial, ticket, PDF y correo):
- P4 según D-14.4:
  - `/status` y el historial exponen `no_conforme` y su motivo;
  - franja roja (es/en);
  - segundo botón de reconocimiento, auditado con el usuario, que bloquea CONFIRMAR hasta pulsarlo;
  - «NO CONFORME» en el encabezado del historial, el ticket, el PDF y el correo.
- Puerta de inicio de PRG-01, si cae en sus archivos.

### I. Integración (sesión principal)
1. Une las ramas en `tanda-16` con `--no-ff`, en el orden s4, s3, s1, s2, s5. Si hay conflictos, resuélvelos conservando las dos intenciones y anótalos.
2. Une los fragmentos i18n en `es.json`/`en.json`.
3. Pruebas de VCH §8, puntos 1–9, de punta a punta, en `tests/test_t16_integracion.py`, si no quedaron cubiertas.
4. Suite completa en verde. Recolectadas = base + nuevas.

### R. Revisión (5 subagentes de solo lectura, en paralelo)
Hay un revisor por área (s1…s5), sobre `git diff dev...tanda-16 -- <rutas del área>`.

Prompt común: «Es código de seguridad Clase C de un autoclave. Busca:
- vapor sin control (`vapor_chaqueta` encendida sin techo efectivo, `vapor_camara` reabierta durante un aislamiento, el corte de chaqueta vencido por la orden de la fase);
- `vapor_camara` cerrada en la transición CALENTAMIENTO → ESTERILIZACIÓN;
- cambios no pedidos en modo cámara;
- reloj de pared en temporizadores;
- F0 o exposición detenidos por el aislamiento;
- dos controladores sobre una salida en el mismo tick;
- debounce que no confirma o que confirma de más;
- migraciones que pierden datos o no auditan;
- límites de DEU-01 que no se propagan a todos sus usos;
- NO CONFORME que se puede confirmar sin reconocimiento;
- pruebas que pasan sin probar lo que dicen.

No ejecutes la suite completa. Responde en español con hallazgos `V16-<s>-xx` (archivo:línea, severidad alta/media/baja, motivo) o "sin hallazgos".»

Corrige los hallazgos válidos (commit) y repite la suite. Un hallazgo alto que no puedas corregir bloquea K.

### K. Unión y entrega (solo con la suite en verde y sin hallazgos altos abiertos)
1. Ejecuta `git checkout dev` y `git merge --no-ff tanda-16 -m "Merge tanda-16 en dev"`, y luego la suite completa.
2. Commit `docs(t16)` en `dev` con `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md`:
   - parte de la alpha.1;
   - marca como corregidas AN-01 a AN-08, AN-10 y AN-11;
   - agrega VCH-01 (ALTA: los parámetros de las dos fases deben reajustarse en banco con la chaqueta antes de liberar) y VCH-02;
   - agrega las DECISIONES SIN CONFIRMAR de P1, P3 y P6, pendientes de los datos del banco;
   - uso previsto: igual que la alpha.1, sin uso clínico;
   - incluye la prueba de humo.
3. `python tools/entrega/compilar_entrega.py --con-generador`.

Si falla la unión o la suite: `git merge --abort` o revert del merge, estado `Bloqueada` con el motivo, y pasa a L.

Si falla la entrega: el script deshace su commit. Anota el paso y pasa a L.

No hagas push de `dev` ni de etiquetas: el comando de push que imprime el script va al informe.

### L. Limpieza de git (P10, D-14.10; sin agentes activos)
- Quita los worktrees de `.claude/worktrees/` sin cambios sin commit (los que tengan cambios solo se listan) y ejecuta `git worktree prune`.
- `git branch -d` de las `tanda-*` y `worktree-agent-*` unidas a `dev`.
- Etiquetas `archivo/<rama>` para `feature/roles-sensor-temperatura`, `worktree-anuncios-voz` e `instalador-setup`, y `-d` si git lo permite.
- Informe de los 3 commits de `main` que no están en `dev`, sin integrarlos.
- Lista de las remotas `origin/tanda-*`.
- `/data/` al `.gitignore` (commit en `dev`, después de K).

### Z. Cierre (OBLIGATORIO)
- **CLAUDE.md:**
  - sección «CONTROL DE VAPOR POR CHAQUETA (tanda 16)»;
  - nota C-08: la histéresis de 2 kPa rige solo en modo cámara;
  - actualizar los defectos y comportamientos que cambian con P1, P3, P5, P6 y P7, el corte de chaqueta único y DEU-01 (los límites ya no son constantes).
- **Hoja de banco** (`docs/mis_plans/hoja_pruebas_banco/` y `hoja_pruebas_banco_equipo_pruebas.md`, más su generador si existe). Sección VCH:
  - válvulas por fase;
  - golpe inicial (VCH-02);
  - sobrepaso y tiempo de calentamiento frente al control anterior (VCH-01);
  - aislamientos;
  - datos para confirmar P1, P3 y P6: temperatura real con la presión en el techo, diferencia Principal–Referencia y oscilación pico a pico.
- **Informe R16:**
  - respuestas de V-01 a V-05;
  - tabla de propiedad de archivos;
  - tabla de etapas;
  - pruebas tocadas;
  - códigos asignados;
  - hallazgos de R y su resolución;
  - resultado de K (versión, SHA-256 y comando de push);
  - resultado de L;
  - evaluación IEC 62304: solicitud de cambio, peligros nuevos o actualizados (VCH §7, SAF, NO CONFORME, DEU-01) y regresión;
  - DECISIONES SIN CONFIRMAR.
- Push de `tanda-16` (solo la rama).
- Índice cuya **primera línea** diga: «Tanda 16: pendientes 14 + VCH + PRG-01 + DEU-01 — suite N passed (base M), unida a dev: sí/no, entrega: 1.0.0-alpha.N / no.»
- Fila `| Z | Hecha | … |` en `estado.md`.
