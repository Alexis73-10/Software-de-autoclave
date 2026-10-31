# tests/test_consignas_pdf.py
#
# Consignas de esterilización para la gráfica de los PDF (D-14):
# ui_qml/domain/consignas.py.

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.ui_qml.domain.consignas import consigna_esterilizacion

_FASES = [{"clave": "vacio", "inicioMin": 0.0}, {"clave": "calentamiento", "inicioMin": 9.0},
          {"clave": "esterilizacion", "inicioMin": 15.0}, {"clave": "secado", "inicioMin": 22.0}]


def test_tramo_de_esterilizacion_con_su_presion_de_saturacion():
    c = consigna_esterilizacion(134, _FASES, t_fin_min=40.0)
    assert c == {"temp": 134.0, "pres": pytest.approx(p_saturacion_kpa(134.0)),
                 "desde_min": 15.0, "hasta_min": 22.0}


def test_ciclo_que_termina_en_esterilizacion():
    c = consigna_esterilizacion(121, _FASES[:3], t_fin_min=17.5)
    assert (c["desde_min"], c["hasta_min"]) == (15.0, 17.5)


@pytest.mark.parametrize("temp, fases", [
    (None, _FASES), ("134", _FASES), (80, _FASES), (160, _FASES),   # sin dato o fuera de 99-145 °C
    (134, _FASES[:2]),                                              # no llegó a esterilizar
    (134, []),
])
def test_sin_consigna(temp, fases):
    assert consigna_esterilizacion(temp, fases, t_fin_min=40.0) is None
