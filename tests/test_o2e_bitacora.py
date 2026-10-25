# tests/test_o2e_bitacora.py
#
# O2e (tanda 6; mockup 9): Bitácora de auditoría. GET /audit_log con
# paginación y filtros (fecha, usuario, tipo), solo lectura para admin,
# técnico e ingeniero; textos por código (es/en) y valores en la unidad
# vigente; eventos nuevos de suspensión.

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import bitacora
from tests.backend_doble import fuente_backend

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.core.runtime.unidades import ConfigUnidades
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager()
    c.load_config()
    c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.config_unidades = ConfigUnidades(tmp_path / "u.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def _sembrar(db, n=25):
    for i in range(n):
        db.registrar_auditoria("login_ok", usuario="ana" if i % 2 else "tomas", rol="admin")
    db.registrar_auditoria("param_sistema_cambio", usuario="ines", rol="ingeniero",
                           entidad="temp_max_apertura", valor_anterior={"temp_max_apertura": 80},
                           valor_nuevo={"temp_max_apertura": 90})


@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("admin", 200), ("tecnico", 200),
                                          ("ingeniero", 200)])
def test_matriz_lectura(api, rol, esperado):
    client, srv, ctx, cab = api
    assert client.get("/audit_log", headers=cab(srv, rol)).status_code == esperado
    assert client.get("/audit_log").status_code == 401


def test_nadie_edita_ni_borra(api):
    client, srv, ctx, cab = api
    h = cab(srv, "ingeniero")
    for metodo in ("post", "put", "patch", "delete"):
        assert getattr(client, metodo)("/audit_log", headers=h).status_code == 405


def test_paginacion_y_filtros(api):
    client, srv, ctx, cab = api
    _sembrar(ctx.db)
    h = cab(srv, "admin")
    d = client.get("/audit_log", params={"por_pagina": 10}, headers=h).json()
    total = d["total"]
    assert total >= 26 and d["paginas"] == -(-total // 10) and len(d["filas"]) == 10
    ultima = client.get("/audit_log", params={"por_pagina": 10, "pagina": d["paginas"]}, headers=h).json()
    assert len(ultima["filas"]) == total - 10 * (d["paginas"] - 1)
    solo = client.get("/audit_log", params={"usuario": "ana", "evento": "login_ok"}, headers=h).json()
    assert solo["total"] == 12 and {f["usuario"] for f in solo["filas"]} == {"ana"}
    assert "login_ok" in d["tipos"] and "ines" in d["usuarios"]
    futuro = client.get("/audit_log", params={"desde": "2999-01-01"}, headers=h).json()
    assert futuro["total"] == 0 and futuro["paginas"] == 1
    hoy = client.get("/audit_log", params={"hasta": "2999-01-01"}, headers=h).json()
    assert hoy["total"] >= 26
    assert client.get("/audit_log", params={"desde": "ayer"}, headers=h).status_code == 422


def test_valores_en_la_unidad_vigente(api):
    client, srv, ctx, cab = api
    _sembrar(ctx.db, 0)
    h = cab(srv, "admin")
    f = client.get("/audit_log", params={"evento": "param_sistema_cambio"}, headers=h).json()["filas"][0]
    assert f["clave_texto"] == "bitacora.ev.param_sistema_cambio"
    assert "80" in f["anterior"] and "°C" in f["anterior"]
    ctx.config_unidades.guardar("F", "psi")
    f = client.get("/audit_log", params={"evento": "param_sistema_cambio"}, headers=h).json()["filas"][0]
    assert "176" in f["anterior"] and "°F" in f["anterior"]


def test_formateo_puro():
    metas = {"temp_max_apertura": {"unidad": "°C", "clase": "absoluto"},
             "rango_temp_drenaje": {"unidad": "°C", "clase": "diferencia"},
             "timeout_puerta": {"unidad": "s", "clase": "absoluto"}}
    uf = {"temperatura": "F", "presion": "kPa"}
    assert "176" in bitacora.formatear('{"temp_max_apertura": 80}', metas, uf)       # 80 °C = 176 °F
    assert "9" in bitacora.formatear('{"rango_temp_drenaje": 5}', metas, uf)         # Δ5 °C = Δ9 °F
    assert bitacora.formatear('{"timeout_puerta": 60}', metas, uf) == "60 s"
    assert bitacora.formatear(None, metas, uf) == ""
    assert bitacora.presentar({"evento": "raro"}, {}, uf)["clave_texto"] == "bitacora.ev_generico"


def test_suspension_no_queda_en_bitacora(api):
    # D9-6 (tanda 9): la suspensión pasó al log de desarrollo
    client, srv, ctx, cab = api
    assert client.post("/ui/standby", json={"activa": True, "pantalla": "puerta1"}).status_code == 200
    assert client.post("/ui/standby", json={"activa": False}).status_code == 200
    assert not ctx.db.get_auditoria(evento="suspension_entra")
    assert not ctx.db.get_auditoria(evento="suspension_sale")
    assert client.post("/ui/standby", json={"activa": "si"}).status_code == 422


def test_standby_informa_al_backend():
    from autoclave.ui_qml.bridge import standby as sb
    s = sb.Standby.__new__(sb.Standby)
    s._backend, s._ui = MagicMock(), MagicMock(connected=True)
    s._registrar_suspension = True
    original = sb._en_hilo
    sb._en_hilo = lambda tarea: tarea()
    try:
        s._informar_suspension(True)
    finally:
        sb._en_hilo = original
    s._backend.post.assert_called_once_with("/ui/standby", {"activa": True})


def test_textos_de_todos_los_eventos():
    for lang in ("es", "en"):
        b = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))["bitacora"]
        for e in bitacora.EVENTOS:
            assert b["ev"][e] and b["tipo"][e], (lang, e)
    # todo evento literal que el backend audita tiene texto propio
    fuente = fuente_backend()
    usados = set(re.findall(r'_auditar\(\s*"([A-Za-z_]+)"', fuente))
    assert usados - set(bitacora.EVENTOS) == set()


