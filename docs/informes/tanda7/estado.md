# Tanda 7: estado

Rama `tanda-7`, creada desde `dev` (18eb429) tras A0. Sesión principal arrancada por el lanzador el 22-oct a las 00:12 (hora de Bogotá). Línea base de la suite (tanda-7 = dev 18eb429 + docs): **5020 passed, 2 skipped, 3 xfailed** (20 min).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | (commit docs(tanda7)) | Tanda 6 CERRADA: `merge-base --is-ancestor tanda-6 dev` = OK; sin ramas `tanda-6-*` locales (todas unidas y borradas); árbol sin cambios rastreados; commits de cierre f631f35 y 1d6cf98; el lanzador confirmó el cierre (23:46). Su `estado.md` dejó la fila Z como "En curso" aunque el cierre está commiteado y empujado (dev = origin/dev = 18eb429): discrepancia solo documental. Sin remanente para R6 (ver abajo). Sin stash `t6-pendiente` (no hacía falta). |
| K1 | Hecha | etiqueta `inst-2026-10-22-a` (18eb429) | `entrega/2026-10-22_a/` (Autoclave onedir + GeneradorCodigos.exe + zip + SHA-256). Prueba de humo OK (`--portable` abre el asistente). Ver `K1_compilacion_a.md`. |
| L1 | Hecha, unida a `tanda-7` | 6615b4f (merge) | Suite rama 5020 p / 2 s / 3 xf; tras unir 5020 p. |
| P1 | Hecha, unida a `tanda-7` | c20e243 (merge) | Suite rama 5081 p; tras unir 5081 p / 2 s / 3 xf. |
| M1 | Hecha, unida a `tanda-7` | bce8623 (merge) | Suite rama 5139 p; tras unir 5200 p / 2 s / 3 xf. REQ-19 de M1 renumerado a REQ-27 (choque con Q1). |
| C2 | Hecha, unida a `tanda-7` | 0d32135 (merge) | Suite rama 5053 p; tras unir 5233 p / 2 s / 3 xf. Conflicto solo en `revision_traducciones.md` (unión de filas). |
| M2 | Hecha, unida a `tanda-7` | ceb5f64 (merge) | Suite rama 5042 p; tras unir 5255 p / 2 s / 3 xf. |
| R6 | Sin objeto | | A0 no encontró etapas de la tanda 6 sin hacer ni ramas sin unir (todas las filas "Hecha", ramas `tanda-6-*` ya contenidas y borradas). Los hallazgos abiertos de O2f (TMG-04/05, SAF-01/02) no son etapas; quedan listados en el índice. |
| Q1 ★ | En curso: correcciones de la revisión | | Suite rama 5139 p / 3 s; unión de ensayo sobre M2: 5374 p / 3 s / 3 xf. Revisores corridos 06:12: safety 0 Altos; timing 1 Alto (TMG-01, F0 tras un corte); sensores 1 Alto preexistente en la base (SEN-01). Subagente corrigiendo TMG-01 y los Medios coincidentes. |
| K2 | Pendiente | | |
| D2 | Código hecho (rama `tanda-7-d2`); se une después de K2 | | Suite rama 4997 p / 2 s / 3 xf. |
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
| L1 | Hecha, unida a `tanda-7` | 6615b4f (merge) | Suite rama 5020 p / 2 s / 3 xf; tras unir 5020 p. |
| P1 | Hecha, unida a `tanda-7` | c20e243 (merge) | Suite rama 5081 p; tras unir 5081 p / 2 s / 3 xf. |
| M1 | Hecha, unida a `tanda-7` | bce8623 (merge) | Suite rama 5139 p; tras unir 5200 p / 2 s / 3 xf. REQ-19 de M1 renumerado a REQ-27 (choque con Q1). |
| C2 | Hecha, unida a `tanda-7` | 0d32135 (merge) | Suite rama 5053 p; tras unir 5233 p / 2 s / 3 xf. Conflicto solo en `revision_traducciones.md` (unión de filas). |
| M2 | Hecha, unida a `tanda-7` | ceb5f64 (merge) | Suite rama 5042 p; tras unir 5255 p / 2 s / 3 xf. |
| Q1 | tanda-7-q1 | agent-ab2c9a3b57297a83c | 12 | Q1_preguntas_abiertas.md, Q1_ensayo_tabla.md |
| D2 | Código hecho (rama `tanda-7-d2`); se une después de K2 | | Suite rama 4997 p / 2 s / 3 xf. |

Para seguir:
1. NO relances los subagentes desde cero. En cada worktree:
   - revisa `git status` y commitea en su rama el informe y cualquier cambio pendiente que sea suyo;
   - corre la suite con `PYTHONPATH=<worktree>/src` (aviso de Q1: el paquete editable apunta al repo principal; verifica con `autoclave.__file__`);
   - anota el resultado en su informe.
2. Integra a `tanda-7` una rama a la vez, en el orden de prioridad: L1, P1, M1, C2, M2, Q1. Corre la suite en verde tras cada unión. En Q1, confirma antes que no tenga hallazgos Altos/Críticos abiertos. Si una rama no queda en verde a las 12:30, se queda fuera.
3. Después: K2 (lista a las 13:45), luego D2, luego Z.


## Reanudación de la sesión principal (22-oct, 06:10)
- 06:23: las 7 suites de rama en verde (resultados arriba).
- 06:25-06:44: uniones L1→P1→M1→C2→M2→Q1 en la rama de ensayo `tanda-7-integ`; suite en cada punto de unión, todas en verde. `tanda-7` avanzada hasta la unión de M2 (ceb5f64) + ac639f6 (resultados en los informes).
- Q1 queda fuera hasta cerrar el Alto TMG-01.
