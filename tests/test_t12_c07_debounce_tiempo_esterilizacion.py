# tests/test_t12_c07_debounce_tiempo_esterilizacion.py
#
# Tanda 12, C-07.2: las 4 fallas de ESTERILIZACION (temp alta/baja, pres
# alta/baja del Principal contra T_est fija) pasan de 3 lecturas a 5 s
# continuos (monotonic). Una lectura dentro de rango reinicia el conteo.

import pytest

from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases import esterilizacion as est
from tests import t12_e12_apoyo as ap

T_EST = 134.0

# (código del motivo, temperatura, presión) fuera de rango, con dT de C-03
# dentro de ±2 K para que solo actúe la falla bajo prueba
_CASOS = {
    "est_temp_alta": (137.5, ap.psat(136.0)),        # > 134 + 3
    "est_temp_baja": (133.8, ap.psat(134.0)),        # < 134 - 0.1
    "est_pres_alta": (137.0, ap.psat(134.0) + 31.0),  # > Psat(134) + 30
    "est_pres_baja": (134.0, ap.psat(134.0) - 2.1),  # < Psat(134) - 2
}
_DENTRO = (134.5, ap.psat(134.5))


def test_constante():
    assert est._DEBOUNCE_FALLA_S == 5.0


@pytest.mark.parametrize("codigo", sorted(_CASOS))
def test_muchas_lecturas_en_menos_de_5_s_no_fallan(monkeypatch, codigo):
    temp, pres = _CASOS[codigo]
    f, _, _, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=temp, pres=pres)
    for _ in range(10):                      # 10 lecturas en 4.5 s (antes: FALLO a la 3.ª)
        assert f.update() == FaseResult.EN_CURSO
        reloj.avanzar(0.5)
    reloj.t -= 0.1                           # 4.9 s desde la primera lectura
    assert f.update() == FaseResult.EN_CURSO


@pytest.mark.parametrize("codigo", sorted(_CASOS))
def test_5_s_continuos_fallan(monkeypatch, codigo):
    temp, pres = _CASOS[codigo]
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=temp, pres=pres)
    f.update()
    reloj.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    assert getattr(estado.motivo_fallo, "codigo", None) == codigo
    set_do.vapor_camara_off.assert_called()


@pytest.mark.parametrize("codigo", sorted(_CASOS))
def test_una_lectura_dentro_reinicia(monkeypatch, codigo):
    temp, pres = _CASOS[codigo]
    f, estado, _, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=temp, pres=pres)
    f.update()
    reloj.avanzar(4.5)
    assert f.update() == FaseResult.EN_CURSO
    ap.poner(estado, *_DENTRO)
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO          # reinicia
    ap.poner(estado, temp, pres)
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO          # t = 0 del nuevo conteo
    reloj.avanzar(4.9)
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(0.1)
    assert f.update() == FaseResult.FALLO
