# Equipment Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar los 5 perfiles de equipo (`EquipmentClass`) con capacidades derivadas que configuran condicionalmente el hardware IO, tipos de puerta y lógica de fases del ciclo.

**Architecture:** `EquipmentClass` (enum) persiste en `InstallationProfile` en disco. Al arrancar, `get_capabilities()` deriva un `EquipmentCapabilities` frozen dataclass en memoria (nunca se serializa). Todo el código usa los flags del dataclass, nunca el enum directamente. Las capacidades fluyen `context.py → ControlLoop → StateMachine → CicloState → BaseFase.cap`.

**Tech Stack:** Python 3.14, dataclasses (frozen), Enum, Tkinter (wizard), pytest + unittest.mock

---

## Mapa de archivos

**Nuevos:**
- `src/autoclave/installation/equipment.py` — EquipmentClass, EquipmentCapabilities, get_capabilities()
- `src/autoclave/devices/puertas/door_type.py` — DoorType enum
- `tests/test_equipment.py`
- `tests/test_prevacio_caps.py`
- `tests/test_calentamiento_caps.py`
- `tests/test_esterilizacion_caps.py`

**Modificados (datos):**
- `src/autoclave/installation/profile.py` — reemplaza equipment_type/drying_type/door_type:str por equipment_class/cooling_level/door_type:DoorType
- `src/autoclave/installation/storage.py` — load/save para los nuevos campos
- `tests/test_profile_validation.py` — actualizar VALID_DATA y tests

**Modificados (hardware):**
- `src/autoclave/devices/puertas/advanced_door.py` — do/ai/di keys opcionales sin fallar
- `src/autoclave/devices/puertas/door_factory.py` — usa DoorType enum, no enteros
- `src/autoclave/devices/factory/factory.py` — config de puerta condicional por DoorType
- `tests/test_door_from_profile.py` — actualizar para DoorType enum

**Modificados (fases):**
- `src/autoclave/state_machine/cycle_phases/base_fase.py` — agrega cap param + _temp_camara_2()
- `src/autoclave/state_machine/states/ciclo.py` — pasa cap a fases
- `src/autoclave/state_machine/state_machine.py` — acepta y pasa cap
- `src/autoclave/services/domain/loop/control_loop.py` — acepta y pasa cap
- `src/autoclave/backend/context.py` — llama get_capabilities(), pasa cap
- `src/autoclave/state_machine/cycle_phases/prevacio.py` — skip si !cap.has_vacuum
- `src/autoclave/state_machine/cycle_phases/calentamiento.py` — sensor dual si cap.has_liquid_sensor
- `src/autoclave/state_machine/cycle_phases/esterilizacion.py` — sensor dual si cap.has_liquid_sensor
- Tests existentes de fases: agregar cap=MagicMock() a todos los helpers

**Modificado (UI):**
- `src/autoclave/installation/wizard.py` — 3 pasos nuevos

---

## Task 1: equipment.py

**Files:**
- Create: `src/autoclave/installation/equipment.py`
- Create: `tests/test_equipment.py`

- [ ] **Step 1: Escribir test que falla**

```python
# tests/test_equipment.py
import pytest
from autoclave.installation.equipment import EquipmentClass, EquipmentCapabilities, get_capabilities


def test_mesa_n_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_N)
    assert isinstance(cap, EquipmentCapabilities)
    assert cap.has_vacuum is False
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_mesa_b_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_B)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_mesa_b_lab_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_B_LAB)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is True
    assert cap.has_liquid_sensor is True
    assert cap.bleve_protection is True


def test_piso_capabilities():
    cap = get_capabilities(EquipmentClass.PISO)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is True
    assert cap.door_count_max == 2
    assert cap.cooling_level_max == 4
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_piso_lab_capabilities():
    cap = get_capabilities(EquipmentClass.PISO_LAB)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is True
    assert cap.door_count_max == 2
    assert cap.cooling_level_max == 4
    assert cap.has_liquids is True
    assert cap.has_liquid_sensor is True
    assert cap.bleve_protection is True


def test_capabilities_frozen():
    cap = get_capabilities(EquipmentClass.MESA_N)
    with pytest.raises(Exception):
        cap.has_vacuum = True  # type: ignore


def test_all_equipment_classes_have_capabilities():
    for ec in EquipmentClass:
        cap = get_capabilities(ec)
        assert isinstance(cap, EquipmentCapabilities)
```

- [ ] **Step 2: Correr test para verificar que falla**

```
pytest tests/test_equipment.py -v
```
Expected: `ModuleNotFoundError: No module named 'autoclave.installation.equipment'`

- [ ] **Step 3: Implementar equipment.py**

```python
# src/autoclave/installation/equipment.py
from dataclasses import dataclass
from enum import Enum


class EquipmentClass(Enum):
    MESA_N     = "mesa_n"
    MESA_B     = "mesa_b"
    MESA_B_LAB = "mesa_b_lab"
    PISO       = "piso"
    PISO_LAB   = "piso_lab"


@dataclass(frozen=True)
class EquipmentCapabilities:
    has_vacuum:        bool
    has_full_jacket:   bool
    door_count_max:    int
    cooling_level_max: int
    has_liquids:       bool
    has_liquid_sensor: bool
    bleve_protection:  bool


_CAPABILITIES: dict[EquipmentClass, EquipmentCapabilities] = {
    EquipmentClass.MESA_N: EquipmentCapabilities(
        has_vacuum=False, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False,
    ),
    EquipmentClass.MESA_B: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False,
    ),
    EquipmentClass.MESA_B_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True,
    ),
    EquipmentClass.PISO: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False,
    ),
    EquipmentClass.PISO_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True,
    ),
}


def get_capabilities(equipment_class: EquipmentClass) -> EquipmentCapabilities:
    return _CAPABILITIES[equipment_class]
```

- [ ] **Step 4: Correr test para verificar que pasa**

```
pytest tests/test_equipment.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```
git add src/autoclave/installation/equipment.py tests/test_equipment.py
git commit -m "feat: agregar EquipmentClass, EquipmentCapabilities y get_capabilities()"
```

---

## Task 2: door_type.py

**Files:**
- Create: `src/autoclave/devices/puertas/door_type.py`

- [ ] **Step 1: Crear door_type.py**

```python
# src/autoclave/devices/puertas/door_type.py
from enum import Enum


class DoorType(Enum):
    SIMPLE            = "simple"
    MOTORIZED         = "motorized"
    LOCKING           = "locking"
    MOTORIZED_LOCKING = "motorized_locking"
    ADVANCED          = "advanced"
