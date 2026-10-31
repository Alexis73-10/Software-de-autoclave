# Auditoría planes vs. código — LOTE 2 (comunicación y seguridad de la información)

- **Fecha:** 2026-10-07
- **Norma:** NTC-IEC 62304:2019 (IEC 62304:2006), Clase C — cláusulas 5.2.6, 5.4.4, 8.2.3, 7.4.
- **Base auditada:** rama `audit/62304-snapshot`, commit **8d1884c** (2026-10-07 21:37, = `dev` e7bccf2 + cambios sin commit). Todas las citas `ruta:línea` se refieren a 8d1884c.
- **Alcance:** `docs/mis_plans/planeacion_protocolo_serial_esp32.md`, `planeacion_backend_autenticacion.md`, `planeacion_endurecimiento_backend_parametros.md`, `planeacion_backend_parametros.md`.
- **Modo:** solo lectura. No se corrige ni se propone; no se decide quién tiene razón.

## Aviso sobre la base

Después de crear el snapshot, `dev` avanzó a **dd8f107** (2026-10-07 21:47, "feat: autenticación etapa 1, Nuevo usuario, ajustes de OPCIONES y ciclo en curso"). Se hizo `git diff --stat audit/62304-snapshot dev` sin interpretar los cambios:

- **Lo que dd8f107 trae del snapshot:** el código de autenticación y `planeacion_backend_autenticacion.md`.
- **Lo que dd8f107 NO trae:**
  - los tres planes restantes del lote;
  - el código del protocolo serial v2: `protocols/crc16.py`, `protocols/serial_link_config.py`, `config/serial_link.json`, los cambios de `protocols/serial_link.py` y sus pruebas;
  - el diagnóstico de comunicación en `/status` (`server.py`).

En dd8f107, `/status` usa `units.is_connected()`. Esta auditoría califica contra 8d1884c, como se pidió.

## Diferencias e7bccf2 → 8d1884c en rutas del lote

```
docs/mis_plans/planeacion_backend_autenticacion.md | 275 ++++++++
docs/mis_plans/planeacion_backend_parametros.md    | 196 ++++++
...planeacion_endurecimiento_backend_parametros.md | 230 +++++++
.../mis_plans/planeacion_protocolo_serial_esp32.md | 180 ++++++
src/autoclave/backend/autenticacion.py             | 117 ++++
src/autoclave/backend/context.py                   |  25 +-
src/autoclave/backend/contrasenas.py               |  53 ++
src/autoclave/backend/main.py                      |   6 +-
src/autoclave/backend/server.py                    | 699 +++++++++++++++++----
src/autoclave/config/serial_link.json              |  10 +
src/autoclave/core/managers/validacion_config.py   |  33 +
src/autoclave/protocols/crc16.py                   |  55 ++
src/autoclave/protocols/serial_link.py             | 312 +++++++--
src/autoclave/protocols/serial_link_config.py      | 111 ++++
.../services/domain/logging/db_manager.py          | 197 +++++-
src/autoclave/services/domain/loop/control_loop.py | 142 +++--
src/autoclave/ui/service_ui/ui_service_backend.py  |  17 +-
src/autoclave/ui_pyside/services/roles.py          |  20 +-
.../ui_pyside/services/session_manager.py          |   2 +
.../ui_pyside/services/validacion_usuario.py       |  62 ++
.../ui_pyside/views/nuevo_usuario/__init__.py      |   0
.../ui_pyside/views/nuevo_usuario/puente.py        | 160 +++++
.../ui_pyside/views/nuevo_usuario/vista.py         |  69 ++
.../ui_qml/controllers/login_controller.py         |  12 +-
24 files changed, 2727 insertions(+), 256 deletions(-)
```

---

