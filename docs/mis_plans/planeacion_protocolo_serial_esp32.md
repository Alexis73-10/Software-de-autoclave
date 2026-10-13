# Planeación: protocolo serial PC↔ESP32 (v2) y endurecimiento del firmware

Estado: especificación para aprobación final antes de instruir a Code. No contiene código.
Fecha: 2026-10-02. Marco: IEC 62304 Clase C, ISO 14971.
Ubicación sugerida: `docs\mis_plans\planeacion_protocolo_serial_esp32.md`
Documento hermano: `planeacion_arranque_y_modo_sin_bd.md` (etapas de arranque, sensores, modo sin base de datos).

---

## 1. Alcance

- Firmware de la tarjeta de E/S: `Comunicacion_esclava_ESP32_V2.ino`. Se crea una versión V3 y se conserva V2 en el repositorio como retorno.
- Capa serial del PC: `protocols/serial_link.py`, `set_io.py` y lo relativo a comunicación en `control_loop.py`.
- Por ahora el cambio se corre solo en el PC de desarrollo, no en equipos de campo.
- Fuera de alcance: verificación de sensores y etapas de arranque (documento hermano).

## 2. Decisiones aprobadas por Cristian

1. Protocolo v2 con CRC en ambas direcciones, en modo estricto: PC y firmware se actualizan juntos; el firmware viejo se rechaza mediante `VER`. No hay compatibilidad hacia atrás.
2. Diagnóstico I2C en el firmware, trama `ST:` y lectura de vuelta de las salidas.
3. Tolerancia de 1 s (dos tramas) antes de declarar discrepancia entre salida comandada y salida reportada.
4. Backend como subproceso independiente del lanzador (relevante para la reconexión: ver sección 6).
5. Los fallos de E/S críticos son bloqueantes en el arranque y, durante un ciclo, disparan el protocolo de fallo (salidas a estado seguro).
6. Prueba de banco de sensores diferida; no bloquea esta especificación.

## 3. Hallazgos

Severidad: Crítico (puede dejar al equipo operando con información falsa de seguridad), Alto, Medio.

Firmware:

- FW-01 [Crítico] Fallos I2C silenciosos. Verificado en `PCF8575.cpp` v0.2.5: `read16()` ante fallo de bus fija `_error` y devuelve el último valor leído (`_dataIn`); `write16()` es `void` y guarda `_error = endTransmission()`, de modo que una escritura posterior sobre el mismo objeto borra un error de lectura previo. `pcf_mux` se lee y se escribe, así que su error de lectura se enmascara. El sketch nunca consulta `lastError()`. Consecuencia: entradas digitales congeladas (`paro_emergencia`, puertas, presostatos) sin aviso, y selección de canal analógico no verificada.
- FW-02 [Alto] `DO:` publica `estadoOut1/2` (variable sombra), no el estado real de los pines. Un `write16()` fallido pasa inadvertido.
- FW-03 [Alto] Sin CRC. El firmware responde `ACK` a cualquier línea terminada en `\n` y la cuenta como comando válido para reiniciar el watchdog.
- FW-04 [Medio] `serialBuffer` es un `String` sin límite: sin `\n` crece indefinidamente y fragmenta el heap.
- FW-05 [Medio] Sin banner de reinicio ni comando de versión: el PC no distingue un reinicio del ESP32 (salidas a OFF) de otras condiciones.
- FW-06 [Medio] Los expansores de salida (0x24, 0x25) no tienen tráfico periódico: su falla solo se detectaría en la siguiente escritura de un comando.
- FW-07 [Medio] `leerAnalogico()` escribe `pcf_mux.write16(canal << 8)`, que deja el byte bajo en 0 y fuerza a nivel bajo los pines P0-P7 del 0x26; `read16()` lee las entradas DI49-DI56 siempre en 0 y se publican como activas (`!bitRead`). Sin efecto hoy porque `map_di` solo usa los índices 0-13. Corrección en V3: `(canal << 8) | 0x00FF`.

