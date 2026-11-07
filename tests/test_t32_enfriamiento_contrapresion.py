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


def _comp(modo_5=False, solo_aviso=False, presion_max_reposicion=None, **kw):
    r = Reloj()
    return EnfriamientoContrapresion(_params(**kw), modo_5=modo_5,
                                     solo_aviso=solo_aviso, ahora=r,
                                     presion_max_reposicion=presion_max_reposicion), r


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


def test_topes_en_solo_aviso_no_fallan_y_mantienen_la_contrapresion():
    """Revisión de la tanda 32 (hallazgo 1): con solo_aviso el tope queda
    enclavado en `tope`, sin fallo; el aire sigue reponiendo, la chaqueta
    sigue abierta y el agua y la lenta quedan cerradas."""
    c, r = _comp(modo_5=True, solo_aviso=True)
    assert _tick(c, pc=150.0, pj=ATM).descompresion_lenta_on
    r.avanzar(10 * 60)
    res = _tick(c, pc=150.0, pj=ATM)
    assert res.fallo is None and c.fallo is None
    assert res.tope == ENFR_TIMEOUT_PRESURIZACION == c.tope
    assert res.aire_comprimido_on and res.descompresion_chaqueta_on
    assert not res.descompresion_lenta_on and not res.agua_chaqueta_on
    # aunque después se cumplan (a) y (b), el agua no abre y el tope no cambia
    r.avanzar(1)
    res = _tick(c, pc=P_OBJ, pj=ATM)
    assert res.cond_a and res.cond_b and not res.agua_chaqueta_on
    assert not res.descompresion_lenta_on and res.tope == ENFR_TIMEOUT_PRESURIZACION


def test_tope_chaqueta_en_solo_aviso():
    c, r = _comp(solo_aviso=True)
    _tick(c, pc=P_OBJ, pj=300.0)
    r.avanzar(5 * 60)
    res = _tick(c, pc=P_OBJ - 20, pj=300.0)
    assert res.fallo is None and res.tope == ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA
    assert res.aire_comprimido_on and not res.agua_chaqueta_on


# ---------------- M1 (revisión de la tanda 32) ----------------

T_EST = 121.0
P_CONTRA = p_saturacion_kpa(T_EST) + 30.0     # contrapresión mínima a T_est


def test_m1_principal_sobre_t_est_con_contrapresion_minima_sin_aviso_ni_fallo():
    """Objetivo = Psat(T_est) + 30 y el Principal 1 °C sobre T_est: el aire
    repone hasta P_min + 2 y no hay aviso ni CIC-24."""
    c, r = _comp(presion_camara_enfriamiento=P_CONTRA, presion_max_reposicion=375.0)
    t = T_EST + 1.0
    p_min = p_saturacion_kpa(t) + 30.0
    pc = P_CONTRA
    for _ in range(120):
        res = c.tick(pc, ATM, t, ATM, True)
        assert res.fallo is None and not res.aviso_contrapresion
        # planta mínima: el aire sube la presión 1 kPa por tick, sin aire baja 1
        pc = pc + 1.0 if res.aire_comprimido_on else pc - 1.0
        r.avanzar(1)
    assert res.armada and p_min - 1.0 <= pc <= p_min + ec.HISTERESIS_REPOSICION_AIRE_KPA + 1.0


def test_m1_objetivo_de_reposicion():
    c, r = _comp(presion_max_reposicion=375.0)
    t = 130.0
    p_min = p_saturacion_kpa(t) + 30.0                    # ≈300 kPa > objetivo
    assert _tick(c, pc=p_min + 1.9, t=t).aire_comprimido_on
    r.avanzar(1)
    assert not _tick(c, pc=p_min + 2.0, t=t).aire_comprimido_on
    # sin P_min calculable: solo el objetivo
    r.avanzar(1)
    assert not _tick(c, pc=P_OBJ, t=None).aire_comprimido_on
    r.avanzar(1)
    assert _tick(c, pc=P_OBJ - 1, t=None).aire_comprimido_on
    # P_min bajo el objetivo: rige el objetivo
    r.avanzar(1)
    assert _tick(c, pc=P_OBJ - 1, t=80.0).aire_comprimido_on


