# tests/test_t12_c10_sin_medicion.py
#
# Tanda 12, C-10: sin exposición sin medición válida.
#  C-10.1: en CicloState la vigilancia SENSOR_AUSENTE (§4) corre antes de
#          fase.update() en el mismo tick: con el Principal o la presión sin
#          lectura el ciclo pasa a FALLO sin que ESTERILIZACION cuente el tick.
#  C-10.2: defensa propia de la fase: el tiempo sin lectura corre el fin de
#          la exposición (sin sumarlo a pausa_total_s de CIC-11).

from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from tests.helpers import t12_e12_apoyo as ap
from tests.test_t3_sensores_ciclo import _ciclo

_ASIG = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"}


# ── C-10.2: fase ─────────────────────────────────────────────────────────────

def test_60_s_sin_datos_corren_el_fin_60_s(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, tiempo_min=1)        # 60 s
    assert f.update() == FaseResult.EN_CURSO                         # t = 0
    fin_original = f._timer_fin
    estado.sensores_temp["temp_camara"] = None
    reloj.avanzar(0.5)
    for _ in range(120):                                             # 60 s sin datos
        assert f.update() == FaseResult.EN_CURSO
        reloj.avanzar(0.5)
    assert f._timer_fin == fin_original                              # todavía sin correr
    estado.sensores_temp["temp_camara"] = 134.0
    assert f.update() == FaseResult.EN_CURSO                         # t = 60.5
    # SAF-05 / P8 (tanda 16, D-14.8): el tramo descontado empieza en la última
    # lectura válida (t = 0), no en el primer tick sin dato (t = 0.5): 60.5 s
    assert f._timer_fin == fin_original + 60.5
    assert f.pausa_total_s == 0.0                                    # no suma al tope de CIC-11
    assert f.sin_lectura_s == 60.5
    reloj.t = fin_original + 60.4
    assert f.update() == FaseResult.EN_CURSO
    reloj.t = fin_original + 60.5
    assert f.update() == FaseResult.COMPLETADO


def test_presion_sin_lectura_tambien_corre_el_fin(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, tiempo_min=1)
    f.update()
    fin_original = f._timer_fin
    estado.sensores_pres["pres_camara"] = None
    reloj.avanzar(1.0)
    f.update()
    reloj.avanzar(30.0)
    f.update()
    estado.sensores_pres["pres_camara"] = ap.psat(134.0)
    f.update()
    # SAF-05 / P8 (tanda 16, D-14.8): desde la última lectura válida (1 s antes)
    assert f._timer_fin == fin_original + 31.0


def test_sin_datos_no_completa_aunque_haya_vencido(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, tiempo_min=1)
    f.update()
    estado.sensores_temp["temp_camara"] = None
    reloj.avanzar(1.0)
    f.update()
    reloj.avanzar(100.0)
    assert f.update() == FaseResult.EN_CURSO


# ── C-10.1: CicloState ───────────────────────────────────────────────────────

def _ciclo_en_esterilizacion(sensores_temp):
    ciclo, estado, am = _ciclo(_ASIG, sensores_temp)
    estado.sensores_pres["pres_camara"] = ap.psat(134.0)
    ciclo._fase_idx = 3
    fase = ciclo._fases[3]
    assert isinstance(fase, EsterilizacionFase)
    fase.update()                                   # exposición iniciada
    assert fase._timer_fin is not None
    return ciclo, estado, am, fase


def test_principal_sin_lectura_falla_sen02_sin_que_la_fase_cuente_el_tick():
    ciclo, estado, am, fase = _ciclo_en_esterilizacion({"temp_camara": 134.0})
    fin = fase._timer_fin
    estado.sensores_temp["temp_camara"] = None
    fase.update = MagicMock(wraps=fase.update)
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    fase.update.assert_not_called()                 # §4 corre antes que la fase
    assert fase._timer_fin == fin
    assert [i.codigo for i in am.activas()] == ["SEN-02"]
    assert ciclo._resultado_pendiente == "FALLO"


def test_presion_sin_lectura_falla_sin_que_la_fase_cuente_el_tick():
    ciclo, estado, am, fase = _ciclo_en_esterilizacion({"temp_camara": 134.0})
    estado.sensores_pres["pres_camara"] = None
    fase.update = MagicMock(wraps=fase.update)
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    fase.update.assert_not_called()
    assert [i.codigo for i in am.activas()] == ["SEN-04"]
