# Sistema de alarmas — Parte A: catálogo, modelo, historial y contrato

Fecha: 2026-10-06. Estado: diseño aprobado en chat por secciones, pendiente de revisión escrita.
Base: `docs/informes/analisis_sistema_alarmas.md`.

## 1. Objetivo y alcance

Hoy la pantalla muestra códigos internos (`FALLO_PREVACIO`, `ERROR_AI_PRES_EMPAQUE_1`) o descripciones genéricas, y no guarda cuándo ocurrió nada. La Parte A cambia la base del sistema:

- un catálogo central con título legible, descripción con valores, acción sugerida y un código técnico;
- instancias con origen, valores, horas y reconocimiento;
- historial persistente en la base de datos;
- un contrato nuevo en `/status`, compatible con los consumidores actuales.

El rediseño completo tiene tres partes:

| Parte | Contenido |
|---|---|
| **A (esta)** | Base del sistema + migración de las alarmas existentes, **sin cambiar cuándo se dispara ninguna ni su nivel** |
| B | Cobertura nueva por área (puertas, fases, comunicación, sensores) y separación de los CIC por causa |
| C | Interfaz QML (campo legible, reconocimiento, avisos emergentes) y pestaña de alarmas de Reportes |

Fuera del alcance de A: alarmas nuevas (salvo `SIS-02`, que la propia Parte A necesita), cambios en las condiciones de disparo, cambio de `time.time()` a `time.monotonic()` en puertas (Parte B) y cualquier cambio visual en QML.

## 2. Niveles de severidad

| Nivel nuevo | Nivel actual | Reconocimiento | Lista de activas | Prioridad IEC (sin cambio) |
|---|---|---|---|---|
| `INFORMATIVO` | — (nuevo) | No | Nunca entra (ver §5.6) | — |
| `AVISO` | `ALERTA` | No | Sí | baja |
| `ALARMA` | `FALLA` | **Sí** | Sí | media |
| `FALLO_CRITICO` | `EMERGENCIA` | **Sí** | Sí | alta |

Coinciden con las severidades 1–4 de `ui_qml/domain/alarmas.py`.

## 3. Códigos

Formato `ÁREA-NN`, con número de dos dígitos dentro de cada área. Un código **nunca se reutiliza** para otro significado, aunque se elimine la alarma.

| Área | Alcance |
|---|---|
| `PUE` | Puertas |
| `CIC` | Ciclo y sus fases |
| `PRE` | Condiciones de preparación (chaqueta, cámara, drenaje) |
| `COM` | Comunicación con la tarjeta |
| `SEN` | Sensores |
| `SUM` | Suministros (eléctrico, agua, aire, vapor) |
| `SIS` | Sistema (paro de emergencia, historial, software) |

En pantalla se muestran juntos: `PUE-01 · Puerta abierta`.

## 4. Catálogo (`state_machine/alarms/catalogo.py`)

### 4.1 Entrada del catálogo

Es una dataclass congelada `DefinicionAlarma`:

| Campo | Tipo | Significado |
|---|---|---|
| `codigo` | str | `ÁREA-NN`, único |
| `nivel` | `Nivel` (enum) | ver §2 |
| `titulo` | str | Corto y legible, sin valores |
| `descripcion` | str | Plantilla con campos `{nombre}` / `{nombre:.1f}`. Explica *qué pasó y por qué*, con valores medidos y límites |
| `accion` | str | Qué debe hacer el operador. Puede quedar vacía en los informativos |
| `bloquea_inicio` | bool | Equivale al `blocks_operation` actual. **Es solo informativo**: hoy ningún consumidor lo usa (`has_blocking_alarm()` no tiene llamadas) y el inicio de ciclo se decide en `esta_preparado()`. La Parte A no cambia eso |
| `despeje` | `AUTOMATICO` / `MANUAL` | `AUTOMATICO`: quien la disparó llama a `resolver()` cuando la condición desaparece, igual que hoy con `clear()`. `MANUAL`: nadie la resuelve por condición. Se resuelve al reiniciar desde FALLA (§5.4) |

