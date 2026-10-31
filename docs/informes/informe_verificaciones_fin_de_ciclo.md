# Informe de verificaciones — fin de ciclo, arranque, apagado y perfiles

- **Fecha:** 2026-10-12
- **Rama:** `dev` (HEAD `2b89b55`), solo lectura, sin cambios de código.
- **Alcance:** V-01 a V-10.
- **Rutas:** relativas a la raíz del repositorio. `src/autoclave/` se abrevia como `sa/`.

---

## Resumen

| # | Respuesta corta | Gravedad |
|---|---|---|
| V-01 | Tras el reconocimiento **nadie continúa el protocolo de fallo**. PREPARACION sí ventea, pero **solo** por `descompresion_rapida` y **solo** si pasan los chequeos de sensores y suministros y no salta una excepción. Si no pasan, las válvulas quedan como las dejó el protocolo y nadie las supervisa. | Alta |
| V-02 | La fila de `ciclos` queda con `fecha_fin`/`resultado` en NULL. **No existe** el marcado de "interrumpido" al arrancar. Un ciclo COMPLETADO que muere antes de la confirmación también queda sin cierre. | Media |
| V-03 | Las salidas arrancan apagadas (0xFFFF, lógica activa en bajo). El watchdog es de 5 s, pero **cualquier línea** lo reinicia y solo se arma después de recibir la primera. El PC **no** envía ALL_OFF al conectar. **El .ino del repositorio no entiende el protocolo v2 con CRC que usa el PC.** | Alta |
| V-04 | Hay un botón "Apagar" solo en la UI tkinter: apaga salidas y cierra procesos, pero **no** apaga Windows **ni** cierra la base de datos. En QML no hay botón. Agregarlo es acotado, pero la protección actual solo bloquea CICLO: no impide apagar con la cámara presurizada. | Media |
| V-05 | `SimpleDoor` usa solo `puerta_N_cerrada`. Sin embargo, PREPARACION/PREPARADO/CICLO exigen **siempre** las dos puertas y los dos sensores de empaque, sea cual sea el tipo o la cantidad de puertas. El paro se lee en el DI 10, dentro de `ControlLoop`. | Alta |
| V-06 | Fábrica: `bowe_dick`, `instrumental_134`. Usuario: esos dos más `instrumental_121`. **Falta `factory/instrumental_121.json`.** `apertura_automatica=false` en los 5. | Baja |
| V-07 | Las temperaturas inválidas llegan como `None`, pero PREPARACION/PREPARADO las comparan con `== 0`. Un sensor ausente pasa como válido, y `temp_drenaje=None` provoca un `TypeError` que aborta el tick. `ciclo.py` sí está protegido. | Alta |
| V-08 | Sin presostato: alarma no bloqueante y **chaqueta nunca calentada**. Hay un conflicto ON/OFF en PRECALENTAMIENTO. Sin entrada de suministro eléctrico: **PREPARADO nunca queda listo** y no se puede iniciar ningún ciclo. | Alta |
| V-09 | El perfil de instalación no tiene tipo de secado (solo `cooling_level`, que no se usa). El tipo de secado se elige por ciclo en `secado.modo` (1–3), y todos los modos usan solo la fase SECADO. | Info |
| V-10 | No hay ciclo de líquidos. Calentamiento y esterilización ignoran la sonda de carga, y `cycle_temperature_sensors` no se usa. La descompresión de líquidos (modos 4/5) existe, pero el **protocolo de fallo la omite** y despresuriza sin enfriar. | Alta |

---

## V-01. Reconocimiento de un FALLO con la cámara presurizada

### Secuencia real

1. Una fase falla. `CicloState` llama a `ProtocoloFallo.ejecutar()` y guarda `_resultado_pendiente = FALLO` (`sa/state_machine/states/ciclo.py:551-568`).
   - `ejecutar()` hace ALL_OFF y abre la válvula del modo de descompresión (`sa/state_machine/cycle_phases/protocolo_fallo.py:58-104`). Con el modo 0/2 abre la lenta; con el 1, la rápida; con el 4/5, chaqueta y rápida.
