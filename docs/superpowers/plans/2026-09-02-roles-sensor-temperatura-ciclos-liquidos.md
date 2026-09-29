# Roles de sensor de temperatura para ciclos líquidos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que cada perfil de ciclo asigne un rol (principal/referencia/no en uso) a sus sensores de cámara/referencia, cablear ese rol al control real de CALENTAMIENTO/ESTERILIZACION/F0/impresión, y agregar las pantallas de configuración (sensores de temperatura + entradas exhibidas) que lo hacen usable.

**Architecture:** `Cycle` (core/managers/cycle_manager.py) gana `sensor_roles`/`display_slots` cargados del JSON del ciclo y expuestos vía `get_principal_sensor()`/`get_referencia_sensor()`. `BaseFase` gana helpers que resuelven esos roles a lecturas reales de sensor. `CalentamientoFase`, `EsterilizacionFase`, `ControlLoop._acumular_f0` y `CycleLogger` pasan de leer `temp_camara` fijo a leer a través de esos helpers, con fallback a `temp_camara` cuando el ciclo no configura roles (compatibilidad hacia atrás). Dos endpoints PATCH nuevos en el backend FastAPI persisten los roles. Tres vistas nuevas en `ui_pyside` (submenú + 2 pantallas de configuración) siguen el patrón ya establecido por `ParametrosCicloView`/`io_temp.py` (nav_callback string-based, `BackendClient` para PATCH, combo de ciclo recargado en `showEvent`).

**Tech Stack:** Python 3.14, FastAPI + Pydantic (backend), PySide6 + PySide6-Fluent-Widgets (UI), pytest + `unittest.mock` (tests), `fastapi.testclient.TestClient` (tests de endpoints).

**Spec:** `docs/superpowers/specs/2026-09-02-roles-sensor-temperatura-ciclos-liquidos-design.md`

## Global Constraints

- Ciclos sin `cycle_temperature_sensors` configurado deben comportarse exactamente igual que hoy (`get_principal_sensor()` → `"temp_camara"`, `get_referencia_sensor()` → `None`). Ningún test existente puede empezar a fallar por este cambio.
- A lo sumo un sensor puede tener el rol `"principal"` en un ciclo — se valida al persistir (`ValueError` / HTTP 422), nunca se muta parcialmente ante un rechazo.
- Solo los ciclos con `source == "user"` persisten cambios a disco (mismo criterio que `/cycle/parameter` ya usa).
- Todo temporizador de proceso sigue usando `time.monotonic()` — este plan no introduce temporizadores nuevos, pero cualquier código tocado debe mantener esa convención si la tiene.
- La UI se implementa únicamente en `ui_pyside` — no tocar `ui/` (Tkinter) ni `ui_qml/`.

---

## Task 1: `Cycle` — roles de sensor y entradas exhibidas

**Files:**
- Modify: `src/autoclave/core/managers/cycle_manager.py`
- Test: `tests/test_cycle_sensor_roles.py` (crear)

**Interfaces:**
- Produces: `Cycle.sensor_roles: dict[str, str]`, `Cycle.display_slots: list[str | None]`, `Cycle.get_principal_sensor() -> str`, `Cycle.get_referencia_sensor() -> str | None`, `Cycle.set_sensor_roles(roles: dict[str, str]) -> None` (lanza `ValueError`), `Cycle.set_display_slots(slots: list[str | None]) -> None` (lanza `ValueError`).
- Consumes: `EstadoAutoclave.map_temp` / `EstadoAutoclave.map_pres` (`src/autoclave/core/runtime/status.py`) para validar nombres de sensor conocidos.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_cycle_sensor_roles.py`:

```python
import pytest
from autoclave.core.managers.cycle_manager import Cycle


def _cycle(sensor_roles=None, display_slots=None):
    return Cycle(
        cycle_id="test", name="Test", parameters={},
        sensor_roles=sensor_roles, display_slots=display_slots,
    )


def test_get_principal_sensor_por_defecto_sin_roles_configurados():
    cycle = _cycle()
    assert cycle.get_principal_sensor() == "temp_camara"


def test_get_principal_sensor_devuelve_el_marcado():
    cycle = _cycle(sensor_roles={"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.get_principal_sensor() == "temp_2_camara"


def test_get_referencia_sensor_none_si_no_hay_ninguno():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    assert cycle.get_referencia_sensor() is None


def test_get_referencia_sensor_devuelve_el_marcado():
    cycle = _cycle(sensor_roles={"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.get_referencia_sensor() == "temp_camara"


def test_display_slots_por_defecto_vacio():
    cycle = _cycle()
    assert cycle.display_slots == [None, None, None]


def test_set_sensor_roles_actualiza_el_dict():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    cycle.set_sensor_roles({"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.sensor_roles == {"temp_camara": "referencia", "temp_2_camara": "principal"}


def test_set_sensor_roles_rechaza_dos_principales():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"temp_camara": "principal", "temp_2_camara": "principal"})
    # no debe mutar ante el rechazo
    assert cycle.sensor_roles == {"temp_camara": "principal"}


def test_set_sensor_roles_rechaza_sensor_desconocido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"sensor_inventado": "principal"})


def test_set_sensor_roles_rechaza_rol_invalido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"temp_camara": "rol_inventado"})


def test_set_sensor_roles_acepta_no_en_uso_repetido():
    cycle = _cycle()
    cycle.set_sensor_roles({"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"})
    assert cycle.sensor_roles == {"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"}


def test_set_display_slots_actualiza_la_lista():
    cycle = _cycle()
    cycle.set_display_slots(["temp_camara", "pres_camara", None])
    assert cycle.display_slots == ["temp_camara", "pres_camara", None]


def test_set_display_slots_rechaza_longitud_incorrecta():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_display_slots(["temp_camara", "pres_camara"])


def test_set_display_slots_rechaza_sensor_desconocido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_display_slots(["sensor_inventado", None, None])


def test_set_display_slots_acepta_sensor_de_presion():
    cycle = _cycle()
    cycle.set_display_slots(["pres_empaque_1", None, None])
    assert cycle.display_slots == ["pres_empaque_1", None, None]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cycle_sensor_roles.py -v`
Expected: FAIL — `TypeError: Cycle.__init__() got an unexpected keyword argument 'sensor_roles'`

- [ ] **Step 3: Implementar `Cycle.sensor_roles`/`display_slots`**

En `src/autoclave/core/managers/cycle_manager.py`, reemplazar la clase `Cycle` completa:

```python
_ROLES_SENSOR_VALIDOS = {"principal", "referencia", "no_en_uso"}


