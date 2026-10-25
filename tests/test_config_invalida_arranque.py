# Configuración inválida al arrancar (decisión de Cristian del 2026-10-07,
# revisión de la etapa 1 de autenticación): rango_presion_atm debe estar en
# 1–10 kPa. Fuera de rango, o ausente, el backend arranca bloqueado con la
# alarma CONFIGURACION_INVALIDA: sin puertas, máquina de estados, ciclo ni
# modo prueba, y con todas las salidas apagadas.

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.context import BackendContext
from autoclave.core.managers.validacion_config import errores_config_arranque
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import Despeje, Nivel
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor
from tests.test_control_loop_test_mode import _make_control_loop, _run_one_tick


class _Config:
    def __init__(self, **valores):
        # Claves de cámara segura (SAF-03 de T4) con sus valores de fábrica
        self._valores = {"presion_admosferica": 75.0, "temp_max_apertura": 120, **valores}

    def get(self, clave, default=None):
        return self._valores.get(clave, default)


# ── Validación pura ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("rango", [1, 1.0, 5, 7.5, 10, 10.0])
def test_rango_valido(rango):
    assert errores_config_arranque(_Config(rango_presion_atm=rango)) == []


@pytest.mark.parametrize("rango,texto", [
    (0.99, "fuera de rango"), (10.01, "fuera de rango"), (0, "fuera de rango"),
    (-5, "fuera de rango"), (20, "fuera de rango"),
    (None, "Falta"), ("5", "no es numérico"), (True, "no es numérico"),
    (float("nan"), "no es numérico"),
])
def test_rango_invalido(rango, texto):
    errores = errores_config_arranque(_Config(rango_presion_atm=rango))
    assert len(errores) == 1 and texto in errores[0]


@pytest.mark.parametrize("clave,valor,texto", [
    ("presion_admosferica", None, "Falta"), ("temp_max_apertura", None, "Falta"),
    ("presion_admosferica", 30.0, "fuera de rango"), ("temp_max_apertura", 150, "fuera de rango"),
    ("temp_max_apertura", "80", "no es numérico"),
])
def test_claves_de_camara_segura(clave, valor, texto):
    # SAF-03 de T4: sin ellas la cámara nunca es segura y PREPARADO no avanza
    errores = errores_config_arranque(_Config(rango_presion_atm=5, **{clave: valor}))
    assert len(errores) == 1 and clave in errores[0] and texto in errores[0]


def test_configuracion_de_fabrica_es_valida():
    from autoclave.core.managers.config_manager import ConfigManager
    cm = ConfigManager()
    cm.load_config()
    assert errores_config_arranque(cm) == []


# ── Arranque del backend ─────────────────────────────────────────────────────

class _Estado:
    def __init__(self):
        self.Alarmas_activas = []


def _contexto(rango):
    ctx = object.__new__(BackendContext)
    ctx.config_manager = _Config(rango_presion_atm=rango)
    ctx.alarm_manager = AlarmManager(_Estado())
    ctx.control_loop = MagicMock()
    return ctx


def test_arranque_con_rango_invalido_queda_bloqueado_con_alarma():
    ctx = _contexto(25)
    ctx._validar_configuracion()

    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "CONFIGURACION_INVALIDA"
    assert alarma.nivel is Nivel.ALARMA
    assert alarma.definicion.bloquea_inicio is True
    assert alarma.definicion.despeje is Despeje.MANUAL
    assert "rango_presion_atm" in alarma.descripcion
    motivo = ctx.control_loop.bloquear_por_configuracion.call_args.args[0]
    assert "25" in motivo


def test_arranque_con_rango_valido_no_bloquea():
    ctx = _contexto(5)
    ctx._validar_configuracion()
    assert ctx.alarm_manager.activas() == []
    ctx.control_loop.bloquear_por_configuracion.assert_not_called()


# ── ControlLoop bloqueado ───────────────────────────────────────────────────

def test_loop_bloqueado_apaga_y_no_ejecuta_puertas_ni_maquina():
    puerta = MagicMock()
    loop, mock_sm, estado = _make_control_loop(doors=[puerta])
    loop.bloquear_por_configuracion("rango_presion_atm fuera de rango")

    _run_one_tick(loop)
    _run_one_tick(loop)

    loop.set_do.reset_all_outputs.assert_called_once()   # una vez por conexión
    puerta.update.assert_not_called()
    loop.door_service.update.assert_not_called()
    mock_sm.update.assert_not_called()
    loop.set_do.buzer.update.assert_not_called()
    assert loop.units.get_all.call_count == 2            # sensores sí se publican
    assert loop.bloqueo_configuracion == "rango_presion_atm fuera de rango"


def test_loop_bloqueado_vuelve_a_apagar_tras_reconectar():
    loop, _, _ = _make_control_loop()
    loop.bloquear_por_configuracion("x")
    _run_one_tick(loop)
    loop.link_was_connected = False      # la tarjeta se desconectó y volvió
    _run_one_tick(loop)
    assert loop.set_do.reset_all_outputs.call_count == 2


def test_loop_bloqueado_rechaza_modo_prueba():
    loop, _, _ = _make_control_loop()
    loop.bloquear_por_configuracion("rango_presion_atm fuera de rango")
    ok, motivo = loop.enter_test_mode()
    assert ok is False and "Configuración inválida" in motivo
    assert loop.test_mode_active is False


def test_loop_sin_bloqueo_funciona_normal():
    loop, mock_sm, _ = _make_control_loop()
    assert loop.bloqueo_configuracion is None
    _run_one_tick(loop)
    mock_sm.update.assert_called_once()


# ── Endpoints ───────────────────────────────────────────────────────────────

@pytest.fixture
def bloqueado():
    ctx = MagicMock()
    ctx.control_loop.bloqueo_configuracion = "rango_presion_atm fuera de rango: 25 kPa"
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = True          # LISTO_PARA_CICLO
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx, srv


@pytest.mark.parametrize("ruta", ["/cycle/start", "/doors/Puerta 1/open", "/doors/Puerta 1/close"])
def test_operacion_rechazada_con_configuracion_invalida(bloqueado, ruta):
    client, ctx, _ = bloqueado
    r = client.post(ruta, json={})
    assert r.status_code == 409
    assert "Configuración inválida" in r.json()["detail"]
    ctx.estado.set_flag.assert_not_called()
    ctx.servicio_puertas.request_open.assert_not_called()
    ctx.servicio_puertas.request_close.assert_not_called()


def test_modo_prueba_rechazado_con_configuracion_invalida(bloqueado):
    client, ctx, srv = bloqueado
    r = client.post("/io/test/enter", headers=cabecera(srv, "tecnico"))
    assert r.status_code == 409 and "Configuración inválida" in r.json()["detail"]
    ctx.control_loop.enter_test_mode.assert_not_called()


def test_apagar_salidas_sigue_disponible(bloqueado):
    client, ctx, _ = bloqueado
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    assert client.post("/outputs/reset").status_code == 200


def test_sin_bloqueo_el_inicio_de_ciclo_funciona():
    ctx = MagicMock()
    ctx.control_loop.bloqueo_configuracion = None
    ctx.estado.get_flag.return_value = True
    srv, _ = cargar_servidor(ctx)
    assert TestClient(srv.app).post("/cycle/start").status_code == 200