PC (a partir de los reportes de Code):

- PC-01 [Crítico] No se parsea `WD: ALL_OFF` ni se compara el `DO:` reportado contra lo comandado. Tras un disparo del watchdog del ESP32 el software sigue creyendo que las salidas están activas.
- PC-02 [Alto] El latido (`HEARTBEAT_INTERVAL = 2.0 s`) usa `time.time()` y `_check_timeout` usa `datetime.now()`. Un cambio de hora del sistema (la app tiene permitido cambiarla) puede detener el latido y disparar el watchdog del ESP32 con ciclo en curso.
- PC-03 [Alto] `ACK` y `OK DOn ESTADO` se ignoran; `set_output()` devuelve `True` sin confirmar nada.
- PC-04 [Alto] Cualquier línea recibida (incluso `WD:`, `ACK` o basura) marca `data_alive`; `_check_timeout()` solo corre cuando `readline()` vuelve vacío; una línea `AI:` no numérica mata el hilo lector (`ValueError` no capturado) y el control sigue con valores congelados.
- PC-05 [Alto] No se envía `ALL_OFF` ni se resincroniza el estado al conectar o reconectar.
- PC-06 [Medio] Los mínimos y máximos analógicos del firmware nunca se publican ni se usan (sin acción; solo registro).

## 4. Especificación del protocolo v2

### 4.1 Formato de línea

`<payload>*HHHH\n`

- CRC-16/CCITT-FALSE: polinomio 0x1021, valor inicial 0xFFFF, sin reflexión de entrada ni de salida, sin XOR final.
- Se calcula sobre los bytes del payload (sin el `*`, sin el CRC y sin `\r\n`).
- `HHHH`: cuatro dígitos hexadecimales en mayúscula.
- Vector de prueba obligatorio para ambas implementaciones: el payload `123456789` produce `0x29B1`.

### 4.2 ESP32 → PC

Todas las líneas llevan CRC: `AI:`, `DI:`, `DO:`, `ST:`, `ACK`, `OK ...`, `WD:`, `BOOT`, `VER`.

- `BOOT <version_fw> <protocolo>` una vez al iniciar el firmware.
- `VER <version_fw> <protocolo>` en respuesta al comando `VER`.
- `WD: ALL_OFF` cuando el watchdog dispara.
- Las tramas `AI:`, `DI:`, `DO:` mantienen su contenido actual y su periodo de 500 ms; se agrega `ST:` con el mismo periodo.

### 4.3 PC → ESP32

Comandos: `HB`, `ALL_OFF`, `RESET_MINMAX`, `SET DOn ON|OFF` (sin espacio entre `DO` y el número, como lo parsea el firmware; ejemplo `SET DO4 ON`), `VER`.

- El PC los envía en mayúscula y sin espacios sobrantes, con sufijo `*HHHH`.
- El firmware elimina `\r`, valida el CRC sobre el texto recibido tal cual y solo después normaliza (trim y mayúsculas).

### 4.4 Línea inválida

- Firmware: se descarta, se incrementa `crc_rx_err`, no responde `ACK` y no reinicia el watchdog.
- PC: se descarta y se cuenta. El tiempo de vida de la comunicación se mide solo con líneas de CRC válido. Valor por defecto: 10 líneas inválidas consecutivas se declaran pérdida de comunicación; además rige el timeout de datos existente (3.0 s) medido con `time.monotonic()`.

### 4.5 Trama ST

`ST:<ver>,<pcf_ok>,<disc_do>,<ai_inv>,<crc_rx_err>,<i2c_err>,<wd>,<uptime_s>*HHHH`

