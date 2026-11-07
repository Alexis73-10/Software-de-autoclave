"""T30-01 (tanda 30): operador obligatorio al iniciar el ciclo sin sesión.

- backend: POST /cycle/start sin token válido y con operadores activos exige
  `operador_id` de un operador activo (409 operador_requerido, 422
  operador_invalido, 503 operador_no_verificable; sin START_CICLO); con sesión,
  el usuario; sin operadores activos o sin base, como antes; el nombre queda
  en `estado.operador_inicio` y en la fila `ciclo_iniciado` de la bitácora;
- cliente: start_cycle envía operador_id y guarda el rechazo por hilo;
- controlador: 409 operador_requerido abre la elección; elegir reenvía;
  Cancelar no inicia; sin lista no inicia;
- códigos: ruta y texto es/en (sesion_backend);
- QML: PantallaPreciclo real (offscreen, subproceso) muestra la lista y solo
  habilita «Iniciar ciclo» con un operador tocado.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


# ── backend ─────────────────────────────────────────────────────────────────

@pytest.fixture
def api(monkeypatch, tmp_path):
    db = DbManager(tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.apagando = False
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    ctx.control_loop.cycle.danado = []
    ctx.control_loop.cycle.id = "prog1"
    ctx.control_loop.cycle.get_param.side_effect = lambda *a, default=None: default
    ctx.estado = SimpleNamespace(
        get_flag=lambda f: f == "LISTO_PARA_CICLO", set_flag=MagicMock(), operador_inicio="",
        sensores_pres={"pres_camara": 101.0, "pres_chaqueta": 300.0})
    ctx.cap.has_liquids = True
    srv, _ = cargar_servidor(ctx)
    monkeypatch.setattr(modulo_backend("rutas.ciclo").sc, "verificar_inicio", lambda *a: None)
    monkeypatch.setattr(modulo_backend("rutas.ciclo"), "_rechazo_salidas_pendientes", lambda: None)
    yield TestClient(srv.app), ctx, srv
    db.close()


def _inicio_marcado(ctx) -> bool:
    return ("START_CICLO", True) in [c.args for c in ctx.estado.set_flag.call_args_list]


def _filas(ctx):
    filas = [dict(f) for f in ctx.db.get_auditoria(evento="ciclo_iniciado", limite=50)]
    for f in filas:
        if isinstance(f["detalle"], str):
            f["detalle"] = json.loads(f["detalle"])
    return filas


def test_sin_operadores_activos_inicia_sin_operador_como_antes(api):
    client, ctx, _ = api
    inactivo = ctx.db.crear_operador("Inactivo")
    ctx.db.fijar_activo_operador(inactivo, False)
    r = client.post("/cycle/start")
    assert r.status_code == 200, r.text
    assert ctx.estado.operador_inicio == "" and _inicio_marcado(ctx)
    fila = _filas(ctx)[0]
    assert fila["detalle"]["origen_operador"] == "sin_operador" and fila["usuario"] == ""


@pytest.mark.parametrize("cuerpo", [None, {}, {"operador_id": None}])
def test_sin_sesion_y_con_activos_sin_operador_409(api, cuerpo):
    client, ctx, _ = api
    ctx.db.crear_operador("Ana")
    r = client.post("/cycle/start", json=cuerpo) if cuerpo is not None else client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == "operador_requerido"
    assert not _inicio_marcado(ctx) and _filas(ctx) == []


@pytest.mark.parametrize("cabeceras", [{"Authorization": "Bearer inexistente"},
                                       {"Authorization": "basura"}])
def test_token_invalido_cuenta_como_sin_sesion(api, cabeceras):
    client, ctx, _ = api
    ctx.db.crear_operador("Ana")
    r = client.post("/cycle/start", headers=cabeceras)
    assert r.status_code == 409 and r.json()["codigo"] == "operador_requerido"
    assert not _inicio_marcado(ctx)


def test_operador_activo_queda_en_el_ciclo_y_la_bitacora(api):
    client, ctx, _ = api
    ana = ctx.db.crear_operador("Ana Pérez")
    r = client.post("/cycle/start", json={"operador_id": ana})
    assert r.status_code == 200, r.text
    assert ctx.estado.operador_inicio == "Ana Pérez" and _inicio_marcado(ctx)
    fila = _filas(ctx)[0]
    assert fila["usuario"] == "Ana Pérez" and fila["valor_nuevo"] == "Ana Pérez"
    assert fila["detalle"] == {"origen_operador": "lista", "operador": "Ana Pérez",
                               "programa": "prog1", "operador_id": ana}


def test_operador_inactivo_o_inexistente_422(api):
    client, ctx, _ = api
    ctx.db.crear_operador("Ana")
    beto = ctx.db.crear_operador("Beto")
    ctx.db.fijar_activo_operador(beto, False)
    for ident in (beto, 9999):
        r = client.post("/cycle/start", json={"operador_id": ident})
        assert r.status_code == 422 and r.json()["codigo"] == "operador_invalido"
    assert not _inicio_marcado(ctx)


@pytest.mark.parametrize("ident", ["1", True, 1.0, [1]])
def test_operador_id_mal_formado_422(api, ident):
    client, ctx, _ = api
    ctx.db.crear_operador("Ana")
    r = client.post("/cycle/start", json={"operador_id": ident})
    assert r.status_code == 422 and r.json()["codigo"] == "operador_invalido"
    assert not _inicio_marcado(ctx)


def test_con_sesion_rige_el_usuario_sin_preguntar(api):
    client, ctx, srv = api
    ana = ctx.db.crear_operador("Ana")
    r = client.post("/cycle/start", headers=cabecera(srv, "tecnico", "tec1"),
                    json={"operador_id": ana})
    assert r.status_code == 200 and ctx.estado.operador_inicio == "tec1"
    fila = _filas(ctx)[0]
    assert fila["usuario"] == "tec1" and fila["detalle"]["origen_operador"] == "sesion"
    assert "operador_id" not in fila["detalle"]


def test_lista_ilegible_falla_cerrada_503(api):
    client, ctx, _ = api
    ctx.db.listar_operadores = MagicMock(side_effect=RuntimeError("bd"))
    r = client.post("/cycle/start", json={"operador_id": 1})
    assert r.status_code == 503 and r.json()["codigo"] == "operador_no_verificable"
    assert not _inicio_marcado(ctx)


def test_sin_base_de_datos_no_pide_operador(api):
    client, ctx, _ = api
    ctx.sin_base_de_datos = True
    ctx.respaldo_ciclos.probar_escritura.return_value = None
    ctx.db.listar_operadores = MagicMock(side_effect=AssertionError("no se consulta"))
    r = client.post("/cycle/start", json={"confirmar_sin_registro": True})
    assert r.status_code == 200, r.text
    assert ctx.estado.operador_inicio == ""


def test_inicio_rechazado_por_otro_motivo_no_deja_operador(api):
    client, ctx, _ = api
    ana = ctx.db.crear_operador("Ana")
    ctx.estado.get_flag = lambda f: False          # no listo
    r = client.post("/cycle/start", json={"operador_id": ana})
    assert r.status_code == 409 and ctx.estado.operador_inicio == "" and _filas(ctx) == []


# ── códigos: ruta y texto ───────────────────────────────────────────────────

@pytest.mark.parametrize("codigo", ["operador_requerido", "operador_invalido",
                                    "operador_no_verificable"])
def test_codigos_con_ruta_y_texto_es_en(codigo):
    from autoclave.ui_qml import sesion_backend as sb
    assert codigo in sb.codigos_conocidos("/cycle/start")
    assert codigo not in sb.codigos_conocidos("/cycle/abort")
    clave = sb.clave_mensaje(codigo, "/cycle/start")
    assert clave.startswith("operador_ciclo.")
    for lang in ("es", "en"):
        d = json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["operador_ciclo"][clave.split(".", 1)[1]]
        assert d["bitacora"]["ev"]["ciclo_iniciado"] and d["bitacora"]["tipo"]["ciclo_iniciado"]


def test_codigos_emitidos_por_la_ruta_estan_registrados():
    import re
    fuente = (RAIZ / "src" / "autoclave" / "backend" / "rutas" / "ciclo.py").read_text(encoding="utf-8")
    emitidos = set(re.findall(r'^(OPERADOR_\w+) = "(\w+)"', fuente, re.M))
    from autoclave.ui_qml import sesion_backend as sb
    assert {v for _, v in emitidos} <= sb.codigos_conocidos("/cycle/start")
    assert len(emitidos) == 3


# ── cliente ─────────────────────────────────────────────────────────────────

def test_cliente_envia_operador_id_y_guarda_el_rechazo():
    import requests
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    SessionManager.logout()
    assert ui.start_cycle(operador_id=7) is True
    assert ui.backend.post.call_args.kwargs["body"] == {"operador_id": 7}
    assert ui.ultimo_rechazo_inicio() is None
    resp = MagicMock(status_code=409)
    resp.json.return_value = {"codigo": "operador_requerido", "detail": "x"}
    ui.backend.post.side_effect = requests.HTTPError(response=resp)
    assert ui.start_cycle() is False
    assert ui.ultimo_rechazo_inicio() == (409, {"codigo": "operador_requerido", "detail": "x"})


def test_cliente_operadores_activos_filtra_y_falla_cerrada():
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.get.return_value = {"operadores": [
        {"id": 1, "nombre": "Ana", "activo": True}, {"id": True, "nombre": "x"},
        {"id": 2, "nombre": "  "}, {"id": 3, "nombre": "Inactivo", "activo": False}]}
    assert ui.operadores_activos() == [{"id": 1, "nombre": "Ana"}]
    ui.backend.get.assert_called_with("/operadores?activos=true")
    ui.backend.get.side_effect = RuntimeError("red")
    assert ui.operadores_activos() is None
    ui.backend.get.side_effect = None
    ui.backend.get.return_value = {"otra": 1}
    assert ui.operadores_activos() is None


# ── controlador ─────────────────────────────────────────────────────────────

pyside = pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Puente:
    connected = True
    listoParaCiclo = True
    modoPrueba = False


class _UiFalsa:
    """start_cycle según una cola de respuestas: True o (estado, cuerpo)."""
    def __init__(self, respuestas, operadores=None):
        self.respuestas = list(respuestas)
        self.lista = operadores
        self.llamadas = []
        self._rechazo = None

    def start_cycle(self, **kw):
        self.llamadas.append(kw)
        r = self.respuestas.pop(0)
        self._rechazo = None if r is True else r
        return r is True

    def ultimo_rechazo_inicio(self):
        return self._rechazo

    def operadores_activos(self):
        return self.lista


def _cmd(ui):
    from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo
    return ComandoIniciarCiclo(_Puente(), ui, ejecutar=lambda t: t())


def _procesar():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()


_REQ = (409, {"codigo": "operador_requerido", "detail": "x"})
_INV = (422, {"codigo": "operador_invalido", "detail": "x"})
_OPS = [{"id": 1, "nombre": "Ana"}, {"id": 2, "nombre": "Beto"}]


def test_controlador_con_sesion_o_sin_activos_inicia_directo(qt_app):
    ui = _UiFalsa([True])
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    assert ui.llamadas == [{}] and c.eligiendoOperador is False


def test_controlador_abre_la_eleccion_y_reenvia_con_el_elegido(qt_app):
    ui = _UiFalsa([_REQ, True], _OPS)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    assert c.eligiendoOperador is True and c.operadores == _OPS and c.mensajeClave == ""
    c.iniciarConOperador(2)
    _procesar()
    assert ui.llamadas == [{}, {"operador_id": 2}]
    assert c.eligiendoOperador is False and c.ocupado is False


def test_controlador_cancelar_no_inicia(qt_app):
    ui = _UiFalsa([_REQ], _OPS)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    c.cancelarOperador()
    assert c.eligiendoOperador is False and ui.llamadas == [{}]
    c.iniciarConOperador(1)                       # sin elección abierta: nada
    assert ui.llamadas == [{}]


def test_controlador_elegir_es_obligatorio(qt_app):
    ui = _UiFalsa([_REQ], _OPS)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    c.iniciarConOperador(99)                      # fuera de la lista
    assert ui.llamadas == [{}] and c.mensajeClave == "operador_ciclo.err_requerido"


def test_controlador_operador_desactivado_entre_tanto(qt_app):
    ui = _UiFalsa([_REQ, _INV], _OPS)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    ui.lista = [_OPS[0]]
    c.iniciarConOperador(2)
    _procesar()
    assert c.eligiendoOperador is True and c.operadores == [_OPS[0]]
    assert c.mensajeClave == "operador_ciclo.err_invalido"


@pytest.mark.parametrize("lista", [None, []])
def test_controlador_sin_lista_no_inicia(qt_app, lista):
    ui = _UiFalsa([_REQ], lista)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    assert c.eligiendoOperador is True and c.operadores == []
    assert c.mensajeClave == "operador_ciclo.err_lista" and ui.llamadas == [{}]


def test_controlador_otro_rechazo_solo_se_registra(qt_app):
    ui = _UiFalsa([(409, {"codigo": "modo_prueba_activo", "detail": "x"})], _OPS)
    c = _cmd(ui)
    c.iniciar()
    _procesar()
    assert c.eligiendoOperador is False and c.mensajeClave == ""


# ── QML ─────────────────────────────────────────────────────────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import QtQuick.Window
import "Pantallas"
Window {
    width: 1196; height: 1917; visible: true
    QtObject { id: pf
        objectName: "puenteFalso"
        property bool connected: true
        property string machineState: "PREPARADO"
        property bool listoParaCiclo: true
        property bool inicioCicloVisible: true
        property bool modoPrueba: false
        property string estadoModuloEs: "ok"
    }
    QtObject { id: cc
        objectName: "comandoFalso"
        property bool ocupado: false
        property bool eligiendoOperador: false
        property var operadores: []
        property string mensajeClave: ""
        property var enviados: []
        property int cancelados: 0
        function iniciarConOperador(i) { enviados = enviados.concat([i]) }
        function cancelarOperador() { cancelados += 1; eligiendoOperador = false }
    }
    PantallaPreciclo { objectName: "pantallaPre"; anchors.fill: parent; puente: pf; comandoCiclo: cc }
}''', QUrl.fromLocalFile(qml_dir + "/prueba_t30_01.qml"))
win = c.create()
assert win is not None, c.errorString()
pre = win.findChild(QObject, "pantallaPre")
cc = win.findChild(QObject, "comandoFalso")
pf = win.findChild(QObject, "puenteFalso")
modal = pre.findChild(QObject, "modalOperador")
r = {"hay_modal": modal is not None, "cerrado": bool(modal.property("visible"))}
largo = "Operadora con un nombre muy largo que no cabe en una sola linea de la lista tactil"
cc.setProperty("operadores", [{"id": 1, "nombre": "Ana"}, {"id": 2, "nombre": largo}])
cc.setProperty("eligiendoOperador", True)
QTest.qWait(30)
r["abierto"] = bool(modal.property("visible"))
boton = modal.findChild(QObject, "botonIniciarOperador")
r["activo_sin_elegir"] = bool(boton.property("activo"))
from PySide6.QtQuick import QQuickItem
lista = modal.findChild(QQuickItem, "listaModalOperador")
filas = {i.objectName(): i for i in lista.property("contentItem").childItems()}
fila2 = filas["filaOperador_1"]
r["alto_fila_larga"] = float(fila2.property("height"))
fila1 = filas["filaOperador_0"]
r["alto_fila_corta"] = float(fila1.property("height"))
def tocar(item):
    p = item.mapToScene(QPointF(item.property("width") / 2, item.property("height") / 2))
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p.toPoint())
    QTest.qWait(20)
tocar(boton)                                 # sin elegir: nada
r["enviados_sin_elegir"] = list(cc.property("enviados").toVariant()) if hasattr(cc.property("enviados"), "toVariant") else list(cc.property("enviados"))
tocar(fila2)
r["elegido"] = int(modal.property("elegido"))
r["activo_elegido"] = bool(boton.property("activo"))
tocar(boton)
env = cc.property("enviados")
r["enviados"] = list(env.toVariant()) if hasattr(env, "toVariant") else list(env)
cc.setProperty("mensajeClave", "operador_ciclo.err_invalido")
QTest.qWait(20)
nota = modal.findChild(QObject, "textoNotaModalOperador")
r["nota"] = nota.property("text")
tocar(modal.findChild(QObject, "botonCancelarOperador"))
r["cancelados"] = int(cc.property("cancelados"))
r["cerrado_tras_cancelar"] = bool(modal.property("visible"))
cc.setProperty("eligiendoOperador", True)
pf.setProperty("inicioCicloVisible", False)
QTest.qWait(20)
r["cancelados_al_ocultar"] = int(cc.property("cancelados"))
r["visible_al_ocultar"] = bool(modal.property("visible"))
print(json.dumps({"avisos": avisos, **r}, ensure_ascii=True))
"""


