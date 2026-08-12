from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(pres_camara, presion_admosferica=1013.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "presion_admosferica": presion_admosferica,
        "rango_presion_atm": rango,
        "tiempo_estable_alarma": 5,
    }[key]
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_presion_en_banda_retorna_true():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    assert p.mantener_presion_camara() is True


def test_presion_baja_enciende_aire_de_inmediato():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1000.0)
    assert p.mantener_presion_camara() is False
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_apagado_aire_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_apagado_aire_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    p.estado.sensores_pres["pres_camara"] = 1000.0
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_called()
    p.estado.sensores_pres["pres_camara"] = 1013.0
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()
