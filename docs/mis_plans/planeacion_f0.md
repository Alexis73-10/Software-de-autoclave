# Planeación de la funcionalidad F0 (letalidad acumulada)

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Nueva funcionalidad — adición, no reemplazo. Cálculo de letalidad acumulada (F0) como criterio opcional de finalización de la meseta de esterilización, activable por ciclo (`globals.F0`).

---

## 1. Objetivo y alcance

### Objetivo

Acumular el tiempo equivalente de esterilización a 121.1°C (F0, z=10, referencia ISO 17665) durante todo el tramo del ciclo donde hay letalidad real (CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION), y usarlo como condición adicional (no sustituta) de finalización de la meseta de ESTERILIZACION cuando el ciclo tiene `globals.F0 = true`.

### No es reemplazo de nada existente

`F0` ya existe como flag booleano sin uso en la sección `globals` de cada JSON de ciclo (`bowe_dick.json`, `instrumental_134.json`, etc.). Esta planeación le da comportamiento real. El criterio de tiempo fijo (`tiempo_esterilizacion`) **se mantiene intacto** para ciclos con `F0=false` — no hay cambio de comportamiento en esos ciclos.

### Posición en el pipeline

Sin cambios en la orquestación de `CicloState`:

```
PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION → SECADO → DESCOMPRESION
                                        └──────────── acumula F0 ────────────┘
```

La acumulación **inicia** al entrar a `CALENTAMIENTO` y **se detiene** al completar `ESTERILIZACION` (no continúa en `SECADO`/`DESCOMPRESION`). Confirmado con Cristian.

### Entradas

- `estado.sensores_temp["temp_camara"]`, `estado.sensores_temp["temp_2_camara"]` (existente, mapa ya definido en `EstadoAutoclave`).
- `cap.has_liquid_sensor` (ya usado en `EsterilizacionFase`).
- `estado.fase_ciclo` (para saber si la fase activa está en el rango que acumula).
- `cycle.get_param("globals", "F0")` y `cycle.get_param("globals", "F0_objetivo")`.

### Salidas

- `estado.f0_acumulado: float` (minutos) — nuevo campo, legible por UI, ticket y `EsterilizacionFase`.
- Línea adicional en el ticket de cierre de ciclo, solo si `F0=true`.

### Fuera de alcance

- Cambio del valor de `z` o de la temperatura de referencia (121.1°C) — fijos en código, no parametrizables (decisión explícita de Cristian, punto 6 de la ronda anterior).
- F0 por sensor de chaqueta o drenaje — solo `temp_camara` / `temp_2_camara`.
- Acumulación durante `SECADO`/`DESCOMPRESION`.

---

## 2. Parámetro nuevo

| Nombre en código | Sección | Unidad | Defecto | Mín | Máx | Rol |
|---|---|---|---|---|---|---|
| `F0` | `globals` | bool | `false` | — | — | Ya existe. Activa/desactiva toda la funcionalidad para el ciclo. |
| `F0_objetivo` | `globals` | min | **12** | 0 | 60 *(propuesto — confirmar)* | Letalidad mínima acumulada requerida para poder cerrar la meseta de ESTERILIZACION. |

⚠️ Min/máx de `F0_objetivo` son un valor propuesto por mí para no dejar el campo sin rango en el JSON — confirmar antes de implementar, dado que es un parámetro de seguridad/eficacia del ciclo.

No se agrega parámetro para el timeout de seguridad (ver sección 5): se calcula en código como `2 × tiempo_esterilizacion`, no se guarda en el perfil, para evitar que quede desincronizado si alguien cambia `tiempo_esterilizacion` sin tocar un segundo campo.

---

## 3. Modelo de cálculo

Función pura, sin estado, candidata a vivir junto a `p_saturacion_kpa` en `src/autoclave/core/runtime/steam.py` (mismo módulo de física del ciclo) o en un módulo nuevo `letalidad.py` al lado — **a definir en implementación, no afecta el diseño**.

```
F0_incremento = 10 ** ((T_ref - 121.1) / 10.0) * dt_min
```

- `T_ref`: temperatura de referencia del tick (ver sección 4 — selección de sensor).
- `dt_min`: tiempo real transcurrido desde el tick anterior, en minutos (no el `interval` nominal del `ControlLoop`, para no acumular drift si un tick se retrasa).
- `10.0` = z, fijo.
- `121.1` = temperatura base ISO, fija.

