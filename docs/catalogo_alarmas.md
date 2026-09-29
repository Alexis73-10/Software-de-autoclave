# Catálogo de alarmas

Inventario de todas las alarmas (`Alarm`, `state_machine/alarms/`) que el código genera actualmente,
por búsqueda directa en `src/` (no hay un registro central único — cada `Alarm(...)` se instancia
donde ocurre la condición). Generado 2026-09-18.

No incluye el sistema de severidad 1-4 de `ui_qml/domain/alarmas.py` (toast/banner/banner-blink/
fullscreen): esa es una clasificación genérica para la UI QML nueva, sin mapeo por `alarm_id` en el
código todavía.

## Cómo leer esto

- **Tipo**: `AlarmType` — `ALERTA` (no bloqueante por diseño, aunque algunas sí bloquean
  operación), `FALLA`, `EMERGENCIA`.
- **Bloqueante**: valor de `blocks_operation` en el `Alarm(...)` (default `True` si no se indica).
- **Recuperable**: valor de `recoverable` — si puede auto-limpiarse cuando la condición desaparece.
- IDs con `<...>` son dinámicos (se interpolan en tiempo de ejecución, típicamente con el nombre de
  un sensor, puerta o fase).

## PREPARADO / PREPARACION

Fuente: `state_machine/states/preparado.py`, `state_machine/states/preparacion.py`.
Ver también §"PREPARADO / PREPARACION" de `CLAUDE.md` (separación válvula/alarma/gate).

| ID | Tipo | Bloqueante | Recuperable | Origen | Descripción |
|---|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí | no | PREPARADO, PREPARACION | Paro de emergencia activado. |
| `SUMINISTRO_VAPOR` | ALERTA | no | sí | PREPARADO, PREPARACION | Sin suministro de vapor; chaqueta queda pendiente (no bloquea listo/inicio). |
| `CHAQUETA_FRIA` | ALERTA | sí | sí | PREPARADO, PREPARACION | Presión de chaqueta por debajo de la banda `presion_chaqueta ± rango_presion_chaqueta`. En PREPARADO se dispara con retardo `tiempo_estable_alarma` (temporizada); en PREPARACION es inmediata. |
| `CHAQUETA_SOBRECALENTADA` | ALERTA | sí | sí | PREPARADO | Presión de chaqueta por encima de la banda. Solo en PREPARADO (temporizada). |
| `TEMP_DRENAJE_ALTA` | ALERTA | sí | sí | PREPARADO, PREPARACION | Temperatura de drenaje por encima de `temp_segura_drenaje + rango_temp_drenaje`. En PREPARADO se dispara con retardo `tiempo_estable_alarma` (temporizada); en PREPARACION es inmediata. Unificado 2026-09-18 — antes PREPARACION usaba el ID `TEMPERATURA_DRENAJE_ALTA` para el mismo hecho. |
| `PRESION_CAMARA_BAJA` | ALERTA | sí | sí | PREPARADO, PREPARACION | Presión de cámara por debajo de `presion_admosferica − rango_presion_atm`. |
| `PRESION_CAMARA_ALTA` | ALERTA | sí | sí | PREPARADO, PREPARACION | Presión de cámara por encima de `presion_admosferica + rango_presion_atm`. |
| `PUERTA_1_ABIERTA` | ALERTA | sí | sí | PREPARADO | Puerta 1 no cerrada. |
| `PUERTA_2_ABIERTA` | ALERTA | sí | sí | PREPARADO | Puerta 2 no cerrada. |
| `AGUA_RESIDUAL_CAMARA` | ALERTA | sí | sí | PREPARACION | Agua residual detectada en cámara (`agua_camara` DI activo). |
| `SUMINISTRO_ELECTRICO` | ALERTA | sí | sí | PREPARADO | DI `suministro_electrico` en 0. |
| `ERROR_AI_<SENSOR>` | ALERTA | sí | sí | PREPARADO, PREPARACION | Lectura de sensor analógico (presión o temperatura) en 0 → fallo de sensor. `<SENSOR>` es la clave del sensor en mayúsculas (p.ej. `ERROR_AI_PRES_CAMARA`, `ERROR_AI_TEMP_DRENAJE`). En PREPARACION la lista de sensores chequeados es fija (`pres_camara`, `pres_chaqueta`, `pres_empaque_1`, `pres_empaque_2`, `temp_camara`, `temp_2_camara`, `temp_ref`, `temp_chaqueta`, `temp_drenaje_cam`, `temp_drenaje`); en PREPARADO recorre todo `sensores_pres`/`sensores_temp` configurados. |
| `SUMINISTRO_<SERVICIO>` | ALERTA | sí | sí | PREPARADO, PREPARACION | DI de suministro en 0. `<SERVICIO>` ∈ `AGUA_BOMBA`, `AGUA_GENERADOR`, `AIRE_COMPRIMIDO` (lista fija en ambos estados; en PREPARADO además cualquier otro DI que caiga en ese mismo filtro). |

