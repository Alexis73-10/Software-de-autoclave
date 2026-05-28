# Door Type from Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que el tipo y cantidad de puertas se determinen desde `InstallationProfile.door_type` y `door_count` en lugar de estar hardcodeados en `factory.py`.

**Architecture:** `build_hardware(profile)` recibe el perfil, mapea `door_type` a entero y filtra `doors_cfg` por `door_count`. `create_door()` lee el tipo de la entrada `cfg["type"]` en lugar de `config.get("tipo_puerta")`. `BackendContext` pasa `self.profile` a `build_hardware()`.

**Tech Stack:** Python 3.14, pytest, `unittest.mock`

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/devices/factory/factory.py` | Modificar — `build_hardware(profile)`, mapear door_type, filtrar por door_count |
| `src/autoclave/devices/puertas/door_factory.py` | Modificar — leer `cfg["type"]` en lugar de `config.get("tipo_puerta")` |
| `src/autoclave/backend/context.py` | Modificar — pasar `self.profile` a `build_hardware()` |
| `tests/test_door_from_profile.py` | Crear — tests unitarios |

---

## Task 1: Tests de door_type desde profile (rojo)

**Files:**
- Create: `tests/test_door_from_profile.py`

### Contexto

- `InstallationProfile` importa de `autoclave.installation.profile`; campos relevantes: `door_type: str` y `door_count: int`
- `create_door(config, io)` recibe `io = {"cfg": cfg, "estado": estado, "setdo": setdo}`; actualmente lee `config.get("tipo_puerta")` — debe pasar a leer `cfg["type"]`
- `build_hardware(profile)` actualmente no recibe argumento; debe recibir `profile` y retornar `doors_cfg` con largo `door_count` y `type` mapeado
- `Units` y `SerialLink` en `factory.py` se parchean para evitar hardware real en tests

- [ ] **Step 1: Crear `tests/test_door_from_profile.py`**

```python
# tests/test_door_from_profile.py
from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime

from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.puertas.simple_door import SimpleDoor
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.factory.factory import build_hardware
from autoclave.installation.profile import InstallationProfile, Role


def _make_profile(door_type="advanced", door_count=2):
    return InstallationProfile(
        machine_id="TEST-001",
        model_id="SOLIDS",
        serial_number="ACV-TEST",
        door_count=door_count,
        door_type=door_type,
        equipment_type="horizontal",
        drying_type="vacuum",
        door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.now(),
        locked=False,
    )


_CFG_SIMPLE = {
    "name": "Puerta 1",
    "type": 1,
    "di": {
        "abierta": "puerta_1_abierta",
        "cerrada": "puerta_1_cerrada",
        "atrapamiento": "atrapamiento_puerta_1",
    },
    "ai": {},
    "do": {},
}

