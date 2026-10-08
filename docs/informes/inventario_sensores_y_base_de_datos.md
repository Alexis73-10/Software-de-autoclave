# Inventario de sensores, detección de fallas y dependencias de base de datos

Fecha: 2026-10-02 · Rama: `dev` · Solo lectura (no se modificó código). Los hallazgos salen de leer el código, no de ejecutarlo; los que dependen de ese análisis están marcados como "por lectura".

---

## 1. Cadena de adquisición

`ESP32 → SerialLink (protocols/serial_link.py) → Units (hal/measures/units.py) → converters.py → EstadoAutoclave (core/runtime/status.py) → máquina de estados`

- La trama `AI:` trae 16 enteros de ADC de 12 bits (0–4095): los índices 0–7 son temperatura y los 8–15 son presión (`converters.py:167` y `:211-212`). Se acepta solo si trae exactamente 16 valores (`serial_link.py:225`).
- La trama `DI:` trae ≥56 bits y `DO:` trae ≥32 bits (`serial_link.py:230`, `:235`).
- La conversión de temperatura es: mediana(5) sobre el crudo → calibración de fábrica lineal `adc_min..adc_max → temp_min..temp_max`, después `×gain+offset` → calibración de usuario (`gain/offset` o `poly`) → filtro OneEuro → redondeo a 0.1 (`converters.py:154-191`).
- La presión sigue la misma tubería, más un recorte final `max(0.0, valor)` (`converters.py:198-232`).
- El nombre lógico → índice está **solo** en `EstadoAutoclave.map_temp / map_pres / map_di` (`status.py:12-43`). La API de calibración usa ese mismo mapa (`backend/server.py:35-41`).

## 2. Canales de sensores

### 2.1 Analógicos — temperatura (unidad °C, índice ADC = índice lógico)

| Nombre (runtime) | Canal AI | Fábrica `calibration.yaml` (adc_min–adc_max → °C, gain/offset) | Usuario (gain/offset) |
|---|---|---|---|
| `temp_camara` | 0 | 20–4000 → 0–200, 1.015 / 6.89 | 1.079022 / −6.163755 (recalibrado 2026-08-04) |
| `temp_2_camara` | 1 | 100–4000 → 0–200, 0.9893 / 11.63 | 1.0 / 0.0 |
| `temp_ref` | 2 | 105–3990 → 0–200, 0.9893 / 11.63 | 1.0 / 0.0 |
| `temp_chaqueta` | 3 | 100–4000 → 0–200, 0.9893 / 11.63 | 1.0 / 0.0 |
| `temp_drenaje_cam` | 4 | 95–4010 → 0–200, 0.9893 / 11.63 | 1.0 / 0.0 |
| `temp_drenaje` | 5 | 100–4000 → 0–200, 0.9893 / 11.63 | 1.0 / 0.0 |
| (sin nombre) | 6, 7 | 102–3995 / 100–4000 → 0–200 | 1.0 / 0.0 |

### 2.2 Analógicos — presión (unidad kPa, canal ADC = 8 + índice)

| Nombre (runtime) | Índice / canal AI | Fábrica (adc → kPa, gain/offset) | Usuario (gain/offset) |
|---|---|---|---|
| `pres_camara` | 0 / AI8 | 5–4050 → 2–400, 1.0 / 0.0 | 1.364056 / −75.348611 (2026-08-04) |
| `pres_chaqueta` | 1 / AI9 | 50–4050 → 0–400, 1.0 / 0.0 | 1.313705 / −71.829031 (2026-07-23) |
| `pres_empaque_1` | 2 / AI10 | 50–4050 → 0–400 | 1.313705 / −71.829031 |
| `pres_empaque_2` | 3 / AI11 | 50–4050 → 0–400 | 1.313705 / −71.829031 |
| (sin nombre) | 4–7 / AI12–15 | 50–4050 → 0–400 | 1.3466 / −67.11 (dato de ejemplo, nunca calibrado) |

### 2.3 Digitales (bit de la trama `DI:`, 0/1, sin unidad)

