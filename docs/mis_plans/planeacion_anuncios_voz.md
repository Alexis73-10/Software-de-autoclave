# Planeación — Subsistema de anuncios por voz

**Proyecto:** Software-de-autoclave
**Estado:** Especificación de diseño — pendiente de aprobación
**Versión objetivo:** V1.0 (solo español)
**Clasificación IEC 62304 propuesta:** Clase A (ver §9.1)

---

## 1. Objetivo y alcance

Emitir mensajes de voz pregrabados ante eventos informativos y de alarma del
equipo, como complemento visual-independiente para el operador que no está
mirando la pantalla.

### 1.1 Dentro del alcance

- Reproducción de archivos WAV pregenerados, embebidos en el repositorio.
- Cola de reproducción con prioridad e interrupción.
- Configuración de habilitación y volumen desde la interfaz, sin credenciales.
- Botón de prueba de salida de audio.
- Detección de ausencia de dispositivo de audio, reportada como alerta.

### 1.2 Fuera del alcance

- Síntesis de voz (TTS) en tiempo de ejecución. Ver §3.1.
- Idiomas distintos del español. La estructura del manifiesto queda preparada
  para multi-idioma pero V1.0 no lo implementa.
- Reemplazo o modificación del buzzer de hardware. Ver §9.2.
- Anuncio de transiciones internas de fase del ciclo (PRE_VACIO, CALENTAMIENTO,
  ESTERILIZACION, SECADO). Decisión explícita: son frecuentes, ya están en
  pantalla, y su anuncio degradaría la atención del operador hacia los mensajes
  que sí son críticos.

---

## 2. Decisiones de diseño cerradas

| # | Decisión | Valor |
|---|---|---|
| D-01 | Origen del audio | Archivos WAV pregenerados, no TTS en runtime |
| D-02 | Generación de locuciones V1.0 | TTS offline en *build time* (Piper), voz es_MX/es_ES |
| D-03 | Proceso que reproduce | Backend (uvicorn), no la UI |
| D-04 | Librería de reproducción | `sounddevice` + `soundfile` |
| D-05 | Salida física | Jack analógico 3.5 mm a parlante amplificado |
| D-06 | Identificación de puerta | Obligatoria ("Puerta uno" / "Puerta dos") |
| D-07 | Estados de puerta anunciados | Solo terminales: ABIERTO, CERRADO, ATRAPADA, ERROR |
| D-08 | Política de solapamiento | Cola con prioridad; mayor urgencia interrumpe |
| D-09 | Repetición de alarma activa | Una sola vez por activación |
| D-10 | Silenciamiento | Silencia todo; el buzzer de hardware queda intacto |
| D-11 | Persistencia de configuración | Archivo nuevo de preferencias, independiente |
| D-12 | Nivel de acceso | Sin credenciales, accesible al operador |
| D-13 | Momento de la bienvenida | Cuando la UI ya es usable, no al arrancar el backend |
| D-14 | Sin dispositivo de audio | Alerta no bloqueante, el equipo sigue operando |
| D-15 | Punto de integración | Observador único en `ControlLoop._tick()` |

### 2.1 Justificación de D-04 (librería)

`winsound` de la biblioteca estándar sería atractivo por no agregar SOUP, pero
se descarta: no permite control de ganancia por software (D-11 exige volumen
configurable) ni abortar una reproducción en curso (D-08 exige interrupción).

`sounddevice`/`soundfile` agregan PortAudio y libsndfile como SOUP. Deben
registrarse en el inventario de SOUP del expediente IEC 62304 con su versión
fijada en `requirements.lock.txt`.

### 2.2 Justificación de D-15 (punto de integración)

La alternativa evaluada fue enganchar `ServicioPuertas._on_state_change()` y
`AlarmManager.report()`, que ya son puntos de detección por flanco.

Se descarta porque `ser_puertas.py`, `alarm_manager.py` y `ciclo.py` son unidades
de software Clase C. Insertar llamadas de audio en ellas obliga a re-verificar
archivos críticos de seguridad para una funcionalidad informativa.

El observador propuesto solo **lee** `estado.estado_puertas`,
`estado.Alarmas_activas` y `estado.get_machine_state()` — estructuras que ya
están publicadas en `EstadoAutoclave` al momento en que se lo invoca. No altera
ninguna ruta de decisión existente y se verifica de forma aislada.

---

## 3. Arquitectura

