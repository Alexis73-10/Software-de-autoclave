# tests/test_q1rev_solo_lenta_debounce.py
"""Revisión Q1 (SAF-01 / SEN-02 / TMG-07): el paso a `solo_lenta` con el
protocolo en marcha exige _DEBOUNCE_LECTURAS lecturas inválidas seguidas del
Principal; una válida reinicia el contador."""

from autoclave.state_machine.cycle_phases.protocolo_fallo import _DEBOUNCE_LECTURAS
from tests.test_q1_r1p4_principal_perdido_tras_protocolo import _protocolo


def test_una_lectura_invalida_no_basta():
    prot, estado, _ = _protocolo(1)
    prot.ejecutar()
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS - 1):
        prot.update()
        assert prot.solo_lenta is False
    prot.update()
    assert prot.solo_lenta is True


def test_una_lectura_valida_reinicia_el_contador():
    prot, estado, _ = _protocolo(1)
    prot.ejecutar()
    for _ in range(3):
        for valor in (None, 0):
            estado.sensores_temp["temp_camara"] = valor
            prot.update()
        estado.sensores_temp["temp_camara"] = 130.0
        prot.update()
    assert prot.solo_lenta is False


def test_reset_reinicia_el_contador():
    prot, estado, _ = _protocolo(1)
    prot.ejecutar()
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS - 1):
        prot.update()
    prot.reset()
    prot.ejecutar()
    prot.update()
    assert prot.solo_lenta is False
