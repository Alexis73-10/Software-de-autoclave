# Tanda 9: estado

Rama `tanda-9`, creada desde `dev` (1ff5afa, contiene `tanda-8`) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 00:10 (hora de Bogotá).

Precondición A0: `tanda8/estado.md` tiene `| Z | Hecha |` y `git merge-base --is-ancestor tanda-8 dev` = sí. Cumplida.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | 090a8bf | Línea base de la suite en `_suites_t9/base` (`dev` 1ff5afa): **6201 passed, 7 skipped, 3 xfailed** (24 min, `suites/base.log`). |
| S9 ★ | Código, pruebas y documentos commiteados en su rama; faltan revisores e informe (sesión 10) | `tanda-9-s9` (57b2844) | La sesión 01 se cortó por límite de uso con S9 sin informe. Revisores ★ lanzados desde la sesión principal. |
| B9 ★ | Terminada en su rama, espera a que se una S9 | `tanda-9-b9` (581710a) | Causa: `AdvancedDoor.update()` reenvía `cerrar_on`/`bloquear_on` durante el paro (firmware y reenvío descartados). 2 Altos de revisión que son decisión de Cristian (D9-9 los pide así o son preexistentes): ver informe. |
| E9 | Hecha, unida a `tanda-9` (bafc067). Suite tras unir: **6236 passed, 7 skipped, 3 xfailed** (`suites/integ_e9.log`) | `tanda-9-e9` (59db092) | Refresco de config de fábrica lo hace el programa al arrancar (E9-2, DECISIÓN SIN CONFIRMAR). Absorbe la rama `instalador-setup`. |
| A9 | Hecha, unida a `tanda-9` (98c9897). Suite tras unir: en curso (`suites/integ_a9.log`) | `tanda-9-a9` (4b69be7) | Informe sin commitear al corte: la sesión 10 corrió la pasada final (435 passed) y lo commiteó. |
| P9 | Terminada en su rama, espera unión | `tanda-9-p9` (8ec67c6) | |
| C9 | Terminada en su rama, espera unión | `tanda-9-c9` (de24991) | |
| X9 (★ D9-13.3) | En curso (subagente lanzado en la sesión 10) | `tanda-9-x9` | |
| K9 | Pendiente | | |
| Z | Pendiente | | |

Instrucciones comunes de los subagentes: `tanda9/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-9-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (00:10)
- 00:2x: lanzados S9, B9, E9 y A9 (4 subagentes, worktrees `.claude/worktrees/agent-*`, ramas `tanda-9-<id>`). En cola: P9, C9, X9. La sesión principal NO termina el turno con subagentes activos.
- B9 y E9 terminaron. Lanzados P9 y C9. E9 unida; suite de integración en `_suites_t9/base`.

## Sesión 10 (02:35, tras el límite de uso)
- La sesión 01 se cortó a la 01:05 por límite de uso (subagentes S9, A9, P9 y C9 muertos con ella). P9 y C9 alcanzaron a commitear su informe; A9 y S9 no.
- A9: pasada final de pruebas y commit del informe (4b69be7); unida a `tanda-9` (98c9897); suite en `_suites_t9/base`.
- S9: documentos commiteados (57b2844); revisores `safety-reviewer` y `timing-auditor` lanzados desde la sesión principal sobre `_suites_t9/s9_diff_src.patch`.
- X9 lanzado (subagente, worktree propio).
