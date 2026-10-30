# B8 — Salida forzada del modo prueba huérfano

## Hecho
- `POST /io/test/force-exit` (nuevo, solo **ingeniero**; técnico, operador y admin → 403 `rol_sin_permiso`, sin sesión → 401). Cuerpo `{"confirmar": true, "motivo": "..."}`; sin `confirmar: true` → 422 `confirmacion_requerida`.
- **Huérfano** = el dueño (`_token_modo_prueba`) ya no tiene sesión: token caducado por inactividad (B7), cierre de sesión o cambio de turno. Con el dueño aún en sesión → 409 `modo_prueba_dueno_vigente` (debe salir él). Sin modo prueba → 409 `modo_prueba_inactivo`. Si quien llama es el propio dueño (ingeniero) también puede.
- **Misma salida que la normal** (`_salir_modo_prueba` → `exit_test_mode`): todas las salidas a seguro (ALL_OFF) y se reanuda la máquina; no toca el estado seguro (si hay uno activo sigue su camino; el flag `estado_seguro_activo` queda en la bitácora). Bajo `guard_estado` (mismo lock de la máquina).
- **Auditoría:** `modo_prueba_salida_forzada` (quién fuerza = usuario/rol de la sesión; a quién: `dueno` y `rol_dueno`, recordados por `AlmacenTokens.quien_fue(token)` aunque el token ya caducó —solo nombres, nunca el token—; por qué: `motivo`; `estado_seguro_activo`) y además `modo_prueba_sale` con motivo "salida forzada por ingeniero". Los rechazos se auditan como siempre.
- La ruta normal `/io/test/exit` sigue exigiendo al dueño (decisión 30 intacta).

## Pruebas (`tests/test_b8_salida_forzada_modo_prueba.py`, 13)
dueño vencido → ingeniero fuerza; auditoría completa; dueño vigente rechazado; dueño que cerró sesión; técnico rechazado; sin sesión / operador / admin; confirmación obligatoria; sin modo prueba; con estado seguro activo (no se cancela y queda registrado); ingeniero dueño; ruta normal sigue exigiendo al dueño; `quien_fue` sin token en claro.

## PENDIENTES / DECISIONES SIN CONFIRMAR
1. **Sin botón en pantalla:** la pantalla de OPCIONES › Entradas/Salidas la está desarrollando otra sesión; falta un botón "Forzar salida del modo prueba" (solo ingeniero, con diálogo de confirmación) que llame a esta ruta. Hasta entonces: API.
2. Otra sesión añadió (sin commitear) caducidad por inactividad del propio modo prueba (90 s sin keepalive, `P-ES-4`), lo que reduce la ventana de huérfano; esta ruta cubre el hueco restante. Coordinar al unir.
3. Revisión con agentes `safety-reviewer`/`timing-auditor`: NO ejecutada por orden de Cristian (20-oct); es una etapa de seguridad, revisar aparte.