El catálogo es un `dict[str, DefinicionAlarma]` construido en el mismo módulo. Los códigos se exponen además como constantes (`PUE_01 = "PUE-01"`), para que un error tipográfico falle al importar y no en ejecución.

### 4.2 Nombres legibles

`catalogo.py` contiene también la tabla `NOMBRES_LEGIBLES`: clave interna → nombre para el operador. Cubre sensores (`temp_camara` → "Temperatura de cámara", `pres_empaque_1` → "Presión de empaque puerta 1", y así con todos los sensores de `preparacion.py`), fases (`PREVACIO` → "Prevacío") y puertas. La función `nombre_legible(clave)` devuelve la misma clave si no la encuentra, y una prueba exige que todas las claves usadas hoy estén en la tabla.

### 4.3 Migración de las alarmas actuales

Todos los textos son una propuesta para revisión. Las plantillas usan solo los valores que ya están disponibles en cada punto de disparo actual.

| Código | Reemplaza | Nivel | Bloquea | Despeje | Título | Descripción (plantilla) | Acción |
|---|---|---|---|---|---|---|---|
| SIS-01 | PARO_EMERGENCIA | FALLO_CRITICO | sí | AUTOMATICO | Paro de emergencia activado | Se presionó el paro de emergencia en estado {estado}. Todas las salidas están apagadas. | Verifique que no haya riesgo y libere el botón de paro. |
| SIS-02 | (nueva) | AVISO | no | MANUAL | Historial de alarmas no disponible | No se pudo guardar el historial de alarmas: {error}. Las alarmas siguen funcionando, pero no quedan registradas. | Avise a soporte técnico. |
| SUM-01 | FALLO_SUMINISTRO_ELECTRICO | FALLO_CRITICO | sí | MANUAL | Corte eléctrico durante el ciclo | Se perdió el suministro eléctrico en la fase {fase}. El ciclo se abortó. | Verifique la alimentación del equipo antes de reiniciar. |
| SUM-02 | SUMINISTRO_ELECTRICO | AVISO | sí | AUTOMATICO | Sin suministro eléctrico | La señal de suministro eléctrico está inactiva. | Verifique la alimentación del equipo. |
| SUM-03 | SUMINISTRO_AGUA_BOMBA | AVISO | sí | AUTOMATICO | Sin agua para la bomba de vacío | La señal de suministro de agua de la bomba está inactiva. | Abra la válvula de agua de la bomba y verifique la presión de la red. |
| SUM-04 | SUMINISTRO_AGUA_GENERADOR | AVISO | sí | AUTOMATICO | Sin agua para el generador | La señal de suministro de agua del generador está inactiva. | Abra la válvula de agua del generador y verifique la presión de la red. |
| SUM-05 | SUMINISTRO_AIRE_COMPRIMIDO | AVISO | sí | AUTOMATICO | Sin aire comprimido | La señal de suministro de aire comprimido está inactiva. | Verifique el compresor y la válvula de aire. |
| SUM-06 | SUMINISTRO_VAPOR | AVISO | no | AUTOMATICO | Sin suministro de vapor | No hay suministro de vapor en estado {estado}. La chaqueta queda en espera hasta que regrese. | Verifique el generador y la válvula de vapor. |
| PRE-01 | CHAQUETA_FRIA | AVISO | sí | AUTOMATICO | Presión de chaqueta baja | La chaqueta está en {pres:.0f} kPa, por debajo del mínimo de {minimo:.0f} kPa (objetivo {objetivo:.0f} ± {rango:.0f}). | Espere a que la chaqueta alcance presión. Si no sube, verifique el suministro de vapor. |
| PRE-02 | CHAQUETA_SOBRECALENTADA | AVISO | sí | AUTOMATICO | Presión de chaqueta alta | La chaqueta está en {pres:.0f} kPa, por encima del máximo de {maximo:.0f} kPa (objetivo {objetivo:.0f} ± {rango:.0f}). | Verifique la válvula de vapor de chaqueta. |
| PRE-03 | PRESION_CAMARA_BAJA | AVISO | sí | AUTOMATICO | Presión de cámara baja | La cámara está en {pres:.0f} kPa, por debajo de {minimo:.0f} kPa. | Espere a que la cámara se iguale con la atmósfera. |
| PRE-04 | PRESION_CAMARA_ALTA | AVISO | sí | AUTOMATICO | Presión de cámara alta | La cámara está en {pres:.0f} kPa, por encima de {maximo:.0f} kPa. | No abra la puerta. Espere a que la cámara descomprima. |
| PRE-05 | AGUA_RESIDUAL_CAMARA | AVISO | sí | AUTOMATICO | Agua residual en la cámara | El sensor de nivel detecta agua acumulada en la cámara. Se está drenando. | Si no desaparece, verifique el drenaje de la cámara y la trampa de vapor. |
| PRE-06 | TEMP_DRENAJE_ALTA | AVISO | sí | AUTOMATICO | Temperatura de drenaje alta | El drenaje está en {temp:.1f} °C, por encima del máximo de {maximo:.1f} °C. Se activó el enfriamiento. | Verifique el agua del intercambiador. |
| PUE-01 | PUERTA_1_ABIERTA / PUERTA_2_ABIERTA | AVISO | sí | AUTOMATICO | Puerta abierta | {puerta} está abierta. El ciclo no puede iniciar. | Cierre la puerta. |
| PUE-02 | FALLO_PUERTA_n_ABIERTA | ALARMA | sí | MANUAL | Puerta abierta durante el ciclo | {puerta} dejó de detectarse cerrada en la fase {fase}. El ciclo se abortó. | Verifique el sensor de puerta cerrada y el cierre mecánico. |
| PUE-03 | FALLO_PUERTA_n_EMPAQUE | ALARMA | sí | MANUAL | Presión de empaque insuficiente | El empaque de {puerta} bajó a {pres:.0f} kPa (mínimo {minimo:.0f} kPa) en la fase {fase}. El ciclo se abortó. | Verifique el aire comprimido y el estado del empaque. |
| PUE-04 | ABRIENDO_MODO_SEGURO_x | AVISO | no | AUTOMATICO | Apertura en modo seguro | {puerta} se está abriendo sin bomba de vacío por falla eléctrica. | Ninguna, la apertura continúa. |
| PUE-05 | CERRANDO_MODO_SEGURO_x | AVISO | no | AUTOMATICO | Cierre en modo seguro | {puerta} se está cerrando sin bomba de vacío por falla eléctrica. | Ninguna, el cierre continúa. |
| SEN-01 | ERROR_AI_<SENSOR> | AVISO | sí | AUTOMATICO | Lectura inválida de sensor | {sensor} entrega una lectura inválida ({valor}). | Verifique la conexión del sensor. |
| SEN-02 | SENSOR_AUSENTE | FALLO_CRITICO | sí | MANUAL | Sensor crítico sin lectura | Sin lectura de: {sensores}, en la fase {fase}. El ciclo se abortó. | Verifique la conexión de los sensores antes de reiniciar. |
| CIC-01 | FALLO_PRECALENTAMIENTO | ALARMA | sí | MANUAL | Fallo en precalentamiento | {motivo} | Revise el suministro de vapor de la chaqueta. |
| CIC-02 | FALLO_PREVACIO | ALARMA | sí | MANUAL | Fallo en prevacío | {motivo} | Revise la bomba de vacío y su agua de sello. |
| CIC-03 | FALLO_CALENTAMIENTO | ALARMA | sí | MANUAL | Fallo en calentamiento | {motivo} | Revise el suministro de vapor y la presión del generador. |
| CIC-04 | FALLO_ESTERILIZACION | ALARMA | sí | MANUAL | Fallo en esterilización | {motivo} | La carga NO está estéril. Revise el suministro de vapor y repita el ciclo. |
| CIC-05 | FALLO_DESCOMPRESION | ALARMA | sí | MANUAL | Fallo en descompresión | {motivo} | No abra la puerta hasta confirmar presión atmosférica. Revise las válvulas de escape. |
| CIC-06 | FALLO_SECADO | ALARMA | sí | MANUAL | Fallo en secado | {motivo} | Revise la bomba de vacío. La carga puede salir húmeda. |
| CIC-07 | TIMEOUT_APERTURA_AUTOMATICA | AVISO | no | AUTOMATICO | Enfriamiento demorado | La cámara sigue en {temp:.1f} °C (máximo para abrir {maximo:.1f} °C) tras {minutos:.0f} min. | Espere. La puerta se abrirá sola al enfriar. |
| CIC-08 | APERTURA_AUTOMATICA_DENEGADA | AVISO | no | AUTOMATICO | Apertura automática denegada | No se pudo abrir {puerta}: {motivo}. | Verifique el bloqueo mecánico de la puerta. |
| COM-01 | NO_HAY_CONEXION | ALARMA | sí | AUTOMATICO | Sin comunicación con la tarjeta | No llegan datos válidos de la tarjeta de control. | Verifique el cable USB y la alimentación de la tarjeta. |
| COM-02 | FALLO_CONEXION | FALLO_CRITICO | sí | MANUAL | Comunicación perdida durante el ciclo | Se perdió la comunicación con la tarjeta por más de {segundos:.0f} s en la fase {fase}. El ciclo se abortó. | Verifique el cable USB y la alimentación de la tarjeta antes de reiniciar. |