- `ver`: versión de protocolo (2).
- `pcf_ok`: máscara de 6 bits en hexadecimal (2 dígitos); 1 significa sin error en los últimos 500 ms. Bit 0: 0x24 (salidas 1-16); bit 1: 0x25 (salidas 17-32); bit 2: 0x21 (entradas 1-16); bit 3: 0x22 (entradas 17-32); bit 4: 0x23 (entradas 33-48); bit 5: 0x26 (entradas 49-56 y MUX). Estado sano: `3F`.
- `disc_do`: máscara de 32 bits en hexadecimal (8 dígitos); el bit n-1 vale 1 si el pin real de la salida n difiere de la variable sombra.
- `ai_inv`: máscara de 16 bits en hexadecimal (4 dígitos): canales analógicos cuya última muestra se descartó por error del MUX. Campo agregado a la lista aprobada; permite que el PC no tome como válido un valor de otro canal.
- `crc_rx_err`: contador acumulado de líneas rechazadas por CRC.
- `i2c_err`: contador acumulado de errores I2C.
- `wd`: 1 si el watchdog disparó y no se ha recibido aún un comando válido posterior; 0 en otro caso.
- `uptime_s`: segundos desde el arranque del ESP32, calculados con un contador de 64 bits (`esp_timer_get_time()`), NO con `millis()/1000`: `millis()` es de 32 bits y se desborda a los 49,7 días, lo que el PC interpretaría como un reinicio falso. Si retrocede, el PC lo interpreta como reinicio.
- Codificación: `ver`, `crc_rx_err`, `i2c_err` y `uptime_s` en decimal sin ceros a la izquierda; `wd` como 0 o 1; las máscaras en hexadecimal de ancho fijo y mayúscula (`pcf_ok` 2 dígitos, `ai_inv` 4, `disc_do` 8). Los contadores son de 32 bits y pueden dar la vuelta: el PC calcula diferencias módulo 2^32.

### 4.6 Handshake de conexión (PC)

Presupuesto total por defecto: 15 s (etapa "Conectando con la tarjeta" del splash).

1. Abrir el puerto y vaciar buffers.
2. Esperar la primera trama con CRC válido.
3. Enviar `VER` y verificar protocolo 2.
4. Enviar `HB` y esperar `ACK`.
5. Enviar `ALL_OFF` y esperar `OK ALL_OFF` (1 s por intento, 3 intentos).
6. Verificar en dos tramas `ST:` consecutivas que `pcf_ok = 3F` y en `DO:` que todas las salidas están en 0.
7. Conexión declarada válida.

Nota: si el backend se reinicia con un ciclo en curso, el `ALL_OFF` del paso 5 deja el equipo en estado seguro; el ciclo no se reanuda porque la máquina de estados vive en memoria.

## 5. Firmware V3: cambios requeridos

1. CRC en todas las líneas de salida y validación en las de entrada (sección 4).
2. Armar cada trama en un buffer `char` y enviarla de una vez; reemplazar `String` por buffer de 64 bytes con descarte de la línea si desborda.
3. Tras cada `read16()` y `write16()`, llamar a `lastError()` de inmediato sobre el mismo objeto, antes de cualquier otra operación sobre él. Acumular en `i2c_err` y marcar el bit del dispositivo en `pcf_ok`, con retención de al menos un periodo de publicación.
4. MUX: si `write16()` del selector falla, no muestrear ese canal, conservar el valor previo y marcar `ai_inv`.
5. Entradas: si `read16()` falla, el bit correspondiente de `pcf_ok` pasa a 0. El PC invalida la entrada digital en ese caso.
6. Salidas: cada 500 ms, reescribir la variable sombra (`write16`), verificar con `lastError()`, leer el puerto de vuelta (`read16`) y construir `disc_do`. La reescritura periódica también corrige un reinicio espontáneo del expansor.
7. Watchdog: reiniciarlo solo con comandos válidos (CRC correcto). Al disparar, emitir `WD: ALL_OFF` y fijar `wd = 1`.
8. Emitir `BOOT` al iniciar y responder `VER`.
9. Conservar sin cambios: estado seguro al arrancar (0xFFFF), `WD_TIMEOUT_MS = 5000`, lectura por ADC1, resolución y atenuación fijadas, promedio de 64 muestras.
10. Selector del MUX con `(canal << 8) | 0x00FF` (FW-07). Verificar en hardware que DI49-DI56 leen inactivas con nada conectado.
11. `uptime_s` con contador de 64 bits (sección 4.5).

