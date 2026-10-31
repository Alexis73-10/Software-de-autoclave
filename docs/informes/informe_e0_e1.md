# Informe — Etapas E0 y E1 (fin de ciclo y puertas manuales)

**Fecha:** 2026-10-12 · **Rama:** `dev` · **Sin commit:** Cristian confirma visualmente antes.
**Instrucción:** `docs/mis_plans/instruccion_claude_code_e0_e1.md` · **Spec:** `docs/mis_plans/planeacion_fin_de_ciclo_y_puertas.md` (v3)
**Solicitudes de cambio:** CR-FC-01 (E0) y CR-FC-02 (E1). Clase C. SOUP sin cambios. No se tocaron `docs/catalogo_alarmas.md` ni los demás cambios ajenos del árbol.

---

## 1. Archivos modificados

### Código

| Archivo | Cambio |
|---|---|
| `src/autoclave/core/runtime/lectura.py` (nuevo) | `lectura_valida(valor)`: False para `None`, NaN, ±inf y no numéricos (E0-1). |
| `src/autoclave/state_machine/states/preparacion.py` | Temperatura `None`/no finita = `ERROR_AI_<SENSOR>` igual que un 0 (E0-1). |
| ″ | `pres_chaqueta`, `pres_camara` y `temp_drenaje` sin dato: sin órdenes de válvula y no listo, sin excepción (E0-2, E0-3). `ejecutor()` no ordena la descompresión rápida si la presión de cámara no tiene dato. |
| ″ | Recibe `profile`; omite las entradas de suministro declaradas "no aplica" y, con vapor sin presostato, controla la chaqueta solo por presión (E1-1). |
| ″ | Revisa empaque solo de las puertas declaradas y nunca con `door_type=simple` (E1-2). |
| ″ | Usa el flag `PARO_EMERGENCIA` en vez del DI crudo; la alarma lleva el aviso de cableado NC (E1-5). |
| `src/autoclave/state_machine/states/preparado.py` | Mismo trato de lecturas inválidas que PREPARACION (E0). `esta_preparado()` ya no lanza con `temp_drenaje=None`. |
| ″ | Recibe `profile`: omite suministros "no aplica" (incluido el eléctrico en `verificar_suministros()` y en `esta_preparado()`); vapor sin presostato = control solo por presión (E1-1). |
| ″ | `puertas_cerradas()` itera `door_count`; `verificar_sensores()` omite los empaques que no aplican (E1-2). Aviso NC en la alarma de paro (E1-5). |
| `src/autoclave/state_machine/states/ciclo.py` | Recibe `profile`. `_mantener_chaqueta()` sin OFF forzado ni `SUMINISTRO_VAPOR` si el vapor no aplica (E1-1). |
| ″ | `_verificar_puertas()` itera `door_count` y sin empaque para `simple` (E1-2). |
| ″ | `_mantener_apertura_automatica()` sale en silencio si la puerta de descarga no tiene actuador (E1-4). Aviso NC en la alarma de paro (E1-5). |
| `src/autoclave/state_machine/state_machine.py` | Pasa `profile` a PREPARACION, PREPARADO y CICLO. |
| `src/autoclave/state_machine/states/falla.py`, `hibernacion.py` | Aviso de cableado NC en la descripción de `PARO_EMERGENCIA` (E1-5). |
| `src/autoclave/services/domain/loop/control_loop.py` | Recibe `profile` y lo pasa a la máquina de estados (también en `set_active_cycle`). No llama a `SuministroElectrico.update()` si la entrada no aplica (E1-1). Pasa el DI crudo del paro (E1-5). |
| `src/autoclave/devices/paro_emergencia/paro_emergencia.py` | Lógica invertida: paro = entrada en 0 o `None`; sin datos al construirse = paro. Constante `AVISO_CABLEADO_NC` (E1-5). |
| `src/autoclave/devices/puertas/simple_door.py` | Lectura `None`/ausente = `DoorState.ABIERTO` (E1-3). |
| `src/autoclave/devices/puertas/door_factory.py` | `tipo_tiene_actuador(door_type)` (E1-4). |
| `src/autoclave/installation/profile.py` | Campo `supply_inputs` (defecto: las cinco en True), validación (solo claves conocidas y booleanas), `entrada_requerida()`, `entradas_no_monitoreadas()`, `numero_puertas()`, `revisa_empaque()`, `sensores_empaque()`. |
| `src/autoclave/installation/storage.py` | Lee y guarda `supply_inputs` (campo ausente = todas True). |
| `src/autoclave/installation/wizard.py` | Paso 5: cinco casillas "Entradas de suministro cableadas" (marcadas por defecto). |
| `src/autoclave/backend/context.py` | `logger.warning` al arrancar con la lista de entradas no monitoreadas; pasa `profile` al ControlLoop. |
| `src/autoclave/backend/server.py` | `/status` agrega `entradas_no_monitoreadas`. |
| `src/autoclave/simulador/servidor.py` | `/status` agrega `entradas_no_monitoreadas: []` (mismo contrato). El simulador no modela DI ni el paro: no había nada que invertir. |
| `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py` | Oculta `finalizacion.apertura_automatica` si la puerta no tiene actuador (E1-4). |
| `tools/declarar_entradas_suministro.py` (nuevo) | Herramienta del ingeniero para declarar `supply_inputs` en el perfil (§4). |

