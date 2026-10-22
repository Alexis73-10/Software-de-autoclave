# Tanda 8: estado

Rama `tanda-8`, creada desde `dev` (d2f7353) en A0. Sesión principal arrancada por el lanzador el 22-oct a las 12:10 (hora de Bogotá).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | e1d8f5e, 23704cb | Línea base de la suite (tanda-8 = dev d2f7353 + docs): **5382 passed, 3 skipped, 3 xfailed** (27 min, con 13 subagentes en paralelo). Log `tanda8/suites/base.log`. |
| H8 | Sin objeto | | La sección "Hallazgos de la instalación del 22-oct" de la instrucción está vacía ("(vacío)"). |
| S1 ★ | Lanzada 12:20 | rama `tanda-8-s1` | Subagente en worktree `.claude/worktrees/agent-*`. |
| S2a ★ | Lanzada 12:20 | rama `tanda-8-s2a` | D8-2.6 a 2.10. |
| S2b ★ | Lanzada 12:20 | rama `tanda-8-s2b` | D8-2.11 a 2.16. |
| N8 | Hecha, unida a `tanda-8` | e8718cf (merge) | Suite de integración tras unir: **5393 p / 3 s / 3 xf** (`suites/integ_n8.log`). |
| R8 ★ | Lanzada 12:20 | rama `tanda-8-r8` | |
| V8a | Lanzada 12:20 | rama `tanda-8-v8a` | ★ solo D8-5.7. |
| E1 | Lanzada 12:20 | rama `tanda-8-e1` | ★ solo D8-3.19. |
| E2 | Lanzada 12:20 | rama `tanda-8-e2` | |
| M8 | Hecha, unida a `tanda-8` | aaa78ae (merge) | Informe `tanda8/M8_mantenimiento.md`. Suite tras unir 5388 p / 3 s / 3 xf (`suites/integ_m8.log`). |
| U8 | Hecha, unida a `tanda-8` | 8bcaeb2 (merge) | Suite de la rama 5378 p / 3 s / 3 xf (= 5382 − 7 retiradas + 3 nuevas). Tras unir, `src/` y `tests/` idénticos a la rama (`git diff tanda-8-u8 tanda-8 -- src tests` vacío): misma suite. |
| L8 | Lanzada 12:20 | rama `tanda-8-l8` | |
| D8 | Lanzada 12:20 | rama `tanda-8-d8` | |
| V8b | Lanzada 12:20 | rama `tanda-8-v8b` | Se une la última. |
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