## 6. PC: cambios requeridos

1. Parser con CRC. El hilo lector captura excepciones por línea y no muere (PC-04, FW-03).
2. Vida de la comunicación solo con líneas válidas, en un temporizador propio con `time.monotonic()` (PC-02, PC-04).
3. Latido con `time.monotonic()` (PC-02).
4. Parseo de `ST:`, `WD:`, `BOOT` y `VER`; las condiciones se clasifican en la sección 7 (PC-01).
5. Comparación entre lo comandado y el `DO:` reportado: discrepancia sostenida por 2 tramas (1 s) genera un reenvío único del comando y, si persiste, FALLO (EMERGENCIA) en ciclo, o alarma bloqueante `DISCREPANCIA_SALIDAS` con nuevo handshake fuera de ciclo. Se comparan solo los canales comandados desde el último handshake y se excluyen los comandados hace menos de 1 s. Esta comparación (comandado contra `DO:` reportado) es independiente de `disc_do` y no está sujeta a D-05 (PC-01, PC-03).
6. Handshake de conexión en `_connect()` y tras cada reconexión (PC-05).
7. Tras `WD:` o `BOOT` inesperado, volver a ejecutar el handshake antes de aceptar nuevos comandos de salida.
8. Contadores `crc_rx_err` y líneas inválidas expuestos en `/status` (diagnóstico).

## 7. Clasificación de fallos de E/S y comunicación

- Arranque (cualquier falla del handshake: puerto, CRC, `VER`, `HB`, `ALL_OFF`, estado de `DO:`): el equipo queda en pantalla de espera con alarma específica, botón INICIAR deshabilitado y reintento automático cada 3 s (supuesto D-02, ver sección 10).
- Arranque, `pcf_ok` distinto de `3F`: bloqueante. Mismo tratamiento anterior.
- Expansor de entradas, de salidas o MUX fuera de línea (`pcf_ok` distinto de `3F` sostenido en 2 tramas ST consecutivas, para filtrar un NACK aislado; `i2c_err` sigue contando cada error): en ciclo, FALLO (EMERGENCIA) y protocolo de fallo; fuera de ciclo, alarma bloqueante y repetir el handshake.
- Ciclo en curso, `WD:` recibido, `BOOT` inesperado o `uptime_s` que retrocede: FALLO (EMERGENCIA) y protocolo de fallo. Fuera de ciclo: alarma bloqueante hasta repetir el handshake con éxito.
- `disc_do` distinto de cero sostenido por 2 tramas: igual que expansor de salidas fuera de línea, una vez cumplida la condición D-05.
- Línea con CRC inválido aislada: registro informativo. 10 consecutivas: pérdida de comunicación (flujo existente `NO_HAY_CONEXION` / `FALLO_CONEXION`).

## 8. Pruebas de aceptación

1. Vector CRC `123456789` → `0x29B1` en C++ y en Python (prueba unitaria en ambos).
2. Inyección de ruido en el PC con el simulador: línea con CRC erróneo, línea `AI:` con valor no numérico, línea larga sin `\n`; el hilo lector sobrevive y el contador sube.
3. Sin comandos por más de 5 s: el firmware emite `WD: ALL_OFF`, el PC lo registra y reacciona según la sección 7.
4. Reinicio del ESP32: el PC detecta `BOOT` o retroceso de `uptime_s`.
5. Desconexión de un PCF en banco (con el equipo en reposo y salidas en OFF): `pcf_ok` refleja el bit y el PC aplica la sección 7.
6. Cambio de la hora del sistema hacia atrás y adelante: el latido no se interrumpe.
7. Firmware V2 conectado al PC nuevo: rechazado por `VER` con mensaje explícito.

