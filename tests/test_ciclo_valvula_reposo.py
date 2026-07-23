from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 25.0}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_completado_pendiente_en_rango_normal_abre_valvula_del_modo():
    ciclo, estado = _make_ciclo()
    ciclo.cycle.get_param.side_effect = (
        lambda *a, default=None: 1 if a == ("descompresion", "modo") else default
    )
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.sensores_pres["pres_camara"] = 101.3

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo.set_do.descompresion_rapida_on.assert_called()
    ciclo.set_do.aire_admosferico_camara_off.assert_called()
    ciclo.set_do.aire_admosferico_camara_on.assert_not_called()


def test_completado_pendiente_en_vacio_abre_aire_atmosferico():
    ciclo, estado = _make_ciclo()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.sensores_pres["pres_camara"] = 50.0  # < 101.3 - 20 = 81.3

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo.set_do.aire_admosferico_camara_on.assert_called()
    ciclo.set_do.descompresion_rapida_off.assert_called()
    ciclo.set_do.descompresion_lenta_off.assert_called()
    ciclo.set_do.descompresion_chaqueta_off.assert_called()


def test_fallo_pendiente_no_usa_mantener_valvula_reposo():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()
    ciclo._mantener_valvula_reposo = MagicMock()
    ciclo._resultado_pendiente = CicloResultado.FALLO

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.update.assert_called_once()
    ciclo._mantener_valvula_reposo.assert_not_called()


def test_cancelado_pendiente_no_usa_mantener_valvula_reposo():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()
    ciclo._mantener_valvula_reposo = MagicMock()
    ciclo._resultado_pendiente = CicloResultado.CANCELADO

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.update.assert_called_once()
    ciclo._mantener_valvula_reposo.assert_not_called()
