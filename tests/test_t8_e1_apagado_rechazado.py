"""D8-3.21 (tanda 8, E1): si Windows rechaza el apagado, la pantalla lo dice
con texto del catálogo ("Windows no permitió apagar el equipo: apáguelo
manualmente") y queda en la bitácora. Nunca se apaga el equipo real: el
subprocess se reemplaza en todas las pruebas."""

import json
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cargar_servidor, modulo_backend

_RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def servidor(monkeypatch):
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.apagando = False
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    llamadas = []

    def run_falso(resultado):
        def run(args, **k):
            llamadas.append(args)
            if isinstance(resultado, BaseException):
                raise resultado
            return resultado
        monkeypatch.setattr(subprocess, "run", run)
    return srv, ctx, llamadas, run_falso


def _r(codigo, err=""):
    return SimpleNamespace(returncode=codigo, stderr=err, stdout="")


def test_estado_inicial_sin_rechazo(servidor):
    srv, ctx, _, _ = servidor
    r = TestClient(srv.app).get("/system/shutdown/estado")
    assert r.status_code == 200
    assert r.json()["windows_rechazado"] is False


def test_codigo_distinto_de_cero_es_rechazo_y_va_a_la_bitacora(servidor):
    srv, ctx, llamadas, run_falso = servidor
    ctx.control_loop.apagando = True
    run_falso(_r(1190, "Ya hay un apagado programado"))
    modulo_backend("rutas.apagado")._apagar_windows()
    assert llamadas and llamadas[0][0] == "shutdown"
    r = TestClient(srv.app).get("/system/shutdown/estado").json()
    assert r == {"apagando": True, "windows_rechazado": True}
    ctx.db.registrar_auditoria_tras_cierre.assert_called_once()
    args, kw = ctx.db.registrar_auditoria_tras_cierre.call_args
    assert args[0] == "apagado_windows_rechazado"
    assert "1190" in json.dumps(kw.get("detalle"), ensure_ascii=False)


@pytest.mark.parametrize("error", [FileNotFoundError("shutdown"), OSError("acceso denegado"),
                                   subprocess.TimeoutExpired("shutdown", 30)])
def test_excepcion_al_lanzar_el_apagado_es_rechazo(servidor, error):
    srv, ctx, _, run_falso = servidor
    run_falso(error)
    modulo_backend("rutas.apagado")._apagar_windows()      # no lanza
    assert TestClient(srv.app).get("/system/shutdown/estado").json()["windows_rechazado"] is True
    ctx.db.registrar_auditoria_tras_cierre.assert_called_once()


def test_apagado_aceptado_no_es_rechazo(servidor):
    srv, ctx, _, run_falso = servidor
    run_falso(_r(0))
    modulo_backend("rutas.apagado")._apagar_windows()
    assert TestClient(srv.app).get("/system/shutdown/estado").json()["windows_rechazado"] is False
    ctx.db.registrar_auditoria_tras_cierre.assert_not_called()


def test_sin_base_usa_la_base_real(servidor):
    srv, ctx, _, run_falso = servidor
    ctx.sin_base_de_datos = True
    run_falso(_r(5))
    modulo_backend("rutas.apagado")._apagar_windows()
    ctx.db_real.registrar_auditoria_tras_cierre.assert_called_once()


def test_fallo_de_la_bitacora_no_impide_el_aviso(servidor):
    srv, ctx, _, run_falso = servidor
    ctx.db.registrar_auditoria_tras_cierre.side_effect = sqlite3.OperationalError("bloqueada")
    run_falso(_r(5))
    modulo_backend("rutas.apagado")._apagar_windows()
    assert TestClient(srv.app).get("/system/shutdown/estado").json()["windows_rechazado"] is True


# ── base de datos: el registro se escribe aunque la conexión ya se cerró ────