2. Mientras se espera la confirmación, **solo ahí** corre `ProtocoloFallo.update()` (`ciclo.py:430-431`). Ese método:
   - escala a chaqueta+rápida si vence el timeout (`protocolo_fallo.py:174-182`);
   - abre aire atmosférico si la cámara entra en vacío (`:188-193`);
   - emite el buzzer de "condición segura" (`:202-212`).
3. El backend acepta `/cycle/acknowledge` en cuanto `fase_ciclo` tiene resultado. **No mira presión ni temperatura** (`sa/backend/server.py:1092-1126`). Con un fallo, además pre-arma `RESET_FALLA` (`:1117-1123`).
4. Tick N: `CicloState.run()` devuelve `FALLO` (`ciclo.py:409-417`), y la máquina pasa a FALLA (`sa/state_machine/state_machine.py:112-114`).
5. Tick N+1: `FallaState.run()` ve `RESET_FALLA` y devuelve True (`sa/state_machine/states/falla.py:38-41`). Se limpian `Alarmas_activas` y la máquina pasa a PREPARACION (`state_machine.py:127-130`). **FALLA no toca ninguna salida** salvo con el paro activo.
6. Desde ese momento `ProtocoloFallo.update()` no vuelve a ejecutarse: la última llamada está en `ciclo.py:431`. Lo que hizo el protocolo queda **enclavado en la tarjeta**, porque nadie lo apaga.

### ¿PREPARACION despresuriza?

Sí, pero de forma parcial y condicionada:

- `igualar_presion_camara()`: si `pres_camara > atm + rango`, devuelve `quiere_rapida=True` y `ejecutor()` enciende `descompresion_rapida` (`sa/state_machine/states/preparacion.py:239-244` y `:95-98`). En rango, apaga la lenta y la rápida (`:222-229`, `:98`). En vacío, abre aire atmosférico (`:231-237`).
- **Condición 1:** `ejecutor()` solo corre si `supervisor()` pasa (`preparacion.py:72-75`). Basta un sensor en 0 (por ejemplo `pres_empaque_2` sin sensor, ver V-05) o un DI de suministro en 0 (`agua_bomba`, `agua_generador`, `aire_comprimido`, `:142-159`) para que **no se ejecute ninguna acción**. Las válvulas quedan como las dejó el protocolo, sin supervisión de vacío ni escalado por timeout.
- **Condición 2:** dentro de `ejecutor()`, `verificar_temperatura_drenaje()` corre **antes** de decidir la válvula rápida (`:90-98`). Con `temp_drenaje=None`, `evaluar_banda(None, …)` lanza un `TypeError` (ver V-07). La excepción la captura `ControlLoop.run()` (`sa/services/domain/loop/control_loop.py:101-104`), y la orden de la descompresión rápida **nunca se emite**.
- **Hueco 1:** PREPARACION no apaga nunca `descompresion_chaqueta` (no aparece en `preparacion.py` ni en `preparado.py`). Con el modo 4/5, esa válvula queda abierta indefinidamente mientras `suministrar_vapor_chaqueta()` vuelve a meter vapor a la chaqueta (`preparacion.py:191-192`).
- **Hueco 2:** PREPARACION deja `descompresion_lenta` abierta mientras la presión siga alta; solo la cierra al llegar al rango (`:226`). Funciona, pero sin el timeout ni el escalado del protocolo.

**Conclusión:** ningún módulo "continúa" el protocolo de fallo. PREPARACION hace un venteo propio y más simple, que depende de que los sensores, los suministros y el drenaje estén sanos.

---

## V-02. Tabla `ciclos` si el proceso muere a mitad de ciclo

### Qué se escribe y cuándo

- **Esquema** (`sa/services/domain/logging/db_manager.py:35-50`): `fecha_fin`, `resultado` y `motivo_fallo` son anulables o tienen valor por defecto. WAL activado (`:32`).
- **Al entrar en CICLO:** `CycleLogger._on_inicio()` llama a `crear_ciclo()` (`sa/services/domain/logging/cycle_logger.py:206-236`). La fila solo lleva `fecha_inicio` y metadatos, y se confirma de inmediato (`db_manager.py:315-348`, commit en `:348`).
- **Durante el ciclo:** cada lectura (`insertar_lectura`, commit en `:462`), cada punto de la gráfica (`:495`) y cada tramo de fase (`abrir_fase` `:515`, `cerrar_fase_abierta` `:525`) se confirma por separado.
- **Al cerrar:** `cerrar_ciclo()` es el **único** `UPDATE ciclos` del código (`db_manager.py:350-358`). Lo invoca `_on_fin()` (`cycle_logger.py:269-278`).

