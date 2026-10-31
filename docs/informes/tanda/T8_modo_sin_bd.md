# T8 — Modo sin base de datos

Instrucción: tanda 2026-10-14 §2 T8, con las decisiones 1.7 (D-03, D-04, D-06, D-07); `planeacion_arranque_y_modo_sin_bd.md` §7 y §9.

## 1. Qué se hizo

**Alarma (D-03).** `OPERANDO_SIN_BD` pasa a ser una alerta persistente **no bloqueante**: nivel ALARMA, `bloquea=False`, despeje manual. El id no cambia. El texto ahora explica que los ciclos se registran solo en el respaldo y en el ticket, y que Opciones, calibración y usuarios no están disponibles.

**Estado de la base (§7.1).**
- `GET /db/estado` devuelve `{"estado": "OK" | "DEGRADADA"}`.
- `/status` incluye `sin_base_de_datos`.

**Ciclo sin base, con confirmación explícita en cada ciclo (§7.6).**
- Sin base, `POST /cycle/start` exige `{"confirmar_sin_registro": true}` en cada ciclo; sin eso responde 409 `confirmar_sin_registro`. Solo el booleano `true` cuenta como confirmación.
- En la UI (provisional, sin diseño), INICIAR CICLO abre un diálogo: "Base de datos no disponible… ¿Desea continuar sin registro?". Con la confirmación se llama a `ComandoIniciarCiclo.iniciarSinRegistro()`.
- El ticket imprime `SIN OPERADOR / SIN BD`, y el respaldo guarda `operador = "SIN OPERADOR / SIN BD"`.

**Login sin base (§7.6).**
- Los ciclos ya no exigían login. Opciones exige login, y el login exige la base: Opciones, calibración, parámetros y altas de usuario quedan bloqueados porque no se puede iniciar sesión (además, las rutas que usan la base responden 503 `sin_base_de_datos`).
- La pantalla de login muestra el aviso y el botón **"Continuar sin operador"**, que vuelve al menú principal.

**`CycleLogger` protegido (§7.3, BD-02).**
- `crear_ciclo`, `insertar_lectura` y `cerrar_ciclo` van dentro de `try/except`: un fallo de la base ya no sube al tick ni corta el buzzer.
- Sin base, ni siquiera se intenta escribir en ella.
- Las lecturas, el ticket y el cierre siguen aunque el ciclo no tenga id en la base (antes, sin id, no se imprimía nada).

**Respaldo por ciclo (§7.4)** (`core/runtime/respaldo_ciclos.py`, nuevo).
- Formato: `data/respaldo_ciclos/<uuid>.jsonl`, con una línea de encabezado, una por lectura (las mismas del ticket) y una de cierre.
- Cada escritura hace `flush` + `os.fsync`.
- Se escribe **siempre**, con y sin base.
- Si el disco también falla, queda en el log y el ciclo continúa.
- Al leer, una última línea cortada se descarta.

**Reimportación (§7.4).**
- Al arrancar con la base disponible, cada respaldo cuyo uuid no está en `ciclos` se importa en una sola transacción (`DbManager.importar_ciclo_respaldo`). Un respaldo sin cierre entra como INTERRUMPIDO.
- Luego el archivo se mueve a `importados/`; nunca se borra.
- Un error deja el archivo en su sitio y se reintenta en el siguiente arranque.
- Queda `ciclo_reimportado` en `audit_log`.

**Base corrupta (§7.7, BD-06).**
- Un `DatabaseError` de "not a database" o "malformed" (no un bloqueo ni un error de E/S) hace que la base se renombre a `autoclave.db.corrupta-<fecha>` (con sus `-wal`, `-shm` y `-journal`) y que se escriba la marca `data/BD_BLOQUEADA`. En ese caso no se reintenta.
- Mientras exista la marca, `DbManager` no crea la base ni siembra `admin`: el equipo sigue sin base hasta que un técnico la retire.
- Si el esquema falla, la conexión se cierra (en Windows, una conexión abierta impide renombrar el archivo).

