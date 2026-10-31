"""D8-2.15 (tanda 8, Q1-P6): la QML muestra, con textos del catálogo i18n, la
"cancelación en espera" (/cycle/abort aceptado con `pendiente`) y el motivo del
rechazo de DESPEJAR, en lugar del texto de la excepción HTTP."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.cliente.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso
from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
I18N = RAIZ / "src" / "autoclave" / "i18n"

_EN_ESPERA = {"ok": True, "action": "CICLO_CANCELADO", "pendiente": True,
              "codigo": "cancelacion_en_espera_datos", "mensaje": "texto del backend"}


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _cliente():
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    return ui


def _http_error(status):
    respuesta = MagicMock()
    respuesta.status_code = status
    return requests.HTTPError(f"{status} Client Error: Conflict for url: http://x", response=respuesta)


# ── cliente HTTP ────────────────────────────────────────────────────────────

def test_abort_cycle_devuelve_la_respuesta_veraz():
    ui = _cliente()
    ui.backend.post.return_value = dict(_EN_ESPERA)
    r = ui.abort_cycle()
    assert r and r.get("pendiente") is True
    ui.backend.post.return_value = {"ok": True, "action": "CICLO_CANCELADO"}
    assert ui.abort_cycle()
    ui.backend.post.side_effect = _http_error(409)
    assert ui.abort_cycle() is False


@pytest.mark.parametrize("error, clave", [
    (_http_error(409), "notificaciones.despejar_sin_enlace"),
    (_http_error(404), "notificaciones.despejar_no_activa"),
    (_http_error(422), "notificaciones.despejar_rechazado"),
    (requests.ConnectionError("sin red"), "notificaciones.despejar_sin_respuesta"),
])
def test_reconocer_alarma_devuelve_clave_del_catalogo(error, clave):
    ui = _cliente()
    ui.backend.post.side_effect = error
    ok, motivo = ui.reconocer_alarma("COM-02|X", "operador")
    assert ok is False and motivo == clave


def test_las_claves_estan_en_es_y_en():
    claves = ("despejar_sin_enlace", "despejar_no_activa", "despejar_rechazado",
              "despejar_sin_respuesta")
    for idioma in ("es", "en"):
        cat = json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))
        for c in claves:
            assert cat["notificaciones"][c].strip(), (idioma, c)
        assert cat["ciclo"]["cancelacion_en_espera_datos"].strip()


# ── puentes ─────────────────────────────────────────────────────────────────

class _Puente:
    connected = True


def _puente_sistema():
    p = MagicMock()
    p.connected = True
    return p


def test_cancelar_en_espera_deja_el_aviso_del_catalogo():
    ui = MagicMock(spec=UIServiceBackend)
    ui.abort_cycle.return_value = dict(_EN_ESPERA)
    c = ComandosCicloEnCurso(_Puente(), ui, ejecutar=lambda t: t())
    terminados = []
    c.terminado.connect(lambda a, ok: terminados.append((a, ok)))
    c.cancelar()
    QCoreApplication.processEvents()
    assert terminados == [("cancelar", True)]
    assert c.error == ""
    assert c.aviso == "ciclo.cancelacion_en_espera_datos"
    c.descartarAviso()
    assert c.aviso == ""


def test_cancelar_normal_sin_aviso():
    ui = MagicMock(spec=UIServiceBackend)
    ui.abort_cycle.return_value = {"ok": True, "action": "CICLO_CANCELADO"}
    c = ComandosCicloEnCurso(_Puente(), ui, ejecutar=lambda t: t())
    c.cancelar()
    QCoreApplication.processEvents()
    assert c.aviso == "" and c.error == ""
    ui.abort_cycle.return_value = True          # dobles antiguos (bool)
    c.cancelar()
    QCoreApplication.processEvents()
    assert c.aviso == "" and c.error == ""


def test_despejar_rechazado_va_a_su_propio_mensaje_no_al_de_apagar():
    ui = MagicMock()
    ui.reconocer_alarma.return_value = (False, "notificaciones.despejar_sin_enlace")
    c = ComandosSistema(_puente_sistema(), ui, 1, ejecutar=lambda t: t())
    c.despejarAlarma("COM-02|X")
    QCoreApplication.processEvents()
    assert c.mensajeDespejar == "notificaciones.despejar_sin_enlace"
    assert c.mensaje == ""                      # no sale como "apagado rechazado"
    assert c.ocupado is False
    ui.reconocer_alarma.return_value = (True, "")
    c.despejarAlarma("COM-02|X")
    QCoreApplication.processEvents()
    assert c.mensajeDespejar == ""


def test_motivo_desconocido_no_se_muestra_crudo():
    """Un motivo que no es una clave del catálogo (texto de excepción) se
    sustituye por el genérico del catálogo."""
    ui = MagicMock()
    ui.reconocer_alarma.return_value = (False, "409 Client Error: Conflict for url")
    c = ComandosSistema(_puente_sistema(), ui, 1, ejecutar=lambda t: t())
    c.despejarAlarma("COM-02|X")
    QCoreApplication.processEvents()
    assert c.mensajeDespejar == "notificaciones.despejar_rechazado"
    c.descartarMensajeDespejar()
    assert c.mensajeDespejar == ""


# ── QML ─────────────────────────────────────────────────────────────────────

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n

    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_d8_2_15.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(200)
    hijos = lambda: ventana.findChildren(QObject)
    comandos = [o for o in hijos() if o.objectName() == "comandosFalsos"][0]
    sistema = [o for o in hijos() if o.objectName() == "sistemaFalso"][0]

    def textos_visibles():
        out = []
        for o in ventana.findChildren(QQuickItem):
            if o.metaObject().className() == "QQuickText" and o.isVisible():
                out.append(o.property("text"))
        return out

    def aviso():
        return [o for o in hijos() if o.metaObject().className().startswith("PanelModal_QML")
                and o.property("objectName") == "avisoComando"][0]

    r = {}
    esperado = i18n.t("ciclo.cancelacion_en_espera_datos")
    comandos.setProperty("aviso", "ciclo.cancelacion_en_espera_datos")
    QTest.qWait(80)
    r["aviso_abre"] = aviso().property("visible")
    r["aviso_texto"] = esperado in textos_visibles()
    aviso().setProperty("visible", False)
    QTest.qWait(50)
    r["aviso_descartado"] = comandos.property("aviso")

    panel = [o for o in hijos() if o.objectName() == "panelNotificaciones"][0]
    panel.setProperty("visible", True)
    sistema.setProperty("mensajeDespejar", "notificaciones.despejar_sin_enlace")
    QTest.qWait(80)
    r["despejar_texto"] = i18n.t("notificaciones.despejar_sin_enlace") in textos_visibles()
    panel.setProperty("visible", False)
    QTest.qWait(50)
    r["despejar_descartado"] = sistema.property("mensajeDespejar")
    r["avisos"] = avisos
    print(json.dumps(r))
""")

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        objectName: "comandosFalsos"
        property bool ocupado: false
        property string error: ""
        property string aviso: ""
        function cancelar() {}
        function confirmar() {}
        function descartarError() { error = "" }
        function descartarAviso() { aviso = "" }
    }
    QtObject {
        id: sistema
        objectName: "sistemaFalso"
        property bool ocupado: false
        property string mensaje: ""
        property string mensajeDespejar: ""
        property bool camaraNoSegura: false
        property bool ventanaPrincipal: true
        function descartarMensajeDespejar() { mensajeDespejar = "" }
        function despejarAlarma(c) {}
    }
    QtObject { id: progresoFalso; property string resultado: ""; property bool activo: false }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        datosVigentes: true
    }
    PanelNotificaciones {
        objectName: "panelNotificaciones"
        comandosSistema: sistema
    }
}
"""


def test_qml_muestra_los_textos_del_catalogo():
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["aviso_abre"] is True
    assert s["aviso_texto"] is True
    assert s["aviso_descartado"] == ""
    assert s["despejar_texto"] is True
    assert s["despejar_descartado"] == ""
    assert s["avisos"] == []
