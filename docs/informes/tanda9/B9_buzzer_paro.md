# B9 ★ — Buzzer y paro de emergencia (D9-9, H-nuevo 12)

Rama `tanda-9-b9` (desde `tanda-9`, 090a8bf). Subagente B9, noche del 23-oct-2026, sin supervisión.

## Resumen

- **Causa confirmada en el código:** con el paro activo, las **puertas avanzadas** (`AdvancedDoor.update()`, paso 3 de `ControlLoop._tick`, que también corre durante el paro) vuelven a mandar `cerrar_on()` (puerta CERRADO) y `bloquear_on()` (empaque bajo) **en cada tick**. Esas salidas estaban activas antes del paro y se encendían en el mismo tick que el buzzer, hasta el siguiente ALL_OFF del paro (espaciado 1 s). Las hipótesis 1 (firmware) y 2 (reenvío del enlace) quedan descartadas; la 3 (ALL_OFF espaciado) solo decide cuánto dura el encendido.
- **Advertencia (leer antes de cerrar H-nuevo 12):** según la hoja de banco, el equipo de pruebas tiene **puertas abatibles manuales**. Si su perfil es `door_type=simple` (`SimpleDoor`, sin salidas), esta causa **no aplica al banco**. Con puertas simples y el firmware 1.0.0 del repositorio, la simulación **no reproduce** el síntoma: ninguna salida de control se re-enciende. Si el síntoma sigue con la compilación D, la causa está fuera del PC. Según el log, sería el firmware cargado (¿distinto de 1.0.0?) o el cableado y la tarjeta. El caso de banco B-13 lo discrimina. Ver «Preguntas para Cristian».
- **Corrección (PC, independiente de la causa):**
  - `SetOutput.set_output` deja de encender cualquier salida distinta del buzzer mientras dure el paro: la orden sale como `SET DOn OFF` y se avisa una sola vez en el log.
  - `ControlLoop` manda ALL_OFF con ACK de inmediato en el flanco del paro.
  - Con esto el PC nunca ordena encender nada durante el paro: si en banco algo se enciende, queda demostrado que no viene del PC.
- **Firmware:** sin cambios, porque la causa no es el firmware (ver hipótesis 1). No se sube versión y no hay que cargar nada.

## Evidencia

### (a) Registro de órdenes con la planta simulada

Archivo: `tests/test_b9_buzzer_paro.py`. Componentes:
- `SerialLink` real, sobre el doble de puerto `tests/serial_doble.PuertoDoble`.
- Un doble del firmware V3 (`FirmwareV3`), que reproduce del `.ino`:
  - la sombra `estadoOut1/estadoOut2`;
  - `procesarSet` (un bit y `write16` del expansor);
  - `apagarTodo` (la sombra a 0xFFFF);
  - las respuestas `ACK` / `OK ...`;
  - la trama `DO:` cada 500 ms.
- `SetOutput` real, `BuzzerPlayer` real y los estados reales PREPARACION, PREPARADO y FALLA.
- Una `AdvancedDoor` real en CERRADO con empaque bajo, o ninguna puerta.
- El tick reproduce el orden de `ControlLoop._tick` (flanco del paro → puertas → máquina de estados → buzzer) con el intervalo de producción, 0,5 s.

Antes del paro se encienden DO3, DO6, DO14 y DO17. Se registra cada orden `SET`/`ALL_OFF` y los pines encendidos después de cada una.

- **Antes de la corrección** (`docs/informes/tanda9/B9_registro_ordenes_antes.md`), con puerta avanzada:

  ```
  0.0 --- PARO PULSADO ---
  0.0 SET DO22 ON   -> DO3, DO6, DO14, DO17, DO22
  0.0 SET DO11 ON   -> DO3, DO6, DO11, DO14, DO17, DO22
  0.0 ALL_OFF       -> —
  0.0 SET DO24 ON   -> DO24
  0.5 SET DO22 ON   -> DO22, DO24          <- cerrar puerta 1, con el buzzer
  0.5 SET DO11 ON   -> DO11, DO22, DO24    <- bloqueo puerta 1
  1.0 ALL_OFF       -> —
  1.5 SET DO22 ON / SET DO11 ON / SET DO24 ON -> DO11, DO22, DO24
  ...
  ```

  - DO22 y DO11 se encienden cada vez que el buzzer se enciende y se apagan con el ALL_OFF siguiente.
  - DO3, DO6, DO14 y DO17 (salidas de control previas al paro) **nunca** vuelven a encenderse.
  - Sin puerta avanzada no se enciende nada. La prueba `test_evidencia_sin_correccion_solo_las_puertas_se_reencienden` fija este resultado con la corrección desactivada.
