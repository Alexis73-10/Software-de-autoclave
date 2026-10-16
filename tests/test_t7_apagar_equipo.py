"""T7 (E5, tanda 2026-10-14): "Apagar equipo" (fin de ciclo §16, D-20)."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cargar_servidor

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


@pytest.fixture
def entorno(monkeypatch):
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.sensores_pres = {"pres_camara": 101.3}
    ctx.estado.sensores_temp = {"temp_camara": 40.0}
    ctx.config_manager = _Config(_CFG)
    ctx.profile = None
    ctx.programas_para_seguridad.return_value = []
    ctx.temp_max_tras_ciclo.return_value = None
    ctx.control_loop.datos_vigentes = True
    ctx.control_loop.estado_seguro.activo = False
    ctx.control_loop.apagando = False
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    srv, _ = cargar_servidor(ctx)
    apagados = []
    monkeypatch.setattr(srv, "_apagar_windows", lambda: apagados.append(True))
    monkeypatch.setattr(srv, "_apagado_windows_habilitado", lambda: True)
    hilos = []
    monkeypatch.setattr(srv.threading, "Thread",
                        lambda target, **k: SimpleNamespace(start=lambda: hilos.append(target)))
    return TestClient(srv.app), ctx, srv, apagados, hilos


def _apagar(client, ventana="principal"):
    return client.post("/system/shutdown", json={"ventana": ventana})


def test_apaga_con_camara_segura(entorno):
    client, ctx, srv, apagados, hilos = entorno
    r = _apagar(client)
    assert r.status_code == 200
    [secuencia] = hilos
    secuencia()
    ctx.control_loop.stop.assert_called_once()
    ctx.db.close.assert_called_once()
    assert apagados == [True]


def test_solo_ventana_principal(entorno):
    client, ctx, _, apagados, hilos = entorno
    r = _apagar(client, ventana="secundaria")
    assert r.status_code == 403 and hilos == []


def test_rechaza_en_ciclo(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert _apagar(client).status_code == 409 and hilos == []


def test_rechaza_con_camara_no_segura(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.estado.sensores_temp["temp_camara"] = 95.0
    r = _apagar(client)
    assert r.status_code == 409 and r.json()["codigo"] == "camara_no_segura"
    assert hilos == []


def test_rechaza_con_estado_seguro_activo(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.estado_seguro.activo = True
    assert _apagar(client).json()["codigo"] == "estado_seguro_activo"


def test_rechaza_con_datos_no_vigentes(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.datos_vigentes = False
    assert _apagar(client).status_code == 409


def test_sin_ejecutable_no_apaga_windows(monkeypatch):
    import autoclave.backend.server as srv_mod
    monkeypatch.delenv("AUTOCLAVE_APAGADO_REAL", raising=False)
    monkeypatch.setattr(srv_mod.sys, "frozen", False, raising=False)
    assert srv_mod._apagado_windows_habilitado() is False


# ── Correcciones de los revisores de T7 ────────────────────────────────────

def test_inicia_el_apagado_dentro_del_guard(entorno):
    """TMG-01 / SAF-01: el lazo se detiene en el mismo bloque que validó."""
    client, ctx, _, _, hilos = entorno
    bloqueado = []
    lock = threading.Lock()
    ctx.control_loop.bloqueo_maquina.return_value = lock
    ctx.control_loop.iniciar_apagado.side_effect = lambda: bloqueado.append(lock.locked())
    assert _apagar(client).status_code == 200
    assert bloqueado == [True]


def test_rechaza_un_segundo_apagado(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.apagando = True
    r = _apagar(client)
    assert r.json()["codigo"] == "apagado_en_curso" and hilos == []
    ctx.control_loop.iniciar_apagado.assert_not_called()


def test_rechaza_con_modo_prueba(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.test_mode_active = True
    assert _apagar(client).json()["codigo"] == "modo_prueba_activo"
    ctx.control_loop.iniciar_apagado.assert_not_called()


def test_no_inicia_ciclo_si_se_apaga(entorno):
    client, ctx, _, _, _ = entorno
    ctx.control_loop.apagando = True
    ctx.control_loop.bloqueo_configuracion = None
    ctx.sin_base_de_datos = False
    r = client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == "apagado_en_curso"


def test_control_loop_iniciar_apagado_descarta_start_ciclo():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl._running = threading.Event()
    cl._running.set()
    cl._apagando = False
    cl.estado = MagicMock()
    cl.iniciar_apagado()
    assert cl.apagando is True and not cl._running.is_set()
    cl.estado.set_flag.assert_called_once_with("START_CICLO", False)


class _Respuesta:
    def __init__(self, cuerpo):
        self._c = cuerpo

    def json(self):
        return self._c


def _ui_con_error(error):
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.post.side_effect = error
    return ui


def test_motivo_del_rechazo_sale_de_detail():
    """SAF-02: RechazoApi responde {"detail", "codigo"}."""
    e = Exception("409")
    e.response = _Respuesta({"detail": "Temperatura demasiado alta (95 °C)",
                             "codigo": "camara_no_segura"})
    assert _ui_con_error(e).apagar_equipo("principal") == (
        False, "Temperatura demasiado alta (95 °C)")


def test_sin_respuesta_no_es_un_rechazo():
    """TMG-02: un timeout no se presenta como rechazo."""
    from autoclave.ui.service_ui.ui_service_backend import APAGADO_INCIERTO
    ok, motivo = _ui_con_error(TimeoutError("timeout")).apagar_equipo("principal")
    assert ok is False and motivo == APAGADO_INCIERTO
