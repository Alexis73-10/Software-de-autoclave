from unittest.mock import MagicMock
from autoclave.devices.pump.pump import VacuumPump


def _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=False):
    estado = MagicMock()
    estado.sensores_di = {"agua_bomba": agua_bomba}
    estado.salidas_do  = {"bomba_vacio": bomba_vacio}
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    return VacuumPump(estado)


def test_puede_activar_con_agua_y_sin_fallo():
    pump = _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=False)
    assert pump.puede_activar() is True


def test_no_puede_activar_sin_agua():
    pump = _make_pump(agua_bomba=0, fallo_suministro=False)
    assert pump.puede_activar() is False


def test_no_puede_activar_con_fallo_suministro():
    pump = _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=True)
    assert pump.puede_activar() is False