```
ControlLoop._tick()
  ├─ 1..7  (secuencia existente, sin cambios)
  └─ 8. AnnouncerObserver.update()          ← NUEVO, no bloqueante
          │  detección de flanco sobre estado compartido
          │  emite event_id
          ▼
       Announcer.say(event_id, prioridad)
          │  encola (heapq + Condition), retorna de inmediato
          ▼
       [hilo worker daemon]
          │  desencola → aplica ganancia → sd.play() → sd.wait()
          ▼
       Dispositivo de audio (jack 3.5 mm)
```

### 3.1 Por qué WAV pregenerados y no TTS en runtime

| Criterio | TTS runtime | WAV pregenerado |
|---|---|---|
| Determinismo de salida | La voz depende de las voces instaladas en el SO y cambia entre versiones de Windows | Idéntico bit a bit en todo equipo |
| Verificabilidad V&V | No se puede escribir una prueba que compare la salida | Hash SHA-256 por archivo, verificable |
| Latencia | Variable, depende de la síntesis | Constante, buffer ya en memoria |
| Revisión por Calidad | Imposible revisar antes del despliegue | Archivo fijo, escuchable y aprobable |
| Carga SOUP | Motor TTS completo | Solo decodificador WAV |

El TTS se usa **una sola vez, en tiempo de construcción**, para generar los WAV.
Los archivos generados se versionan en el repositorio. Sustituirlos por locución
humana en una versión posterior no requiere cambio de código: solo se reemplazan
los archivos y se regenera el manifiesto.

### 3.2 Carga en memoria al arranque

Los WAV se decodifican **una sola vez al iniciar el backend** y se conservan en
memoria como arreglos `numpy` float32. Peso total estimado: 3–4 MB.

Motivos:

- Elimina I/O de disco de la ruta de reproducción → latencia determinista.
- Un archivo faltante o corrupto se detecta al arranque, no en el momento en que
  se necesita anunciar una emergencia.
- Sin manejadores de archivo abiertos durante la operación.

Si algún archivo del manifiesto falta o no se puede decodificar, el subsistema
arranca **deshabilitado** y reporta la alerta `AUDIO_NO_DISPONIBLE` (§7.2).

### 3.3 Aislamiento del hilo de control

`Announcer.say()` **nunca** bloquea. Encola bajo lock y notifica al worker. El
`ControlLoop._tick()` no debe verse afectado por el estado del dispositivo de
audio bajo ninguna circunstancia — un dispositivo desconectado en caliente no
puede detener el bucle de control.

El hilo worker es `daemon=True` y se detiene con un evento de parada limpio en
el apagado del backend.

---

## 4. Catálogo de eventos

### 4.1 Niveles de prioridad

| Nivel | Categoría | Interrumpe a | Cooldown |
|---|---|---|---|
| P0 | Emergencia | P1–P5 | 60 s |
| P1 | Fallo de ciclo | P2–P5 | 60 s |
| P2 | Alerta | P3–P5 | 60 s |
| P3 | Estado de puerta | — | 5 s |
| P4 | Ciclo | — | 5 s |
| P5 | Sistema | — | 5 s |

**Regla de interrupción:** si llega un evento de prioridad estrictamente más
urgente que el que está sonando, la reproducción actual se aborta (`sd.stop()`),
se **descarta** (no se reencola) y suena el nuevo. Eventos de igual o menor
urgencia se encolan.

**Cooldown:** registro `{event_id: timestamp_última_locución}` interno al
anunciador, independiente del ciclo de vida de las alarmas. Ver §9.3 (H-E).

### 4.2 P0 — Emergencia

| event_id | Origen (alarm_id / estado) | Texto |
|---|---|---|
| `emg_paro_emergencia` | `PARO_EMERGENCIA` | "Paro de emergencia activado." |
| `emg_fallo_electrico` | `FALLO_SUMINISTRO_ELECTRICO` | "Fallo de suministro eléctrico." |
| `emg_sensor_ausente` | `SENSOR_AUSENTE` | "Sensor crítico ausente. Ciclo abortado." |
| `emg_puerta_1_atrapada` | `DoorState.ATRAPADA` (Puerta 1) | "Atrapamiento en puerta uno." |
| `emg_puerta_2_atrapada` | `DoorState.ATRAPADA` (Puerta 2) | "Atrapamiento en puerta dos." |

### 4.3 P1 — Fallo de ciclo