Notas sobre la migración:

- **CIC-01…06** reciben en `{motivo}` el `estado.motivo_fallo` que deja la fase. Si la fase no dejó motivo (precalentamiento, prevacío, descompresión y secado), el texto es "La fase terminó en fallo; el motivo detallado aún no se registra." La separación por causa con valores es Parte B.
- **Origen** de cada instancia: la puerta (PUE-01…05), el sensor en nombre legible (SEN-01) o la fase en la que ocurrió (CIC-01…06, SUM-01, SEN-02, COM-02). En el resto (SIS, SUM-02…06, PRE, CIC-07/08, COM-01) **no hay origen** (`None`): una sola instancia por código, igual que hoy con un solo id.
- **El origen nunca es el estado de la máquina.** SIS-01, SUM-06, PRE-xx y SEN-01 se activan desde un estado y se resuelven desde otro (por ejemplo, PRE-06 se activa en PREPARACION y se resuelve en PREPARADO o CICLO). Si el estado formara parte de la clave, la instancia creada en un estado nunca se resolvería en el siguiente y quedaría colgada. Cuando el estado aporta información, va dentro de la descripción con `{estado}`, no en la clave.
- **PRE-06:** hoy TEMP_DRENAJE_ALTA es no bloqueante en CICLO y bloqueante en los demás estados. Como `bloquea_inicio` no tiene consumidores (§4.1), PRE-06 queda con un único `bloquea_inicio = sí` y eso no cambia el comportamiento. Si la Parte C llega a usar ese campo, debe tratarlo como irrelevante durante CICLO.
- **`AlarmType`** se mantiene como alias de `Nivel` (`ALERTA = AVISO`, etc.) solo durante la migración. Al cerrar la Parte A ningún módulo de `src/` debe importar `Alarm` ni `AlarmType`.

