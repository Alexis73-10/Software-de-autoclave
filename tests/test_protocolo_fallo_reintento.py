from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo


def _make_protocolo(pres_camara=101.3):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    estado.sensores_temp = {"temp_camara": 25.0}
    config = MagicMock()
    config.get.return_value = None
    set_do = MagicMock()
    return ProtocoloFallo(estado, set_do, config), set_do


def test_reset_all_outputs_se_reintenta_en_update_si_no_se_confirmo():
    protocolo, set_do = _make_protocolo()
    set_do.reset_all_outputs.side_effect = [False, False, True]

    protocolo.ejecutar()
    protocolo.update()
    protocolo.update()

    assert set_do.reset_all_outputs.call_count == 3


def test_reset_all_outputs_no_se_reintenta_una_vez_confirmado():
    protocolo, set_do = _make_protocolo()
    set_do.reset_all_outputs.side_effect = [True]

    protocolo.ejecutar()
    protocolo.update()
    protocolo.update()

    set_do.reset_all_outputs.assert_called_once()