**BD-03.** La calibración ya no queda activa sin auditoría. Se guarda el YAML previo; si `registrar_auditoria` falla, se restaura, se recarga y se responde 503 `auditoria_no_disponible`.

**D-04.** `doble_pantalla.vigilar_pantallas` (también la usa `lanzar.py`): una pantalla que se cierra se relanza hasta 3 veces, 5 s después de cada cierre, medidos con `time.monotonic`. La otra pantalla sigue abierta y el backend no se toca.

**D-06.** Verificado sin cambios: hoy solo se vigilan `temp_camara`, `temp_2_camara`, `temp_ref` y `temp_drenaje`, más las presiones de cámara, chaqueta y empaque. `temp_ref` y los sensores del ciclo dan SEN-03, que no bloquea (T3). `temp_chaqueta`, `temp_drenaje_cam` y los canales sin nombre no se leen en `EstadoAutoclave`, así que no pueden bloquear.

**D-07.** Sin prefijo: el contador persistente (T6) numera los ciclos con y sin base.

## 2. Pruebas

- `tests/test_t8_modo_sin_bd.py` (18): respaldo, reimportación idempotente, base corrupta, alarma, `CycleLogger` sin base y con la base fallando, ticket, BD-03, puente y comando.
- Ajustadas:
  - `test_endpoint_arranque`: confirmación y `/db/estado`.
  - `test_secuencia_arranque`: alarma no bloqueante.
  - `test_doble_pantalla`: casos D-04.
  - `test_lanzar_ui_qml`.
- Suite completa: ver `estado.md`.

## 3. DECISIONES SIN CONFIRMAR

- D-T8-1: "Continuar sin operador" vuelve al menú principal; no crea una sesión. Los ciclos nunca exigieron login, así que basta con impedir el login, que ya bloquea Opciones, calibración y usuarios.
- D-T8-2: el respaldo JSONL se escribe en todos los ciclos, no solo sin base. Así cubre el caso de una base que falla a mitad de ciclo.
- D-T8-3: un ciclo que estaba en la base y siguió solo en el respaldo (la base falló a mitad de ciclo) no se fusiona al reimportar: su uuid ya existe, así que la base conserva las lecturas parciales y el respaldo completo queda en `importados/`.
- D-T8-4: D-04 relanza ante cualquier cierre, incluido un cierre normal. En producción la pantalla no tiene botón de cerrar.
- D-T8-5: la reimportación solo ocurre al arrancar. La base no "vuelve" en caliente: en DEGRADADA queda así hasta reiniciar.

## 4. PENDIENTES

- La alarma por falla de escritura del respaldo: hoy queda solo en el log y en `RespaldoCiclos.ultimo_error`. Falta un id de alarma; no se creó uno nuevo sin catálogo aprobado.
- La lista de ciclos sin base (historial) no muestra los ciclos del respaldo hasta que se reimportan.
- Las UI siguen abriendo `DbManager` en algunos flujos PySide (D-01 opción B está fuera del alcance de T8).

## 5. Revisores (resultado)

**timing-auditor**: 0 críticos, 1 alto, 6 medios y 3 bajos. **safety-reviewer**: 0 críticos, 2 altos, 5 medios y 5 bajos.

Corregidos:
- **TMG-01 (alto)**: las escrituras del ciclo en SQLite podían bloquear el tick hasta 10 s (lock compartido más el timeout de sqlite), cortando el latido; con eso el watchdog apaga las salidas. Corrección:
  - El backend usa `EscritorBD`: un hilo propio con cola acotada que ejecuta las operaciones en orden.
  - El tick solo encola. Si la cola está llena, se corta el registro del ciclo en la base y no se bloquea el tick.
  - Cortacircuito por ciclo: con el primer error de la base se deja de escribir en ella durante ese ciclo, y el ciclo sigue en el respaldo y en el ticket.
  - Las pruebas siguen en línea (ejecutor síncrono por defecto).