## 9. Riesgos para ISO 14971

- R-COM-01: entrada digital congelada (paro de emergencia o puerta no leídos) por fallo I2C silencioso. Mitigación: FW-01, `pcf_ok`.
- R-COM-02: salida activa creída tras disparo del watchdog (o inversa). Mitigación: PC-01, comparación de DO, handshake con `ALL_OFF`.
- R-COM-03: control con datos congelados por muerte del hilo lector. Mitigación: PC-04.
- R-COM-04: comando corrupto interpretado como válido. Mitigación: CRC bidireccional.
- R-COM-05: salida eléctricamente distinta de la comandada (carga, corto, expansor reiniciado). Mitigación: lectura de vuelta, refresco periódico.

## 10. Pendientes y supuestos por confirmar

- D-02: sin tarjeta o con handshake fallido, el equipo continúa a pantalla de espera con alarma y sin poder iniciar ciclos (comportamiento actual con timeout y mensaje propios). CONFIRMADA el 2026-10-12: el splash se libera a la pantalla de espera a los 15 s (ver `planeacion_barra_arranque_real.md`, D-E).
- D-05: la lectura de vuelta de salidas se debe validar en el hardware real antes de usarla como disparador de fallo. Con una salida alta, el pin solo tiene pull-up débil y una etapa de potencia de baja impedancia podría leerlo como 0 sin que haya falla. Mientras no se valide, `disc_do` se registra y se muestra como diagnóstico, sin disparar protocolo de fallo.
- El tamaño de los buffers de línea y los valores por defecto (10 líneas inválidas, 15 s de handshake, 3 reintentos) son ajustables en configuración.
- Prueba de banco de sensores: diferida; los umbrales dependen de ella (documento hermano).

## 11. Decisiones de implementación (2026-10-02, respuestas a las preguntas de Code)

1. Configuración: archivo nuevo `src/autoclave/config/serial_link.json`, leído solo por `SerialLink`. Valores por defecto internos iguales a los de la especificación; si el archivo falta o es inválido, se registra una advertencia y se usan los internos; valores fuera de rango se rechazan con el mismo tratamiento. El interruptor de `disc_do` está apagado por defecto (D-05).
2. Comando de salida: `SET DOn ON|OFF` sin espacio (la sección 4.3 original estaba equivocada).
3. Versión: `BOOT 3.0.0 2` y `VER 3.0.0 2`.
4. Codificación de ST: sección 4.5.
5. Fallo durante ciclo: nuevo método `abortar_por_falla_io(alarm_id, motivo)` en `state_machine/states/ciclo.py`, análogo a `abortar_por_desconexion()`, sin tocar la lógica existente. El alcance de la fase A incluye solo ese método de `ciclo.py`.
6. Alarmas específicas aprobadas. Handshake: `TARJETA_SIN_TRAMA_VALIDA`, `TARJETA_VERSION_INCOMPATIBLE`, `TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_SALIDAS_NO_APAGADAS`, `TARJETA_EXPANSOR_FUERA_DE_LINEA`. Operación: `TARJETA_WATCHDOG`, `TARJETA_REINICIO`, `DISCREPANCIA_SALIDAS`. Los textos en español se registran en `es.json`.
7. `pcf_ok` distinto de `3F` fuera de ciclo con handshake válido: alarma bloqueante y repetir el handshake. La invalidación de cada entrada digital queda para la fase C (sensores).
8. Discrepancia entre lo comandado y el `DO:` reportado: sección 6.5.
9. `ai_inv`: solo diagnóstico en `/status` en esta fase; un error de MUX ya baja el bit correspondiente de `pcf_ok` y se cubre con el punto 7.
10. D-02 sin tocar UI ni splash: mientras el handshake no sea válido, `is_connected()` devuelve False, más la alarma específica y reintento cada 3 s.
11. FW-07 se corrige en V3.