Acumulación: `estado.f0_acumulado += F0_incremento` en cada tick que corresponda (ver sección 4).

---

## 4. Punto de integración: `ControlLoop._tick()`

No vive dentro de ninguna `Fase` individual (no sobreviviría el cambio de fase). Vive como paso adicional en `ControlLoop._tick()`, junto a los pasos numerados existentes (después del paso 1 `estado.update(...)`, antes o después de `state_machine.update()` — no importa el orden relativo a la máquina de estados porque solo lee `estado.fase_ciclo`, ya publicado).

**Condición de ejecución (todas deben cumplirse):**
1. `estado.get_machine_state() == GlobalState.CICLO`
2. `estado.fase_ciclo in {"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}`
3. `cycle.get_param("globals", "F0") is True`

**Selección de sensor de referencia (por tick):**
```
if cap.has_liquid_sensor and temp_2_camara is not None:
    T_ref = min(temp_camara, temp_2_camara)
elif cap.has_liquid_sensor:                     # sensor 2 configurado pero sin lectura
    T_ref = temp_camara                         # degradado — confirmado con Cristian
else:
    T_ref = temp_camara
```

Si `temp_camara` también es `None` (sensor caído), ese tick no acumula (mismo patrón que `test_pres_none_no_avanza_ni_lanza_excepcion` en `test_calentamiento_fase.py` — ausencia de sensor no debe lanzar excepción, solo no avanzar).

**Cálculo de `dt_min`:** requiere que `ControlLoop` guarde `self._f0_ultimo_tick: float | None` (timestamp), igual que el patrón `_t_tick_anterior` ya usado en `CalentamientoFase` para el debounce de tasa. Al entrar por primera vez a las fases que acumulan (`_f0_ultimo_tick is None`), se inicializa sin sumar incremento ese tick (evita un `dt` artificialmente grande si el ciclo llevaba rato en PRE_VACIO).

---

## 5. Reset del acumulador

`estado.f0_acumulado = 0.0` se agrega a `CicloState.reset()`, junto a la línea existente `self.estado.motivo_fallo = ""` — mismo punto del ciclo de vida (una vez al iniciar CICLO), mismo criterio de "se limpia al empezar, no al terminar", consistente con cómo ya se maneja `motivo_fallo`.

`ControlLoop._f0_ultimo_tick` también se resetea a `None` en el mismo punto (o al detectar `fase_ciclo == "CALENTAMIENTO"` con `f0_acumulado == 0.0`, a definir en implementación según qué objeto tiene más fácil acceso al reset de ciclo).

---

## 6. Modificación de `EsterilizacionFase`

### 6.1 Timeout de seguridad (nuevo)

Hoy `ESTERILIZACION` no tiene timeout propio — a diferencia de `CALENTAMIENTO` (`timeout_calentamiento`). Con el criterio F0 activo la meseta puede extenderse indefinidamente si el sensor de referencia no sube lo suficiente (fuga, descalibración). Se agrega:

```python
timeout_max_esterilizacion_seg = 2 * tiempo_seg   # tiempo_seg = tiempo_esterilizacion * 60, ya existe
```

Armado en la inicialización de la fase (junto a `self._timer_fin`), igual patrón que `_timer_timeout_fin` en `CalentamientoFase`. Si se excede → `FALLO` con `alarm_id="ESTERILIZACION_TIMEOUT_F0"`, apaga salidas, igual que los demás `_fallo(...)` de la fase.

**Este timeout aplica siempre que `F0=true`**, independientemente de si F0 finalmente se cumple justo a tiempo o no — es un techo duro de seguridad, no depende de si la meseta iba a completar en el siguiente tick.

### 6.2 Condición de finalización (modificada)

Reemplaza el bloque actual:

```python
if time.time() >= self._timer_fin:
    return FaseResult.COMPLETADO
```

Por (solo cuando `F0=true`; si `F0=false`, se mantiene el bloque original sin cambios):

```python
tiempo_cumplido = time.time() >= self._timer_fin
f0_cumplido     = self.estado.f0_acumulado >= f0_objetivo   # f0_objetivo leído de globals

if tiempo_cumplido and f0_cumplido:
    return FaseResult.COMPLETADO      # ambos criterios satisfechos

if time.time() >= self._timer_timeout_max:
    return self._fallo("ESTERILIZACION_TIMEOUT_F0", f"F0 no alcanzado tras {2*tiempo_seg/60:.0f} min (F0={self.estado.f0_acumulado:.2f}/{f0_objetivo:.1f} min)")

return FaseResult.EN_CURSO            # falta uno de los dos → sigue en meseta
```

