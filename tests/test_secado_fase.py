# tests/test_secado_fase.py
import time as time_module
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.secado import (
    SecadoFase, _PASO_VACIO_BAJO, _PASO_AIRE_ALTO
)
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(
    modo=1, tiempo_min=5.0,
    presion_chaqueta=200, rango_chaqueta=30,
    presion_baja=20.0, presion_alta=80.0,
    timeout_pulso=10, has_vacuum=True,
    pres_camara=50.0, pres_chaqueta=200.0,
):
    estado = MagicMock()
    estado.sensores_pres = {
        "pres_camara": pres_camara,
        "pres_chaqueta": pres_chaqueta,
    }

    set_do = MagicMock()

    params = {
        "modo": modo,
        "tiempo_secado": tiempo_min,
        "presion_chaqueta_secado": presion_chaqueta,
        "rango_chaqueta_secado": rango_chaqueta,
        "presion_baja_secado": presion_baja,
        "presion_alta_secado": presion_alta,
        "timeout_pulso": timeout_pulso,
    }

    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, param, default=None: params.get(param, default)

    fase = SecadoFase(estado, set_do, cycle, MagicMock(), MagicMock(), MagicMock())
    fase.cap.has_vacuum = has_vacuum
    fase.reset()
    return fase, estado, set_do


# ── skip ─────────────────────────────────────────────────────────────────────

def test_skip_sin_vacío():
    fase, _, set_do = _make_fase(has_vacuum=False)
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()


def test_skip_tiempo_cero():
    fase, _, set_do = _make_fase(tiempo_min=0)
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()


# ── modo 1 ───────────────────────────────────────────────────────────────────

def test_modo1_activa_vacio_cada_tick():
    fase, _, set_do = _make_fase(modo=1)
    assert fase.update() == FaseResult.EN_CURSO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_modo1_completa_al_expirar_timer():
    fase, _, set_do = _make_fase(modo=1, tiempo_min=1)
    fase.update()            # inicializar
    fase._timer_fin -= 200   # simular tiempo transcurrido
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_off.assert_called()
    set_do.vacio_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_modo1_chaqueta_on_cuando_presion_baja():
    fase, estado, set_do = _make_fase(modo=1, presion_chaqueta=200, rango_chaqueta=30)
    estado.sensores_pres["pres_chaqueta"] = 100.0   # muy por debajo
    fase.update()
    set_do.vapor_chaqueta_on.assert_called()


def test_modo1_chaqueta_off_cuando_presion_alta():
    fase, estado, set_do = _make_fase(modo=1, presion_chaqueta=200, rango_chaqueta=30)
    estado.sensores_pres["pres_chaqueta"] = 350.0   # muy por encima
    fase.update()
    set_do.vapor_chaqueta_off.assert_called()


# ── modo 2 ───────────────────────────────────────────────────────────────────

def test_modo2_activa_vacio_y_aire():
    fase, _, set_do = _make_fase(modo=2)
    assert fase.update() == FaseResult.EN_CURSO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


def test_modo2_apaga_aire_al_completar():
    fase, _, set_do = _make_fase(modo=2, tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    assert fase.update() == FaseResult.COMPLETADO
    set_do.aire_admosferico_camara_off.assert_called()


# ── modo 3 ───────────────────────────────────────────────────────────────────

def test_modo3_inicia_en_vacio_bajo():
    fase, _, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    assert fase.update() == FaseResult.EN_CURSO
    assert fase._sub_estado == _PASO_VACIO_BAJO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_modo3_transicion_a_aire_al_alcanzar_presion_baja():
    fase, estado, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    fase.update()   # inicializar en VACIO_BAJO; pres=50 > 20, no transiciona
    estado.sensores_pres["pres_camara"] = 15.0   # ahora pres <= presion_baja
    set_do.reset_mock()
    fase.update()
    assert fase._sub_estado == _PASO_AIRE_ALTO
    set_do.vacio_camara_off.assert_called()
    set_do.bomba_vacio_off.assert_called()


def test_modo3_transicion_a_vacio_al_alcanzar_presion_alta():
    fase, estado, set_do = _make_fase(
        modo=3, pres_camara=15.0, presion_baja=20.0, presion_alta=80.0
    )
    fase.update()   # inicializar; pres=15 <= 20 → transiciona a AIRE_ALTO en este tick
    assert fase._sub_estado == _PASO_AIRE_ALTO
    estado.sensores_pres["pres_camara"] = 90.0   # pres >= presion_alta
    set_do.reset_mock()
    fase.update()
    assert fase._sub_estado == _PASO_VACIO_BAJO
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo3_fallo_timeout_vacio_bajo():
    fase, _, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    fase.update()   # inicializar
    fase._timeout_pulso_fin -= 200   # simular timeout
    assert fase.update() == FaseResult.FALLO
    set_do.bomba_vacio_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_modo3_fallo_timeout_aire_alto():
    fase, estado, set_do = _make_fase(
        modo=3, pres_camara=15.0, presion_baja=20.0, presion_alta=80.0
    )
    fase.update()   # inicializar; transiciona a AIRE_ALTO
    assert fase._sub_estado == _PASO_AIRE_ALTO
    fase._timeout_pulso_fin -= 200
    assert fase.update() == FaseResult.FALLO
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo3_completa_cuando_expira_timer_fin():
    fase, _, set_do = _make_fase(modo=3, tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_off.assert_called()


# ── Reloj monótono (C-01) ────────────────────────────────────────────────

def test_timer_fin_inmune_a_salto_de_reloj_de_pared(monkeypatch):
    fake_monotonic = [1000.0]
    monkeypatch.setattr(time_module, "monotonic", lambda: fake_monotonic[0])
    monkeypatch.setattr(time_module, "time", lambda: 10.0)

    fase, _, set_do = _make_fase(modo=1, tiempo_min=1)  # 60s
    fase.update()  # inicializa _timer_fin con monotonic=1000.0

    fake_monotonic[0] += 61  # reloj monótono avanza 61s (tiempo cumplido)

    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.bomba_vacio_off.assert_called()
