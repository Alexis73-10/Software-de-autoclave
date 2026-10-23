"""Tanda 8 / S2a / D8-2.6 (`permite_salir_de_falla` + R1-P4): se mantiene la
regla de P-2. Una vez el protocolo está en `solo_lenta` se sale de FALLA sin
técnico, aunque se haya llegado ahí con el protocolo ya en marcha por otra
causa (R1-P4). "NO ABRIR" sigue hasta que la cámara esté segura: el estado
seguro sigue activo en PREPARACION y la cámara no se da por segura sin el
Principal."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.cycle_phases.protocolo_fallo import (
    _DEBOUNCE_LECTURAS, ProtocoloFallo)
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _protocolo_en_marcha(modo, liquido=False):
    """Protocolo disparado por otra causa (cancelación / fallo de fase)."""
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 250.0
    estado.sensores_temp["temp_camara"] = 130.0
    params = {("descompresion", "modo"): modo,
              ("globals", "tipo_carga"): "liquido" if liquido else "solido"}
    cycle = SimpleNamespace(sensores=None,
                            get_param=lambda *a, default=None: params.get(a[:2], default))
    prot = ProtocoloFallo(estado, MagicMock(), cycle, _Config(_CFG))
    prot.ejecutar()
    return prot, estado, cycle


def _estado_seguro(prot, estado, cycle):
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG), programas_seguridad=lambda: [cycle])
    es.iniciar(prot)
    return es


@pytest.mark.parametrize("modo", [0, 1, 2, 3])
def test_r1p4_en_estado_seguro_habilita_salir_de_falla(modo):
    prot, estado, cycle = _protocolo_en_marcha(modo)
    es = _estado_seguro(prot, estado, cycle)
    es.update()
    assert es.permite_salir_de_falla is False          # Principal leyendo: no

    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        es.update()
    assert prot.solo_lenta is True
    assert es.permite_salir_de_falla is True          # D8-2.6: aunque llegó con el protocolo en marcha


def test_falla_pasa_a_preparacion_sin_tecnico_y_no_abrir_sigue():
    prot, estado, cycle = _protocolo_en_marcha(1)
    es = _estado_seguro(prot, estado, cycle)
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        es.update()

    prog = MagicMock(); prog.copia.return_value = prog; prog.get_param.return_value = None
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=prog,
                      config=_Config(_CFG), estado_seguro=es,
                      programas_seguridad=lambda: [cycle])
    estado.set_machine_state(GlobalState.FALLA)
    estado.set_flag("RESET_FALLA", True)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION

    # NO ABRIR: el estado seguro sigue venteando por la lenta en PREPARACION
    # y la cámara no es segura ni con la presión ya atmosférica
    estado.sensores_pres["pres_camara"] = 101.3
    for _ in range(10):
        es.update()
    assert es.activo is True
    segura, _ = camara_segura.evaluar(estado, _Config(_CFG), [cycle])
    assert segura is False


def test_no_abrir_se_libera_solo_con_la_camara_segura():
    prot, estado, cycle = _protocolo_en_marcha(2)
    es = _estado_seguro(prot, estado, cycle)
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        es.update()
    assert es.permite_salir_de_falla is True
    # la sonda vuelve a leer (o se reasigna) con la cámara fría y atmosférica
    estado.sensores_temp["temp_camara"] = 60.0
    estado.sensores_pres["pres_camara"] = 101.3
    for _ in range(3):
        es.update()
    assert es.activo is False
    segura, _ = camara_segura.evaluar(estado, _Config(_CFG), [cycle])
    assert segura is True


def test_tras_un_paro_sigue_exigiendo_la_confirmacion():
    prot, estado, cycle = _protocolo_en_marcha(1)
    es = _estado_seguro(prot, estado, cycle)
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        es.update()
    es.requiere_confirmacion = True
    assert es.permite_salir_de_falla is False