- **TMG-03 (medio)**: la lectura y el cierre van primero al respaldo y después a la base.
- **SAF-01 (alto)**:
  - Sin base, `/cycle/start` hace antes una prueba de escritura con fsync en `data/respaldo_ciclos/`; si falla, responde 503 `respaldo_no_disponible`.
  - Si el respaldo falla durante el ciclo, se activa la alarma nueva **SIS-03** "Respaldo del ciclo no disponible" (aviso, no bloquea, despeje manual).
  - Ningún id existente se renombró.
- **SAF-02 (alto) / TMG-04 (medio)**: un ciclo que existe en la base pero quedó incompleto (la base falló a mitad de ciclo) se completa desde el respaldo. Se agregan las lecturas que faltan y, si la fila no tenía fin, el cierre real; así deja de quedar como INTERRUMPIDO. Una fila ya cerrada conserva su resultado. Queda `ciclo_completado_desde_respaldo` en `audit_log`.
- **SAF-04 / TMG-06 (medios)**: la marca `BD_BLOQUEADA` se escribe antes de mover cualquier archivo. Se mueven primero `-wal`, `-shm` y `-journal`, y la base al final.
- **SAF-05 / TMG-05 (medios)**:
  - Sin base, la calibración se rechaza de entrada (503) sin tocar el archivo.
  - La restauración del YAML es atómica: temporal, fsync y `os.replace`.
- **TMG-08 / SAF-10 (bajos)**: un fallo al lanzar una pantalla cuenta como cierre y ya no mata al vigilante.
- **SAF-11 (bajo)**: docstring de `sin_bd.py` actualizado a D-03.

Pendientes (no son altos ni críticos):
- TMG-02 / SAF-09: el fsync del respaldo sigue en el tick. Es poco frecuente (cambios de fase, intervalos de 60 a 180 s), pero hay que medirlo en el equipo real (eMMC/SSD, antivirus).
- SAF-03: la base que falla en caliente no activa OPERANDO_SIN_BD ni pide confirmación en el siguiente ciclo (hoy solo se decide al arrancar). El ticket de ese ciclo no lleva la leyenda.
- SAF-06: las alarmas y los eventos de seguridad sin base no van al respaldo.
- SAF-07: el respaldo no tiene integridad criptográfica (hash encadenado o HMAC).
- SAF-08 / TMG-09: un respaldo que no se puede importar se reintenta en cada arranque, sin alarma; `importados/` no rota.
- SAF-12: `SensorCalibrationAuditDB` y `CycleParamsAuditDB` abren SQLite directo sin respetar `BD_BLOQUEADA`.
- TMG-07: resuelto en parte por SIS-03.
- Además, `_numero_nuevo` sigue leyendo `MAX(numero)` en el tick al iniciar (pendiente de T6).

## 6. Comprobaciones manuales de Cristian

- Renombrar `data/autoclave.db` a un archivo que no sea SQLite y arrancar. Debe pasar lo siguiente:
  - la base queda apartada como `autoclave.db.corrupta-…`;
  - aparece `data/BD_BLOQUEADA`;
  - se activa la alarma "Operando sin base de datos";
  - no se crea una base nueva.
- Sin base, pulsar INICIAR CICLO: debe aparecer el diálogo de confirmación. Al confirmar, el ciclo corre y el ticket imprime `SIN OPERADOR / SIN BD`.
- En el login sin base: debe verse el aviso y el botón "Continuar sin operador".
- Quitar la marca, restaurar la base y arrancar: los ciclos del respaldo aparecen en el historial y sus archivos pasan a `data/respaldo_ciclos/importados/`.
- Cerrar una de las pantallas: se relanza a los 5 s, como máximo 3 veces.
