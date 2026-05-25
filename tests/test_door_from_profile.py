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