@pytest.fixture(scope="module")
def qml():
    p = subprocess.run([sys.executable, "-c", _GUION, str(RAIZ_QML)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=RAIZ, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_qml_eleccion_de_operador(qml):
    assert qml["hay_modal"] and qml["cerrado"] is False and qml["abierto"] is True
    assert qml["activo_sin_elegir"] is False and qml["enviados_sin_elegir"] == []
    assert qml["elegido"] == 2 and qml["activo_elegido"] is True
    assert qml["enviados"] == [2]
    assert qml["nota"] and "operador" in qml["nota"].lower()
    assert qml["cancelados"] == 1 and qml["cerrado_tras_cancelar"] is False
    # el control de inicio desaparece con la elección abierta: se cancela
    assert qml["cancelados_al_ocultar"] == 2 and qml["visible_al_ocultar"] is False


def test_qml_nombre_largo_en_varias_lineas_sin_elide(qml):
    assert qml["alto_fila_larga"] > qml["alto_fila_corta"]
    texto = (RAIZ_QML / "Componentes" / "ModalOperador.qml").read_text(encoding="utf-8")
    assert not [l for l in texto.splitlines() if "elide" in l.split("//", 1)[0]]


def test_qml_sin_errores_de_referencia(qml):
    malos = [a for a in qml["avisos"] if "ReferenceError" in a or "TypeError" in a
             or "ModalOperador" in a]
    assert malos == [], malos


def test_qml_sin_colores_literales():
    import re
    texto = (RAIZ_QML / "Componentes" / "ModalOperador.qml").read_text(encoding="utf-8")
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b|Qt\.rgba|"(red|white|black|gray|grey)"', texto)
