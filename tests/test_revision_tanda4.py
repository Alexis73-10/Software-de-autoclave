"""Correcciones de la revisión de seguridad y temporización de la tanda 4
(SAF-01, SAF-03, SAF-06, TMG-01, TMG-02, TMG-03/09, TMG-08)."""

import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.autenticacion import AlmacenTokens
from autoclave.core.runtime.sesion_inactividad import PLAZO_TOKEN_BACKEND_S
from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import cargar_servidor, fijar_en_backend, modulo_backend


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


# ── SAF-01: el vigilante cierra el modo prueba si la sesión dueña caduca ────

@pytest.fixture
def srv_prueba(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.bloqueo_maquina.return_value = threading.RLock()
    srv, _ = cargar_servidor(ctx)
    reloj = Reloj()
    fijar_en_backend("tokens", AlmacenTokens(reloj=reloj))
    dueno = modulo_backend("dependencias").tokens.emitir("tec_dueno", "Dueño", "tecnico", False)
    modulo_backend("rutas.io")._token_modo_prueba = dueno.token
    return srv, ctx, db, reloj, dueno


def test_dueno_vigente_el_vigilante_no_hace_nada(srv_prueba):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S - 1
    assert modulo_backend("rutas.io")._revisar_dueno_modo_prueba() is False
    ctx.control_loop.exit_test_mode.assert_not_called()
    assert modulo_backend("rutas.io")._token_modo_prueba == dueno.token


def test_dueno_caducado_el_vigilante_apaga_todo_y_lo_registra(srv_prueba, caplog):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    with caplog.at_level(logging.INFO):
        assert modulo_backend("rutas.io")._revisar_dueno_modo_prueba() is True
    ctx.control_loop.exit_test_mode.assert_called_once()        # ALL_OFF y se reanuda
    assert modulo_backend("rutas.io")._token_modo_prueba is None
    # Tanda 17 (BIT-01, decisión de Cristian): modo_prueba_sale va al log de desarrollo,
    # no a audit_log; el dueño y el motivo siguen quedando registrados ahí
    assert db.get_auditoria(evento="modo_prueba_sale") == []
    assert any("modo_prueba_sale" in r.getMessage() and "tec_dueno" in r.getMessage()
               and "caducada" in r.getMessage() for r in caplog.records)


def test_dueno_que_cerro_sesion_sin_salir_tambien_se_cierra(srv_prueba):
    srv, ctx, db, reloj, dueno = srv_prueba
    modulo_backend("dependencias").tokens.invalidar(dueno.token)
    assert modulo_backend("rutas.io")._revisar_dueno_modo_prueba() is True


def test_sin_modo_prueba_o_sin_dueno_no_hace_nada(srv_prueba):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    ctx.control_loop.test_mode_active = False
    assert modulo_backend("rutas.io")._revisar_dueno_modo_prueba() is False
    modulo_backend("rutas.io")._token_modo_prueba = None
    ctx.control_loop.test_mode_active = True
    assert modulo_backend("rutas.io")._revisar_dueno_modo_prueba() is False
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_el_vigilante_se_lanza_con_el_arranque(srv_prueba, monkeypatch):
    srv, *_ = srv_prueba
    lanzados = []
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: None)
    monkeypatch.setattr(modulo_backend("rutas.io"), "_vigilar_dueno_modo_prueba", lambda *a, **k: lanzados.append(1))
    srv._hilo_arranque = None
    modulo_backend("rutas.io")._hilo_vigilancia_dueno = None
    srv.iniciar_arranque()
    modulo_backend("rutas.io")._hilo_vigilancia_dueno.join(2)
    assert lanzados == [1]


def test_el_vigilante_usa_un_plazo_monotonico_menor_que_la_sesion():
    import autoclave.backend.server as s
    assert modulo_backend("rutas.io").VIGILANCIA_DUENO_PRUEBA_S <= 5.0


