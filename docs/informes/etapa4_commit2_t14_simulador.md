# Etapa 4 — Commit 2: T-14, simulador con el contrato v7

**Fecha:** 2026-10-08 · **Rama:** `dev` · **Plan:** `docs/mis_plans/plan_t8_login_qml.md` v5.1, §5 (commit 2)
**Suite:** 2062 pruebas en verde (`python -m pytest -q tests`, 2 min 43 s). Sin commit.

## Qué se hizo

| Cambio | Dónde |
|---|---|
| Endpoints `/auth/login`, `/auth/logout`, `GET /auth/sesion`, `/auth/change_password` y `POST /usuarios` con los mismos códigos y cuerpos que el backend (`{"detail", "codigo", ...}`; 429 con `segundos_restantes` y `Retry-After`; 422 en lista `{campo, codigo}` con `clave` desde el inicio; `igual_actual`; H-T8-01) | `src/autoclave/simulador/autenticacion_simulada.py` (nuevo) |
| Usuarios sembrados en memoria: `tec1`, `adm1`, `ing1` (`clave1234`), semillas `admin`/`admin1234` e `ingeniero`/`ingeniero1234` con clave pendiente, `bloq1` dedicado al bloqueo | `USUARIOS_SEMBRADOS` |
| Token determinista por sesión `sim-<usuario>-<n>` con tabla en memoria (decisión 8: logout invalida solo su token) | `registrar_autenticacion` |
| Bloqueo con `ControlIntentos` del backend (mismo código), con el reloj del simulador | idem |
| `crear_app` registra la autenticación; sigue escuchando solo en 127.0.0.1 (`__main__.py:60`) | `src/autoclave/simulador/servidor.py` |

Sin cambios en el backend ni en el cliente; el cliente no tiene trato especial para el simulador.

## Pruebas

- **Nueva:** `tests/test_contrato_autenticacion_simulador.py`. Importa la batería de `test_contrato_autenticacion.py` y sustituye la fixture `cliente` por el simulador: las **18 pruebas de contrato** corren igual contra el backend real y contra el simulador (incluidas dos sesiones simultáneas con cierre en una, los nombres de campo del 422 de `/usuarios` y "Admin"/"admin"). Además: los usuarios de la batería existen en el simulador con esa clave; tokens `sim-<usuario>-<n>` distintos por sesión; ningún módulo de `backend/` importa `simulador/`.
- Se usó un archivo aparte, en vez de añadir el parámetro al de la batería, para no tocar `test_contrato_autenticacion.py`, que pertenece al commit 1 y aún no estaba agregado.

## Para el commit

Archivos: `src/autoclave/simulador/autenticacion_simulada.py`, `src/autoclave/simulador/servidor.py`, `tests/test_contrato_autenticacion_simulador.py`, este informe.

**Antes del commit 3 (T-8):** T-8 modifica `puente.py` y `validacion_usuario.py`, que están en el índice para el commit 1. Conviene hacer los commits 1 y 2 antes de seguir, para que esos archivos no mezclen versiones.

## Riesgo cerrado

R-2 (parte servidor): el simulador ya responde login, logout, sesión, cambio de clave, bloqueo y `/usuarios` igual que el backend. Queda la parte cliente (T-8) y la verificación visual.
