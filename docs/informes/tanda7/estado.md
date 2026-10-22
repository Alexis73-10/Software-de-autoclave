# Tanda 7: estado

Rama `tanda-7`, creada desde `dev` (18eb429) tras A0. Sesión principal arrancada por el lanzador el 22-oct a las 00:12 (hora de Bogotá). Línea base de la suite (tanda-7 = dev 18eb429 + docs): **5020 passed, 2 skipped, 3 xfailed** (20 min).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | (commit docs(tanda7)) | Tanda 6 CERRADA: `merge-base --is-ancestor tanda-6 dev` = OK; sin ramas `tanda-6-*` locales (todas unidas y borradas); árbol sin cambios rastreados; commits de cierre f631f35 y 1d6cf98; el lanzador confirmó el cierre (23:46). Su `estado.md` dejó la fila Z como "En curso" aunque el cierre está commiteado y empujado (dev = origin/dev = 18eb429): discrepancia solo documental. Sin remanente para R6 (ver abajo). Sin stash `t6-pendiente` (no hacía falta). |
| K1 | Hecha | etiqueta `inst-2026-10-22-a` (18eb429) | `entrega/2026-10-22_a/` (Autoclave onedir + GeneradorCodigos.exe + zip + SHA-256). Prueba de humo OK (`--portable` abre el asistente). Ver `K1_compilacion_a.md`. |
| L1 | En curso (subagente, rama `tanda-7-l1`) | | Lanzado 00:36. |
| P1 | En curso (subagente, rama `tanda-7-p1`) | | Lanzado 00:36. |
| M1 | En curso (subagente, rama `tanda-7-m1`) | | Lanzado 00:36. |
| C2 | En curso (subagente, rama `tanda-7-c2`) | | Lanzado 00:36. |
| M2 | En curso (subagente, rama `tanda-7-m2`) | | Al principio se marcó "NO SE HACE" por la decisión 1.4; Cristian corrigió la instrucción el 22-oct a las 00:30 (E1 SÍ entra, formulario del preventivo NO). Se hace.  Lanzado 00:36. |
| R6 | Sin objeto | | A0 no encontró etapas de la tanda 6 sin hacer ni ramas sin unir (todas las filas "Hecha", ramas `tanda-6-*` ya contenidas y borradas). Los hallazgos abiertos de O2f (TMG-04/05, SAF-01/02) no son etapas; quedan listados en el índice. |
| Q1 ★ | En curso (subagente, rama `tanda-7-q1`) | | Lanzado 00:36. Revisores al terminar; límite 10:30. |
| K2 | Pendiente | | |
| D2 | En curso (subagente, rama `tanda-7-d2`) | | Lanzado 00:36. |
| Z | Pendiente | | |

## NOTA DE REANUDACIÓN (asistente de Cristian, 22-oct 06:10) — leer antes de seguir
Qué pasó:
- A las 01:43 la sesión principal llegó al límite de uso (se restablecía a las 02:50).
- Los relanzamientos de 01:53 y 02:03 fallaron por el mismo límite.
- A partir de las 02:03 el lanzador dejó de registrar, y la tanda quedó detenida hasta ahora.

Estado real de los subagentes: TODOS terminaron su trabajo de código, con commits en su rama. Les faltó lo siguiente:
- Los informes NO están commiteados: están en sus worktrees, en `docs/informes/tanda7/`.
- El resultado final de la suite NO está anotado: los informes dicen RESULTADO_SUITE o "ver al final".

| Etapa | Rama | Worktree (`.claude/worktrees/`) | Commits | Informe sin commit |
|---|---|---|---|---|
| L1 | tanda-7-l1 | agent-a252c72db53b8944d | 1 | L1_lock_soup.md |
| P1 | tanda-7-p1 | agent-a89312d6f73d480a8 | 12 | P1_preparacion_instalacion.md (informe y LEEME ya commiteados) |
| M1 | tanda-7-m1 | agent-a31c84146e39065a8 | 6 | M1_asistente_modelo.md + capturas |
| C2 | tanda-7-c2 | agent-a017e8dfb3f2420ce | 3 | C2_correo_manual.md |
| M2 | tanda-7-m2 | agent-a5b2f9cd2968b4864 | 4–5 | M2_mantenimiento_e1.md |
| Q1 | tanda-7-q1 | agent-ab2c9a3b57297a83c | 12 | Q1_preguntas_abiertas.md, Q1_ensayo_tabla.md |
| D2 | tanda-7-d2 | agent-a0d4bc84447812c0e | 3 | D2_depuracion.md (NO unir antes de K2) |

Para seguir:
1. NO relances los subagentes desde cero. En cada worktree:
   - revisa `git status` y commitea en su rama el informe y cualquier cambio pendiente que sea suyo;
   - corre la suite con `PYTHONPATH=<worktree>/src` (aviso de Q1: el paquete editable apunta al repo principal; verifica con `autoclave.__file__`);
   - anota el resultado en su informe.
2. Integra a `tanda-7` una rama a la vez, en el orden de prioridad: L1, P1, M1, C2, M2, Q1. Corre la suite en verde tras cada unión. En Q1, confirma antes que no tenga hallazgos Altos/Críticos abiertos. Si una rama no queda en verde a las 12:30, se queda fuera.
3. Después: K2 (lista a las 13:45), luego D2, luego Z.
