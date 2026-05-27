from unittest.mock import MagicMock
from autoclave.devices.suministro_electrico.suministro_electrico import SuministroElectrico


def _make_device():
    estado = MagicMock()
    set_do = MagicMock()
    device = SuministroElectrico(estado, set_do)
    return device, estado, set_do


def test_flag_inactivo_cuando_suministro_presente():
    device, estado, _ = _make_device()
    device.update(True)
    estado.set_flag.assert_called_with("FALLO_SUMINISTRO_ELECTRICO", False)


def test_flag_activo_cuando_suministro_cortado():
    device, estado, _ = _make_device()
    device.update(False)
    estado.set_flag.assert_called_with("FALLO_SUMINISTRO_ELECTRICO", True)


def test_bomba_apagada_en_flanco_bajante():
    device, estado, set_do = _make_device()
    device.update(True)   # estado normal
    set_do.reset_mock()
    device.update(False)  # corte
    set_do.bomba_vacio_off.assert_called_once()


def test_bomba_no_apagada_si_ya_habia_fallo():
    device, estado, set_do = _make_device()
    device.update(False)  # primer corte
    set_do.reset_mock()
    device.update(False)  # sigue cortado
    set_do.bomba_vacio_off.assert_not_called()


def test_restauracion_limpia_flag():
    device, estado, _ = _make_device()
    device.update(False)  # corte
    device.update(True)   # restaurar
    assert estado.set_flag.call_args == (("FALLO_SUMINISTRO_ELECTRICO", False),)