def test_tmg08_el_paro_registra_al_dueno_aunque_su_sesion_haya_caducado(srv_prueba, caplog):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    ctx.control_loop.test_mode_active = False
    with caplog.at_level(logging.INFO):
        srv._prueba_cancelada_por_paro()
    # Tanda 17 (BIT-01, decisión de Cristian): modo_prueba_sale va al log de desarrollo,
    # no a audit_log; el dueño y el motivo siguen quedando registrados ahí
    assert db.get_auditoria(evento="modo_prueba_sale") == []
    assert any("modo_prueba_sale" in r.getMessage() and "tec_dueno" in r.getMessage()
               and "paro de emergencia" in r.getMessage() for r in caplog.records)


# ── SAF-03 y SAF-06: salida forzada ─────────────────────────────────────────

def _cliente(srv):
    return TestClient(srv.app)


def test_saf03_el_tecnico_dueno_puede_forzar_su_propio_modo_prueba(srv_prueba):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1                       # su token caducó
    nuevo = modulo_backend("dependencias").tokens.emitir("tec_dueno", "Dueño", "tecnico", False)   # vuelve a entrar
    r = _cliente(srv).post("/io/test/force-exit", json={"confirmar": True},
                           headers={"Authorization": f"Bearer {nuevo.token}"})
    assert r.status_code == 200 and r.json()["dueno"] == "tec_dueno"


def test_saf03_otro_tecnico_sigue_sin_poder(srv_prueba):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    otro = modulo_backend("dependencias").tokens.emitir("tec_otro", "Otro", "tecnico", False)
    r = _cliente(srv).post("/io/test/force-exit", json={"confirmar": True},
                           headers={"Authorization": f"Bearer {otro.token}"})
    assert r.status_code == 403 and r.json()["codigo"] == "rol_sin_permiso"
    ctx.control_loop.exit_test_mode.assert_not_called()


@pytest.mark.parametrize("valor", ["true", 1, "yes", "on"])
def test_saf06_la_confirmacion_exige_el_literal_true(srv_prueba, valor):
    srv, ctx, db, reloj, dueno = srv_prueba
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    ing = modulo_backend("dependencias").tokens.emitir("ing", "Ing", "ingeniero", False)
    r = _cliente(srv).post("/io/test/force-exit", json={"confirmar": valor},
                           headers={"Authorization": f"Bearer {ing.token}"})
    assert r.status_code == 422
    ctx.control_loop.exit_test_mode.assert_not_called()


# ── TMG-01: el contador que no se puede escribir no deja el ciclo sin registro ─

def test_tmg01_reemplazo_bloqueado_un_instante_se_reintenta(tmp_path, monkeypatch):
    from autoclave.core.runtime import contador_ciclos as cc
    c = cc.ContadorCiclos(tmp_path / "c.json")
    real = cc.os.replace
    fallos = {"n": 2}

    def replace(a, b):
        if fallos["n"]:
            fallos["n"] -= 1
            raise PermissionError(32, "en uso por otro proceso")
        return real(a, b)
    monkeypatch.setattr(cc.os, "replace", replace)
    monkeypatch.setattr(cc, "ESPERA_REINTENTO_S", 0.0)
    assert c.siguiente(None) == 1 and c.ultimo == 1


def test_tmg01_reemplazo_siempre_bloqueado_lanza_y_no_deja_temporal(tmp_path, monkeypatch):
    from autoclave.core.runtime import contador_ciclos as cc
    c = cc.ContadorCiclos(tmp_path / "c.json")
    monkeypatch.setattr(cc.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(32, "x")))
    monkeypatch.setattr(cc, "ESPERA_REINTENTO_S", 0.0)
    with pytest.raises(PermissionError):
        c.siguiente(None)
    assert not list(tmp_path.glob("*.tmp"))


def test_tmg01_cycle_logger_usa_un_numero_provisional_y_sigue(monkeypatch):
    from autoclave.services.domain.logging.cycle_logger import CycleLogger
    cl = object.__new__(CycleLogger)
    cl._numero_provisional = None
    contador = MagicMock()
    contador.siguiente.side_effect = PermissionError(32, "en uso")
    contador.ultimo = 41
    cl.contador = contador
    assert cl._siguiente_protegido(45) == 46
    assert cl._siguiente_protegido(None) == 47           # sigue subiendo, sin repetir
    contador.siguiente.side_effect = None
    contador.siguiente.return_value = 48
    assert cl._siguiente_protegido(None) == 48 and cl._numero_provisional is None