| event_id | Origen | Texto |
|---|---|---|
| `fal_ciclo_abortado` | `CicloResultado.FALLO` | "Ciclo abortado por fallo." |
| `fal_camara_segura` | `protocolo_fallo` → buzzer emitido | "Cámara en condiciones seguras." |
| `fal_puerta_1_error` | `DoorState.ERROR` (Puerta 1) | "Fallo en puerta uno." |
| `fal_puerta_2_error` | `DoorState.ERROR` (Puerta 2) | "Fallo en puerta dos." |

### 4.4 P2 — Alerta

**Suministros** (origen: `SUMINISTRO_*`)

| event_id | alarm_id | Texto |
|---|---|---|
| `alr_sum_agua_bomba` | `SUMINISTRO_AGUA_BOMBA` | "Falta suministro de agua de bomba." |
| `alr_sum_agua_generador` | `SUMINISTRO_AGUA_GENERADOR` | "Falta suministro de agua de generador." |
| `alr_sum_aire_comprimido` | `SUMINISTRO_AIRE_COMPRIMIDO` | "Falta suministro de aire comprimido." |
| `alr_sum_electrico` | `SUMINISTRO_ELECTRICO` | "Alerta de suministro eléctrico." |

**Sensores analógicos** (origen: `ERROR_AI_*`)

| event_id | alarm_id | Texto |
|---|---|---|
| `alr_ai_pres_camara` | `ERROR_AI_PRES_CAMARA` | "Error en sensor de presión de cámara." |
| `alr_ai_pres_chaqueta` | `ERROR_AI_PRES_CHAQUETA` | "Error en sensor de presión de chaqueta." |
| `alr_ai_pres_empaque_1` | `ERROR_AI_PRES_EMPAQUE_1` | "Error en sensor de presión de empaque uno." |
| `alr_ai_pres_empaque_2` | `ERROR_AI_PRES_EMPAQUE_2` | "Error en sensor de presión de empaque dos." |
| `alr_ai_temp_camara` | `ERROR_AI_TEMP_CAMARA` | "Error en sensor de temperatura de cámara." |
| `alr_ai_temp_2_camara` | `ERROR_AI_TEMP_2_CAMARA` | "Error en sensor de temperatura de cámara dos." |
| `alr_ai_temp_ref` | `ERROR_AI_TEMP_REF` | "Error en sensor de temperatura de referencia." |
| `alr_ai_temp_chaqueta` | `ERROR_AI_TEMP_CHAQUETA` | "Error en sensor de temperatura de chaqueta." |
| `alr_ai_temp_drenaje_cam` | `ERROR_AI_TEMP_DRENAJE_CAM` | "Error en sensor de temperatura de drenaje de cámara." |
| `alr_ai_temp_drenaje` | `ERROR_AI_TEMP_DRENAJE` | "Error en sensor de temperatura de drenaje." |

Se decide una frase por sensor, no una genérica: el operador necesita saber cuál
sensor falló sin ir a la pantalla. Son diez archivos adicionales, costo
despreciable.

### 4.5 P3 — Estado de puerta

| event_id | Origen | Texto |
|---|---|---|
| `pta_1_abierta` | `DoorState.ABIERTO` (Puerta 1) | "Puerta uno abierta." |
| `pta_1_cerrada` | `DoorState.CERRADO` (Puerta 1) | "Puerta uno cerrada." |
| `pta_2_abierta` | `DoorState.ABIERTO` (Puerta 2) | "Puerta dos abierta." |
| `pta_2_cerrada` | `DoorState.CERRADO` (Puerta 2) | "Puerta dos cerrada." |

Los estados transitorios ABRIENDO y CERRANDO no se anuncian (D-07): la
transición ABRIENDO→ABIERTO ocurre en segundos y produciría solapamiento.

En equipos de una sola puerta, los eventos de Puerta 2 no se registran. El
observador construye su tabla a partir de `estado.estado_puertas`, que ya refleja
la configuración del equipo.

### 4.6 P4 — Ciclo

| event_id | Origen | Texto |
|---|---|---|
| `cic_iniciado` | Transición a `GlobalState.CICLO` | "Ciclo iniciado." |
| `cic_completado` | `CicloResultado.COMPLETADO` | "Ciclo completado." |
| `equipo_preparado` | Transición a `GlobalState.PREPARADO` | "Equipo preparado." |

