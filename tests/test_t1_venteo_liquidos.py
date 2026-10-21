"""T1 (tanda 5): con carga líquida, PREPARACION y PREPARADO ventean una cámara
presurizada con la descompresión LENTA, nunca con la rápida (D-19). Caso
real: reconocer un ciclo de líquidos COMPLETADO con la cámara aún presurizada."""

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states import control_banda
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from tests.test_e0_lecturas_invalidas import _config, _estado, _sensores_ok


def _prog(tipo):
    p = MagicMock()
    p.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0, "tipo_carga": tipo,
    }.get(n, k.get("default"))
    return p


def _make(clase, tipo, ultimo=None):
    pres, temp, di = _sensores_ok()
    pres["pres_camara"] = 250.0                      # sobrepresión
    set_do = MagicMock()
    prog = _prog(tipo)
    obj = clase(MagicMock(), _estado(pres, temp, di), set_do, prog, _config())
    obj.programas_seguridad = (lambda: [prog, ultimo]) if ultimo is not None else None
    return obj, set_do, pres


def _correr(obj):
    if isinstance(obj, preparado_state):
        obj.mantener_presion_camara()
    else:
        obj.ejecutor(controlar_chaqueta=False)


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_solidos_siguen_con_la_rapida(clase):
    obj, set_do, _ = _make(clase, "solido")
    _correr(obj)
    set_do.descompresion_rapida_on.assert_called()
    set_do.descompresion_lenta_on.assert_not_called()


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_liquidos_ventean_con_la_lenta(clase):
    obj, set_do, pres = _make(clase, "liquido")
    _correr(obj)
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called()
    # al llegar a rango se cierra la lenta
    pres["pres_camara"] = 101.0
    _correr(obj)
    set_do.descompresion_lenta_off.assert_called()


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_programa_cambiado_a_solido_tras_un_ciclo_liquido_sigue_con_la_lenta(clase):
    """El programa del último ciclo (líquido) también cuenta."""
    obj, set_do, _ = _make(clase, "solido", ultimo=_prog("liquido"))
    _correr(obj)
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called()


def test_error_al_leer_los_programas_cuenta_como_liquido():
    def falla():
        raise RuntimeError("x")
    assert control_banda.carga_liquida(falla, None) is True


def test_sin_tipo_de_carga_o_sin_programa_cuenta_como_liquido():
    sin_campo = MagicMock()
    sin_campo.get_param.side_effect = lambda s, n, *a, **k: k.get("default")
    assert control_banda.carga_liquida(lambda: [sin_campo], None) is True
    assert control_banda.carga_liquida(lambda: [], None) is True
    assert control_banda.carga_liquida(None, None) is True
    assert control_banda.carga_liquida(None, _prog("solido")) is False


def _ultima(set_do, valvula):
    """Último estado ordenado de la válvula: True, False o None si no se ordenó."""
    on, off = getattr(set_do, valvula + "_on"), getattr(set_do, valvula + "_off")
    llamadas = [(c, True) for c in on.mock_calls] + [(c, False) for c in off.mock_calls]
    if not llamadas:
        return None
    orden = set_do.mock_calls
    return max(llamadas, key=lambda x: max(i for i, m in enumerate(orden)
                                             if m[0] == (valvula + ("_on" if x[1] else "_off"))))[1]


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("siguiente", [101.0, 20.0, None])
def test_la_lenta_queda_cerrada_al_salir_de_la_sobrepresion(clase, siguiente):
    """Revisión T1: a rango, por debajo (rebase) o sin dato, la lenta propia se cierra."""
    obj, set_do, pres = _make(clase, "liquido")
    _correr(obj)
    assert _ultima(set_do, "descompresion_lenta") is True
    pres["pres_camara"] = siguiente
    set_do.reset_mock()
    _correr(obj)
    assert _ultima(set_do, "descompresion_lenta") is False
    assert getattr(obj, "_lenta_por_liquido", False) is False


def test_una_sola_orden_de_lenta_por_tick_en_preparacion():
    """Revisión T1 (TMG A): nunca OFF y ON de la lenta en el mismo tick."""
    obj, set_do, _ = _make(preparacion_state, "liquido")
    obj.estado.sensores_di["agua_camara"] = 1
    _correr(obj)
    assert not (set_do.descompresion_lenta_on.called and set_do.descompresion_lenta_off.called)


def test_drenaje_a_presion_igualada_en_liquidos_va_por_la_lenta():
    # P-12 (tanda 6): reemplaza la prueba anterior ("sigue con la rápida").
    # Sin temp_max_apertura en la configuración de la prueba: la lenta.
    obj, set_do, pres = _make(preparacion_state, "liquido")
    pres["pres_camara"] = 101.0
    obj.estado.sensores_di["agua_camara"] = 1
    _correr(obj)
    assert _ultima(set_do, "descompresion_lenta") is True
    set_do.descompresion_rapida_on.assert_not_called()
