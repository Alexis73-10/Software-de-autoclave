# Tanda 24 — estado

Rama `tanda-24` desde `dev` (9a933ff3). Spec: `docs/mis_plans/prompt_claude_code_tanda24.md` (RSB-01..08).

| Paso | Estado | Nota |
|---|---|---|
| A0 | Hecha | rama, prompt, inventario RSB-04 |
| P1 backend | Hecha | rama tanda-24-backend, d4e80a4d (en la sesión principal, sin worktree) |
| P2 UI | Hecha | rama tanda-24-ui (desde tanda-24-backend), 7948967e |
| Unión P1+P2 | Hecha | merge 36f56b3e en tanda-24 |
| R revisión | Hecha | safety-reviewer; SAF-01..06 corregidos en dfca3de3 |
| Suite | Hecha | pytest tests -n auto: 9275 passed, 11 skipped, 7 xfailed, 2 failed (test_home_view y test_impresion_menu, caídas de trabajador xdist; en serie 13 passed) |
| K merge a dev | Pendiente | |
| Z cierre | Pendiente | |

Último commit: dfca3de3 (revisión R)

## Inventario RSB-04 (códigos de `/io/assignment*`)

Rechazos con `codigo` en el cuerpo (`server_reasignacion.py`, `asignacion_io.py`, `dependencias.py`):

- Validación de la asignación (422, `_rechazo_validacion`, primer error de `aio.validar`/`combinar`/`_errores_calibracion`): `conflicto`, `puerto_inexistente`, `funcion_desconocida`, `fabrica_invalida`, `puerto_sin_calibracion`, `asignacion_invalida` (sin errores), `archivo_ilegible`/`archivo_invalido` (solo `validar_respaldo`/`leer`; no los emiten estas rutas, pero sí `GET` como `error_archivo`).
- POST /io/assignment y /factory: `sin_cambios` (422), `confirmacion_requerida` (428), `confirmacion_reforzada` (428), `nombre_no_coincide` (422), `reinicio_en_curso` (409), `no_se_pudo_guardar` (503).
- POST /io/assignment/verify: `no_pendiente` (422), `confirmacion_reforzada`/`nombre_no_coincide`, faltas 409 `sin_cambio_observado`, `sin_prueba_de_salida`, `sin_lectura`, `calibracion_requerida` (se retira con RSB-07), `reinicio_pendiente` (409), `no_se_pudo_guardar` (503).
- Comunes (`_comprobar_estado`/`guard_estado`/`requiere_rol`/`_reautenticar`): `estado_no_permitido` (409, `extra.motivo` ∈ ciclo/estado/modo_prueba/apagando; antes también estado_seguro*), `sensor_camara_no_segura` (409, se retira con RSB-01), `rol_sin_permiso`, `sesion_invalida`, `clave_pendiente` (403/401), `reautenticacion_requerida`/`reautenticacion_fallida` (403), `usuario_bloqueado` (429), `validacion` (422 de cuerpo inválido), `configuracion_invalida` (409, compuerta de arranque).
- GET /io/assignment: `motivo` (ciclo/estado/modo_prueba/apagando), `verificacion.funciones[].falta` (faltas de arriba, `error`), `error_archivo` (códigos de validación/archivo).