### Si el proceso muere

- La fila queda con `fecha_fin = NULL`, `resultado = NULL` y `motivo_fallo = ''`. La última fila de `ciclo_fases` queda con `fin_s = NULL`. Las lecturas llegan hasta el último commit.
- **Caso adicional, ciclo COMPLETADO:** los cierres anormales (fallo, cancelación, emergencia) se registran en cuanto aparecen (`cycle_logger.py:153-160`). En cambio, `COMPLETADO` solo se cierra cuando la máquina **sale** de CICLO, es decir, tras la confirmación del operador o la apertura automática (`:150-152`, `:161-164`). Un corte durante la espera de confirmación deja **un ciclo exitoso sin cierre**.

### ¿Existe el marcado de "interrumpido" al arrancar?

**No.** No hay ningún `UPDATE` sobre `ciclos` fuera de `cerrar_ciclo`, ni código de arranque que busque `fecha_fin IS NULL`. Hoy los consumidores toleran el NULL:

- `progreso_ciclo.resultado()` devuelve `None` (`sa/core/runtime/progreso_ciclo.py:35-45`).
- Reportes lo cuenta como `sin_cierre` (`sa/services/domain/reportes/resumen_periodo.py:5-8`).
- QML lo muestra "sin dato" (`sa/ui_qml/domain/resumen_sistema.py:64-69`).
- `get_ciclos_desde(terminados=True)` lo excluye (`db_manager.py:401-406`).

Existe un latido en `data/last_shutdown.json` cada 30 s (`sa/devices/printer/heartbeat.py:10,40`; `sa/main.py:254-255`), pero solo lo usa el ticket de arranque, no la base de datos.

---

## V-03. Firmware (`Comunicacion_esclava_ESP32_V2.ino`) y ALL_OFF en el PC

Archivo: `Hardware/Comunocacion_esclava_ESP32_V2/Comunicacion_esclava_ESP32_V2/Comunicacion_esclava_ESP32_V2.ino`. Su última modificación es `17758bd`, anterior al protocolo v2.

### Estado de las salidas al arrancar

- `estadoOut1 = estadoOut2 = 0xFFFF`, con el comentario "1 = OFF" (lógica activa en bajo, `.ino:24-25`). Se escriben en `setup()` justo después de `begin()` (`.ino:47-55`), así que **todas las salidas arrancan apagadas**.
- El intervalo entre el encendido y `setup()` depende del estado de encendido del PCF8575 (salidas en alto) y de la librería `PCF8575::begin()`. Ninguna de las dos cosas se puede verificar desde el repositorio.

### Watchdog de comunicación

- Dispara a los **5 s** sin recibir líneas (`WD_TIMEOUT_MS = 5000`, `.ino:35`). Al dispararse escribe 0xFFFF en las dos expansiones y envía `"WD: ALL_OFF"` (`.ino:86-96`).
- **Limitaciones:**
  - Al arrancar está **desarmado** (`wdActivo = false`, `.ino:34`). Solo se arma al recibir la primera línea (`:105`). Tras dispararse vuelve a desarmarse (`:93`).
  - **Cualquier línea** terminada en `\n` lo reinicia, sea válida o no (`.ino:103-105`, antes de interpretar el comando). No valida tramas.
  - En el PC, el `HB` lo envía el hilo de supervisión de `SerialLink` (`sa/protocols/serial_link.py:257-260`), que es independiente de `ControlLoop`. Un `ControlLoop` o una máquina de estados colgados **siguen alimentando** el watchdog del ESP32.