### Pruebas existentes actualizadas

| Archivo | Cambio |
|---|---|
| `tests/test_control_loop_test_mode.py` | DI del paro: 1 = sin paro, 0 = paro; el ayudante simula la primera trama. |
| `tests/test_control_loop_f0.py` | El doble de estado acepta `set_flag` (EmergencyStop publica el paro al construirse). |
| `tests/test_control_loop_set_active_cycle.py` | La llamada esperada a `StateMachine(...)` incluye `profile=`. |
| `tests/test_preparacion_ejecutor_paralelo.py` | El paro se simula con el flag. Antes pasaba "por accidente": `get_flag` de un MagicMock siempre es verdadero. |

## 2. Pruebas

Comando: `python -m pytest -q -p no:cacheprovider`

| | Resultado |
|---|---|
| Antes (línea base) | **2236 passed**, 6 warnings |
| Después | **2440 passed**, 6 warnings (las mismas advertencias de `datetime.utcnow()` que antes) |

Pruebas nuevas (204), por requisito:

| Requisito | Archivo | N.º |
|---|---|---|
| E0-1, E0-2, E0-3 | `test_e0_lecturas_invalidas.py` | 54 |
| E1-1 perfil, estados, combinaciones de `supply_inputs` (32 + campo ausente, en PREPARACION y PREPARADO), PRECALENTAMIENTO | `test_e1_supply_inputs.py` | 89 |
| E1-1 ControlLoop, `/status`, aviso de arranque | `test_e1_supply_inputs_loop_status.py` | 8 |
| E1-1 herramienta de instalación | `test_declarar_entradas_suministro.py` | 3 |
| E1-2 una y dos puertas, `simple` / `advanced` | `test_e1_puertas_perfil.py` | 21 |
| E1-3 puerta `None` = abierta | `test_e1_simple_door_lectura_invalida.py` | 3 |
| E1-4 apertura automática sin actuador | `test_e1_apertura_automatica_sin_actuador.py` | 9 |
| E1-5 paro con 0, con 1 y sin datos | `test_e1_paro_emergencia_nc.py` | 15 |
| E1 integración: `simple`, sin empaque y solo aire → CICLO | `test_e1_integracion_inicio_ciclo.py` | 2 |

Cada prueba se vio fallar antes del cambio. Hay dos excepciones: las 3 de la herramienta, escritas después de ella, y las de E1-2, cuyo fallo inicial fue de importación porque las funciones aún no existían.

## 3. Respuestas pedidas

### E0-2 — ¿Qué hace `CicloState._mantener_drenaje()` ante `None`?

`ciclo.py:247-249`: si `temp_drenaje` es `None`, **retorna sin hacer nada**. No emite orden de válvula (`agua_intercambiador` queda como estaba), no genera ni limpia alarmas y **no reinicia los contadores de debounce en curso** ("solo salta el tick").

Comportamiento copiado en PREPARACION y PREPARADO: sin orden de válvula y sin tocar el confirmador de apagado (hay una prueba de que el conteo en curso sigue). A eso se suma lo que pide la instrucción:
- la alarma de sensor `ERROR_AI_TEMP_DRENAJE` sale de `verificar_sensores()`;
- el método devuelve False, así que el equipo no queda listo;
- `esta_preparado()` ya no falla.

### E0-4 — Opciones para que una excepción en la máquina de estados no impida F0, el registro ni el buzzer

No se cambió `ControlLoop.run()`. Hoy una excepción en `state_machine.update()` corta el resto de `_tick()` (F0, registro de ciclo y buzzer). Además se registra con `logger.warning`, sin traceback.

1. **`try/except` alrededor de `state_machine.update()` dentro de `_tick()`**, de modo que los pasos 5b a 7 sigan corriendo. Es el cambio más acotado.
2. **`try/finally` en `_tick()`**: F0, registro y buzzer en el `finally`. Corren siempre, pero mezclan su propio fallo con el original.
3. **Etapas aisladas**: cada paso del tick (publicar estado, paro, puertas, servicios, máquina, F0, registro, buzzer) con su propio `try/except`, `logger.exception` y un contador por etapa.
4. **Escalado de seguridad** (complemento de 1 o 3): si la máquina lanza N ticks seguidos estando en CICLO, abortar como `abortar_por_desconexion()` (protocolo de fallo y alarma con id nuevo, que debe pasar por el catálogo de alarmas). Fuera de CICLO, `reset_all_outputs()`.

