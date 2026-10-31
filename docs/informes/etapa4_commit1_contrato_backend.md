# Etapa 4 — Commit 1: contrato del backend (spec v7)

**Fecha:** 2026-10-08 · **Rama:** `dev` · **Plan:** `docs/mis_plans/plan_t8_login_qml.md` v5.1, §3.4 y §5 (commit 1)
**Suite:** 2041 pruebas en verde (`python -m pytest -q tests`, 2 min 45 s). Sin commit: lo hace Cristian.

## Qué se hizo

| Cambio | Dónde |
|---|---|
| `RechazoApi` + manejador: cuerpo `{"detail": <texto actual>, "codigo": <código>, ...extra}`. `detail` sigue siendo texto (puertas y Tk no cambian) | `backend/server.py` (`RechazoApi`, `_responder_rechazo`) |
| `_rechazar` y `_Rechazo` llevan código; todos sus puntos de uso codificados (§3.4 del plan) | `server.py` |
| 401 `sesion_invalida` / `credenciales_invalidas`; 403 `clave_pendiente` / `rol_sin_permiso` / `clave_actual_incorrecta` / `rol_no_creable`; 409 `estado_no_permitido` (+ `estado`), `configuracion_invalida`, `usuario_existe`, `programa_en_curso`, `modo_prueba_otra_sesion`, `modo_prueba_inactivo`, `modo_prueba_no_dueno`, `paro_emergencia`, `modo_prueba_rechazado` | `server.py` |
| 429 con `codigo: usuario_bloqueado`, `segundos_restantes` y `Retry-After`; el 5.º fallo ya responde 429 | `server.py` (`_rechazar_bloqueado`, `login`); `backend/autenticacion.py` (`segundos_restantes`) |
| H-T8-01: fallos de `clave_actual` suman al contador del login; al 5.º, 429 e invalidación del token (con salida del modo prueba si era la dueña, como el logout); clave actual correcta reinicia el contador | `server.py` (`change_password`, `_bloquear_por_cambio_clave`, `_invalidar_sesion`) |
| 422 de `change_password` y `POST /usuarios`: lista `{campo, codigo}` con los nombres del cuerpo; `igual_actual` en `clave_nueva`; `clave_actual` vacía → `obligatorio` (sin contar intento) | `server.py` (`_rechazar_validacion`) |
| `GET /auth/sesion`: 200 `{usuario, rol}`, también con clave pendiente; 401 estándar | `server.py` |
| Reglas por código (`codigos_nuevo_usuario`, `codigo_clave`, `codigo_confirmacion`) y envoltura de textos `validar_nuevo_usuario` con resultado idéntico al anterior | `ui_pyside/services/validacion_usuario.py` |
| Renombre `password` → `clave` en los errores del 422 de `/usuarios`, con el puente adaptado (traduce la lista con la envoltura de textos) | `ui_pyside/views/nuevo_usuario/puente.py` |

## Pruebas

- **Nueva:** `tests/test_contrato_autenticacion.py` (18 casos, parametrizada por servidor; hoy solo `backend`, el simulador se añade en el commit 2): campos del login, 401 con código, 5.º fallo 429 con 300 s y `Retry-After`, usuario inexistente con las mismas respuestas, **"Admin" y "admin" comparten contador y respuesta**, clave correcta no cuenta, 401 `sesion_invalida` con `WWW-Authenticate`, `GET /auth/sesion` (también con clave pendiente), dos sesiones y cierre en una, 403 `clave_pendiente`, cambio de clave 403/422/200, H-T8-01 (bloqueo e invalidación, contador compartido con el login, reinicio tras cambio exitoso), `/usuarios` 422 con los cinco campos del cuerpo, 403 y 409.
- **Ajustadas:** `test_backend_autenticacion.py` (5.º fallo 429 con cuerpo exacto; concurrencia: 5 verificaciones y el resto 429; 422 de `/usuarios` en lista; nueva `test_segundos_restantes_redondea_hacia_arriba`), `test_nuevo_usuario_puente.py` (422 en lista).

## Para el commit

`server.py` tiene **dos hunks ajenos** del enlace serial A1/A2 que no van en este commit: `_diagnostico_comunicacion()` (antes de `@app.get("/status")`) y `card_connected` / `comunicacion` dentro de `get_status()`. Agregar `server.py` por hunks (`git add -p`) dejando esos dos fuera.

Archivos del commit 1: `src/autoclave/backend/server.py` (parcial), `src/autoclave/backend/autenticacion.py`, `src/autoclave/ui_pyside/services/validacion_usuario.py`, `src/autoclave/ui_pyside/views/nuevo_usuario/puente.py`, `tests/test_backend_autenticacion.py`, `tests/test_nuevo_usuario_puente.py`, `tests/test_contrato_autenticacion.py`. Los documentos (`planeacion_backend_autenticacion.md` v7, `plan_t8_login_qml.md`, `hallazgos_nrm.md`, `planeacion_opciones.md`, este informe) según la política documental que decidas (NRM-04).

## Notas

- Con el usuario ya bloqueado (p. ej. por logins de otra persona), `change_password` responde 429 sin verificar e invalida igualmente el token de esa sesión: la UI cierra la sesión ante cualquier 429 del cambio de clave (R4-1), así que el backend lo hace coherente.
- Los 409/422 de texto de endpoints operativos (`:592` selección de ciclo, impresión) no cambian; la UI de T-8 no los usa.
- Siguiente: commit 2 (T-14, simulador con el mismo contrato).