```

- [ ] **Step 2: Verificar que el import funciona**

```
python -c "from autoclave.devices.puertas.door_type import DoorType; print(list(DoorType))"
```
Expected: lista con los 5 tipos

- [ ] **Step 3: Commit**

```
git add src/autoclave/devices/puertas/door_type.py
git commit -m "feat: agregar DoorType enum (5 tipos de puerta)"
```

---

## Task 3: profile.py + storage.py + test_profile_validation.py

**Files:**
- Modify: `src/autoclave/installation/profile.py`
- Modify: `src/autoclave/installation/storage.py`
- Modify: `tests/test_profile_validation.py`

- [ ] **Step 1: Escribir los nuevos tests de validación (reemplazar todo el contenido)**

```python
# tests/test_profile_validation.py
from autoclave.installation.profile import validate_profile_data, ProfileValidationError

VALID_DATA = {
    "machine_id":      "ACV-2026-SN001",
    "model_id":        "MX-500",
    "serial_number":   "SN001",
    "equipment_class": "piso",
    "door_count":      2,
    "door_type":       "advanced",
    "cooling_level":   2,
    "door_id":         1,
    "role":            "operator_front",
    "created_at":      "2026-01-01T00:00:00",
    "locked":          True,
}


def test_valid_profile_returns_no_errors():
    assert validate_profile_data(VALID_DATA) == []


def test_missing_field_reported():
    data = {**VALID_DATA}
    del data["serial_number"]
    errors = validate_profile_data(data)
    assert any("serial_number" in e for e in errors)


def test_wrong_type_reported():
    data = {**VALID_DATA, "door_count": "dos"}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_invalid_door_count():
    data = {**VALID_DATA, "door_count": 5}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_invalid_equipment_class():
    data = {**VALID_DATA, "equipment_class": "diagonal"}
    errors = validate_profile_data(data)
    assert any("equipment_class" in e for e in errors)


def test_invalid_door_type():
    data = {**VALID_DATA, "door_type": "giratoria"}
    errors = validate_profile_data(data)
    assert any("door_type" in e for e in errors)


def test_door_count_excede_max_para_perfil():
    # Mesa N tiene door_count_max=1; door_count=2 debe fallar
    data = {**VALID_DATA, "equipment_class": "mesa_n", "door_count": 2}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_cooling_level_excede_max_para_perfil():
    # Mesa N tiene cooling_level_max=0; cooling_level=1 debe fallar
    data = {**VALID_DATA, "equipment_class": "mesa_n", "door_count": 1, "cooling_level": 1}
    errors = validate_profile_data(data)
    assert any("cooling_level" in e for e in errors)


def test_piso_acepta_dos_puertas_y_cooling():
    data = {**VALID_DATA, "equipment_class": "piso", "door_count": 2, "cooling_level": 4}
    assert validate_profile_data(data) == []


def test_profile_validation_error_contains_messages():
    errors = ["campo faltante: 'serial_number'"]
    exc = ProfileValidationError(errors)
    assert "serial_number" in str(exc)
    assert exc.errors == errors
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```
pytest tests/test_profile_validation.py -v
```
Expected: varios fallos por ImportError / campos faltantes

- [ ] **Step 3: Reemplazar profile.py**

```python
# src/autoclave/installation/profile.py
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType


class Role(Enum):
    OPERATOR_FRONT = "operator_front"
    OPERATOR_BACK  = "operator_back"
    SERVICE        = "service"


class ProfileValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Perfil de instalación inválido: {'; '.join(errors)}")


@dataclass
class InstallationProfile:
    machine_id:      str
    model_id:        str
    serial_number:   str
    equipment_class: EquipmentClass
    door_count:      int
    door_type:       DoorType
    cooling_level:   int
    door_id:         int
    role:            Role
    created_at:      datetime
    locked:          bool = True


_REQUIRED_TYPES: dict[str, type] = {
    "machine_id":      str,
    "model_id":        str,
    "serial_number":   str,
    "equipment_class": str,
    "door_count":      int,
    "door_type":       str,
    "cooling_level":   int,
    "door_id":         int,
    "role":            str,
    "created_at":      str,
    "locked":          bool,
}

_VALID_EQUIPMENT_CLASSES = {e.value for e in EquipmentClass}
_VALID_DOOR_TYPES        = {e.value for e in DoorType}


def validate_profile_data(data: dict) -> list[str]:
    from autoclave.installation.equipment import get_capabilities
    errors: list[str] = []

    for field, expected_type in _REQUIRED_TYPES.items():
        if field not in data:
            errors.append(f"campo faltante: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"tipo incorrecto en '{field}': "
                f"esperado {expected_type.__name__}, "
                f"recibido {type(data[field]).__name__}"
            )

    if "door_count" in data and isinstance(data["door_count"], int):
        if data["door_count"] not in {1, 2}:
            errors.append(
                f"valor inválido en 'door_count': '{data['door_count']}' no está en {{1, 2}}"
            )

    if "equipment_class" in data and isinstance(data["equipment_class"], str):
        if data["equipment_class"] not in _VALID_EQUIPMENT_CLASSES:
            errors.append(
                f"valor inválido en 'equipment_class': '{data['equipment_class']}' "
                f"no está en {_VALID_EQUIPMENT_CLASSES}"
            )

    if "door_type" in data and isinstance(data["door_type"], str):
        if data["door_type"] not in _VALID_DOOR_TYPES:
            errors.append(
                f"valor inválido en 'door_type': '{data['door_type']}' "
                f"no está en {_VALID_DOOR_TYPES}"
            )

    # Validaciones cruzadas (solo si equipment_class es válido)
    ec_value = data.get("equipment_class")
    if (ec_value in _VALID_EQUIPMENT_CLASSES
            and isinstance(data.get("door_count"), int)
            and isinstance(data.get("cooling_level"), int)):
        cap = get_capabilities(EquipmentClass(ec_value))
        if data["door_count"] > cap.door_count_max:
            errors.append(
                f"door_count {data['door_count']} excede el máximo "
                f"({cap.door_count_max}) para '{ec_value}'"
            )
        if data["cooling_level"] > cap.cooling_level_max:
            errors.append(
                f"cooling_level {data['cooling_level']} excede el máximo "
                f"({cap.cooling_level_max}) para '{ec_value}'"
            )

    return errors
```

- [ ] **Step 4: Actualizar storage.py**

