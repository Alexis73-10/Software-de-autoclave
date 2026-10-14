# Planeación: firmware 1.0.0 de la tarjeta ESP32 y su contraparte en el PC

Estado: v2 (2026-10-12), aprobado por Cristian (§9). Sin código. Nota: el nombre del archivo conserva "1_5" por historial; la versión de firmware aprobada es 1.0.0.
Marco: IEC 62304 Clase C. Equipo: piso de laboratorio, instalación objetivo 19-oct-2026.
Documento normativo del protocolo: `planeacion_protocolo_serial_esp32.md` (v2, aprobado 2026-10-02). **Este documento no lo reemplaza**: lo hace ejecutable para el 19-oct y agrega lo decidido después (versión, ID de tarjeta, arranque seguro, latido atado al lazo de control).
Relación con `planeacion_fin_de_ciclo_y_puertas.md`: etapa E6 (§9 de ese documento, ruta crítica).

---

## 1. Punto de partida verificado

| Hecho | Evidencia |
|---|---|
| La tarjeta lleva el `.ino` V2 del repositorio: sin CRC, sin banner, sin versión | `Comunicacion_esclava_ESP32_V2.ino` (229 líneas) |
| El PC ya habla protocolo v2: valida CRC al recibir y firma `payload*HHHH` al enviar | `serial_link.py:321, 436-438`, `crc16.py` |
| Consecuencia hoy: toda línea del firmware V2 se descarta por "CRC ausente" y todo comando del PC llega al firmware con `*HHHH` pegado, de modo que `SET DOn ON*HHHH` se interpreta como OFF | `.ino:139` (`estado == "ON"`) |
| Del plan de protocolo solo se implementó la Fase A (lector con CRC, latido monotónico, contadores). **No existen** en el PC: parseo de `ST:`/`WD:`/`BOOT`/`VER`, handshake, `ALL_OFF` al conectar, comparación comandado vs `DO:` | búsqueda en `src/`: sin coincidencias |
| El `.ino` no existe en versión V3: nunca se escribió | `Hardware/` solo contiene V2 |

Conclusión: con este PC y el firmware actual **el equipo no funciona**. El firmware nuevo y la Fase B del PC son requisito de instalación, no mejora.

## 2. Decisiones heredadas (no se reabren)

CRC en ambas direcciones en modo estricto; trama `ST:`; comprobación de errores I2C; lectura de vuelta de salidas; tolerancia de 2 tramas (1 s); fallos de PCF y discrepancia de salida bloqueantes en arranque y FALLO en ciclo; `disc_do` solo diagnóstico hasta validarlo en hardware real (D-05); salidas activas en bajo, estado seguro 0xFFFF; `WD_TIMEOUT_MS = 5000`; mapa de pines y direcciones I2C del `.ino` actual (confirmado por Cristian, 2026-10-12); librería PCF8575 de Rob Tillaart 0.2.5; ADC1 a 12 bits, 11 dB, promedio de 64 muestras sin cambios.

## 3. Decisiones nuevas para esta versión (aprobadas 2026-10-12: FW-D1 a FW-D6 explícitas; FW-D7 y FW-D2 según el borrador)

| ID | Propuesta |
|---|---|
| FW-D1 | **Versión** `1.0.0`, protocolo `2` (aprobado). Reemplaza el `3.0.0` del plan de protocolo; no hay control de versiones previo. Carpeta nueva `Hardware/Comunicacion_esclava_ESP32_V3/`; V2 se conserva como retorno. |
| FW-D2 | **ID único**: MAC de fábrica del chip (`ESP.getEfuseMac()`), 12 dígitos hex mayúscula. Va en `BOOT` y `VER`: `BOOT 1.0.0 2 <ID12>`. Se muestra en "Información del sistema" y se registra en `audit_log` en cada conexión. |
| FW-D3 | **Arranque seguro**: antes de `Wire.begin()` no se toca ninguna salida; primera acción útil = `write16(0xFFFF)` a ambos expansores de salida, verificada con `lastError()`; solo después se emite `BOOT`. El estado inicial del firmware es **NO_SINCRONIZADO**. |
| FW-D4 | **NO_SINCRONIZADO** (tras `BOOT` y tras disparo del watchdog): el firmware acepta `HB`, `VER`, `ALL_OFF`, `RESET_MINMAX`; **rechaza `SET DOn`** (sin `OK`, cuenta en `rechazados`) hasta recibir un `ALL_OFF` válido. Evita que un comando rezagado del PC encienda una salida tras un reinicio o un disparo del watchdog. |
| FW-D5 | **Watchdog**: se reinicia solo con líneas de CRC válido (cualquier comando válido). Al disparar: salidas a 0xFFFF, `WD: ALL_OFF`, `wd=1`, estado NO_SINCRONIZADO. |
| FW-D6 | **Latido atado al lazo de control (D-21)**: el PC envía `HB` solo mientras `ControlLoop` haya completado un tick en los últimos 1,5 s. Si el lazo se congela, el latido se detiene y el watchdog de 5 s del firmware apaga todo. Los `SET`/`ALL_OFF` solo los emite el lazo, así que no mantienen vivo el watchdog por otra vía. |
| FW-D7 | **Emparejamiento tarjeta–equipo (versión 1.0)**: el ingeniero registra el ID en el perfil (`board_id`, herramienta análoga a `declarar_entradas_suministro.py`). ID distinto o sin registrar = **advertencia no bloqueante** + `audit_log` + visible en Información del sistema. El bloqueo y la autenticación del reemplazo quedan para una versión posterior. |