### 4.7 P5 — Sistema

| event_id | Origen | Texto |
|---|---|---|
| `sys_bienvenida` | `POST /audio/ui-ready` | "Bienvenido. Autoclave Especifika." |
| `sys_prueba_audio` | `POST /audio/test` | "Prueba de audio correcta." |

**Total: 33 archivos WAV.**

### 4.8 Redacción de los textos

Todos los textos describen **estado**, nunca instruyen ni autorizan. Ver §9.4
(hallazgo H-B, IEC 62366-1). Ejemplos de redacción rechazada:

- ✘ "Puede retirar la carga" — implica una autorización que el software no verificó.
- ✘ "Abra la puerta" — instrucción directiva.
- ✔ "Cámara en condiciones seguras" — descripción de estado medido.

Los números se escriben como palabra ("uno", "dos") para forzar la pronunciación
correcta en el TTS de generación.

---

## 5. Formato de audio y manifiesto

### 5.1 Formato

| Parámetro | Valor |
|---|---|
| Contenedor | WAV (PCM sin comprimir) |
| Profundidad | 16 bits |
| Frecuencia de muestreo | 22 050 Hz |
| Canales | Mono |
| Normalización de pico | −3 dBFS |
| Duración máxima por frase | 4 s |

Mono a 22.05 kHz es suficiente para voz y reduce a la mitad la memoria respecto
a 44.1 kHz. La normalización uniforme evita que unas frases se oigan más fuerte
que otras.

### 5.2 Estructura de directorios

```
src/autoclave/assets/audio/
├── manifest.json
└── es/
    ├── emg_paro_emergencia.wav
    ├── emg_fallo_electrico.wav
    ├── ...
    └── sys_prueba_audio.wav
```

### 5.3 Formato del manifiesto

```json
{
  "version": "1.0",
  "idioma_default": "es",
  "eventos": {
    "emg_paro_emergencia": {
      "prioridad": 0,
      "cooldown_s": 60,
      "texto": "Paro de emergencia activado.",
      "archivos": { "es": "es/emg_paro_emergencia.wav" },
      "sha256": { "es": "a3f1..." }
    }
  }
}
```

El campo `texto` es documentación del contenido — permite a Calidad revisar y
aprobar la redacción sin escuchar los archivos, y sirve de fuente para
regenerarlos. El campo `sha256` se valida al arranque contra el archivo real.

---

## 6. Cola de prioridad

### 6.1 Estructura

`heapq` con tuplas `(prioridad, secuencia, event_id)`. El contador `secuencia`
monótono garantiza orden FIFO dentro del mismo nivel de prioridad y evita que
`heapq` intente comparar `event_id` en caso de empate.

Sincronización: `threading.Condition` — el worker espera sin consumir CPU.

### 6.2 Reglas

1. **Cooldown.** Si `now - último[event_id] < cooldown_s`, se descarta en
   silencio (nivel DEBUG en log).
2. **Duplicado en cola.** Si el `event_id` ya está encolado sin reproducir, se
   descarta el nuevo.
3. **Interrupción.** Si la prioridad entrante es estrictamente menor (más
   urgente) que la que está sonando, se aborta la reproducción actual y se
   descarta; el evento entrante pasa al frente.
4. **Límite de cola.** Máximo 10 elementos. Al desbordar se descarta el de menor
   urgencia y se registra WARNING. Nunca se descarta un P0.
5. **Deshabilitado.** Al deshabilitar el audio se vacía la cola y se aborta la
   reproducción en curso.

### 6.3 Ganancia

```
ganancia = (volumen / 100) ** 2.0
muestras_salida = muestras * ganancia
```

Escala cuadrática: la percepción de sonoridad no es lineal, y un deslizador
lineal se siente concentrado en el tramo alto. Volumen por defecto: 80.

---

## 7. Configuración y persistencia

### 7.1 Archivo de preferencias

**Ruta:** `data/preferences.json`

```json
{
  "audio": {
    "enabled": true,
    "volume": 80
  }
}
```

Archivo nuevo e independiente (D-11). No va en `installation_profile.json`
porque no es un dato de instalación ni participa en la validación de licencia; no
va en el perfil de parámetros del ciclo porque un cambio de volumen no puede
tocar un archivo que participa en la validación del proceso de esterilización.

Escritura atómica (archivo temporal + `os.replace`) para no corromper el archivo
ante un corte de energía. Si el archivo no existe o es inválido, se usan valores
por defecto y se regenera.

