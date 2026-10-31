from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.alarms.catalogo import PRE_03, PRE_04
from tests.helpers.alarmas_helpers import codigos_activados


def _make_preparacion(pres_camara, presion_admosferica=1013.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "presion_admosferica": presion_admosferica,
        "rango_presion_atm": rango,
    }[key]
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_presion_en_banda_ok_sin_pedir_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is True
    assert quiere_rapida is False
    set_do.aire_admosferico_camara_off.assert_called_once()
    # T1 (tanda 5): la lenta ya no se cierra aquí sino en ejecutor(), en la
    # única decisión de venteo del tick (test_t1_venteo_liquidos.py)
    set_do.descompresion_lenta_off.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


def test_presion_baja_pide_aire_no_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1000.0)
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is False
    assert quiere_rapida is False
    set_do.aire_admosferico_camara_on.assert_called()
    ids = codigos_activados(alarm_mgr)
    assert PRE_03 in ids


def test_presion_alta_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1030.0)
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is False
    assert quiere_rapida is True
    set_do.aire_admosferico_camara_off.assert_called()
    ids = codigos_activados(alarm_mgr)
    assert PRE_04 in ids


def test_apagado_aire_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_apagado_aire_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    p.estado.sensores_pres["pres_camara"] = 1000.0
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_on.assert_called()
    p.estado.sensores_pres["pres_camara"] = 1013.0
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()