_CFG_ADVANCED = {
    "name": "Puerta 1",
    "type": 2,
    "di": {
        "abierta": "puerta_1_abierta",
        "cerrada": "puerta_1_cerrada",
        "atrapamiento": "atrapamiento_puerta_1",
    },
    "ai": {"presion_empaque": "pres_empaque_1"},
    "do": {"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
}


# ── create_door: lee cfg["type"] ──────────────────────────────────────────────

def test_create_door_simple_desde_cfg():
    door = create_door(
        config=MagicMock(),
        io={"cfg": _CFG_SIMPLE, "estado": MagicMock(), "setdo": MagicMock()},
    )
    assert isinstance(door, SimpleDoor)


def test_create_door_advanced_desde_cfg():
    door = create_door(
        config=MagicMock(),
        io={"cfg": _CFG_ADVANCED, "estado": MagicMock(), "setdo": MagicMock()},
    )
    assert isinstance(door, AdvancedDoor)


def test_create_door_tipo_invalido_lanza_error():
    cfg = {"name": "X", "type": 99, "di": {}, "ai": {}, "do": {}}
    with pytest.raises(ValueError):
        create_door(
            config=MagicMock(),
            io={"cfg": cfg, "estado": MagicMock(), "setdo": MagicMock()},
        )


# ── build_hardware: usa profile.door_type y door_count ───────────────────────

def test_build_hardware_advanced_dos_puertas():
    profile = _make_profile(door_type="advanced", door_count=2)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert len(doors_cfg) == 2
    assert all(cfg["type"] == 2 for cfg in doors_cfg)


def test_build_hardware_simple_una_puerta():
    profile = _make_profile(door_type="simple", door_count=1)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert len(doors_cfg) == 1
    assert doors_cfg[0]["type"] == 1


def test_build_hardware_advanced_una_puerta():
    profile = _make_profile(door_type="advanced", door_count=1)
    with patch("autoclave.devices.factory.factory.Units"), \
         patch("autoclave.devices.factory.factory.SerialLink"):
        _, _, doors_cfg = build_hardware(profile)
    assert len(doors_cfg) == 1
    assert doors_cfg[0]["type"] == 2
```

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest tests/test_door_from_profile.py -v
```

Resultado esperado:
- `test_create_door_simple_desde_cfg` → FAIL (actualmente `create_door` lee `config.get("tipo_puerta")` que retorna un MagicMock, no 1 ni 2)
- `test_create_door_advanced_desde_cfg` → FAIL (misma razón)
- `test_create_door_tipo_invalido_lanza_error` → FAIL
- `test_build_hardware_advanced_dos_puertas` → ERROR (`build_hardware()` no acepta argumento)
- `test_build_hardware_simple_una_puerta` → ERROR
- `test_build_hardware_advanced_una_puerta` → ERROR

---

## Task 2: Implementar los tres archivos

**Files:**
- Modify: `src/autoclave/devices/factory/factory.py`
- Modify: `src/autoclave/devices/puertas/door_factory.py`
- Modify: `src/autoclave/backend/context.py`

- [ ] **Step 1: Reemplazar `factory.py`**

```python
# src/autoclave/devices/factory/factory.py
from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink
from autoclave.utils.resources import resource_path

_DOOR_TYPE_MAP = {"simple": 1, "advanced": 2}

def build_hardware(profile):
    units = Units(resource_path("autoclave/config/calibration.yaml"))

    serial = SerialLink(
        on_update=lambda data: units.update_from_serial(data)
    )
    serial._scan_ports()
    serial.start()

    door_type_int = _DOOR_TYPE_MAP[profile.door_type]

    all_doors_cfg = [
        {
            "name": "Puerta 1",
            "type": door_type_int,
            "di": {
                "abierta": "puerta_1_abierta",
                "cerrada": "puerta_1_cerrada",
                "atrapamiento": "atrapamiento_puerta_1",
            },
            "ai": {"presion_empaque": "pres_empaque_1"},
            "do": {"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
        },
        {
            "name": "Puerta 2",
            "type": door_type_int,
            "di": {
                "abierta": "puerta_2_abierta",
                "cerrada": "puerta_2_cerrada",
                "atrapamiento": "atrapamiento_puerta_2",
            },
            "ai": {"presion_empaque": "pres_empaque_2"},
            "do": {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
        },
    ]

    return units, serial, all_doors_cfg[:profile.door_count]
```

- [ ] **Step 2: Reemplazar `door_factory.py`**

```python
# src/autoclave/devices/puertas/door_factory.py
from .simple_door import SimpleDoor
from .advanced_door import AdvancedDoor


def create_door(config, io):
    cfg    = io["cfg"]
    estado = io["estado"]
    setdo  = io["setdo"]

    door_type = cfg["type"]

    if door_type == 1:
        return SimpleDoor(
            name=cfg["name"],
            di=cfg["di"],
            estado=estado,
        )
    elif door_type == 2:
        return AdvancedDoor(
            name=cfg["name"],
            di=cfg["di"],
            do=cfg["do"],
            ai=cfg["ai"],
            estado=estado,
            setdo=setdo,
            config=config,
        )
    else:
        raise ValueError("Tipo de puerta no soportado")
```

- [ ] **Step 3: Modificar `context.py` — pasar profile a build_hardware**

En `src/autoclave/backend/context.py`, línea 42, cambiar:

```python
        self.units, self.serial, doors_cfg = build_hardware()
```

Por:

```python
        self.units, self.serial, doors_cfg = build_hardware(self.profile)
```

- [ ] **Step 4: Correr los tests de door_from_profile**

```
pytest tests/test_door_from_profile.py -v
```

Resultado esperado:
```
PASSED test_create_door_simple_desde_cfg
PASSED test_create_door_advanced_desde_cfg
PASSED test_create_door_tipo_invalido_lanza_error
PASSED test_build_hardware_advanced_dos_puertas
PASSED test_build_hardware_simple_una_puerta
PASSED test_build_hardware_advanced_una_puerta

6 passed
```

- [ ] **Step 5: Correr suite completa**

```
pytest tests/ --ignore=tests/test_config.py -q
```

Resultado esperado: todos los tests pasan, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/devices/factory/factory.py \
        src/autoclave/devices/puertas/door_factory.py \
        src/autoclave/backend/context.py \
        tests/test_door_from_profile.py
git commit -m "feat: tipo y cantidad de puertas desde InstallationProfile"
```