class Cycle:
    def __init__(self, cycle_id: str, name: str, parameters: dict,
                 sensor_roles: dict | None = None,
                 display_slots: list | None = None):
        self.id = cycle_id
        self.name = name
        self.parameters = parameters
        self.sensor_roles = sensor_roles or {}
        self.display_slots = display_slots or [None, None, None]

    def get_param(self, *keys, default=None):
        data = self.parameters

        for key in keys:
            data = data.get(key, {})

        return data.get("value", default)

    def set_param(self, fase: str, path: list[str], value):
        """Actualiza el 'value' de un parámetro navegando fase + path, coercionando
        y validando contra el 'type'/'min'/'max' propio del JSON del ciclo.
        Devuelve el valor ya coercionado. No muta nada si la validación falla."""
        section = self.parameters.get(fase)
        if section is None:
            raise KeyError(f"El ciclo no tiene la sección '{fase}'")

        node = section
        for key in path[:-1]:
            if not isinstance(node, dict) or key not in node:
                raise KeyError(f"Ruta de parámetro inválida: {'.'.join(path)}")
            node = node[key]

        leaf_key = path[-1]
        if not isinstance(node, dict) or leaf_key not in node or "value" not in node[leaf_key]:
            raise KeyError(f"El parámetro '{'.'.join(path)}' no existe en '{fase}'")

        leaf = node[leaf_key]
        param_type = leaf.get("type", "int")

        if param_type == "bool":
            coerced = bool(value)
        elif param_type == "float":
            coerced = float(value)
        else:
            coerced = int(value)

        if param_type != "bool":
            pmin, pmax = leaf.get("min"), leaf.get("max")
            if pmin is not None and coerced < pmin:
                raise ValueError(f"'{leaf_key}' fuera de rango (mínimo {pmin})")
            if pmax is not None and coerced > pmax:
                raise ValueError(f"'{leaf_key}' fuera de rango (máximo {pmax})")

        leaf["value"] = coerced
        return coerced

    def get_principal_sensor(self) -> str:
        for sensor, rol in self.sensor_roles.items():
            if rol == "principal":
                return sensor
        return "temp_camara"

    def get_referencia_sensor(self) -> str | None:
        for sensor, rol in self.sensor_roles.items():
            if rol == "referencia":
                return sensor
        return None

    def set_sensor_roles(self, roles: dict) -> None:
        from autoclave.core.runtime.status import EstadoAutoclave
        sensores_validos = set(EstadoAutoclave.map_temp.keys())

        principales = 0
        for sensor, rol in roles.items():
            if sensor not in sensores_validos:
                raise ValueError(f"Sensor desconocido: '{sensor}'")
            if rol not in _ROLES_SENSOR_VALIDOS:
                raise ValueError(f"Rol inválido para '{sensor}': '{rol}'")
            if rol == "principal":
                principales += 1

        if principales > 1:
            raise ValueError("Solo puede haber un sensor 'principal'")

        self.sensor_roles = dict(roles)

    def set_display_slots(self, slots: list) -> None:
        from autoclave.core.runtime.status import EstadoAutoclave

        if len(slots) != 3:
            raise ValueError("display_slots debe tener exactamente 3 elementos")

        sensores_validos = set(EstadoAutoclave.map_temp.keys()) | set(EstadoAutoclave.map_pres.keys())
        for slot in slots:
            if slot is not None and slot not in sensores_validos:
                raise ValueError(f"Sensor desconocido: '{slot}'")

        self.display_slots = list(slots)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_cycle_sensor_roles.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Cargar los dos campos desde el JSON en `_load_from_folder`**

En `src/autoclave/core/managers/cycle_manager.py`, dentro de `CycleManager._load_from_folder`, ubicar:

```python
                        cycle = Cycle(
                            cycle_id=data["cycle_id"],
                            name=data.get("display_name", data.get("cycle_name", data["cycle_id"])),
                            parameters=data.get("parameters", {})
                        )
```

Reemplazar por:

```python
                        cycle = Cycle(
                            cycle_id=data["cycle_id"],
                            name=data.get("display_name", data.get("cycle_name", data["cycle_id"])),
                            parameters=data.get("parameters", {}),
                            sensor_roles=data.get("cycle_temperature_sensors", {}),
                            display_slots=data.get("cycle_display_slots", [None, None, None]),
                        )
```

- [ ] **Step 6: Correr toda la suite de `cycle_manager`/`cycle_set_param` para confirmar que no se rompió nada**

Run: `pytest tests/test_cycle_set_param.py tests/test_cycle_sensor_roles.py -v`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/core/managers/cycle_manager.py tests/test_cycle_sensor_roles.py
git commit -m "feat: Cycle expone roles de sensor de temperatura y entradas exhibidas"
```

---

## Task 2: Actualizar los 5 perfiles JSON de ciclo al nuevo formato

**Files:**
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/user/bowe_dick.json`
- Modify: `src/autoclave/cycles/user/instrumental_121.json`
- Modify: `src/autoclave/cycles/user/instrumental_134.json`
- Test: `tests/test_cycle_manager_carga_roles_de_sensor.py` (crear)

**Interfaces:**
- Consumes: `CycleManager.load_all_cycles()`, `Cycle.get_principal_sensor()` (Task 1).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_cycle_manager_carga_roles_de_sensor.py`:

```python
from autoclave.core.managers.cycle_manager import CycleManager


def _cargar_ciclos():
    cm = CycleManager()
    cm.load_all_cycles()
    return cm


def test_todos_los_perfiles_cargan_sin_excepcion():
    cm = _cargar_ciclos()
    assert len(cm.cycles) == 5


def test_perfiles_existentes_no_configuran_liquido_por_defecto():
    """Los 5 perfiles actuales son de sólidos: el principal por defecto debe
    seguir siendo temp_camara y no debe haber referencia configurada."""
    cm = _cargar_ciclos()
    for cycle in cm.cycles.values():
        assert cycle.get_principal_sensor() == "temp_camara", cycle.id
        assert cycle.get_referencia_sensor() is None, cycle.id


def test_perfiles_traen_display_slots_de_longitud_3():
    cm = _cargar_ciclos()
    for cycle in cm.cycles.values():
        assert len(cycle.display_slots) == 3, cycle.id
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_cycle_manager_carga_roles_de_sensor.py -v`
Expected: FAIL en `test_perfiles_existentes_no_configuran_liquido_por_defecto` — el JSON actual trae `cycle_temperature_sensors: {"1": "temp_camara", "2": "temp_ref"}`, que con las claves `"1"`/`"2"` no coincide con ningún sensor real, así que `get_principal_sensor()` ya devuelve `"temp_camara"` por el fallback (este test en particular podría pasar por accidente) — pero `test_perfiles_traen_display_slots_de_longitud_3` FALLA porque `cycle_display_slots` todavía no existe en ningún JSON y el default es `[None, None, None]` (ese sí pasaría). Confirmar con la corrida real cuál falla antes de continuar; el objetivo de este step es solo dejar constancia del estado antes de editar los JSON.

- [ ] **Step 3: Actualizar los 5 archivos JSON**

En cada uno de los 5 archivos, reemplazar:

```json
    "cycle_temperature_sensors": {
        "1":"temp_camara",
        "2":"temp_ref"
    },
```

(o la variante equivalente que tenga cada archivo) por:

```json
    "cycle_temperature_sensors": {
        "temp_camara": "principal",
        "temp_2_camara": "no_en_uso",
        "temp_ref": "no_en_uso"
    },
    "cycle_display_slots": [null, null, null],
