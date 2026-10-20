"""B5 (tanda 4): aviso NO bloqueante de impresora desconectada al arrancar."""

import sys
import threading
import time
import types
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.vigilancia_impresora import ConfigImpresora, VigilanciaImpresora
from autoclave.devices.printer import win32_printer as wp
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, IMPRESORA_DESCONECTADA, Nivel)


@pytest.fixture(autouse=True)
def sin_observadores():
    previos = list(wp._observadores_exito)
    wp._observadores_exito.clear()
    yield
    wp._observadores_exito[:] = previos


def _win32(monkeypatch, impresoras=("Impresora_Termica",), attrs=0, status=0,
           enum_falla=False, open_falla=False, get_falla=False):
    m = types.ModuleType("win32print")
    m.PRINTER_ENUM_LOCAL, m.PRINTER_ENUM_CONNECTIONS = 2, 4

    def enum(flags, nombre, nivel):
        if enum_falla:
            raise OSError("spooler detenido")
        return [(0, "", n, "") for n in impresoras]
    m.EnumPrinters = enum

    def abrir(n):
        if open_falla:
            raise OSError("no abre")
        return object()
    m.OpenPrinter = abrir

    def info(h, nivel):
        if get_falla:
            raise OSError("sin info")
        return {"Attributes": attrs, "Status": status}
    m.GetPrinter = info
    m.ClosePrinter = lambda h: None
    m.StartDocPrinter = lambda *a: 1
    m.WritePrinter = lambda *a: None
    m.EndDocPrinter = lambda *a: None
    monkeypatch.setitem(sys.modules, "win32print", m)
    return m


# ── conexion_impresora ──────────────────────────────────────────────────────

def test_conectada(monkeypatch):
    _win32(monkeypatch)
    assert wp.conexion_impresora() == wp.CONECTADA


def test_sin_papel_o_con_error_sigue_conectada(monkeypatch):
    _win32(monkeypatch, status=0x10 | 0x02)
    assert wp.conexion_impresora() == wp.CONECTADA


def test_ausente_de_la_lista_es_desconectada(monkeypatch):
    _win32(monkeypatch, impresoras=("Otra",))
    assert wp.conexion_impresora() == wp.DESCONECTADA


@pytest.mark.parametrize("attrs, status", [(0x400, 0), (0, 0x80), (0, 0x1000)])
def test_cola_sin_conexion_es_desconectada(monkeypatch, attrs, status):
    _win32(monkeypatch, attrs=attrs, status=status)
    assert wp.conexion_impresora() == wp.DESCONECTADA


@pytest.mark.parametrize("falla", [{"enum_falla": True}, {"open_falla": True}, {"get_falla": True}])
def test_si_no_se_pudo_consultar_es_desconocida(monkeypatch, falla):
    _win32(monkeypatch, **falla)
    assert wp.conexion_impresora() == wp.DESCONOCIDA


