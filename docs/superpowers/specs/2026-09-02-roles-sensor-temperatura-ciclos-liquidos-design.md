# Roles de sensor de temperatura para ciclos líquidos — diseño

Fecha: 2026-09-02

## Objetivo

Para ciclos de líquidos, la segunda sonda de cámara (`temp_2_camara`) se instala
sumergida en el líquido, no en el vapor. Hoy el código no distingue esto:
`CalentamientoFase`/`EsterilizacionFase` controlan y fallan siempre contra
`temp_camara` fijo; `temp_2_camara` solo se usa (opcionalmente) en el cálculo
de F0. Esta spec agrega, por perfil de ciclo, una asignación de **rol** por
sensor (`principal` / `referencia` / `no_en_uso`) y cablea ese rol a la
lógica de control, de forma que:

- El vapor se controla con la sonda rápida (vapor) — evita el lag térmico
  del líquido en el lazo de control.
- Las fallas de temperatura, el gate de entrada a esterilización, F0 y la
  impresión del ticket usan la sonda que de verdad importa (el líquido) —
  evita esterilizar con el líquido frío o sobrecalentarlo.
- Ciclos sin segunda sonda (sólidos, hoy) quedan bit-a-bit iguales a como
  están, porque el rol por defecto es "todo en `temp_camara`".

Además, agrega el menú y las dos pantallas de configuración que lo hacen
usable: **Sensores de temperatura** (roles) y **Entradas exhibidas**
(qué 3 sensores se muestran en la pantalla de ciclo en curso — pantalla que
hoy solo existe en la UI Tkinter vieja y se está reconstruyendo en QML).
Esta spec deja lista la configuración y los endpoints; la pantalla QML que
consuma "entradas exhibidas" en tiempo real se conecta más adelante, fuera
de este alcance.

## Alcance de UI

Se implementa en `ui_pyside` (donde vive hoy el flujo completo
login → admin_menu → parámetros del ciclo). La UI QML de doble pantalla
(`ui_qml/`, en construcción) no se toca — cuando exista ahí una pantalla de
ciclo en curso, consumirá los mismos datos/endpoints.

## Modelo de datos

### Campo JSON `cycle_temperature_sensors` (reutilizado)

Ya existe en los 5 perfiles JSON de ciclo (`factory/` y `user/`) con la
forma `{"1": "temp_camara", "2": "temp_ref"}`, pero **no tiene consumidores
en código** — `Cycle.__init__` (`core/managers/cycle_manager.py`) solo
guarda `parameters`; este campo se descarta al cargar. No hay migración que
romper: se redefine su forma a `sensor → rol`:

```json
"cycle_temperature_sensors": {
    "temp_camara":   "principal",
    "temp_2_camara": "referencia",
    "temp_ref":      "no_en_uso"
}
```

Roles válidos: `"principal"`, `"referencia"`, `"no_en_uso"`. Un sensor
ausente del dict se trata como `"no_en_uso"`. A lo sumo un sensor puede ser
`"principal"` en todo el dict — se valida al persistir (ver Backend).

Los 5 JSON existentes se actualizan al nuevo formato como parte de esta
implementación: `{"temp_camara": "principal", "temp_2_camara": "no_en_uso",
"temp_ref": "no_en_uso"}` (comportamiento actual, sin segunda sonda activa).

### Campo JSON `cycle_display_slots` (nuevo)

```json
"cycle_display_slots": ["temp_camara", "pres_camara", null]
```

Lista de exactamente 3 elementos, cada uno el nombre de un sensor analógico
(cualquiera de `map_temp`/`map_pres` en `core/runtime/status.py`) o `null`
(casilla vacía). Sin restricción de unicidad entre casillas. Se agrega vacío
(`[null, null, null]`) a los 5 perfiles existentes si no se especifica otra
cosa al escribir los JSON.

### `Cycle` (`core/managers/cycle_manager.py`)

- `self.sensor_roles: dict[str, str]` — cargado de `cycle_temperature_sensors`
  en `_load_from_folder` (hoy se descarta; deja de descartarse).
- `self.display_slots: list[str | None]` — cargado de `cycle_display_slots`,
  default `[None, None, None]` si el campo no está presente.