**Recomendación:** 1 + 4, y cambiar `logger.warning` por `logger.exception`. La opción 1 sola mantendría vivos el buzzer y el registro mientras el control está caído, lo que podría ocultar el problema. Por eso hace falta el escalado. La alarma nueva espera a la Parte A del catálogo.

### E1-3 — Estado de error o desconocido en `DoorState`

`DoorState` (`devices/puertas/enum_doors.py`) tiene **`DESCONOCIDO`** (valor inicial de `EstadoAutoclave.estado_puertas`) y **`ERROR`**. **No se usó ninguno.** Se aplicó lo pedido: lectura inválida = `ABIERTO`.

Propuesta: mantener `ABIERTO` como posición para la lógica de seguridad. Si se quiere que la UI distinga "sensor de puerta sin dato", usar `ERROR` solo después de revisar cada consumidor. Hoy `ser_puertas`, la apertura automática (`"ABRIENDO"`/`"ABIERTO"`) y la UI comparan contra nombres concretos, y un estado nuevo podría tomarse como "no abierta" en algún punto.

En la práctica el DI de puerta nunca vale `None`: los DI son enteros. Solo falta la clave si se pierde del mapa.

### E1-5 — Lugares que leen el DI del paro

| Lugar | Antes | Ahora |
|---|---|---|
| `services/domain/loop/control_loop.py:188-189` | `bool(sensores_di.get("paro_emergencia", 0))` → 1 = paro | Pasa el valor crudo; `EmergencyStop` decide: 0 o `None` = paro |
| `state_machine/states/preparacion.py:63` | DI crudo | Flag `PARO_EMERGENCIA` |
| `core/runtime/status.py:42` | Índice 10 del mapa de DI | Sin cambio |
| `backend/server.py:1060, 1109, 1394` | Solo usan `"paro_emergencia"` como código de rechazo (leen el flag) | Sin cambio |
| Simulador (`simulador/servidor.py`) | No modela DI ni el flag de paro | Sin cambio |
| `tests/serial_doble.py` (`DI_OK` = 56 ceros) | Solo lo usa la prueba del lector serial; no pasa por `EmergencyStop` | Sin cambio |

**Aviso de cableado (D-16):** con el cableado actual (contacto NO, lee 1 al pulsar), el equipo mostrará **paro de emergencia permanente** hasta que Cristian pase la señal a contacto NC. Es el fallo deseado. El mensaje de la alarma `PARO_EMERGENCIA` lo dice en todos los estados: *"Paro = entrada en 0 o sin datos de la tarjeta. Si el botón no está pulsado, revisar que el cableado sea contacto normalmente cerrado (NC)."*

Efectos colaterales de ese paro permanente:
- **El modo prueba (`/io/test/output`) queda bloqueado** hasta cambiar el cableado: `enter_test_mode()` rechaza con el paro activo.
- Desde el arranque hasta la primera trama con DI, `PARO_EMERGENCIA` vale True. PREPARACION apaga salidas y hace sonar el buzzer de emergencia en esos primeros ticks.
- La pantalla de E/S muestra el DI crudo: ahora `paro_emergencia = 1` significa **sin paro**.

## 4. Procedimiento para declarar `supply_inputs` en este equipo

No se editó `installation_profile.json` (está `locked`). Procedimiento, **con el software cerrado** y desde la raíz del repo (o la carpeta del `.exe`):

```powershell
# 1. Ver el valor actual (sin el campo = todas en True)
python tools/declarar_entradas_suministro.py --mostrar

# 2. Declarar solo aire comprimido cableado (las otras cuatro quedan en False)
python tools/declarar_entradas_suministro.py --cableadas aire_comprimido
```

La herramienta:
- conserva los demás campos del perfil, incluidos `equipment_type` y `drying_type`, que la aplicación no lee;
- deja un respaldo `installation_profile.json.<fecha>.bak`;
- valida antes de escribir y, si el perfil quedaría inválido, no escribe nada.

Resultado esperado:

```json
"supply_inputs": {"agua_bomba": false, "agua_generador": false, "aire_comprimido": true,
                  "vapor_suministro": false, "suministro_electrico": false}
```

Al arrancar, el log mostrará `Entradas de suministro no monitoreadas (perfil de instalación): agua_bomba, agua_generador, vapor_suministro, suministro_electrico`. `/status` traerá la misma lista en `entradas_no_monitoreadas`.

