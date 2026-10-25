"""T7 (E5, tanda 2026-10-14): "Apagar equipo" (fin de ciclo §16, D-20)."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cargar_servidor, modulo_backend

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
    monkeypatch.setattr(modulo_backend("rutas.apagado"), "_apagar_windows", lambda: apagados.append(True))
    monkeypatch.setattr(modulo_backend("rutas.apagado"), "_apagado_windows_habilitado", lambda: True)
    hilos = []
    real = threading.Thread

    def falso(target, **k):
        if k.get("name") == "ApagarEquipo":      # los pasos auxiliares corren de verdad
            return SimpleNamespace(start=lambda: hilos.append(target))
        return real(target=target, **k)

    monkeypatch.setattr(srv.threading, "Thread", falso)
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


def _flags(ctx, **banderas):
    ctx.estado.get_flag.side_effect = lambda k: banderas.get(k, False)


def _detalle_auditoria(ctx):
    llamadas = [c for c in ctx.db.registrar_auditoria.call_args_list
                if c.args and c.args[0] == "apagar_equipo"]
    assert len(llamadas) == 1
    return llamadas[0].kwargs["detalle"]


def test_apaga_con_camara_no_segura_y_lo_registra(entorno):
    """A1: la cámara caliente ya no impide dejar el equipo fuera de servicio."""
    client, ctx, _, apagados, hilos = entorno
    ctx.estado.sensores_temp["temp_camara"] = 95.0
    r = _apagar(client)
    assert r.status_code == 200 and r.json()["camara_segura"] is False
    d = _detalle_auditoria(ctx)
    assert d["camara_segura"] is False and d["motivo"] == "fuera de servicio solicitado"
    assert d["estado"] == "PREPARADO" and d["tarjeta_conectada"] is True
    hilos[0]()
    assert apagados == [True]


@pytest.mark.parametrize("estado", [GlobalState.FALLA, GlobalState.PREPARACION,
                                    GlobalState.PREPARADO])
def test_apaga_en_cualquier_estado_salvo_ciclo(entorno, estado):
    client, ctx, _, apagados, hilos = entorno
    ctx.estado.get_machine_state.return_value = estado
    assert _apagar(client).status_code == 200
    assert _detalle_auditoria(ctx)["estado"] == estado.name
    hilos[0]()
    assert apagados == [True]


def test_apaga_en_falla_con_paro_de_emergencia_y_camara_caliente(entorno):
    client, ctx, _, apagados, hilos = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.estado.sensores_temp["temp_camara"] = 120.0
    _flags(ctx, PARO_EMERGENCIA=True, PARO_REAL=True)
    ctx.control_loop.estado_seguro.activo = True          # pausado por el paro
    assert _apagar(client).status_code == 200
    d = _detalle_auditoria(ctx)
    assert d["paro_emergencia"] is True and d["camara_segura"] is False
    hilos[0]()
    assert apagados == [True]


def test_apaga_sin_tarjeta_y_aunque_falle_todo_lo_demas(entorno):
    """Sin tarjeta, con el ALL_OFF/stop lanzando y la BD fallando: Windows se apaga igual."""
    client, ctx, _, apagados, hilos = entorno
    ctx.control_loop.desconectado = True
    ctx.control_loop.datos_vigentes = False
    ctx.control_loop.stop.side_effect = OSError("puerto roto")
    ctx.historial_alarmas.detener.side_effect = RuntimeError("x")
    ctx.cycle_logger.detener.side_effect = RuntimeError("x")
    ctx.db.close.side_effect = RuntimeError("db")
    assert _apagar(client).status_code == 200
    assert _detalle_auditoria(ctx)["tarjeta_conectada"] is False
    hilos[0]()
    ctx.db.close.assert_called_once()
    assert apagados == [True]


def test_un_fallo_de_la_bitacora_no_impide_el_apagado(entorno):
    client, ctx, _, apagados, hilos = entorno
    ctx.db.registrar_auditoria.side_effect = RuntimeError("bd")
    assert _apagar(client).status_code == 200
    hilos[0]()
    assert apagados == [True]


def test_camara_que_no_se_puede_evaluar_cuenta_como_no_segura(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.programas_para_seguridad.side_effect = RuntimeError("sin programas")
    r = _apagar(client)
    assert r.status_code == 200 and r.json()["camara_segura"] is False


def test_apaga_con_estado_seguro_actuando(entorno):
    """S9 (tanda 9, D9-1.3): con el estado seguro actuando también se apaga
    (antes 409 estado_seguro_activo); queda en la bitácora."""
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.estado_seguro.activo = True
    ctx.control_loop.estado_seguro.requiere_confirmacion = False
    _flags(ctx)
    r = _apagar(client)
    assert r.status_code == 200, r.text


def test_estado_seguro_esperando_confirmacion_se_puede_apagar(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.estado_seguro.activo = True
    ctx.control_loop.estado_seguro.requiere_confirmacion = True
    _flags(ctx)
    assert _apagar(client).status_code == 200


def test_estado_seguro_sin_datos_de_la_tarjeta_se_puede_apagar(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.estado_seguro.activo = True
    ctx.control_loop.estado_seguro.requiere_confirmacion = False
    ctx.control_loop.datos_vigentes = False
    ctx.control_loop.desconectado = True
    _flags(ctx)
    assert _apagar(client).status_code == 200


def test_apaga_con_datos_no_vigentes(entorno):
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.datos_vigentes = False
    assert _apagar(client).status_code == 200


def test_apaga_con_modo_prueba(entorno):
    """Un técnico reparando suele estar en modo prueba: puede dejarlo fuera de servicio."""
    client, ctx, _, _, hilos = entorno
    ctx.control_loop.test_mode_active = True
    assert _apagar(client).status_code == 200
    assert _detalle_auditoria(ctx)["modo_prueba"] is True
    ctx.control_loop.iniciar_apagado.assert_called_once()


def test_sin_ejecutable_no_apaga_windows(monkeypatch):
    import autoclave.backend.server as srv_mod
    monkeypatch.delenv("AUTOCLAVE_APAGADO_REAL", raising=False)
    monkeypatch.setattr(modulo_backend("rutas.apagado").sys, "frozen", False, raising=False)
    assert modulo_backend("rutas.apagado")._apagado_windows_habilitado() is False


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
    from autoclave.cliente.ui_service_backend import UIServiceBackend
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
    from autoclave.cliente.ui_service_backend import APAGADO_INCIERTO
    ok, motivo = _ui_con_error(TimeoutError("timeout")).apagar_equipo("principal")
    assert ok is False and motivo == APAGADO_INCIERTO


# ── A1 (tanda 3): robustez de la secuencia y del arranque posterior ────────

def test_control_loop_stop_cierra_el_puerto_aunque_el_all_off_lance():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._running = threading.Event()
    cl.thread = None
    cl.link = MagicMock()
    cl.link.all_off.side_effect = OSError("sin tarjeta")
    cl.stop()
    cl.link.stop.assert_called_once()


def test_control_loop_stop_sigue_si_el_cierre_del_enlace_lanza():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._running = threading.Event()
    cl.thread = None
    cl.link = MagicMock()
    cl.link.all_off.return_value = True
    cl.link.stop.side_effect = OSError("puerto")
    cl.stop()      # no lanza


def test_el_apagado_no_deja_marcas_que_impidan_arrancar(entorno):
    """El apagado en FALLA no escribe la marca de ciclo en curso ni toca el
    contador: el arranque siguiente es normal (sin intervención técnica)."""
    client, ctx, _, _, hilos = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    assert _apagar(client).status_code == 200
    hilos[0]()
    ctx.contador_ciclos.marcar_en_curso.assert_not_called()
    ctx.contador_ciclos.siguiente.assert_not_called()


def test_un_paso_colgado_no_retrasa_el_apagado_de_windows(entorno, monkeypatch):
    client, ctx, srv, apagados, hilos = entorno
    monkeypatch.setattr(modulo_backend("rutas.apagado"), "_TOPE_PASO_APAGADO_S", 0.2)
    libera = threading.Event()
    ctx.db.close.side_effect = lambda: libera.wait(5)
    assert _apagar(client).status_code == 200
    hilos[0]()
    assert apagados == [True]
    libera.set()


def test_iniciar_apagado_manda_all_off_de_inmediato():
    """SAF-01 de A1: el lazo se detiene y las salidas se apagan sin esperar a stop()."""
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl._running = threading.Event()
    cl._apagando = False
    cl.estado = MagicMock()
    cl.link = MagicMock()
    cl.iniciar_apagado()
    cl.link.all_off.assert_called_once()


def test_iniciar_apagado_sobrevive_a_un_all_off_que_lanza():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl._running = threading.Event()
    cl._apagando = False
    cl.estado = MagicMock()
    cl.link = MagicMock()
    cl.link.all_off.side_effect = OSError("sin tarjeta")
    cl.iniciar_apagado()
    assert cl.apagando is True


def test_no_se_entra_en_modo_prueba_mientras_se_apaga():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl._bloqueo_config = None
    cl._apagando = True
    ok, motivo = cl.enter_test_mode()
    assert ok is False and "apagando" in motivo
