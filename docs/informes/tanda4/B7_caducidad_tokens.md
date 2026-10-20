# B7 — Caducidad de tokens de sesión (backend)

## Hecho
- **Plazo único:** `core/runtime/sesion_inactividad.py` (`SESION_INACTIVIDAD_S = 300`, 5 min) es ahora la fuente de la UI (`ui_qml/sesion_backend.py` lo importa; sigue exponiendo el mismo nombre) y del backend. No se inventó otro parámetro.
- `backend/autenticacion.py`: `AlmacenTokens(reloj=time.monotonic, inactividad_s=...)`. Cada sesión guarda su última actividad (monotónica). `obtener(token)` devuelve `None` y borra el token si pasaron ≥ 300 s sin peticiones autenticadas; cada petición autenticada (`requiere_rol`) lo **renueva**. `obtener(token, renovar=False)` y `existe(token)` son consultas internas que NO cuentan como actividad (usadas en el modo prueba y la bitácora). Se purgan las caducadas al emitir un token nuevo. Un token vencido → **401 `sesion_invalida`** (auditado como los demás rechazos) y la UI ya sabía volver al Login/Reposo con ese 401 (`SesionVentana.enviar`).
- **La UI mantiene viva la sesión mientras se usa:** `SesionVentana.registrarActividad` (toque/tecla en una pantalla con token) avisa al backend con `GET /auth/sesion` como máximo cada 30 s (`KEEPALIVE_S`), para que el token no caduque mientras el operador navega sin escribir. Un 401 de ese aviso cierra la sesión local (mismo camino que al reconectar). Fuera de pantallas con token o sin sesión no hay avisos.
- **No interrumpe un ciclo ni deja salidas sin supervisión:** la caducidad solo afecta a rutas que exigen sesión; el ControlLoop, la máquina de estados y el estado seguro no leen tokens (prueba: tras vencer, ninguna llamada al ControlLoop y las rutas sin sesión responden). Con el ciclo en curso, si caduca la sesión de un ingeniero que editaba parámetros, su siguiente cambio pide login de nuevo; el ciclo sigue.
- **Apagado de Windows sin sesión (A1):** `/system/shutdown` no mira el token; un token vencido no lo impide (prueba).
- **PySide (C1):** cada acción con token renueva; si la ventana queda inactiva >5 min el siguiente cambio responde 401 y las vistas lo muestran ("Sesión no válida o vencida; inicie sesión de nuevo"; calibración/E-S/secado/parámetros). No se añadió un aviso periódico en PySide (no tiene lógica de inactividad propia): el modo prueba de esa ventana ya tiene su propio keepalive e inactividad (trabajo de otra sesión sobre E/S) — ver B8 para el huérfano.

## Pruebas (`tests/test_b7_caducidad_tokens.py`, 17)
Reloj monotónico inyectable (sin `time.sleep`): mismo plazo que la UI; vigente / caducado / exactamente en el plazo; renovación por petición; consulta interna sin renovar; purga; invalidar caducado; reloj por defecto monotónico; endpoints (401, mantiene viva, auditoría, no toca el ControlLoop ni rutas sin sesión, apagado, nuevo login); UI (aviso cada 30 s como máximo, sin sesión/fuera de pantalla no avisa, 401 cierra).

## DECISIONES SIN CONFIRMAR
1. Aviso periódico cada 30 s desde la UI (alternativa: renovar solo con escrituras; el operador que solo navega vería 401 al primer cambio tras 5 min).
2. PySide sin aviso periódico (ver arriba).
3. Revisión con agentes `safety-reviewer`/`timing-auditor`: NO ejecutada por orden de Cristian (20-oct); revisar aparte.