| Nombre | Bit | | Nombre | Bit |
|---|---|---|---|---|
| `aire_comprimido` | 0 | | `atrapamiento_puerta_2` | 7 |
| `presion_agua` | 1 | | `agua_bomba` | 8 |
| `puerta_1_cerrada` | 2 | | `agua_generador` | 9 |
| `puerta_1_abierta` | 3 | | `paro_emergencia` | 10 |
| `puerta_2_cerrada` | 4 | | `agua_camara` | 11 |
| `puerta_2_abierta` | 5 | | `vapor_suministro` | 12 |
| `atrapamiento_puerta_1` | 6 | | `suministro_electrico` | 13 |

### 2.4 Inconsistencias de configuración encontradas

1. **Los YAML de modelo e instancia no se usan.** `config/models/*.yaml` (`io_contract`, `limits`) y `config/instances/ACV-2026-001.yaml` (`io_enabled`) no se leen desde ningún `.py` (grep sin resultados para `io_enabled`, `io_contract`, `limits`, `active_instances`). Las capacidades reales vienen de `installation/equipment.py` (enum en código).
2. **Los nombres y el orden no coinciden** entre esos YAML y el runtime: YAML `temp_referencia` / `temp_drenaje_camara` vs runtime `temp_ref` / `temp_drenaje_cam`. Si se tomara el orden del YAML, `temp_drenaje` caería en el índice 3, pero en el runtime el índice 3 es `temp_chaqueta` y `temp_drenaje` es el 5. `suministro_electrico` (DI 13) no figura en el YAML.
3. `models/solids_liquids.yaml:10-11` tiene `supported_count` al mismo nivel que `chamber:` (indentación rota; hoy no importa porque nadie lo lee).
4. La instancia no incluye `descompresion_lenta` en `io_enabled.DO`, aunque ESTERILIZACION la usa.
5. Los mapas de salidas usan `aire_admosferico_camara` / `buzer_alarma` (`status.py:60,69`), mientras que el YAML dice `aire_atmosferico_camara` / `buzzer_alarma`.

## 3. Rangos válidos definidos

| Fuente | Temperatura | Presión | ¿Se aplica? |
|---|---|---|---|
| `calibration.yaml` factory | `temp_min/temp_max` 0–200 °C; ventana ADC por canal (p. ej. 20–4000) | `pres_min/pres_max` 2–400 (canal 0) o 0–400 kPa | **No como límite.** Solo define la recta de conversión. Un ADC fuera de `adc_min..adc_max` se extrapola y no se rechaza (`converters.py:124`). |
| `hal/measures/units.py` | No define rango | No define rango | — |
| `converters.py` | Rechaza solo el ADC `0` o `≥4095` → `None` (`:170`) | Solo recorta a `≥0.0` (`:228`); sin detección de desconexión | Sí |
| `config/schema.py` | No hay campos de límite | No hay campos de límite | — |
| `models/*.yaml` `limits` | 0–200 °C | 1–400 kPa | **No** (archivo sin uso) |
| Escala por defecto si falta la calibración de fábrica | `raw/4095×200` (`converters.py:129`) | `raw/4095×400` | Sí |

Conclusión: **no existe hoy ningún rango de plausibilidad de ingeniería** (p. ej. "temp_camara debe estar entre −10 y 160 °C") aplicado a la lectura convertida. Los únicos umbrales son los de proceso de cada fase (sección 5).

## 4. Detección de circuito abierto, cortocircuito y fuera de rango

