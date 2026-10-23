# Tanda 10: estado

Rama `tanda-10`, creada desde `dev` (748337a, contiene `tanda-9` cerrada) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 10:49 (hora de Bogotá).

Precondición A0: `tanda9/estado.md` tiene `| Z | Hecha |` y `dev` contiene la tanda 9 cerrada (fb32ad4, registro del push). Cumplida. La rama `tanda-9` tiene además 2 commits posteriores al cierre (Entrega E: 376eeb5 y cafb06e, sin push); se unieron a `tanda-10` (e391ffe) porque la compilación de esta tanda los necesita (DECISIÓN SIN CONFIRMAR A0-1).

**DECISIÓN SIN CONFIRMAR A0-2:** la letra **E** ya está usada (etiqueta `inst-2026-10-23-e`, `entrega/2026-10-23_e/`, Setup 1.0.0-e ya en la USB). Reusarla exigiría mover la etiqueta (`--force`, prohibido) y sobrescribir la entrega. La compilación de esta tanda (D10-5) se llama **F**: `inst-<fecha>-f`, `entrega/<fecha>_f/`, `Autoclave_Setup_1.0.0-f.exe`, y el LEEME describe «Actualizar E → F» (y D → F, por si el equipo aún tiene la D).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | En curso | | Línea base en `_suites_t10/base` (`tanda-10` e391ffe), `suites/base.log`. |
| G10 | Pendiente | | |
| T10 | Pendiente | | |
| W10 | Pendiente | | |
| U10a | Pendiente | | |
| U10b | Pendiente | | |
| K10 | Pendiente | | |
| Z | Pendiente | | |

Instrucciones comunes de los subagentes: `tanda10/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-10-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (10:49)
- A0: rama creada, Entrega E unida, línea base lanzada.