## planeacion_protocolo_serial_esp32 (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en `dev` (ni en e7bccf2 ni en dd8f107). Solo existe en 8d1884c. Modificación del archivo: 2026-10-02 13:35. El plan se fecha a sí mismo 2026-10-02.
- Commits que lo citan: ninguno.
- Otra rama: no. `git log --all -S crc16_ccitt_false` y `-S abortar_por_falla_io` solo devuelven 8d1884c. No existe un firmware V3 en ninguna rama.
- Commits posteriores en el área (`protocols`, `set_io.py`, `Hardware`, `control_loop.py`): 8d1884c 2026-10-07 snapshot.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×18:** CRC-16/CCITT-FALSE (poli 0x1021, init 0xFFFF, sin reflexión, sin XOR) y vector `29B1` con su prueba (§4.1); formato `payload*HHHH` en hexadecimal mayúscula (§4.1); comandos del PC con sufijo CRC (§4.3); `SET DOn ON\|OFF` sin espacio (§4.3, §11.2); la línea inválida se descarta y se cuenta, y 10 consecutivas cortan la comunicación (§4.4); la vida del enlace se mide solo con líneas válidas, `DATA_TIMEOUT` 3.0 s con monotonic (§4.4, §6.2); latido de 2.0 s con monotonic (§6.3); el hilo lector no muere y un `AI:` no numérico se rechaza (§6.1); contadores de líneas inválidas en `/status` (§6.8); `serial_link.json` con defaults internos y rechazo de valores fuera de rango (§11.1); `disc_do` apagado por defecto (D-05); reintento cada 3 s (D-02); FW §5.9 conserva estado seguro 0xFFFF y `WD_TIMEOUT_MS=5000`; los hallazgos FW-03 (ACK a cualquier línea), FW-04 (`String` sin límite) y FW-05 (sin BOOT ni VER) siguen presentes en V2 | COINCIDE | crc16.py:17-55; tests/test_crc16.py (no ejecutado); serial_link.py:44-47, 58-59, 238-277, 310-363, 417-423, 436-448, 465-471; server.py:453-459, 534; serial_link_config.py:24-111; serial_link.json:1-10; .ino:24-25, 35, 38, 80, 107 | — | — |
| 1 | Firmware V3 (`Comunicacion_esclava_ESP32_V3.ino`) con: CRC en todas las líneas, buffer de 64 bytes, `lastError()` tras cada `read16`/`write16`, `pcf_ok`/`i2c_err`, MUX con `ai_inv`, reescritura periódica y `disc_do`, watchdog solo con comandos válidos, `BOOT`/`VER`, selector `(canal<<8)\|0x00FF`, `uptime_s` de 64 bits (§1, §5.1-5.8, §5.10-5.11) — 10 afirmaciones | NO IMPLEMENTADO | Solo existe `Hardware/.../Comunicacion_esclava_ESP32_V2.ino`. Ahí `"WD: ALL_OFF"` (:94), `"ACK"` (:107) y `"OK ALL_OFF"` (:116) se emiten sin CRC, y `String serialBuffer` está en :38 | — | SEGURIDAD |
| 2 | Parseo de `ST:`, `WD:`, `BOOT` y `VER` (§6.4) | NO IMPLEMENTADO | Todo lo que no es AI/DI/DO/ACK/OK se trata como `LineaMalformada("tipo de línea desconocido")` y se cuenta como inválido (serial_link.py:365-391) | — | SEGURIDAD |
| 3 | Handshake de 7 pasos en `_connect()` y en cada reconexión (§4.6, §6.6) | NO IMPLEMENTADO | `_connect()` solo abre el puerto y vacía los buffers (serial_link.py:136-160) | — | SEGURIDAD |
| 4 | `is_connected()` devuelve False mientras el handshake no sea válido (§11.10) | DIFIERE | `is_connected = port_open and data_alive` (serial_link.py:211-213); `data_alive` pasa a True con la primera línea de CRC válido (:343) | indeterminado | SEGURIDAD |
| 5 | Comparación entre lo comandado y el `DO:` reportado, reenvío y `DISCREPANCIA_SALIDAS` (§6.5, PC-03) | NO IMPLEMENTADO | `set_output()` devuelve True sin confirmar (serial_link.py:440-448); `git grep DISCREPANCIA` en src no encuentra nada | — | SEGURIDAD |
| 6 | Nuevo handshake tras `WD:` o `BOOT` inesperado (§6.7) | NO IMPLEMENTADO | serial_link.py:365-391 | — | SEGURIDAD |
| 7 | Clasificación de fallos de E/S (§7); `abortar_por_falla_io()` en `ciclo.py` (§11.5) | NO IMPLEMENTADO | No existe en ciclo.py ni en ninguna rama (`git log --all -S` solo encuentra el texto del plan en 8d1884c) | — | SEGURIDAD |
| 8 | Alarmas `TARJETA_*` y textos en `es.json` (§11.6) | NO IMPLEMENTADO | `git grep TARJETA_` en src no encuentra nada | — | SEGURIDAD |
| 9 | Un firmware V2 conectado al PC nuevo se rechaza **por `VER`, con mensaje explícito** (§2.1, §8.7) | DIFIERE | Como V2 no envía CRC, todas sus líneas son inválidas y a las 10 se desconecta y reintenta (serial_link.py:321-324, 358-363). No hay mensaje de incompatibilidad | indeterminado | SEGURIDAD |
| 10 | — | SIN DOCUMENTAR | Claves configurables declaradas que ningún código consume: `handshake_presupuesto_s`, `all_off_intentos`, `all_off_timeout_s`, `tramas_discrepancia`, `disc_do_dispara_fallo` (serial_link_config.py:29-41; `git grep` sin otros usos) | — | FUNCIONAL |
| 11 | — | SIN DOCUMENTAR | El respaldo de `reset_all_outputs()`, si falla ALL_OFF, apaga solo los canales 1-24; el bitstream DO tiene 32 (set_io.py:176-184; serial_link.py:71) | — | SEGURIDAD |
| 12 | Configuración del firmware conservada: lectura por ADC1, resolución y atenuación, promedio de 64 muestras (§5.9) | NO VERIFICADO | No se leyó el cuerpo del .ino | — | — |
| 13 | FW-01, FW-02, FW-06, FW-07 (hallazgos sobre el estado de V2) | NO VERIFICADO | No se leyó el cuerpo del .ino; el `grep` de `canal << 8` no encontró coincidencias | — | — |