- **Del lado del PC:**
  - El enlace se declara caído a los 3 s sin líneas válidas (`serial_link.py:44`, `:264-281`).
  - `HB` se envía cada 2 s (`:45`).
  - El ciclo se aborta tras 5 s de desconexión (`control_loop.py:37`, `:162-165`).

### ¿El PC envía ALL_OFF al conectar?

**No.** `_connect()` abre el puerto y limpia los búferes, pero no envía ALL_OFF (`serial_link.py:136-181`). Los parámetros `all_off_intentos`, `all_off_timeout_s` y `handshake_presupuesto_s` están definidos (`sa/protocols/serial_link_config.py:29-32`), pero **ningún código los usa**.

ALL_OFF solo se envía en estos casos:
- `ControlLoop.stop()` (`control_loop.py:307`);
- bloqueo por configuración (`:201`);
- modo prueba (`:217`, `:374`, `:383`);
- `/outputs/reset` (`server.py:1084`);
- protocolo de fallo;
- estados con el paro activo.

### Hallazgo crítico: incompatibilidad de protocolo

El PC envía comandos con CRC (`payload*HHHH`, `serial_link.py:436-438`) y rechaza las líneas que llegan sin CRC (`:310-323`). El `.ino` del repositorio no conoce el CRC:

- `"ALL_OFF*HHHH"` no coincide con `"ALL_OFF"` (`.ino:111`).
- En `"SET DO3 ON*HHHH"`, el estado queda como `"ON*HHHH"`, así que `on = false` (`.ino:135-139`). **Todo SET … ON apaga la salida.**
- Las tramas `AI:`, `DI:` y `DO:` salen sin CRC (`.ino:211-228`). El PC nunca marca `data_alive` y reconecta cada 3 s.

Esto concuerda con la nota de que `858f840` rompe el firmware V2. **El firmware v2 con CRC no está en el repositorio**, así que no fue posible verificar su comportamiento.

---

## V-04. Función de apagado del equipo

### Lo que existe

- **UI tkinter:** el botón de encendido (`sa/ui/window/main_window.py:515-518`) llama a `apagar_equipo()` (`:621-657`), que hace lo siguiente:
  1. `POST /outputs/reset`, rechazado con 409 en CICLO (`sa/ui/service_ui/ui_service_backend.py:274-290`).
  2. Muestra la pantalla "Apagando equipo…".
  3. A los 3 s ejecuta `on_close()` (`sa/main.py:265-298`): repite el reset de salidas, termina el proceso de ajustes, termina el backend (con `terminate()`, que en Windows es TerminateProcess) y cierra la ventana.
- **Backend:**
  - `/outputs/reset` (`sa/backend/server.py:1070-1089`) llama a `control_loop.stop()` (ALL_OFF + detener el enlace, `control_loop.py:305-315`) y después a `reset_all_outputs()`. Solo se bloquea en CICLO.
  - El `lifespan` también detiene el loop en un cierre ordenado (`server.py:36-47`). Un TerminateProcess no pasa por ahí.
- **UI QML:** no hay botón de apagado (sin coincidencias en `sa/ui_qml/qml`). `sa/ui_qml/lanzar.py:85-121` solo lanza y termina procesos.

### Lo que no existe

- **Apagar Windows:** no hay `shutdown /s` en ningún sitio.
- **Cierre de la base de datos:** `DbManager.close()` existe (`db_manager.py:557-563`), pero **nadie lo llama**. Hoy la integridad depende de los commits por escritura y del WAL.

### Alcance estimado para agregar "Apagar equipo"

Es un cambio acotado, de 3 a 4 piezas:

1. Un endpoint del backend que reutilice `/outputs/reset`, agregue `context.db.close()` (y el de las otras bases de auditoría) y lance `shutdown /s /t N`.
2. Un botón en QML con confirmación, a través del bridge.
3. En tkinter, encadenar el apagado de Windows después de `on_close()`.
4. Pruebas.

**Riesgo a decidir:** la protección actual solo bloquea CICLO. En FALLA o PREPARACION con la cámara aún presurizada (ver V-01), el ALL_OFF **cierra todas las válvulas de descompresión** y deja la cámara presurizada y sin supervisión. El apagado debería exigir presión y temperatura seguras, con el mismo criterio fail-closed del botón CONFIRMAR.