## 5. Instancias y `AlarmManager`

### 5.1 Instancia (`InstanciaAlarma`)

`clave` (`"{codigo}|{origen}"`, o solo `codigo` sin origen), `definicion`, `origen`, `valores` (dict), `titulo`, `descripcion` (renderizada), `aparecida` (datetime), `resuelta` (datetime | None), `reconocida_por` (str | None), `reconocida_en` (datetime | None), `estado` (`ACTIVA` | `RESUELTA_SIN_RECONOCER`), `ciclo_id` (int | None), `id_historial` (int | None).

### 5.2 API

| Método | Comportamiento |
|---|---|
| `activar(codigo, origen=None, **valores)` | Crea la instancia si no existe. Si ya existe `ACTIVA`, actualiza `valores` y `descripcion` sin tocar `aparecida`. Si existe `RESUELTA_SIN_RECONOCER`, la reactiva (`ACTIVA`, `resuelta=None`), conserva `aparecida` y no crea fila nueva en el historial. Un código desconocido lanza `KeyError`. Una plantilla con valores faltantes **no lanza**: registra `logger.error` y usa "Detalle no disponible" |
| `resolver(codigo, origen=None)` | Si la instancia exige reconocimiento y nadie la reconoció, pasa a `RESUELTA_SIN_RECONOCER`. Si no, sale de la lista. En ambos casos se registra `resuelta`. Si la instancia no existe, no hace nada |
| `reconocer(clave, usuario) -> bool` | Registra `reconocida_por`/`reconocida_en`. Si estaba `RESUELTA_SIN_RECONOCER`, sale de la lista. Si sigue `ACTIVA`, queda marcada. Devuelve False si la clave no existe o el nivel no exige reconocimiento |
| `resolver_todas_por_reinicio()` | Reemplaza a `Alarmas_activas.clear()` al salir de FALLA (`state_machine.py:122`). Aplica `resolver` a todas las activas |
| `activas() -> list[InstanciaAlarma]` | Copia ordenada por nivel (de mayor a menor) y luego por `aparecida` |
| `eventos_recientes() -> list` | Ver §5.6 |
| `has_emergency/has_failure/has_alert/has_blocking_alarm/has_active_alarms` | Se conservan con la equivalencia de §2 y cuentan solo instancias `ACTIVA` |