## CICLO

Fuente: `state_machine/states/ciclo.py`.

| ID | Tipo | Bloqueante | Recuperable | Descripción |
|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí (default) | no | Paro de emergencia durante el ciclo → aborta a FALLA. |
| `FALLO_SUMINISTRO_ELECTRICO` | EMERGENCIA | sí (default) | no | Pérdida de suministro eléctrico durante el ciclo. |
| `FALLO_PUERTA_1_ABIERTA` / `FALLO_PUERTA_2_ABIERTA` | FALLA | sí (default) | sí | Puerta 1/2 se abrió durante el ciclo. |
| `FALLO_PUERTA_1_EMPAQUE` / `FALLO_PUERTA_2_EMPAQUE` | FALLA | sí (default) | sí | Presión de empaque de puerta 1/2 por debajo de `0.6 × presion_empaque`. |
| `SENSOR_AUSENTE` | EMERGENCIA | sí (default) | no | `temp_camara` y/o `pres_camara` (sensores críticos) sin lectura. |
| `FALLO_CONEXION` | EMERGENCIA | sí (default) | no | Comunicación serial caída más que la tolerancia de `ControlLoop`; abortado fuera del tick normal vía `abortar_por_desconexion()`. |
| `FALLO_<FASE>` | FALLA | sí (default) | sí | Fallo genérico al completar una fase con `FaseResult.FALLO`. `<FASE>` es el `name` de la fase: `PRECALENTAMIENTO`, `PURGA`, `PRE_VACIO`, `CALENTAMIENTO`, `ESTERILIZACION`, `DESCOMPRESION`, `SECADO`. El **motivo específico** (temp/pres alta o baja, timeout, timeout F0, etc.) queda solo en `estado.motivo_fallo` como texto libre — la fase nunca reporta un `alarm_id` distinto por tipo de falla interna (ver `_fallo()` en `esterilizacion.py`/`calentamiento.py`). |
| `SUMINISTRO_VAPOR` | ALERTA | no | sí | Sin suministro de vapor durante el ciclo; chaqueta pendiente. |
| `TEMP_DRENAJE_ALTA` | ALERTA | no | sí | Temperatura de drenaje alta durante el ciclo (debounce de 3 lecturas). |
| `TIMEOUT_APERTURA_AUTOMATICA` | ALERTA | no | sí | Apertura automática de puerta al finalizar: la cámara tarda más de `timeout_temperatura` min en enfriar bajo `temp_max_apertura`. Se dispara una sola vez por ciclo. |
| `APERTURA_AUTOMATICA_DENEGADA` | ALERTA | no | sí | Apertura automática: `request_open()` no logra mover la puerta (bloqueo mecánico/interlock) por más de 60 s. Se dispara una sola vez; sigue reintentando cada 5 s. |

## CONTROL_LOOP

Fuente: `services/domain/loop/control_loop.py`.

| ID | Tipo | Bloqueante | Recuperable | Descripción |
|---|---|---|---|---|
| `NO_HAY_CONEXION` | FALLA | sí | sí | Sin comunicación con el hardware (fuera de un ciclo en curso — dentro de ciclo, ver `FALLO_CONEXION`). |

## PUERTA

Fuente: `devices/puertas/advanced_door.py` (solo `AdvancedDoor`, puertas con actuador/bomba de vacío).

| ID | Tipo | Bloqueante | Recuperable | Descripción |
|---|---|---|---|---|
| `ABRIENDO_MODO_SEGURO_<nombre>` | ALERTA | no | sí | Puerta `<nombre>` abriendo en modo seguro, sin bomba de vacío disponible. |
| `CERRANDO_MODO_SEGURO_<nombre>` | ALERTA | no | sí | Puerta `<nombre>` cerrando en modo seguro, sin bomba de vacío disponible. |

## FALLA / HIBERNACION

Fuente: `state_machine/states/falla.py`, `state_machine/states/hibernacion.py`.

| ID | Tipo | Bloqueante | Recuperable | Descripción |
|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí (default) | no | Paro de emergencia activo mientras la máquina ya está en FALLA o HIBERNACION. Mismo ID que en PREPARADO/PREPARACION/CICLO — el `source_state` en la descripción es lo que distingue el origen. |

## Notas de consistencia

- **`PARO_EMERGENCIA` no es una sola alarma**: se re-instancia con el mismo `alarm_id` desde 5
  estados distintos (PREPARADO, PREPARACION, CICLO, FALLA, HIBERNACION). `AlarmManager.report()`
  deduplica por `id`, así que solo queda una activa a la vez independientemente de cuál estado la
  reportó última.
- **Sin catálogo central**: no existe un enum/registro único de `alarm_id` válidos — son literales
  de texto en cada punto de la fase/estado. Renombrar una alarma requiere `grep` de su string en
  todo `src/` (instanciación, `clear()`, y cualquier UI que la referencie por nombre).