def test_sin_win32print_es_desconocida(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32print", None)       # ImportError al importar
    assert wp.conexion_impresora() == wp.DESCONOCIDA


# ── bandera ─────────────────────────────────────────────────────────────────

def test_bandera_por_defecto_habilitada_y_robusta(tmp_path):
    c = ConfigImpresora(tmp_path / "impresora.json")
    assert c.habilitada() is True                              # comportamiento actual
    (tmp_path / "impresora.json").write_text("{roto", encoding="utf-8")
    assert c.habilitada() is True
    (tmp_path / "impresora.json").write_text('{"habilitada": "no"}', encoding="utf-8")
    assert c.habilitada() is True
    assert c.guardar(False) is False and c.habilitada() is False
    with pytest.raises(ValueError):
        c.guardar("si")


# ── verificación ────────────────────────────────────────────────────────────

def _vig(tmp_path, resultado, habilitada=True, plazo_s=1.0, consultar=None):
    cfg = ConfigImpresora(tmp_path / "impresora.json")
    cfg.guardar(habilitada)
    alarmas = AlarmManager()
    llamadas = []

    def consulta():
        llamadas.append(1)
        return resultado

    v = VigilanciaImpresora(cfg, alarmas, consultar=consultar or consulta, plazo_s=plazo_s)
    return v, alarmas, llamadas


def _ids(alarmas):
    return [i.definicion.codigo for i in alarmas.activas()]


def test_habilitada_y_conectada_no_avisa(tmp_path):
    v, alarmas, _ = _vig(tmp_path, wp.CONECTADA)
    assert v.verificar() == wp.CONECTADA and _ids(alarmas) == []


def test_habilitada_y_desconectada_avisa_en_status_y_no_bloquea(tmp_path):
    v, alarmas, _ = _vig(tmp_path, wp.DESCONECTADA)
    v.verificar()
    assert _ids(alarmas) == [IMPRESORA_DESCONECTADA]
    # Visible donde ven los avisos Preciclo y la campana: /status.alarms con
    # nivel de aviso/alerta (no FALLA ni EMERGENCIA) y sin bloquear nada
    d = CATALOGO[IMPRESORA_DESCONECTADA]
    assert d.nivel is Nivel.AVISO and d.bloquea_inicio is False
    assert alarmas.has_blocking_alarm() is False
    from autoclave.backend import server
    dto = server._alarma_dto(alarmas.activas()[0])
    assert dto["level"] == "ALERTA" and "no conectada" in dto["description"].lower()


def test_el_aviso_no_se_duplica(tmp_path):
    v, alarmas, _ = _vig(tmp_path, wp.DESCONECTADA)
    v.verificar()
    v.verificar()
    assert _ids(alarmas) == [IMPRESORA_DESCONECTADA]


def test_deshabilitada_no_consulta_ni_avisa(tmp_path):
    v, alarmas, llamadas = _vig(tmp_path, wp.DESCONECTADA, habilitada=False)
    assert v.verificar() is None and llamadas == [] and _ids(alarmas) == []


def test_desconocida_no_avisa(tmp_path):
    v, alarmas, _ = _vig(tmp_path, wp.DESCONOCIDA)
    v.verificar()
    assert _ids(alarmas) == []


def test_consulta_lenta_no_avisa_ni_retrasa(tmp_path):
    def lenta():
        time.sleep(3)
        return wp.DESCONECTADA
    v, alarmas, _ = _vig(tmp_path, None, plazo_s=0.2, consultar=lenta)
    t0 = time.monotonic()
    assert v.verificar() is None
    assert time.monotonic() - t0 < 1.5 and _ids(alarmas) == []


def test_consulta_con_error_no_avisa_ni_lanza(tmp_path):
    def rota():
        raise RuntimeError("spooler")
    v, alarmas, _ = _vig(tmp_path, None, consultar=rota)
    assert v.verificar() in (None, wp.DESCONOCIDA) and _ids(alarmas) == []


def test_iniciar_vuelve_de_inmediato(tmp_path):
    def lenta():
        time.sleep(1)
        return wp.CONECTADA
    v, _, _ = _vig(tmp_path, None, plazo_s=2.0, consultar=lenta)
    t0 = time.monotonic()
    hilo = v.iniciar()
    assert time.monotonic() - t0 < 0.3 and isinstance(hilo, threading.Thread)
    hilo.join(5)


def test_una_impresion_exitosa_limpia_el_aviso(tmp_path, monkeypatch):
    _win32(monkeypatch)
    v, alarmas, _ = _vig(tmp_path, wp.DESCONECTADA)
    v.verificar()
    assert _ids(alarmas) == [IMPRESORA_DESCONECTADA]
    assert wp.print_raw("ticket") is True
    assert _ids(alarmas) == [] and v.aviso_activo is False


def test_una_impresion_fallida_no_limpia_el_aviso(tmp_path, monkeypatch):
    _win32(monkeypatch, open_falla=True)
    v, alarmas, _ = _vig(tmp_path, wp.DESCONECTADA)
    v.verificar()
    assert wp.print_raw("ticket") is False
    assert _ids(alarmas) == [IMPRESORA_DESCONECTADA]


# ── la impresora nunca bloquea un ciclo ─────────────────────────────────────

def test_impresion_que_falla_degrada_sin_bloquear(monkeypatch):
    """El cierre del ciclo encola el reporte: aunque la impresora no responda,
    `enqueue` no lanza ni espera, y el hilo de impresión sigue vivo."""
    _win32(monkeypatch, open_falla=True)
    from autoclave.devices.printer.realtime_printer import RealtimePrinter
    rp = RealtimePrinter()
    t0 = time.monotonic()
    rp.enqueue("fin de ciclo")
    assert time.monotonic() - t0 < 0.2
    rp._queue.join()
    assert rp._thread.is_alive()


def test_el_servicio_no_toca_el_control_del_ciclo():
    import inspect
    from autoclave.core.runtime import vigilancia_impresora as mod
    fuente = inspect.getsource(mod)
    assert "control_loop" not in fuente and "GlobalState" not in fuente


# ── endpoints ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rol, esperado", [("operador", 403), ("tecnico", 200), ("ingeniero", 200)])
def test_solo_tecnico_o_ingeniero_edita_la_bandera_y_queda_auditada(tmp_path, rol, esperado):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.backend_doble import cabecera, cargar_servidor
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.config_impresora = ConfigImpresora(tmp_path / "impresora.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app)
    assert client.get("/printer/config").json() == {"habilitada": True}
    assert client.put("/printer/config", json={"habilitada": False}).status_code == 401
    r = client.put("/printer/config", headers=cabecera(srv, rol), json={"habilitada": False})
    assert r.status_code == esperado
    if esperado == 200:
        assert ctx.config_impresora.habilitada() is False
        assert any(f["evento"] == "impresora_configurada" for f in db.get_auditoria(limite=10))
    else:
        assert ctx.config_impresora.habilitada() is True
