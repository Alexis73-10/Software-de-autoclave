# Tanda 8: estado

Rama `tanda-8`, creada desde `dev` (d2f7353) en A0. Sesión principal arrancada por el lanzador el 22-oct a las 12:10 (hora de Bogotá).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | e1d8f5e, 23704cb | Línea base de la suite (tanda-8 = dev d2f7353 + docs): **5382 passed, 3 skipped, 3 xfailed** (27 min, con 13 subagentes en paralelo). Log `tanda8/suites/base.log`. |
| H8 | Sin objeto | | La sección "Hallazgos de la instalación del 22-oct" de la instrucción está vacía ("(vacío)"). |
| S1 ★ | Hecha, unida a `tanda-8` (bd5aa6d). Suite tras unir **5783 p / 6 s / 3 xf** (`suites/integ_s1.log`) | rama `tanda-8-s1` (02c8613) | D8-1. Informe commiteado por la sesión principal (estaba sin commit). Conflictos con S2a: sellado D8-2.10 solo con presión leyendo (DECISIÓN SIN CONFIRMAR, HAZ-S1-05); banco F-12/13 de S1 → F-21/22. |
| S2a ★ | Hecha, unida a `tanda-8` (a5acf3b). Suite tras unir: 5568 p / 4 s / 3 xf / 1 falla intermitente (`test_opciones_qml.py::test_tecnico_entra_a_opciones[PREPARADO-False]`, temporización QML ya vista en la tanda 7; aislada 3/3 en verde) (`suites/integ_s2a.log`) | rama `tanda-8-s2a` (582a48b) | D8-2.6 a 2.10. Revisores 2 vueltas, 0 Altos/Críticos (condición: válvula de seguridad mecánica, pregunta 4). Informe `tanda8/S2a_transiciones_ciclo.md`. |
| S2b ★ | Hecha, unida a `tanda-8` (22fa108). Suite tras unir **5676 p / 5 s / 3 xf** (`suites/integ_s2b.log`) | rama `tanda-8-s2b` (343260d) | D8-2.11 a 2.16. Revisores 2 vueltas, 0 Altos/Críticos (TMG-01 = D8-2.7, cubierto por S2a vía `marcar_sin_datos_tarjeta` → `_cerrar_pausa_sin_datos`, verificado al unir). Migración BD v10. Banco F-12..15 de S2b renumerado a F-17..20. Informe `tanda8/S2b_transiciones_ciclo.md`. |
| N8 | Hecha, unida a `tanda-8` | e8718cf (merge) | Suite de integración tras unir: **5393 p / 3 s / 3 xf** (`suites/integ_n8.log`). |
| R8 ★ | Hecha, unida a `tanda-8` (6e68489). Suite tras unir: en curso (`suites/integ_r8.log`) | rama `tanda-8-r8` (8dca169) | Revisores 4 vueltas, 0 Altos/Críticos. Su alarma SEN-04 se renumeró a **SEN-09** al unir (S1 ya usa SEN-04). Sin migración de BD. |
| V8a | Hecha, unida a `tanda-8` (1369057; i18n por unión de claves). Suite tras unir V8a+L8: en curso (`suites/integ_v8a_l8.log`) | rama `tanda-8-v8a` (002af73) | ★ solo D8-5.7: revisores 0 Altos/Críticos. Banco G-04 y riesgo HAZ-V8A-01 agregados por la sesión principal (fc66e25). D8-5.7 no toca transiciones: sin celdas de planta simulada. |
| E1 | Hecha, unida a `tanda-8` (7ec6980). Suite tras unir: en curso (`suites/integ_e1.log`) | rama `tanda-8-e1` (128925d) | ★ D8-3.19: re-revisión 0 Altos/Críticos. Banco B-12/B-13/D-38 de E1 → B-14/B-15/D-39. 876 pruebas relacionadas en verde tras resolver conflictos (units, serial_link, control_loop, comandos_sistema). |
| E2 | Hecha, unida a `tanda-8` | 1aab868 (merge) | Informe `tanda8/E2_nombres_familia_modelo.md`. Suite tras unir **5438 p / 3 s / 3 xf** (`suites/integ_e2.log`, autoclave de `_suites_t8/base`). |
| M8 | Hecha, unida a `tanda-8` | aaa78ae (merge) | Informe `tanda8/M8_mantenimiento.md`. Suite tras unir 5388 p / 3 s / 3 xf (`suites/integ_m8.log`). |
| U8 | Hecha, unida a `tanda-8` | 8bcaeb2 (merge) | Suite de la rama 5378 p / 3 s / 3 xf (= 5382 − 7 retiradas + 3 nuevas). Tras unir, `src/` y `tests/` idénticos a la rama (`git diff tanda-8-u8 tanda-8 -- src tests` vacío): misma suite. |
| L8 | Hecha, unida a `tanda-8` (255f4cd). No toca `src/` ni `tests/`: misma suite que V8a (`suites/integ_v8a_l8.log`) | rama `tanda-8-l8` (d539e14) | |
| D8 | Hecha, unida a `tanda-8` (0a0dd75, sin conflictos). Suite tras unir: pendiente | rama `tanda-8-d8` (2c8be1e) | P5: 5 funciones muertas retiradas con safety-reviewer. P10/P11: worktrees no quitados (piden `--force`, PREGUNTA). Etiquetas `archivo/*` empujadas. |
| V8b | Relanzada 22:15 (commitear lo pendiente, seguir barrido) | rama `tanda-8-v8b` (6768e33) | Se une la última (antes, unir tanda-8 en su rama y repasar textos nuevos). |
| K8 | Pendiente | | |
| Z | Pendiente | | |

