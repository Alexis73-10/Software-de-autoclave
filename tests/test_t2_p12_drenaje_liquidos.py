"""T2 / P-12 (tanda 6): en Líquidos, D-19 también rige el drenaje de agua
residual con la cámara a presión atmosférica. PREPARACION drena por la LENTA
mientras la temperatura del Principal sea mayor que temp_max_apertura (o no
tenga lectura) y por la rápida solo por debajo, con 3 lecturas seguidas
(convención de debounce). En sólidos sigue la rápida."""

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states.preparacion import preparacion_state
from tests.test_e0_lecturas_invalidas import _estado, _sensores_ok
from tests.test_t1_venteo_liquidos import _prog, _ultima


def _config(temp_max=80.0):
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0, "temp_max_apertura": temp_max,
    }.get(k)
    return cfg


def _make(tipo, temp_principal, temp_max=80.0):
    pres, temp, di = _sensores_ok()
    pres["pres_camara"] = 101.0                       # cámara a presión atmosférica
    temp["temp_camara"] = temp_principal
    di["agua_camara"] = 1                             # agua residual
    set_do = MagicMock()
    obj = preparacion_state(MagicMock(), _estado(pres, temp, di), set_do, _prog(tipo),
                            _config(temp_max))
    return obj, set_do, temp


def _tick(obj, set_do):
    set_do.reset_mock()
    obj.ejecutor(controlar_chaqueta=False)


def test_liquido_caliente_drena_por_la_lenta():
    obj, set_do, _ = _make("liquido", 95.0)
    for _ in range(5):
        _tick(obj, set_do)
        assert _ultima(set_do, "descompresion_lenta") is True
        set_do.descompresion_rapida_on.assert_not_called()
        # una sola orden de la lenta por tick (nunca ON y OFF a la vez)
        assert not set_do.descompresion_lenta_off.called


def test_liquido_sin_lectura_del_principal_drena_por_la_lenta():
    obj, set_do, _ = _make("liquido", None)
    _tick(obj, set_do)
    assert _ultima(set_do, "descompresion_lenta") is True
    set_do.descompresion_rapida_on.assert_not_called()


def test_liquido_sin_temp_max_configurada_drena_por_la_lenta():
    obj, set_do, _ = _make("liquido", 30.0, temp_max=None)
    for _ in range(4):
        _tick(obj, set_do)
    set_do.descompresion_rapida_on.assert_not_called()


def test_liquido_frio_pasa_a_la_rapida_tras_tres_lecturas():
    obj, set_do, _ = _make("liquido", 60.0)
    _tick(obj, set_do); _tick(obj, set_do)
    set_do.descompresion_rapida_on.assert_not_called()
    _tick(obj, set_do)
    assert _ultima(set_do, "descompresion_rapida") is True
    assert _ultima(set_do, "descompresion_lenta") is False   # cierra la lenta propia


def test_lectura_caliente_reinicia_la_cuenta():
    obj, set_do, temp = _make("liquido", 60.0)
    _tick(obj, set_do); _tick(obj, set_do)
    temp["temp_camara"] = 85.0
    _tick(obj, set_do)
    temp["temp_camara"] = 60.0
    _tick(obj, set_do); _tick(obj, set_do)
    set_do.descompresion_rapida_on.assert_not_called()


def test_si_se_recalienta_vuelve_a_la_lenta():
    obj, set_do, temp = _make("liquido", 60.0)
    for _ in range(3):
        _tick(obj, set_do)
    temp["temp_camara"] = 90.0
    _tick(obj, set_do)
    assert _ultima(set_do, "descompresion_rapida") is False
    assert _ultima(set_do, "descompresion_lenta") is True


@pytest.mark.parametrize("temp", [95.0, None])
def test_solidos_siguen_con_la_rapida(temp):
    obj, set_do, _ = _make("solido", temp)
    _tick(obj, set_do)
    assert _ultima(set_do, "descompresion_rapida") is True


def test_sin_agua_cierra_la_lenta_propia():
    obj, set_do, _ = _make("liquido", 95.0)
    _tick(obj, set_do)
    obj.estado.sensores_di["agua_camara"] = 0
    _tick(obj, set_do)
    assert _ultima(set_do, "descompresion_lenta") is False