- **Después de la corrección** (`docs/informes/tanda9/B9_registro_ordenes.md`):
  - primera orden tras el paro: `ALL_OFF`, uno solo en ese tick;
  - las puertas salen como `SET DO22 OFF` / `SET DO11 OFF`;
  - la única orden `ON` es `SET DO24 ON`;
  - ningún pin distinto de DO24 se enciende en 15 s.

### (b) Lectura del firmware (`Hardware/Comunicacion_esclava_ESP32_V3/.../Comunicacion_esclava_ESP32_V3.ino`, 1.0.0)

- `apagarTodo()` (l. 140-146) pone `estadoOut1 = estadoOut2 = 0xFFFF` **antes** de escribir y sin condiciones: aunque falle el I2C, la sombra queda limpia.
- `ALL_OFF` (l. 290-299) llama a `apagarTodo()` siempre; solo el `OK ALL_OFF` depende de que la escritura se verifique.
- `procesarSet` (l. 318-351) cambia **un solo bit** (`bitWrite`) y escribe la sombra completa del expansor (`write16`). Con la sombra limpia, el `SET DO24` del buzzer solo enciende DO24.
- `refrescarSalidas` (l. 433-446, cada 500 ms) re-escribe la sombra: con la sombra limpia, no enciende nada.
- El firmware nunca enciende una salida por su cuenta. Durante el paro acepta los `SET` (no conoce el paro: «toda decisión de fallo es del PC», FW §4.7).

### Descarte de las hipótesis, en orden

1. **Firmware (sombra con bits previos): DESCARTADA.** El ALL_OFF limpia la sombra sin condiciones (ver b). En la simulación, la primera orden tras el paro es `ALL_OFF` (antes, en el paso 5 del mismo tick; ahora, en el paso 2) y después de cada `ALL_OFF` la sombra está vacía (lo verifica la prueba). Condición: que el firmware cargado sea el 1.0.0 del repositorio. El PC exige el protocolo 2 con CRC, así que no puede ser V2.
2. **PC, reenvío por discrepancia o `_comandado`: DESCARTADA.**
   - `SerialLink.all_off()` registra OFF en los 32 canales de `_comandado` (`serial_link.py`, `all_off`).
   - El reenvío relee `_comandado` bajo `_cmd_lock`, así que solo puede reenviar OFF.
   - En el registro no aparece ningún `SET ... ON` de DO3/DO6/DO14/DO17 tras el paro.
3. **PC, ALL_OFF espaciado (`_INTERVALO_ALL_OFF_PARO_SEG`, `_SALIDAS_IGNORADAS_PARO`): CONTRIBUYE, no origina.** Permite que una salida re-encendida dure hasta el ALL_OFF siguiente. El origen son las órdenes `ON` de las puertas (`advanced_door.py`, `_from_cerrado`: `cerrar_on()` siempre y `bloquear_on()` con empaque bajo).

## Corrección (D9-9)

### `src/autoclave/devices/io/set_io.py`

- **`set_output` → `_paro_bloquea(index)`:** si la orden es encender y el canal no es el del buzzer, se fuerza a OFF y se avisa una sola vez por canal y por paro: «DOn no se enciende con el paro de emergencia activo». Bloquea en estos casos:
  - `PARO_REAL` en cualquier estado;
  - `PARO_EMERGENCIA` sin `PARO_REAL` (sin datos de la tarjeta) fuera de CICLO;
  - en CICLO, solo si la máquina pidió apagar hace 3 s o menos (`_VIGENCIA_PEDIDO_PARO_SEG`), con `apagar_por_paro` o con un `reset_all_outputs` hecho con el paro activo. Cubre el ciclo ya abortado que espera confirmación; la **tolerancia de DI vencida (P-3) no cambia**.
  - Solo cuentan flags `is True`: un estado de prueba `MagicMock` no bloquea nada.
  - Cubre todas las salidas: fases, estados, puertas (`AdvancedDoor._accionar` → `set_do.set_output`), `/io/test/output` y la orden invertida por atrapamiento.
- **`apagar_por_paro(inmediato=False)`:**
  - con `inmediato=True` manda el ALL_OFF sin mirar el intervalo;
  - si ese ALL_OFF se confirma, la llamada siguiente (la del estado, en el mismo tick) no usa el DO reportado, que todavía es el anterior al ALL_OFF. Así sale un solo ALL_OFF en el tick del flanco (SAF-04/TMG-01);
  - el resto del comportamiento A-7 no cambia.

### `src/autoclave/services/domain/loop/control_loop.py`

- **`_all_off_en_flanco_de_paro()`**, llamado en el paso 2 justo después de `paro_emergencia.update`. En el tick en que `PARO_REAL` pasa a True llama a `set_do.apagar_por_paro(inmediato=True)` bajo `_sm_lock`, para no compartir la espera del ACK con el ALL_OFF de entrar o salir del modo prueba (TMG-02). Nunca lanza.
- **`_paro_real_previo`**: se reinicia al perder el enlace (tras reconectar con el paro pulsado hay un flanco nuevo).
- Cambio acotado: unas 25 líneas en tres puntos, por el choque con S9.

