import pytest
from unittest.mock import MagicMock
from autoclave.devices.puertas.advanced_door import AdvancedDoor, DoorState
from autoclave.devices.factory.factory import _build_door_cfg
from autoclave.devices.puertas.door_type import DoorType


_CONFIG = {
    "vacio_empaque": 30,
    "timeout_puerta": 60,
    "presion_empaque": 300,
    "presion_admosferica": 74.5,
    "rango_presion_atm": 20,
}


def _make_door(di_extra=None, bloqueo_sensor_val=0):
    estado = MagicMock()
    estado.get_door_state.return_value = DoorState.CERRADO
    estado.get_flag.return_value = False
    estado.sensores_di.get.side_effect = lambda key, *a: (
        bloqueo_sensor_val if key == "bloqueo_puerta_1" else 0
    )
    estado.sensores_pres.get.return_value = 300.0

    di = {"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"}
    if di_extra:
        di.update(di_extra)

    door = AdvancedDoor(
        name="Puerta 1",
        di=di,
        do={"abrir": 19, "cerrar": 21},
        ai={},
        estado=estado,
        setdo=MagicMock(),
        config=_CONFIG,
        alarm_manager=None,
    )
    return door


# ── Tests de factory ──────────────────────────────────────────────────────────

def test_motorized_cfg_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.MOTORIZED)
    assert "bloqueo" in cfg["di"]
    assert cfg["di"]["bloqueo"] == "bloqueo_puerta_1"


def test_motorized_locking_cfg_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.MOTORIZED_LOCKING)
    assert "bloqueo" in cfg["di"]
    assert cfg["di"]["bloqueo"] == "bloqueo_puerta_1"


def test_motorized_cfg_puerta2_sensor_bloqueo_correcto():
    cfg = _build_door_cfg(2, DoorType.MOTORIZED)
    assert cfg["di"]["bloqueo"] == "bloqueo_puerta_2"


def test_advanced_cfg_no_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.ADVANCED)
    assert "bloqueo" not in cfg["di"]


def test_simple_cfg_no_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.SIMPLE)
    assert "bloqueo" not in cfg["di"]


def test_locking_cfg_no_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.LOCKING)
    assert "bloqueo" not in cfg["di"]


# ── Tests de cmd_abrir ────────────────────────────────────────────────────────

def test_cmd_abrir_bloqueada_no_transiciona():
    door = _make_door(di_extra={"bloqueo": "bloqueo_puerta_1"}, bloqueo_sensor_val=1)
    door.cmd_abrir()
    door.estado.update_door_state.assert_not_called()


def test_cmd_abrir_desbloqueada_transiciona():
    door = _make_door(di_extra={"bloqueo": "bloqueo_puerta_1"}, bloqueo_sensor_val=0)
    door.cmd_abrir()
    door.estado.update_door_state.assert_called_once_with("Puerta 1", DoorState.ABRIENDO)


def test_cmd_abrir_sin_sensor_bloqueo_siempre_transiciona():
    """ADVANCED no tiene di['bloqueo'], siempre permite apertura desde este método."""
    door = _make_door()
    door.cmd_abrir()
    door.estado.update_door_state.assert_called_once_with("Puerta 1", DoorState.ABRIENDO)