Cubre los tres casos confirmados: tiempo cumplido + F0 pendiente → continúa; F0 cumplido + tiempo pendiente → continúa (implícito, ambos se validan); ambos cumplidos → termina. El timeout de 6.1 es la salida de emergencia para el caso "nunca se cumple".

### 6.3 Sin cambios en verificación de temp/presión

Las validaciones de `TEMP_ALTA/BAJA` y `PRES_ALTA/BAJA` existentes no se tocan — F0 es un criterio adicional de *finalización*, no reemplaza las bandas de seguridad ya vigentes.

---

## 7. Ticket de impresión

`CycleLogger._on_fin()` ya arma el footer con `temp_final` y `motivo`. Se agrega `f0_total`:

```python
cycle = self.cycle_manager.get_selected_cycle()
f0_activo = cycle.get_param("globals", "F0") if cycle else False
f0_total  = self.estado.f0_acumulado if f0_activo else None
```

`format_footer(resultado, fecha, temp_final=..., motivo=..., f0_total=f0_total)` — nueva línea en el footer **solo si `f0_total is not None`**, formato propuesto: `F0 total: {valor:.1f} min`. Ubicación en el ticket (antes/después de temp final) — a definir en implementación, no es una decisión de arquitectura.

---

## 8. Archivos afectados (resumen para la fase de código)

| Archivo | Cambio |
|---|---|
| `core/runtime/status.py` (`EstadoAutoclave`) | Nuevo atributo `f0_acumulado: float = 0.0` |
| `core/runtime/steam.py` (o nuevo `letalidad.py`) | Nueva función pura de cálculo de incremento F0 |
| `services/domain/loop/control_loop.py` | Nuevo paso en `_tick()`: selección de sensor, cálculo `dt_min`, acumulación condicionada |
| `state_machine/states/ciclo.py` (`CicloState.reset()`) | Reset de `f0_acumulado` |
| `state_machine/cycle_phases/esterilizacion.py` | Timeout de seguridad + condición de finalización AND |
| `cycles/user/*.json`, `cycles/factory/*.json` | Agregar `F0_objetivo` a `globals` en todos los ciclos existentes |
| `services/domain/logging/cycle_logger.py` | Pasar `f0_total` a `format_footer` |
| `services/domain/logging/ticket_formatter.py` (`format_footer`) | Nuevo parámetro opcional `f0_total`, línea condicional |

---

## 9. Plan de pruebas (para la fase de Test)

Mismo estilo que `tests/test_calentamiento_fase.py` / `test_steam.py`:

- Cálculo puro: `F0_incremento` en T=121.1°C con dt=1min → 1.0 exacto; T=101°C → ≈0.01; T<<121 → prácticamente 0; monotonicidad con T creciente.
- `ControlLoop`: no acumula fuera de `{CALENTAMIENTO, ESTABILIZACION, ESTERILIZACION}`; no acumula si `F0=false`; no acumula ni lanza excepción si `temp_camara is None`; degrada a `temp_camara` si `has_liquid_sensor` y `temp_2_camara is None`; usa `min()` cuando ambos sensores disponibles.
- `EsterilizacionFase` con `F0=true`: no completa si tiempo cumplido pero F0 no; no completa si F0 cumplido pero tiempo no; completa cuando ambos se cumplen; `FALLO` por `ESTERILIZACION_TIMEOUT_F0` al superar 2× tiempo_esterilizacion sin cumplir F0.
- `EsterilizacionFase` con `F0=false`: comportamiento actual sin cambios (regresión).
- Reset: `f0_acumulado` vuelve a 0.0 al iniciar un ciclo nuevo tras uno anterior con F0 activo.
- Ticket: `f0_total` presente solo si `F0=true`; ausente si `F0=false`.

---

## 10. Abierto — confirmar antes de codificar

1. Rango `F0_objetivo` (min/máx propuestos: 0–60) — confirmar o corregir.
2. Ubicación final de la función pura de cálculo (`steam.py` vs. módulo nuevo) — no bloquea el diseño, se resuelve en implementación.
