"""AJ-01 (ajustes 28-oct): «Apagar equipo» no aparece en ningún momento de la
pantalla de ciclo (en curso ni en la espera de CONFIRMAR), ni en ninguna
pantalla con el equipo en CICLO o sin dato del estado (falla cerrada). Fuera
de ciclo sigue visible en Menú Principal y Preciclo de la ventana principal.
Si el ciclo arranca con el panel abierto, la zona y el diálogo se cierran."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Property, QCoreApplication, QObject, Signal

from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


# ── ComandosSistema.fueraDeCiclo ────────────────────────────────────────────

@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _PuenteFalso(QObject):
    machineStateChanged = Signal()
    seguridadChanged = Signal()

    def __init__(self, estado):
        super().__init__()
        self._estado = estado
        self.connected = True
        self.noAbrir = False

    def fijar(self, estado):
        self._estado = estado
        self.machineStateChanged.emit()

    @Property(str, notify=machineStateChanged)
    def machineState(self):
        return self._estado


def _comandos(estado):
    puente = _PuenteFalso(estado)
    ui = MagicMock()
    ui.apagar_equipo.return_value = (False, "x")
    return ComandosSistema(puente, ui, 1, ejecutar=lambda t: t()), puente, ui


@pytest.mark.parametrize("estado,esperado", [
    ("PREPARADO", True), ("PREPARACION", True), ("FALLA", True), ("INICIO", True),
    ("CICLO", False), ("DESCONOCIDO", False), ("", False),
])
def test_fuera_de_ciclo_por_estado(qt_app, estado, esperado):
    c, _, _ = _comandos(estado)
    assert c.fueraDeCiclo is esperado


def test_fuera_de_ciclo_sin_dato_del_puente_es_false(qt_app):
    puente = MagicMock()
    puente.machineState = None
    c = ComandosSistema(puente, MagicMock(), 1, ejecutar=lambda t: t())
    assert c.fueraDeCiclo is False


def test_fuera_de_ciclo_avisa_al_cambiar_el_estado(qt_app):
    c, puente, _ = _comandos("PREPARADO")
    avisos = []
    c.fueraDeCicloChanged.connect(lambda: avisos.append(c.fueraDeCiclo))
    puente.fijar("CICLO")
    assert avisos == [False]


def test_apagar_en_ciclo_no_envia_la_orden(qt_app):
    c, _, ui = _comandos("CICLO")
    c.apagarEquipo()
    ui.apagar_equipo.assert_not_called()


def test_apagar_fuera_de_ciclo_envia_la_orden(qt_app):
    c, _, ui = _comandos("PREPARADO")
    c.apagarEquipo()
    ui.apagar_equipo.assert_called_once_with("principal")


# ── QML: visibilidad en las pantallas ──────────────────────────────────────

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl, QMetaObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_aj01.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(200)

    def obj(nombre):
        return [o for o in ventana.findChildren(QObject) if o.objectName() == nombre][0]

    def hijo(padre, nombre):
        return [o for o in padre.findChildren(QQuickItem) if o.objectName() == nombre][0]

    sistema = obj("sistemaFalso")
    progreso = obj("progresoFalso")
    paneles = {"menu": "panelEquipoMenu", "preciclo": "panelEquipoPreciclo",
               "ciclo": "panelEquipoCiclo"}

    def ver(clave):
        p = obj(paneles[clave])
        QMetaObject.invokeMethod(p, "abrir")
        QTest.qWait(30)
        boton = hijo(p, "botonApagarEquipo")
        return {"puede": p.property("puedeApagar"), "boton": boton.isVisible()}

    r = {}
    for ventana_principal in (True, False):
        for fuera in (True, False):
            sistema.setProperty("ventanaPrincipal", ventana_principal)
            sistema.setProperty("fueraDeCiclo", fuera)
            for resultado in ("", "COMPLETADO", "FALLO", "CANCELADO"):
                progreso.setProperty("resultado", resultado)
                QTest.qWait(20)
                for clave in paneles:
                    r[f"{clave}|{ventana_principal}|{fuera}|{resultado}"] = ver(clave)

    # El ciclo arranca con el panel y el diálogo de apagar abiertos (Menú)
    sistema.setProperty("ventanaPrincipal", True)
    sistema.setProperty("fueraDeCiclo", True)
    p = obj("panelEquipoMenu")
    QMetaObject.invokeMethod(p, "abrir")
    dialogo = [o for o in p.findChildren(QObject) if o.objectName() == "confirmarApagar"][0]
    QMetaObject.invokeMethod(dialogo, "abrir")
    QTest.qWait(30)
    r["dialogo_antes"] = dialogo.property("visible")
    sistema.setProperty("fueraDeCiclo", False)
    QTest.qWait(30)
    r["dialogo_despues"] = dialogo.property("visible")
    r["zona_despues"] = hijo(p, "botonApagarEquipo").isVisible()
    r["apagados"] = sistema.property("apagados")
    print("RESULTADO=" + json.dumps(r))
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
        id: sistema
        objectName: "sistemaFalso"
        property bool ocupado: false
        property string mensaje: ""
        property string mensajeDespejar: ""
        property bool camaraNoSegura: false
        property bool apagadoRechazado: false
        property bool ventanaPrincipal: true
        property bool fueraDeCiclo: true
        property int apagados: 0
        function apagarEquipo() { apagados += 1 }
        function despejarAlarma(c) {}
        function descartarMensajeDespejar() { mensajeDespejar = "" }
    }
    QtObject { id: progresoFalso; objectName: "progresoFalso"; property string resultado: ""; property bool activo: true }
    QtObject {
        id: comandosFalsos
        property bool ocupado: false
        property string error: ""
        property string aviso: ""
        function cancelar() {}
        function confirmar() {}
        function descartarError() { error = "" }
        function descartarAviso() { aviso = "" }
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    MenuPrincipal { anchors.fill: parent; comandosSistema: sistema }
    PantallaPreciclo { anchors.fill: parent; comandosSistema: sistema }
    PantallaCicloEnCurso {
        anchors.fill: parent
        comandosSistema: sistema
        comandos: comandosFalsos
        progreso: progresoFalso
        datosVigentes: true
    }
}
"""


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
        timeout=120, cwd=RAIZ,
    )
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


