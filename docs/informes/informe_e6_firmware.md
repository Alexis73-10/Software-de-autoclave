# Informe E6: firmware 1.0.0 y Fase B recortada del enlace serial

Fecha: 2026-10-14. Instrucción: `docs/mis_plans/instruccion_claude_code_e6_firmware.md`.
Spec: `planeacion_firmware_1_5.md` (v2) y `planeacion_protocolo_serial_esp32.md` (normativo).
**Sin commit** (lo confirma Cristian). No se tocó hardware, no se compiló ni se instaló nada.

## 1. Resumen

- **Parte 1, firmware 1.0.0:** escrito en `Hardware/Comunicacion_esclava_ESP32_V3/`. Incluye `LEEME_carga.md`.
  Está **sin compilar**: no hay compilador en este equipo y la instrucción lo prohíbe. Se revisó a mano (§5).
- **Parte 2, PC:** puntos 1 a 9 de §5 implementados, con dos excepciones:
  - Los textos de las alarmas nuevas **no** se agregaron a `es.json`, porque no existe un formato de alarmas en ese archivo. Ver la pregunta P1.
  - El emparejamiento no genera una alarma nueva. La advertencia es por log, `audit_log` y la pantalla Información del sistema. Ver la pregunta P3.
- **Pruebas:**
  - Línea base: 2656 pasan. La instrucción decía 2440; el árbol creció desde que se escribió.
  - Después del cambio: **2765 passed** (6 warnings, 0 fallos; +109 pruebas). Se ajustaron pruebas existentes de 4 archivos, por cambio de comportamiento que pide la spec o por la firma nueva de `build_serial` (§3).

## 2. Archivos

Nuevos:

| Archivo | Contenido |
|---|---|
| `Hardware/Comunicacion_esclava_ESP32_V3/Comunicacion_esclava_ESP32_V3/Comunicacion_esclava_ESP32_V3.ino` | Firmware 1.0.0, protocolo 2 |
| `Hardware/Comunicacion_esclava_ESP32_V3/LEEME_carga.md` | Procedimiento de §8, librería PCF8575 0.2.5, paquete esp32 3.3.7, líneas con CRC para probar a mano |
| `tools/emparejar_tarjeta.py` | `--mostrar` y `--id <ID12>`. Mismo patrón que `declarar_entradas_suministro.py`: confirmación SI, respaldo `.bak`, validación y registro en `installation_profile_cambios.log` |
| `tests/test_e6_enlace_handshake.py` | 53 pruebas: handshake y cada fallo, parseo, eventos, comparación DO, latido FW-D6 |
| `tests/test_e6_control_loop_tarjeta.py` | 18 pruebas: reacción del lazo y `abortar_por_falla_io` |
| `tests/test_e6_emparejamiento_tarjeta.py` | 38 pruebas de `board_id`, herramienta, `/status.tarjeta`, `audit_log` e Información del sistema |

Modificados:

| Archivo | Cambio |
|---|---|
| `protocols/serial_link.py` | Handshake §4.6. `is_connected()` exige el handshake. Parseo de `BOOT`/`VER`/`ST:`/`WD:`. Eventos (`EventoTarjeta`, `tomar_eventos()`). Comparación comandado vs `DO:` con un solo reenvío. Nuevos `marcar_tick_control()`, `solicitar_handshake()`, `tarjeta()` y el callback `al_conectar`. `set_output`/`all_off` no envían nada sin handshake. `get_diagnostico()` agrega `handshake_completo` y `tarjeta_st` |
| `services/domain/loop/control_loop.py` | `_tick()` llama primero a `marcar_tick_control()` y luego procesa los eventos de la tarjeta. **`run()` no se tocó** (E0-4) |
| `state_machine/states/ciclo.py` | `abortar_por_falla_io(alarm_id, motivo)`, análogo a `abortar_por_desconexion()`. Este último no se tocó |
| `installation/profile.py`, `storage.py` | `board_id` opcional, validado como 12 dígitos hex en mayúscula. Nueva función `tarjeta_emparejada()` |
| `backend/server.py` | `/status.tarjeta = {version, id, emparejada}`. Se conservan los contadores en `comunicacion` |
| `backend/context.py`, `devices/factory/factory.py` | `_al_conectar_tarjeta`: escribe en `audit_log` (`tarjeta_conectada`) en cada conexión y advierte si la tarjeta no está emparejada. Se registra antes de `start()` |
| `ui_qml/bridge/info_equipo.py`, `Componentes/PanelEquipo.qml` | Filas Versión de tarjeta, ID de tarjeta y Tarjeta del equipo (Emparejada / No emparejada), leídas de `GET /status`. El splash no se tocó |
| `ui_qml/assets/textos/es.json` | 4 claves en `equipo` para esas filas. El archivo ya tenía cambios ajenos sin commitear (bloque `instalacion`); no se tocaron |
| `docs/catalogo_alarmas.md` | Nueva §2.2 con los 9 ids, una fila en §4.1 y una fila en §9. No se cambió ningún id existente |
| `tests/serial_doble.py` | Se agregan `TarjetaSimulada` (firmware 1.0.0 simulado: `BOOT`, `VER`, `ST` con `sync`, `WD:`, ACK, ALL_OFF, SET y cada fallo del handshake) y `st()` |

