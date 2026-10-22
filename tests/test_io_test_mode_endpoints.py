# Entrada y salida del modo prueba (planeacion_backend_autenticacion.md §4.5
# y §5.4): token de técnico o ingeniero, estados bloqueados y salida solo
# desde la sesión que entró.

import pytest
from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor


@pytest.fixture
def io_client():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)

    from fastapi.testclient import TestClient
    return TestClient(srv.app), ctx, srv


def _entrar(client, ctx, cab):
    resp = client.post("/io/test/enter", headers=cab)
    if resp.status_code == 200:
        ctx.control_loop.test_mode_active = True
    return resp


def test_enter_test_mode_ok(io_client):
    client, ctx, srv = io_client
    resp = _entrar(client, ctx, cabecera(srv, "tecnico"))

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    ctx.control_loop.enter_test_mode.assert_called_once()
    assert ctx.db.registrar_auditoria.call_args.args[0] == "modo_prueba_entra"


def test_enter_test_mode_rechazado_devuelve_409_con_motivo(io_client):
    client, ctx, srv = io_client
    ctx.control_loop.enter_test_mode.return_value = (
        False, "No se puede activar el modo prueba con el paro de emergencia activado."
    )

    resp = client.post("/io/test/enter", headers=cabecera(srv, "tecnico"))

    assert resp.status_code == 409
    assert "paro de emergencia" in resp.json()["detail"]


@pytest.mark.parametrize("estado", [GlobalState.CICLO])   # P-8 (tanda 6)
def test_enter_bloqueado_en_ciclo_hibernacion_y_emergencia(io_client, estado):
    client, ctx, srv = io_client
    ctx.estado.get_machine_state.return_value = estado

    resp = client.post("/io/test/enter", headers=cabecera(srv, "ingeniero"))

    assert resp.status_code == 409
    ctx.control_loop.enter_test_mode.assert_not_called()


@pytest.mark.parametrize("estado", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                    GlobalState.FALLA])
def test_enter_permitido_fuera_de_ciclo(io_client, estado):
    client, ctx, srv = io_client
    ctx.estado.get_machine_state.return_value = estado
    assert client.post("/io/test/enter", headers=cabecera(srv, "tecnico")).status_code == 200


def test_enter_sin_token_401_y_admin_403(io_client):
    client, ctx, srv = io_client
    assert client.post("/io/test/enter").status_code == 401
    assert client.post("/io/test/enter", headers=cabecera(srv, "admin")).status_code == 403
    ctx.control_loop.enter_test_mode.assert_not_called()


def test_exit_test_mode_ok(io_client):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)

    resp = client.post("/io/test/exit", headers=cab)

    assert resp.status_code == 200
    assert resp.json()["ok"] is True   # + all_off_confirmado (R1-P1)
    ctx.control_loop.exit_test_mode.assert_called_once()


def test_exit_fuera_de_modo_prueba_409(io_client):
    client, ctx, srv = io_client
    resp = client.post("/io/test/exit", headers=cabecera(srv, "tecnico"))
    assert resp.status_code == 409
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_exit_desde_otra_sesion_409(io_client):
    client, ctx, srv = io_client
    _entrar(client, ctx, cabecera(srv, "tecnico", "tec1"))

    resp = client.post("/io/test/exit", headers=cabecera(srv, "ingeniero", "ing1"))

    assert resp.status_code == 409
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_enter_desde_otra_sesion_con_modo_prueba_activo_409(io_client):
    """Otra sesión no puede quitarle el modo prueba a la que entró."""
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico", "tec1")
    _entrar(client, ctx, cab)

    assert client.post("/io/test/enter", headers=cabecera(srv, "ingeniero", "ing1")).status_code == 409
    assert client.post("/io/test/exit", headers=cab).status_code == 200


def test_logout_de_la_sesion_que_entro_sale_del_modo_prueba(io_client):
    """Decisión 30: al invalidar el token que entró, el backend sale del modo
    prueba y apaga las salidas (exit_test_mode apaga todo)."""
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)

    assert client.post("/auth/logout", headers=cab).status_code == 200

    ctx.control_loop.exit_test_mode.assert_called_once()
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list]
    assert "modo_prueba_sale" in eventos