- `get_principal_sensor() -> str`: el sensor con rol `"principal"`, o
  `"temp_camara"` si no hay ninguno marcado (ciclo sin el campo, o todos en
  `no_en_uso`/`referencia`) — garantiza compatibilidad hacia atrás.
- `get_referencia_sensor() -> str | None`: el sensor con rol `"referencia"`,
  o `None` si no hay ninguno.
- `set_sensor_roles(roles: dict[str, str]) -> None`: reemplaza
  `sensor_roles` completo, valida que a lo sumo una entrada sea
  `"principal"` y que las claves sean nombres de sensor conocidos
  (`EstadoAutoclave.map_temp`); lanza `ValueError` si no.
- `set_display_slots(slots: list[str | None]) -> None`: valida longitud 3 y
  que cada valor no nulo sea un sensor conocido (`map_temp` o `map_pres`).

### `BaseFase` (`state_machine/cycle_phases/base_fase.py`)

Nuevos helpers, junto a `_temp_camara()`/`_temp_camara_2()` existentes (que
no se tocan — siguen leyendo el sensor físico por nombre fijo):

```python
def _temp_principal(self) -> float | None:
    return self.estado.sensores_temp.get(self.cycle.get_principal_sensor())

def _temp_referencia(self) -> float | None:
    sensor = self.cycle.get_referencia_sensor()
    return self.estado.sensores_temp.get(sensor) if sensor else None

def _temp_control(self) -> float | None:
    """Sensor que alimenta el lazo de control de vapor: la referencia si
    hay una configurada, si no el principal (que por defecto es
    temp_camara — comportamiento actual sin cambios)."""
    return self._temp_referencia() if self.cycle.get_referencia_sensor() else self._temp_principal()
```

## Lógica de control

### `CalentamientoFase`

Todo el cálculo de duty (`duty_tasa`, `duty_proximidad`, `duty_calidad_vapor`,
techo, ventana de `ESTABLE_PREESTERILIZACION`) cambia su lectura de
`self._temp_camara()` a `self._temp_control()`. Sin referencia configurada
(ciclos de un sensor), `_temp_control()` resuelve a `_temp_principal()`
que por defecto es `temp_camara` — idéntico al comportamiento de hoy.

Se agrega una condición nueva para completar la fase: además de la ventana
de estabilidad ya existente (medida contra `_temp_control()`), si hay una
sonda de referencia distinta configurada, `_temp_principal()` debe validar
vapor saturado contra la presión real de cámara, reutilizando
`_verificar_vapor_saturado()` (método existente en `base_fase.py`, sin
consumidores hoy) con `rango_calentamiento` como tolerancia — el mismo
parámetro que ya usa el control de proximidad, sin agregar parámetro nuevo:

```python
hay_referencia = self.cycle.get_referencia_sensor() is not None
principal = self._temp_principal() if hay_referencia else None  # None si no hay referencia distinta
if principal is not None:
    if not self._verificar_vapor_saturado(principal, pres, rango_cal):
        # no completar todavía — se mantiene EN_CURSO en ESTABLE_PREESTERILIZACION,
        # sin reiniciar el timer de sostenimiento del vapor
        ...
```

Si `_temp_principal()` es `None` (sensor desconectado) mientras hay una
referencia configurada, la fase no completa ni falla — mismo patrón de
riesgo aceptado que ya existe para `temp`/`pres` en `EsterilizacionFase`.

### `EsterilizacionFase`

`_control_vapor_pwm` y la transición `RECUPERACION ↔ PWM_ACTIVO` pasan a
usar `self._temp_control()` en vez de `self._temp_camara()` — igual
razonamiento: rápido con la sonda de vapor.

Las 4 condiciones de falla (debounce de 3 lecturas) cambian de referencia:
- **Temp alta / temp baja**: comparan contra `self._temp_principal()`
  (antes: `temp_camara`/referencia). Si `_temp_principal()` es `None`, la
  fase devuelve `EN_CURSO` sin evaluar fallas ese tick (mismo patrón que ya
  existe hoy cuando `temp`/`pres` son `None`).