## 3. Pruebas

- Antes: `python -m pytest -q -p no:cacheprovider` → **2656 passed** (6 warnings, 7 min).
- Después: **2765 passed** (6 warnings, 0 fallos; +109 pruebas).
- Cada prueba nueva se vio fallar antes de implementar (AttributeError / ImportError / aserción).

Pruebas existentes ajustadas porque la spec cambia su comportamiento:

- `test_serial_link_v2_lector.py`:
  - `test_latido_usa_monotonic…` y `test_latido_lleva_crc`: ahora el HB exige handshake completo y un tick reciente (FW-D6).
  - `test_set_output_envia_comando_con_crc`: ahora exige handshake.
- `test_info_equipo.py`:
  - La versión de tarjeta ya tiene fuente, así que deja de mostrar "No disponible".
  - `actualizar()` también consulta `/status`.
- `test_arranque_sin_tarjeta.py` y `test_secuencia_arranque.py`: los dobles de `build_serial` aceptan el argumento nuevo `al_conectar`. Sin ese ajuste fallaban 3 pruebas con `TypeError`; lo que prueban no cambia.

Nota: `tests/test_flujo_unidades.py` y `tests/test_serial_directo.py` son scripts manuales con un bucle infinito. La suite normal no los ejecuta. Si se pasan a pytest a mano, se cuelgan. Ya pasaba antes de E6.

## 4. Comprobaciones manuales de Cristian (§6 de la spec, en banco, sin autoclave y sin carga)

1. Vector CRC en C++: el firmware se autoprueba al arrancar. Si `crc16("123456789") != 0x29B1`, no emite `BOOT` y se queda con todo apagado. Que aparezca `BOOT` ya prueba el vector. En Python lo cubre `tests/test_crc16.py`.
2. Arranque: salidas en 0 desde el encendido hasta `BOOT`. Medir con osciloscopio o multímetro una salida durante 10 ciclos de energía.
3. Línea sin CRC, con CRC malo, larga sin `\n` (más de 63 caracteres) y con `\r`:
   - Las tres primeras se descartan: sube `crc_rx_err` en la `ST`, no hay ACK y el watchdog no se reinicia.
   - Con `\r` final la línea sigue siendo válida.
4. `SET DO4 ON*F896` justo después de `BOOT`: rechazado (sin `OK`, la salida no cambia). Después de `ALL_OFF*70D2`: aceptado (`OK DO4 ON`).
5. Tras `ALL_OFF`, 5 s sin líneas válidas: llega `WD: ALL_OFF`, las salidas se apagan, la `ST` muestra `wd=1` y `sync=0`, y todo `SET` se rechaza hasta un nuevo `ALL_OFF`.
6. Desconectar un PCF con el equipo en reposo:
   - El bit de ese PCF baja en `pcf_ok` y sube `i2c_err`.
   - Al reconectarlo, `pcf_ok` vuelve a `3F`.
   - Con el PC conectado debe aparecer `TARJETA_EXPANSOR_FUERA_DE_LINEA` y, al reconectar, un nuevo handshake.