```python
# src/autoclave/installation/storage.py
import json
import logging
from pathlib import Path
from datetime import datetime
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType
from .profile import InstallationProfile, Role, ProfileValidationError, validate_profile_data

logger = logging.getLogger(__name__)

INSTALLATION_FILE = Path(__file__).resolve().parents[3] / "installation_profile.json"


def exists() -> bool:
    return INSTALLATION_FILE.exists()


def load() -> InstallationProfile:
    data = json.loads(INSTALLATION_FILE.read_text(encoding="utf-8"))
    errors = validate_profile_data(data)
    if errors:
        raise ProfileValidationError(errors)

    return InstallationProfile(
        machine_id=data["machine_id"],
        model_id=data["model_id"],
        serial_number=data["serial_number"],
        equipment_class=EquipmentClass(data["equipment_class"]),
        door_count=data["door_count"],
        door_type=DoorType(data["door_type"]),
        cooling_level=data["cooling_level"],
        door_id=data["door_id"],
        role=Role(data["role"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        locked=data["locked"],
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("El perfil de instalación está bloqueado y no puede modificarse")

    INSTALLATION_FILE.write_text(json.dumps({
        "machine_id":      profile.machine_id,
        "model_id":        profile.model_id,
        "serial_number":   profile.serial_number,
        "equipment_class": profile.equipment_class.value,
        "door_count":      profile.door_count,
        "door_type":       profile.door_type.value,
        "cooling_level":   profile.cooling_level,
        "door_id":         profile.door_id,
        "role":            profile.role.value,
        "created_at":      profile.created_at.isoformat(),
        "locked":          profile.locked,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Correr tests de validación**

```
pytest tests/test_profile_validation.py -v
```
Expected: 10 passed

- [ ] **Step 6: Commit**

```
git add src/autoclave/installation/profile.py src/autoclave/installation/storage.py tests/test_profile_validation.py
git commit -m "feat: actualizar InstallationProfile para perfiles de equipo (EquipmentClass, DoorType, cooling_level)"
```

---

## Task 4: advanced_door.py — keys opcionales

**Files:**
- Modify: `src/autoclave/devices/puertas/advanced_door.py`

Contexto: `AdvancedDoor` se usa ahora para 4 tipos (MOTORIZED, LOCKING, MOTORIZED_LOCKING, ADVANCED). Cada tipo tiene un subconjunto de claves en `di`/`do`/`ai`. Los métodos deben ser no-op si la clave no existe.

- [ ] **Step 1: Actualizar los 8 métodos de salida + 2 de entrada que pueden fallar**

Reemplazar los métodos de acción y lectura en `AdvancedDoor`. Las líneas afectadas son las que acceden a `self.do[...]` y `self.ai[...]` sin verificar:

```python
# Reemplazar en advanced_door.py — sección ACCIONES (SALIDAS)

def abrir_on(self):
    if "abrir" in self.do:
        self.set_do.set_output(self.do["abrir"], True)

def abrir_off(self):
    if "abrir" in self.do:
        self.set_do.set_output(self.do["abrir"], False)

def cerrar_on(self):
    if "cerrar" in self.do:
        self.set_do.set_output(self.do["cerrar"], True)

def cerrar_off(self):
    if "cerrar" in self.do:
        self.set_do.set_output(self.do["cerrar"], False)

def bloquear_on(self):
    if "bloquear" in self.do:
        self.set_do.set_output(self.do["bloquear"], True)

def bloquear_off(self):
    if "bloquear" in self.do:
        self.set_do.set_output(self.do["bloquear"], False)

def desbloquear_on(self):
    if "desbloquear" in self.do:
        self.set_do.set_output(self.do["desbloquear"], True)

def desbloquear_off(self):
    if "desbloquear" in self.do:
        self.set_do.set_output(self.do["desbloquear"], False)
```

```python
# Reemplazar en advanced_door.py — sección LECTURA DE ENTRADAS

def atrapamiento(self):
    if "atrapamiento" not in self.di:
        return False
    val = self.estado.sensores_di.get(self.di["atrapamiento"])
    return val if val is not None else False

def presion_empaque(self):
    if "presion_empaque" not in self.ai:
        return 0.0
    val = self.estado.sensores_pres.get(self.ai["presion_empaque"])
    return val if val is not None else 0.0
```

- [ ] **Step 2: Correr tests de puerta para verificar que no se rompió nada**

```
pytest tests/test_advanced_door_safe_mode.py -v
```
Expected: todos pasan (los tests usan do/ai completos, así que no hay diferencia funcional)

- [ ] **Step 3: Commit**

```
git add src/autoclave/devices/puertas/advanced_door.py
git commit -m "feat: advanced_door maneja claves do/ai/di opcionales sin fallar"
```

---

## Task 5: door_factory.py + factory.py + test_door_from_profile.py

**Files:**
- Modify: `src/autoclave/devices/puertas/door_factory.py`
- Modify: `src/autoclave/devices/factory/factory.py`
- Modify: `tests/test_door_from_profile.py`

- [ ] **Step 1: Escribir los nuevos tests**

```python
# tests/test_door_from_profile.py  (reemplazar contenido completo)
from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime

from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.puertas.door_type import DoorType
from autoclave.devices.puertas.simple_door import SimpleDoor
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.factory.factory import build_hardware
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.installation.equipment import EquipmentClass


def _make_profile(door_type=DoorType.ADVANCED, door_count=2,
                  equipment_class=EquipmentClass.PISO):
    return InstallationProfile(
        machine_id="TEST-001",
        model_id="MX-TEST",
        serial_number="ACV-TEST",
        equipment_class=equipment_class,
        door_count=door_count,
        door_type=door_type,
        cooling_level=0,
        door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.now(),
        locked=False,
    )


# ── create_door ────────────────────────────────────────────────────────────────

def test_create_door_simple():
    cfg = {
        "name": "Puerta 1",
        "type": DoorType.SIMPLE,
        "di": {"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"},
    }
    door = create_door(config=MagicMock(),
                       io={"cfg": cfg, "estado": MagicMock(), "setdo": MagicMock()})
    assert isinstance(door, SimpleDoor)


def test_create_door_motorized_usa_advanced_door():
    cfg = {
        "name": "Puerta 1",
        "type": DoorType.MOTORIZED,
        "di": {"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"},
        "do": {"abrir": 20, "cerrar": 22},
    }
    door = create_door(config=MagicMock(),
                       io={"cfg": cfg, "estado": MagicMock(), "setdo": MagicMock()})
    assert isinstance(door, AdvancedDoor)