**Resumen:** 43 afirmaciones: COINCIDE 18 · DIFIERE 2 · NO IMPLEMENTADO 16 · SIN DOCUMENTAR 2 · NO VERIFICADO 5 (filas 12-13).

---

## planeacion_backend_autenticacion (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en e7bccf2. Modificación del archivo: 2026-10-07 14:14. Entra a `dev` en dd8f107 (2026-10-07 21:47), después del snapshot.
- Commits que lo citan por nombre: ninguno.
- Otra rama: `dev` dd8f107 contiene el mismo código de autenticación (la única diferencia con el snapshot en `server.py` es `/status`).
- Commits posteriores en el área: 8d1884c (snapshot) y dd8f107 (dev).

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×37:** host `127.0.0.1` fijo (D1); token `secrets.token_urlsafe(32)` en memoria, que se pierde al reiniciar (D2, §5.1); cabecera Bearer; PBKDF2-SHA256 de 600 000 iteraciones con formato `pbkdf2$…` (D4); semillas `admin`/`ingeniero` con `debe_cambiar_clave` (D5); 403 por `debe_cambiar_clave` salvo en `change_password`/`logout`; lectura sin token (D6, §4.2); endpoints operativos sin token (D7, §4.3); campo `operador` ausente porque la tabla no existe (D7, condición no cumplida); `git_autocommit` eliminado (D9); bloqueo de 5 intentos / 5 min por usuario, con monotonic y casefold (D10, §5.6); guard "distinto de CICLO" (D13); excepción del ingeniero en CICLO (D14); el modo prueba se bloquea en HIBERNACION/EMERGENCIA (D15, D20); `/fault/reset` sin identificación (D16); puerta automática con la regla vigente (D21); programas no seleccionados editables en CICLO (D23); roles sin `biomedico` (D25); calibración y parámetros solo ingeniero, prueba técnico+ingeniero (D25); reglas de `POST /usuarios` con 403/409/422 y casefold (D26); puente de Nuevo usuario contra el endpoint (T-20); un hash sin `pbkdf2$` nunca valida (D27); `audit_log` en la migración v1 con `user_version` (D28); 401 genérico, 429 con usuario bloqueado, cuenta también usuarios inexistentes (D29); el logout de la sesión de prueba sale y apaga (D30); `PATCH /cycle/parameters`, `/io/test/reset_all` y `ticket.txt` eliminados (D32, §4.6); `/outputs/reset` da 409 en CICLO; `/io/test/enter`, `/exit` y `/output` con su guard y R-02 (§4.5, §5.4); `requiere_rol` 401/403 con el rol tomado del token (§5.2); guard bajo `_sm_lock` (§5.5); `compare_digest` (§5.6); calibración inmediata en CICLO (§5.8); `audit_log` con ciclo, fase, programa y `aplica` (§5.8, §5.10); `GET /calibration` toma el último cambio de `audit_log` o de la tabla histórica (§5.10) | COINCIDE | main.py:9, 31-33; autenticacion.py:15-117; contrasenas.py:14-53; server.py:63-79, 125-217, 227-350, 360-450, 912-1012, 1072-1121, 1143-1275; db_manager.py:115-126, 129-158, 227-241, 592-633; roles.py:13-31; puente.py:34-43, 114-122; ciclo.py:304 | — | — |
| 1 | El login se hace en el backend y QML deja de leer SQLite (D3, T-8); el puente QML guarda el token y maneja 401/403/409 (§5.7) | NO IMPLEMENTADO | `LoginController` sigue validando contra SQLite, marcado "PROVISIONAL hasta T-8 (etapa 4)" (login_controller.py:3-7, 76-77). Ese camino no aplica el bloqueo por intentos ni `debe_cambiar_clave`, y no obtiene token | — | SEGURIDAD |
| 2 | Hash con **sal aleatoria por usuario** (D4) | DIFIERE | Las semillas usan un hash precalculado con sal fija (db_manager.py:116-126) | indeterminado | SEGURIDAD |
| 3 | Logins fallidos y **rechazos 401/403/409 de acciones físicas** y de configuración van a `audit_log` (D10) | DIFIERE | Los rechazos de puertas (403) y de `/cycle/start` (409) se lanzan con `HTTPException` sin auditar (server.py:923-927, 1020-1025, 1040-1045) | indeterminado | SEGURIDAD |
| 4 | El simulador replica 401/403/409 y acepta un token fijo (D11, T-14) | NO IMPLEMENTADO | `git grep token\|Bearer\|/auth` en simulador/servidor.py no encuentra nada | — | FUNCIONAL |
| 5 | Puertas con guard 409 en CICLO, HIBERNACION y EMERGENCIA (D15, D20, §4.3, §5.3, T-13) | NO IMPLEMENTADO | `open_door`/`close_door` solo comprueban la configuración inválida y responden 403 (server.py:1015-1052) | — | SEGURIDAD |
| 6 | Apertura rechazada si falta `pres_camara`, `temp_camara` o la configuración (§5.3, OPC-16) | NO IMPLEMENTADO | "Si los parámetros de config no están disponibles, permitir (modo degradado)" (ser_puertas.py:140-159) | — | SEGURIDAD |
| 7 | Valores leídos en vivo, no copiados en `__init__` (§5.3, OPC-11) | NO IMPLEMENTADO | ser_puertas.py:41-44 | — | SEGURIDAD |
| 8 | Cierre rechazado si falta una presión que interviene o la configuración atmosférica (§5.3) | NO IMPLEMENTADO | Si la presión o la configuración son None, se omite la comprobación (ser_puertas.py:181-194) | — | SEGURIDAD |
| 9 | Cierre rechazado con estado propio DESCONOCIDO (D18) | NO IMPLEMENTADO | Solo rechaza CERRADO/CERRANDO (ser_puertas.py:172-175) | — | SEGURIDAD |
| 10 | `request_open`/`request_close` devuelven el resultado real: 409 y "sin actuador" (D19, T-18) | NO IMPLEMENTADO | Devuelven True tras despachar el comando (ser_puertas.py:71-73, 86-88) | — | SEGURIDAD |
| 11 | `/cycle/acknowledge` restablece **todo** FALLO; con paro activo, `acknowledge` y `/fault/reset` dan 409 y se descarta `RESET_FALLA` (D22, §5.9, T-16) | NO IMPLEMENTADO | Solo `FALLO_*` o `EMERGENCIA` (server.py:1008-1010); ningún chequeo de paro en server.py:953-962, 987-1012 | — | SEGURIDAD |
| 12 | `temp_chaqueta` eliminado del mapa de ejecución (D24, T-19) | NO IMPLEMENTADO | status.py:16; server.py:491; preparacion.py:116 | — | FUNCIONAL |
| 13 | `ciclo_controller.py` usa la constante de URL común (§5.7, T-15) | NO IMPLEMENTADO | Tiene su propia `URL_BACKEND` (ciclo_controller.py:23) y no respeta `AUTOCLAVE_BACKEND_URL` (app.py:49-54) | — | FUNCIONAL |
| 14 | Ingeniero en CICLO: un cambio a una fase no iniciada aplica al ciclo en curso, con copia profunda (§5.8, T-17) | DIFIERE | Editar el programa en curso da 409 "PROVISIONAL hasta T-17" y `aplica` siempre vale "siguiente" (server.py:1087-1094, 1106) | indeterminado (código marcado provisional) | SEGURIDAD |
| 15 | Código de evento `falla_reconocida` (§5.10) | DIFIERE | No existe (`git grep falla_reconocida` sin resultados). Los otros 14 códigos sí existen | indeterminado | SEGURIDAD |
| 16 | Implementación en **una sola fase** (§1) | DIFIERE | El código se declara "etapa 1" y pospone tareas a las etapas 3 y 4 (server.py:1092-1093; login_controller.py:6). La decisión 31 del propio plan también habla de etapas | indeterminado | FUNCIONAL |
| 17 | — | SIN DOCUMENTAR | Con `CONFIGURACION_INVALIDA` se rechazan `/cycle/start`, puertas y modo prueba (server.py:178-183, 921, 1018, 1038, 1157-1159; context.py:106-123) | — | SEGURIDAD |
| 18 | — | SIN DOCUMENTAR | Apagado ordenado en el `lifespan`: `control_loop.stop()` al detener el backend (server.py:32-43) | — | SEGURIDAD |
| 19 | — | SIN DOCUMENTAR | Encender una salida en prueba exige además ser la sesión dueña (server.py:1261-1265) | — | SEGURIDAD |
| 20 | — | SIN DOCUMENTAR | Con el login QML local la sesión no tiene token, así que Nuevo usuario no puede crear usuarios desde QML (session_manager.py:18-19; puente.py:114-116) | — | FUNCIONAL |
| 21 | — | SIN DOCUMENTAR | `secado.py:135` (PySide) sigue llamando a `PATCH /cycle/parameters`, que ya no existe | — | FUNCIONAL |
| 22 | — | SIN DOCUMENTAR | La búsqueda del login distingue mayúsculas (`usuario=?`), mientras el bloqueo y `existe_usuario` usan casefold (db_manager.py:592-607; autenticacion.py:80-82) | — | FUNCIONAL |