Propietario del archivo: el backend. La UI solo lo modifica a través de la API.

### 7.2 Alerta por ausencia de dispositivo

Si al arranque no hay dispositivo de salida disponible, o si una reproducción
falla con excepción de PortAudio, se reporta:

| Campo | Valor |
|---|---|
| alarm_id | `AUDIO_NO_DISPONIBLE` |
| tipo | `AlarmType.ALERTA` |
| blocks_operation | `False` |
| recoverable | `True` |

El equipo sigue operando normalmente (D-14). La alerta es visible en pantalla y
en el ticket de alarmas. Esta alerta **no** se anuncia por voz, por razones
evidentes.

Tras tres fallos consecutivos de reproducción, el subsistema se autodeshabilita
para no llenar el log, manteniendo la alerta activa. Se reintenta al usar el
botón de prueba.

---

## 8. API y interfaz

### 8.1 Endpoints nuevos (`backend/server.py`)

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| GET | `/audio/config` | — | `{"enabled": bool, "volume": int, "available": bool}` |
| PATCH | `/audio/config` | `{"enabled"?: bool, "volume"?: int}` | `{"ok": true, ...}` |
| POST | `/audio/test` | — | `{"ok": bool}` |
| POST | `/audio/ui-ready` | — | `{"ok": bool}` |

Restricciones deliberadas:

- **No existe un endpoint genérico `/audio/announce`.** Un endpoint que acepte un
  `event_id` arbitrario ampliaría la superficie de la API sin necesidad. Solo se
  exponen las dos acciones que la UI realmente necesita disparar.
- **Ningún endpoint acepta rutas de archivo.** Aceptar una ruta convertiría la
  API en una primitiva de lectura de disco remota.
- `volume` se valida en rango 0–100; fuera de rango devuelve 422.
- `/audio/ui-ready` es idempotente por sesión de backend: solo la primera llamada
  produce sonido, para que un reinicio de la UI no repita la bienvenida.

Ver §9.5 sobre la relación con el hallazgo abierto H-03.

### 8.2 Interfaz de usuario

Vista nueva en `ui_pyside/views/`, accesible **sin credenciales** (D-12), con:

- Interruptor "Anuncios por voz" (habilitado / deshabilitado).
- Deslizador de volumen 0–100.
- Botón "Probar" → `POST /audio/test`.
- Indicador de estado del dispositivo de audio (desde `available`).

El botón de prueba es el mecanismo de verificación en campo: permite al técnico
de instalación confirmar cableado, volumen y funcionamiento del parlante sin
provocar un evento real del equipo.

### 8.3 Bienvenida

`autoclave/main.py` llama `POST /audio/ui-ready` **después** de que la ventana
principal está construida y visible (D-13), no al arrancar el backend. El backend
puede estar esperando hardware hasta 40 s, y una bienvenida en ese punto sonaría
frente a una pantalla que aún no es utilizable.

---

## 9. Seguridad y cumplimiento

### 9.1 Clasificación IEC 62304

Se propone **Clase A** para el subsistema de anuncios:

- Ningún fallo del subsistema puede contribuir a una situación peligrosa: no
  escribe salidas digitales, no participa en enclavamientos, no altera el estado
  de la máquina.
- Se ejecuta en un hilo aislado; su fallo no puede detener el `ControlLoop`.
- Los archivos existentes que se modifican (`control_loop.py`, `server.py`,
  `context.py`) reciben adiciones que no alteran rutas de decisión de seguridad.

Requiere confirmación del responsable de calidad regulatoria.

### 9.2 H-A — El anuncio de voz no es un control de riesgo (ISO 14971)

**Los anuncios por voz no pueden contarse como mitigación de ningún riesgo.**
Son señal informativa redundante. En particular:

- El enclavamiento de puerta sigue siendo exclusivamente por software.
- El buzzer de hardware sigue siendo la señal audible de alarma, y **no se
  modifica**. `BuzzerPlayer` y su actualización en `ControlLoop._tick()` paso 7
  quedan intactos.
- El silenciamiento de la voz (D-10) **no** silencia el buzzer. Si en alguna
  iteración futura se propone unificar ambos controles, debe rechazarse: sería
  un defecto de seguridad.