En instalaciones nuevas, el asistente (`wizard.py`, paso 5) muestra las cinco casillas, marcadas por defecto.

**Ojo:** el perfil real de este equipo dice `"door_type": "advanced"` y `"equipment_class": "piso"`. La spec (§6.1, PF-01) dice que es `simple` y piso de laboratorio. Mientras siga en `advanced`, E1-2 no aplica: se siguen exigiendo los sensores de empaque. Ver pregunta 2.

## 5. Qué no se pudo verificar y preguntas pendientes

**No verificado:**
- Nada se probó con la tarjeta real ni con hardware (regla 3).
- No vi en pantalla el asistente de instalación (tkinter) ni la pestaña "Finalización" de Parámetros del ciclo (PySide). Solo están probadas las funciones puras que deciden qué mostrar.
- "Información del sistema": el aviso se escribe con `logger.warning` al arrancar, pero no comprobé que esa pantalla lea ese log.
- Revisión final: la hice yo mismo, sin un revisor independiente. Antes del commit recomiendo pasar los agentes `safety-reviewer` y `timing-auditor` del proyecto: el cambio toca paro, puertas, salidas y ControlLoop.

**Decisiones tomadas sin preguntar** (están en las pruebas; cámbialas si no las compartes):
1. Presión de cámara sin dato: PREPARACION no ordena la descompresión rápida (ni ON ni OFF), aunque el drenaje no la pida.
2. Presión de chaqueta sin dato: "no lista" aunque falte el vapor. Antes, sin vapor, la chaqueta se daba por lista.
3. Con `advanced` y **una** puerta ya no se exige `pres_empaque_2`. Antes lo exigía, aunque ese sensor no existe. Con dos puertas el comportamiento es idéntico.
4. PREPARADO también omite los empaques que no aplican. La instrucción solo nombraba PREPARACION y CICLO, pero sin esto un equipo `simple` no inicia ciclo.
5. Una clave desconocida o un valor no booleano en `supply_inputs` invalida el perfil, y al arrancar se abre el asistente de instalación.
6. Si la UI de parámetros no puede leer el perfil local, muestra `apertura_automatica`. Es inofensivo: CICLO la ignora sin actuador.

**Preguntas:**
1. Los tipos `motorized`, `locking` y `motorized_locking` siguen exigiendo empaque, como hoy, aunque `factory.py` solo define sensor de empaque para `advanced`. ¿Se les quita la revisión?
2. ¿Ampliamos la herramienta para cambiar también `door_type` a `simple` y `equipment_class` a `piso_lab` en este equipo, o lo hace el ingeniero con el asistente (reinstalación)?
3. E0-4: ¿aplicamos la opción 1 + 4 en una etapa siguiente? El escalado necesita un id de alarma nuevo (Parte A del catálogo).
4. E1-3: ¿se queda `ABIERTO` o se audita a los consumidores para usar `DoorState.ERROR`?
5. La pantalla de E/S muestra el DI crudo del paro. ¿Cambiamos su etiqueta para que se lea "1 = sin paro (NC)"?

## 6. Recordatorio

**Sin commit.** Los cambios están en el árbol de trabajo de `dev`, junto a los cambios ajenos, que no se tocaron. Cristian confirma visualmente antes de confirmar.

---

## 7. Revisión de `safety-reviewer` y `timing-auditor` (2026-10-12)

Solo lectura. Ninguno encontró hallazgos Críticos. Ningún identificador de alarma cambió y los cambios en cuándo se disparan corresponden a lo pedido. **No se ha corregido nada todavía.**

### Introducidos o expuestos por E0/E1

