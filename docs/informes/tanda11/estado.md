# Tanda 11: estado

Rama `tanda-11`, creada desde `dev` (c607dc4, contiene `tanda-10` cerrada) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 16:58 (hora de Bogotá).

Precondición A0: `tanda10/estado.md` tiene `| Z | Hecha | (cierre) | Suite en verde (7218 passed, 25bbe81; después solo documentación). `tanda-11` unida a `dev` (--no-ff), push de `dev`, `tanda-11` e `inst-2026-10-23-g`. Índice: `docs/informes/informe_tanda_2026-10-23_t11.md`. |

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | 1b3ec0d | Línea base en `_suites_t11/base` (c607dc4) con `-n auto`: **6990 passed, 3 failed, 10 skipped, 3 xfailed** en 7 min (`suites/base.log`); los 3 (`test_ciclos_print.py::test_print_selected_sin_seleccion_no_imprime`, `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`, `test_e6_enlace_handshake.py::test_uptime_que_retrocede_es_reinicio`) pasan en serie (`suites/base_serie.log`): interferencia del paralelo. **Línea base: 6993 passed.** |
| R11 | Hecha, unida a `tanda-11` (68fd4a1) | `tanda-11-r11` (0aa9250) | 811 passed en el worktree. Revisor de seguridad: sin bloqueantes; SAF-01..04 corregidos, SAF-06 pendiente (aviso en la otra pantalla). Suite tras unir (68fd4a1): 7076 + 5 de impresión/menú que pasan en serie = **7081 passed**, verde (`suites/integ_r11*.log`). |
| E11 | Hecha, unida a `tanda-11` (e6886df) | `tanda-11-e11` (9eaf7f3) | 1311 passed, 8 skipped + 34 QML en el worktree. DO 13 libre (DECISIÓN SIN CONFIRMAR). Suite tras unir (e6886df): 7003 passed + 3 de impresión que pasan en serie = **7006 passed**, verde (`suites/integ_e11*.log`). |
| S11 | Hecha, unida a `tanda-11` (d0397cd) | `tanda-11-s11` (9843a40) | 104 passed en el worktree (2322 en los 107 archivos dependientes antes de ajustar `test_t3`). Usa `programas_seguridad()` (DECISIÓN SIN CONFIRMAR y 1 PREGUNTA en su informe). Suite tras unir (d0397cd): 7028 + 3 en serie = **7031 passed**, verde (`suites/integ_s11*.log`). |
| U11 | Hecha, unida a `tanda-11` (fe04763) | `tanda-11-u11` (558b030) | Revisor de seguridad (★): sin bloqueantes; SAF-01..04 corregidos (NFKC, caracteres permitidos, nombres reservados, `recursive_triggers`, rol de la semilla, 422 con cuerpo vacío). 85 + 2512 + 263 passed en el worktree. Esquema BD v11. Suite tras unir (fe04763): 7192 + 2 en serie = **7194 passed**, verde (`suites/integ_u11*.log`). |
| N11 | Hecha, unida a `tanda-11` (d31d44b) | `tanda-11-n11` (6cfaf23) | Revisor de seguridad: sin bloqueantes; SAF-01..08 corregidos (borrado con un solo renombrado, enlaces/uniones, WMI, versiones). 35 passed; ISCC compila; parser PS 0 errores. Suite final tras unir (25bbe81, con el guion de ensayo F → G): 7216 + 2 en serie = **7218 passed, 10 skipped, 3 xfailed**, verde (`suites/integ_n11_final*.log`). |
| O11 | Hecha, unida a `tanda-11` (f6b1edd) | `tanda-11-o11` (8b19121) | 28 nuevas; 1070 passed en el worktree; 14 capturas es/en. Suite tras unir (f6b1edd): 7103 passed, 6 rojos; 5 pasan en serie y 1 rojo real (`test_o2e_bitacora::test_textos_de_todos_los_eventos`: evento `entradas_mostradas` sin texto), arreglado en `tanda-11` (commit fix antes de fe04763). |
| K11 | Hecha: compilación **G** (`inst-2026-10-23-g` → 8051145, `entrega/2026-10-23_g/`, Setup 1.0.0-g compilado y no ejecutado) | (commit de cierre) | `K11_compilacion_g.md`. Humo OK (2 pantallas); ensayo F → G OK (migración de usuarios). |
| Z | Hecha | (cierre) | Suite en verde (7218 passed, 25bbe81; después solo documentación). `tanda-11` unida a `dev` (--no-ff), push de `dev`, `tanda-11` e `inst-2026-10-23-g`. Índice: `docs/informes/informe_tanda_2026-10-23_t11.md`. |

Instrucciones comunes de los subagentes: `tanda11/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-11-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (16:58)
- A0: rama creada (1b3ec0d), línea base lanzada.
- Lanzados R11, E11, S11 y U11 (4 subagentes, cada uno en su worktree). En cola: N11 y O11 (en ese orden, al liberarse un cupo). La sesión principal NO termina el turno con subagentes activos.
- E11 terminada y unida (e6886df); suite de integración lanzada en `_suites_t11/integ`. N11 lanzado en el cupo libre.
- S11 terminada y unida (d0397cd). O11 lanzado en el cupo libre (parte de S11 unida).
- Suites de E11 y S11 en verde. R11: revisor de seguridad → correcciones en curso. U11 terminada → revisor de seguridad (★) en curso.
- R11 corregida tras la revisión y unida (68fd4a1); suite lanzada. U11: correcciones de la revisión en curso.
- Suite de R11 en verde. N11 terminada → revisor de seguridad (no exigido, pero la limpia borra datos) → correcciones en curso.
- O11 unida (f6b1edd) con un rojo real arreglado en `tanda-11`. U11 corregida y unida (fe04763); suite lanzada. N11 corregida, se une después de la suite de U11.
- U11 en verde; N11 unida (d31d44b); suite final en verde (25bbe81: 7218 passed). LEEME con «Cambios respecto a la F» y 8f. DECISIONES_PARA_REVISAR escrito. Siguiente: unir a `dev`, etiqueta G, compilación.
- 18:00-18:20: `tanda-11` unida a `dev` (8051145), etiqueta G, compilación G (PyInstaller, ISCC), humo, ensayo F → G, SHA-256 y `usb/`. Z: índice, unión final y push.