**Resumen:** 60 afirmaciones: COINCIDE 37 · DIFIERE 5 · NO IMPLEMENTADO 12 (las filas 1 y 5 agrupan 2 afirmaciones cada una) · SIN DOCUMENTAR 6.

---

## planeacion_endurecimiento_backend_parametros (código @ 8d1884c)

**Estado:**
- El plan se declara **BORRADOR rev. 3, pendiente de aprobación**.
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-02 13:36.
- Commits que lo citan: ninguno.
- Otra rama: no.
- Commits posteriores en el área: 8d1884c.
- **Choca con `planeacion_backend_autenticacion.md` v6 (cerrada para implementación):** estados permitidos (D-1 frente a D13), roles (D-2 frente a D25), identidad declarada (D-8 frente a D2), `PATCH /cycle/parameters` (D-12 frente a D32) y `_sm_lock` (RB-01.2 frente a §5.5). Es pertinente para 5.2.6 (requisitos sin contradicción).

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| 1 | D-1/RB-01.1: edición solo en PREPARACION o PREPARADO (lista blanca), bloqueada en FALLA | DIFIERE | Guard "distinto de CICLO", que permite FALLA, con excepción del ingeniero en CICLO (server.py:76, 1087-1094) | plan desactualizado probable (planeacion_backend_autenticacion D13-D14) | SEGURIDAD |
| 2 | D-2/RB-02.2: editan biomédico, técnico e ingeniero | DIFIERE | Solo ingeniero (server.py:1074); `biomedico` eliminado (roles.py:10-15) | plan desactualizado probable (D25) | SEGURIDAD |
| 3 | D-3/RB-03.1: la auditoría la escribe el backend | COINCIDE | server.py:1119-1120 (en `audit_log`) | — | — |
| 4 | RB-03.1: `params_ciclo.py` deja de insertar en la auditoría | NO VERIFICADO | params_ciclo.py:29, 366 instancian `CycleParamsAuditDB`; no se leyó si inserta | — | — |
| 5 | D-4/RB-06: `valor_anterior_esperado` y 409 `VALOR_CAMBIO` | NO IMPLEMENTADO | `_CycleParamValueBody` sin ese campo (server.py:1055-1059) | — | FUNCIONAL |
| 6 | D-5/RB-05.4: 0 prohibido, con mínimo mayor que 0 en los parámetros del Anexo A | NO IMPLEMENTADO | Los JSON siguen con mínimo 0 (p. ej. `rango_temp_estabilizacion`, factory/instrumental_134.json:68); no hay catálogo | — | SEGURIDAD |
| 7 | D-6/RB-05.1-2: catálogo de parámetros en código | NO IMPLEMENTADO | `git grep catalogo_parametros` sin resultados | — | SEGURIDAD |
| 8 | D-7/D-10/RB-04.5: programas de usuario en `app_root()/data/cycles/user/` | NO IMPLEMENTADO | Se cargan desde el paquete (cycle_manager.py:9, 82-83, 101-102); paths.py:8, 25 solo tiene `app_root` y `calibration_path` | — | FUNCIONAL |
| 9 | D-8/RB-02.1/RB-02.3: identidad declarada por el cliente, `identidad_verificada=0` | DIFIERE | Identidad tomada del token verificado (server.py:134-150) | plan desactualizado probable (D2) | SEGURIDAD |
| 10 | D-9: host `127.0.0.1` y comentarios de dos PC corregidos | COINCIDE | main.py:9, 31-33; `git grep` "dos pc\|0.0.0.0" sin resultados | — | — |
| 11 | D-11: el programa activo se edita en PREPARACION/PREPARADO con efecto inmediato | COINCIDE | cycle_manager.py:70; server.py:1098 | — | — |
| 12 | D-12: `PATCH /cycle/parameters` se conserva como envoltorio | DIFIERE | Eliminado; `secado.py:135` aún lo llama | plan desactualizado probable (D32) | FUNCIONAL |
| 13 | D-13/RB-03.7: triggers de solo anexar | NO IMPLEMENTADO | `git grep "CREATE TRIGGER"` sin resultados | — | SEGURIDAD |
| 14 | D-14/RB-03.2: nuevas columnas en `cycle_params_audit` (`usuario_login`, `rol`, `accion`, `identidad_verificada`…) | DIFIERE | Se usa la tabla nueva `audit_log` (db_manager.py:138-149); `cycle_params_audit` sin cambios | plan desactualizado probable (D28) | FUNCIONAL |
| 15 | D-15/RB-09: timeout de escritura de 5 s y resultado incierto | NO IMPLEMENTADO | backend_client.py:34, 42, 52 (`timeout=0.8`) | — | FUNCIONAL |
| 16 | RB-01.2: el hilo HTTP NO toma `_sm_lock` | DIFIERE | `guard_estado` toma `_sm_lock`, que ahora es RLock (server.py:153-175; control_loop.py:50) | plan desactualizado probable (§5.5 de autenticación) | SEGURIDAD |
| 17 | RB-01.3: `_param_lock` y diferir el inicio de ciclo un tick | NO IMPLEMENTADO | `git grep _param_lock` sin resultados | — | SEGURIDAD |
| 18 | RB-01.5/RB-07: códigos `EDICION_BLOQUEADA_ESTADO` y otros, con cuerpo `{codigo, mensaje}` | DIFIERE | 409 con `detail` de texto libre (server.py:107-112, 172) | indeterminado | FUNCIONAL |
| 19 | RB-02.2: lista de roles en un módulo compartido, no en `ui_pyside` | DIFIERE | server.py:25 importa de `ui_pyside.services.roles` | indeterminado | FUNCIONAL |
| 20 | RB-03.3: sello con segundos | NO VERIFICADO | No se leyó `registrar_auditoria` | — | — |
| 21 | RB-03.5: si la auditoría falla, el cambio no se aplica | DIFIERE | `_auditar` corre después del cambio; un fallo se registra y no deshace (server.py:88-104, 1113-1120) | indeterminado | SEGURIDAD |
| 22 | RB-03.6: `database is locked` → 503 `BASE_OCUPADA` | NO IMPLEMENTADO | `git grep BASE_OCUPADA` sin resultados | — | FUNCIONAL |
| 23 | RB-03.8: ruta de última modificación de parámetros | NO IMPLEMENTADO | Solo existe para calibración (server.py:378-394) | — | FUNCIONAL |
| 24 | RB-03.9: sin `PRAGMA user_version` | DIFIERE | Implementado (db_manager.py:227-241) | plan desactualizado probable | FUNCIONAL |
| 25 | RB-04.1: escritura atómica (temporal + fsync + `os.replace`) | DIFIERE | `_save_cycle_json` abre el definitivo en modo "w" (server.py:1124-1134) | indeterminado | SEGURIDAD |
| 26 | RB-04.2: copia `.json.bak` | NO IMPLEMENTADO | `git grep .json.bak` sin resultados | — | SEGURIDAD |
| 27 | RB-04.3: git en hilo aparte, de mejor esfuerzo | DIFIERE | git eliminado del todo | plan desactualizado probable (D9) | FUNCIONAL |
| 28 | RB-04.4: archivo dañado marcado como no ejecutable, logging en vez de `print` | NO IMPLEMENTADO | `print` y descarte silencioso (cycle_manager.py:106-107, 131-132) | — | SEGURIDAD |
| 29 | RB-05.3: tipos estrictos (rechazar `"false"`, NaN, infinito, flotante en entero, cadena numérica) | NO IMPLEMENTADO | `bool(value)`, `float(value)` e `int(value)` sin validar (cycle_manager.py:56-61); el cuerpo acepta `value: object` (server.py:1059) | — | SEGURIDAD |
| 30 | RB-05.6/RB-08: servicio único `ServicioConfiguracionCiclo` | NO IMPLEMENTADO | `git grep` sin resultados | — | FUNCIONAL |
| 31 | §3: si F0 pasa de falso a verdadero durante ESTERILIZACION, `_timer_timeout_max=None` → `TypeError` | COINCIDE | esterilizacion.py:181-182, 286. Mitigación provisional: el programa en curso no se edita en CICLO (server.py:1091-1094) | — | — |

