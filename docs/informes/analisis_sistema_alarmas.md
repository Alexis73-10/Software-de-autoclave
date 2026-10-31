# Análisis del sistema de alarmas actual

Fecha: 2026-10-06. Solo lectura: no se modificó código. Sirve de base para el rediseño del sistema de alarmas.

## 1. Cómo funciona hoy

El modelo es `Alarm` (`state_machine/alarms/alarm.py`) y tiene 6 campos: `id`, `type` (ALERTA / FALLA / EMERGENCIA), `source_state`, `description`, `recoverable` y `blocks_operation`. `AlarmManager` guarda la lista en memoria (`estado.Alarmas_activas`) y descarta un reporte si ya hay otra alarma activa con el mismo `id`.

`backend/server.py` publica `id`, `level`, `description` y `source_state`. En QML, `FilaAlarma.qml` muestra la descripción, o el `id` si la descripción viene vacía, con un color según la prioridad (EMERGENCIA alta, FALLA media, ALERTA baja).

Además existe `estado.motivo_fallo`, un texto libre que se guarda en la tabla `ciclos` y se imprime en el ticket del ciclo.

## 2. Problemas estructurales

| # | Problema | Dónde | Efecto visible |
|---|---|---|---|
| E1 | No hay título legible: el `id` hace de nombre | todo | La pantalla muestra `FALLO_PREVACIO`, `ERROR_AI_PRES_EMPAQUE_1` y similares |
| E2 | Las descripciones son genéricas y se arman con el `id` | `preparado.py:36` ("Error CHAQUETA_FRIA en estado PREPARADO"), `preparacion.py:56` ("Alerta: X en PREPARACION.") | El texto no explica nada |
| E3 | Un fallo de fase usa un solo `id` por fase (`FALLO_<FASE>`) | `ciclo.py:506` | No se distingue un timeout de vacío de uno de presión alta |
| E4 | 4 de las 6 fases no dejan motivo | precalentamiento, prevacío, descompresión, secado | El motivo cae al genérico "Fallo en la fase prevacio." y la causa solo queda en el log |
| E5 | No hay valores medidos ni umbrales | todo, salvo ESTERILIZACION | No se sabe cuánto marcaba el sensor ni contra qué límite se comparó |
| E6 | No hay sello de tiempo de aparición ni de despeje | `Alarm` | No se sabe cuándo ocurrió ni cuánto duró |
| E7 | No hay historial persistente | `AlarmManager` en memoria | La salida de FALLA hace `Alarmas_activas.clear()` (`state_machine.py:122`) y se pierde todo. Solo sobrevive `motivo_fallo` del ciclo |
| E8 | No hay reconocimiento (ack) del operador | todo | Ya existe `ui_qml/domain/alarmas.py` con 4 severidades y ack, pero no está conectado al backend |
| E9 | La deduplicación por `id` congela la primera descripción | `alarm_manager.py:17` | Si la condición empeora, el texto no se actualiza |
| E10 | Los sensores se nombran con la clave interna | `ciclo.py:450` | "Sensor crítico ausente: temp_camara, pres_camara" |
| E11 | `source_state` es inconsistente | varios | Mezcla estados (CICLO, PREPARADO), módulos (PUERTA, CONTROL_LOOP) y nunca dice qué puerta, fase o sensor |
| E12 | Un sensor solo da error si la lectura es exactamente `0` | `preparado.py:250`, `preparacion.py:122` | No detecta sensor abierto, en corto, fuera de rango ni congelado. Además usa `[]` y no `.get()`, así que una clave ausente lanza KeyError |

## 3. Inventario de alarmas existentes

