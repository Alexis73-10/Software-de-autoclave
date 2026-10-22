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
