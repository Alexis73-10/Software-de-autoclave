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
