# Hotfix ES — estado

Rama `hotfix-estado-seguro` (desde `dev`). Prompt: `docs/mis_plans/prompt_claude_code_hotfix_estado_seguro.md`. Informe: `R_informe.md`.

| Paso | Estado |
|---|---|
| 1. Diagnóstico (R_informe.md §1) | Hecho (por código; sin el log del equipo) |
| 2. Retiro (8 puntos) | Hecho (9e0f29cc, 409b459c, c0e23c89) |
| 3. Pruebas nuevas y ajuste/retiro de las del protocolo | Hecho (409b459c, c0e23c89) |
| 3. Riesgo HAZ-ES-RET-01 | Hecho |
| 3. CLAUDE.md (sección del estado seguro) | Hecho |
| 3. Suite completa | Hecho: 11054 pasan, 11 omitidas, 3 xfail, 1 roja preexistente (`test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite`, también roja en `dev` b3660278) |
| Revisión de seguridad | Hecha por el director (6-nov) |
| Corrección ALTA: paro soltado sin confirmar (puertas y SetOutput) | Hecho (cf7fba48) |
| Corrección MEDIA: AI vencida en FALLA/PREPARACION | Hecho (2849c6e8) |
| Corrección MEDIA: válvulas de reposo al pasar a PREPARADO | Hecho (f12f74ce) |
| BAJA: texto «Confirmar paro» | Hecho (91b52ae1) |
| Riesgo HAZ-ES-RET-01, R_informe §7, AJUSTES.md | Hecho (AJUSTES.md sin commitear: tiene cambios ajenos) |
| Suite completa tras la revisión | Hecho: `pytest tests -n auto` 11071 pasan, 11 omitidas, 3 xfail, 1 roja preexistente (`test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite`) |
| Merge a `dev`, compilación, CERRADO.txt | Pendiente: lo hace el director |

Commits: 9e0f29cc (retiro en máquina de estados, lazo y /status), 409b459c (NO ABRIR con valor y límite, UI, pruebas nuevas), c0e23c89 (pruebas retiradas y ajustadas), y el de documentación (riesgo, CLAUDE.md, informe y este archivo).
