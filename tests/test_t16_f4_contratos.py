# tests/test_t16_f4_contratos.py
#
# F4 (tanda 16): contratos del estado del ciclo que publica CicloState
# (aislamiento_camara, inhibir_vapor_chaqueta, no_conforme / motivo,
# modo_vapor) y alarmas propias de fase CIC-15/16/17.

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.installation.profile import MODO_CAMARA
from autoclave.state_machine.cycle_phases.aislamiento_camara import AislamientoCamara
from autoclave.state_machine.states import ciclo as mod_ciclo
from tests.test_t12_c13_7b_referencia_sin_lectura import _ciclo_con_ref

pytestmark = pytest.mark.req("T16-F4")


def test_estado_trae_los_contratos_por_defecto():
    e = EstadoAutoclave()
    assert e.aislamiento_camara is None and e.inhibir_vapor_chaqueta is False
    assert e.modo_vapor is None and e.cancelado_por is None
    # Tanda 21 (FC-08): los campos NO CONFORME se retiraron del estado
    assert not hasattr(e, "no_conforme") and not hasattr(e, "no_conforme_reconocido")


def test_reset_crea_aislamiento_y_fija_modo_camara_sin_perfil():
    ciclo, estado, _, _ = _ciclo_con_ref(120.0)
    ciclo.reset()
    assert isinstance(estado.aislamiento_camara, AislamientoCamara)
    assert estado.modo_vapor == MODO_CAMARA
    assert estado.inhibir_vapor_chaqueta is False and estado.cancelado_por is None
    primero = estado.aislamiento_camara
    ciclo.reset()
    assert estado.aislamiento_camara is not primero      # una instancia por ciclo


def test_referencia_sin_lectura_ya_no_publica_no_conforme():
    # Tanda 21 (FC-08): sin NO CONFORME; la observación va en avisos_ciclo
    ciclo, estado, _, _ = _ciclo_con_ref(None)
    estado.cancelado_por = "otro"
    ciclo.run()
    assert not hasattr(mod_ciclo, "MOTIVO_NO_CONFORME_REFERENCIA")
    assert [a["clave"] for a in estado.avisos_ciclo] == [mod_ciclo.CLAVE_OBSERVACION_REFERENCIA]
    ciclo.reset()
    assert estado.avisos_ciclo == [] and estado.cancelado_por is None


def test_al_confirmar_se_limpia_el_modo():
    ciclo, estado, _, _ = _ciclo_con_ref(120.0)
    ciclo.reset()
    estado.inhibir_vapor_chaqueta = True
    ciclo._resultado_pendiente = mod_ciclo.CicloResultado.COMPLETADO
    banderas = {"CICLO_CONFIRMADO": True}
    estado.get_flag.side_effect = lambda f: banderas.get(f, False)
    assert ciclo.run() == mod_ciclo.CicloResultado.COMPLETADO
    assert estado.modo_vapor is None and estado.inhibir_vapor_chaqueta is False


def test_alarmas_propias_de_fase_incluyen_las_nuevas():
    for codigo in ("CIC-15", "CIC-16", "CIC-17"):
        assert codigo in mod_ciclo._ALARMAS_PROPIAS_FASE