Instrucciones comunes de los subagentes: `tanda8/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-8-<id>`; NO relanzarlos desde cero, revisar su rama y su informe.

## Corte por límite de uso (22-oct ~12:50)
Los subagentes S1, S2a, S2b, V8a, V8b, L8, R8, E2, N8 y E1 se detuvieron por el límite de sesión (se restablece a las 16:00). Su trabajo quedó en sus worktrees `.claude/worktrees/agent-*` (ramas `tanda-8-<id>` o `worktree-agent-*` si no alcanzaron a crearla), en parte sin commit. Al reanudar: NO relanzar desde cero; continuar cada subagente (o, si se perdió, revisar `git status` del worktree, commitear lo suyo y terminar la etapa). U8, M8 y D8 estaban corriendo su suite.


## CAMBIO DE REGLAS (Cristian, 22-oct 12:51), aplicar al reanudar
Lee de nuevo la sección "Modo" de la instrucción y la regla 8 del brief:
- máximo 4 subagentes a la vez;
- los subagentes NO corren la suite completa, solo sus pruebas;
- la suite completa la corre solo la sesión principal al unir;
- revisores solo en las ★.

Al reanudar, retoma primero las etapas con commits (S1, S2a, S2b, N8, R8, V8a, E1 y E2), de a 4. Revisa en cada worktree qué falta, sin rehacer lo commiteado.

## Reanudación (sesión 12:54, reglas nuevas)
- M8 ya estaba unida (aaa78ae). U8 unida (8bcaeb2).
- Se relanzan subagentes de a 4, cada uno CONTINUANDO en su worktree existente (sin rehacer lo commiteado), en este orden: S1, S2a, S2b, N8 → R8, V8a, E1, E2 → L8, D8, V8b.
- Revisores de las ★ (S1, S2a, S2b, R8, V8a 5.7, E1 3.19): si el subagente no puede lanzarlos, los corre la sesión principal antes de unir.

## Reanudación (sesión 17, 16:10, tras el límite de 12:58 a 16:00)
- La sesión 01 de las 12:54 unió N8 (suite 5393 p en verde) y relanzó S1, S2a, S2b y R8, que se cortaron por el límite con trabajo sin commit en sus worktrees.
- E2 terminó con informe commiteado (8124bd1): se une ahora.
- Se relanzan S1, S2a, S2b y R8 continuando en sus worktrees; en cola: V8a, E1, L8, D8, V8b.

## Corte por límite de uso (22-oct ~17:45, se restablece a las 21:00)
- Unidas y en verde: M8, U8, N8, E2, S2a, S2b.
- Cortados a mitad (trabajo guardado en sus worktrees, CONTINUAR, no relanzar de cero): R8 (actualizaba el registro de riesgos tras la 2.ª vuelta de revisores), V8a (editando pantallas para D8-5.2/5.10), E1 (implementando en serial_link/control_loop/server, probablemente D8-3.21).
- S1: tenía las correcciones de la revisión y re-revisiones con 0 Altos/Críticos; faltaba cerrar su informe (revisar `git log`/`git status` del worktree).
- En cola: L8, D8, V8b (V8b se une la última). Después K8 y Z.

## Reanudación (sesión 21:36, tras el límite de 17:45 a 21:00)
- Se relanzan, CONTINUANDO en sus worktrees, S1 (falta commitear correcciones y su informe), R8 (cambios sin commit + informe), V8a (falta el informe; D8-5.6 por confirmar) y E1 (cambios sin commit en serial_link/control_loop/server; faltan D8-3.21, 3.22, 3.20 e informe).
- En cola: L8 (1 commit, falta informe), D8 (2 commits, falta el resto de D8-3.27 e informe), V8b (cambios sin commit; se une la última).

## REGLA NUEVA (Cristian, 22-oct 22:00)
No termines el turno con subagentes activos: en modo `-p` el CLI los mata a los 10 min (pasó a las 21:48). Espera a que terminen, une y lanza el siguiente. Ver regla 3 del prompt.

## Reanudación (sesión 02, 21:58)
- La sesión 01 de las 21:36 terminó su turno con los subagentes en segundo plano y el CLI los detuvo a los 10 min (lección: no terminar el turno con subagentes activos).
- S1: informe commiteado (02c8613) y unida (bd5aa6d); 736 pruebas relacionadas en verde; suite completa en curso.
- Relanzados, continuando en sus worktrees: R8, V8a, E1 y L8. En cola: D8, V8b.

## Reanudación (sesión 22:11)
- La sesión 02 (21:58) murió con R8, V8a, E1 y L8 activos. V8a y L8 alcanzaron a commitear su informe.
- La suite de integración de S1 (`suites/integ_s1.log`, en `_suites_t8/base`) sigue corriendo sola.
- Relanzados 22:15, continuando en sus worktrees: R8, E1, D8 y V8b. La sesión principal une V8a y L8 mientras tanto, y NO termina el turno con subagentes activos.
