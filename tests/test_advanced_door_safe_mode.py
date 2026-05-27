# tests/test_advanced_door_safe_mode.py
from unittest.mock import MagicMock
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.enum_doors import DoorState


def _make_door(fallo_suministro=False):
    estado = MagicMock()
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    estado.sensores_di = {
        "puerta_1_abierta": 0, "puerta_1_cerrada": 0, "atrapamiento_puerta_1": 0,
    }
    estado.sensores_pres = {"pres_empaque_1": 200.0}
    estado.get_door_state.return_value = DoorState.ABRIENDO

    set_do = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "timeout_puerta": 30,
        "vacio_empaque": 30.0,
        "presion_empaque": 300.0,
        "presion_admosferica": 101.3,
        "rango_presion_atm": 20.0,
    }.get(k, 0)

    alarm_manager = MagicMock()

    door = AdvancedDoor(
        name="Puerta 1",
        di={"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada",
            "atrapamiento": "atrapamiento_puerta_1"},
        do={"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
        ai={"presion_empaque": "pres_empaque_1"},
        estado=estado,
        setdo=set_do,
        config=config,
        alarm_manager=alarm_manager,
    )
    return door, set_do, alarm_manager, config


def test_modo_normal_activa_bomba_al_abrir():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=False)
    door._from_abriendo()
    set_do.bomba_vacio_on.assert_called()
    alarm_mgr.report.assert_not_called()


def test_modo_seguro_no_activa_bomba_al_abrir():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    door._from_abriendo()
    set_do.bomba_vacio_on.assert_not_called()


def test_modo_seguro_genera_alarma_no_bloqueante():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    door._from_abriendo()
    alarm_mgr.report.assert_called_once()
    alarma = alarm_mgr.report.call_args[0][0]
    assert alarma.id == "ABRIENDO_MODO_SEGURO"
    assert alarma.recoverable is True


def test_modo_seguro_usa_umbral_atmosferico():
    """Con safe mode y presión 200 kPa (mayor que umbral atm 121.3 kPa), NO debe activar abrir_on."""
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    import time
    door.timer_start = time.time() + 30
    door._pulso_desbloqueo_enviado = True
    # presion_empaque = 200 kPa > umbral seguro (101.3 + 20 = 121.3 kPa)
    door._from_abriendo()
    # No debe activar el actuador de apertura (DO20)
    door.set_do.set_output.assert_not_called()


def test_modo_seguro_activa_abrir_cuando_presion_baja():
    """Con safe mode y presión 100 kPa (menor que 121.3 kPa), SÍ debe activar abrir_on."""
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    import time
    door.timer_start = time.time() + 30
    door._pulso_desbloqueo_enviado = True
    door.estado.sensores_pres["pres_empaque_1"] = 100.0
    door._from_abriendo()
    set_do.set_output.assert_any_call(20, True)  # abrir_on (DO20)