| ID | Gravedad | Hallazgo | Propuesta |
|---|---|---|---|
| SAF-01 | Importante | Con `agua_bomba` declarada "no aplica", `VacuumPump.puede_activar()` (`devices/pump/pump.py:21`) sigue exigiendo el DI en 1 y la bomba nunca arranca. Antes el equipo no salía de PREPARACION; ahora inicia ciclos. Con prevacío, el ciclo falla por timeout. Sin prevacío, SECADO modo 1/2 termina por tiempo y el ciclo sale **COMPLETADO sin vacío de secado** (carga húmeda informada como exitosa). Es justo el caso del procedimiento §4. | Que `VacuumPump` respete el perfil, o impedir declarar `agua_bomba` en False con `has_vacuum`. Además, que SECADO compruebe que hubo vacío real. |
| TMG-02 | Importante | Con E0-1, una temperatura `None` hace fallar `supervisor()` y no corre `ejecutor()`: las salidas quedan congeladas. Ejemplo: con `vapor_chaqueta` en ON se cae `temp_ref` y la chaqueta queda sin control de presión. | Si el supervisor falla, llevar a OFF las salidas de control (o dejar correr los lazos que no dependen del sensor caído). |
| SAF-04 / TMG-02 | Menor / Importante | Canales de temperatura sin sonda instalada (`temp_2_camara`, `temp_ref`, `temp_drenaje_cam`) ahora bloquean PREPARACION para siempre. | Filtrar los canales vigilados por perfil o capacidades, igual que el empaque. |
| TMG-01 / SAF-06 | Importante / Menor | "Sin datos = paro" solo se cumple antes de la **primera** trama. Durante una desconexión el flag se queda con su último valor. Al reconectar, `_connect()` no limpia `di` y el primer tick usa un DI viejo. Si la tarjeta sigue mandando `AI:` pero no `DI:`, el paro queda congelado. | Sello monotónico de la última trama `DI:`; si vence → `update(None)`. Poner `di` en 0 al reconectar. Publicar el paro mientras está desconectado. |
| SAF-02 | Importante | `temp_drenaje` sin dato deja `agua_intercambiador` como esté (copiado de CICLO por orden de E0-2). Si PREPARACION descomprime al drenaje con el intercambiador apagado, el vapor sale sin enfriar. | Con lectura inválida, forzar `agua_intercambiador_on()`. Requiere decisión de Cristian, porque cambia lo que pidió E0-2. |
| SAF-03 | Menor | `pres_chaqueta` sin dato: `vapor_chaqueta` queda en su último estado y no sale `ERROR_AI_PRES_*`. En la práctica solo ocurre antes del primer dato. | Forzar `vapor_chaqueta_off()` y emitir `ERROR_AI` también con `None`. |
| SAF-05 | Menor | La herramienta acepta `--cableadas` sin argumentos y declara las cinco entradas en "no aplica". Tampoco deja registro de auditoría. | Rechazar la lista vacía salvo con un flag explícito, pedir confirmación y registrar el cambio. |
| SAF-07 | Menor | `door_count=1` en un equipo de dos puertas deja la puerta 2 sin interlock por software. | Avisar si llega `puerta_2_cerrada`=1 con `door_count=1`. |
| TMG-08 | Menor | Las ramas `None` de drenaje y presión casi no se alcanzan desde `run()`. Las pruebas las ejercitan llamando directo a los métodos. | Tenerlo en cuenta en la evidencia de verificación. |
| TMG-09 | Menor | Con el paro permanente (cableado NO), cada tick manda `ALL_OFF` bajo el lock (espera de ACK de hasta 1 s) y el buzzer da un pulso por tick. El buzzer usa `time.time()`. | `ALL_OFF` solo en el flanco o si hay salidas encendidas; pasar el buzzer a `time.monotonic()`. |
| TMG-11 | Menor | CICLO usa `is None` en vez de `lectura_valida`; el suministro eléctrico usa `get(..., 1)` como valor por defecto. | Unificar el criterio. |

### Preexistentes, no introducidos por E0/E1

| ID | Gravedad | Hallazgo |
|---|---|---|
| TMG-04 | Importante | Con un resultado de ciclo pendiente de confirmar, `CicloState.run()` no evalúa el paro (`ciclo.py:423-447` corre antes de `:459`). Con el paro pulsado se siguen accionando la válvula de reposo, el aire atmosférico y el intercambiador. |
| TMG-05 | Importante | `/io/test/enter` y `/io/test/output` no comprueban `desconectado`: el modo prueba funciona con el enlace caído y con datos viejos. |
| TMG-03 | Importante | E0-4 (excepción en el tick). Ambos revisores apoyan la opción 1 + 4 + `logger.exception`. El auditor de temporización añade: umbral medido con `time.monotonic()`, escalado con respaldo a `reset_all_outputs()`, proteger también los pasos 1-2 y limitar la frecuencia del log. |
| TMG-06 | Menor | PREPARADO llama a `mantener_*` dos veces por tick (en `ejecutor` y en `esta_preparado`). El confirmador de apagado cuenta 2 por tick y las alarmas se reportan dos veces. |
| TMG-07 | Menor | `timer_estabilidad` de PREPARADO se comparte entre alarmas y no se reinicia al limpiarse una: una alarma posterior puede dispararse sin retardo. |
| TMG-10 | Menor | `abortar_por_desconexion()` corre fuera de `_sm_lock`. |

### Preguntas de los revisores para Cristian

