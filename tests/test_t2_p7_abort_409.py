"""T2 / P-7 (tanda 6): /cycle/abort responde 409 con motivo cuando no tendría
efecto (resultado ya pendiente o paro de emergencia) y no deja el indicador
CICLO_CANCELADO puesto; si el ciclo termina por otra causa con la
cancelación aún sin procesar, el indicador se limpia."""

from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_backend_autenticacion import db, entorno  # noqa: F401  (fixtures)
from tests.test_t5_estado_seguro import _ciclo


def _en_ciclo(ctx, fase="ESTERILIZACION", flags=None):
    flags = flags or {}
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = fase
    ctx.estado.get_flag.side_effect = lambda f: flags.get(f, False)


def _cancelado_puesto(ctx):
    return ("CICLO_CANCELADO", True) in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_abort_en_curso_sigue_aceptandose(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx)
    r = client.post("/cycle/abort")
    assert r.status_code == 200 and _cancelado_puesto(ctx)


def test_abort_con_resultado_pendiente_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    for fase in ("COMPLETADO", "CANCELADO", "FALLO_CALENTAMIENTO", "SENSOR_AUSENTE"):
        ctx.estado.set_flag.reset_mock()
        _en_ciclo(ctx, fase=fase)
        r = client.post("/cycle/abort")
        assert r.status_code == 409, fase
        assert r.json()["codigo"] == "resultado_pendiente"
        assert not _cancelado_puesto(ctx)


def test_abort_con_paro_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    _en_ciclo(ctx, flags={"PARO_EMERGENCIA": True, "PARO_REAL": True})
    r = client.post("/cycle/abort")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not _cancelado_puesto(ctx)


def test_abort_fuera_de_ciclo_409(entorno):  # noqa: F811
    client, ctx, _ = entorno
    r = client.post("/cycle/abort")
    assert r.status_code == 409
    assert not _cancelado_puesto(ctx)


def test_ciclo_limpia_la_cancelacion_no_procesada_al_quedar_pendiente():
    flags = {"CICLO_CANCELADO": True}
    ciclo, _ = _ciclo(flags)
    ciclo.estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo.run()
    assert flags["CICLO_CANCELADO"] is False
