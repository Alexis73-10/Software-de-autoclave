"""RCB-01/02/09: borrador de la carga (dos pasos, suma por lectura, «−1»,
límites, cambiar lote, vaciar), puente de la ventana, envío con el inicio
(se limpia al aceptar, se conserva con 409/422) y QML: VentanaCarga capta
lecturas del lector (teclado + Enter) solo con la ventana abierta; el botón
«Carga» solo en la pantalla de carga (HAZ-RCB-01, HAZ-RCB-03)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import registro_carga as rc
from autoclave.ui_qml.domain import registro_carga as dom

pytestmark = pytest.mark.req("REQ-115")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


# ── borrador (dominio) ──────────────────────────────────────────────────────

def _borrador(catalogo=None):
    b = dom.BorradorCarga()
    b.fijar_catalogo([{"codigo": c, "nombre": n, "activo": True}
                      for c, n in (catalogo or {"A1": "Pinza", "B2": "Tijera"}).items()])
    return b


def test_dos_pasos_lote_y_elementos():
    b = _borrador()
    assert b.paso == dom.PASO_LOTE
    tipo, clave, _ = b.leer("A1")                       # elemento del catálogo
    assert tipo == dom.AVISO_ERROR and clave.endswith("aviso_es_elemento") and b.lote == ""
    assert b.leer("  LT-1 ")[0] == dom.AVISO_OK and b.lote == "LT-1"
    assert b.paso == dom.PASO_ELEMENTOS
    b.leer("A1"); b.leer("A1"); b.leer("ZZ")
    assert [(e["codigo"], e["cantidad"]) for e in b.elementos] == [("A1", 2), ("ZZ", 1)]
    filas = b.filas()
    assert filas[0]["nombre"] == "Pinza" and filas[0]["enCatalogo"]
    assert filas[1]["enCatalogo"] is False and filas[1]["ultimo"] is True
    assert b.leer("LT-1")[1].endswith("aviso_es_lote")  # el lote no se suma como elemento


def test_menos_uno_cambiar_lote_y_vaciar():
    b = _borrador()
    b.leer("L"); b.leer("A1"); b.leer("A1"); b.leer("B2")
    b.quitar_uno("A1")
    assert [(e["codigo"], e["cantidad"]) for e in b.elementos] == [("A1", 1), ("B2", 1)]
    b.quitar_uno("A1")
    assert [e["codigo"] for e in b.elementos] == ["B2"]           # con 1, la fila desaparece
    b.cambiar_lote()
    assert b.lote == "" and b.paso == dom.PASO_LOTE and len(b.elementos) == 1
    b.vaciar()
    assert b.vacio() and b.para_inicio() is None


def test_lectura_invalida_y_manual():
    b = _borrador()
    for malo in ("", "   ", "a|b", "ñ", "x" * 65):
        assert b.leer(malo)[1].endswith("aviso_lectura_invalida")
    assert b.vacio()
    b.leer("L")
    b.leer("C9", manual=True)
    assert b.elementos[0]["manual"] is True
    assert b.para_inicio() == {"lote": "L", "elementos": [
        {"codigo": "C9", "cantidad": 1, "manual": True}]}


def test_limites():
    b = _borrador({})
    b.leer("L")
    for i in range(rc.MAX_CODIGOS):
        b.leer(f"C{i}")
    assert b.leer("OTRO")[1].endswith("aviso_max_codigos") and len(b.elementos) == rc.MAX_CODIGOS
    b2 = _borrador({})
    b2.leer("L")
    for _ in range(rc.MAX_CANTIDAD):
        b2.leer("X")
    assert b2.leer("X")[1].endswith("aviso_max_cantidad") and b2.elementos[0]["cantidad"] == 999


def test_elementos_sin_lote_se_envian_y_el_backend_decide():
    b = _borrador()
    b.leer("L"); b.leer("A1"); b.cambiar_lote()
    assert b.para_inicio() == {"lote": "", "elementos": [
        {"codigo": "A1", "cantidad": 1, "manual": False}]}
    with pytest.raises(rc.CargaInvalida):
        rc.validar_carga(b.para_inicio())


def test_resumen_y_requerida():
    b = _borrador()
    t = lambda clave, **p: f"{clave}:{p}"
    assert dom.resumen_boton(b, t).startswith("registro_carga.resumen_sin")
    b.leer("LT"); b.leer("A1"); b.leer("A1")
    assert dom.resumen_boton(b, t) == "registro_carga.resumen:{'lote': 'LT', 'n': 2}"
    exige = {"globals": {"registro_carga_obligatorio": {"value": True}}}
    assert dom.carga_requerida_falta(exige, dom.BorradorCarga()) is True
    assert dom.carga_requerida_falta(exige, b) is False
    assert dom.carga_requerida_falta({}, dom.BorradorCarga()) is False


# ── puente y envío con el inicio ────────────────────────────────────────────

@pytest.fixture
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def test_puente_lee_catalogo_y_requerida(qt):
    from autoclave.ui_qml.bridge.registro_carga_qml import RegistroCarga
    backend = MagicMock()
    backend.get.return_value = {"elementos": [{"codigo": "A1", "nombre": "Pinza", "activo": True}]}
    ui = MagicMock()
    ui.get_cycle.return_value = {"parameters": {"globals": {
        "registro_carga_obligatorio": {"value": True, "type": "bool"}}}}
    r = RegistroCarga(backend, ui, ejecutar=lambda t: t())
    r.revisarRequerida()
    assert r.requerida is True
    r.actualizarCatalogo()
    backend.get.assert_called_with("/carga/catalogo", params={"activos": "true"})
    r.leer("LT")
    r.leer("A1")
    assert r.lote == "LT" and r.filas[0]["nombre"] == "Pinza" and r.avisoTipo == "ok"
    assert r.requerida is False and r.totalUnidades == 1
    r.leer("a|b")
    assert r.avisoTipo == "error" and r.totalUnidades == 1
    r.limpiar()
    assert r.vacio and r.requerida is True


class _Puente:
    connected = True
    listoParaCiclo = True
    modoPrueba = False


def _comando(ui, registro):
    from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo
    return ComandoIniciarCiclo(_Puente(), ui, ejecutar=lambda t: t(), registro_carga=registro)


def test_inicio_envia_la_carga_y_limpia_al_aceptar(qt):
    from autoclave.ui_qml.bridge.registro_carga_qml import RegistroCarga
    r = RegistroCarga(None, None)
    r.leer("LT"); r.leer("A1")
    ui = MagicMock()
    ui.start_cycle.return_value = True
    c = _comando(ui, r)
    c.iniciar()
    ui.start_cycle.assert_called_once_with(carga={"lote": "LT", "elementos": [
        {"codigo": "A1", "cantidad": 1, "manual": False}]})
    assert r.vacio and c.mensajeCargaClave == ""


@pytest.mark.parametrize("estado,codigo,clave", [
    (409, "carga_requerida", "registro_carga.err_requerida"),
    (422, "carga_invalida", "registro_carga.err_invalida")])
def test_rechazo_por_la_carga_conserva_el_borrador(qt, estado, codigo, clave):
    from autoclave.ui_qml.bridge.registro_carga_qml import RegistroCarga
    r = RegistroCarga(None, None)
    r.leer("LT"); r.leer("A1")
    ui = MagicMock()
    ui.start_cycle.return_value = False
    ui.ultimo_rechazo_inicio.return_value = (estado, {"codigo": codigo, "detail": "x"})
    c = _comando(ui, r)
    c.iniciar()
    assert not r.vacio and r.lote == "LT"
    assert c.mensajeCargaClave == clave
    c.limpiarMensajeCarga()
    assert c.mensajeCargaClave == ""


def test_sin_borrador_el_inicio_es_como_antes(qt):
    ui = MagicMock()
    ui.start_cycle.return_value = True
    _comando(ui, None).iniciar()
    ui.start_cycle.assert_called_once_with()


def test_cliente_pone_la_carga_en_el_cuerpo():
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    assert ui.start_cycle(carga={"lote": "L", "elementos": []}) is True
    assert ui.backend.post.call_args.kwargs["body"] == {"carga": {"lote": "L", "elementos": []}}


# ── QML ─────────────────────────────────────────────────────────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml.bridge.registro_carga_qml import RegistroCarga
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
registro = RegistroCarga(None, None)
registro.setObjectName("registro")
e.rootContext().setContextProperty("registroPy", registro)
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import QtQuick.Window
import "Pantallas"
Window {
    width: 1196; height: 1917; visible: true
    QtObject { id: pf
        property bool connected: true
        property string machineState: "PREPARADO"
        property bool listoParaCiclo: true
        property bool inicioCicloVisible: true
        property bool modoPrueba: false
        property string estadoModuloEs: "ok"
        signal datosCicloChanged()
    }
    QtObject { id: cc
        property bool ocupado: false
        property bool eligiendoOperador: false
        property var operadores: []
        property string mensajeClave: ""
        property string mensajeCargaClave: ""
        function limpiarMensajeCarga() { mensajeCargaClave = "" }
    }
    Item {
        anchors.fill: parent
        PantallaPreciclo { objectName: "conCarga"; anchors.fill: parent; puente: pf; comandoCiclo: cc
                           registroCarga: registroPy }
    }
    PantallaPreciclo { objectName: "sinCarga"; visible: false; width: 1196; height: 1917; puente: pf; comandoCiclo: cc }
}''', QUrl.fromLocalFile(qml_dir + "/prueba_rcb_ventana.qml"))
win = c.create()
assert win is not None, c.errorString()
from PySide6.QtCore import QEvent
from PySide6.QtGui import QKeyEvent
def teclear(texto):
    # como un lector HID: una tecla por carácter y Enter al final
    for ch in texto:
        clave = ord(ch.upper()) if ch.isalnum() else (Qt.Key_Minus if ch == "-" else 0)
        for tipo in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(win, QKeyEvent(tipo, clave, Qt.NoModifier, ch))
    for tipo in (QEvent.KeyPress, QEvent.KeyRelease):
        QGuiApplication.sendEvent(win, QKeyEvent(tipo, Qt.Key_Return, Qt.NoModifier, chr(13)))
    QTest.qWait(20)
con = win.findChild(QObject, "conCarga")
sin = win.findChild(QObject, "sinCarga")
r = {}
r["boton_con"] = bool(con.findChild(QObject, "botonCargaPreciclo").property("visible"))
r["boton_sin"] = bool(sin.findChild(QObject, "botonCargaPreciclo").property("visible"))
win.requestActivate()
QTest.qWait(50)
# sin ventana abierta: lo que se teclea no se interpreta
teclear("LOTEFUERA")
r["lote_sin_ventana"] = registro.property("lote")
ventana = con.findChild(QObject, "ventanaCargaPreciclo")
ventana.metaObject().invokeMethod(ventana, "abrir")
QTest.qWait(400)
r["abierta"] = bool(ventana.property("abierta"))
captura = ventana.findChild(QObject, "capturaLector")
r["foco"] = bool(captura.property("activeFocus"))
for texto in ("LT-77", "A1", "A1", "B2"):
    teclear(texto)
r["lote"] = registro.property("lote")
r["filas"] = [(f["codigo"], f["cantidad"]) for f in registro.property("filas")]
r["aviso"] = registro.property("aviso")
lista = ventana.findChild(QObject, "listaCarga")
r["filas_qml"] = int(lista.property("count"))
ventana.metaObject().invokeMethod(ventana, "cerrar")
QTest.qWait(400)
teclear("B2")
r["filas_tras_cerrar"] = [(f["codigo"], f["cantidad"]) for f in registro.property("filas")]
r["resumen_boton"] = con.findChild(QObject, "resumenCargaPreciclo").property("text")
print(json.dumps({"avisos": avisos, **r}, ensure_ascii=True))
"""