Justificación de por qué la voz no califica como control: es silenciable por el
operador sin credenciales, depende de hardware externo no monitoreado
(parlante, cableado), y no tiene realimentación de que el mensaje fue emitido ni
percibido.

### 9.3 H-E — Chattering de alarmas

`AlarmManager.report()` descarta duplicados por ID mientras la alarma está
activa. Pero en `preparado_state.verificar_sensores()` y
`verificar_suministros()`, un sensor oscilando alrededor del umbral produce
`report → clear → report` en ticks consecutivos. Sin mitigación, un
`agua_generador` intermitente haría hablar al equipo sin parar.

**Mitigación:** cooldown de 60 s por `event_id` (§4.1), interno al anunciador.
No se modifica `AlarmManager`.

### 9.4 H-B — Redacción como riesgo de uso (IEC 62366-1)

Un mensaje directivo puede ser interpretado por el operador como autorización
verificada del sistema. Mitigación: todos los textos describen estado (§4.8), y
el catálogo de textos requiere aprobación documentada antes de generar los WAV.

### 9.5 H-03 — Superficie de API

Los cuatro endpoints nuevos amplían la superficie de la API sin autenticación
(hallazgo abierto H-03). Evaluación:

- Impacto máximo de abuso: hacer sonar un mensaje o cambiar el volumen. No hay
  actuación sobre el proceso.
- Ningún endpoint acepta rutas ni identificadores arbitrarios.
- Se registran en el inventario de superficie expuesta, para revisión conjunta
  cuando se implemente la pantalla de diagnóstico v2 y el backend deje de estar
  limitado a `localhost`.

### 9.6 H-C — Sesión de audio de Windows

Si el backend llegara a ejecutarse como servicio de Windows (sesión 0), no tiene
sesión de audio y las reproducciones fallarían. Hoy el backend se lanza como
subproceso de la UI (`main.py`), en sesión de usuario, así que la condición no se
presenta. Se documenta como restricción de despliegue: **el backend debe correr
en sesión de usuario interactiva.** La detección de §7.2 cubre el caso residual.

### 9.7 Riesgos a registrar en ISO 14971

| ID | Riesgo | Control |
|---|---|---|
| R-VOZ-01 | Anuncio asociado al evento equivocado induce acción incorrecta | Manifiesto con `event_id`↔archivo verificado por SHA-256 al arranque; prueba unitaria de la tabla de mapeo |
| R-VOZ-02 | Ausencia de audio no detectada; el operador confía en anuncios que no suenan | Alerta `AUDIO_NO_DISPONIBLE` + botón de prueba en campo |
| R-VOZ-03 | Mensaje interpretado como autorización del sistema | Redacción descriptiva (§4.8) con aprobación documentada |
| R-VOZ-04 | Saturación de cola oculta un evento urgente | Prioridad con interrupción; los P0 nunca se descartan |
| R-VOZ-05 | El anunciador bloquea el `ControlLoop` | Hilo separado; `say()` no bloqueante; prueba unitaria de tiempo de retorno |
| R-VOZ-06 | Fatiga por exceso de anuncios; el operador ignora los críticos | Exclusión de transiciones de fase; cooldown; catálogo cerrado |

---

## 10. Archivos afectados

### 10.1 Nuevos

| Archivo | Contenido |
|---|---|
| `src/autoclave/devices/audio/announcer.py` | `Announcer` — cola, worker, ganancia |
| `src/autoclave/devices/audio/manifest.py` | Carga y validación del manifiesto |
| `src/autoclave/services/domain/audio/announcer_observer.py` | Detección de flanco sobre `EstadoAutoclave` |
| `src/autoclave/config/preferences.py` | Lectura/escritura atómica de `data/preferences.json` |
| `src/autoclave/assets/audio/manifest.json` | Manifiesto |
| `src/autoclave/assets/audio/es/*.wav` | 33 archivos |
| `src/autoclave/ui_pyside/views/audio_config.py` | Vista de configuración |
| `tools/generar_audio.py` | Generación de WAV con Piper (build time) |
| `tests/test_announcer.py` | Cola, prioridad, cooldown, no bloqueo |
| `tests/test_announcer_observer.py` | Detección de flanco por categoría |
| `tests/test_audio_endpoints.py` | Endpoints |

### 10.2 Modificados