- **Presión alta / presión baja**: sin cambios, siguen contra `pres_camara`
  — no existe una segunda sonda de presión.

### F0 (`ControlLoop._acumular_f0`, `services/domain/loop/control_loop.py`)

Reemplaza la lógica actual (`cap.has_liquid_sensor` + `min(temp_camara,
temp_2_camara)`) por `T_ref = self.estado.sensores_temp.get(cycle.get_principal_sensor())`,
leyendo el ciclo activo desde donde ya esté disponible en `ControlLoop`
(mismo objeto `cycle` que usan las fases). Se elimina el `min()`: ya no
hace falta, porque el rol `principal` ya identifica explícitamente la sonda
relevante para la letalidad real. `cap.has_liquid_sensor` deja de
consultarse en esta función (queda vigente solo como filtro de candidatos
en la pantalla "Sensores de temperatura", ver abajo).

### Impresión de ticket (`services/domain/logging/cycle_logger.py`)

La lectura fija `self.estado.sensores_temp.get("temp_camara")` (línea 296)
pasa a resolver `cycle.get_principal_sensor()` **solo cuando la fase activa
es `"ESTERILIZACION"`**; en el resto del ciclo (precalentamiento, purga,
calentamiento, secado, etc.) se mantiene `temp_camara` como hoy, porque el
rol de sensor no aplica fuera de calentamiento/esterilización. El pie del
ticket ("Temp. final") sigue el mismo criterio: usa la última lectura
registrada según esa misma regla.

## UI (`ui_pyside`)

### Navegación

`AdminMenuView._OPTION_ROUTES["Parámetros del ciclo"]` deja de apuntar a
`"params_ciclo"` y apunta a un nuevo `"params_ciclo_menu"`.

Nueva vista `ParametrosCicloMenuView` (mismo patrón de las vistas existentes:
constructor recibe `nav_callback`, botón "←" vuelve a `"admin_menu"`): 3
botones —

- **Sensores de temperatura** → `"sensores_temperatura_ciclo"`
- **Entradas exhibidas** → `"entradas_exhibidas_ciclo"`
- **Fases del ciclo** → `"params_ciclo"` (la vista `ParametrosCicloView`
  existente, sin cambios internos — solo cambia quién navega hacia ella)

Es solo navegación — no pasa contexto de ciclo seleccionado. Cada una de las
3 pantallas destino mantiene su propio combo de selección de ciclo,
recargado en `showEvent` (mismo patrón que `ParametrosCicloView._reload_cycles`).

### Pantalla "Sensores de temperatura" (`SensoresTemperaturaView`, nueva)

Header + botón atrás (→ `"params_ciclo_menu"`) + combo de ciclo (igual
estilo que `ParametrosCicloView`). Cuerpo: una fila por sensor candidato:

- `temp_camara` — siempre.
- `temp_ref` — siempre.
- `temp_2_camara` — solo si `cap.has_liquid_sensor` es `True` para la
  clase de equipo instalada (`InstallationProfile.equipment_class` vía
  `installation/storage.py` + `installation/equipment.py`).

Cada fila: nombre formateado + 3 opciones excluyentes (radio buttons o
equivalente): **Principal / Referencia / No en uso**, reflejando
`cycle.sensor_roles`. Marcar "Principal" en una fila desmarca
automáticamente cualquier otra fila que lo tuviera (un solo grupo de
exclusión para ese rol específico; Referencia y No en uso no tienen esa
restricción entre sí, salvo que solo puede haber una fila en "Referencia"
también — un sensor por rol, ningún rol repetido salvo "no en uso"). Cada
cambio dispara `PATCH /cycle/sensor-roles` de inmediato (guardar al cambiar,
igual que el resto de parámetros del ciclo hoy). Solo editable si
`cycle.source == "user"` — ciclos `factory` se muestran de solo lectura,
mismo criterio que el resto de la pantalla de parámetros.

### Pantalla "Entradas exhibidas" (`EntradasExhibidasView`, nueva)

