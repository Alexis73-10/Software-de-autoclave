# S3 (continuación) — base de datos en caliente, fsync del respaldo, `door_id`/`source_door`, SECADO y CIC-10

Continúa `S3a_calibracion_plausibilidad.md`. Instrucción: `instruccion_claude_code_tanda_2.md` §2 S3.

## S3c — Una base de datos que falla en caliente activa OPERANDO_SIN_BD (T8 SAF-03)

- `CycleLogger` avisa **una vez por ciclo**, con un candado, cuando una escritura de la base falla o la cola de escritura se llena (`al_fallar_bd`).
- `BackendContext.bd_fallo_en_caliente(motivo)`, idempotente y con candado:
  - activa la alarma no bloqueante `OPERANDO_SIN_BD` y marca `sin_base_de_datos`;
  - **el ciclo en curso no se detiene**: sigue en el respaldo JSONL y en el ticket;
  - el siguiente ciclo pide confirmación (`confirmar_sin_registro`) y lleva la leyenda "SIN OPERADOR / SIN BD";
  - calibración, parámetros y `/cycle/start` ya se guardaban con ese indicador;
  - **`context.db` y `context.calibration_audit` pasan a `BdNoDisponible`**, como en el arranque sin base, así que las altas, el historial y los reportes responden 503 en vez de fallar al azar. La referencia real queda en `db_real`: el apagado la cierra y el logger y el historial de alarmas conservan la suya.
- Con la base en falla, `_numero_nuevo` ya no la consulta dentro del tick.
- La marca `sin_registro` de un ciclo ya no la contamina una tarea tardía del anterior.

## S3d — El fsync del respaldo sale del tick

- El respaldo (flush y fsync) va por un **hilo FIFO propio y sin límite** (`EscritorBD(maximo=0)`), independiente de la base. Una base atascada (timeout de 10 s por tarea) ya no retrasa el respaldo, y la cola nunca se llena ni obliga a escribir en línea.
- Se conserva "primero el respaldo, después la base": el lazo encola primero el respaldo y después la base.
- **Marca de ciclo en curso** (hallazgo Alto de ambos revisores): se limpia **después** del cierre del respaldo, en el mismo hilo FIFO, y solo si sigue siendo la del mismo ciclo (`limpiar_en_curso(solo_numero=…)`). Así, un corte entre la limpieza y el cierre no deja un ciclo terminado sin cierre ni marca, y una limpieza tardía no borra la marca de un ciclo nuevo.
- **Apagado** (hallazgo Alto): `CycleLogger.detener()` vacía las dos colas, y `_secuencia_apagado` lo llama después de detener el lazo y antes de cerrar la base. Antes `EscritorBD.detener` no se llamaba en ningún sitio.
- **Efecto aceptado:** un corte de energía puede perder la última línea del respaldo que aún esté en cola (milisegundos, en condiciones normales). La lectura ya descarta una línea incompleta y el ciclo queda como INTERRUMPIDO. Antes el fsync iba dentro del tick; la medición real en el equipo (eMMC/SSD, antivirus) sigue pendiente en la hoja de banco.
- Sigue síncrono en el tick, una vez por ciclo y fuera de este alcance:
  - `contador.siguiente`;
  - `marcar_en_curso`: debe estar en disco antes de iniciar;
  - la lectura de `max_numero_ciclo` con la base sana.

## S3e — `door_id` y `source_door` con dos pantallas en un solo PC (T9 SAF-03)

**Definición:**
- `door_id` (perfil de instalación) = la puerta del PC principal. Identifica la ventana principal (backend, Apagar equipo). **No** decide qué puerta puede operar cada pantalla.
- `source_door` (cuerpo de `/doors/<puerta>/open|close`) = la puerta que controla la pantalla que manda la orden. Es **declarada por el cliente, no autenticada**.