@pytest.mark.parametrize("rol", ["admin", "tecnico", "ingeniero"])
def test_visible_para_todos(rol):
    from autoclave.ui_qml.domain import permisos_opciones as p
    assert p.puede_ver("bitacora", rol) and p.edicion_permitida("CICLO", rol, "bitacora")


def test_controlador_filtros_y_paginas():
    import sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.bitacora_controller import BitacoraController
    from autoclave.ui_qml.sesion_backend import Resultado
    rutas = []

    class S:
        def enviar(self, m, r, c=None):
            rutas.append(r)
            pagina = int(re.search(r"pagina=(\d+)", r).group(1))
            return Resultado("ok", {"filas": [], "pagina": pagina, "paginas": 3, "total": 30,
                                    "usuarios": ["ana", "tomas"], "tipos": ["login_ok"]}, 200)
    c = BitacoraController(sesion=S())
    c.cargar()
    c.siguienteUsuario()
    assert c.usuario == "ana" and "usuario=ana" in rutas[-1]
    c.siguienteTipo()
    assert "evento=login_ok" in rutas[-1]
    assert not c.fijarDesde("21/10") and c.mensaje == "bitacora.err_fecha"
    assert c.fijarDesde("2026-10-01") and "desde=2026-10-01" in rutas[-1]
    c.paginaSiguiente()
    assert "pagina=2" in rutas[-1] and c.pagina == 2


FILAS = [
    {"id": 3, "ts": "2026-10-21T08:15:02", "usuario": "ines_ing", "evento": "param_sistema_cambio",
     "entidad": "temp_max_apertura", "anterior": "80.0 °C", "nuevo": "90.0 °C",
     "clave_texto": "bitacora.ev.param_sistema_cambio"},
    {"id": 2, "ts": "2026-10-21T08:10:40", "usuario": "ana_admin", "evento": "usuario_desactivado",
     "entidad": "luis_tec", "anterior": "", "nuevo": "", "clave_texto": "bitacora.ev.usuario_desactivado"},
    {"id": 1, "ts": "2026-10-21T08:00:00", "usuario": "<i>x</i>", "evento": "login_ok", "entidad": "",
     "anterior": "", "nuevo": "", "clave_texto": "bitacora.ev.login_ok"},
]


def test_pantalla():
    pytest.importorskip("PySide6")
    from tests.opciones_qml_doble import correr
    datos = {"filas": FILAS, "total": 27, "pagina": 1, "paginas": 3, "usuarios": ["ana_admin"],
             "tipos": ["login_ok"]}
    r = correr("bitacora", "tecnico", {"/audit_log": datos},
               pasos=[{"leer": [("textoPagina", "text"), ("paginaAnterior", "habilitado"),
                                ("paginaSiguiente", "habilitado"), ("avisoEdicionBloqueada", "visible")],
                       "captura": "O2e_1_bitacora.png"}])
    assert r["avisos"] == []
    p = r["pasos"][0]["props"]
    assert p["textoPagina.text"] == "Página 1 de 3"
    assert p["paginaAnterior.habilitado"] is False and p["paginaSiguiente.habilitado"] is True
    assert p["avisoEdicionBloqueada.visible"] is False
    t = " ".join(r["pasos"][0]["textos"])
    assert "temp_max_apertura: 80.0 °C → 90.0 °C" in t and "desactivó al usuario luis_tec" in t
    assert "&lt;i>x&lt;/i>" in t                       # el usuario se escapa antes de dar formato