### 5.3 Instancia única y concurrencia

- **Una sola instancia de `AlarmManager`**, creada en `BackendContext` e inyectada a `ControlLoop` → `StateMachine`. Hoy `StateMachine.__init__` crea la suya (`state_machine.py:22`) y además se recrea al cambiar de ciclo (`control_loop.py:306`). Las dos funcionan solo porque comparten la lista `estado.Alarmas_activas`. Con estado interno, eso deja de valer: `StateMachine` recibe el manager por parámetro.
- `estado.Alarmas_activas` desaparece como fuente de verdad. `server.py` lee `alarm_manager.activas()`. Si algún consumidor necesita el atributo durante la transición, se mantiene como propiedad de solo lectura que delega en el manager.
- **Candado interno** (`threading.Lock`): `reconocer()` llega por HTTP (hilo del backend), mientras `activar`/`resolver` corren en el hilo del ControlLoop. Las notificaciones al oyente (§6.2) se hacen **fuera** del candado.

### 5.4 Salida de FALLA y fallo de ciclo

- `resolver_todas_por_reinicio()` deja en la lista solo las `ALARMA`/`FALLO_CRITICO` que nadie reconoció, en estado `RESUELTA_SIN_RECONOCER`.
- Al terminar el ciclo en fallo, `estado.motivo_fallo` pasa a ser `"{codigo} · {titulo}: {descripcion}"` de la alarma causante, y se guarda `estado.codigo_fallo = codigo`. La tabla `ciclos` gana la columna `codigo_fallo TEXT DEFAULT ''` (migración con `ALTER TABLE`, igual que `motivo_fallo`) y `cerrar_ciclo()` la escribe. El ticket del ciclo imprime en la línea de motivo solo `"{codigo} · {titulo}"`.

### 5.5 Buzer

**Corrección del 2026-10-07, al preparar el plan:** en la Parte A el reconocimiento **no toca el buzer**. Hoy no hay ningún tono de alarma que se pueda silenciar:

- `buzer_fallo` (`BEEP_FALLO`) es un pitido único de unos 1,7 s. Indica que la cámara alcanzó condiciones seguras después de un fallo. Es una señal de "ya puede abrir", no una alarma sonora.
- `buzer_emergencia` se repite mientras el paro esté activo y **no debe silenciarse** con un reconocimiento.
- `BEEP_ALARMA` existe en `buzer.py`, pero nadie lo usa.

Un tono de alarma sostenido para `ALARMA`/`FALLO_CRITICO` sin reconocer, que el reconocimiento silencie, se diseña aparte (Parte B o C), con revisión de `safety-reviewer`. Así la Parte A no toca ningún actuador.

### 5.6 Informativos

Hoy ninguna alarma es `INFORMATIVO`; el nivel queda listo para la Parte B. `activar()` con un código informativo:

- no crea instancia en la lista de activas;
- inserta una fila en el historial con `resuelta = aparecida`;
- agrega `{codigo, titulo, descripcion, origen, hora}` a una cola circular de 20 elementos (`eventos_recientes()`).

## 6. Historial persistente

### 6.1 Tabla

```sql
CREATE TABLE IF NOT EXISTS alarmas_historial (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo               TEXT NOT NULL,
    nivel                TEXT NOT NULL,
    titulo               TEXT NOT NULL,
    origen               TEXT DEFAULT '',
    descripcion_inicial  TEXT NOT NULL,
    descripcion_final    TEXT DEFAULT '',
    valores_json         TEXT DEFAULT '{}',
    aparecida            TEXT NOT NULL,
    resuelta             TEXT,
    reconocida_por       TEXT,
    reconocida_en        TEXT,
    ciclo_id             INTEGER REFERENCES ciclos(id)
);
CREATE INDEX IF NOT EXISTS idx_alarmas_aparecida ON alarmas_historial(aparecida);
```

Se crea en `_apply_schema` de `db_manager.py`. Las horas van en ISO 8601 con `datetime.now()`, por ser sellos de registro. Los temporizadores siguen con `time.monotonic()`.

Cuándo se escribe:

| Evento | Escritura |
|---|---|
| Aparición | INSERT. `valores_json` = valores al aparecer. `ciclo_id` = ciclo en curso si lo hay |
| Actualización de valores mientras está activa | No se escribe |
| Resolución | UPDATE de `resuelta`, `descripcion_final` y `valores_json` (los últimos) |
| Reconocimiento | UPDATE de `reconocida_por` y `reconocida_en` |
| Reactivación de una `RESUELTA_SIN_RECONOCER` | UPDATE de `resuelta = NULL` |

### 6.2 Desacople

`AlarmManager` no importa nada de la base de datos. Expone `suscribir(oyente)`, y el oyente recibe `(evento, instancia)` con evento en `APARECIDA` / `RESUELTA` / `RECONOCIDA` / `REACTIVADA`. En `BackendContext` se registra `HistorialAlarmas(db)` (nuevo, `services/domain/logging/historial_alarmas.py`), que traduce los eventos a `DbManager` y guarda `id_historial` en la instancia.

Si la escritura falla, `HistorialAlarmas`:

1. registra `logger.error`;
2. **no** propaga la excepción, para que el ControlLoop siga funcionando;
3. activa `SIS-02` una sola vez por arranque, sin escribirla en el historial.

`ciclo_id` lo obtiene de `CycleLogger`, que ya conoce el ciclo abierto.

## 7. Backend

### 7.1 `/status` → `alarms`

Cada elemento lleva:

| Campo | Nuevo / compat. | Valor |
|---|---|---|
| `clave`, `codigo`, `nivel`, `titulo`, `descripcion`, `accion`, `origen`, `aparecida` (ISO), `estado`, `requiere_reconocimiento`, `reconocida_por` | nuevos | según §5.1 |
| `id` | compat. | `clave` |
| `level` | compat. | nombre viejo: AVISO→`ALERTA`, ALARMA→`FALLA`, FALLO_CRITICO→`EMERGENCIA` |
| `description` | compat. | `descripcion` |
| `source_state` | compat. | `origen` |