**Implementado** (`_orden_puerta`):
- cada pantalla opera solo su puerta: otra puerta se rechaza con 409 `puerta_ajena`, y un valor no entero o fuera de 1..N con 422 `source_door_invalido`;
- cada orden, aceptada o rechazada, queda en `audit_log` con el origen (`puerta_orden` y `puerta_orden_rechazada`; antes las puertas no se auditaban);
- sin `source_door` (clientes antiguos y simulador) se acepta y queda como "desconocido".

Pruebas: `tests/test_s3_source_door.py` (12). Se ajustó el ayudante `_abrir` de `test_puertas_fallas_endpoints.py`, que mandaba `source_door=1` para la puerta 2.

**Pendiente heredado:** los permisos por rol de puertas (`open_other_door`, etc.) siguen sin aplicarse en la ruta HTTP; solo existen en `ServicioPuertas.can_open`. Fuera de alcance de S3 (nota ya existente en la memoria del proyecto).

## S3f — SECADO alcanza atm − rango con la bomba y las válvulas cerradas (T5)

**No validable en el simulador:** el simulador (`autoclave.simulador`) reproduce un ciclo grabado, sin modelar la bomba ni las válvulas. Queda para el banco: **hoja de pruebas E-03** (`docs/mis_plans/hoja_pruebas_banco/pruebas.py`).

## S3b — CIC-10: salida autorizada cuando el estado seguro no puede terminar (T5)

Ver la propuesta en `docs/informes/tanda2/S3b_cic10_propuesta.md`. **PENDIENTE de decisión de producto.**

## Pruebas

- Antes: 3560 (con 2 fallos ajenos). Después: 3585 (los mismos 2 fallos ajenos).
- Nuevas:
  - `tests/test_s3_bd_caliente_respaldo.py` (13);
  - `tests/test_s3_source_door.py` (12).
- Ajustada: `test_puertas_fallas_endpoints.py` (S3e).

## Revisores (safety-reviewer y timing-auditor)

Sin Críticos.
- **Alto**, marca de ciclo limpiada antes del cierre del respaldo: **corregido** (arriba).
- **Alto**, el apagado no vaciaba la cola: **corregido**.
- **Medio**, el respaldo detrás de una base atascada y la escritura en línea que rompía el orden con la cola llena: **corregido** con el hilo propio y sin límite.
- **Medio**, `sin_registro` por ciclo, el candado del aviso y el candado del cambio de estado: **corregidos**.
- **Medio**, endpoints con `context.db` que no se bloqueaban tras el cambio: **corregido** con `BdNoDisponible`.
- **Medio**, lectura de la base en el tick con la base en falla: **corregido**.
- **Bajo**, `EscritorBD.detener` con la cola llena: devuelve falso y deja un aviso.

## DECISIONES SIN CONFIRMAR

- **D-S3c-1:** el cambio a "sin base" es **permanente hasta reiniciar** (como el del arranque). Un fallo transitorio (p. ej. un bloqueo de 10 s) deja el equipo en modo sin base, con 503 en la API y confirmación por ciclo, hasta reiniciar. Alternativas: exigir N fallos seguidos antes del cambio, o recuperarlo automáticamente al responder una sonda de la base.
- **D-S3d-1:** el respaldo en su propio hilo implica que, bajo una pausa del hilo del respaldo, la base podría escribirse antes que él. Es inocuo: la reimportación del arranque completa un respaldo incompleto frente a la base (T8 SAF-02).
- **D-S3e-1:** `source_door` ajeno se rechaza. Si un cliente legítimo necesitara operar la otra puerta (rol de servicio), habría que agregarle sesión y permisos, hoy fuera de alcance.

## Comprobaciones manuales

1. Con la base en modo de solo lectura o bloqueada a mitad de un ciclo (p. ej. renombrar la base con el equipo en marcha), el ciclo termina; aparece "Operando sin base de datos"; el siguiente ciclo pide confirmación y el ticket imprime "SIN OPERADOR / SIN BD".
2. Apagar el equipo justo después de terminar un ciclo: el respaldo en `data/respaldo_ciclos/` tiene el cierre.
3. Pantalla 2 (puerta 2): abre y cierra solo la puerta 2; el `audit_log` registra `source_door`.