| Mecanismo | Dónde | Qué detecta | Qué hace / alarma |
|---|---|---|---|
| ADC en los extremos (temperatura) | `hal/measures/converters.py:169-174` | `raw == 0` (corto a GND) o `raw >= 4095` (abierto / VCC), sin distinguir uno del otro | Devuelve `None`, reinicia los filtros. No genera alarma por sí solo. |
| ADC en los extremos (presión) | — | **Nada.** Un transmisor abierto (0 V o 4 mA perdido) da `raw≈0` → valor negativo → recortado a `0.0`. Un corto a VCC da `raw=4095` → ~400 kPa (×gain/offset de usuario ≈ 470 kPa). | No hay `None` para presión. |
| `SENSOR_AUSENTE` | `state_machine/states/ciclo.py:439-457`, críticos en `:32-33` | `temp_camara is None` o `pres_camara is None` durante CICLO | Alarma **EMERGENCIA** `SENSOR_AUSENTE`, no recuperable → `ProtocoloFallo` → FALLO. En la práctica solo la dispara `temp_camara`, porque la presión nunca es `None`. |
| `ERROR_AI_<SENSOR>` en PREPARACION | `state_machine/states/preparacion.py:102-141` (llamado en `:80`) | Valor **igual a 0** en los 4 de presión y los 6 de temperatura | Alarma ALERTA bloqueante `ERROR_AI_PRES_CAMARA`, etc.; `supervisor()` devuelve False. |
| `ERROR_AI_<SENSOR>` en PREPARADO | `state_machine/states/preparado.py:246-262` (llamado en `:70`) | Igual, sobre todos los elementos de `sensores_pres` / `sensores_temp` | ALERTA bloqueante. |
| Pérdida de comunicación | `protocols/serial_link.py:209-216` (`DATA_TIMEOUT=3.0 s`) + `services/domain/loop/control_loop.py:96-131` | 3 s sin líneas → desconexión | `NO_HAY_CONEXION` (FALLA, bloqueante) de inmediato; si dura ≥5 s (`_TOLERANCIA_DESCONEXION_SEG`, `control_loop.py:37`) en CICLO → `abortar_por_desconexion()` → `FALLO_CONEXION` (EMERGENCIA) (`ciclo.py:528-548`). |
| Empaque de puerta bajo | `ciclo.py:130-150` | `pres_empaque_N < 0.6×presion_empaque` | `FALLO_PUERTA_N_EMPAQUE` (FALLA). Si el valor es `None` se omite (nunca ocurre para presión). |

### 4.1 Huecos detectados (por lectura)

1. **`ERROR_AI_*` nunca detecta una termocupla/RTD abierta.** Un canal abierto produce `None`, y `None == 0` es False, así que la alarma se limpia en vez de dispararse. Un `0.0` de temperatura convertida es posible pero muy improbable. En temperatura, la verificación es casi inoperante.
2. **En presión, `== 0` sí atrapa el transmisor abierto (por el recorte a 0.0), pero confunde vacío real con falla.** Un vacío profundo que el filtro redondee a 0.0 levanta `ERROR_AI_PRES_CAMARA`; afecta solo a PREPARACION/PREPARADO, donde la cámara está cerca de la presión atmosférica, así que el riesgo es bajo. Un corto a VCC (~400+ kPa) no se detecta en ningún estado.
3. **`temp_drenaje = None` en PREPARACION/PREPARADO probablemente lanza `TypeError`.** `evaluar_banda()` (`control_banda.py:12-27`) compara `None < float` sin protección; se llama desde `preparacion.py:262-266` y `preparado.py:169-173`, y como el supervisor no frena con `None`, el ejecutor sí corre. La excepción la captura `ControlLoop.run()` (`control_loop.py:85-89`), que solo registra un warning; el resto de ese tick (F0, `cycle_logger`, **buzzer**) no se ejecuta, y eso se repite cada tick. Lo mismo vale para `preparado.py:94` si `pres_chaqueta` fuera `None` (hoy no ocurre).
4. **En el hilo serial, una línea `AI:` con un valor no numérico mata el hilo de lectura.** `int(v)` lanza `ValueError` en `serial_link.py:226`, y `_read_loop` solo captura `SerialException` (`:188`). Al morir el hilo, nadie vuelve a llamar `_check_timeout()`; `data_alive` queda en True y `last_update` congelado, así que el ControlLoop seguiría operando con **los últimos valores, sin detectar la caída**. No hay checksum en la trama.
5. `_check_timeout` usa `datetime.now()` (reloj de pared, `serial_link.py:214`), contra la convención de `time.monotonic()` de CLAUDE.md: un ajuste de hora puede provocar una desconexión espuria o retrasar la detección.
6. **Ningún canal tiene detección de valor congelado ni de tasa de cambio imposible.**
7. Nota sobre el "riesgo aceptado" de ESTERILIZACION en CLAUDE.md (sensor `None` → EN_CURSO indefinido): para `temp_camara` está cubierto en la práctica, porque `ciclo.py:439` falla antes de llamar a la fase. Para `pres_camara` el riesgo no es `None` sino una lectura de `0.0` o saturada que se toma como válida; con 0.0, ESTERILIZACION terminaría en `FALLO_PRES_BAJA` y no quedaría colgada.