_RESULTADOS = ("", "COMPLETADO", "FALLO", "CANCELADO")


@pytest.mark.parametrize("resultado", _RESULTADOS)
@pytest.mark.parametrize("fuera", [True, False])
def test_oculto_en_la_pantalla_de_ciclo(r, fuera, resultado):
    """En curso y en la espera de CONFIRMAR, aun en la ventana principal."""
    assert r[f"ciclo|True|{fuera}|{resultado}"] == {"puede": False, "boton": False}


@pytest.mark.parametrize("clave", ["menu", "preciclo", "ciclo"])
def test_oculto_con_el_equipo_en_ciclo_en_cualquier_pantalla(r, clave):
    for resultado in _RESULTADOS:
        assert r[f"{clave}|True|False|{resultado}"] == {"puede": False, "boton": False}


@pytest.mark.parametrize("clave", ["menu", "preciclo"])
def test_visible_fuera_de_ciclo_en_la_ventana_principal(r, clave):
    assert r[f"{clave}|True|True|"] == {"puede": True, "boton": True}


@pytest.mark.parametrize("clave", ["menu", "preciclo", "ciclo"])
def test_oculto_en_la_ventana_secundaria(r, clave):
    assert r[f"{clave}|False|True|"] == {"puede": False, "boton": False}


def test_el_ciclo_cierra_el_dialogo_de_apagar_abierto(r):
    assert r["dialogo_antes"] is True
    assert r["dialogo_despues"] is False
    assert r["zona_despues"] is False
    assert r["apagados"] == 0
