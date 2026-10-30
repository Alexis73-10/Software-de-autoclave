# tests/test_q1rev_solo_lenta_abre_lenta.py
"""Revisión Q1 (TMG-06 / SEN-04): `pasar_a_solo_lenta()` abre la lenta en el
mismo paso, aunque no haya presión, salvo vacío confirmado."""

import pytest

from autoclave.state_machine.cycle_phases.protocolo_fallo import _DEBOUNCE_LECTURAS
from tests.test_q1_r1p4_principal_perdido_tras_protocolo import _protocolo


@pytest.mark.parametrize("pres", [None, 250.0, 101.3])
def test_pasar_a_solo_lenta_abre_la_lenta_en_el_mismo_paso(pres):
    prot, estado, set_do = _protocolo(1)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = pres
    set_do.reset_mock()
    assert prot.pasar_a_solo_lenta() is True
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_lenta_on.assert_called()


def test_pasar_a_solo_lenta_en_vacio_no_abre_la_lenta():
    prot, estado, set_do = _protocolo(1)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 50.0          # < atm - rango
    set_do.reset_mock()
    prot.pasar_a_solo_lenta()
    set_do.descompresion_lenta_on.assert_not_called()


def test_sin_presion_el_update_deja_la_lenta_abierta():
    prot, estado, set_do = _protocolo(1)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    estado.sensores_temp["temp_camara"] = None
    set_do.reset_mock()
    for _ in range(_DEBOUNCE_LECTURAS):
        prot.update()
    assert prot.solo_lenta is True
    set_do.descompresion_lenta_on.assert_called()