Se agrega además `eventos_recientes` (lista de §5.6) al mensaje de `/status`. Los consumidores actuales ignoran las claves extra: `UiBridge` lee solo `alarms`, y `ui_qml/domain/telemetria.py` valida otro mensaje, comprobando que estén sus claves requeridas sin rechazar las adicionales. Se verifica con `test_ui_bridge`.

### 7.2 Endpoints nuevos

- `POST /alarms/{clave}/acknowledge` con cuerpo `{"usuario": str}`. Responde 200 `{"ok": true}`; 404 si la clave no existe; 422 si el nivel no exige reconocimiento. La clave lleva `|` y espacios, así que el cliente la codifica en la URL.
- `GET /alarms/history?desde=ISO&hasta=ISO&nivel=NIVEL&limite=N` devuelve las filas de `alarmas_historial` en orden descendente por `aparecida`. Por defecto `limite=200`, con máximo de 1000.

### 7.3 Ticket de alarmas activas

`_build_alarms_ticket_lines` (`ui_pyside/views/impresion_menu.py`) imprime por alarma:

```
{codigo} · {titulo}
{aparecida HH:MM:SS dd/mm/aaaa} — {origen}
```

Para leer `codigo`, `titulo` y `aparecida` usa los campos nuevos. Si faltan (backend viejo), cae a `id`/`description`.

## 8. Pruebas

| Archivo | Cubre |
|---|---|
| `tests/test_alarmas_catalogo.py` | Códigos únicos con formato `ÁREA-NN` y área válida; ningún campo vacío salvo `accion` en informativos; cada plantilla se renderiza con un juego de valores de ejemplo declarado en la propia prueba; `NOMBRES_LEGIBLES` cubre todos los sensores de `preparacion.py` y las fases de `cycle_phases` |
| `tests/test_alarm_manager.py` | activar, actualizar, resolver (con y sin reconocimiento), reconocer antes y después de resolver, reactivación, `resolver_todas_por_reinicio`, plantilla con valores faltantes (no lanza, deja log), código desconocido (KeyError), informativo fuera de la lista y en la cola, acceso concurrente desde dos hilos, oyente llamado fuera del candado |
| `tests/test_historial_alarmas.py` | INSERT/UPDATE por evento con SQLite temporal; `ciclo_id`; una escritura que falla no propaga la excepción y activa SIS-02 una sola vez |
| `tests/test_status_endpoint_alarms.py` (actualizar) | Campos nuevos y de compatibilidad, `eventos_recientes` |
| `tests/test_alarms_endpoints.py` | Reconocimiento 200/404/422; historial con filtros y límite |
| `tests/test_preparacion_alarm_wording.py` (actualizar) | Pasa a verificar códigos y textos de catálogo |
| Suite completa | Debe seguir pasando, en particular `test_ui_bridge`, ciclo, puertas y control loop |

## 9. Criterios de aceptación

1. Ningún módulo de `src/` construye `Alarm(...)` ni llama `alarm_manager.report/clear`; todos usan `activar/resolver` con códigos del catálogo.
2. Ninguna alarma cambia su condición de disparo ni su nivel respecto a hoy (equivalencia de §2).
3. Existe una sola instancia de `AlarmManager` en ejecución.
4. Cada alarma activa en `/status` trae título, descripción con valores, acción, origen y hora, y conserva los campos de compatibilidad.
5. Las alarmas `ALARMA`/`FALLO_CRITICO` no reconocidas sobreviven a la salida de FALLA.
6. Toda aparición, resolución y reconocimiento queda en `alarmas_historial`, y una falla de la base de datos no detiene el control.
7. El comportamiento del buzer no cambia: el paro de emergencia sigue sonando mientras esté activo, aunque se reconozca SIS-01.
8. La suite pasa y `safety-reviewer` revisó el diff antes del commit.