## 4. Firmware 1.0.0: requisitos (sobre `planeacion_protocolo_serial_esp32.md` §5)

1. Todo lo de §5 del plan de protocolo (puntos 1–11), con `BOOT`/`VER` según FW-D1/D2.
2. Arranque, no sincronización y watchdog según FW-D3 a FW-D5.
3. Recepción: buffer `char[64]`; línea que desborda se descarta entera hasta el siguiente `\n`; cuenta en `rx_largas`. Se elimina `\r`; CRC sobre el texto recibido; solo después, `trim` y mayúsculas.
4. Todas las líneas de salida firmadas; vector de prueba `123456789 → 0x29B1`.
5. `ST:` según §4.5 del plan de protocolo. Se **agrega un campo al final**: `<sync>` (1 = sincronizado, 0 = NO_SINCRONIZADO). El PC lo exige en 1 después del handshake. Orden final: `ST:<ver>,<pcf_ok>,<disc_do>,<ai_inv>,<crc_rx_err>,<i2c_err>,<wd>,<uptime_s>,<sync>`.
6. `uptime_s` con `esp_timer_get_time()` (64 bits).
7. Sin lógica de seguridad nueva en el firmware aparte de la anterior: la decisión de fallo es del PC.
8. Cada `write16`/`read16` seguido de `lastError()` sobre el mismo objeto antes de cualquier otra operación sobre él.

Fuera de alcance del firmware 1.0.0: autenticación de tarjeta, cifrado, lectura de sensores nuevos, soporte M31-U (la ESP32 es temporal).

## 5. PC: cambios mínimos para el 19-oct (Fase B del plan de protocolo, recortada)

1. **Handshake** (§4.6 del plan de protocolo) en `_connect()` y tras cada reconexión: primera trama válida → `VER` (protocolo 2; si no, `TARJETA_VERSION_INCOMPATIBLE`) → `HB`/`ACK` → `ALL_OFF`/`OK ALL_OFF` (3 intentos de 1 s) → dos `ST:` con `pcf_ok=3F`, `sync=1`, y `DO:` todo en 0. Mientras no se complete, `is_connected()` es False y no se aceptan órdenes de salida.
2. Parseo de `BOOT`, `VER`, `ST:`, `WD:`; `BOOT` inesperado, `WD:` o `uptime_s` que retrocede en ciclo → FALLO vía `abortar_por_falla_io()` (método nuevo, plan de protocolo §11.5) + PES (§15 de fin de ciclo).
3. Comparación comandado vs `DO:` reportado (plan de protocolo §6.5): discrepancia sostenida 2 tramas → un reenvío; si persiste, FALLO en ciclo / alarma bloqueante fuera de ciclo. `disc_do` solo diagnóstico.
4. `pcf_ok ≠ 3F` sostenido 2 tramas: bloqueante en arranque, FALLO en ciclo.
5. Latido atado al tick del lazo (FW-D6): `SerialLink.marcar_tick_control()` llamado por `ControlLoop` en cada tick; `_watchdog_tick` envía `HB` solo si el último tick es reciente.
6. `ALL_OFF` en cada conexión (usa los parámetros `all_off_*` hoy sin uso). Es el punto de apoyo de E4 (arranque seguro tras corte o reinicio).
7. Versión e ID: guardar en `data`, exponer en `/status` (`tarjeta: {version, id, emparejada}`), `audit_log` en cada conexión, y comparar con `board_id` del perfil (FW-D7).
8. Alarmas del plan de protocolo §11.6 (nueve ids); textos en `es.json`. Los ids nuevos pasan por el catálogo de alarmas; **no esperan a la Parte A** completa (solo estos ids).
9. Herramienta `tools/emparejar_tarjeta.py` (`--mostrar`, `--id <ID12>`), mismo patrón que `declarar_entradas_suministro.py`: perfil `locked`, respaldo, validación.