## 5. Canales que usa la máquina de estados para decidir transiciones

### 5.1 Estado global CICLO (`state_machine/states/ciclo.py`)

| Canal | Uso | Efecto |
|---|---|---|
| `paro_emergencia` (DI 10) → flag `PARO_EMERGENCIA` | `:391` | FALLO (EMERGENCIA) |
| `suministro_electrico` (DI 13) → flag | `:406` | FALLO (EMERGENCIA) |
| `puerta_1_cerrada`, `puerta_2_cerrada` (DI 2, 4) | `:139-144` | `FALLO_PUERTA_N_ABIERTA` |
| `pres_empaque_1/2` | `:146-148` | `FALLO_PUERTA_N_EMPAQUE` |
| `temp_camara`, `pres_camara` | `:439-457` | `SENSOR_AUSENTE` |
| `pres_chaqueta`, `vapor_suministro` | `_mantener_chaqueta` `:152-181` | Solo actuador y alerta; no cambia de fase |
| `temp_drenaje` | `_mantener_drenaje` `:183-219` | Solo actuador y alerta `TEMP_DRENAJE_ALTA` |
| `temp_camara`, `pres_camara` | apertura automática `:269-297` | Habilita la confirmación automática al terminar |

### 5.2 Fases del ciclo (`state_machine/cycle_phases/`)

| Fase | Canales que deciden COMPLETADO / FALLO |
|---|---|
| PRECALENTAMIENTO | `pres_chaqueta` (alcanza el objetivo y sostiene; timeout → FALLO) |
| PREVACIO | `pres_camara` (umbrales de pulso alto/bajo; timeouts → FALLO) |
| CALENTAMIENTO | `temp_camara` y `pres_camara` (rampa, ventana de estabilidad, timeout / recuperación → FALLO) |
| ESTERILIZACION | `temp_camara` y `pres_camara` (4 fallas con debounce; timer como éxito; F0 opcional) |
| DESCOMPRESION | `pres_camara` (vuelta a atmosférica / cambio de etapa), `temp_camara` (`descompresion.py:180`, temperatura objetivo) |
| SECADO | `pres_camara` (pulsos con timeout → FALLO), `pres_chaqueta` (solo mantenimiento) |
| ProtocoloFallo | `pres_camara`, `temp_camara` (gestión posterior al fallo) |

`temp_2_camara` **no decide ninguna transición**: solo entra en el cálculo de F0 (`control_loop.py:224-226`, si `has_liquid_sensor`), que a su vez es condición de éxito de ESTERILIZACION con `F0=true`. `temp_ref`, `temp_chaqueta` y `temp_drenaje_cam` no se usan en la lógica de control (solo pasan por `ERROR_AI_*` y la UI).

### 5.3 Estados PREPARACION / PREPARADO (gate de "listo")

Canales que deciden: `paro_emergencia`, `agua_bomba`, `agua_generador`, `aire_comprimido`, `suministro_electrico`, `vapor_suministro`, `pres_chaqueta` (banda), `pres_camara` (cerca de la atmosférica), `agua_camara` (drenaje), `temp_drenaje` (techo), `puerta_1_cerrada` y `puerta_2_cerrada` (PREPARADO `:208-209`), además de todos los AI vía `ERROR_AI_*`.

## 6. Funciones que dependen de la base de datos

Hay una sola base, SQLite `<app_root>/data/autoclave.db`, abierta por **tres clases independientes** (cada una con su propia conexión) y desde **dos procesos** (backend y UI PySide/QML).

