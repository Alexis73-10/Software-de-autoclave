# tests/test_t12_v12_correcciones_esterilizacion.py
#
# Tanda 12, V12 (revisión de seguridad), correcciones en ESTERILIZACION:
#  - SAF-01: la exposición no termina en COMPLETADO mientras haya una falla
#    del Principal en conteo (debounce de 5 s sin confirmar): se espera a que
#    se confirme (FALLO) o se despeje.
#  - SAF-03: sin lectura del Principal o de la presión, vapor_camara se
#    corta (la fase no controla a ciegas).

from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap

T_EST = 134.0
_DENTRO = (134.5, ap.psat(134.5))


def _hasta_el_final(monkeypatch):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, tiempo_min=1.0,
                                       temp=_DENTRO[0], pres=_DENTRO[1])
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(57.0)                       # 3 s antes del fin
    assert f.update() == FaseResult.EN_CURSO
    return f, estado, set_do, reloj


def test_saf01_temp_baja_en_conteo_al_final_no_completa(monkeypatch):
    f, estado, _, reloj = _hasta_el_final(monkeypatch)
    ap.poner(estado, 133.8, ap.psat(134.0))   # < T_est - 0.1, aún sin confirmar
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(4.0)                        # ya pasó el fin, la falla lleva 4 s
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(1.0)                        # 5 s continuos → FALLO, no COMPLETADO
    assert f.update() == FaseResult.FALLO
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_temp_baja"


def test_saf01_aire_en_conteo_al_final_no_completa(monkeypatch):
    f, estado, _, reloj = _hasta_el_final(monkeypatch)
    ap.poner(estado, 134.0, ap.psat(136.6))   # dT = +2.6 K (aire), presión dentro
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(4.0)
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(1.0)
    assert f.update() == FaseResult.FALLO


def test_saf01_falla_que_se_despeja_deja_completar(monkeypatch):
    f, estado, _, reloj = _hasta_el_final(monkeypatch)
    ap.poner(estado, 133.8, ap.psat(134.0))
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(4.0)
    assert f.update() == FaseResult.EN_CURSO   # fin vencido, falla en conteo
    ap.poner(estado, *_DENTRO)
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.COMPLETADO


def test_saf03_sin_lectura_corta_vapor(monkeypatch):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, temp=133.0, pres=ap.psat(133.0))
    assert f.update() == FaseResult.EN_CURSO   # RECUPERACION: vapor ON
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.reset_mock()
    estado.sensores_pres["pres_camara"] = None
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