En equipos de dos PC, la ventana secundaria no debe apagar (`main.py:268-277`).

---

## V-05. Puerta `door_type="simple"` y paro de emergencia

### Construcción

- `build_hardware()` arma `doors_cfg` con una entrada por cada puerta de `profile.door_count` (`sa/devices/factory/factory.py:48-55`). Para cada una, `_build_door_cfg()` (`:12-45`) define:
  - `name = "Puerta N"`;
  - `type`;
  - `di = {"abierta": "puerta_N_abierta", "cerrada": "puerta_N_cerrada"}`.
- El tipo simple **no** recibe `do`, `ai`, `atrapamiento` ni `bloqueo`.
- `create_door()` instancia `SimpleDoor(name, di, estado)` (`sa/devices/puertas/door_factory.py:13-18`). El tipo llega como enum gracias a `sa/installation/storage.py:30`.
- `SimpleDoor` solo lee `di["cerrada"]` (`sa/devices/puertas/simple_door.py:19-20`, `:58-67`). La clave `"abierta"` se arma pero **no se usa**. `tiene_actuador = False` y los comandos no hacen nada (`:8`, `:42-49`).
- Índices de los DI (`sa/core/runtime/status.py:34-37`): `puerta_1_cerrada`=2, `puerta_1_abierta`=3, `puerta_2_cerrada`=4, `puerta_2_abierta`=5.

### Hallazgo: los estados ignoran el tipo y la cantidad de puertas

- `preparado.puertas_cerradas()` exige `puerta_1_cerrada` **y** `puerta_2_cerrada` (`sa/state_machine/states/preparado.py:206-221`).
- `CicloState._verificar_puertas()` exige las dos puertas **y** `pres_empaque_1/2 ≥ 0.6 × presion_empaque` (300 × 0.6 = 180 kPa) (`ciclo.py:184-204`). Como la presión nunca es `None` después de la primera trama (`sa/hal/measures/converters.py:194-228`), el chequeo está siempre activo.
- `preparacion.verificar_sensores()` exige `pres_empaque_1/2 != 0` (`preparacion.py:105-110`, `:120-128`). Si no se cumple, PREPARACION se queda bloqueada.

**Consecuencia:** un equipo de una puerta, o una puerta simple sin sensor de empaque, no sale de PREPARACION. Si lograra entrar a CICLO, fallaría con `FALLO_PUERTA_N_EMPAQUE` en el primer tick, salvo que se puenteen las entradas.

### Paro de emergencia

- Se lee en el DI índice 10 (`status.py:42`). Cada tick, `ControlLoop._tick()` lo pasa a `EmergencyStop.update()` (`control_loop.py:186-189`), que publica el flag `PARO_EMERGENCIA` (`sa/devices/paro_emergencia/paro_emergencia.py:22-30`).
- Consumen el flag: PREPARADO (`preparado.py:46`), CICLO (`ciclo.py:445`), FALLA (`falla.py:21`), HIBERNACION (`hibernacion.py:16`), puertas (`sa/services/domain/puertas/ser_puertas.py:90`), el backend (`server.py:1056`, `:1105`, `:1390`) y el modo prueba (`control_loop.py:215`, `:369`).
- **Excepción:** PREPARACION lee el DI crudo `sensores_di["paro_emergencia"]` en vez del flag (`preparacion.py:63`). En el mismo tick el valor es equivalente, pero es inconsistente.
- **Polaridad:** el firmware invierte los bits (`.ino:219-222`), así que una entrada sin conectar (pull-up) se lee como 0, es decir, "sin paro". Si el cableado del paro es normalmente cerrado y abre al pulsarse, un cable cortado **no** se detectaría. Hay que confirmarlo contra el esquema eléctrico, que no está en el repositorio.

---

## V-06. Programas de fábrica y de usuario