def test_logout_de_otra_sesion_no_sale_del_modo_prueba(io_client):
    client, ctx, srv = io_client
    _entrar(client, ctx, cabecera(srv, "tecnico", "tec1"))

    assert client.post("/auth/logout", headers=cabecera(srv, "ingeniero", "ing1")).status_code == 200

    ctx.control_loop.exit_test_mode.assert_not_called()


def test_status_incluye_test_mode_active(io_client):
    client, ctx, _ = io_client
    ctx.control_loop.test_mode_active = True
    ctx.alarm_manager.activas.return_value = []
    ctx.alarm_manager.eventos_recientes.return_value = []
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["test_mode_active"] is True


def _status_vacio(ctx):
    ctx.alarm_manager.activas.return_value = []
    ctx.alarm_manager.eventos_recientes.return_value = []
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}


def test_status_expone_cuentas_adc_por_sensor(io_client):
    """B-ES-1: raw_ai[0..7] temperatura, raw_ai[8..15] presión."""
    client, ctx, _ = io_client
    _status_vacio(ctx)
    raw = list(range(100, 116))
    ctx.units.get_all.return_value = {"raw_ai": raw}

    adc = client.get("/status").json()["sensors"]["adc"]

    assert adc["temp_camara"] == 100
    assert adc["temp_ref"] == 102
    assert adc["temp_drenaje"] == 104
    assert adc["pres_camara"] == 108
    assert adc["pres_empaque_2"] == 111


def test_status_adc_sin_datos_es_none_y_no_rompe(io_client):
    client, ctx, _ = io_client
    _status_vacio(ctx)
    ctx.units.get_all.side_effect = RuntimeError("sin units")

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["sensors"]["adc"]["temp_camara"] is None


def test_io_channels_lista_los_canales_del_equipo(io_client):
    client, _, srv = io_client
    from tests.backend_doble import cabecera
    resp = client.get("/io/channels", headers=cabecera(srv, "tecnico"))

    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos["DI"]) == 13 and len(datos["DO"]) == 18
    assert len(datos["temperature"]) == 3 and len(datos["pressure"]) == 4
    assert datos["DO"][0]["name"] == "vapor_generador"
    assert any(c["momentanea"] for c in datos["DO"])


def test_io_channels_admin_403(io_client):
    client, _, srv = io_client
    from tests.backend_doble import cabecera
    assert client.get("/io/channels", headers=cabecera(srv, "admin")).status_code == 403


@pytest.mark.parametrize("causa", ["abandono de la sección", "inactividad de la interfaz"])
def test_exit_registra_la_causa_enviada_por_la_ui(io_client, causa):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)
    assert client.post("/io/test/exit", headers=cab, json={"motivo": causa}).status_code == 200
    llamada = [c for c in ctx.db.registrar_auditoria.call_args_list
               if c.args[0] == "modo_prueba_sale"][-1]
    assert llamada.kwargs["detalle"]["motivo"] == causa   # + all_off_confirmado (R1-P1)


def test_exit_ignora_causa_desconocida(io_client):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)
    client.post("/io/test/exit", headers=cab, json={"motivo": "<script>"})
    llamada = [c for c in ctx.db.registrar_auditoria.call_args_list
               if c.args[0] == "modo_prueba_sale"][-1]
    assert llamada.kwargs["detalle"]["motivo"] == "salida solicitada"


def test_io_channels_marca_salidas_bloqueadas_por_configuracion(io_client):
    client, ctx, srv = io_client
    from tests.backend_doble import cabecera
    from autoclave.core.runtime.status import EstadoAutoclave as E
    ctx.setdo.salida_bloqueada.side_effect = lambda ch: ch == E.map_do["vapor_generador"] + 1
    do = client.get("/io/channels", headers=cabecera(srv, "tecnico")).json()["DO"]
    bloq = [c["name"] for c in do if c["bloqueada"]]
    assert bloq == ["vapor_generador"]