1. ¿El paro corta físicamente la potencia de las salidas (cadena de seguridad), o la protección es solo por software? De eso depende la gravedad de TMG-01.
2. ¿El firmware interpreta por su cuenta el DI 10 (paro)?
3. ¿Hay válvula de alivio mecánica en la chaqueta y en la cámara? (SAF-03)
4. ¿Este equipo tiene bomba de vacío y sensor de agua de sello? ¿Sus programas usan prevacío y SECADO modo 1/2? (SAF-01)
5. ¿Qué sondas de temperatura tiene cableadas este equipo? (SAF-04 / TMG-02)
6. Con `agua_generador` en "no aplica", ¿qué protege al generador contra marcha en seco: el software o un control propio?
7. ¿Con qué periodo y en qué orden envía la tarjeta las líneas `AI:`, `DI:` y `DO:`? Define el umbral de vigencia de TMG-01.

---

## 8. Adenda (2026-10-12)

Instrucción: `docs/mis_plans/instruccion_claude_code_e0_e1_adenda.md`. **Sin commit.**

### 8.1 Archivos cambiados

| Archivo | Cambio |
|---|---|
| `devices/pump/pump.py` | A-1: `VacuumPump(estado, profile)`; con `agua_bomba` en "no aplica" no exige el DI. |
| `devices/io/set_io.py` | A-1: pasa `profile` a la bomba. A-7: `apagar_por_paro()` manda ALL_OFF como máximo una vez por segundo, o en cada tick si el último `DO:` tiene una salida activa (el buzzer no cuenta; sin `DO:` se asume que hay alguna activa). |
| `devices/buzer/buzer.py` | A-7: `time.monotonic()`. |
| `installation/profile.py`, `storage.py`, `wizard.py` | A-2: campo `temperature_probes` (por defecto todas presentes), validación (`temp_camara` no puede ser false), casillas en el paso 5 del asistente. |
| `installation/cambio_perfil.py` (nuevo) | A-6: escritura auditada (valida, pide confirmación, deja `.bak` y escribe una línea en `installation_profile_cambios.log`). |
| `tools/declarar_entradas_suministro.py` | A-6: rechaza `--cableadas` vacío salvo con `--permitir-ninguna`; pide confirmación (`--si` la omite); registra el cambio en la auditoría. |
| `tools/declarar_sondas_temperatura.py` (nuevo) | A-2: lo mismo para `temperature_probes`. |
| `state_machine/states/preparacion.py`, `preparado.py` | A-2: no vigilan las sondas no instaladas. Si el supervisor falla por un sensor analógico: vapor de chaqueta y de cámara en OFF, y siguen los lazos de presión de cámara, drenaje y enfriamiento. A-4: drenaje sin lectura válida (o sin sonda) → intercambiador ON y se reinicia el confirmador de apagado. A-5: presión `None`/NaN = `ERROR_AI_PRES_*`, y `pres_chaqueta` sin dato → vapor de chaqueta OFF. A-7: `apagar_por_paro()`. A-9: el suministro eléctrico sin la entrada cuenta como fallo. |
| `state_machine/states/ciclo.py` | A-4 en `_mantener_drenaje`. A-5: `pres_chaqueta` sin dato → OFF (extensión a CICLO). A-9: `lectura_valida` en sensores críticos, empaque, válvula de reposo y apertura automática. |
| `state_machine/states/falla.py`, `hibernacion.py` | A-7: `apagar_por_paro()`. |
| `protocols/serial_link.py` | A-3: sello monotónico de la última trama `DI:` y `edad_ultima_di()`. `_connect()` pone `di` en 0 y borra el sello; `_disconnect()` también borra el sello. |
| `services/domain/loop/control_loop.py` | A-3: trama DI con más de 1,5 s o sin sello → `EmergencyStop.update(None)`; con el enlace caído también se publica el paro. Propiedad `datos_vigentes`. A-6: aviso en el log (en el flanco) si `puerta_2_cerrada`=1 con `door_count`=1. A-9: suministro eléctrico sin `get(..., 1)`. `run()` no cambió. |
| `backend/server.py` | A-8: `/io/test/enter` y `/io/test/output` responden 409 `sin_conexion_tarjeta` (el código existente de las órdenes de puerta) si el enlace está caído o los datos no son vigentes. `/status` agrega `sondas_no_vigiladas`. |
| `backend/context.py`, `simulador/servidor.py` | Aviso al arrancar con las sondas no vigiladas; mismo contrato de `/status`; `SetOutput` recibe el perfil. |

Pruebas nuevas: `test_adenda_estados.py` (76), `test_adenda_enlace_paro.py` (41), `test_adenda_herramientas_perfil.py` (12). Se escribieron antes del cambio y fallaron todas, salvo 8 que son de regresión.
Pruebas actualizadas: `test_declarar_entradas_suministro.py` (ahora usa `--si`) y `test_e1_supply_inputs_loop_status.py` (+3 de `/status` y del aviso de sondas, escritas después del cambio).
Por requisito: A-1 6 · A-2 46 · A-3 15 · A-4 10 · A-5 13 · A-6 11 · A-7 12 · A-8 9 · A-9 5.