| Archivo | `cycle_id` | Nº | `apertura_automatica` | Observación |
|---|---|---|---|---|
| `sa/cycles/factory/bowe_dick.json` | `bowe_dick` | 1 | `false` (`:143`) | `temp_max_apertura` 80 |
| `sa/cycles/factory/instrumental_134.json` | `134_instrumental` | 2 | `false` (`:134`) | **sin sección `estabilizacion`**; `temp_max_apertura` 80 |
| `sa/cycles/user/bowe_dick.json` | `bowe_dick` | 1 | `false` (`:653-654`) | `temp_max_apertura` 100 |
| `sa/cycles/user/instrumental_121.json` | `instrumental_121` | 3 | `false` (`:653-654`) | **no tiene equivalente de fábrica** |
| `sa/cycles/user/instrumental_134.json` | `134_instrumental` | 2 | `false` (`:653-654`) | `secado.modo` = 3 |

- **Falta:** `sa/cycles/factory/instrumental_121.json`. No existe ningún perfil de líquidos.
- La carga es primero fábrica y después usuario, que **pisa** por `cycle_id` (`sa/core/managers/cycle_manager.py:121-126`, `:168`). Por eso `instrumental_121` solo existe como programa de usuario y no hay valores de fábrica para restaurarlo.
- El nombre de archivo `instrumental_134` no coincide con su `cycle_id` `134_instrumental`.
- El ciclo por defecto es `bowe_dick` (`sa/backend/context.py:39`).
- Los 5 perfiles traen `descompresion.modo = 1`.

---

## V-07. Entradas leídas sin verificar `None`

### De dónde viene el `None`

- **Temperaturas:** valen `None` cuando el ADC lee 0 o ≥ 4095 (`converters.py:168-174`).
- **Presiones:** nunca valen `None` después de la primera trama, porque se recortan a ≥ 0 (`converters.py:194-228`). Solo valen `None` antes del primer dato (`status.py:98`).
- **DI:** son enteros, empiezan en 0 y nunca valen `None` (`status.py:99`).
- **Excepciones:** se capturan en `ControlLoop.run()` (`control_loop.py:101-104`). Se pierde el resto del tick (F0, registro de ciclo, buzzer) y las salidas quedan enclavadas.

### `preparacion.py`

| Línea | Entrada | Problema |
|---|---|---|
| `:130-138` | todas las temperaturas | Compara `== 0`. Un `None` **pasa como válido** y además borra `ERROR_AI_*`. |
| `:120-128` | todas las presiones | `== 0` (correcto en la práctica: un sensor desconectado lee 0). |
| `:171` → `:188` | `pres_chaqueta` | `evaluar_banda` sin chequeo (solo riesgo antes del primer dato). |
| `:216` → `:222` | `pres_camara` | Comparación directa sin chequeo (ídem). |
| `:261` → `:265` | `temp_drenaje` | **`TypeError` si el sensor está desconectado**. Corta `ejecutor()` antes de decidir la descompresión rápida (`:95-98`). |
| `:63`, `:150`, `:178`, `:251` | DI | Acceso con `[...]`, seguro porque las claves existen siempre. |

### `preparado.py`

| Línea | Entrada | Problema |
|---|---|---|
| `:256-261` | todas las temperaturas | `== 0`. Un `None` pasa como válido. |
| `:249-254` | todas las presiones | `== 0`. |
| `:94` → `:110` | `pres_chaqueta` | Sin chequeo (antes del primer dato). |
| `:136` → `:143` | `pres_camara` | Sin chequeo (ídem). |
| `:169` → `:173` | `temp_drenaje` | **`TypeError` si el sensor está desconectado.** Ocurre en `ejecutor()` y otra vez en `esta_preparado()`. |

### `ciclo.py`

Está protegido. Todas las lecturas usan `.get()` con chequeo de `None`: `:196`, `:200-201`, `:210-212`, `:215`, `:247-249`, `:280-282`, `:323-325`, `:350-352` y sensores críticos en `:494-500`. Solo se consideran críticos `temp_camara` y `pres_camara` (`:32-33`).

---

## V-08. Perfil piso de laboratorio sin presostato de vapor ni entrada de suministro eléctrico

