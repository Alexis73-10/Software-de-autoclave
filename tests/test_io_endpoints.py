# PATCH /io/test/output/{name}: canal físico y apagado/encendido dentro del
# modo prueba (planeacion_backend_autenticacion.md §4.5 y §5.4, y revisión de
# seguridad de la etapa 1: puertas leídas en vivo y encendido solo desde la
# sesión dueña). /io/test/reset_all se eliminó (§4.6).

import pytest
from unittest.mock import MagicMock

from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor

_DI_CERRADA, _DI_ABIERTA = "puerta_cerrada_1", "puerta_abierta_1"


def _puerta(nombre="Puerta 1", con_abierta=True):
    d = MagicMock()
    d.name = nombre
    d.di = {"cerrada": _DI_CERRADA, **({"abierta": _DI_ABIERTA} if con_abierta else {})}
    return d


@pytest.fixture
def entorno():
    """Modo prueba activo con la sesión del técnico como dueña, PREPARADO, sin
    paro, cámara a 101 kPa y puerta cerrada según sus entradas: todas las
    condiciones de R-02 se cumplen."""
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_pres = {"pres_camara": 101.0}
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0}
    ctx.estado.get_door_state.return_value = DoorState.CERRADO
    ctx.config_manager.get.side_effect = {"presion_admosferica": 101.3,
                                          "rango_presion_atm": 5.0}.get
    ctx.doors = [_puerta()]
    ctx.control_loop.test_mode_active = True
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    srv._token_modo_prueba = cab["Authorization"].split()[1]

    from fastapi.testclient import TestClient
    return TestClient(srv.app, headers=cab), ctx, srv


@pytest.fixture
def io_client(entorno):
    client, ctx, _ = entorno
    return client, ctx


def test_reset_all_eliminado(io_client):
    client, _ = io_client
    assert client.post("/io/test/reset_all").status_code in (404, 405)


def test_set_output_activa_vapor_generador(io_client):
    """map_do es 0-indexado (vapor_generador=0) pero serial_link.set_output()
    espera el canal DO físico 1-indexado (DO1)."""
    client, ctx = io_client
    resp = client.patch("/io/test/output/vapor_generador", json={"value": True})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "name": "vapor_generador", "value": True}
    ctx.setdo.set_output.assert_called_once_with(1, True)


def test_set_output_apaga_vapor_caldera(io_client):
    client, ctx = io_client
    resp = client.patch("/io/test/output/vapor_caldera", json={"value": False})
    assert resp.status_code == 200
    ctx.setdo.set_output.assert_called_once_with(2, False)


def test_set_output_404_para_nombre_invalido(io_client):
    client, _ = io_client
    resp = client.patch("/io/test/output/no_existe", json={"value": True})
    assert resp.status_code == 404


def test_set_output_queda_en_audit_log(io_client):
    client, ctx = io_client
    client.patch("/io/test/output/vapor_camara", json={"value": True})
    args, kwargs = ctx.db.registrar_auditoria.call_args
    assert args[0] == "salida_prueba"
    assert kwargs["entidad"] == "vapor_camara"
    assert kwargs["valor_nuevo"] is True
    assert kwargs["usuario"] == "tec1"


# ── Criterio 3: rechazos ────────────────────────────────────────────────────

def _rechazo(client, ctx, value=True, headers=None):
    resp = client.patch("/io/test/output/vapor_camara", json={"value": value},
                        **({"headers": headers} if headers else {}))
    assert resp.status_code == 409, resp.text
    ctx.setdo.set_output.assert_not_called()
    return resp.json()["detail"]


def test_fuera_de_modo_prueba_409(io_client):
    client, ctx = io_client
    ctx.control_loop.test_mode_active = False
    assert "modo prueba" in _rechazo(client, ctx, value=False)


@pytest.mark.parametrize("estado", [GlobalState.CICLO, GlobalState.HIBERNACION,
                                    GlobalState.EMERGENCIA])
