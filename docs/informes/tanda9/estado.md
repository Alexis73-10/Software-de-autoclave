# Tanda 9: estado

Rama `tanda-9`, creada desde `dev` (1ff5afa, contiene `tanda-8`) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 00:10 (hora de Bogotá).

Precondición A0: `tanda8/estado.md` tiene `| Z | Hecha |` y `git merge-base --is-ancestor tanda-8 dev` = sí. Cumplida.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | 090a8bf | Línea base de la suite en `_suites_t9/base` (`dev` 1ff5afa): **6201 passed, 7 skipped, 3 xfailed** (24 min, `suites/base.log`). |
| S9 ★ | Pendiente | | |
| B9 ★ | Terminada en su rama, espera a que se una S9 | `tanda-9-b9` (581710a) | Causa: `AdvancedDoor.update()` reenvía `cerrar_on`/`bloquear_on` durante el paro (firmware y reenvío descartados). 2 Altos de revisión que son decisión de Cristian (D9-9 los pide así o son preexistentes): ver informe. |
| E9 | Hecha, unida a `tanda-9` (bafc067). Suite tras unir: en curso (`suites/integ_e9.log`) | `tanda-9-e9` (59db092) | Refresco de config de fábrica lo hace el programa al arrancar (E9-2, DECISIÓN SIN CONFIRMAR). Absorbe la rama `instalador-setup`. |
| A9 | Pendiente | | |
| P9 | Pendiente | | |
| C9 | Pendiente | | |
| X9 (★ D9-13.3) | Pendiente | | |
| K9 | Pendiente | | |
| Z | Pendiente | | |

Instrucciones comunes de los subagentes: `tanda9/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-9-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (00:10)
- 00:2x: lanzados S9, B9, E9 y A9 (4 subagentes, worktrees `.claude/worktrees/agent-*`, ramas `tanda-9-<id>`). En cola: P9, C9, X9. La sesión principal NO termina el turno con subagentes activos.
- B9 y E9 terminaron. Lanzados P9 y C9. E9 unida; suite de integración en `_suites_t9/base`.