def test_create_door_advanced():
    cfg = {
        "name": "Puerta 1",
        "type": DoorType.ADVANCED,
        "di": {"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada",
               "atrapamiento": "atrapamiento_puerta_1"},
        "do": {"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
        "ai": {"presion_empaque": "pres_empaque_1"},
    }
    door = create_door(config=MagicMock(),
                       io={"cfg": cfg, "estado": MagicMock(), "setdo": MagicMock()})
    assert isinstance(door, AdvancedDoor)


# ── build_hardware ─────────────────────────────────────────────────────────────

def test_build_hardware_advanced_dos_puertas():
    profile = _make_profile(door_type=DoorType.ADVANCED, door_count=2)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert len(doors_cfg) == 2
    assert all(cfg["type"] == DoorType.ADVANCED for cfg in doors_cfg)


def test_build_hardware_simple_una_puerta():
    profile = _make_profile(door_type=DoorType.SIMPLE, door_count=1,
                             equipment_class=EquipmentClass.MESA_N)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert len(doors_cfg) == 1
    assert doors_cfg[0]["type"] == DoorType.SIMPLE
    assert "do" not in doors_cfg[0]
    assert "ai" not in doors_cfg[0]


def test_build_hardware_motorized_tiene_do_abrir_cerrar():
    profile = _make_profile(door_type=DoorType.MOTORIZED, door_count=1,
                             equipment_class=EquipmentClass.MESA_B)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert "do" in doors_cfg[0]
    assert "abrir" in doors_cfg[0]["do"]
    assert "cerrar" in doors_cfg[0]["do"]
    assert "bloquear" not in doors_cfg[0]["do"]


def test_build_hardware_locking_tiene_do_bloquear_desbloquear():
    profile = _make_profile(door_type=DoorType.LOCKING, door_count=1,
                             equipment_class=EquipmentClass.MESA_B)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert "do" in doors_cfg[0]
    assert "bloquear" in doors_cfg[0]["do"]
    assert "desbloquear" in doors_cfg[0]["do"]
    assert "abrir" not in doors_cfg[0]["do"]


def test_build_hardware_advanced_tiene_ai_y_atrapamiento():
    profile = _make_profile(door_type=DoorType.ADVANCED, door_count=1,
                             equipment_class=EquipmentClass.MESA_B)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    cfg = doors_cfg[0]
    assert "ai" in cfg
    assert "presion_empaque" in cfg["ai"]
    assert "atrapamiento" in cfg["di"]
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```
pytest tests/test_door_from_profile.py -v
```
Expected: fallos de ImportError y AssertionError (los configs aún usan enteros)

- [ ] **Step 3: Reemplazar door_factory.py**

```python
# src/autoclave/devices/puertas/door_factory.py
from .simple_door import SimpleDoor
from .advanced_door import AdvancedDoor
from .door_type import DoorType


def create_door(config, io):
    cfg           = io["cfg"]
    estado        = io["estado"]
    setdo         = io["setdo"]
    alarm_manager = io.get("alarm_manager")
    door_type     = cfg["type"]

    if door_type == DoorType.SIMPLE:
        return SimpleDoor(
            name=cfg["name"],
            di=cfg["di"],
            estado=estado,
        )

    return AdvancedDoor(
        name=cfg["name"],
        di=cfg["di"],
        do=cfg.get("do", {}),
        ai=cfg.get("ai", {}),
        estado=estado,
        setdo=setdo,
        config=config,
        alarm_manager=alarm_manager,
    )
```

- [ ] **Step 4: Reemplazar factory.py**

```python
# src/autoclave/devices/factory/factory.py
from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink
from autoclave.utils.resources import resource_path
from autoclave.devices.puertas.door_type import DoorType

_DOOR_DO_CHANNELS = {
    1: {"abrir": 20, "cerrar": 22, "desbloquear": 9,  "bloquear": 11},
    2: {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
}


def _build_door_cfg(n: int, door_type: DoorType) -> dict:
    do_ch = _DOOR_DO_CHANNELS[n]
    cfg = {
        "name": f"Puerta {n}",
        "type": door_type,
        "di": {
            "abierta": f"puerta_{n}_abierta",
            "cerrada": f"puerta_{n}_cerrada",
        },
    }

    has_motor  = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_lock   = door_type in (DoorType.LOCKING, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_sensor = door_type == DoorType.ADVANCED

    if has_motor or has_lock:
        do = {}
        if has_motor:
            do["abrir"]  = do_ch["abrir"]
            do["cerrar"] = do_ch["cerrar"]
        if has_lock:
            do["desbloquear"] = do_ch["desbloquear"]
            do["bloquear"]    = do_ch["bloquear"]
        cfg["do"] = do

    if has_sensor:
        cfg["di"]["atrapamiento"] = f"atrapamiento_puerta_{n}"
        cfg["ai"] = {"presion_empaque": f"pres_empaque_{n}"}

    return cfg


def build_hardware(profile):
    units = Units(resource_path("autoclave/config/calibration.yaml"))
    serial = SerialLink(on_update=lambda data: units.update_from_serial(data))
    serial._scan_ports()
    serial.start()

    doors_cfg = [_build_door_cfg(n + 1, profile.door_type) for n in range(profile.door_count)]
    return units, serial, doors_cfg
```

- [ ] **Step 5: Correr todos los tests de puerta**

```
pytest tests/test_door_from_profile.py tests/test_advanced_door_safe_mode.py -v
```
Expected: todos pasan

- [ ] **Step 6: Commit**

```
git add src/autoclave/devices/puertas/door_factory.py src/autoclave/devices/factory/factory.py tests/test_door_from_profile.py
git commit -m "feat: door_factory y build_hardware usan DoorType enum con config condicional por tipo"
```

---

## Task 6: base_fase.py — agregar cap + actualizar tests existentes de fases

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/base_fase.py`
- Modify: `tests/test_purga_fase.py`
- Modify: `tests/test_precalentamiento_fase.py`
- Modify: `tests/test_calentamiento_fase.py`
- Modify: `tests/test_estabilizacion_fase.py`
- Modify: `tests/test_esterilizacion_fase.py`

- [ ] **Step 1: Actualizar base_fase.py**

```python
# src/autoclave/state_machine/cycle_phases/base_fase.py
from __future__ import annotations
from enum import Enum, auto
import logging
from autoclave.core.steam import p_saturacion_kpa

logger = logging.getLogger(__name__)


class FaseResult(Enum):
    EN_CURSO   = auto()
    COMPLETADO = auto()
    FALLO      = auto()


class BaseFase:
    name: str = "BASE"

    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap

    def reset(self):
        pass

    def update(self) -> FaseResult:
        raise NotImplementedError(f"{self.__class__.__name__} debe implementar update()")

    def _temp_camara(self) -> float | None:
        return self.estado.sensores_temp.get("temp_camara")

    def _temp_camara_2(self) -> float | None:
        return self.estado.sensores_temp.get("temp_2_camara")

    def _pres_camara(self) -> float | None:
        return self.estado.sensores_pres.get("pres_camara")

    def _pres_atm(self) -> float:
        return self.config.get("presion_admosferica") or 101.3

    def _rango_atm(self) -> float:
        return self.config.get("rango_presion_atm") or 20.0

    def _verificar_vapor_saturado(self, t_celsius: float, p_real_kpa: float, tolerancia_kpa: float) -> bool:
        return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
```

- [ ] **Step 2: Agregar cap=MagicMock() a test_purga_fase.py**

En la función `_make_fase`:
```python
def _make_fase(tiempo_min=5):
    estado = MagicMock()
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        return {"tiempo_purga": tiempo_min}.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()

    fase = PurgaFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do
```

- [ ] **Step 3: Agregar cap=MagicMock() a test_precalentamiento_fase.py**

En la función `_make_fase`:
```python
def _make_fase(tiempo_min=5, presion_obj=200.0, timeout_min=10):
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": 0.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "tiempo_precalentamiento":  tiempo_min,
            "presion_precalentamiento": presion_obj,
            "timeout_precalentamiento": timeout_min,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()

    fase = PrecalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do
```

- [ ] **Step 4: Agregar cap=MagicMock() a test_calentamiento_fase.py**

En la función `_make_fase`:
```python
def _make_fase(t_obj=134.0, tasa=5.0, timeout_min=60, tolerancia=9.0, t_inicial=20.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento":   t_obj,
            "tasa_calentamiento":          tasa,
            "timeout_calentamiento":       timeout_min,
            "presion_add_calentamiento":   tolerancia,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = False  # default: sin sensor líquido

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do
```

- [ ] **Step 5: Agregar cap=MagicMock() a test_estabilizacion_fase.py**

Buscar en ese archivo el helper `_make_fase` y agregar `cap = MagicMock()` antes de instanciar la clase, luego pasar como 6° argumento.

- [ ] **Step 6: Agregar cap=MagicMock() a test_esterilizacion_fase.py**

Buscar en ese archivo el helper `_make_fase` y agregar:
```python
cap = MagicMock()
cap.has_liquid_sensor = False
fase = EsterilizacionFase(estado, set_do, cycle, config, alarms, cap)
```

- [ ] **Step 7: Correr todos los tests de fases**

```
pytest tests/test_purga_fase.py tests/test_precalentamiento_fase.py tests/test_calentamiento_fase.py tests/test_estabilizacion_fase.py tests/test_esterilizacion_fase.py -v
```
Expected: todos pasan

- [ ] **Step 8: Commit**

```
git add src/autoclave/state_machine/cycle_phases/base_fase.py tests/test_purga_fase.py tests/test_precalentamiento_fase.py tests/test_calentamiento_fase.py tests/test_estabilizacion_fase.py tests/test_esterilizacion_fase.py
git commit -m "feat: BaseFase acepta cap como 6° parámetro + helper _temp_camara_2()"
```

---

## Task 7: Cadena de inyección de cap

**Files:**
- Modify: `src/autoclave/backend/context.py`
- Modify: `src/autoclave/services/domain/loop/control_loop.py`
- Modify: `src/autoclave/state_machine/state_machine.py`
- Modify: `src/autoclave/state_machine/states/ciclo.py`

No hay TDD aquí — son cambios de wiring que se verifican con el arranque del sistema.

- [ ] **Step 1: Actualizar context.py**

Agregar al inicio de `BackendContext.__init__`, después de cargar el perfil:
```python
from autoclave.installation.equipment import get_capabilities
# ...
# En __init__, después de: self.profile = get_installation_profile()
cap = get_capabilities(self.profile.equipment_class)
```

Y en la llamada a `ControlLoop`, agregar `cap=cap` como kwarg:
```python
self.control_loop = ControlLoop(
    units=self.units,
    door_service=self.servicio_puertas,
    doors=self.doors,
    estado=self.estado,
    link=self.serial,
    set_do=self.setdo,
    alarm_manager=self.alarm_manager,
    cycle_manager=self.cycle_manager,
    config_manager=self.config_manager,
    cycle_logger=self.cycle_logger,
    cap=cap,
)
```

- [ ] **Step 2: Actualizar control_loop.py**

En `__init__`, agregar `cap` al final de los parámetros:
```python
def __init__(self, units, door_service, doors, estado, link, set_do,
             alarm_manager, cycle_manager, config_manager,
             cycle_logger=None, interval=0.5, cap=None):
```

Y en la creación de `StateMachine`:
```python
self.state_machine = StateMachine(
    io=self.link, estado=self.estado, set_do=set_do,
    cycle=self.cycle, config=self.config_manager,
    cap=cap,
)
```

- [ ] **Step 3: Actualizar state_machine.py**

En `__init__`, agregar `cap`:
```python
def __init__(self, io, estado, set_do, cycle, config, cap=None):
    ...
    self.ciclo = CicloState(estado, set_do, cycle, config, self.alarm_manager, cap)
```

- [ ] **Step 4: Actualizar ciclo.py**

En `CicloState.__init__`, agregar `cap`:
```python
def __init__(self, estado, set_do, cycle, config, alarm_manager, cap=None):
    ...
    _args = (estado, set_do, cycle, config, alarm_manager, cap)
    self._fases = [
        PrecalentamientoFase(*_args),
        PurgaFase(*_args),
        PrevacioFase(*_args),
        CalentamientoFase(*_args),
        EstabilizacionFase(*_args),
        EsterilizacionFase(*_args),
    ]
```

- [ ] **Step 5: Correr todos los tests existentes para verificar que no se rompió nada**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Expected: todos pasan (los fases usan `cap=MagicMock()` de Task 6)

- [ ] **Step 6: Commit**

```
git add src/autoclave/backend/context.py src/autoclave/services/domain/loop/control_loop.py src/autoclave/state_machine/state_machine.py src/autoclave/state_machine/states/ciclo.py
git commit -m "feat: inyectar EquipmentCapabilities desde context hasta BaseFase"
```

---

## Task 8: prevacio.py — skip si no hay vacío

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/prevacio.py`
- Create: `tests/test_prevacio_caps.py`

- [ ] **Step 1: Escribir test que falla**

```python
# tests/test_prevacio_caps.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_vacuum: bool):
    estado = MagicMock()
    set_do = MagicMock()
    cycle  = MagicMock()
    cycle.get_param.return_value = 0  # todos los conteos en 0
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_vacuum = has_vacuum

    fase = PrevacioFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, set_do


def test_prevacio_skip_sin_vacuum():
    fase, set_do = _make_fase(has_vacuum=False)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()
    set_do.vacio_camara_on.assert_not_called()


def test_prevacio_skip_sin_vacuum_retorna_en_primer_tick():
    fase, _ = _make_fase(has_vacuum=False)
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_prevacio_con_vacuum_y_pulsos_cero_igual_salta():
    fase, set_do = _make_fase(has_vacuum=True)
    result = fase.update()
    # Todos los conteos en 0 → COMPLETADO aunque tenga vacuum
    assert result == FaseResult.COMPLETADO
```

- [ ] **Step 2: Correr test para verificar que falla**

```
pytest tests/test_prevacio_caps.py::test_prevacio_skip_sin_vacuum -v
```
Expected: FAIL — la fase intentará procesar aunque no haya vacuum

- [ ] **Step 3: Agregar guard en prevacio.py**

Al inicio del método `update()`, antes del bloque `if not self._inicializado`:
```python
def update(self) -> FaseResult:
    if not self.cap.has_vacuum:
        logger.info("PrevacioFase: sin bomba de vacío — fase saltada")
        return FaseResult.COMPLETADO
    if not self._inicializado:
        ...
```

- [ ] **Step 4: Correr todos los tests de prevacio**

```
pytest tests/test_prevacio_caps.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add src/autoclave/state_machine/cycle_phases/prevacio.py tests/test_prevacio_caps.py
git commit -m "feat: PrevacioFase se salta si el equipo no tiene bomba de vacío"
```

---

## Task 9: calentamiento.py — sensor dual

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py`
- Create: `tests/test_calentamiento_caps.py`

Comportamiento: si `cap.has_liquid_sensor`, también se monitorea `temp_2_camara`. La fase completa solo cuando AMBOS sensores alcanzan `t_obj`.

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_calentamiento_caps.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_liquid_sensor: bool, t_inicial=20.0, t_inicial_2=20.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial, "temp_2_camara": t_inicial_2}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        return {
            "temperatura_calentamiento": 134.0,
            "tasa_calentamiento":        5.0,
            "timeout_calentamiento":     60,
            "presion_add_calentamiento": 9.0,
        }.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = has_liquid_sensor

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do


def test_sin_sensor_liquido_completa_con_un_sensor():
    fase, estado, _ = _make_fase(has_liquid_sensor=False)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 135.0  # solo temp_camara llega
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_con_sensor_liquido_no_completa_si_solo_camara_llega():
    fase, estado, _ = _make_fase(has_liquid_sensor=True, t_inicial=20.0, t_inicial_2=20.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp["temp_2_camara"] = 80.0   # sensor líquido frío aún
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_con_sensor_liquido_completa_cuando_ambos_llegan():
    fase, estado, _ = _make_fase(has_liquid_sensor=True, t_inicial=20.0, t_inicial_2=20.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp["temp_2_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_con_sensor_liquido_espera_si_temp2_es_none():
    fase, estado, _ = _make_fase(has_liquid_sensor=True)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp.pop("temp_2_camara")  # sensor ausente
    result = fase.update()
    assert result == FaseResult.EN_CURSO
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```
pytest tests/test_calentamiento_caps.py -v
```
Expected: test_con_sensor_liquido_no_completa_si_solo_camara_llega FAIL (la fase completaría con solo temp_camara)

- [ ] **Step 3: Actualizar calentamiento.py — bloque de verificación de completación**

Reemplazar el bloque `# ── 3. Verificar completación antes de checkpoint` en `update()`:

```python
        # ── 3. Verificar completación antes de checkpoint ─────────────────
        if temp is None:
            return FaseResult.EN_CURSO

        if self.cap.has_liquid_sensor:
            temp2 = self._temp_camara_2()
            if temp2 is None:
                return FaseResult.EN_CURSO
            if temp >= t_obj and temp2 >= t_obj:
                logger.info(
                    "Calentamiento: COMPLETADO — camara=%.1f°C liquido=%.1f°C",
                    temp, temp2,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
        else:
            if temp >= t_obj:
                logger.info("Calentamiento: COMPLETADO — %.1f°C alcanzados", temp)
                self._apagar_salidas()
                return FaseResult.COMPLETADO
```

- [ ] **Step 4: Correr todos los tests de calentamiento**

```
pytest tests/test_calentamiento_caps.py tests/test_calentamiento_fase.py -v
```
Expected: todos pasan

- [ ] **Step 5: Commit**

```
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_caps.py
git commit -m "feat: CalentamientoFase monitorea temp_2_camara si cap.has_liquid_sensor"
```

---

## Task 10: esterilizacion.py — sensor dual

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/esterilizacion.py`
- Create: `tests/test_esterilizacion_caps.py`

Comportamiento: si `cap.has_liquid_sensor`, `temp_2_camara` también debe ser >= `t_est` durante la esterilización. Si baja, la fase falla.

- [ ] **Step 1: Escribir tests que fallan**

```python
# tests/test_esterilizacion_caps.py
from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_liquid_sensor: bool, t_camara=135.0, t_2_camara=135.0):
    t_est = 134.0
    p_sat = p_saturacion_kpa(t_camara)
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_camara, "temp_2_camara": t_2_camara}
    estado.sensores_pres = {"pres_camara": p_sat + 5.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        return {
            "temperatura_esterilizacion":      t_est,
            "tiempo_esterilizacion":           3.5,
            "temperatura_add_esterilizacion":  2.0,
            "temperatura_error_esterilizacion":5.0,
            "rango_presion_esterilizacion":    20.0,
            "presion_error_esterilizacion":    40.0,
        }.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = has_liquid_sensor

    fase = EsterilizacionFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, alarms


def test_sin_sensor_liquido_no_verifica_temp2():
    fase, estado, _ = _make_fase(has_liquid_sensor=False, t_camara=135.0, t_2_camara=20.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO  # no falla aunque temp2 sea baja


def test_con_sensor_liquido_falla_si_temp2_bajo_setpoint():
    fase, estado, alarms = _make_fase(has_liquid_sensor=True, t_camara=135.0, t_2_camara=100.0)
    result = fase.update()
    assert result == FaseResult.FALLO
    alarms.report.assert_called()
    alarm_id = alarms.report.call_args[0][0].alarm_id
    assert "TEMP2" in alarm_id


def test_con_sensor_liquido_en_curso_ambos_sobre_setpoint():
    fase, estado, _ = _make_fase(has_liquid_sensor=True, t_camara=135.0, t_2_camara=135.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```
pytest tests/test_esterilizacion_caps.py -v
```
Expected: test_con_sensor_liquido_falla_si_temp2_bajo_setpoint FAIL

- [ ] **Step 3: Actualizar esterilizacion.py — sección verificación de temperatura**

En el método `update()`, después de obtener `temp = self._temp_camara()` y antes del check `if temp < t_est:`, agregar la lectura condicional de `temp2`:

```python
        temp = self._temp_camara()
        pres = self._pres_camara()
        temp2 = self._temp_camara_2() if self.cap.has_liquid_sensor else None

        # ── 2. Verificar temperatura ─────────────────────────────────────
        if temp < t_est:
            return self._fallo(
                "ESTERILIZACION_TEMP_BAJA",
                f"Temperatura baja: {temp:.1f}°C < {t_est:.1f}°C"
            )
        if temp > t_est + temp_add + temp_err:
            return self._fallo(
                "ESTERILIZACION_TEMP_ALTA",
                f"Temperatura alta: {temp:.1f}°C > {t_est + temp_add + temp_err:.1f}°C"
            )
        if self.cap.has_liquid_sensor and temp2 is not None and temp2 < t_est:
            return self._fallo(
                "ESTERILIZACION_TEMP2_BAJA",
                f"Temperatura sensor líquido baja: {temp2:.1f}°C < {t_est:.1f}°C"
            )
```

- [ ] **Step 4: Correr todos los tests de esterilizacion**

```
pytest tests/test_esterilizacion_caps.py tests/test_esterilizacion_fase.py -v
```
Expected: todos pasan

- [ ] **Step 5: Commit**

```
git add src/autoclave/state_machine/cycle_phases/esterilizacion.py tests/test_esterilizacion_caps.py
git commit -m "feat: EsterilizacionFase verifica temp_2_camara si cap.has_liquid_sensor"
```

---

## Task 11: wizard.py — 3 pasos nuevos

**Files:**
- Modify: `src/autoclave/installation/wizard.py`

El wizard pasa de 2 pasos a 5 pasos. El frame 1 (activación) no cambia. Se agregan 3 frames nuevos y se modifica el frame final.

**Flujo nuevo:**
1. Activación (sin cambios)
2. Selección de perfil de equipo (nuevo)
3. Configuración de puertas (nuevo, condicionado por cap.door_count_max)
4. Configuración de enfriamiento (nuevo, oculto si cap.cooling_level_max == 0)
5. Datos finales: modelo + puerta de este PC

- [ ] **Step 1: Reemplazar wizard.py completo**

```python
# src/autoclave/installation/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from .profile import InstallationProfile, Role
from .equipment import EquipmentClass, get_capabilities
from .storage import save
from .activation import validate_installation_code
from autoclave.devices.puertas.door_type import DoorType

logger = logging.getLogger(__name__)

_EQUIPMENT_LABELS = {
    EquipmentClass.MESA_N:     "Mesa Clase N",
    EquipmentClass.MESA_B:     "Mesa Clase B",
    EquipmentClass.MESA_B_LAB: "Mesa Clase B Laboratorio",
    EquipmentClass.PISO:       "Piso",
    EquipmentClass.PISO_LAB:   "Piso Laboratorio",
}

_DOOR_TYPE_LABELS = {
    DoorType.SIMPLE:            "Simple (solo sensor posición)",
    DoorType.MOTORIZED:         "Motorizada (apertura/cierre automático)",
    DoorType.LOCKING:           "Con bloqueo (seguro de empaque)",
    DoorType.MOTORIZED_LOCKING: "Motorizada con bloqueo",
    DoorType.ADVANCED:          "Avanzada (motorizada + bloqueo + sensor empaque)",
}


def launch_installation_wizard() -> bool:
    result = {"done": False}

    root = tk.Tk()
    root.title("Instalación — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    # ── Variables ──────────────────────────────────────────────────────────
    serial_var       = tk.StringVar()
    code_var         = tk.StringVar()
    model_var        = tk.StringVar()
    door_count_var   = tk.IntVar(value=1)
    door_type_var    = tk.StringVar(value=DoorType.ADVANCED.value)
    equipment_var    = tk.StringVar(value=EquipmentClass.MESA_B.value)
    cooling_var      = tk.IntVar(value=0)
    door_id_var      = tk.IntVar(value=1)

    # Estado compartido derivado del perfil seleccionado
    _cap_holder = [None]  # cap actual, actualizado en paso 2

    # ── PASO 1: Código de activación ───────────────────────────────────────
    frame1 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame1, text="Instalación del equipo",
             font=("", 14, "bold")).pack(pady=(0, 20))
    tk.Label(frame1, text="Número de serie del equipo:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=serial_var, width=35).pack(fill="x", pady=(0, 12))
    tk.Label(frame1, text="Código de activación:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=code_var, width=35).pack(fill="x", pady=(0, 16))
    err1 = tk.Label(frame1, text="", fg="red")
    err1.pack()

    def ir_a_paso2():
        serial = serial_var.get().strip()
        code   = code_var.get().strip()
        if not serial:
            err1.config(text="Ingrese el número de serie"); return
        if not code:
            err1.config(text="Ingrese el código de activación"); return
        if not validate_installation_code(serial, code):
            err1.config(text="Código de activación incorrecto o expirado")
            logger.warning("Intento de instalación con código inválido para serie '%s'", serial)
            return
        err1.config(text="")
        frame1.pack_forget()
        frame2.pack()

    tk.Button(frame1, text="Siguiente →", command=ir_a_paso2, width=20).pack(pady=(10, 0))

    # ── PASO 2: Selección de perfil ────────────────────────────────────────
    frame2 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame2, text="Perfil de equipo",
             font=("", 14, "bold")).pack(pady=(0, 12))
    tk.Label(frame2, text="Seleccione el tipo de equipo:", anchor="w").pack(fill="x")

    for ec in EquipmentClass:
        cap_preview = get_capabilities(ec)
        cap_str = (
            f"{'Vacío ' if cap_preview.has_vacuum else ''}"
            f"{'Chaqueta ' if cap_preview.has_full_jacket else ''}"
            f"{'Líquidos ' if cap_preview.has_liquids else ''}"
            f"Puertas: {cap_preview.door_count_max}"
        ).strip()
        ttk.Radiobutton(
            frame2,
            text=f"{_EQUIPMENT_LABELS[ec]}  ({cap_str})",
            variable=equipment_var,
            value=ec.value,
        ).pack(anchor="w", pady=2)

    err2 = tk.Label(frame2, text="", fg="red")
    err2.pack(pady=(8, 0))

    def ir_a_paso3():
        ec_value = equipment_var.get()
        cap = get_capabilities(EquipmentClass(ec_value))
        _cap_holder[0] = cap
        # Ajustar defaults condicionados por cap
        door_count_var.set(min(door_count_var.get(), cap.door_count_max))
        cooling_var.set(min(cooling_var.get(), cap.cooling_level_max))
        err2.config(text="")
        frame2.pack_forget()
        frame3.pack()
        _actualizar_frame3(cap)

    tk.Button(frame2, text="Siguiente →", command=ir_a_paso3, width=20).pack(pady=(10, 0))

    # ── PASO 3: Configuración de puertas ───────────────────────────────────
    frame3 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame3, text="Configuración de puertas",
             font=("", 14, "bold")).pack(pady=(0, 12))

    _door_count_frame = tk.Frame(frame3)
    _door_count_frame.pack(fill="x", pady=4)
    tk.Label(_door_count_frame, text="N° de puertas:", width=22, anchor="w").pack(side="left")
    _door_count_spin = ttk.Spinbox(_door_count_frame, from_=1, to=2,
                                   textvariable=door_count_var, width=6, state="readonly")
    _door_count_spin.pack(side="left")

    _door_type_frame = tk.Frame(frame3)
    _door_type_frame.pack(fill="x", pady=4)
    tk.Label(_door_type_frame, text="Tipo de puerta:", width=22, anchor="w").pack(side="left")
    _door_type_combo = ttk.Combobox(
        _door_type_frame, textvariable=door_type_var,
        values=[dt.value for dt in DoorType], state="readonly"
    )
    _door_type_combo.pack(side="left", fill="x", expand=True)

    err3 = tk.Label(frame3, text="", fg="red")
    err3.pack(pady=(8, 0))

    def _actualizar_frame3(cap):
        if cap.door_count_max == 1:
            door_count_var.set(1)
            _door_count_spin.config(state="disabled")
        else:
            _door_count_spin.config(state="readonly")

    def ir_a_paso4():
        err3.config(text="")
        cap = _cap_holder[0]
        frame3.pack_forget()
        if cap.cooling_level_max == 0:
            frame4.pack_forget()
            frame5.pack()
        else:
            _actualizar_frame4(cap)
            frame4.pack()

    tk.Button(frame3, text="Siguiente →", command=ir_a_paso4, width=20).pack(pady=(10, 0))

    # ── PASO 4: Configuración de enfriamiento (opcional) ──────────────────
    frame4 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame4, text="Configuración de enfriamiento",
             font=("", 14, "bold")).pack(pady=(0, 12))
    tk.Label(frame4, text="Nivel de enfriamiento (0 = sin enfriamiento):",
             anchor="w").pack(fill="x")

    _cooling_spin = ttk.Spinbox(frame4, from_=0, to=4,
                                textvariable=cooling_var, width=6, state="readonly")
    _cooling_spin.pack(anchor="w", pady=(4, 0))

    def _actualizar_frame4(cap):
        _cooling_spin.config(to=cap.cooling_level_max)

    err4 = tk.Label(frame4, text="", fg="red")
    err4.pack(pady=(8, 0))

    def ir_a_paso5():
        frame4.pack_forget()
        frame5.pack()

    tk.Button(frame4, text="Siguiente →", command=ir_a_paso5, width=20).pack(pady=(10, 0))

    # ── PASO 5: Datos finales ──────────────────────────────────────────────
    frame5 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame5, text="Datos del equipo",
             font=("", 14, "bold")).pack(pady=(0, 16))

    def fila(parent, label_text, widget_factory):
        f = tk.Frame(parent)
        tk.Label(f, text=label_text, width=22, anchor="w").pack(side="left")
        w = widget_factory(f)
        w.pack(side="left", fill="x", expand=True)
        f.pack(fill="x", pady=4)

    fila(frame5, "Modelo:", lambda p: tk.Entry(p, textvariable=model_var))
    fila(frame5, "Puerta de este PC (1/2):", lambda p: ttk.Spinbox(
        p, from_=1, to=2, textvariable=door_id_var, width=6, state="readonly"))

    err5 = tk.Label(frame5, text="", fg="red")
    err5.pack(pady=(10, 0))

    def instalar():
        model = model_var.get().strip()
        if not model:
            err5.config(text="El modelo es obligatorio"); return

        serial = serial_var.get().strip().upper()
        profile = InstallationProfile(
            machine_id=f"ACV-{datetime.utcnow().strftime('%Y')}-{serial}",
            model_id=model,
            serial_number=serial,
            equipment_class=EquipmentClass(equipment_var.get()),
            door_count=door_count_var.get(),
            door_type=DoorType(door_type_var.get()),
            cooling_level=cooling_var.get(),
            door_id=door_id_var.get(),
            role=Role.OPERATOR_FRONT,
            created_at=datetime.utcnow(),
            locked=True,
        )

        try:
            save(profile)
        except Exception as e:
            err5.config(text=f"Error al guardar: {e}")
            logger.error("Error guardando perfil de instalación: %s", e)
            return

        result["done"] = True
        logger.info("Instalación completada para serie '%s'", serial)
        messagebox.showinfo(
            "Instalación completada",
            "El equipo ha sido registrado correctamente.\n"
            "Reinicie el software para continuar."
        )
        root.destroy()

    tk.Button(frame5, text="Instalar", command=instalar,
              width=20, bg="#27ae60", fg="white",
              font=("", 10, "bold")).pack(pady=(14, 0))

    frame1.pack()
    root.mainloop()
    return result["done"]
```

- [ ] **Step 2: Correr los tests de activación para verificar que el wizard sigue funcionando**

```
pytest tests/test_activation.py -v
```
Expected: pasan (no dependen del contenido de wizard.py)

- [ ] **Step 3: Correr toda la suite de tests**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Expected: todos pasan

- [ ] **Step 4: Commit**

```
git add src/autoclave/installation/wizard.py
git commit -m "feat: wizard de instalación con 5 pasos incluyendo selección de perfil, puertas y enfriamiento"
```

---

## Verificación final

- [ ] **Correr suite completa**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Expected: todos los tests pasan (incluyendo los nuevos de equipment, caps de fases, y los actualizados de validación y puertas)

- [ ] **Verificar que installation_profile.json existente no bloquea el arranque**

Si existe un `installation_profile.json` con el formato viejo (campos `equipment_type`, `drying_type`), el backend fallará al cargarlo. Eliminar el archivo y correr el wizard para generar uno nuevo:
```
del installation_profile.json
```
Luego arrancar el wizard con `python -m autoclave.ui.main`.

---

## Fuera de alcance (no implementar en este plan)

- Definición de los 4 modos de enfriamiento (cooling_level 1–4)
- Definición de los 4 modos de secado
- Relación entre `model_id` y perfiles de equipo
- `PrecalentamientoFase`: no requiere cambio de código — los ciclos de líquidos configuran sus propios parámetros de tiempo y presión
- Lógica de BLEVE en descompresión — la fase de descompresión no existe aún