def test_m1_reposicion_acotada():
    c, r = _comp(presion_max_reposicion=250.0)
    t = 134.0                                             # P_min + 2 ≈ 336 kPa
    assert _tick(c, pc=249.0, t=t).aire_comprimido_on
    r.avanzar(1)
    assert not _tick(c, pc=250.0, t=t).aire_comprimido_on
    # sin límite: objetivo + 30
    c2, r2 = _comp()
    assert _tick(c2, pc=P_OBJ + 29.0, t=t).aire_comprimido_on
    r2.avanzar(1)
    assert not _tick(c2, pc=P_OBJ + 30.0, t=t).aire_comprimido_on
    # M-A (segunda revisión): un límite bajo el objetivo SÍ acota la
    # reposición (nunca se repone sobre alivio − 10)
    c3, r3 = _comp(presion_max_reposicion=150.0)
    assert _tick(c3, pc=149.0, t=t).aire_comprimido_on
    r3.avanzar(1)
    assert not _tick(c3, pc=150.0, t=t).aire_comprimido_on


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
    assert ec.HISTERESIS_REPOSICION_AIRE_KPA == 2.0


# ---------------- Segunda revisión de seguridad (M-A, M-B) ----------------

@pytest.mark.parametrize("t", [None, 80.0, 134.0])
def test_ma_objetivo_sobre_el_tope_nunca_repone_sobre_el_tope(t):
    """presion_camara_enfriamiento 395 (programa que el catálogo rechaza) con
    el tope del equipo 375 (alivio 385 − 10): el aire corta en 375."""
    c, r = _comp(presion_max_reposicion=375.0, presion_camara_enfriamiento=395.0)
    assert _tick(c, pc=374.0, t=t).aire_comprimido_on
    r.avanzar(1)
    for pc in (375.0, 380.0, 390.0):
        assert not _tick(c, pc=pc, t=t).aire_comprimido_on
        r.avanzar(1)


def test_ma_tope_mayor_que_objetivo_sin_cambio():
    """Con el tope sobre el objetivo, el objetivo de reposición es el de M1."""
    c, r = _comp(presion_max_reposicion=375.0)
    assert _tick(c, pc=P_OBJ - 1, t=80.0).aire_comprimido_on
    r.avanzar(1)
    assert not _tick(c, pc=P_OBJ, t=80.0).aire_comprimido_on


def _bajo_minimo(c, r, segundos):
    res = None
    for _ in range(int(segundos)):
        res = _tick(c, pc=P_MIN - 5, pj=ATM)
        r.avanzar(1)
    return res


def test_mb_solo_aviso_modo_5_cierra_la_lenta_con_el_aviso_y_reabre():
    c, r = _comp(modo_5=True, solo_aviso=True)
    _armar(c, r)
    res = _tick(c, pc=P_MIN - 5, pj=ATM)
    assert res.descompresion_lenta_on and not res.aviso_contrapresion
    r.avanzar(9.9)
    assert _tick(c, pc=P_MIN - 5, pj=ATM).descompresion_lenta_on
    r.avanzar(0.1)
    res = _tick(c, pc=P_MIN - 5, pj=ATM)
    assert res.aviso_contrapresion and not res.descompresion_lenta_on
    assert res.aire_comprimido_on                      # el aire sigue reponiendo
    res = _bajo_minimo(c, r, 120)
    assert res.fallo is None and not res.descompresion_lenta_on
    # recupera P_min: el aviso se despeja y la lenta reabre
    res = _tick(c, pc=P_MIN + 1, pj=ATM)
    assert not res.aviso_contrapresion and res.descompresion_lenta_on


def test_mb_solo_aviso_sin_dato_tambien_cierra_la_lenta():
    c, r = _comp(modo_5=True, solo_aviso=True)
    _armar(c, r)
    _tick(c, pc=None, pj=ATM)
    r.avanzar(10)
    res = _tick(c, pc=None, pj=ATM)
    assert res.aviso_contrapresion and not res.descompresion_lenta_on


def test_mb_fase_sin_cambio_lenta_abierta_hasta_el_fallo():
    """Sin solo_aviso (la fase) la lenta sigue abierta con el aviso; a los
    60 s, CIC-24 (FALLO con todo apagado)."""
    c, r = _comp(modo_5=True, solo_aviso=False)
    _armar(c, r)
    _tick(c, pc=P_MIN - 5, pj=ATM)
    r.avanzar(10)
    res = _tick(c, pc=P_MIN - 5, pj=ATM)
    assert res.aviso_contrapresion and res.descompresion_lenta_on
    r.avanzar(50)
    res = _tick(c, pc=P_MIN - 5, pj=ATM)
    assert res.fallo == ENFR_CONTRAPRESION_BAJA and not res.descompresion_lenta_on


def test_mb_modo_4_sin_lenta_con_o_sin_aviso():
    c, r = _comp(modo_5=False, solo_aviso=True)
    _armar(c, r)
    for _ in range(15):
        res = _tick(c, pc=P_MIN - 5, pj=ATM)
        assert not res.descompresion_lenta_on
        r.avanzar(1)
    assert res.aviso_contrapresion