7. DI49–DI56 se leen inactivas sin nada conectado (FW-07): los últimos 8 caracteres de `DI:` deben ser `0`.
8. Lectura de vuelta de salidas con la carga real (cierra D-05): con cada salida en ON y en OFF, anotar si `disc_do` (8 dígitos hex de la `ST`) marca falsos positivos.
9. Reiniciar la ESP32 en marcha con el botón EN: el PC recibe `BOOT`, muestra `TARJETA_REINICIO` y repite el handshake solo (en ciclo: FALLO).

Comprobaciones adicionales que conviene agregar:

10. Tarjeta con V2 conectada al PC nuevo: debe aparecer `TARJETA_VERSION_INCOMPATIBLE` con el mensaje "tramas sin CRC".
11. Congelar el lazo de control (p. ej. con un punto de interrupción en `ControlLoop._tick`): el HB se detiene a los 1,5 s y la tarjeta apaga todo a los 5 s.
12. Verificar si abrir el puerto reinicia la ESP32 (DTR/RTS del CP210x). Si la reinicia, cada conexión empieza con `BOOT`. Es compatible, pero conviene saberlo.
13. `python tools/emparejar_tarjeta.py --id <ID>` con el ID del `BOOT`. Después Información del sistema debe mostrar "Emparejada", y con otra tarjeta, "No emparejada (aviso)".

## 5. Revisión manual del firmware

- **Tipos y buffers:**
  - Recepción en `char[64]`: como máximo 63 caracteres más `\0`. Al desbordar, la línea se descarta entera hasta el `\n`.
  - `cmd[64]` nunca supera el payload (≤ 58).
  - Transmisión en `char[160]`. Las tramas más largas, `AI:` (≤ 82) y `ST:` (≤ 72), caben con `*HHHH\n`.
  - `uptime_s` se convierte de uint64 a texto a mano, sin depender de `%llu`.
  - En el ESP32, `unsigned long` es de 32 bits, lo que es correcto para `%08lX`/`%lu`.
- **`lastError()` en la librería 0.2.5:** leída en `Documents/Arduino/libraries/PCF8575/PCF8575.cpp`.
  - `read16()` con falla fija `_error = PCF8575_I2C_ERROR` y devuelve el último valor.
  - `write16()` hace `_error = endTransmission()`.
  - `lastError()` devuelve y limpia.
  - Un `read16()` exitoso **no** limpia `_error`.
  - Por eso se llama a `lastError()` justo después de cada `read16`/`write16`, sobre el mismo objeto (`verificarI2C`), y una vez al arrancar sobre las salidas.
- **Ninguna ruta enciende una salida antes del primer `ALL_OFF` válido:**
  - El único código que pone un bit en ON es `procesarSet()`, y su primera línea rechaza la orden si no está `sincronizado`.
  - `sincronizado = true` solo se asigna en la rama `ALL_OFF`, y solo con CRC válido y las dos escrituras verificadas.
  - `refrescarSalidas()` reescribe la sombra, que vale 0xFFFF hasta que llega un `SET` aceptado.
  - No se usa `begin()` de la librería.
- `getEfuseMac()`, `esp_timer_get_time()` y `ADC_11db` existen en el core esp32 3.3.7 instalado.

## 6. Lo no verificado

- Compilación del `.ino`: no hay compilador y la instrucción lo prohíbe. Pueden aparecer advertencias o errores triviales al compilar.
- Comportamiento real de la tarjeta, de los tiempos y de `disc_do` con la carga (D-05).
- Si abrir el puerto reinicia la ESP32 (§4, punto 12).
- Vista QML del panel: no se ejecutó la interfaz. Solo hay pruebas del bridge.
- Integración extremo a extremo con el backend real y la tarjeta: solo hay pruebas con el doble serial.
- No se ejecutaron los agentes de revisión del proyecto (`safety-reviewer`, `timing-auditor`). Se recomienda pasarlos antes del commit, porque el cambio toca actuadores, ControlLoop y el enlace serial.

## 7. Decisiones tomadas sin preguntar