```

Aplicar el mismo reemplazo en los 5 archivos listados en "Files" arriba.

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `pytest tests/test_cycle_manager_carga_roles_de_sensor.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/cycles/factory/*.json src/autoclave/cycles/user/*.json tests/test_cycle_manager_carga_roles_de_sensor.py
git commit -m "chore: migrar cycle_temperature_sensors al formato sensor->rol y agregar cycle_display_slots"
```

---

## Task 3: `BaseFase` — helpers de resolución de rol

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/base_fase.py`
- Test: `tests/test_base_fase_sensor_roles.py` (crear)

**Interfaces:**
- Consumes: `Cycle.get_principal_sensor()`, `Cycle.get_referencia_sensor()` (Task 1).
- Produces: `BaseFase._temp_principal() -> float | None`, `BaseFase._temp_referencia() -> float | None`, `BaseFase._temp_control() -> float | None`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_base_fase_sensor_roles.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.base_fase import BaseFase


def _fase(sensores_temp, principal="temp_camara", referencia=None):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp
    cycle = MagicMock()
    cycle.get_principal_sensor.return_value = principal
    cycle.get_referencia_sensor.return_value = referencia
    return BaseFase(estado, MagicMock(), cycle, MagicMock(), MagicMock(), MagicMock())


def test_temp_principal_lee_el_sensor_marcado_como_principal():
    fase = _fase({"temp_camara": 100.0, "temp_2_camara": 80.0}, principal="temp_2_camara")
    assert fase._temp_principal() == 80.0


def test_temp_principal_none_si_el_sensor_no_tiene_lectura():
    fase = _fase({"temp_camara": 100.0}, principal="temp_2_camara")
    assert fase._temp_principal() is None


def test_temp_referencia_none_si_no_hay_ninguna_configurada():
    fase = _fase({"temp_camara": 100.0}, referencia=None)
    assert fase._temp_referencia() is None


def test_temp_referencia_lee_el_sensor_marcado():
    fase = _fase({"temp_camara": 100.0, "temp_ref": 90.0}, referencia="temp_ref")
    assert fase._temp_referencia() == 90.0


def test_temp_control_usa_principal_sin_referencia_configurada():
    fase = _fase({"temp_camara": 100.0}, principal="temp_camara", referencia=None)
    assert fase._temp_control() == 100.0


def test_temp_control_usa_referencia_cuando_esta_configurada():
    fase = _fase(
        {"temp_camara": 100.0, "temp_2_camara": 80.0},
        principal="temp_2_camara", referencia="temp_camara",
    )
    assert fase._temp_control() == 100.0
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_base_fase_sensor_roles.py -v`
Expected: FAIL — `AttributeError: 'BaseFase' object has no attribute '_temp_principal'`

- [ ] **Step 3: Implementar los helpers**

En `src/autoclave/state_machine/cycle_phases/base_fase.py`, agregar debajo de `_temp_camara_2`:

```python
    def _temp_principal(self) -> float | None:
        return self.estado.sensores_temp.get(self.cycle.get_principal_sensor())

    def _temp_referencia(self) -> float | None:
        sensor = self.cycle.get_referencia_sensor()
        return self.estado.sensores_temp.get(sensor) if sensor else None

    def _temp_control(self) -> float | None:
        """Sensor que alimenta el lazo de control de vapor: la referencia si
        hay una configurada (reacciona rápido — sonda de vapor), si no el
        principal (que por defecto es temp_camara — comportamiento actual
        sin cambios para ciclos de un solo sensor)."""
        if self.cycle.get_referencia_sensor():
            return self._temp_referencia()
        return self._temp_principal()
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_base_fase_sensor_roles.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/base_fase.py tests/test_base_fase_sensor_roles.py
git commit -m "feat: BaseFase resuelve sensor principal/referencia/control por rol"
```

---

## Task 4: `CalentamientoFase` — control por referencia, gate de saturación por principal

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py`
- Modify: `tests/test_calentamiento_fase.py`

**Interfaces:**
- Consumes: `BaseFase._temp_control()`, `BaseFase._temp_principal()`, `BaseFase._verificar_vapor_saturado()` (Task 3, y método ya existente en `base_fase.py`), `Cycle.get_referencia_sensor()` (Task 1).

- [ ] **Step 1: Actualizar el fixture `_make_fase` de los tests existentes (sin romper ninguno)**

En `tests/test_calentamiento_fase.py`, en la firma de `_make_fase` agregar dos parámetros nuevos con default que preserva el comportamiento actual:

```python
def _make_fase(t_obj=134.0, presion_add=11.0, timeout_min=60,
               factor=50.0, rango=2.0, tasa_calentamiento=0.0, tasa_presion=0.0,
               tiempo_estable=0, intervalo=2, t_inicial=20.0,
               escape_lento_on=1, escape_lento_off=0,
               escape_rapido_on=0, escape_rapido_off=10,
               rango_temp_estabilizacion=1.0, timeout_recuperacion_estabilizacion=5,
               principal_sensor="temp_camara", referencia_sensor=None):
```

Y justo después de `cycle.get_param.side_effect = get_param`, agregar:

```python
    cycle.get_principal_sensor.return_value = principal_sensor
    cycle.get_referencia_sensor.return_value = referencia_sensor
```

- [ ] **Step 2: Correr toda la suite existente y confirmar que sigue pasando (regresión cero)**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — todos los tests existentes deben seguir en verde, ya que `principal_sensor="temp_camara"`/`referencia_sensor=None` reproduce exactamente el comportamiento actual.

- [ ] **Step 3: Agregar los tests nuevos que fallan**

Al final de `tests/test_calentamiento_fase.py`, agregar:

```python
# ── Roles de sensor (referencia controla, principal valida saturación) ──────

def test_duty_sigue_a_la_referencia_no_al_principal():
    fase, estado, set_do = _make_fase(
        t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0,
        referencia_sensor="temp_camara", principal_sensor="temp_2_camara",
    )
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 20.0     # referencia lejos -> debe seguir rampeando
    estado.sensores_temp["temp_2_camara"] = 134.0    # principal ya "caliente" pero no debe importar aquí
    estado.sensores_pres["pres_camara"] = 100.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0


def test_no_completa_hasta_que_el_principal_valide_saturacion_de_vapor():
    fase, estado, set_do = _make_fase(
        t_obj=134.0, presion_add=0.0, rango=2.0, tiempo_estable=0,
        referencia_sensor="temp_camara", principal_sensor="temp_2_camara",
    )
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0)
    estado.sensores_temp["temp_camara"] = 134.0      # referencia ya en objetivo
    estado.sensores_pres["pres_camara"] = p_obj
    estado.sensores_temp["temp_2_camara"] = 100.0     # principal (líquido) todavía frío
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_completa_cuando_el_principal_tambien_valida_saturacion():
    fase, estado, set_do = _make_fase(
        t_obj=134.0, presion_add=0.0, rango=2.0, tiempo_estable=0,
        referencia_sensor="temp_camara", principal_sensor="temp_2_camara",
    )
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0)
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    estado.sensores_temp["temp_2_camara"] = 134.0     # principal ya corresponde a vapor saturado
    result = fase.update()
    assert result == FaseResult.COMPLETADO
```

- [ ] **Step 4: Correr los tests nuevos y verificar que fallan**

Run: `pytest tests/test_calentamiento_fase.py -v -k "duty_sigue_a_la_referencia or no_completa_hasta_que or completa_cuando_el_principal"`
Expected: FAIL en las tres — el código todavía usa `_temp_camara()` fijo, no hay gate de saturación.

- [ ] **Step 5: Implementar el cambio en `calentamiento.py`**

Ubicar (dentro de `update()`, sección 2):

```python
        temp = self._temp_camara()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO
```

Reemplazar por:

```python
        temp = self._temp_control()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO
```

Agregar el nuevo helper, después de `_apagar_salidas`:

```python
    def _principal_en_saturacion(self, pres: float, tolerancia: float) -> bool:
        """True si no hay una sonda de referencia distinta configurada (nada
        que verificar — comportamiento actual sin cambios), o si la sonda
        principal ya corresponde a vapor saturado contra la presión real de
        cámara. False bloquea el COMPLETADO sin fallar — mismo patrón de
        riesgo aceptado que el resto de la fase."""
        if self.cycle.get_referencia_sensor() is None:
            return True
        principal = self._temp_principal()
        if principal is None:
            return False
        return self._verificar_vapor_saturado(principal, pres, tolerancia)
```

Ubicar, en la sección 7 (entrada y control de `ESTABLE_PREESTERILIZACION`):

```python
            self.estado.fase_en_sostenimiento = True
            if now - self._timer_sostenido_desde >= tiempo_est:
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento continuo de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
```

Reemplazar por:

```python
            self.estado.fase_en_sostenimiento = True
            if now - self._timer_sostenido_desde >= tiempo_est:
                if not self._principal_en_saturacion(pres, rango_cal):
                    return FaseResult.EN_CURSO
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento continuo de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
```

- [ ] **Step 6: Correr toda la suite y verificar que todo pasa**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — todos los tests, incluidos los preexistentes y los 3 nuevos.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: CalentamientoFase controla por sonda de referencia y valida saturacion del principal antes de completar"
```

---

## Task 5: `EsterilizacionFase` — control por referencia, fallas por principal

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/esterilizacion.py`
- Modify: `tests/test_esterilizacion_fase.py`

**Interfaces:**
- Consumes: `BaseFase._temp_control()`, `BaseFase._temp_principal()` (Task 3).

- [ ] **Step 1: Actualizar el fixture `_make_fase` (sin romper tests existentes)**

En `tests/test_esterilizacion_fase.py`, agregar dos parámetros a la firma de `_make_fase`:

```python
def _make_fase(t_est=134.0, tiempo_min=3.5, factor=70.0, presion_add=11.0,
               intervalo=3, rango_temp=3.0, rango_pres=30.0,
               brecha_seg=0.3, brecha_seg_p=1.5, brecha_err_t=0.1, brecha_err_p=2.0,
               escape_lento_on=1, escape_lento_off=0,
               escape_rapido_on=0, escape_rapido_off=400,
               t_inicial=None, p_inicial=None,
               f0_activo=False, f0_objetivo=12.0, f0_acumulado_inicial=0.0,
               principal_sensor="temp_camara", referencia_sensor=None):
```

Y después de `cycle.get_param.side_effect = get_param`, agregar:

```python
    cycle.get_principal_sensor.return_value = principal_sensor
    cycle.get_referencia_sensor.return_value = referencia_sensor
```

- [ ] **Step 2: Correr toda la suite existente y confirmar regresión cero**

Run: `pytest tests/test_esterilizacion_fase.py -v`
Expected: PASS — todos los tests existentes en verde.

- [ ] **Step 3: Agregar los tests nuevos que fallan**

Al final de `tests/test_esterilizacion_fase.py`, agregar:

```python
# ── Roles de sensor (referencia controla el PWM, principal decide fallas) ───

def test_temp_baja_dispara_falla_segun_el_principal_no_la_referencia():
    fase, estado, set_do = _make_fase(
        t_est=134.0, brecha_err_t=0.1,
        referencia_sensor="temp_camara", principal_sensor="temp_2_camara",
    )
    estado.sensores_temp["temp_2_camara"] = 130.0  # principal muy por debajo -> debe fallar
    result = None
    for _ in range(3):
        result = fase.update()
    assert result == FaseResult.FALLO
    assert "Temperatura baja" in estado.motivo_fallo


def test_pwm_activo_reacciona_a_la_referencia_no_al_principal():
    fase, estado, set_do = _make_fase(
        t_est=134.0, brecha_seg=0.3, brecha_seg_p=1.5,
        referencia_sensor="temp_camara", principal_sensor="temp_2_camara",
    )
    fase.update()  # inicializa en RECUPERACION
    estado.sensores_temp["temp_camara"] = 135.0         # referencia ya por encima de la brecha segura
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
    estado.sensores_temp["temp_2_camara"] = 100.0        # principal (líquido) todavía muy frío
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is False  # el líquido frío no debe forzar RECUPERACION
```

- [ ] **Step 4: Correr los tests nuevos y verificar que fallan**

Run: `pytest tests/test_esterilizacion_fase.py -v -k "temp_baja_dispara_falla_segun_el_principal or pwm_activo_reacciona_a_la_referencia"`
Expected: FAIL en las dos — el código todavía compara siempre contra `temp_camara`.

- [ ] **Step 5: Implementar el cambio en `esterilizacion.py`**

Ubicar (dentro de `update()`, sección 1→2):

```python
        temp = self._temp_camara()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO

        now = time.monotonic()

        # ── 2. Chequeo de fallas (debounce 3, referencia fija t_est) ───────
        if temp > t_est + rango_temp:
            self._contador_temp_alta += 1
        else:
            self._contador_temp_alta = 0
        if self._contador_temp_alta >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura alta: {temp:.1f}°C > {t_est + rango_temp:.1f}°C"
            )

        if temp < t_est - brecha_err_t:
            self._contador_temp_baja += 1
        else:
            self._contador_temp_baja = 0
        if self._contador_temp_baja >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura baja: {temp:.1f}°C < {t_est - brecha_err_t:.1f}°C"
            )
```

Reemplazar por:

```python
        temp_control = self._temp_control()
        temp_principal = self._temp_principal()
        pres = self._pres_camara()
        if temp_control is None or temp_principal is None or pres is None:
            return FaseResult.EN_CURSO

        now = time.monotonic()

        # ── 2. Chequeo de fallas (debounce 3, referencia fija t_est, sonda
        # principal — es la que puede sobrecalentarse o enfriarse de verdad) ─
        if temp_principal > t_est + rango_temp:
            self._contador_temp_alta += 1
        else:
            self._contador_temp_alta = 0
        if self._contador_temp_alta >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura alta: {temp_principal:.1f}°C > {t_est + rango_temp:.1f}°C"
            )

        if temp_principal < t_est - brecha_err_t:
            self._contador_temp_baja += 1
        else:
            self._contador_temp_baja = 0
        if self._contador_temp_baja >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura baja: {temp_principal:.1f}°C < {t_est - brecha_err_t:.1f}°C"
            )
```

Ubicar (sección 3→4, sin cambios en las fallas de presión que van entre medio):

```python
        # ── 3. Transición bidireccional RECUPERACION↔PWM_ACTIVO ────────────
        # Sin chattering-guard: reacción inmediata ante pérdida de reserva
        # térmica o de presión es el objetivo de diseño (plan sección 4.1).
        # La presión también dispara RECUPERACION: la temperatura puede
        # mantenerse cerca del setpoint mientras la presión sola cae por la
        # fuga continua de descompresion_lenta, y sin este chequeo el modo
        # agresivo (sin techo de control) nunca se activaba en ese caso.
        self._en_recuperacion = (
            temp < t_est + brecha_seg
            or pres < p_sat_est - brecha_seg_p
        )

        # ── 4. Control de vapor_camara ─────────────────────────────────────
        if self._en_recuperacion:
            self.set_do.vapor_camara_on()
        else:
            self._control_vapor_pwm(temp, pres, factor_pct, intervalo, p_control_max, now)
```

Reemplazar por:

```python
        # ── 3. Transición bidireccional RECUPERACION↔PWM_ACTIVO ────────────
        # Sin chattering-guard: reacción inmediata ante pérdida de reserva
        # térmica o de presión es el objetivo de diseño (plan sección 4.1).
        # Reacciona a la sonda de control (referencia si hay una configurada,
        # si no el principal): es la sonda rápida, evita el lag térmico del
        # líquido en el lazo de control. La presión también dispara
        # RECUPERACION: la temperatura puede mantenerse cerca del setpoint
        # mientras la presión sola cae por la fuga continua de
        # descompresion_lenta, y sin este chequeo el modo agresivo (sin techo
        # de control) nunca se activaba en ese caso.
        self._en_recuperacion = (
            temp_control < t_est + brecha_seg
            or pres < p_sat_est - brecha_seg_p
        )

        # ── 4. Control de vapor_camara ─────────────────────────────────────
        if self._en_recuperacion:
            self.set_do.vapor_camara_on()
        else:
            self._control_vapor_pwm(temp_control, pres, factor_pct, intervalo, p_control_max, now)
```

- [ ] **Step 6: Correr toda la suite y verificar que todo pasa**

Run: `pytest tests/test_esterilizacion_fase.py -v`
Expected: PASS — todos los tests, incluidos los preexistentes y los 2 nuevos.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/esterilizacion.py tests/test_esterilizacion_fase.py
git commit -m "feat: EsterilizacionFase controla PWM por referencia y falla por sonda principal"
```

---

## Task 6: F0 — acumular contra el sensor principal del ciclo

**Files:**
- Modify: `src/autoclave/services/domain/loop/control_loop.py`
- Modify: `tests/test_control_loop_f0.py`

**Interfaces:**
- Consumes: `self.cycle.get_principal_sensor()` — `self.cycle` ya existe en `ControlLoop` (`control_loop.py:51`, actualizado en `set_active_cycle`).

- [ ] **Step 1: Actualizar el fixture `_make_loop` y reemplazar los 2 tests obsoletos**

En `tests/test_control_loop_f0.py`, en `_make_loop`, después de:

```python
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, nombre, default=None: {
        ("globals", "F0"): f0_activo,
    }.get((seccion, nombre), default)
```

agregar:

```python
    cycle.get_principal_sensor.return_value = "temp_camara"
```

Eliminar por completo estos dos tests (probaban el mecanismo viejo basado en `cap.has_liquid_sensor` + `min()`, que este task reemplaza):

```python
def test_usa_el_minimo_entre_ambos_sensores_cuando_hay_sensor_de_liquido():
    ...

def test_degrada_a_temp_camara_si_hay_liquido_sensor_pero_sin_lectura():
    ...
```

Reemplazarlos por:

```python
def test_usa_el_sensor_principal_configurado_en_el_ciclo():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = 100.0  # el líquido va más atrás
    loop, estado, cycle = _make_loop(estado=estado)
    cycle.get_principal_sensor.return_value = "temp_2_camara"
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    f0_con_principal_liquido = estado.f0_acumulado

    estado2 = _FakeEstado()
    estado2.sensores_temp["temp_camara"] = 134.0
    estado2.sensores_temp["temp_2_camara"] = 100.0
    loop2, estado2, cycle2 = _make_loop(estado=estado2)
    cycle2.get_principal_sensor.return_value = "temp_camara"
    loop2._acumular_f0(now=1000.0)
    loop2._acumular_f0(now=1060.0)
    f0_con_principal_vapor = estado2.f0_acumulado

    assert f0_con_principal_liquido < f0_con_principal_vapor


def test_no_acumula_si_la_lectura_del_sensor_principal_es_none():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = None
    loop, estado, cycle = _make_loop(estado=estado)
    cycle.get_principal_sensor.return_value = "temp_2_camara"
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0
```

`_make_loop` ya devuelve `loop, estado, cycle` (3 valores) — no hace falta cambiar su `return`, solo el `.get_principal_sensor.return_value` agregado arriba.

- [ ] **Step 2: Correr la suite y verificar qué falla**

Run: `pytest tests/test_control_loop_f0.py -v`
Expected: FAIL en `test_usa_el_sensor_principal_configurado_en_el_ciclo` y `test_no_acumula_si_la_lectura_del_sensor_principal_es_none` (el código todavía usa `cap.has_liquid_sensor` + `min()`); el resto sigue en PASS.

- [ ] **Step 3: Implementar el cambio en `control_loop.py`**

Ubicar `_acumular_f0` (líneas ~198-231):

```python
        temp_camara = self.estado.sensores_temp.get("temp_camara")
        if temp_camara is None:
            return

        if self.cap is not None and getattr(self.cap, "has_liquid_sensor", False):
            temp_2 = self.estado.sensores_temp.get("temp_2_camara")
            t_ref = min(temp_camara, temp_2) if temp_2 is not None else temp_camara
        else:
            t_ref = temp_camara

        dt_min = (now - ultimo) / 60.0
        self.estado.f0_acumulado += calcular_incremento_f0(t_ref, dt_min)
```

Reemplazar por:

```python
        principal_sensor = self.cycle.get_principal_sensor()
        t_ref = self.estado.sensores_temp.get(principal_sensor)
        if t_ref is None:
            return

        dt_min = (now - ultimo) / 60.0
        self.estado.f0_acumulado += calcular_incremento_f0(t_ref, dt_min)
```

- [ ] **Step 4: Correr toda la suite y verificar que todo pasa**

Run: `pytest tests/test_control_loop_f0.py -v`
Expected: PASS — 9 tests (9 preexistentes, menos los 2 eliminados en el Step 1, más los 2 nuevos agregados ahí mismo = 9 total).

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/services/domain/loop/control_loop.py tests/test_control_loop_f0.py
git commit -m "feat: F0 acumula contra el sensor principal del ciclo en vez de has_liquid_sensor+min"
```

---

## Task 7: Impresión del ticket — usar el principal durante ESTERILIZACION

**Files:**
- Modify: `src/autoclave/services/domain/logging/cycle_logger.py`
- Modify: `tests/test_cycle_logger_printer.py`

**Interfaces:**
- Consumes: `self.cycle_manager.get_selected_cycle().get_principal_sensor()` — mismo `cycle_manager` que ya usa `_on_inicio`/`_on_fin`.

- [ ] **Step 1: Actualizar los fakes del test**

En `tests/test_cycle_logger_printer.py`, reemplazar `FakeCycle` y `FakeCycleManager`:

```python
class FakeCycle:
    id = "bowe_dick"
    name = "Bowie-Dick"

    def __init__(self, f0_activo=False, principal_sensor="temp_camara"):
        self.f0_activo = f0_activo
        self.principal_sensor = principal_sensor

    def get_principal_sensor(self):
        return self.principal_sensor

    def get_param(self, *keys, default=None):
        # Replica la semántica real de Cycle.get_param: recorre las claves
        # anidadas (sección → parámetro), no sólo la última.
        data = {
            "esterilizacion": {
                "temperatura_esterilizacion": 134,
                "tiempo_esterilizacion": 3.5,
            },
            "globals": {
                "F0": self.f0_activo,
            },
        }
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key)
            if data is None:
                return default
        return data


class FakeCycleManager:
    def __init__(self, f0_activo=False, principal_sensor="temp_camara"):
        self.f0_activo = f0_activo
        self.principal_sensor = principal_sensor

    def get_selected_cycle(self):
        return FakeCycle(f0_activo=self.f0_activo, principal_sensor=self.principal_sensor)
```

- [ ] **Step 2: Correr la suite existente y confirmar regresión cero**

Run: `pytest tests/test_cycle_logger_printer.py -v`
Expected: PASS — todos los tests preexistentes siguen en verde (`principal_sensor="temp_camara"` por defecto reproduce el comportamiento actual).

- [ ] **Step 3: Agregar los tests nuevos que fallan**

Al final de `tests/test_cycle_logger_printer.py`, agregar:

```python
def test_en_esterilizacion_imprime_la_temperatura_del_sensor_principal():
    printer = FakePrinter()
    cl = _build_logger(printer, cycle_manager=FakeCycleManager(principal_sensor="temp_2_camara"))
    cl.estado.fase_ciclo = "ESTERILIZACION"
    cl.estado.sensores_temp = {"temp_camara": 134.0, "temp_2_camara": 110.0}

    cl.update()   # header
    cl.update()   # fila por cambio de fase -> "S"

    assert len(printer.calls) == 2
    assert "110.0" in printer.calls[1]
    assert "134.0" not in printer.calls[1]


def test_fuera_de_esterilizacion_sigue_usando_temp_camara():
    printer = FakePrinter()
    cl = _build_logger(printer, cycle_manager=FakeCycleManager(principal_sensor="temp_2_camara"))
    cl.estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 999.0}
    # fase_ciclo por defecto es "PRECALENTAMIENTO"

    cl.update()   # header
    cl.update()   # fila por cambio de fase -> "PH"

    assert "25.0" in printer.calls[1]
    assert "999.0" not in printer.calls[1]
```

- [ ] **Step 4: Correr los tests nuevos y verificar que fallan**

Run: `pytest tests/test_cycle_logger_printer.py -v -k "en_esterilizacion_imprime or fuera_de_esterilizacion"`
Expected: FAIL en `test_en_esterilizacion_imprime_la_temperatura_del_sensor_principal` (imprime `134.0`, no `110.0`); `test_fuera_de_esterilizacion_sigue_usando_temp_camara` ya pasa (comportamiento sin cambios ahí), confirma que el segundo test es la línea base correcta.

- [ ] **Step 5: Implementar el cambio en `cycle_logger.py`**

Ubicar, dentro de `_registrar_lectura`:

```python
        temp = self.estado.sensores_temp.get("temp_camara")
        pres = self.estado.sensores_pres.get("pres_camara")
```

Reemplazar por:

```python
        temp = self.estado.sensores_temp.get("temp_camara")
        if fase_codigo == "S":  # ESTERILIZACION — usar el sensor principal del ciclo
            try:
                cycle = self.cycle_manager.get_selected_cycle()
                temp_principal = self.estado.sensores_temp.get(cycle.get_principal_sensor())
                if temp_principal is not None:
                    temp = temp_principal
            except Exception as exc:
                logger.warning("CycleLogger: no se pudo resolver el sensor principal: %s", exc)
        pres = self.estado.sensores_pres.get("pres_camara")
```

- [ ] **Step 6: Correr toda la suite y verificar que todo pasa**

Run: `pytest tests/test_cycle_logger_printer.py -v`
Expected: PASS — todos los tests.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/services/domain/logging/cycle_logger.py tests/test_cycle_logger_printer.py
git commit -m "feat: el ticket imprime la temperatura del sensor principal durante ESTERILIZACION"
```

---

## Task 8: Backend — endpoints PATCH para roles de sensor y entradas exhibidas

**Files:**
- Modify: `src/autoclave/backend/server.py`
- Test: `tests/test_backend_cycle_sensor_config_endpoints.py` (crear)

**Interfaces:**
- Consumes: `Cycle.set_sensor_roles()`, `Cycle.set_display_slots()` (Task 1).
- Produces: `PATCH /cycle/sensor-roles`, `PATCH /cycle/display-slots`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_backend_cycle_sensor_config_endpoints.py`:

```python
import sys
import json
import importlib
import pytest
from unittest.mock import MagicMock, patch

from autoclave.core.managers.cycle_manager import Cycle


def _make_cycle(tmp_path, source="user"):
    cycle_path = tmp_path / "ciclo_test.json"
    cycle_path.write_text(
        json.dumps({
            "cycle_id": "ciclo_test", "display_name": "Test",
            "parameters": {},
            "cycle_temperature_sensors": {"temp_camara": "principal"},
            "cycle_display_slots": [None, None, None],
        }),
        encoding="utf-8",
    )
    cycle = Cycle(
        cycle_id="ciclo_test", name="Test", parameters={},
        sensor_roles={"temp_camara": "principal"},
        display_slots=[None, None, None],
    )
    cycle.source = source
    cycle._path = str(cycle_path)
    return cycle, cycle_path


@pytest.fixture
def sensor_client(tmp_path):
    cycle, cycle_path = _make_cycle(tmp_path)

    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"ciclo_test": cycle}

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), cycle, cycle_path


def test_patch_sensor_roles_actualiza_en_memoria_y_persiste(sensor_client):
    client, cycle, cycle_path = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test",
        "sensor_roles": {"temp_camara": "referencia", "temp_2_camara": "principal"},
    })
    assert resp.status_code == 200
    assert cycle.sensor_roles == {"temp_camara": "referencia", "temp_2_camara": "principal"}

    persisted = json.loads(cycle_path.read_text(encoding="utf-8"))
    assert persisted["cycle_temperature_sensors"] == {
        "temp_camara": "referencia", "temp_2_camara": "principal"
    }


def test_patch_sensor_roles_422_si_hay_dos_principales(sensor_client):
    client, cycle, _ = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test",
        "sensor_roles": {"temp_camara": "principal", "temp_2_camara": "principal"},
    })
    assert resp.status_code == 422
    assert cycle.sensor_roles == {"temp_camara": "principal"}  # sin mutar


def test_patch_sensor_roles_404_si_ciclo_no_existe(sensor_client):
    client, _, _ = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "no_existe", "sensor_roles": {},
    })
    assert resp.status_code == 404


def test_patch_display_slots_actualiza_en_memoria_y_persiste(sensor_client):
    client, cycle, cycle_path = sensor_client
    resp = client.patch("/cycle/display-slots", json={
        "cycle_id": "ciclo_test",
        "display_slots": ["temp_camara", "pres_camara", None],
    })
    assert resp.status_code == 200
    assert cycle.display_slots == ["temp_camara", "pres_camara", None]

    persisted = json.loads(cycle_path.read_text(encoding="utf-8"))
    assert persisted["cycle_display_slots"] == ["temp_camara", "pres_camara", None]


def test_patch_display_slots_422_si_longitud_incorrecta(sensor_client):
    client, _, _ = sensor_client
    resp = client.patch("/cycle/display-slots", json={
        "cycle_id": "ciclo_test", "display_slots": ["temp_camara"],
    })
    assert resp.status_code == 422


def test_patch_sensor_config_no_persiste_ciclos_factory(tmp_path):
    cycle, cycle_path = _make_cycle(tmp_path, source="factory")
    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"ciclo_test": cycle}

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    client = TestClient(srv.app)

    original = cycle_path.read_text(encoding="utf-8")
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test", "sensor_roles": {"temp_camara": "referencia"},
    })
    assert resp.status_code == 200
    assert cycle_path.read_text(encoding="utf-8") == original
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_backend_cycle_sensor_config_endpoints.py -v`
Expected: FAIL — `404 Not Found` en todos, los endpoints todavía no existen.

- [ ] **Step 3: Implementar los endpoints**

En `src/autoclave/backend/server.py`, agregar después de `_save_cycle_json` (justo antes de la sección "Direct hardware access"):

```python
class _SensorRolesBody(BaseModel):
    cycle_id: str
    sensor_roles: dict[str, str]


@app.patch("/cycle/sensor-roles")
def update_sensor_roles(body: _SensorRolesBody):
    """Actualiza los roles de sensor de temperatura (principal/referencia/
    no_en_uso) de un ciclo y persiste si es 'user'."""
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")

    try:
        cycle.set_sensor_roles(body.sensor_roles)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_sensor_roles(cycle)

    return {"ok": True}


def _save_cycle_sensor_roles(cycle) -> None:
    """Escribe cycle.sensor_roles de vuelta al JSON del ciclo (solo ciclos user)."""
    import json as _json
    from pathlib import Path as _Path

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    data["cycle_temperature_sensors"] = cycle.sensor_roles
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=4, ensure_ascii=False)
    git_autocommit(path, f"chore: actualizar roles de sensor de ciclo {cycle.id} (auto)")


class _DisplaySlotsBody(BaseModel):
    cycle_id: str
    display_slots: list[str | None]


@app.patch("/cycle/display-slots")
def update_display_slots(body: _DisplaySlotsBody):
    """Actualiza las 3 entradas exhibidas de un ciclo y persiste si es 'user'."""
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")

    try:
        cycle.set_display_slots(body.display_slots)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_display_slots(cycle)

    return {"ok": True}


def _save_cycle_display_slots(cycle) -> None:
    """Escribe cycle.display_slots de vuelta al JSON del ciclo (solo ciclos user)."""
    import json as _json
    from pathlib import Path as _Path

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    data["cycle_display_slots"] = cycle.display_slots
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=4, ensure_ascii=False)
    git_autocommit(path, f"chore: actualizar entradas exhibidas de ciclo {cycle.id} (auto)")
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_backend_cycle_sensor_config_endpoints.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Correr toda la suite de backend para confirmar que no se rompió nada**

Run: `pytest tests/test_backend_cycle_parameter_endpoint.py tests/test_backend_cycle_select_endpoint.py tests/test_backend_cycle_sensor_config_endpoints.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_backend_cycle_sensor_config_endpoints.py
git commit -m "feat: endpoints PATCH /cycle/sensor-roles y /cycle/display-slots"
```

---

## Task 9: UI — submenú "Parámetros del ciclo" y rewire de navegación

**Files:**
- Create: `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo_menu.py`
- Modify: `src/autoclave/ui_pyside/views/admin_menu.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Produces: `ParametrosCicloMenuView` (nav_callback → `"sensores_temperatura_ciclo"` / `"entradas_exhibidas_ciclo"` / `"params_ciclo"`), registrado en `main_window.py` bajo la clave `"params_ciclo_menu"`.
- Consumes: nada nuevo — mismo patrón `nav_callback` que el resto de vistas de `ui_pyside`.

Nota: las claves `"sensores_temperatura_ciclo"` y `"entradas_exhibidas_ciclo"` se registran recién en Tasks 10 y 11 — hasta entonces, navegar a esos botones no hace nada visible (`navigate_to` simplemente no encuentra la clave en el dict y no cambia de pantalla). Esto es intencional y transitorio: cada task se puede probar de forma independiente sin bloquear a las demás.

No hay tests automatizados para vistas de `ui_pyside` en este repo (no existe suite de UI para ese paquete) — este task se verifica manualmente.

- [ ] **Step 1: Crear `ParametrosCicloMenuView`**

Crear `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo_menu.py`:

```python
from collections.abc import Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_BTN_OPTION = """
    QPushButton {
        background: #f8f9fa;
        color: #1a2a3a;
        border-radius: 12px;
        border: 1.5px solid #e8eaed;
        text-align: left;
        padding-left: 16px;
        font-size: 14px;
    }
    QPushButton:hover   { background: #e8f0fe; border-color: #2563eb; }
    QPushButton:pressed { background: #dbeafe; }
"""

_OPTIONS = [
    ("🌡️", "Sensores de temperatura", "sensores_temperatura_ciclo"),
    ("📺", "Entradas exhibidas",       "entradas_exhibidas_ciclo"),
    ("🧪", "Fases del ciclo",          "params_ciclo"),
]


class ParametrosCicloMenuView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback

        self.setObjectName("paramsCicloMenuView")
        self.setStyleSheet("QWidget#paramsCicloMenuView { background: #f3f4f6; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("admin_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("PARÁMETROS DEL CICLO")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        root.addSpacing(8)

        for icon, label, target in _OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION)
            btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            root.addWidget(btn)

        root.addStretch(1)
```

- [ ] **Step 2: Rewire `admin_menu.py`**

En `src/autoclave/ui_pyside/views/admin_menu.py`, ubicar:

```python
_OPTION_ROUTES = {
    "Parámetros del ciclo": "params_ciclo",
    "Entradas / Salidas":   "io_menu",
}
```

Reemplazar por:

```python
_OPTION_ROUTES = {
    "Parámetros del ciclo": "params_ciclo_menu",
    "Entradas / Salidas":   "io_menu",
}
```

- [ ] **Step 3: Registrar la vista en `main_window.py`**

En `src/autoclave/ui_pyside/main_window.py`, agregar el import junto a los demás:

```python
        from autoclave.ui_pyside.views.params_ciclo.params_ciclo import ParametrosCicloView
        from autoclave.ui_pyside.views.params_ciclo.params_ciclo_menu import ParametrosCicloMenuView
```

Agregar la instanciación junto a `self._params_ciclo`:

```python
        self._params_ciclo = ParametrosCicloView(nav_callback=self.navigate_to)
        self._params_ciclo_menu = ParametrosCicloMenuView(nav_callback=self.navigate_to)
```

Agregar `self._params_ciclo_menu` al tuple que se recorre para `self._stack.addWidget(view)`:

```python
        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo, self._params_ciclo_menu, self._calibracion_sensor):
            self._stack.addWidget(view)
```

Agregar la entrada al dict de `navigate_to`:

```python
            "params_ciclo": self._params_ciclo,
            "params_ciclo_menu": self._params_ciclo_menu,
            "calibracion_sensor": self._calibracion_sensor,
```

- [ ] **Step 4: Verificación manual**

Con el backend corriendo (`uvicorn autoclave.backend.server:app --port 8000`, desde `src/`) y la UI (`python -m autoclave.ui_pyside.app`, desde `src/`):
1. Login → Administración → "Parámetros del ciclo" debe abrir el nuevo submenú de 3 botones (no directamente las tabs de antes).
2. El botón "Fases del ciclo" debe abrir la pantalla de tabs existente, sin cambios visibles en ella.
3. El botón "←" del submenú debe volver a "Administración".
4. Los botones "Sensores de temperatura"/"Entradas exhibidas" no navegan a nada todavía (esperado — se conectan en Tasks 10/11).

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/params_ciclo_menu.py src/autoclave/ui_pyside/views/admin_menu.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: submenu de parametros del ciclo (sensores/entradas/fases)"
```

---

## Task 10: UI — pantalla "Sensores de temperatura"

**Files:**
- Create: `src/autoclave/ui_pyside/views/params_ciclo/sensores_temperatura.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `PATCH /cycle/sensor-roles` (Task 8), `Cycle.sensor_roles`/`get_principal_sensor` (Task 1), `installation.storage`/`installation.equipment.get_capabilities` (ya existentes).
- Produces: `SensoresTemperaturaView`, registrada bajo `"sensores_temperatura_ciclo"`.

No hay tests automatizados para vistas de `ui_pyside` en este repo — este task se verifica manualmente (ver Step 3).

- [ ] **Step 1: Crear `SensoresTemperaturaView`**

Crear `src/autoclave/ui_pyside/views/params_ciclo/sensores_temperatura.py`:

```python
import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _format_name

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_CARD = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"

_ROLES = [("principal", "Principal"), ("referencia", "Referencia"), ("no_en_uso", "No en uso")]

_CANDIDATOS_SIEMPRE = ["temp_camara", "temp_ref"]


def _equipo_tiene_sonda_liquido() -> bool:
    try:
        from autoclave.installation import storage
        from autoclave.installation.equipment import get_capabilities
        if not storage.exists():
            return False
        profile = storage.load()
        return get_capabilities(profile.equipment_class).has_liquid_sensor
    except Exception:
        return False


class _SensorRoleRow(QFrame):
    def __init__(self, sensor_name: str, on_change: Callable[[str, str], None]):
        super().__init__()
        self.sensor_name = sensor_name
        self._on_change = on_change
        self.setStyleSheet(_CARD)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)

        lbl = QLabel(_format_name(sensor_name))
        lbl.setFont(QFont("Segoe UI", 12))
        lbl.setStyleSheet("border: none;")
        lay.addWidget(lbl)
        lay.addStretch()

        self._group = QButtonGroup(self)
        self._buttons: dict[str, QRadioButton] = {}
        for rol, label in _ROLES:
            rb = QRadioButton(label)
            self._group.addButton(rb)
            self._buttons[rol] = rb
            lay.addWidget(rb)
            rb.toggled.connect(lambda checked, r=rol: self._on_toggled(r, checked))

    def _on_toggled(self, rol: str, checked: bool) -> None:
        if checked:
            self._on_change(self.sensor_name, rol)

    def set_role(self, rol: str) -> None:
        btn = self._buttons.get(rol, self._buttons["no_en_uso"])
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)

    def get_role(self) -> str:
        for rol, btn in self._buttons.items():
            if btn.isChecked():
                return rol
        return "no_en_uso"


class SensoresTemperaturaView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cycles: dict = {}
        self._rows: dict[str, _SensorRoleRow] = {}
        self._cycle = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("params_ciclo_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("SENSORES DE TEMPERATURA")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(16)

        self._combo = QComboBox()
        self._combo.setFont(QFont("Segoe UI", 11))
        self._combo.setMinimumWidth(200)
        self._combo.currentIndexChanged.connect(self._on_cycle_changed)
        hdr.addWidget(self._combo)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setSpacing(8)
        self._rows_layout.addStretch(1)
        scroll.setWidget(self._rows_widget)
        root.addWidget(scroll, stretch=1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_cycles()

    def _reload_cycles(self) -> None:
        try:
            from autoclave.core.managers.cycle_manager import CycleManager
            cm = CycleManager()
            cm.load_all_cycles()
            user_cycles = [
                c for c in cm.cycles.values()
                if getattr(c, "source", "user") == "user"
            ]
            self._cycles = {c.id: c for c in user_cycles}

            self._combo.blockSignals(True)
            self._combo.clear()
            for cycle in sorted(user_cycles, key=lambda c: c.name):
                self._combo.addItem(cycle.name, cycle.id)
            self._combo.blockSignals(False)

            if user_cycles:
                self._load_cycle(sorted(user_cycles, key=lambda c: c.name)[0])
        except Exception:
            _logger.exception("Error cargando ciclos de usuario")

    def _on_cycle_changed(self, idx: int) -> None:
        cycle_id = self._combo.itemData(idx)
        cycle = self._cycles.get(cycle_id)
        if cycle:
            self._load_cycle(cycle)

    def _candidatos(self) -> list[str]:
        candidatos = list(_CANDIDATOS_SIEMPRE)
        if _equipo_tiene_sonda_liquido():
            candidatos.insert(1, "temp_2_camara")
        return candidatos

    def _load_cycle(self, cycle) -> None:
        self._cycle = cycle
        for row in self._rows.values():
            row.setParent(None)
        self._rows.clear()

        for sensor in self._candidatos():
            row = _SensorRoleRow(sensor, on_change=self._on_role_changed)
            row.set_role(cycle.sensor_roles.get(sensor, "no_en_uso"))
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._rows[sensor] = row

    def _on_role_changed(self, sensor: str, rol: str) -> None:
        if self._cycle is None:
            return

        if rol == "principal":
            for other_sensor, row in self._rows.items():
                if other_sensor != sensor and row.get_role() == "principal":
                    row.set_role("no_en_uso")
                    self._cycle.sensor_roles[other_sensor] = "no_en_uso"

        nuevos_roles = dict(self._cycle.sensor_roles)
        nuevos_roles[sensor] = rol

        try:
            self._client.patch("/cycle/sensor-roles", {
                "cycle_id": self._cycle.id,
                "sensor_roles": nuevos_roles,
            })
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar el rol:\n{detail}")
            return
        except requests.RequestException as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo contactar al backend, el cambio no se guardó:\n{e}"
            )
            return

        self._cycle.sensor_roles = nuevos_roles
```

- [ ] **Step 2: Registrar la vista en `main_window.py`**

En `src/autoclave/ui_pyside/main_window.py`, agregar el import:

```python
        from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import SensoresTemperaturaView
```

Agregar la instanciación:

```python
        self._sensores_temperatura_ciclo = SensoresTemperaturaView(nav_callback=self.navigate_to)
```

Agregarla al tuple de `self._stack.addWidget(view)`:

```python
        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo, self._params_ciclo_menu,
                     self._sensores_temperatura_ciclo, self._calibracion_sensor):
            self._stack.addWidget(view)
```

Agregarla al dict de `navigate_to`:

```python
            "sensores_temperatura_ciclo": self._sensores_temperatura_ciclo,
```

- [ ] **Step 3: Verificación manual**

Con el backend y la UI corriendo:
1. Administración → Parámetros del ciclo → Sensores de temperatura debe listar `temp_camara` y `temp_ref` (y `temp_2_camara` solo si hay un `installation_profile.json` con clase `MESA_B_LAB`/`PISO_LAB` — si no existe perfil de instalación, no debe aparecer y no debe lanzar excepción).
2. Marcar "Principal" en una fila debe desmarcar automáticamente el "Principal" de cualquier otra fila.
3. Cambiar un rol y revisar el JSON del ciclo correspondiente en `src/autoclave/cycles/user/` — `cycle_temperature_sensors` debe reflejar el cambio inmediatamente.
4. Apagar el backend y cambiar un rol — debe aparecer un `QMessageBox` de error sin crashear la UI.

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/sensores_temperatura.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: pantalla Sensores de Temperatura (roles principal/referencia/no en uso)"
```

---

## Task 11: UI — pantalla "Entradas exhibidas"

**Files:**
- Create: `src/autoclave/ui_pyside/views/params_ciclo/entradas_exhibidas.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `PATCH /cycle/display-slots` (Task 8), `Cycle.display_slots` (Task 1), `EstadoAutoclave.map_temp`/`map_pres` (ya existentes).
- Produces: `EntradasExhibidasView`, registrada bajo `"entradas_exhibidas_ciclo"`.

No hay tests automatizados para vistas de `ui_pyside` en este repo — este task se verifica manualmente (ver Step 3).

- [ ] **Step 1: Crear `EntradasExhibidasView`**

Crear `src/autoclave/ui_pyside/views/params_ciclo/entradas_exhibidas.py`:

```python
import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _format_name
from autoclave.core.runtime.status import EstadoAutoclave

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_CARD = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"


def _todos_los_sensores() -> list[str]:
    return list(EstadoAutoclave.map_temp.keys()) + list(EstadoAutoclave.map_pres.keys())


class EntradasExhibidasView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cycles: dict = {}
        self._cycle = None
        self._combos: list[QComboBox] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("params_ciclo_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("ENTRADAS EXHIBIDAS")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(16)

        self._combo_ciclo = QComboBox()
        self._combo_ciclo.setFont(QFont("Segoe UI", 11))
        self._combo_ciclo.setMinimumWidth(200)
        self._combo_ciclo.currentIndexChanged.connect(self._on_cycle_changed)
        hdr.addWidget(self._combo_ciclo)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        root.addSpacing(8)

        for i in range(3):
            fila = QFrame()
            fila.setStyleSheet(_CARD)
            fl = QHBoxLayout(fila)
            fl.setContentsMargins(16, 10, 16, 10)

            lbl = QLabel(f"Casilla {i + 1}")
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet("border: none;")
            fl.addWidget(lbl)
            fl.addStretch()

            combo = QComboBox()
            combo.addItem("— Vacío —", None)
            for sensor in _todos_los_sensores():
                combo.addItem(_format_name(sensor), sensor)
            combo.currentIndexChanged.connect(lambda idx, slot=i: self._on_slot_changed(slot, idx))
            fl.addWidget(combo)

            self._combos.append(combo)
            root.addWidget(fila)

        root.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_cycles()

    def _reload_cycles(self) -> None:
        try:
            from autoclave.core.managers.cycle_manager import CycleManager
            cm = CycleManager()
            cm.load_all_cycles()
            user_cycles = [
                c for c in cm.cycles.values()
                if getattr(c, "source", "user") == "user"
            ]
            self._cycles = {c.id: c for c in user_cycles}

            self._combo_ciclo.blockSignals(True)
            self._combo_ciclo.clear()
            for cycle in sorted(user_cycles, key=lambda c: c.name):
                self._combo_ciclo.addItem(cycle.name, cycle.id)
            self._combo_ciclo.blockSignals(False)

            if user_cycles:
                self._load_cycle(sorted(user_cycles, key=lambda c: c.name)[0])
        except Exception:
            _logger.exception("Error cargando ciclos de usuario")

    def _on_cycle_changed(self, idx: int) -> None:
        cycle_id = self._combo_ciclo.itemData(idx)
        cycle = self._cycles.get(cycle_id)
        if cycle:
            self._load_cycle(cycle)

    def _load_cycle(self, cycle) -> None:
        self._cycle = cycle
        slots = list(cycle.display_slots) + [None, None, None]
        for i, combo in enumerate(self._combos):
            combo.blockSignals(True)
            idx = combo.findData(slots[i])
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _on_slot_changed(self, slot_idx: int, combo_idx: int) -> None:
        if self._cycle is None:
            return

        sensor = self._combos[slot_idx].itemData(combo_idx)
        slots = list(self._cycle.display_slots) + [None, None, None]
        slots = slots[:3]
        slots[slot_idx] = sensor

        try:
            self._client.patch("/cycle/display-slots", {
                "cycle_id": self._cycle.id,
                "display_slots": slots,
            })
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar la entrada exhibida:\n{detail}")
            return
        except requests.RequestException as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo contactar al backend, el cambio no se guardó:\n{e}"
            )
            return

        self._cycle.display_slots = slots
```

- [ ] **Step 2: Registrar la vista en `main_window.py`**

En `src/autoclave/ui_pyside/main_window.py`, agregar el import:

```python
        from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import EntradasExhibidasView
```

Agregar la instanciación:

```python
        self._entradas_exhibidas_ciclo = EntradasExhibidasView(nav_callback=self.navigate_to)
```

Agregarla al tuple de `self._stack.addWidget(view)`:

```python
        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo, self._params_ciclo_menu,
                     self._sensores_temperatura_ciclo, self._entradas_exhibidas_ciclo,
                     self._calibracion_sensor):
            self._stack.addWidget(view)
```

Agregarla al dict de `navigate_to`:

```python
            "entradas_exhibidas_ciclo": self._entradas_exhibidas_ciclo,
```

- [ ] **Step 3: Verificación manual**

Con el backend y la UI corriendo:
1. Administración → Parámetros del ciclo → Entradas exhibidas debe mostrar 3 casillas, cada una con todos los sensores de temperatura y presión disponibles más "— Vacío —".
2. Elegir un sensor en una casilla y revisar `cycle_display_slots` en el JSON del ciclo correspondiente — debe reflejar el cambio.
3. Repetir el mismo sensor en dos casillas distintas — debe permitirlo sin error.
4. Cambiar de ciclo en el combo — las 3 casillas deben recargar los valores guardados de ese ciclo.

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/entradas_exhibidas.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: pantalla Entradas Exhibidas (configuracion de las 3 casillas de sensor por ciclo)"
```

---

## Verificación final de la suite completa

- [ ] **Step final: correr toda la suite de tests del repo**

Run: `pytest`
Expected: PASS — ningún test preexistente debe haberse roto por este plan (ver Global Constraints).
