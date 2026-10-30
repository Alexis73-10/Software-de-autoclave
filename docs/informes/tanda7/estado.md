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
| Q1 ★ | Hecha, unida a `tanda-7` | 8a4a63d (merge) | Correcciones de la revisión en 733b19f..88858a0. Re-revisión safety + timing: 0 Altos/Críticos abiertos. SEN-01 (Alto preexistente en dev) queda como PREGUNTA (SP-7). Suite tras unir: 5405 passed / 3 skipped / 3 xfailed (19 min 59 s). |
| K2 | Hecha (08:10) | etiqueta `inst-2026-10-22-b` (23e76e2) | `entrega/2026-10-22_b/`. Humo: asistente de 8 pasos, sin traceback. Ver `K2_compilacion_b.md`. **Se instala la B.** |
| D2 | Hecha, unida a `tanda-7` DESPUÉS de K2 | fbd181c (merge) | Suite tras unir: 5382 passed / 3 skipped / 3 xfailed (= 5405 − 23 pruebas de código retirado). No está en ninguna compilación. |
| Z | Hecha | b33a409 + cierre | Suite final 5382 passed / 3 skipped / 3 xfailed; `tanda-7` unida a `dev` (`merge-base --is-ancestor` OK); push de dev, tanda-7 y etiquetas OK; índice en `docs/informes/informe_tanda_2026-10-22_t7.md`. **Instalar `entrega/2026-10-22_b/`.** |

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
| D2 | Hecha, unida a `tanda-7` DESPUÉS de K2 | fbd181c (merge) | Suite tras unir: 5382 passed / 3 skipped / 3 xfailed (= 5405 − 23 pruebas de código retirado). No está en ninguna compilación. |

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
- 08:01: unión de Q1 (con las correcciones de la revisión) en verde: 5405 passed / 3 skipped / 3 xfailed. Una corrida anterior dio 49 F / 40 E por dos pytest simultáneos sobre el mismo worktree (una tarea en segundo plano "cortada" que siguió viva); se descartó y se repitió limpia.
- 08:01: `tanda-7` unida a `dev` (23e76e2) y etiqueta `inst-2026-10-22-b`. 08:10: K2 hecha.
- 08:30: D2 unida a `tanda-7` (después de K2), suite en verde. 08:50: informe de Q1 cerrado por la sesión principal (e7e21f4) y unido (d747de9).
- 09:12: suite final sobre d747de9: 1 fallo intermitente (`test_opciones_qml.py::test_ingeniero_edita_con_ciclo_en_curso`, pasa 5/5 aislado). 09:34: repetida, en verde: 5382 passed / 3 skipped / 3 xfailed.
