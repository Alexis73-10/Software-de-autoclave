"""S2b / D8-2.13 (tanda 8, Q1-P4): con la tarjeta totalmente desconectada
(antes de COM-02, dentro de los 5 s del ControlLoop), /cycle/abort también se
acepta como "cancelación en espera", igual que en R1-P5. Al volver los datos
el ciclo queda CANCELADO; si vence la tolerancia, FALLO_CONEXION y P-7 limpia
la marca."""

import time
from unittest.mock import MagicMock, patch

import pytest

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_backend_autenticacion import db, entorno  # noqa: F401  (fixtures)
from tests.test_control_loop_test_mode import _make_control_loop


# ── ControlLoop.desconexion_en_tolerancia ──────────────────────────────────

@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def test_desconexion_en_tolerancia_solo_antes_de_com02(reloj):
    loop, _, _ = _make_control_loop()
    assert loop.desconexion_en_tolerancia is False
    loop._desconectado_desde = 1000.0
    reloj[0] = 1000.0 + loop._TOLERANCIA_DESCONEXION_SEG - 0.1
    assert loop.desconexion_en_tolerancia is True
    reloj[0] = 1000.0 + loop._TOLERANCIA_DESCONEXION_SEG
    assert loop.desconexion_en_tolerancia is False


# ── /cycle/abort ───────────────────────────────────────────────────────────

def _en_ciclo(ctx, flags, desconexion, tolerancia_di=False, fase="ESTERILIZACION"):
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = fase
    ctx.estado.get_flag.side_effect = lambda f: flags.get(f, False)
    ctx.control_loop.state_machine.ciclo.tolerancia_di_activa = tolerancia_di
    ctx.control_loop.desconexion_en_tolerancia = desconexion


def _cancelado_puesto(ctx):
    return ("CICLO_CANCELADO", True) in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_abort_con_la_tarjeta_desconectada_se_acepta_en_espera(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, desconexion=True)
    r = client.post("/cycle/abort")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["pendiente"] is True
    assert datos["codigo"] == "cancelacion_en_espera_datos"
    assert datos["mensaje"]
    assert _cancelado_puesto(ctx)


def test_abort_desconectada_tras_com02_sigue_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, desconexion=False)
    r = client.post("/cycle/abort")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not _cancelado_puesto(ctx)


def test_abort_desconectada_con_resultado_pendiente_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, desconexion=True, fase="FALLO_CONEXION")
    r = client.post("/cycle/abort")
    assert r.status_code == 409
    assert not _cancelado_puesto(ctx)


def test_abort_desconectada_con_paro_real_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True, "PARO_REAL": True}, desconexion=True)
    r = client.post("/cycle/abort")
    assert r.status_code == 409
    assert not _cancelado_puesto(ctx)


def test_valor_no_booleano_no_acepta(entorno):  # noqa: F811
    """Falla cerrada: solo `True` cuenta (un doble sin configurar no acepta)."""
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, desconexion=MagicMock())
    assert client.post("/cycle/abort").status_code == 409


# ── Recorrido con el ControlLoop (planta sin tarjeta) ──────────────────────

def _tick(loop, conectado):
    loop.link.is_connected.return_value = conectado
    loop.link.puerto_presente.return_value = conectado
    loop.link.tomar_eventos.return_value = []
    loop.link.expansor_fuera_de_linea.return_value = False
    loop._running.set()

    def _stop(*_a, **_k):
        loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()


def test_desconexion_y_cancelacion_aceptada_procesa_o_aborta(reloj):
    from tests.test_control_loop_test_mode import _FakeEstado
    estado = _FakeEstado()
    estado.set_machine_state(GlobalState.CICLO)
    loop, sm, _ = _make_control_loop(estado)
    _tick(loop, True)
    _tick(loop, False)                         # se cae el enlace
    assert loop.desconexion_en_tolerancia is True
    assert estado.get_flag("PARO_EMERGENCIA") is True
    assert estado.get_flag("PARO_REAL") is False
    reloj[0] += loop._TOLERANCIA_DESCONEXION_SEG
    _tick(loop, False)                         # vence: COM-02
    assert loop.desconexion_en_tolerancia is False
    sm.ciclo.abortar_por_desconexion.assert_called_once()
