"""Tanda 32, LIQ-01 y LIQ-02: componente puro EnfriamientoContrapresion."""

import math

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import enfriamiento_contrapresion as ec
from autoclave.state_machine.cycle_phases.enfriamiento_contrapresion import (
    ENFR_CONTRAPRESION_BAJA,
    ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA,
    ENFR_TIMEOUT_PRESURIZACION,
    EnfriamientoContrapresion,
)

ATM = 75.0
P_OBJ = 200.0
T = 100.0                                   # Principal
P_MIN = p_saturacion_kpa(T) + 30.0          # ≈131.4 kPa


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def _params(**kw):
    p = {
        "presion_camara_enfriamiento": P_OBJ,
        "presion_despresurizacion_chaqueta": 10.0,
        "timeout_despresurizacion_chaqueta": 5,
        "timeout_presurizacion_enfriamiento": 10,
    }
    p.update(kw)
    return p


def _comp(modo_5=False, solo_aviso=False, **kw):
    r = Reloj()
    return EnfriamientoContrapresion(_params(**kw), modo_5=modo_5,
                                     solo_aviso=solo_aviso, ahora=r), r


def _tick(c, pc=150.0, pj=300.0, t=T, atm=ATM, vig=True):
    return c.tick(pc, pj, t, atm, vig)


def _armar(c, r):
    """Cumple (a) y (b)."""
    res = _tick(c, pc=P_OBJ, pj=ATM)
    assert res.cond_a and res.cond_b and res.agua_chaqueta_on
    return res


# ---------------- LIQ-01 ----------------

def test_orden_aire_chaqueta_agua():
    c, r = _comp()
    res = _tick(c, pc=150.0, pj=300.0)
    assert res.aire_comprimido_on and res.aire_comprimido_pulso
    assert res.descompresion_chaqueta_on
    assert not res.agua_chaqueta_on and not res.cond_a and not res.cond_b
    r.avanzar(1)
    res = _tick(c, pc=170.0, pj=ATM + 10.0)        # (b) en el borde
    assert res.cond_b and not res.cond_a and not res.agua_chaqueta_on
    assert res.aire_comprimido_on
    r.avanzar(1)
    res = _tick(c, pc=P_OBJ, pj=ATM)
    assert res.cond_a and res.agua_chaqueta_on
    assert not res.aire_comprimido_on               # presión alcanzada
    assert res.descompresion_chaqueta_on


def test_agua_no_abre_solo_con_a():
    c, r = _comp()
    res = _tick(c, pc=P_OBJ, pj=300.0)
    assert res.cond_a and not res.cond_b and not res.agua_chaqueta_on


def test_aire_reafirmado_cada_3_s_y_sostenido():
    c, r = _comp()
    assert _tick(c).aire_comprimido_pulso
    r.avanzar(1)
    res = _tick(c)
    assert res.aire_comprimido_on and not res.aire_comprimido_pulso
    r.avanzar(2)
    assert _tick(c).aire_comprimido_pulso


def test_enclavamientos_no_se_pierden_y_agua_sigue_abierta():
    c, r = _comp()
    _armar(c, r)
    r.avanzar(1)
    res = _tick(c, pc=150.0, pj=300.0)               # cae cámara, sube chaqueta
    assert res.cond_a and res.cond_b and res.agua_chaqueta_on
    assert res.aire_comprimido_on                    # el aire sigue reponiendo
    r.avanzar(1)
    res = _tick(c, pc=None, pj=None, vig=False)
    assert res.cond_a and res.cond_b and res.agua_chaqueta_on


def test_chaqueta_fija_sin_pulsos():
    c, r = _comp()
    for _ in range(40):
        assert _tick(c).descompresion_chaqueta_on
        r.avanzar(1)


def test_tope_despresurizacion_chaqueta():
    c, r = _comp()
    _tick(c, pc=P_OBJ, pj=300.0)
    r.avanzar(5 * 60 - 1)
    assert _tick(c, pc=P_OBJ, pj=300.0).fallo is None
    r.avanzar(1)
    res = _tick(c, pc=P_OBJ, pj=300.0)
    assert res.fallo == ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA
    assert not (res.aire_comprimido_on or res.agua_chaqueta_on
                or res.descompresion_chaqueta_on or res.descompresion_lenta_on)
    r.avanzar(1)
    assert _tick(c, pc=P_OBJ, pj=ATM).fallo == ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA


def test_tope_presurizacion():
    c, r = _comp()
    _tick(c, pc=150.0, pj=ATM)
    r.avanzar(10 * 60 - 1)
    assert _tick(c, pc=150.0, pj=ATM).fallo is None
    r.avanzar(1)
    assert _tick(c, pc=150.0, pj=ATM).fallo == ENFR_TIMEOUT_PRESURIZACION


def test_topes_aplican_en_solo_aviso():
    c, r = _comp(solo_aviso=True)
    _tick(c, pc=150.0, pj=ATM)
    r.avanzar(10 * 60)
    assert _tick(c, pc=150.0, pj=ATM).fallo == ENFR_TIMEOUT_PRESURIZACION


def test_sin_lectura_camara_no_cumple_a_ni_aire():
    c, r = _comp()
    for v in (None, float("nan"), 0.0, -5.0, True, "200"):
        res = _tick(c, pc=v, pj=ATM)
        assert not res.cond_a and not res.aire_comprimido_on
        r.avanzar(0.1)