**Resumen:** 31 afirmaciones: COINCIDE 4 · DIFIERE 12 · NO IMPLEMENTADO 13 · NO VERIFICADO 2.

---

## planeacion_backend_parametros (código @ 8d1884c)

**Estado:**
- El plan se declara borrador v1 y depende de la autenticación.
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-07 14:14.
- Commits que lo citan: ninguno.
- Otra rama: no.
- Commits posteriores en el área: 8d1884c.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| 1 | Tabla `system_params` sembrada desde el JSON (D1, §4.1, §4.2.1) | NO IMPLEMENTADO | Solo existe la migración v1 (db_manager.py:129-158); `ConfigManager` lee el JSON (config_manager.py:10-14) | — | SEGURIDAD |
| 2 | Si falta una clave esperada al arrancar, el arranque falla con alarma (§4.2.2) | DIFIERE | Solo se valida `rango_presion_atm` (1-10 kPa); si falla, alarma `CONFIGURACION_INVALIDA` y bloqueo (validacion_config.py:9-33; context.py:106-123) | indeterminado (implementación parcial declarada en el código) | SEGURIDAD |
| 3 | `ConfigManager` con RLock y `set()` transaccional (§4.3) | NO IMPLEMENTADO | config_manager.py:6-25 | — | FUNCIONAL |
| 4 | `get()` sin `or` ni respaldo; un 0 es válido (§4.3, §11, OPC-13) | NO IMPLEMENTADO | `or 101.3` / `or 20.0` en base_fase.py:44, 47; protocolo_fallo.py:70-71, 166-167; advanced_door.py:397-398, 492-493 | — | SEGURIDAD |
| 5 | `PATCH /global_params/{clave}` y `POST …/reset` (§5) | NO IMPLEMENTADO | No existe la ruta (lista de `@app` en server.py) | — | FUNCIONAL |
| 6 | `GET /global_params` con mín, máx, defecto, usuario y fecha (§5) | DIFIERE | Devuelve el JSON cargado tal cual (server.py:550-552) | indeterminado | FUNCIONAL |
| 7 | `GET /audit_log` (§5) | NO IMPLEMENTADO | No existe la ruta | — | FUNCIONAL |
| 8 | Lectura en vivo en `ServicioPuertas` y `preparado_state` (§6.1-6.2, OPC-11) | NO IMPLEMENTADO | ser_puertas.py:41-44; preparado.py:18 | — | SEGURIDAD |
| 9 | `advanced_door`: `timeout_puerta` se lee al armar el temporizador (§6.3) | COINCIDE | advanced_door.py:372, 461 | — | — |
| 10 | Columnas de `audit_log` (§7) | COINCIDE | db_manager.py:138-149 | — | — |
| 11 | Eventos `param_sistema_cambio`, `calibracion_atm_*`, `suspension_*` (§7) | NO IMPLEMENTADO | `git grep param_sistema_cambio` sin resultados | — | FUNCIONAL |
| 12 | Calibración atmosférica: endpoints, flag `calibracion_en_curso`, ventana de 120 s (§8) | NO IMPLEMENTADO | `git grep atm-calibration\|calibracion_en_curso` sin resultados | — | SEGURIDAD |
| 13 | Tablas de entradas mostradas y `lecturas_grafica (ciclo_id, t, entrada, valor)` (§9.1) | NO IMPLEMENTADO | La gráfica sigue con las columnas fijas `temp_camara`/`temp_ref`/`pres_camara` (server.py:855-861) | — | FUNCIONAL |
| 14 | Módulo `io_names` (§9.3) | NO IMPLEMENTADO | `git grep io_names` sin resultados | — | FUNCIONAL |
| 15 | Migraciones numeradas, atómicas y con registro de versión (§10.2) | COINCIDE | db_manager.py:129-158, 225-241 | — | — |
| 16 | Migración v2 (§10.1) | NO IMPLEMENTADO | `_MIGRACIONES` solo tiene v1 (db_manager.py:154-158) | — | FUNCIONAL |
| 17 | Renombres `presion_admosferica` e `intervalo_imprecion…` (§11) | NO IMPLEMENTADO | global_params.json:3, 13 (el plan los programa para después de unir `alarmas-parte-a`) | — | COSMÉTICO |
| 18 | Eliminar `temp_max` y `tipo_puerta` del JSON (§11) | NO IMPLEMENTADO | global_params.json:2, 9 | — | COSMÉTICO |
| 19 | `git_autocommit` eliminado (D10) | COINCIDE | Sin archivo ni referencias en src | — | — |
| 20 | `time.monotonic()` en `advanced_door`, `buzer` y `cycle_logger` (§12, OPC-08) | NO IMPLEMENTADO | `time.time()` en advanced_door.py:350, 353, 372, 416, 461, 514, 554, 557; buzer.py:23, 37; cycle_logger.py:229, 362, 375 | — | SEGURIDAD |
| 21 | `temp_chaqueta` eliminado del mapa (§15) | NO IMPLEMENTADO | status.py:16 | — | FUNCIONAL |
| 22 | — | SIN DOCUMENTAR | El código dice que el rango `rango_presion_atm` 1-10 kPa fue "decidido en planeacion_backend_parametros.md" (validacion_config.py:9-10, 13), pero el plan no contiene ese rango | — | SEGURIDAD |

