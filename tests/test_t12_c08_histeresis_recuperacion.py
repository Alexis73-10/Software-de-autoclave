# tests/test_t12_c08_histeresis_recuperacion.py
#
# Tanda 12, C-08: entrada a RECUPERACION inmediata (como antes); salida a
# PWM_ACTIVO con histéresis (+0.3 K y +1.0 kPa); en RECUPERACION el techo
# P_control_max también corta el vapor.

from autoclave.state_machine.cycle_phases import esterilizacion as est
from tests import t12_e12_apoyo as ap

T_EST = 134.0
BRECHA = 1.0          # brecha_segura_temperatura de la tanda 12 (C-07.1)


def _fase(monkeypatch, **kw):
    return ap.fase(monkeypatch, t_est=T_EST, brecha_seg=BRECHA, brecha_seg_p=1.5, **kw)


def test_constantes():
    assert est._HIST_RECUP_TEMP_K == 0.3
    assert est._HIST_RECUP_PRES_KPA == 1.0


def test_t_oscilando_entre_1_0_y_1_2_no_conmuta_desde_recuperacion(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    assert f._en_recuperacion is True
    tramos = []
    for i in range(40):
        t = T_EST + (1.0 if i % 2 == 0 else 1.2)
        ap.poner(estado, t, ap.psat(t))
        reloj.avanzar(0.5)
        f.update()
        tramos.append(f._en_recuperacion)
    assert all(tramos)                       # nunca sale (no llega a +1.3 K)


def test_t_oscilando_entre_1_0_y_1_2_no_conmuta_desde_pwm(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    ap.poner(estado, T_EST + 1.4, ap.psat(T_EST + 1.4))
    reloj.avanzar(0.5)
    f.update()
    assert f._en_recuperacion is False
    tramos = []
    for i in range(40):
        t = T_EST + (1.0 if i % 2 == 0 else 1.2)
        ap.poner(estado, t, ap.psat(t))
        reloj.avanzar(0.5)
        f.update()
        tramos.append(f._en_recuperacion)
    assert not any(tramos)                   # nunca vuelve (no baja de +1.0 K)


def test_entrada_inmediata_por_temperatura(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    ap.poner(estado, T_EST + 1.4, ap.psat(T_EST + 1.4))
    f.update()
    assert f._en_recuperacion is False
    ap.poner(estado, T_EST + 0.99, ap.psat(T_EST + 0.99))
    f.update()
    assert f._en_recuperacion is True


def test_salida_exige_histeresis_de_presion(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    p_ref = ap.psat(T_EST) - 1.5
    ap.poner(estado, T_EST + 2.0, p_ref + 0.9)
    f.update()
    assert f._en_recuperacion is True        # falta 0.1 kPa de histéresis
    ap.poner(estado, T_EST + 2.0, p_ref + 1.0)
    f.update()
    assert f._en_recuperacion is False


def test_salida_exige_histeresis_de_temperatura(monkeypatch):
    f, estado, _, _ = _fase(monkeypatch)
    f.update()
    ap.poner(estado, T_EST + 1.29, ap.psat(T_EST + 1.29))
    f.update()
    assert f._en_recuperacion is True
    ap.poner(estado, T_EST + 1.3, ap.psat(T_EST + 1.3))
    f.update()
    assert f._en_recuperacion is False


def test_en_recuperacion_techo_de_control_apaga_el_vapor(monkeypatch):
    f, estado, set_do, _ = _fase(monkeypatch, presion_add=11.0)
    f.update()
    p_control_max = ap.psat(T_EST) + 11.0
    ap.poner(estado, T_EST + 0.5, p_control_max + 0.5)    # T bajo la brecha: RECUPERACION
    set_do.reset_mock()
    f.update()
    assert f._en_recuperacion is True
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_en_recuperacion_bajo_el_techo_vapor_on(monkeypatch):
    f, estado, set_do, _ = _fase(monkeypatch, presion_add=11.0)
    f.update()
    ap.poner(estado, T_EST + 0.5, ap.psat(T_EST + 0.5))
    set_do.reset_mock()
    f.update()
    assert f._en_recuperacion is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


# ── Histéresis del techo en RECUPERACION (DECISIÓN SIN CONFIRMAR, tanda 12) ──
# Con 134/9, Tsat(P_control_max) ≈ 135.01 °C < salida de C-08.2 (135.3 °C):
# con vapor saturado la fase queda en RECUPERACION pegada al techo.

def test_constante_histeresis_techo():
    assert est._HIST_TECHO_KPA == 2.0


def test_t_135_y_p_oscilando_en_el_techo_no_conmuta_cada_tick(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, presion_add=9.0)
    f.update()
    techo = ap.psat(T_EST) + 9.0
    comandos = []
    for i in range(40):
        p = techo + (0.3 if i % 2 == 0 else -0.3)   # alrededor del techo
        ap.poner(estado, 135.0, p)
        set_do.reset_mock()
        reloj.avanzar(0.5)
        f.update()
        assert f._en_recuperacion is True
        if set_do.vapor_camara_on.called:
            comandos.append("on")
        elif set_do.vapor_camara_off.called:
            comandos.append("off")
    assert comandos == ["off"] * 40                  # una vez arriba, OFF sostenido


def test_vuelve_a_on_bajo_techo_menos_2_kpa(monkeypatch):
    f, estado, set_do, _ = _fase(monkeypatch, presion_add=9.0)
    f.update()
    techo = ap.psat(T_EST) + 9.0
    ap.poner(estado, 135.0, techo)
    f.update()
    ap.poner(estado, 135.0, techo - 1.9)
    set_do.reset_mock()
    f.update()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    ap.poner(estado, 135.0, techo - 2.1)
    set_do.reset_mock()
    f.update()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()