def test_sin_lectura_chaqueta_no_cumple_b():
    c, r = _comp()
    for v in (None, float("inf"), 0.0, False):
        res = _tick(c, pc=P_OBJ, pj=v)
        assert not res.cond_b and not res.agua_chaqueta_on


def test_sin_atmosferica_no_cumple_b():
    c, r = _comp()
    res = _tick(c, pc=P_OBJ, pj=ATM, atm=None)
    assert not res.cond_b and not res.agua_chaqueta_on


def test_ai_vencida_sin_aire_y_sin_condiciones():
    c, r = _comp()
    res = _tick(c, pc=150.0, pj=ATM, vig=False)
    assert not res.aire_comprimido_on and not res.cond_a and not res.cond_b
    res = _tick(c, pc=P_OBJ, pj=ATM, vig=False)
    assert not res.cond_a and not res.cond_b


def test_modo_5_lenta_desde_primer_tick_modo_4_sin_lenta():
    c5, _ = _comp(modo_5=True)
    assert _tick(c5).descompresion_lenta_on
    c4, _ = _comp(modo_5=False)
    assert not _tick(c4).descompresion_lenta_on


def test_parametros_invalidos_rechazados():
    for kw in ({"presion_camara_enfriamiento": None},
               {"presion_camara_enfriamiento": 0},
               {"presion_despresurizacion_chaqueta": -1},
               {"timeout_despresurizacion_chaqueta": 0},
               {"timeout_presurizacion_enfriamiento": float("nan")},
               {"timeout_presurizacion_enfriamiento": True}):
        with pytest.raises(ValueError):
            _comp(**kw)


# ---------------- LIQ-02 ----------------

def test_no_armada_antes_de_a():
    c, r = _comp()
    for _ in range(120):
        res = _tick(c, pc=110.0, pj=ATM, t=T)        # bajo P_MIN pero sin (a)
        assert not res.armada and not res.aviso_contrapresion and res.fallo is None
        r.avanzar(1)


def test_aviso_a_10_s_y_fallo_a_60_s():
    c, r = _comp()
    _armar(c, r)
    bajo = P_MIN - 5
    res = _tick(c, pc=bajo, pj=ATM)
    assert res.armada and not res.aviso_contrapresion
    assert math.isclose(res.presion_minima, P_MIN)
    r.avanzar(9.9)
    assert not _tick(c, pc=bajo, pj=ATM).aviso_contrapresion
    r.avanzar(0.1)
    res = _tick(c, pc=bajo, pj=ATM)
    assert res.aviso_contrapresion and res.fallo is None
    assert res.aire_comprimido_on and res.agua_chaqueta_on
    r.avanzar(49.9)
    assert _tick(c, pc=bajo, pj=ATM).fallo is None
    r.avanzar(0.1)
    res = _tick(c, pc=bajo, pj=ATM)
    assert res.fallo == ENFR_CONTRAPRESION_BAJA
    assert not res.agua_chaqueta_on and not res.aire_comprimido_on


def test_recuperacion_reinicia_conteo_y_despeja_aviso():
    c, r = _comp()
    _armar(c, r)
    bajo = P_MIN - 5
    _tick(c, pc=bajo, pj=ATM)
    r.avanzar(50)
    assert _tick(c, pc=bajo, pj=ATM).aviso_contrapresion
    r.avanzar(1)
    res = _tick(c, pc=P_MIN + 1, pj=ATM)
    assert not res.aviso_contrapresion and res.segundos_bajo_minimo == 0.0
    r.avanzar(1)
    _tick(c, pc=bajo, pj=ATM)
    r.avanzar(59)
    res = _tick(c, pc=bajo, pj=ATM)
    assert res.fallo is None and res.aviso_contrapresion


def test_p_min_recalculado_cada_tick():
    c, r = _comp()
    _armar(c, r)
    res = _tick(c, pc=150.0, pj=ATM, t=110.0)
    assert math.isclose(res.presion_minima, p_saturacion_kpa(110.0) + 30.0)


@pytest.mark.parametrize("kw", [
    {"t": None}, {"t": float("nan")}, {"t": 0.0}, {"t": 500.0},   # 500 °C → ValueError
    {"pc": None}, {"vig": False},
])
def test_falla_cerrada_cuenta_como_bajo_minimo(kw):
    c, r = _comp()
    _armar(c, r)
    args = {"pc": P_OBJ, "pj": ATM}
    args.update(kw)
    _tick(c, **args)
    r.avanzar(10)
    assert _tick(c, **args).aviso_contrapresion
    r.avanzar(50)
    assert _tick(c, **args).fallo == ENFR_CONTRAPRESION_BAJA


def test_solo_aviso_nunca_falla_por_contrapresion():
    c, r = _comp(solo_aviso=True)
    _armar(c, r)
    for _ in range(300):
        res = _tick(c, pc=None, pj=ATM, t=None)
        assert res.fallo is None
        r.avanzar(1)
    assert res.aviso_contrapresion and res.agua_chaqueta_on


def test_constantes():
    assert ec.TIEMPO_AVISO_CONTRAPRESION_S == 10
    assert ec.TIEMPO_FALLO_CONTRAPRESION_S == 60
    assert ec.PERIODO_AIRE_COMPRIMIDO_S == 3.0