| ID actual | Nivel | Origen | Texto que se ve hoy |
|---|---|---|---|
| PARO_EMERGENCIA | EMERGENCIA | todos los estados | Varía según el estado |
| FALLO_SUMINISTRO_ELECTRICO | EMERGENCIA | ciclo | "Pérdida de suministro eléctrico durante el ciclo." |
| SUMINISTRO_ELECTRICO | ALERTA | preparado | "Error SUMINISTRO_ELECTRICO en estado PREPARADO" |
| SUMINISTRO_AGUA_BOMBA / _AGUA_GENERADOR / _AIRE_COMPRIMIDO | ALERTA | preparación / preparado | Genérico con el id |
| SUMINISTRO_VAPOR | ALERTA, no bloquea | preparación / preparado / ciclo | Aceptable en ciclo, genérico en los demás |
| CHAQUETA_FRIA / CHAQUETA_SOBRECALENTADA | ALERTA | preparación / preparado | Genérico, sin presión medida ni objetivo |
| PRESION_CAMARA_BAJA / _ALTA | ALERTA | preparación / preparado | Genérico |
| AGUA_RESIDUAL_CAMARA | ALERTA | preparación | Genérico |
| TEMP_DRENAJE_ALTA | ALERTA | preparación / preparado / ciclo | Sin la temperatura medida |
| PUERTA_1_ABIERTA / PUERTA_2_ABIERTA | ALERTA | preparado | Genérico |
| ERROR_AI_<SENSOR> | ALERTA | preparación / preparado | Genérico, con la clave interna del sensor |
| FALLO_PUERTA_<n>_ABIERTA / FALLO_PUERTA_<n>_EMPAQUE | FALLA | ciclo | "Fallo de seguridad: fallo puerta 1 empaque.", sin la presión de empaque ni el mínimo exigido |
| SENSOR_AUSENTE | EMERGENCIA | ciclo | Lista de claves internas |
| FALLO_<FASE> | FALLA | ciclo | Solo CALENTAMIENTO y ESTERILIZACION dan un motivo concreto |
| FALLO_CONEXION | EMERGENCIA | ciclo | "Se perdió la comunicación con el hardware durante el ciclo." |
| NO_HAY_CONEXION | FALLA | control loop | "No hay comunicación con el hardware." |
| ABRIENDO_MODO_SEGURO_<puerta> / CERRANDO_MODO_SEGURO_<puerta> | ALERTA | puerta | Aceptable |
| TIMEOUT_APERTURA_AUTOMATICA / APERTURA_AUTOMATICA_DENEGADA | ALERTA | ciclo | Aceptable |

## 4. Alarmas que faltan

Todos los casos de esta sección hoy solo se registran en el log o pasan sin aviso. El operador no los ve.

### 4.1 Puertas (`devices/puertas/advanced_door.py`)

La puerta pasa a `ERROR` o `ATRAPADA` sin reportar ninguna alarma. Por eso hoy solo se ve "fallo en puerta", sin el motivo.

| Caso | Línea | Lo que debería decir |
|---|---|---|
| Timeout de apertura | 422 | Puerta N no abrió en X s. Debe distinguir si el empaque no llegó a vacío (Y kPa contra el umbral) o si el final de carrera de abierta nunca se activó |
| Timeout de cierre | 511 | Puerta N no cerró en X s. Debe distinguir si no llegó el final de carrera de cerrada o si el empaque no presurizó (Y kPa contra el mínimo) |
| Atrapamiento | 487 | Atrapamiento detectado en puerta N; se reabre automáticamente |
| Sensores incoherentes (abierta y cerrada a la vez, o ninguno de los dos) | 345 (estado inicial), 433, 437, 443, 571 | Puerta N con finales de carrera incoherentes: revisar sensores |
| Puerta perdió su posición estando cerrada o abierta | 433, 443 | Puerta N dejó de detectarse cerrada sin que nadie lo ordenara |
| Re-presurización del empaque en reposo | 451 | Aviso si se repite o se sostiene: posible fuga en el empaque |
| Apertura denegada por bloqueo mecánico | 595 | Hoy se ignora en silencio |
| Puerta en ERROR que no se recupera | `_from_error` | Alarma persistente hasta que se resuelva |

Nota aparte: los temporizadores de puerta usan `time.time()` (líneas 342, 366, 422, 456, 511, 562). Eso viola la convención de `CLAUDE.md`, que exige `time.monotonic()`.