### 8.2 Conteos

| | Resultado |
|---|---|
| Antes (línea base) | **2440 passed**, 6 warnings |
| Las 143 pruebas nuevas y tocadas | 143 passed |
| Suite completa después | **2591 passed**, 6 warnings (las mismas de `datetime.utcnow()`). Diferencia: +151. Las pruebas que agregué suman 132 (129 en los tres archivos `test_adenda_*` y 3 en `test_e1_supply_inputs_loop_status.py`). Las otras 19 vienen de `tests/test_intro_arranque_qml.py` y `tests/test_progreso_arranque.py`: son archivos ajenos a esta adenda (animación de arranque), aparecieron en el árbol durante la sesión y no los toqué. |
| Pruebas antiguas actualizadas (27) | `test_ciclo_drenaje.py` (2) y `test_e0_lecturas_invalidas.py` (17): ahora fijan A-4, A-5 y A-2.2 en vez de "no hace nada". `test_control_loop_test_mode.py` (4) y `test_e1_paro_emergencia_nc.py` (2): el enlace simulado informa una trama DI vigente (A-3). `test_e1_paro_emergencia_nc.py` (1 más) y `test_preparacion_ejecutor_paralelo.py` (1): con el paro esperan `apagar_por_paro()` (A-7). |

### 8.3 A-1 — ¿Qué hace SECADO modo 1/2 hoy sin vacío o sin bomba? (solo informe; la corrección va en E3)

- `secado.py:76-84` (modo 1) y `:86-95` (modo 2): la única condición de salida es el temporizador (`time.monotonic() >= _timer_fin`). Al vencer, **COMPLETADO**. No se lee la presión de cámara ni se comprueba que la bomba haya arrancado.
- `set_io.py` `bomba_vacio_on()`: si `VacuumPump.puede_activar()` devuelve False, **no enciende la bomba y no avisa**. `vacio_camara_on()` sí abre la válvula.
- Resultado: sin vacío real, el ciclo termina **COMPLETADO sin secado**. Con A-1 ya no ocurre por la falta de un DI declarado "no aplica", pero sigue ocurriendo con una bomba averiada. `cap.has_vacuum=False` salta la fase (`secado.py:23-25`).
- Para comparar: el modo 3 sí falla por `timeout_pulso` (`secado.py:111-114`, `:128-131`) y PRE_VACIO por `timeout_bajo` (`prevacio.py:139-145`).

### 8.4 Mapeo de sondas

No existe una configuración de sondas por equipo que se use en tiempo de ejecución. Los YAML `config/models/*.yaml` e `instances/*.yaml` listan sensores, pero nadie los lee y sus nombres no coinciden con los del runtime (ver `inventario_sensores_y_base_de_datos.md` §2). Por eso se creó `temperature_probes`.

| Sonda (Cristian) | Canal |
|---|---|
| Cámara 1 | `temp_camara` (índice 0), obligatoria |
| Cámara 2 | `temp_2_camara` (1) |
| Referencia | `temp_ref` (2) |
| **Drenaje** | **Sin decidir**: `temp_drenaje` (5) o `temp_drenaje_cam` (4) |

**No declaré el procedimiento** para este equipo hasta que se resuelva la pregunta 1. Comando, según la respuesta:
`python tools/declarar_sondas_temperatura.py --instaladas temp_camara temp_2_camara temp_ref temp_drenaje` (o `temp_drenaje_cam` en lugar de `temp_drenaje`).

### 8.5 Nota sobre E0-2

A-4 reemplaza el comportamiento de E0-2: el drenaje sin lectura ya no "salta el tick", ahora fuerza el intercambiador a ON y reinicia el conteo de apagado. Las pruebas de E0-2 y de E0-3 (`pres_chaqueta=None`) ya están actualizadas al nuevo comportamiento.

### 8.6 Preguntas abiertas

1. ¿La sonda "drenaje" está en el canal 5 (`temp_drenaje`, el que controla el intercambiador) o en el 4 (`temp_drenaje_cam`)?
2. Drenaje declarado sin sonda: el intercambiador queda en ON permanente (posición segura, pero gasta agua). ¿Es aceptable?
3. A-3 en CICLO: tras una caída breve del enlace (menos de 5 s), si la primera línea que llega es `AI:` y no `DI:`, el paro se publica y el ciclo aborta por **PARO_EMERGENCIA**. Propuesta: no correr la máquina de estados hasta la primera DI de la nueva conexión. ¿Se aplica?
4. A-2.2 solo se activa con error de sensor analógico. Un fallo de suministro sigue dejando las salidas congeladas, como antes. ¿Lo extendemos?
5. A-5 se extendió a CICLO (`_mantener_chaqueta`). ¿Se confirma?
6. La auditoría de las herramientas va a un archivo JSONL junto al perfil, no a `audit_log` de SQLite (las herramientas corren con el software cerrado). ¿Basta?