@pytest.fixture(scope="module")
def qml():
    p = subprocess.run([sys.executable, "-c", _GUION, str(RAIZ_QML)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=RAIZ, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_qml_boton_solo_en_la_pantalla_de_carga(qml):
    assert qml["boton_con"] is True and qml["boton_sin"] is False


def test_qml_captura_solo_con_la_ventana_abierta(qml):
    assert qml["lote_sin_ventana"] == ""
    assert qml["abierta"] is True and qml["foco"] is True
    assert qml["lote"] == "LT-77"
    assert qml["filas"] == [["A1", 2], ["B2", 1]]
    assert qml["filas_qml"] == 2
    assert qml["filas_tras_cerrar"] == [["A1", 2], ["B2", 1]]      # cerrada: no se lee
    assert "LT-77" in qml["resumen_boton"]


def test_qml_sin_errores_de_referencia(qml):
    malos = [a for a in qml["avisos"] if "ReferenceError" in a or "TypeError" in a
             or "VentanaCarga" in a or "registro" in a.lower()]
    assert malos == []


def test_qml_sin_colores_literales_ni_elide():
    import re
    for nombre in ("Componentes/VentanaCarga.qml",):
        texto = (RAIZ_QML / nombre).read_text(encoding="utf-8")
        codigo = "\n".join(l.split("//")[0] for l in texto.splitlines())
        assert not re.search(r'"#[0-9A-Fa-f]{3,8}"|Qt\.rgba|elide', codigo), nombre


def test_sin_respuesta_del_inicio_el_borrador_se_vacia_al_entrar_en_ciclo(qt):
    # HAZ-RCB-01, revisión SAF-01: el POST vence (False sin código) pero el
    # backend ya arrancó el ciclo con la carga; al verse CICLO el borrador se
    # vacía y no pasa al ciclo siguiente
    from autoclave.ui_qml.bridge.registro_carga_qml import RegistroCarga
    r = RegistroCarga(None, None)
    r.seguir_estado("PREPARADO")
    r.leer("LT"); r.leer("A1")
    ui = MagicMock()
    ui.start_cycle.return_value = False
    ui.ultimo_rechazo_inicio.return_value = None
    c = _comando(ui, r)
    c.iniciar()
    assert not r.vacio                      # sin respuesta: aún se conserva
    r.seguir_estado("CICLO")
    assert r.vacio
    # lo leído durante el ciclo queda para el próximo
    r.leer("LT2")
    r.seguir_estado("CICLO")
    assert r.lote == "LT2"
    r.seguir_estado("PREPARADO")
    assert r.lote == "LT2"


def test_app_conecta_el_estado_de_la_maquina_al_borrador():
    from pathlib import Path
    fuente = Path(__file__).resolve().parents[1].joinpath(
        "src", "autoclave", "ui_qml", "app.py").read_text(encoding="utf-8")
    assert "registro_carga.seguir_estado(puente.machineState)" in fuente