**Resumen:** 22 afirmaciones: COINCIDE 4 · DIFIERE 2 · NO IMPLEMENTADO 15 · SIN DOCUMENTAR 1.

---

## 1. Resumen del lote

| Plan | Afirm. | COINCIDE | DIFIERE | NO IMPL. | EN OTRA RAMA | SIN DOC. | NO VERIF. |
|---|---|---|---|---|---|---|---|
| planeacion_protocolo_serial_esp32 | 43 | 18 | 2 | 16 | 0 | 2 | 5 |
| planeacion_backend_autenticacion | 60 | 37 | 5 | 12 | 0 | 6 | 0 |
| planeacion_endurecimiento_backend_parametros | 31 | 4 | 12 | 13 | 0 | 0 | 2 |
| planeacion_backend_parametros | 22 | 4 | 2 | 15 | 0 | 1 | 0 |
| **Total** | **156** | **63** | **21** | **56** | **0** | **9** | **7** |

Nota: el código de autenticación del snapshot también está en `dev` dd8f107, que es posterior al snapshot. No se cuenta como "en otra rama" porque `dev` es la línea base.

## 2. Discrepancias con impacto SEGURIDAD, por criticidad aparente

1. **Login QML sin pasar por el backend:** sigue validando contra SQLite, sin bloqueo por intentos, sin cambio de contraseña obligatorio y sin token (AUT 1).
2. **Puertas:**
   - sin guard de estado: se abren en CICLO, HIBERNACION y EMERGENCIA (AUT 5);
   - se abren y se cierran con sensor o configuración ausentes (AUT 6, 8);
   - el cierre con estado DESCONOCIDO no se rechaza (AUT 9);
   - se responde éxito sin confirmar el movimiento (AUT 10);
   - los parámetros se copian en `__init__` (AUT 7, PAR 8);
   - el temporizador `timeout_puerta` usa `time.time()` (PAR 20).
