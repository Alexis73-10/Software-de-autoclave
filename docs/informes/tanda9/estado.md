# Tanda 9: estado

Rama `tanda-9`, creada desde `dev` (1ff5afa, contiene `tanda-8`) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 00:10 (hora de Bogotá).

Precondición A0: `tanda8/estado.md` tiene `| Z | Hecha |` y `git merge-base --is-ancestor tanda-8 dev` = sí. Cumplida.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | 090a8bf | Línea base de la suite en `_suites_t9/base` (`dev` 1ff5afa): **6201 passed, 7 skipped, 3 xfailed** (24 min, `suites/base.log`). |
| S9 ★ | Hecha, unida a `tanda-9` (3044b7f y ce8fa3a). Suite: **6575 passed, 8 skipped, 3 xfailed** (`suites/integ_s9_r3.log`) | `tanda-9-s9` (4e4e9e9) | Revisión ★ en 4 pasadas (safety, timing, sensor-role): sin Altos/Críticos propios abiertos. Alto anterior (CICLO con AI vencida) como PREGUNTA 18. |
| B9 ★ | Hecha, unida a `tanda-9` (82da39d). Suite: **6606 passed, 10 skipped, 3 xfailed** (`suites/integ_b9.log`) | `tanda-9-b9` (581710a) | 2 Altos aceptados por el revisor como decisión de Cristian (D9-9) o anteriores: ver informe y DECISIONES_PARA_REVISAR. |
| E9 | Hecha, unida a `tanda-9` (bafc067). Suite tras unir: **6236 passed, 7 skipped, 3 xfailed** (`suites/integ_e9.log`) | `tanda-9-e9` (59db092) | Refresco de config de fábrica lo hace el programa al arrancar (E9-2, DECISIÓN SIN CONFIRMAR). Absorbe la rama `instalador-setup`. |
| A9 | Hecha, unida a `tanda-9` (98c9897). Suite tras unir: **6251 passed, 7 skipped, 3 xfailed** (`suites/integ_a9.log`) | `tanda-9-a9` (4b69be7) | Informe sin commitear al corte: la sesión 10 corrió la pasada final (435 passed) y lo commiteó. |
| P9 | Hecha, unida a `tanda-9` (92417ce). Suite tras unir: **6284 passed, 7 skipped, 3 xfailed** (`suites/integ_p9.log`) | `tanda-9-p9` (8ec67c6) | |
| C9 | Hecha, unida a `tanda-9` (a6d44d0). Suite tras unir: **6337 passed, 7 skipped, 3 xfailed** (`suites/integ_c9.log`) | `tanda-9-c9` (de24991) | |
| X9 (★ D9-13.3) | Hecha, unida a `tanda-9` (8ee6bf7). Suite tras unir: **6391 passed, 7 skipped, 3 xfailed** (`suites/integ_x9.log`) | `tanda-9-x9` (b611d79) | Revisores: 0 Altos/Críticos; 3 Medios como preguntas. |
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
- Revisión ★ de S9: SAF-01 Crítico, SAF-02/TMG-01 y TMG-02 Altos, más Medios; subagente de corrección lanzado en el mismo worktree.
- Unidas P9 (92417ce) y C9 (a6d44d0). X9 terminada (b611d79).
- Unida X9 (8ee6bf7), suite 6391 en verde. S9 pasada 1 corregida; pasada 2 con 1 Alto devuelta al subagente.
- S9 unida a `tanda-9` (3044b7f) tras la pasada 2; suite **6567 passed, 8 skipped, 3 xfailed** (`suites/integ_s9.log`). Pasada 3: R2 cerrados; 1 Alto nuevo (R3-A1, decisión inicial del protocolo con AI vencida) devuelto al subagente; Alto anterior a S9 (CICLO con AI vencida) va como PREGUNTA. `sensor-role-auditor`: 0 Altos. Se volverá a unir `tanda-9-s9` con la corrección.
- Unión de B9 ensayada sobre S9: conflictos de conservar ambos lados (control_loop.py, hoja de banco, riesgos).
- S9 (revisión 3) y B9 unidas; suite 6606 en verde. Los 10 skipped: 3 nuevos son pruebas que solo escriben informes (variables `B9_ESCRIBIR_REGISTRO`/`S9_ESCRIBIR_INFORME`).
- `DECISIONES_PARA_REVISAR.md` escrito. Siguiente: unir `tanda-9` a `dev` y K9.