### Requisitos

| Requisito | Estado |
|---|---|
| Al detectar el paro, ALL_OFF inmediato con ACK | Hecho. Flanco de `PARO_REAL` en el paso 2, antes de puertas y máquina. Sin ACK: órdenes individuales (como siempre) y repetición en el tick. |
| Con el paro, ninguna salida distinta del buzzer se enciende ni un instante (PC) | Hecho. Registro: la única orden `ON` es la del buzzer. Ensayo en los 4 programas: ninguna orden `ON` en 120 s de paro. |
| Ídem en el firmware | Se cumple sin cambios: el firmware solo aplica órdenes del PC y la sombra queda limpia tras el ALL_OFF. Un bloqueo por paro dentro del firmware exigiría conocer la entrada del paro, que es reasignable (R8): no se hace. |
| El buzzer conmuta solo su canal | Hecho: `SET DO24` y en el firmware un solo bit (prueba `test_con_paro_real_el_buzzer_si_conmuta` y el registro). |
| Fuera del paro, el buzzer no altera otras salidas | Verificado: `test_fuera_del_paro_el_buzzer_no_altera_otras_salidas`, con el doble del firmware. |

## Commits

- `2599b6b` fix: con el paro solo el buzzer puede encenderse; ALL_OFF inmediato en el flanco (más las pruebas y los registros).
- `2e9aeff` fix: correcciones de la revisión (SAF-03, SAF-04/TMG-01, TMG-02, SAF-06).
- `62a0be6` fix: re-revisión (TMG-01/02/03).
- Commit de documentación: caso de banco B-13, HAZ-B9-01 a 03 y este informe.

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-abc664462324dcc68\src\autoclave\__init__.py` (`PYTHONPATH=<worktree>/src`).

**Nuevas:** `tests/test_b9_buzzer_paro.py`: **31 aprobadas, 2 omitidas**. Las 2 omitidas son las que escriben el informe; se corren con `B9_ESCRIBIR_REGISTRO=1` y entonces pasan las 33. Cubren:
- el registro de órdenes en PREPARACION, PREPARADO y FALLA, con y sin puerta avanzada;
- la evidencia sin la corrección;
- las unitarias del bloqueo (paro real, sin datos fuera y dentro de CICLO, tick del aborto, buzzer, órdenes de apagar);
- `apagar_por_paro(inmediato)` y un solo ALL_OFF por DO viejo;
- el flanco en `ControlLoop` (una vez por pulsación, de nuevo tras soltar, bajo `_sm_lock`);
- el buzzer fuera del paro;
- el **ensayo en la planta simulada en los 4 programas de fábrica**, con paro en PRE_VACIO (CALENTAMIENTO en Líquidos) y en ESTERILIZACION. Tabla en `docs/informes/tanda9/B9_ensayo_tabla.md`. En las 8 celdas el resultado es ESPERANDO_CONFIRMACION, sin ninguna orden `ON` durante 120 s de paro y sin salidas encendidas; al soltar, las órdenes vuelven a aceptarse.

**Módulos que importan lo tocado** (48 archivos de `tests/`, `grep` de `set_io` / `SetOutput` / `ControlLoop` / `apagar_por_paro`, más `test_advanced_door*`, `test_io_test_mode_endpoints` y `test_s1_ensayo_simulador`): **1012 aprobadas, 5 omitidas, 0 fallidas** en la última pasada, antes del último ajuste.
- En esa pasada falló `test_s2b_revision_correcciones.py::test_set_output_pasa_el_plazo_al_enlace` (un `SetOutput.__new__` sin `estado`).
- Se corrigió en el código: `reset_all_outputs` nunca puede lanzar antes del ALL_OFF.
- Después de ese ajuste se repitieron solo `test_s2b_revision_correcciones`, `test_b9_buzzer_paro`, `test_adenda_enlace_paro` y `test_set_io_reset_outputs`: 87 aprobadas.

## Revisión ★

`safety-reviewer` y `timing-auditor` corrieron en paralelo, con una pasada y una re-revisión.

**Corregidos:**
- SAF-03 (Medio): paro sin datos en CICLO ya abortado.
- SAF-04/TMG-01 (Bajo/Medio): doble ALL_OFF en el flanco.
- TMG-02 (Medio): ALL_OFF del flanco bajo `_sm_lock`.
- SAF-06 (Bajo): clave de la prueba.
- Re-revisión TMG-01, 02 y 03 (Bajos): la gracia ya no depende del reloj, el tick del aborto ya bloquea y el pedido se borra al soltar el paro.

**Sin cambio, documentados:**
- TMG-03 de la primera pasada (Bajo): ventana menor que un tick entre el flag y una orden del backend. Hoy solo el modo prueba enciende desde el backend, y el paso 2c lo cancela con ALL_OFF en ese mismo tick.
- TMG-04 (Bajo): `_avisadas_paro` sin lock; solo afecta al log.
- TMG-02 de fondo (Medio, preexistente): `SerialLink.all_off` comparte `_ack_event` entre hilos. `stop()` y `/outputs/reset` siguen sin `_sm_lock`; la solución de fondo es un lock que cubra el envío y la espera del ACK dentro del enlace.
- SAF-05 (Bajo): se loguea si falla el canal del buzzer.

**Altos abiertos** (no causados por la lógica nueva; requieren decisión):
- **SAF-01 / HAZ-B9-02 (Alto, depende del hardware):**
  - Con el paro y la cámara presurizada, la puerta avanzada ya no repone el empaque (`bloquear_on`) ni mantiene `cerrar_on`.
  - Antes recibía pulsos *accidentales* entre dos ALL_OFF.
  - D9-9 («ninguna salida distinta del buzzer») y §15.1 («con el paro, ALL_OFF y ninguna válvula») piden exactamente esto, así que **se mantiene** y queda como PREGUNTA PARA CRISTIAN.
  - El revisor acepta dejarlo abierto como decisión del dueño, registrada (no como preexistente), con prueba de banco.
- **SAF-02 / HAZ-B9-03 (Alto, preexistente):** una puerta en movimiento reanuda sola al soltar el paro. La máquina de la puerta está fuera del alcance de D9-9. El revisor acepta dejarlo abierto como preexistente; queda como PREGUNTA PARA CRISTIAN.

## DECISIONES SIN CONFIRMAR

1. El bloqueo también rige con «paro sin datos» (`PARO_EMERGENCIA` sin `PARO_REAL`) fuera de CICLO, y en CICLO una vez abortado. Durante la tolerancia de DI vencida en ciclo (P-3) no se bloquea nada, para no cambiar esa transición.
2. Las órdenes de encender bloqueadas salen a la tarjeta como `SET DOn OFF` (reafirman el apagado) en lugar de no enviarse.
3. Se bloquea también la apertura automática por atrapamiento (`ATRAPADA → ABRIENDO`) y la orden invertida de `/io/test/output` mientras dure el paro, porque D9-9 no deja excepciones. Ver la pregunta 3.
4. Sin cambios en el firmware ni en su versión: la causa no es el firmware.

## PREGUNTAS PARA CRISTIAN

1. **Tipo de puerta del equipo de pruebas:** ¿el perfil instalado tiene `door_type=simple` o `advanced`?
   - Si es `advanced`, la causa confirmada explica el banco.
   - Si es `simple`, el PC no ordena esos encendidos. Hay que hacer B-13 con la compilación D y anotar qué salidas se encienden, la versión de firmware (Información del sistema; debe ser 1.0.0) y el log. Si el log no muestra órdenes de encendido y algo se enciende, la causa está en la tarjeta o el cableado: siguiente paso, la trama ST y `disc_do`, y medir con la tarjeta sola.
2. **SAF-01:**
   - ¿El pulsador de paro corta por hardware la alimentación de las salidas o de la neumática?
   - ¿Las válvulas de bloqueo y cierre retienen la presión al apagarse?
   - ¿El cierre mecánico aguanta solo con la cámara presurizada?
   - Si no: ¿se exceptúa `bloqueo_puerta_N` del bloqueo con la cámara no segura (contra la letra de D9-9)?
3. **Atrapamiento con el paro:** ¿la puerta atrapada debe poder abrirse sola con el paro pulsado? Hoy queda bloqueada, igual que en la práctica con el corte físico.
4. **SAF-02:** ¿las puertas en movimiento deben pasar a un estado de parada con el paro y exigir una orden nueva al soltarlo?

## Archivos

- Código: `src/autoclave/devices/io/set_io.py`, `src/autoclave/services/domain/loop/control_loop.py`.
- Pruebas: `tests/test_b9_buzzer_paro.py`.
- Evidencia: `docs/informes/tanda9/B9_registro_ordenes_antes.md`, `B9_registro_ordenes.md`, `B9_ensayo_tabla.md`.
- Banco: B-13 en `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (regenerados `.md` y `.html`).
- Riesgos: HAZ-B9-01 a 03 en `docs/riesgos/registro_riesgos.md`.
- Sin i18n, sin `db_manager.py`, sin alarmas nuevas, sin QML.

## Pendientes

- B-13 en banco con la compilación D (y las preguntas 1 y 2).
- TMG-02 de fondo en `SerialLink.all_off` (un lock para el envío y la espera del ACK).