- **Capacidades de `PISO_LAB`:** `sa/installation/equipment.py:46-50`. **No existe** ninguna capacidad que desactive `vapor_suministro` (DI 12) o `suministro_electrico` (DI 13). Las dos se leen siempre.
- **Entrada sin conectar:** se lee como 0 (inversión del firmware, `.ino:219-222`).
- Los valores por defecto `.get(..., 1)` (`preparado.py:277`, `control_loop.py:193`) **no tienen efecto**: la clave existe siempre (`status.py:99`) y la trama trae los 56 DI.

### `vapor_suministro = 0` (sin presostato)

- **PREPARACION** (`preparacion.py:178-184`) y **PREPARADO** (`preparado.py:100-106`):
  - `vapor_chaqueta` se apaga;
  - aparece la alarma `SUMINISTRO_VAPOR` (ALERTA, **no bloqueante**);
  - se limpian `CHAQUETA_FRIA` y `CHAQUETA_SOBRECALENTADA`;
  - la chaqueta se da por lista (`return True`).
  - Resultado: **la chaqueta nunca se calienta en reposo** y no hay bloqueo.
- **CICLO** (`ciclo.py:214-225`): apaga la chaqueta cada tick con la misma alarma no bloqueante.
- **Conflicto en PRECALENTAMIENTO:** en el mismo tick, `_mantener_chaqueta()` (`ciclo.py:517`) envía OFF y luego la fase envía ON (`sa/state_machine/cycle_phases/precalentamiento.py:74`, `:88`, ejecutada en `ciclo.py:529`). Son dos comandos seriales opuestos por tick. Si no se alcanza `presion_precalentamiento`, termina en `FALLO_PRECALENTAMIENTO` por timeout (`precalentamiento.py:57-64`).
- Durante SECADO, `_mantener_chaqueta` no actúa (`ciclo.py:208-209`).

### `suministro_electrico = 0` (sin entrada)

- `SuministroElectrico.update()` activa `FALLO_SUMINISTRO_ELECTRICO` y, en el flanco, apaga `bomba_vacio` (`sa/devices/suministro_electrico/suministro_electrico.py:16-21`; `control_loop.py:191-194`).
- **PREPARACION:** no mira esta entrada, así que avanza normalmente a PREPARADO.
- **PREPARADO:**
  - `verificar_suministros()` levanta `SUMINISTRO_ELECTRICO` (ALERTA, bloqueante por defecto) y `supervisor()` falla (`preparado.py:276-281`, `:56-58`);
  - `esta_preparado()` también lo excluye (`:234`).
  - **`LISTO_PARA_CICLO` nunca se activa** y `/cycle/start` responde 409 (`server.py:1016-1020`).
- **CICLO:** inalcanzable. Si se llegara, aborta en el primer tick (`ciclo.py:461-474`).

Por lo mismo, `agua_bomba`, `agua_generador` y `aire_comprimido` sin cablear bloquean PREPARACION y PREPARADO (`preparacion.py:142-159`, `preparado.py:268-274`).

---

## V-09. Tipos de secado

- **`InstallationProfile`** (`sa/installation/profile.py:20-32`) **no tiene** campo de tipo de secado. Solo tiene `cooling_level` (un entero). `cap.cooling_mode_max` (`equipment.py:22`) es fijo por clase de equipo. **Ninguno de los dos interviene en el control**: `cooling_level` solo se muestra (`sa/ui_qml/bridge/info_equipo.py:86`) y `cooling_mode_max` no se usa fuera de `equipment.py`. Así que el perfil no admite varios tipos de secado ni uno solo.
- **Elección por ciclo:** `parameters.secado.modo` (1–3) del JSON, leído en `sa/state_machine/cycle_phases/secado.py:32`.
- La fase se salta si `!cap.has_vacuum` o si `tiempo_secado == 0` (`secado.py:23-30`).
- **Modos:**
  - **1:** vacío continuo (bomba + `vacio_camara`) y chaqueta regulada a `presion_chaqueta_secado` (`:76-84`).
  - **2:** como el 1, pero con `aire_admosferico_camara` abierto al mismo tiempo (`:86-95`).
  - **3:** pulsos entre `presion_baja_secado` (vacío) y `presion_alta_secado` (aire), con `timeout_pulso`. Si se agota termina en FALLO (`:97-140`).