def test_estados_bloqueados_409_incluso_para_apagar(io_client, estado):
    client, ctx = io_client
    ctx.estado.get_machine_state.return_value = estado
    _rechazo(client, ctx, value=False)


def test_con_paro_de_emergencia_409(io_client):
    client, ctx = io_client
    ctx.estado.get_flag.side_effect = lambda f: f in ("PARO_EMERGENCIA", "PARO_REAL")  # U4: paro real
    assert "Paro" in _rechazo(client, ctx, value=False)


def test_encender_con_presion_en_camara_409(io_client):
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": 180.0}
    assert "presión atmosférica" in _rechazo(client, ctx)


def test_encender_con_vacio_en_camara_409(io_client):
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": 20.0}
    _rechazo(client, ctx)


def test_encender_sin_lectura_de_presion_409(io_client):
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": None}
    assert "Sin lectura" in _rechazo(client, ctx)


def test_encender_sin_configuracion_atmosferica_409(io_client):
    client, ctx = io_client
    ctx.config_manager.get.side_effect = lambda *_a, **_k: None
    _rechazo(client, ctx)


# ── Hallazgo A: puertas leídas en vivo, no del estado lógico congelado ──────

def test_puerta_abierta_durante_la_prueba_bloquea_aunque_el_estado_diga_cerrado(io_client):
    """Escenario del hallazgo A: en modo prueba door.update() está en pausa y
    el estado lógico sigue en CERRADO, pero la entrada dice que se abrió."""
    client, ctx = io_client
    ctx.estado.get_door_state.return_value = DoorState.CERRADO   # congelado
    ctx.estado.sensores_di = {_DI_CERRADA: 0, _DI_ABIERTA: 1}
    assert "Puerta 1 no está cerrada" in _rechazo(client, ctx)


@pytest.mark.parametrize("entradas,motivo", [
    ({_DI_CERRADA: 0, _DI_ABIERTA: 0}, "no está cerrada"),     # entre medias
    ({_DI_CERRADA: 1, _DI_ABIERTA: 1}, "no está cerrada"),     # incoherente
    ({_DI_CERRADA: None, _DI_ABIERTA: 0}, "Sin lectura"),
    ({_DI_CERRADA: 1, _DI_ABIERTA: None}, "Sin lectura"),
    ({_DI_ABIERTA: 0}, "Sin lectura"),                         # entrada ausente
    ({_DI_CERRADA: 2, _DI_ABIERTA: 0}, "Sin lectura"),         # valor inválido
])
def test_encender_exige_cerrada_1_y_abierta_0(io_client, entradas, motivo):
    client, ctx = io_client
    ctx.estado.sensores_di = entradas
    assert motivo in _rechazo(client, ctx)


def test_estado_logico_abierto_no_bloquea_si_las_entradas_dicen_cerrada(io_client):
    """Una puerta cerrada a mano durante la prueba (estado lógico congelado en
    ABIERTO) se reconoce por sus entradas."""
    client, ctx = io_client
    ctx.estado.get_door_state.return_value = DoorState.ABIERTO
    assert client.patch("/io/test/output/vapor_camara", json={"value": True}).status_code == 200


def test_puerta_sin_sensor_de_abierta_usa_solo_cerrada(io_client):
    client, ctx = io_client
    ctx.doors = [_puerta(con_abierta=False)]
    ctx.estado.sensores_di = {_DI_CERRADA: 1}
    assert client.patch("/io/test/output/vapor_camara", json={"value": True}).status_code == 200
    ctx.setdo.set_output.reset_mock()
    ctx.estado.sensores_di = {_DI_CERRADA: 0}
    _rechazo(client, ctx)