| Archivo | Cambio |
|---|---|
| `services/domain/loop/control_loop.py` | Paso 8: `announcer_observer.update()`; parada del worker en `stop()` |
| `backend/context.py` | Instanciación de `Announcer` y `AnnouncerObserver` |
| `backend/server.py` | Cuatro endpoints de §8.1 |
| `main.py` | Llamada a `POST /audio/ui-ready` tras construir la ventana |
| `ui_pyside/main_window.py` | Registro de la vista nueva en el `QStackedWidget` |
| `requirements.txt` / `requirements.lock.txt` | `sounddevice`, `soundfile` |

**El módulo del buzzer (`devices/buzer/buzer.py`) no se modifica.**

---

## 11. Plan de verificación

| ID | Prueba | Criterio de aceptación |
|---|---|---|
| T-01 | Integridad del manifiesto | Los 33 archivos existen, decodifican y su SHA-256 coincide |
| T-02 | `say()` no bloqueante | Retorna en < 1 ms con el worker ocupado |
| T-03 | Orden por prioridad | Encolar P4, P2, P0 → se reproducen P0, P2, P4 |
| T-04 | Interrupción | P3 sonando + llega P0 → P3 se aborta y descarta |
| T-05 | Cooldown | Mismo `event_id` dos veces en 10 s → una sola reproducción |
| T-06 | Duplicado en cola | Mismo `event_id` encolado dos veces → un solo elemento |
| T-07 | Límite de cola | 15 eventos encolados → 10 en cola, ningún P0 descartado |
| T-08 | Flanco de puerta | ABRIENDO→ABIERTO emite una vez; permanecer en ABIERTO no reemite |
| T-09 | Equipo de una puerta | No se emiten eventos de Puerta 2 |
| T-10 | Dispositivo ausente | Alerta `AUDIO_NO_DISPONIBLE`; `ControlLoop` sigue corriendo |
| T-11 | Silenciamiento | `enabled=false` → cola vacía, sin reproducción, buzzer intacto |
| T-12 | Persistencia | Volumen modificado sobrevive al reinicio del backend |
| T-13 | Escritura atómica | Interrupción durante la escritura no corrompe `preferences.json` |
| T-14 | Validación de volumen | `PATCH` con 150 → 422; el valor almacenado no cambia |
| T-15 | Bienvenida idempotente | Dos llamadas a `/audio/ui-ready` → una sola reproducción |
| T-16 | Aislamiento del tick | Excepción en el worker no propaga al `ControlLoop` |

Verificación en campo (no automatizable): audibilidad del parlante sobre el ruido
ambiente de la sala de autoclaves, medida a la distancia habitual de trabajo del
operador.

---

## 12. Ítems abiertos

| ID | Ítem | Bloquea implementación |
|---|---|---|
| V-01 | Periodo de tick del `ControlLoop` — necesario para dimensionar la detección de flanco y confirmar que no se pierden transiciones | Sí |
| V-02 | ¿`estado.estado_puertas` y `estado.Alarmas_activas` requieren lock para lectura desde el observador? Revisar `EstadoAutoclave` | Sí |
| V-03 | Nombres exactos de `GlobalState` para las transiciones de §4.6, y cómo se expone `CicloResultado.COMPLETADO`/`FALLO` al observador | Sí |
| V-04 | ¿Existe ya algún archivo de preferencias de UI que deba reutilizarse en vez de crear `data/preferences.json`? | Sí |
| V-05 | Modelo y sensibilidad del parlante amplificado; confirmar nivel de presión sonora suficiente para el ambiente | No (afecta solo verificación en campo) |
| V-06 | Aprobación del catálogo de textos de §4 por calidad regulatoria antes de generar los WAV | No (permite avanzar con archivos provisionales) |
| V-07 | Confirmar clasificación Clase A del subsistema (§9.1) | No |

---

## 13. Secuencia de implementación propuesta

1. Resolver V-01 a V-04.
2. `preferences.py` + pruebas → base independiente, sin audio.
3. `manifest.py` + `Announcer` + pruebas con dispositivo simulado (sin WAV reales).
4. `tools/generar_audio.py` y generación de los 33 archivos provisionales.
5. `AnnouncerObserver` + pruebas de flanco.
6. Integración en `context.py` y `control_loop.py`.
7. Endpoints + pruebas.
8. Vista de configuración en PySide6.
9. Verificación en campo y sustitución de locuciones si V-06 lo requiere.

Los pasos 2 y 3 no dependen del hardware de audio y se pueden desarrollar y
verificar por completo antes de que llegue el parlante.