Header + botón atrás + combo de ciclo. Cuerpo: 3 casillas, cada una un combo
con todos los sensores analógicos disponibles (`map_temp` completo:
cámara, cámara_2 si aplica, referencia, chaqueta, drenaje_cámara, drenaje;
más `map_pres` completo: cámara, chaqueta, empaque_1, empaque_2) más la
opción "— vacío —". Las 3 casillas son independientes entre sí (se permite
repetir un sensor en más de una). Cada cambio dispara
`PATCH /cycle/display-slots` de inmediato. Mismo criterio de solo-lectura
para ciclos `factory`.

## Backend (`backend/server.py`)

Dos endpoints nuevos, mismo estilo que el ya existente
`PATCH /cycle/parameter` (valida, aplica sobre el `Cycle` en memoria,
persiste solo si `source == "user"`, auto-commit vía `git_autocommit`):

```python
class _SensorRolesBody(BaseModel):
    cycle_id: str
    sensor_roles: dict[str, str]

@app.patch("/cycle/sensor-roles")
def update_sensor_roles(body: _SensorRolesBody):
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(404, ...)
    try:
        cycle.set_sensor_roles(body.sensor_roles)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_sensor_roles(cycle)
    return {"ok": True}


class _DisplaySlotsBody(BaseModel):
    cycle_id: str
    display_slots: list[str | None]

@app.patch("/cycle/display-slots")
def update_display_slots(body: _DisplaySlotsBody):
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(404, ...)
    try:
        cycle.set_display_slots(body.display_slots)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_display_slots(cycle)
    return {"ok": True}
```

`_save_cycle_sensor_roles`/`_save_cycle_display_slots` siguen el mismo
patrón que `_save_cycle_json`: releen el JSON del disco, sobrescriben solo
su clave top-level correspondiente (`cycle_temperature_sensors` /
`cycle_display_slots`), y llaman `git_autocommit`.

## Compatibilidad hacia atrás

Cualquier ciclo sin `cycle_temperature_sensors` configurado (o con todos los
sensores en `no_en_uso`) se comporta exactamente igual que hoy:
`get_principal_sensor()` devuelve `"temp_camara"`, `get_referencia_sensor()`
devuelve `None`, `_temp_control()` resuelve a `temp_camara`, y el nuevo gate
de saturación en `CalentamientoFase` no se evalúa (no hay referencia
distinta). Ningún perfil de ciclo existente cambia de comportamiento salvo
que alguien asigne explícitamente un rol `referencia`.

## Fuera de alcance

- La pantalla QML de "ciclo en curso" que realmente muestre las 3 entradas
  exhibidas en tiempo real — esta spec solo deja la configuración y los
  endpoints listos.
- El campo `io_enabled` de `config/instances/*.yaml` (lista de sensores
  físicamente cableados por instalación) — hoy no lo lee ningún código; no
  se usa como filtro en esta spec (se usa `cap.has_liquid_sensor` en su
  lugar, que sí está wireado). Conectar `io_enabled` de verdad queda para
  otra spec si se necesita filtrar por cableado real en vez de por clase de
  equipo.
- `bleve_protection`/`cooling_mode_max` de `EquipmentCapabilities` — no
  tocados, siguen sin consumidores.

## Testing

- `tests/test_calentamiento_fase.py`: casos existentes deben seguir
  pasando sin cambios (sin `sensor_roles`, comportamiento idéntico). Casos
  nuevos: con `referencia` configurada, el duty se calcula sobre la
  referencia; `ESTABLE_PREESTERILIZACION` no completa hasta que el
  principal valide saturación aunque la referencia ya esté en banda.
- `tests/test_esterilizacion_fase.py`: casos nuevos con `principal` !=
  sensor de control — las fallas de temperatura deben disparar por el
  principal, no por la referencia; el PWM debe seguir reaccionando a la
  referencia.
- `tests/test_control_loop_f0.py`: actualizar para el nuevo `T_ref` basado
  en `cycle.get_principal_sensor()` en vez de `cap.has_liquid_sensor` +
  `min()`.
- `tests/test_equipment.py`: sin cambios (capabilities no se tocan).
- Nuevos tests para `Cycle.set_sensor_roles`/`set_display_slots`
  (validación de "un solo principal", nombres de sensor desconocidos).
- Nuevos tests de los dos endpoints de `backend/server.py` (happy path +
  422 en validaciones).