### 4.2 Fases del ciclo

| Fase | Caso | Información que debería llevar la alarma |
|---|---|---|
| Precalentamiento | Timeout (`precalentamiento.py:57`) | Presión objetivo de chaqueta, la presión alcanzada y el tiempo |
| Prevacío | Timeout de vacío bajo (`:139`) | Tipo y número de pulso, presión objetivo y presión alcanzada |
| Prevacío | Timeout de presión alta (`:187`) | Lo mismo |
| Calentamiento | Timeout y falta de estabilidad (ya tienen texto) | Agregar la temperatura y la presión al momento del fallo |
| Descompresión | Timeout del modo N (`:58`), modo desconocido (`:73`) | Presión de la cámara y el tiempo |
| Secado | Timeout en VACIO_BAJO / AIRE_ALTO (`:111`, `:128`), modo desconocido (`:51`) | Pulso, presión y umbral |
| Protocolo de fallo | Escalado por timeout de descompresión (`protocolo_fallo.py:176`) | Hoy solo va al log; el operador debería saber que se está forzando la descompresión |
| Esterilización | Entrada en RECUPERACION | Posible aviso informativo de desviación, sin falla |

### 4.3 Comunicación y hardware

| Caso | Dónde | Comentario |
|---|---|---|
| ALL_OFF sin confirmación del ESP32 | `set_io.py:180`, `serial_link.py:460` | Crítico: no hay certeza de que las salidas quedaron apagadas. Hoy solo va al log |
| Enlace degradado (CRC inválidos o líneas malformadas repetidas) | `serial_link.py:323, 359` | Ya existe `get_diagnostico()`, pero nada lo convierte en aviso |
| Puerto serial no encontrado / error al abrir el puerto | `serial_link.py:163` | Hoy solo aparece el genérico NO_HAY_CONEXION |
| Error de escritura en el puerto | `serial_link.py:433` | Solo va al log |
| Excepción inesperada en el tick del ControlLoop | `control_loop.py:89` | Solo un `warning`. Si se repite, el control queda sin actuar y nadie se entera |
| Bomba de vacío bloqueada por fallo eléctrico | `pump.py:18` | Solo va al log |
| Impresora no disponible | impresión en tiempo real | Hoy encola sin avisar |
| Base de datos no disponible / error de escritura | `db_manager.py` | Relacionado con `planeacion_arranque_y_modo_sin_bd.md` |

### 4.4 Sensores

Faltan estas detecciones:
- Lectura `None` (sensor ausente) fuera del estado CICLO.
- Lectura fuera del rango físico (sensor abierto o en corto).
- Sensor congelado (el mismo valor durante mucho tiempo con actuadores activos).
- Discrepancia entre `temp_camara` y `temp_2_camara` / `temp_ref`.

En todos los casos los sensores deben aparecer con su nombre legible ("Temperatura de cámara"), no con la clave interna.

### 4.5 Suministros y estados

- Las alarmas de suministro existen, pero sus textos son genéricos.
- La cancelación por el operador no se registra como evento ("quién y en qué fase").
- El estado FALLA no tiene una alarma que resuma la causa raíz después de limpiar las demás.

## 5. Decisiones abiertas para el rediseño

1. Catálogo central de alarmas (código → título, descripción con plantilla, nivel, acción sugerida) frente a textos dispersos en cada módulo.
2. Cómo mapear los 3 niveles del backend a las 4 severidades de `ui_qml/domain/alarmas.py`.
3. Reconocimiento (ack) por el operador: qué niveles lo exigen y dónde se guarda.
4. Historial persistente en BD (aparición, despeje, ack, valores). Se conecta con Reportes parte 3, "alarmas".
5. Orden de trabajo: infraestructura → cobertura por área → interfaz.
6. Este rediseño toca `alarm_manager`, puertas y `ControlLoop`: requiere revisión con `safety-reviewer`.
