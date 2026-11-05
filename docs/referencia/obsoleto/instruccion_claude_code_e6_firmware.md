# Instrucción para Claude Code — E6: firmware 1.0.0 y Fase B del enlace serial

Spec (obligatoria, léela completa antes de tocar nada): `docs/mis_plans/planeacion_firmware_1_5.md` (v2) y, como normativo del protocolo, `docs/mis_plans/planeacion_protocolo_serial_esp32.md`. Contexto: `planeacion_fin_de_ciclo_y_puertas.md` §9.

## Reglas
1. Informes en español. **No hagas commit**; Cristian confirma antes. No toques los cambios ajenos del árbol (E0/E1 sin commitear).
2. Pruebas primero (se ven fallar antes del cambio). Línea base: `python -m pytest -q -p no:cacheprovider` antes y después; reporta los conteos (hoy 2440 pasan).
3. Ninguna acción sobre hardware. No hay `arduino-cli`: **no compiles ni instales nada**; Cristian compila en Arduino IDE.
4. No cambies ids de alarma existentes. Los ids nuevos (los nueve de `planeacion_protocolo_serial_esp32.md` §11.6) se agregan al catálogo y a `es.json` con el formato existente; no esperan a la Parte A.
5. Tiempos con `time.monotonic()`. No supongas: si algo de la spec es ambiguo o contradice el código, detente en ese punto y pregunta en el informe.
6. Conserva V2 intacto. El firmware nuevo va en `Hardware/Comunicacion_esclava_ESP32_V3/Comunicacion_esclava_ESP32_V3/Comunicacion_esclava_ESP32_V3.ino` (la carpeta y el `.ino` deben llamarse igual).

## Parte 1 — Firmware 1.0.0 (hazla primero)
Implementa `planeacion_firmware_1_5.md` §3 (FW-D1 a FW-D5) y §4 completos, más `planeacion_protocolo_serial_esp32.md` §4 y §5 (CRC, `ST:` con campo `sync` final, `BOOT`/`VER` con ID, buffer `char[64]`, `lastError()` tras cada I2C, lectura de vuelta de salidas, MUX `| 0x00FF`, `uptime_s` de 64 bits). Mapa de pines, direcciones I2C, ADC y temporizaciones: idénticos a V2 salvo lo indicado.
Comentarios breves en español en cada decisión de seguridad. Entrega además `Hardware/.../LEEME_carga.md` con el procedimiento de §8 y la versión de librería requerida (PCF8575 Rob Tillaart 0.2.5).
Como no se puede compilar aquí, revisa a mano: tipos, `lastError()` de la librería 0.2.5 (léela si está en el árbol o dilo en el informe), desbordes de buffer, que ninguna ruta encienda una salida antes del primer `ALL_OFF` válido.

## Parte 2 — PC (Fase B recortada, spec §5)
Puntos 1–9 de §5, con estas precisiones:
- Extiende `tests/serial_doble.py` para simular `BOOT`, `VER`, `ST:` (incluido `sync`), `WD:` y los fallos del handshake. Toda prueba nueva usa el doble.
- `marcar_tick_control()`: `ControlLoop._tick()` lo llama al inicio. **No cambies la estructura de `run()`** (ver pregunta E0-4 abierta).
- `abortar_por_falla_io(alarm_id, motivo)` en `ciclo.py`: análogo a `abortar_por_desconexion()`, sin tocar su lógica. Tras el fallo debe entrar al flujo de fallo existente.
- Mientras el handshake no esté completo, `is_connected()` = False y `set_output`/`all_off` no envían órdenes de salida (salvo `ALL_OFF` del propio handshake).
- `board_id`: campo opcional del perfil (ausente = sin emparejar → advertencia no bloqueante + `audit_log`). `tools/emparejar_tarjeta.py` copia el patrón de `tools/declarar_entradas_suministro.py`. No edites `installation_profile.json` (está `locked`).
- `/status.tarjeta = {version, id, emparejada}` y contadores existentes; Información del sistema muestra versión e ID. No toques el splash.

## Fuera de alcance
Invalidación por entrada digital, bilingüe de alarmas nuevas, `disc_do` como disparador de fallo (queda solo diagnóstico, `disc_do_dispara_fallo=false`), PES completo (E3), arranque seguro tras corte (E4; aquí solo dejas `ALL_OFF` al conectar).

## Entregable
`docs/informes/informe_e6_firmware.md`: archivos modificados; conteos de pruebas antes/después; lista de comprobaciones manuales de Cristian para el firmware (la de §6 de la spec); lo no verificado; decisiones tomadas sin preguntar; preguntas abiertas. Sin commit.