def test_registrar_auditoria_tras_cierre_escribe_con_la_base_cerrada(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    ruta = tmp_path / "a.db"
    db = DbManager(ruta)
    db.close()
    db.registrar_auditoria_tras_cierre("apagado_windows_rechazado", entidad="/system/shutdown",
                                       detalle={"codigo": 5})
    con = sqlite3.connect(str(ruta))
    fila = con.execute("SELECT evento, entidad, detalle FROM audit_log"
                       " WHERE evento='apagado_windows_rechazado'").fetchone()
    con.close()
    assert fila[0] == "apagado_windows_rechazado" and fila[1] == "/system/shutdown"
    assert json.loads(fila[2]) == {"codigo": 5}


# ── servicio de la UI y puente QML ─────────────────────────────────────────

def test_ui_service_estado_apagado():
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.get.return_value = {"apagando": True, "windows_rechazado": True}
    assert ui.estado_apagado() == {"apagando": True, "windows_rechazado": True}
    ui.backend.get.assert_called_once()
    assert ui.backend.get.call_args.kwargs["path"] == "/system/shutdown/estado"


def test_ui_service_estado_apagado_sin_respuesta_es_none():
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.get.side_effect = ConnectionError("apagado")
    assert ui.estado_apagado() is None


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _comandos(estado):
    from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema
    puente = MagicMock()
    puente.connected = True
    ui = MagicMock()
    ui.apagar_equipo.return_value = (True, "")
    ui.estado_apagado.return_value = estado
    c = ComandosSistema(puente, ui, 1, ejecutar=lambda tarea: tarea())
    return c, ui


def test_puente_muestra_el_rechazo_de_windows(qt_app):
    c, ui = _comandos({"apagando": True, "windows_rechazado": True})
    assert c.apagadoRechazado is False
    c.apagarEquipo()
    assert c._vigilancia_apagado.isActive()
    c._consultarApagado()
    assert c.apagadoRechazado is True
    assert not c._vigilancia_apagado.isActive()
    assert c.ocupado is True        # el botón sigue deshabilitado


@pytest.mark.parametrize("estado", [None, {"apagando": True, "windows_rechazado": False},
                                    {"windows_rechazado": "si"}])
def test_puente_sin_rechazo_confirmado_no_lo_muestra(qt_app, estado):
    c, _ = _comandos(estado)
    c.apagarEquipo()
    c._consultarApagado()
    assert c.apagadoRechazado is False
    assert c._vigilancia_apagado.isActive()
    c._vigilancia_apagado.stop()


def test_puente_apagado_rechazado_por_el_backend_no_vigila(qt_app):
    c, ui = _comandos(None)
    ui.apagar_equipo.return_value = (False, "ciclo en curso")
    c.apagarEquipo()
    assert not c._vigilancia_apagado.isActive()


def test_panel_equipo_usa_el_texto_del_catalogo():
    qml = (_RAIZ / "src/autoclave/ui_qml/qml/Componentes/PanelEquipo.qml").read_text(encoding="utf-8")
    assert "equipo.apagado_windows_rechazado" in qml and "apagadoRechazado" in qml
    for idioma in ("es", "en"):
        cat = json.loads((_RAIZ / f"src/autoclave/i18n/{idioma}.json").read_text(encoding="utf-8"))
        assert cat["equipo"]["apagado_windows_rechazado"]
    es = json.loads((_RAIZ / "src/autoclave/i18n/es.json").read_text(encoding="utf-8"))
    assert es["equipo"]["apagado_windows_rechazado"] == (
        "Windows no permitió apagar el equipo: apáguelo manualmente")


def test_registrar_auditoria_tras_cierre_no_espera_el_lock_de_la_base(tmp_path):
    """SAF-05 (revisión final): si el paso "cerrar la base" quedó colgado con
    el lock tomado, el registro del rechazo no se bloquea (usa su conexión)."""
    from autoclave.services.domain.logging.db_manager import DbManager
    ruta = tmp_path / "b.db"
    db = DbManager(ruta)
    db.close()
    db._lock.acquire()
    try:
        hilo = threading.Thread(target=db.registrar_auditoria_tras_cierre,
                                args=("apagado_windows_rechazado",), daemon=True)
        hilo.start()
        hilo.join(5.0)
        assert not hilo.is_alive()
    finally:
        db._lock.release()
    con = sqlite3.connect(str(ruta))
    n = con.execute("SELECT COUNT(*) FROM audit_log WHERE evento='apagado_windows_rechazado'").fetchone()[0]
    con.close()
    assert n == 1


def test_puente_apagado_incierto_tambien_vigila(qt_app):
    """TMG-02 (revisión final): sin respuesta al POST el backend puede haberlo
    aceptado; se vigila igual para poder mostrar un rechazo de Windows."""
    from autoclave.cliente.ui_service_backend import APAGADO_INCIERTO
    c, ui = _comandos({"apagando": True, "windows_rechazado": True})
    ui.apagar_equipo.return_value = (False, APAGADO_INCIERTO)
    c.apagarEquipo()
    assert c.mensaje == APAGADO_INCIERTO
    assert c._vigilancia_apagado.isActive()
    c._consultarApagado()
    assert c.apagadoRechazado is True


def test_registrar_auditoria_tras_cierre_no_crea_una_base_nueva(tmp_path):
    """TMG-03 (revisión final): sin el archivo no se crea una base vacía."""
    from autoclave.services.domain.logging.db_manager import DbManager
    ruta = tmp_path / "c.db"
    db = DbManager(ruta)
    db.close()
    ruta.unlink()
    with pytest.raises(sqlite3.OperationalError):
        db.registrar_auditoria_tras_cierre("apagado_windows_rechazado")
    assert not ruta.exists()
