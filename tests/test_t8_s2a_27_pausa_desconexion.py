"""Tanda 8 / S2a / D8-2.7 (T2-a ampliado; SAF-02 / TMG-02 de la revisión Q1):
la desconexión total del módulo E/S de menos de 5 s (antes de COM-02) y la
ventana después de reconectar (primera DI pendiente y tolerancia de DI
vencida) también pausan la exposición en ESTERILIZACION. Los segundos sin
datos válidos nunca cuentan como esterilización y tampoco acumulan F0."""

import time
from unittest.mock import MagicMock, patch

import pytest

from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_control_loop_test_mode import _make_control_loop
from tests.test_t2_p3_di_vencida import _ciclo


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def _en_esterilizacion(ciclo):
    idx = next(i for i, f in enumerate(ciclo._fases) if f.name == "ESTERILIZACION")
    ciclo._fase_idx = idx
    fase = ciclo._fases[idx]
    fase.update = MagicMock(return_value=None)
    fase.pausar_exposicion = MagicMock()
    return fase


# ── CicloState ─────────────────────────────────────────────────────────────

def test_desconexion_breve_pausa_la_exposicion(reloj):
    flags = {}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_tarjeta_s = 0.0
    fase = _en_esterilizacion(ciclo)

    # el ControlLoop no corre run() sin enlace: solo marca el tramo
    for _ in range(6):
        ciclo.marcar_sin_datos_tarjeta()
        reloj[0] += 0.5
    assert ciclo.exposicion_en_pausa is True
    fase.pausar_exposicion.assert_not_called()

    ciclo.run()                                        # vuelve el enlace con datos
    fase.pausar_exposicion.assert_called_once()
    assert fase.pausar_exposicion.call_args.args[0] == pytest.approx(3.0)
    assert estado.sin_datos_tarjeta_s == pytest.approx(3.0)
    assert ciclo.exposicion_en_pausa is False


def test_desconexion_y_ventana_tras_reconectar_son_un_solo_tramo(reloj):
    flags = {}
    ciclo, estado, _ = _ciclo(flags)
    estado.sin_datos_tarjeta_s = 0.0
    fase = _en_esterilizacion(ciclo)

    ciclo.marcar_sin_datos_tarjeta()                   # desconexión
    reloj[0] += 2.0
    ciclo.marcar_sin_datos_tarjeta()                   # reconectó; primera DI pendiente
    reloj[0] += 1.0
    flags["PARO_EMERGENCIA"] = True                    # primera DI: paro sin dato (TMG-04 de U4)
    assert ciclo.run() == CicloResultado.EN_CURSO
    reloj[0] += 0.5
    flags["PARO_EMERGENCIA"] = False
    ciclo.run()

    fase.pausar_exposicion.assert_called_once()
    assert fase.pausar_exposicion.call_args.args[0] == pytest.approx(3.5)
    assert estado.sin_datos_tarjeta_s == pytest.approx(3.5)


def test_la_desconexion_no_cuenta_como_tolerancia_de_di(reloj):
    """R1-P5 no cambia aquí: /cycle/abort en la desconexión total es D8-2.13."""
    ciclo, _, _ = _ciclo({})
    _en_esterilizacion(ciclo)
    ciclo.marcar_sin_datos_tarjeta()
    assert ciclo.exposicion_en_pausa is True
    assert ciclo.tolerancia_di_activa is False


def test_con_resultado_pendiente_no_marca_nada(reloj):
    ciclo, estado, _ = _ciclo({})
    estado.sin_datos_tarjeta_s = 0.0
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo.marcar_sin_datos_tarjeta()
    assert ciclo.exposicion_en_pausa is False


def test_aborto_por_desconexion_cierra_el_tramo_en_el_ticket(reloj):
    ciclo, estado, _ = _ciclo({})
    estado.sin_datos_tarjeta_s = 0.0
    _en_esterilizacion(ciclo)
    ciclo.marcar_sin_datos_tarjeta()
    reloj[0] += 5.0
    ciclo.abortar_por_desconexion(5.0)
    assert estado.sin_datos_tarjeta_s == pytest.approx(5.0)
    assert ciclo.exposicion_en_pausa is False


def test_reset_limpia_la_marca(reloj):
    ciclo, _, _ = _ciclo({})
    ciclo.marcar_sin_datos_tarjeta()
    ciclo.reset()
    assert ciclo.exposicion_en_pausa is False


# ── ControlLoop: quién marca el tramo ──────────────────────────────────────

def _loop_en_ciclo():
    loop, sm, estado = _make_control_loop()
    estado.set_machine_state(GlobalState.CICLO)
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.tomar_eventos.return_value = []
    return loop, sm, estado


def test_tick_sin_conexion_en_ciclo_marca_el_tramo():
    loop, sm, _ = _loop_en_ciclo()
    loop.link.is_connected.return_value = False
    loop._tick()
    sm.ciclo.marcar_sin_datos_tarjeta.assert_called_once_with()
    sm.update.assert_not_called()


def test_tick_esperando_la_primera_di_en_ciclo_marca_el_tramo():
    loop, sm, _ = _loop_en_ciclo()
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = None
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic",
               return_value=500.0):
        loop._tick()
    sm.ciclo.marcar_sin_datos_tarjeta.assert_called_once_with()
    sm.update.assert_not_called()


def test_tick_sin_conexion_fuera_de_ciclo_no_marca():
    loop, sm, estado = _make_control_loop()
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.tomar_eventos.return_value = []
    loop.link.is_connected.return_value = False
    loop._tick()
    sm.ciclo.marcar_sin_datos_tarjeta.assert_not_called()


# ── F0 ─────────────────────────────────────────────────────────────────────

def test_f0_no_acumula_con_la_exposicion_en_pausa():
    from tests.test_control_loop_f0 import _make_loop
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    loop.state_machine.ciclo.tolerancia_di_activa = False
    loop.state_machine.ciclo.exposicion_en_pausa = True
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1000.5)
    assert estado.f0_acumulado == 0.0
    assert loop._f0_ultimo_tick is None
    loop.state_machine.ciclo.exposicion_en_pausa = False
    loop._acumular_f0(now=1001.0)                       # primer tick tras la pausa: solo el sello
    assert estado.f0_acumulado == 0.0
    loop._acumular_f0(now=1001.5)
    assert estado.f0_acumulado > 0.0
