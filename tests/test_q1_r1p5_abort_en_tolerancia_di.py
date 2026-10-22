"""Q1 / R1-P5 (tanda 7, decisión 1.3 de Cristian): durante la tolerancia por
DI vencida, /cycle/abort ACEPTA la cancelación. La marca se procesa al volver
los datos (CANCELADO) o al vencer la tolerancia (FALLO_CONEXION, y P-7 limpia
la marca), y la respuesta lo dice."""

import time
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_backend_autenticacion import db, entorno  # noqa: F401  (fixtures)
from tests.test_t2_p3_di_vencida import _ciclo


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


# ── CicloState ─────────────────────────────────────────────────────────────

def test_tolerancia_di_activa_solo_dentro_de_la_tolerancia(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, _, _ = _ciclo(flags)
    assert ciclo.tolerancia_di_activa is False
    ciclo.run()
    assert ciclo.tolerancia_di_activa is True
    flags["PARO_EMERGENCIA"] = False
    ciclo.run()
    assert ciclo.tolerancia_di_activa is False


def test_tolerancia_vencida_ya_no_esta_activa(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, _, _ = _ciclo(flags)
    ciclo.run()
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG
    ciclo.run()
    assert ciclo.tolerancia_di_activa is False


def test_marca_aceptada_se_procesa_al_volver_los_datos(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    ciclo.run()
    flags["CICLO_CANCELADO"] = True                 # lo que pone /cycle/abort
    reloj[0] += 1.0
    assert ciclo.run() == CicloResultado.EN_CURSO   # sigue en tolerancia
    ciclo._protocolo.ejecutar.assert_not_called()
    flags["PARO_EMERGENCIA"] = False
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "CANCELADO"
    ciclo._protocolo.ejecutar.assert_called_once_with()
    assert flags["CICLO_CANCELADO"] is False


def test_marca_aceptada_al_vencer_la_tolerancia_queda_fallo_de_conexion(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    ciclo.run()
    flags["CICLO_CANCELADO"] = True
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_CONEXION"
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)
    ciclo.run()                                     # P-7: la marca no queda puesta
    assert flags["CICLO_CANCELADO"] is False


# ── /cycle/abort ───────────────────────────────────────────────────────────

def _en_ciclo(ctx, flags, tolerancia):
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    ctx.estado.get_flag.side_effect = lambda f: flags.get(f, False)
    ctx.control_loop.state_machine.ciclo.tolerancia_di_activa = tolerancia


def _cancelado_puesto(ctx):
    return ("CICLO_CANCELADO", True) in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_abort_en_tolerancia_di_se_acepta_y_lo_dice(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, tolerancia=True)
    r = client.post("/cycle/abort")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["ok"] is True and datos["action"] == "CICLO_CANCELADO"
    assert datos["pendiente"] is True
    assert datos["codigo"] == "cancelacion_en_espera_datos"
    assert "tarjeta" in datos["mensaje"]
    assert _cancelado_puesto(ctx)


def test_abort_sin_datos_fuera_de_la_tolerancia_sigue_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, tolerancia=False)
    r = client.post("/cycle/abort")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not _cancelado_puesto(ctx)


def test_abort_con_paro_real_sigue_409_aunque_haya_tolerancia(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True, "PARO_REAL": True}, tolerancia=True)
    r = client.post("/cycle/abort")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not _cancelado_puesto(ctx)


def test_abort_en_tolerancia_con_resultado_pendiente_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {"PARO_EMERGENCIA": True}, tolerancia=True)
    ctx.estado.fase_ciclo = "FALLO_CONEXION"
    r = client.post("/cycle/abort")
    assert r.status_code == 409
    assert not _cancelado_puesto(ctx)


def test_abort_normal_no_cambia_la_respuesta(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, {}, tolerancia=False)
    r = client.post("/cycle/abort")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "action": "CICLO_CANCELADO"}


def test_texto_en_ingles_existe():
    from autoclave import i18n
    assert i18n.existe("ciclo.cancelacion_en_espera_datos", "en")
    assert i18n.existe("ciclo.cancelacion_en_espera_datos", "es")