# ── TMG-02: la lectura de la base en el tick no espera el candado ───────────

def test_tmg02_max_numero_ciclo_con_espera_no_se_bloquea(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.max_numero_ciclo(espera_s=0.05) == 0
    db._lock.acquire()
    try:
        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            db.max_numero_ciclo(espera_s=0.05)
        assert time.monotonic() - t0 < 1.0
    finally:
        db._lock.release()
    assert db.max_numero_ciclo() == 0                    # sin espera, como antes


def test_tmg02_el_cycle_logger_pide_espera_corta(monkeypatch):
    from autoclave.services.domain.logging import cycle_logger as mod
    cl = object.__new__(mod.CycleLogger)
    cl._numero_provisional = None
    cl.sin_base_de_datos = False
    cl.db = MagicMock()
    cl.db.max_numero_ciclo.side_effect = TimeoutError("base ocupada")
    cl.contador = MagicMock()
    cl.contador.siguiente.return_value = 7
    assert cl._numero_nuevo() == 7
    assert cl.db.max_numero_ciclo.call_args.kwargs == {"espera_s": mod.ESPERA_BD_EN_TICK_S}
    cl.contador.siguiente.assert_called_once_with(None)


# ── TMG-03/09: aviso de impresora ───────────────────────────────────────────

def _vig(tmp_path, consultar):
    from autoclave.core.runtime.vigilancia_impresora import ConfigImpresora, VigilanciaImpresora
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    alarmas = AlarmManager()
    return VigilanciaImpresora(ConfigImpresora(tmp_path / "i.json"), alarmas,
                               consultar=consultar), alarmas


def test_tmg09_una_impresion_confirmada_durante_la_consulta_evita_el_aviso(tmp_path):
    from autoclave.devices.printer import win32_printer as wp
    llamadas = []

    def consultar():
        llamadas.append(1)
        if len(llamadas) == 1:
            v.impresion_exitosa()        # ticket que sale mientras se consulta
            return wp.DESCONECTADA       # respuesta vieja de la primera consulta
        return wp.CONECTADA
    v, alarmas = _vig(tmp_path, consultar)
    v.verificar()
    assert alarmas.activas() == []


def test_tmg09_si_otro_camino_resuelve_el_aviso_puede_volver_a_activarse(tmp_path):
    from autoclave.devices.printer import win32_printer as wp
    v, alarmas = _vig(tmp_path, lambda: wp.DESCONECTADA)
    v.verificar()
    alarmas.resolver_todas_por_reinicio()
    assert v.aviso_activo is False
    v.verificar()
    assert v.aviso_activo is True


def test_tmg03_sin_aviso_ni_verificacion_una_impresion_no_consulta(tmp_path):
    from autoclave.devices.printer import win32_printer as wp
    consultas = []
    v, alarmas = _vig(tmp_path, lambda: consultas.append(1) or wp.CONECTADA)
    v.impresion_exitosa()                 # cada línea del ticket de ciclo
    assert consultas == []


def test_tmg03_print_startup_avisa_el_exito_solo_tras_cerrar_el_trabajo(monkeypatch):
    import sys
    import types
    from autoclave.devices.printer import win32_printer as wp
    exitos = []
    monkeypatch.setattr(wp, "_observadores_exito", [lambda: exitos.append(1)])
    monkeypatch.setattr(wp, "_LOGO_PATH", SimpleNamespace(exists=lambda: False))

    class Impresora:
        def __init__(self, *a, **k):
            pass

        def text(self, t):
            pass

        def close(self):
            raise OSError("EndDoc falló")
    mod = types.ModuleType("escpos.printer")
    mod.Win32Raw = Impresora
    monkeypatch.setitem(sys.modules, "escpos.printer", mod)
    assert wp.print_startup("x") is False and exitos == []
    Impresora.close = lambda self: None
    assert wp.print_startup("x") is True and exitos == [1]