Fuera de alcance de esta etapa: invalidación por entrada digital (fase C de sensores), bilingüe de las alarmas nuevas.

## 6. Pruebas

Firmware (banco, sin autoclave, salidas sin carga):
1. Vector CRC en C++ y en Python.
2. Arranque: salidas en 0 desde el encendido hasta `BOOT`; osciloscopio o multímetro en una salida durante reinicios repetidos (10 ciclos de energía).
3. Línea sin CRC, con CRC malo, larga sin `\n`, con `\r`: descartada, contador sube, watchdog no se reinicia.
4. `SET DO` antes de `ALL_OFF` tras `BOOT`: rechazado. Después: acepta.
5. 5 s sin comandos válidos: `WD: ALL_OFF`, salidas apagadas, `SET` rechazado hasta nuevo `ALL_OFF`.
6. Desconectar un PCF con el equipo en reposo: `pcf_ok` y `i2c_err` reflejan; reconectar y comprobar recuperación.
7. DI49–DI56 leen inactivas sin nada conectado (FW-07).
8. Lectura de vuelta de salidas con carga real conectada (cierra D-05): registrar si `disc_do` da falsos positivos.
9. Reinicio de la ESP32 en marcha (botón EN): el PC detecta `BOOT` y repite el handshake.

PC (con serial doble, sin hardware): handshake completo y cada fallo con su alarma; `HB` se detiene si el lazo no hace tick; discrepancia de salida; `WD:`/`BOOT` en ciclo y fuera de ciclo; `board_id` ausente / distinto / igual; ruido en la línea sin matar el hilo lector. Cada prueba se ve fallar antes del cambio.

## 7. Riesgos (alimentan HAZ-FC)

| ID | Riesgo | Mitigación |
|---|---|---|
| HAZ-FC-09 | Salida activa por comando rezagado tras reinicio o disparo del watchdog | FW-D3/D4 |
| HAZ-FC-10 | Lazo de control congelado con el enlace serial vivo | FW-D6 |
| HAZ-FC-11 | Firmware cargado equivocado (V2) en la tarjeta | `VER` + protocolo 2; rechazo explícito |
| HAZ-FC-12 | Salida mantenida por falla de la etapa de potencia aunque el bit esté en OFF | Fuera del alcance del software: protección de hardware (paro físico corta DO) |

## 8. Procedimiento de carga (lo hace Cristian)

1. Respaldo del firmware actual: el `.ino` V2 ya está en el repositorio (retorno).
2. Compilar en Arduino IDE; librería PCF8575 Rob Tillaart 0.2.5 y el mismo paquete de placas ESP32 que compiló V2 (anotar la versión del paquete en el informe).
3. Cargar por USB con el equipo **sin carga eléctrica en las salidas** y el paro presionado.
4. Leer `BOOT` en el monitor serie a 115200: versión `1.0.0`, protocolo `2`, ID. Registrar el ID con `tools/emparejar_tarjeta.py`.
5. Pruebas 2–9 de §6 antes de conectar al autoclave.

## 9. Respuestas de Cristian (2026-10-12)

1. Versión `1.0.0`.
2. FW-D4 aprobado (rechazar `SET` hasta `ALL_OFF` tras reinicio o watchdog).
3. FW-D6 aprobado (`HB` atado al tick del lazo, margen 1,5 s).
4. Arduino IDE con librerías y paquete de placas disponible en `programacion`: Code escribe el `.ino` y Cristian compila y carga.
5. Hay osciloscopio o multímetro para la prueba de arranque (§6.2).
6. Dónde mostrar versión e ID: criterio de Claude = solo "Información del sistema" (el splash queda fuera de alcance por tiempo).