def test_segunda_puerta_abierta_bloquea(io_client):
    client, ctx = io_client
    p2 = _puerta("Puerta 2")
    p2.di = {"cerrada": "puerta_cerrada_2", "abierta": "puerta_abierta_2"}
    ctx.doors = [_puerta(), p2]
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0,
                              "puerta_cerrada_2": 0, "puerta_abierta_2": 1}
    assert "Puerta 2" in _rechazo(client, ctx)


def test_encender_sin_puertas_conocidas_409(io_client):
    client, ctx = io_client
    ctx.doors = []
    assert "puertas" in _rechazo(client, ctx)


def test_puerta_sin_mapa_de_entradas_409(io_client):
    client, ctx = io_client
    rara = MagicMock()
    rara.name = "Puerta 1"
    rara.di = None
    ctx.doors = [rara]
    assert "Sin lectura" in _rechazo(client, ctx)


def test_apagar_siempre_permitido_en_modo_prueba(io_client):
    """Apagar es la acción segura: no exige R-02 (presión y puerta abierta)."""
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": None}
    ctx.estado.sensores_di = {_DI_CERRADA: 0, _DI_ABIERTA: 1}
    resp = client.patch("/io/test/output/vapor_camara", json={"value": False})
    assert resp.status_code == 200
    ctx.setdo.set_output.assert_called_once_with(4, False)


# ── Extra: encender solo desde la sesión dueña ─────────────────────────────

def test_otra_sesion_no_puede_encender_pero_si_apagar(entorno):
    client, ctx, srv = entorno
    otra = cabecera(srv, "ingeniero", "ing1")
    assert "sesión que activó" in _rechazo(client, ctx, headers=otra)
    resp = client.patch("/io/test/output/vapor_camara", json={"value": False}, headers=otra)
    assert resp.status_code == 200
    ctx.setdo.set_output.assert_called_once_with(4, False)


def test_sin_dueno_nadie_enciende(entorno):
    client, ctx, srv = entorno
    srv._token_modo_prueba = None
    _rechazo(client, ctx)


# ── Hallazgo D: el rechazo se registra con el lock libre ────────────────────

def test_rechazo_409_queda_en_audit_log_fuera_del_lock(entorno):
    import threading
    client, ctx, _ = entorno
    lock = threading.RLock()
    ctx.control_loop.bloqueo_maquina.return_value = lock
    lock_tomado = []
    ctx.db.registrar_auditoria.side_effect = lambda *a, **k: lock_tomado.append(lock._is_owned())
    ctx.estado.sensores_pres = {"pres_camara": 180.0}

    client.patch("/io/test/output/vapor_camara", json={"value": True})

    args, kwargs = ctx.db.registrar_auditoria.call_args
    assert args[0] == "rechazo_409"
    assert kwargs["entidad"] == "/io/test/output/vapor_camara"
    assert "presión" in kwargs["detalle"]["motivo"]
    assert lock_tomado == [False]


def test_salida_se_acciona_con_el_lock_tomado(entorno):
    import threading
    client, ctx, _ = entorno
    lock = threading.RLock()
    ctx.control_loop.bloqueo_maquina.return_value = lock
    tomado = []
    ctx.setdo.set_output.side_effect = lambda *a: tomado.append(lock._is_owned())
    client.patch("/io/test/output/vapor_camara", json={"value": True})
    assert tomado == [True]


# ── Criterio 1: token y rol ─────────────────────────────────────────────────

def test_sin_token_401(io_client):
    client, ctx = io_client
    resp = client.patch("/io/test/output/vapor_camara", json={"value": True},
                        headers={"Authorization": ""})
    assert resp.status_code == 401
    ctx.setdo.set_output.assert_not_called()


def test_admin_403():
    ctx = MagicMock()
    srv, _ = cargar_servidor(ctx)
    from fastapi.testclient import TestClient
    client = TestClient(srv.app, headers=cabecera(srv, "admin"))
    resp = client.patch("/io/test/output/vapor_camara", json={"value": False})
    assert resp.status_code == 403
    ctx.setdo.set_output.assert_not_called()