### 8.7 Respuestas de Cristian (2026-10-12) y cambios aplicados

| Pregunta | Respuesta | Cambio |
|---|---|---|
| 1. Canal de la sonda de drenaje | `temp_drenaje_cam` ya no existe (era de una versión anterior); su entrada la ocupa `temp_drenaje` | `map_temp`: se retira `temp_drenaje_cam` y `temp_drenaje` pasa a la **posición 4**. La posición 5 queda sin sensor y su calibración posicional no se toca (mismo criterio que con `temp_chaqueta` en T-19). La calibración de usuario de las posiciones 4 y 5 era neutra (gain 1, offset 0), así que lo único que cambia para el drenaje es la ventana de fábrica de la entrada 4 (95–4010). Cambios en `status.py`, el comentario de `calibration.yaml`, `TEMPERATURE_PROBE_KEYS` (4 sondas; un perfil con `temp_drenaje_cam` ahora es inválido), el asistente, la lista de PREPARACION, `/status` (sin `drenaje_camara`), el simulador y la vista de E/S de PySide. |
| 2. Intercambiador permanente sin sonda | Sí | Sin cambio. |
| 3. Esperar la primera DI tras reconectar | Aprobado | `ControlLoop`: tras conectar, mientras no llegue la primera trama DI de esa conexión (como máximo 1,5 s), se publican los sensores y el paro (para la UI), pero no corren suministro, puertas, máquina de estados ni buzzer. Si la DI no llega en ese plazo, se sigue con el paro activo y la máquina de estados lo aplica. Una DI que deja de llegar dentro de una conexión sigue siendo paro con la máquina corriendo (A-3). |
| 4. Salidas seguras también con falla de suministro | Extiéndelo | PREPARACION y PREPARADO: con **cualquier** falla del supervisor (sensor o suministro), vapor de chaqueta y de cámara a OFF, y siguen los lazos de presión de cámara, drenaje y enfriamiento. |
| 5. A-5 en CICLO | Sí | Ya estaba aplicado. |
| 6. Auditoría en JSONL | Sí | Sin cambio. |

**Procedimiento para declarar las sondas de este equipo** (con el software cerrado, desde la raíz del repo o la carpeta del `.exe`):

```powershell
python tools/declarar_sondas_temperatura.py --mostrar
python tools/declarar_sondas_temperatura.py --instaladas temp_camara temp_2_camara temp_ref temp_drenaje
```

Con las cuatro sondas cableadas, el resultado equivale al valor por defecto (todas vigiladas). Declararlo deja el registro explícito en el perfil y en `installation_profile_cambios.log`.

**Pruebas:** nuevo `tests/test_adenda_decisiones.py` (17: P1 5, P3 5, P4 7), escrito antes del cambio; fallaron 13 y 4 pasaron por accidente. Actualizadas porque nombraban `temp_drenaje_cam` o fijaban "falla de suministro no cambia": `test_adenda_estados.py`, `test_adenda_herramientas_perfil.py`, `test_e0_lecturas_invalidas.py`, `test_sin_temp_chaqueta.py`, `test_puertas_fallas_endpoints.py`, `test_preparado_suministro.py`, `test_e1_puertas_perfil.py`, `test_e1_supply_inputs.py`, `test_e1_supply_inputs_loop_status.py` y `test_e1_paro_emergencia_nc.py` (su doble ahora aísla la salida segura).

**Suite completa:** 2563 passed, 19 failed, 14 errors. **Las 33 fallas son todas pruebas de QML** (`test_intro_arranque_qml`, `test_navegacion_*`, `test_opciones_qml`, `test_ui_qml_app`, `test_reconocer_falla`, `test_main_menu_principal_qml`): `Main.qml` no carga (`engine.rootObjects()` vacío). Durante esta sesión otro trabajo, ajeno a la adenda (animación de arranque), modificó `ui_qml/app.py`, `Main.qml`, `Colores.qml` y `es.json` y borró `Pantallas/Arranque.qml`. En la corrida anterior de esta misma sesión esas pruebas pasaban (2591 passed), y la adenda no toca `ui_qml`. No las corregí. Todas las pruebas que no son de QML pasan.

**Pendiente para el inventario:** `docs/informes/inventario_sensores_y_base_de_datos.md` §2.1 sigue describiendo `temp_drenaje_cam` (4) y `temp_drenaje` (5). No lo edité (no es de esta instrucción); conviene actualizarlo.