PC:

1. **Dónde corre el handshake.** No corre dentro de `_connect()`: corre en el hilo de supervisión, en el tick siguiente a `_connect()` (≤ 0,1 s), y tras cada reconexión, WD o `BOOT`.
   - Motivo: `_connect()` debe volver de inmediato, y así lo usan las pruebas y el reintento PnP.
   - El handshake bloquea ese hilo como máximo `handshake_presupuesto_s`.
2. **Intentos de `VER` y `HB`.** Usan los mismos intentos y tiempo por intento que `ALL_OFF` (3 × 1 s). La spec solo los fija para `ALL_OFF`.
3. **Firmware V2.** Nunca envía una trama válida.
   - Si durante la espera llegan líneas `AI:`/`DI:`/`DO:` sin `*`, se informa `TARJETA_VERSION_INCOMPATIBLE` con el mensaje "tramas sin CRC: firmware anterior a 1.0.0". Así se cumple el "rechazo explícito" de HAZ-FC-11.
   - Si no llega nada, se informa `TARJETA_SIN_TRAMA_VALIDA`.
   - `VER` sin respuesta también se informa como `TARJETA_VERSION_INCOMPATIBLE`.
   - Además, las 10 líneas inválidas consecutivas cierran el puerto, y el handshake lo detecta y termina sin agotar los 15 s.
4. **Paso 6 del handshake:**
   - Solo cuentan el `DO:` y las `ST:` posteriores al `OK ALL_OFF`; una `ST` sin `DO` previo se ignora.
   - Dos `ST` sanas seguidas = conexión válida.
   - Dos `ST` seguidas con la misma falla terminan el handshake de inmediato, cada una con su alarma:
     - `pcf_ok` distinto de `3F` → `EXPANSOR_FUERA_DE_LINEA`
     - alguna salida en 1 → `SALIDAS_NO_APAGADAS`
     - `sync=0` → `ALL_OFF_SIN_CONFIRMAR`
   - Sin ninguna `ST` en el presupuesto → `SIN_TRAMA_VALIDA`.
5. **Watchdog detectado por la `ST`.** Con el handshake hecho, una `ST` con `wd=1` o `sync=0` también se toma como `TARJETA_WATCHDOG`, por si la línea `WD:` se perdió por ruido.
6. **Handshake fallido.** El puerto no se cierra; se reintenta cada `reintento_handshake_s` (3 s). Así no se reinicia la ESP32 por DTR en cada intento.
7. **Comparación de salidas:**
   - La exclusión de 1 s cuenta desde el último **cambio** de estado comandado, no desde cada reenvío. Las puertas reafirman su salida en cada tick, y con la otra lectura nunca se compararían.
   - `all_off()` del lazo cuenta como orden OFF para los 32 canales.
   - Si la discrepancia se corrige sola, se rearma el reenvío único.
   - El evento `DISCREPANCIA_SALIDAS` se emite una vez por episodio.
8. **`pcf_ok` en operación** (2 `ST` seguidas):
   - Se emite un evento por episodio.
   - En ciclo → FALLO vía `abortar_por_falla_io`.
   - Fuera de ciclo → alarma y nuevo handshake.
   - En ciclo **no** se repite el handshake, porque el protocolo de fallo necesita las salidas.
9. **Severidad de las alarmas de la tarjeta:**
   - Fuera de ciclo: `FALLA`, bloqueante y recuperable. Se despejan solas al completarse el siguiente handshake.
   - En ciclo: `EMERGENCIA` desde `abortar_por_falla_io`. Esas **no** se despejan solas; se liberan con el reconocimiento, como `FALLO_CONEXION`.
10. **`fase_ciclo`.** `abortar_por_falla_io` deja `fase_ciclo = "FALLO_IO"`, que queda como `resultado` del ciclo; el `alarm_id` lleva la causa.
11. **Emparejamiento.**
    - `emparejada` vale `False` tanto si el ID es distinto como si el perfil no tiene `board_id`, y `None` si no hay tarjeta.
    - En `audit_log` queda `evento="tarjeta_conectada"`, `usuario="sistema"`, `entidad="tarjeta_es"`, `valor_nuevo={version, protocolo, id}` y `detalle={emparejada, board_id}`.
