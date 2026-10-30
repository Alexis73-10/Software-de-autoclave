# O1 — Operador del ciclo (MP-14b / D-24)

## Hecho
- `POST /cycle/start` toma opcionalmente el token (`Authorization`): si es una sesión válida, el usuario queda en `estado.operador_inicio` en el mismo bloque (bajo el lock de la máquina) que `START_CICLO`; sin token o con uno inválido/vencido queda `""`. El inicio NO exige sesión (decisión previa: ningún inicio depende de login) y un inicio rechazado no deja operador.
- `CycleLogger.update()` consume `operador_inicio` al crear el ciclo (nunca hereda el de un ciclo anterior): lo guarda en `ciclos.operador` (base), en el encabezado del respaldo JSONL (se reimporta con el ciclo) y en el pie del ticket (`Operador: <usuario>`; sin operador conserva la línea `Operador: ____________` para firma). Sin base de datos se mantiene la leyenda `SIN OPERADOR / SIN BD` (T8) y no se imprime el usuario.
- Reimpresión (`format_ticket`) imprime el operador guardado.
- El cliente de la UI (`UIServiceBackend.start_cycle`) envía el token de la ventana si hay sesión abierta.
- Migración de BD v6: garantiza la columna `ciclos.operador` en bases anteriores (la versión sube a 6). Ciclos antiguos: `''` → la UI muestra "—" y el ticket reimpreso deja la línea para firmar.
- Historial, "Último ciclo" y detalle ya leían `operador` (ahora con dato); se retiraron los 3 `TODO(MP-14b)` de `MenuPrincipal.qml` y el de `DetalleCiclo.qml`/`resumen_sistema.py`.

## Pruebas (`tests/test_o1_operador_ciclo.py`, 14)
Endpoint (con sesión, sin sesión, token inválido, inicio rechazado), logger (base + respaldo + ticket, sin operador, sin BD), pie y reimpresión, migración con una base anterior sin columna, ciclo antiguo en la UI y envío del token desde la UI.

## DECISIONES SIN CONFIRMAR
1. Se guarda el `usuario` (login) y no el nombre completo; sin sesión queda vacío ("—"), no una leyenda tipo "SIN SESIÓN". Alternativa: guardar "SIN SESIÓN" para distinguirlo de un ciclo antiguo.
2. Los reportes por periodo (resumen por resultado/programa) siguen agregando conteos: no se desglosan por operador. El operador aparece en el detalle del ciclo, el historial y el ticket. Alternativa: agregar "por operador" al resumen.
3. Solo un usuario con sesión abierta EN LA PANTALLA desde la que se inicia el ciclo queda como operador (las dos pantallas tienen sesión independiente).

## Pendiente
- Si se quiere exigir identificación para iniciar un ciclo, es un cambio de política (hoy no se exige).

## Revisión (safety-reviewer): sin Críticos ni Altos
- Confirmado: un token ausente/inválido nunca rechaza ni bloquea `START_CICLO`; `operador_inicio` se fija bajo el lock junto con el flag, se consume una sola vez y no se hereda; el token no se guarda ni se registra; la migración v6 es idempotente.
- **SAF-01 (Media, ACEPTADO — decisión T8):** sin base de datos el respaldo guarda la leyenda `SIN OPERADOR / SIN BD` como operador y al reimportar queda así en `ciclos.operador` (es el comportamiento de T8 §7.6, exigido por su prueba). Sirve para distinguir los ciclos que se corrieron sin base. Alternativa: guardar `""` en el respaldo y dejar la leyenda solo en la presentación.
- SAF-02 (Baja): sin BD se descarta el operador autenticado (coherente con T8 "sin operador"). SAF-03 (Baja): `operador_inicio` queda fijo si el inicio se descarta después del lock, pero el siguiente `/cycle/start` lo sobrescribe siempre. SAF-04 (Baja): el encabezado de la reimpresión no lleva la leyenda sin BD (el pie sí lleva el operador).
- La UI QML inicia el ciclo por `UIServiceBackend.start_cycle` (envía el token de la ventana).
