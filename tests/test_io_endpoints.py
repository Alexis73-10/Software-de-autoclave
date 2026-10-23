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


@pytest.mark.parametrize("estado", [GlobalState.CICLO])   # P-8 (tanda 6)
def test_estados_bloqueados_409_incluso_para_apagar(io_client, estado):
    client, ctx = io_client
    ctx.estado.get_machine_state.return_value = estado
    _rechazo(client, ctx, value=False)


def test_con_paro_de_emergencia_409(io_client):
    client, ctx = io_client
    ctx.estado.get_flag.side_effect = lambda f: f in ("PARO_EMERGENCIA", "PARO_REAL")  # U4: paro real
    assert "Paro" in _rechazo(client, ctx, value=False)


# D-ES-15: en modo prueba se permiten todas las salidas; R-02 ya no se aplica.

def test_encender_con_camara_presurizada_y_puerta_abierta_se_acepta(io_client):
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": 180.0}
    ctx.estado.sensores_di = {_DI_CERRADA: 0, _DI_ABIERTA: 1}
    resp = client.patch("/io/test/output/vapor_camara", json={"value": True})
    assert resp.status_code == 200, resp.text
    ctx.setdo.set_output.assert_called_once()


def test_encender_sin_lecturas_ni_configuracion_se_acepta(io_client):
    client, ctx = io_client
    ctx.estado.sensores_pres = {"pres_camara": None}
    ctx.estado.sensores_di = {}
    ctx.doors = []
    ctx.config_manager.get.side_effect = lambda *_a, **_k: None
    assert client.patch("/io/test/output/vapor_camara", json={"value": True}).status_code == 200


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

def test_rechazo_409_queda_en_el_log_fuera_del_lock(entorno):
    # D9-6 (tanda 9): el rechazo ya no va a audit_log, solo al log de desarrollo
    import sys
    import threading
    from unittest.mock import patch
    client, ctx, _ = entorno
    lock = threading.RLock()
    ctx.control_loop.bloqueo_maquina.return_value = lock
    lock_tomado = []
    ctx.estado.get_flag.side_effect = lambda f: f in ("PARO_EMERGENCIA", "PARO_REAL")
    srv = sys.modules["autoclave.backend.server"]
    with patch.object(srv, "_log_desarrollo",
                      side_effect=lambda *a, **k: lock_tomado.append(lock._is_owned())) as log:
        client.patch("/io/test/output/vapor_camara", json={"value": True})

    ctx.db.registrar_auditoria.assert_not_called()
    args, kwargs = log.call_args
    assert args[0] == "rechazo_409"
    assert kwargs["entidad"] == "/io/test/output/vapor_camara"
    assert "aro" in kwargs["motivo"]
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


# ── D-ES-16 / §6.7: seguro de atrapamiento en modo prueba ───────────────────

_DI_ATRAP = "atrapamiento_puerta_1"


def _puerta_avanzada():
    d = _puerta()
    d.di = {**d.di, "atrapamiento": _DI_ATRAP}
    from autoclave.core.runtime.status import EstadoAutoclave as E
    d.do = {"abrir": E.map_do["abrir_puerta_1"] + 1,
            "cerrar": E.map_do["cerrar_puerta_1"] + 1}
    return d


def _canal(nombre):
    from autoclave.core.runtime.status import EstadoAutoclave as E
    return E.map_do[nombre] + 1


def _llamadas(ctx):
    return [(c.args[0], c.args[1]) for c in ctx.setdo.set_output.call_args_list]


@pytest.fixture
def atrapada(entorno):
    client, ctx, srv = entorno
    ctx.doors = [_puerta_avanzada()]
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0, _DI_ATRAP: 0}  # NC: 0 = atrapada
    return client, ctx, srv


def test_cerrar_con_atrapamiento_activo_abre_en_su_lugar(atrapada):
    client, ctx, _ = atrapada
    resp = client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert resp.status_code == 200, resp.text
    llamadas = _llamadas(ctx)
    assert (_canal("cerrar_puerta_1"), True) not in llamadas
    assert (_canal("cerrar_puerta_1"), False) in llamadas
    assert (_canal("abrir_puerta_1"), True) in llamadas


def test_cerrar_con_atrapamiento_normal_pasa_sin_cambio(atrapada):
    client, ctx, _ = atrapada
    ctx.estado.sensores_di[_DI_ATRAP] = 1
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert _llamadas(ctx) == [(_canal("cerrar_puerta_1"), True)]


def test_puerta_sin_sensor_de_atrapamiento_pasa_sin_cambio(entorno):
    client, ctx, _ = entorno
    ctx.doors = [_puerta()]
    ctx.doors[0].do = {"abrir": _canal("abrir_puerta_1"), "cerrar": _canal("cerrar_puerta_1")}
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert _llamadas(ctx) == [(_canal("cerrar_puerta_1"), True)]


def test_inversion_se_audita_una_sola_vez_por_pulsacion(atrapada):
    client, ctx, _ = atrapada
    for _ in range(3):
        client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list]
    assert eventos.count("atrapamiento_orden_invertida") == 1
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": False})
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list]
    assert eventos.count("atrapamiento_orden_invertida") == 2


def test_liberada_la_senal_el_cierre_no_se_reanuda_hasta_soltar(atrapada):
    client, ctx, _ = atrapada
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    ctx.estado.sensores_di[_DI_ATRAP] = 1          # se libera con el dedo pulsado
    ctx.setdo.set_output.reset_mock()
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert (_canal("cerrar_puerta_1"), True) not in _llamadas(ctx)
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": False})   # suelta
    ctx.setdo.set_output.reset_mock()
    client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})    # vuelve a pulsar
    assert _llamadas(ctx) == [(_canal("cerrar_puerta_1"), True)]