12. **`board_id` en el perfil.**
    - La herramienta acepta el ID en minúscula y lo guarda en mayúscula.
    - `storage.save()` solo escribe el campo si existe.

Firmware:

13. **Watchdog.** Solo está armado en SINCRONIZADO. En NO_SINCRONIZADO las salidas ya están en 0xFFFF y los `SET` se rechazan. Sin esto, la tarjeta emitiría `WD: ALL_OFF` cada 5 s mientras el PC no está conectado.
14. **ACK.** Toda línea válida recibe `ACK` primero, como en V2; también `VER` y un `SET` rechazado.
15. **`ALL_OFF`.** `OK ALL_OFF` y la salida de NO_SINCRONIZADO solo ocurren si las dos escrituras se verificaron con `lastError()`. Un `OK` falso dejaría al PC creyendo que todo está apagado.
16. **`SET`.**
    - Si la escritura falla, no hay `OK`.
    - Un estado distinto de `ON`/`OFF` se ignora. V2 lo tomaba como OFF.
17. **Línea larga.** Cuenta en `rx_largas` y también en `crc_rx_err` (es una línea inválida, §4.4). `rx_largas` y `rechazados` existen, pero no se publican porque la `ST` tiene formato fijo (pregunta P2).
18. **Autoprueba CRC.** Si falla al arrancar, la tarjeta se queda con las salidas apagadas y sin `BOOT`.
19. **Formato del ID.** Es la MAC en su orden habitual: el byte bajo de `getEfuseMac()` va primero.
20. **DI al arrancar.** Las DI arrancan en 0xFFFF (inactivas) hasta la primera lectura (≤ 50 ms, antes de la primera publicación). V2 arrancaba en 0 y habría publicado todo activo. Con el paro cableado NC, inactivo = paro, que es el lado seguro.
21. **`disc_do`.** Si la lectura de vuelta de un expansor falla, ese expansor no aporta bits; la falla se ve en `pcf_ok`.
22. **Retención de `pcf_ok`.** Un error se publica en la `ST` de la ventana de 500 ms en que ocurrió.
23. **`DO:`.** Sigue publicando la sombra, como V2 (§4.2 del plan de protocolo). La diferencia con el pin real está en `disc_do`.

## 8. Preguntas abiertas

- **P1. Textos de alarmas en `es.json`.**
  - La instrucción pide agregar los nueve ids "con el formato existente", pero `es.json` no tiene alarmas. `inventario_cadenas_i18n.md` lo confirma: "No existe catálogo de alarmas, ni en `es.json` ni en ningún otro lugar", y la rama `alarmas-parte-a` tampoco las agrega.
  - Me detuve en este punto. Hoy el texto en español viaja en `Alarm.description` y lo muestra la UI.
  - ¿Qué formato quieres? Por ejemplo, un bloque `alarmas` con `{ID: {titulo, accion}}`.
- **P2. `rechazados` (FW-D4) y `rx_largas` (§4.3).** La spec dice que el firmware los cuenta, pero el orden de la `ST` es fijo y no los incluye. ¿Se agregan al final de la `ST` (lo que cambia el formato aprobado y el parser del PC) o se quedan internos?
- **P3. Tarjeta no emparejada.** ¿Basta con log, `audit_log` y Información del sistema, o quieres un id de aviso propio (no bloqueante)? No está entre los nueve aprobados.
- **P4. Re-handshake en ciclo tras WD/`BOOT`.**
  - El ciclo se aborta en el mismo tick y el protocolo de fallo empieza, pero sus órdenes de salida se descartan hasta que el handshake se completa (unos 1–2 s).
  - En ese intervalo la tarjeta está en 0xFFFF, que es el estado seguro, y el protocolo sigue reafirmando sus salidas en cada tick.
  - ¿Es aceptable o el PES (E3) debe contemplarlo?
- **P5. Fase "FALLO_IO".** ¿Te sirve como resultado del ciclo en el ticket y el historial, o prefieres otro nombre, p. ej. el `alarm_id`?
