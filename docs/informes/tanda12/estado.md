# Tanda 12: estado

Rama `tanda-12`, creada desde `dev` (8bda767, contiene `tanda-11` cerrada) en A0. Sesión principal arrancada por el lanzador el 24-oct a las 17:30 (hora de Bogotá).

Precondición A0: `tanda11/estado.md` tiene `| Z | Hecha |` y `dev` contiene `tanda-11`: cumplida.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | c462114 | `t_saturacion_c` + prueba (106 passed con `test_steam.py`). Línea base en `_suites_t12/base` (8bda767) con `-n auto`: **7216 passed, 2 failed, 10 skipped, 3 xfailed** en 8 min (`suites/base.log`); los 2 (`test_ciclos_print.py::test_print_selected_sin_seleccion_no_imprime`, `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`) pasan en serie (`suites/base_serie.log`). **Línea base: 7218 passed.** |
| E12 | Terminada, por unir (después de P12) | `tanda-12-e12` (330cf8b) | 62 pruebas nuevas; 204 módulos dependientes en verde tras ajustar 6 archivos de prueba. Histéresis del techo `_HIST_TECHO_KPA = 2.0` (DECISIÓN SIN CONFIRMAR). Al unir: pasar `exposicion_restante_s` a `armar_progreso` en `backend/server.py` (C-13.7). |
| J12 | En curso | `tanda-12-j12` | Subagente lanzado. Código preasignado SIS-06 (excepción: agrega una entrada a `alarms/catalogo.py` e i18n; DECISIÓN SIN CONFIRMAR de la sesión principal). |
| P12 | Terminada, por unir (después de J12) | `tanda-12-p12` (1073fcc) | 1793 passed, 10 skipped en 85 archivos dependientes; tras el último cambio, 279 passed. Preguntas: Referencia 0,1–0,2 K más fría que el Principal → FALLO `cal_no_sostuvo`; ventana en el borde Psat − 2. |
| L12 | Terminada, por unir (después de E12) | `tanda-12-l12` (2d64c0b) | Solo documentos. Hallazgo: en 134 °C la salida de RECUPERACION (C-08.2, 135,3 °C) supera la Tsat del techo (≈135,0 °C) → reenviado a E12 con histéresis en el techo (DECISIÓN SIN CONFIRMAR). SEN-12 propuesto para la sonda de vapor (solo en la especificación). |

Instrucciones comunes de los subagentes: `tanda12/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-12-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (17:30)
- A0: rama `tanda-12` creada, línea base lanzada.
- A0 hecha (2632566 docs, c462114 feat). Lanzados E12, J12, P12 y L12 (4 subagentes, cada uno en su worktree).
- Línea base terminada: 7218 passed (7216 + 2 en serie).
- L12 terminada (2d64c0b). Su hallazgo de C-08 vs techo se envió a E12.
- P12 terminada (1073fcc), espera la unión de J12.
- E12 terminada (330cf8b). Falta J12.