- **Fases:** todos los modos usan solo la fase SECADO. El pipeline es siempre el mismo (`ciclo.py:97-104`).
- **Parámetros sin uso:** `globals.enfriar_chaqueta_secado` está en los JSON, pero ningún `.py` lo lee.
- **Enfriamiento:** el tipo de enfriamiento es otro parámetro, `descompresion.modo` (0–5, ver V-10). Tampoco se valida contra `cooling_mode_max`: una clase con máximo 3 acepta 4 o 5.

---

## V-10. Ciclo de líquidos en el código actual

### Roles de las sondas

- **Mapa fijo** (`status.py:16-22`): `temp_camara`=0, `temp_2_camara`=1, `temp_ref`=2, `temp_drenaje_cam`=4, `temp_drenaje`=5.
- **`cycle_temperature_sensors`:** está en los JSON (`{"1":"temp_camara","2":"temp_ref"}`), pero **ningún `.py` lo lee en `dev`**. Los roles configurables existen en la rama `feature/roles-sensor-temperatura` (worktree `.worktrees/roles-sensor-temperatura`), con 10 commits sin unir hasta `87fca2f`.
- **`temp_camara`:** es el único sensor de control y de fallas.
- **`temp_ref`:**
  - visualización ("Temp. 1", `sa/ui/window/main_window.py:329`, `:773`);
  - gráfica (`cycle_logger.py:327`; `db_manager.py:80`);
  - verificación de sensores en PREPARACION (`:115`).
- **`temp_2_camara`:**
  - F0 usa `min(temp_camara, temp_2_camara)` si `cap.has_liquid_sensor` (`control_loop.py:283-285`);
  - verificación en PREPARACION (`preparacion.py:114`);
  - lectura en `/status` (`server.py:582`).

### Calentamiento y esterilización

- Solo usan `_temp_camara()` (`sa/state_machine/cycle_phases/calentamiento.py:223`, `:237`; `sa/state_machine/cycle_phases/esterilizacion.py:190`).
- `BaseFase._temp_camara_2()` existe (`sa/state_machine/cycle_phases/base_fase.py:37-38`), pero **no tiene llamadores**.
- **La sonda de carga no participa** en el control ni en las fallas. Es el pendiente que ya registra CLAUDE.md.
- `cap.has_liquids` y `cap.bleve_protection` no se usan en el control. Solo aparecen en el asistente (`sa/installation/wizard.py:85`).
- No existe ningún perfil de líquidos (V-06).

### Descompresión para líquidos

**Modos 4 y 5** (`sa/state_machine/cycle_phases/descompresion.py:132-200`):

1. **Enfriamiento:**
   - `agua_chaqueta` encendida;
   - contrapresión con `aire_comprimido_camara`, en pulsos de 3 s, mientras `pres < presion_camara_enfriamiento` (200 por defecto);
   - pulsos de `descompresion_chaqueta` (`tiempo_apertura_chaqueta` / `tiempo_cierre_chaqueta`);
   - el modo 5 abre además la lenta.
   - Dura hasta que `temp_camara ≤ temperatura_enfriamiento` (80 °C por defecto). Se mide con la sonda de **cámara**, no con la de carga.
2. **Descompresión:** chaqueta + rápida hasta la presión atmosférica.

Los parámetros `modo_4` y `modo_5` existen en `instrumental_134`, tanto de usuario (`:556`, `:593`) como de fábrica (`:115`, `:122`).

**Riesgo:** con el modo 4/5, el **protocolo de fallo** abre directamente chaqueta + rápida, sin la etapa de enfriamiento ni de contrapresión (`protocolo_fallo.py:138-140`; también `valvula_reposo.py:16-18`). Ante un fallo con carga líquida caliente, la cámara se despresuriza sin enfriar, que es precisamente el escenario que `bleve_protection` debería cubrir.

---

## Puntos que no se pudieron verificar desde el repositorio

1. El firmware v2 con CRC que corresponde a `858f840`: no está en el repositorio.
2. El estado de las salidas entre el encendido y `setup()`: depende de la hoja de datos del PCF8575 y de la versión de la librería.
3. La polaridad y el cableado del paro de emergencia, y de los DI de suministro, en el esquema eléctrico.