3. **Protocolo serial:**
   - el firmware V3 no existe (SER 1);
   - el PC del snapshot no hace handshake ni ALL_OFF al conectar (SER 3);
   - no interpreta `WD:`, `BOOT` ni `ST:` (SER 2, 6);
   - no compara salidas (SER 5);
   - declara la conexión con la primera línea válida (SER 4);
   - con el firmware V2 actual nunca conecta, sin mensaje explícito (SER 9);
   - nada de esto está en `dev` dd8f107.
4. **Reconocimiento de fallas:** `/cycle/acknowledge` no cubre todo FALLO, y `RESET_FALLA` no se descarta con el paro activo (AUT 11).
5. **Escritura de parámetros de ciclo:**
   - acepta `value` de cualquier tipo (`bool("false")` da True, NaN pasa) (END 29);
   - escribe el JSON en modo "w", sin atomicidad ni `.bak` (END 25, 26);
   - la auditoría no es atómica con el cambio (END 21);
   - un JSON dañado se descarta en silencio (END 28);
   - no hay catálogo ni mínimos mayores que 0 (END 6, 7).
6. **Planes contradictorios entre sí** (endurecimiento frente a autenticación): estados, roles, identidad, `_sm_lock`, `/cycle/parameters` (END 1, 2, 9, 12, 16).
7. **Respaldos `or 101.3` / `or 20.0`** en fases, protocolo de fallo y puertas (PAR 4); `system_params` y su validación completa al arrancar no existen (PAR 1, 2).
8. **Rechazos no auditados:** puertas y `/cycle/start` no quedan en `audit_log` (AUT 3); falta el evento `falla_reconocida` (AUT 15).
9. **ALL_OFF de respaldo incompleto:** solo apaga los canales 1-24 de 32 (SER 11).
10. **Ingeniero en CICLO:** la regla de fases pendientes está reemplazada por un 409 provisional (AUT 14).
11. **Semillas con sal fija** (AUT 2).
12. **Calibración atmosférica** no implementada (PAR 12).
13. **CONFIGURACION_INVALIDA y su rango 1-10 kPa:** atribuidos a un plan que no los contiene (PAR 22, AUT 17).

## 3. Qué no se pudo verificar y por qué

- **Firmware V2:** no se leyó el .ino completo. FW-01, FW-02, FW-06, FW-07 y la configuración de ADC quedan NO VERIFICADO.
- **Pruebas no ejecutadas:** no se corrió pytest (`test_crc16.py`, `test_serial_link_v2_lector.py`, `test_backend_autenticacion.py`, etc.). No se califica la verificación de cambios (8.2.3).
- **Hardware:** no se probó con la tarjeta. No hay evidencia del comportamiento real del enlace.
- **Archivos no leídos:**
  - `params_ciclo.py` (si aún inserta auditoría);
  - `registrar_auditoria` (formato del sello);
  - `es.json`;
  - el manejo de 401/403/409 en QML;
  - `simulador/servidor.py` completo;
  - los informes `docs/informes/autenticacion_etapa1_*.md`.
- **Divergencia snapshot / dev:** `dev` dd8f107 es posterior al snapshot y difiere en el protocolo serial. Lo auditado aquí no representa exactamente el `dev` actual.