| Función | Tabla(s) | Quién accede | Archivo | ¿Qué pasa si la BD falla? |
|---|---|---|---|---|
| Arranque del backend | todas (crea el esquema, migra, siembra el admin) | `DbManager()` en `BackendContext` | `backend/context.py:74-75`, `db_manager.py:123-134` | **El backend no arranca**: ni ControlLoop ni control del equipo. |
| Registro de ciclo (encabezado, número, cierre, motivo) | `ciclos` | `CycleLogger._on_inicio/_on_fin` | `cycle_logger.py:198-234`, `:258-290` | `crear_ciclo` / `cerrar_ciclo` / `insertar_lectura` **no están protegidos**: la excepción sube a `ControlLoop.run()`, que se salta el paso 7 (buzzer) en ese tick. En el inicio, `_activo` no queda en True y se reintenta en **cada tick** → el buzzer queda mudo durante todo el ciclo mientras la BD siga fallando (por lectura). El ciclo en sí sigue, porque la máquina de estados corre antes. |
| Lecturas del ticket / registro | `lecturas` | `CycleLogger._registrar_lectura` | `cycle_logger.py:371-400` | Igual que la fila anterior (sin protección). |
| Gráfica y tramos de fase en pantalla | `lecturas_grafica`, `ciclo_fases` | `CycleLogger` vía `_guardar()` | `cycle_logger.py:326-332` | Protegido: solo un warning. |
| Historial de ciclos, reimpresión de tickets, resumen del día | `ciclos`, `lecturas`, `lecturas_grafica`, `ciclo_fases` | Endpoints `/cycle/history*`, `/cycle/summary`, `/cycle/current/readings`, `/cycle/current/graph`, `/cycle/current/progress` | `backend/server.py:235-455` | HTTP 500 en esa consulta. |
| Duraciones de referencia (tiempo restante estimado) | `ciclo_fases` | `/cycle/current/progress` | `server.py:273-304`, `db_manager.py:363` | Sin estimación de restante. |
| Login (PySide y QML) | `usuarios` | `DbManager()` creado **en el proceso de la UI** | `ui_pyside/views/login.py:235-236`, `ui_qml/controllers/login_controller.py:26-28,74` | Nadie puede iniciar sesión. |
| Alta de usuarios + auditoría de creación | `usuarios` (`creado_por`, `creado_en`, `codigo_creacion`) | UI | `ui_pyside/views/nuevo_usuario/puente.py:31,89,103` | No se crean usuarios. |
| Vista de ciclos (PySide) | `ciclos`, `lecturas` | `DbManager()` en la UI | `ui_pyside/views/ciclos.py:234` | La vista no carga. |
| Auditoría de calibración de sensores | `sensor_calibration_audit` | `SensorCalibrationAuditDB` (backend) | `sensor_calibration_audit.py`, `server.py:50,95-98` | **La calibración se escribe en el YAML, se hace commit en git y se recarga (`server.py:88-93`) _antes_ de auditar**: si la auditoría falla, la calibración nueva queda activa sin registro y el cliente recibe un error. La lectura de la calibración (GET) también falla. |
| Auditoría de cambios de parámetros de ciclo | `cycle_params_audit` | `CycleParamsAuditDB` en la UI PySide | `ui_pyside/views/params_ciclo/params_ciclo.py:29,366` | La pantalla de parámetros falla al abrir o al guardar. |
| Bridges QML (info del equipo, resumen, progreso) | indirecto vía HTTP | `ui_qml/bridge/info_equipo.py`, `resumen_sistema.py`, `progreso_ciclo.py` | — | Sin datos en esos paneles. |
| Simulador | lee `autoclave.db` en modo URI | `simulador/repeticion.py:42` | — | Solo herramienta de prueba. |

**No dependen de la BD:** las alarmas (`AlarmManager` vive en memoria, `state_machine/alarms/alarm_manager.py`), la calibración activa (YAML), los perfiles de ciclo (JSON), los parámetros globales (`global_params.json`), F0 (memoria) y la impresión en tiempo real (cola propia).

### 6.1 Puntos relevantes para decidir el punto 2

- El acoplamiento más fuerte es el **arranque**: si `autoclave.db` no se puede abrir o está corrupta, todo el backend cae, incluido el control. Es el único caso en que una falla de la BD impide operar el equipo.
- El segundo es el del **CycleLogger sin protección dentro del tick del ControlLoop**: no detiene el ciclo, pero apaga el buzzer y se pierde el registro del ciclo (ticket y trazabilidad) sin que el operador lo vea.
- Login y alta de usuarios abren su propia conexión **desde la UI**, sin pasar por el backend: la BD queda accedida desde dos procesos a la vez (SQLite lo tolera, pero es un factor que hay que tener en cuenta al decidir dónde vive y quién la custodia).
- La auditoría de calibración no es atómica con el cambio que registra.
