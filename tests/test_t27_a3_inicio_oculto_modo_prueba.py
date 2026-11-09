"""A3 (tanda 27): sin control de inicio de ciclo con el modo prueba activo.

- dominio: `pantalla_ciclo.inicio_ciclo_visible` (falla cerrada);
- puente: `UiBridge.inicioCicloVisible` sigue a `test_mode_active` de /status y
  vuelve al salir del modo prueba;
- comando: `ComandoIniciarCiclo` no envía POST /cycle/start con modo prueba;
- QML: PantallaPreciclo cargada de verdad (offscreen, subproceso) oculta el
  DeslizadorInicio (visible=false) con modo prueba y lo vuelve a mostrar; la
  fila «Modo prueba» de la tarjeta de alarmas sigue visible; fuente: el único
  DeslizadorInicio de las pantallas usa la propiedad del puente;
- backend: POST /cycle/start responde 409 `modo_prueba_activo` sin START_CICLO.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402

from autoclave.cliente.ui_service_backend import UIServiceBackend  # noqa: E402
from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo  # noqa: E402
from autoclave.ui_qml.bridge.ui_bridge import UiBridge  # noqa: E402
from autoclave.ui_qml.domain.pantalla_ciclo import inicio_ciclo_visible  # noqa: E402
from tests.test_backend_autenticacion import db, entorno  # noqa: F401,E402  (fixtures)

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── dominio ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("conectado,listo,prueba,estado,esperado", [
    (True, True, False, "PREPARADO", True),
    (True, True, True, "PREPARADO", False),      # A3: modo prueba lo oculta
    (True, True, None, "PREPARADO", False),      # sin dato: falla cerrada
    (True, True, 1, "PREPARADO", False),
    (True, True, False, "FALLA", False),
    (True, False, False, "PREPARADO", False),
    (False, True, False, "PREPARADO", False),
    (1, True, False, "PREPARADO", False),
    (True, 1, False, "PREPARADO", False),
])
def test_dominio_inicio_ciclo_visible(conectado, listo, prueba, estado, esperado):
    assert inicio_ciclo_visible(conectado, listo, prueba, estado) is esperado


# ── puente ──────────────────────────────────────────────────────────────────

def _servicio(campos, listo=True, estado="PREPARADO", connected=True):
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = connected
    ui.get_estado_global.return_value = estado
    ui.get_estado_flag.side_effect = lambda f: listo if f == "LISTO_PARA_CICLO" else False
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_cycle.return_value = {}
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
    return ui


def test_puente_oculta_con_modo_prueba_y_vuelve_al_salir():
    campos = {"test_mode_active": False}
    puente = UiBridge(_servicio(campos), door=2, iniciar=False)
    assert puente.inicioCicloVisible is False          # antes del primer refresco
    puente.refrescar()
    assert puente.inicioCicloVisible is True
    espia = QSignalSpy(puente.inicioCicloVisibleChanged)
    campos["test_mode_active"] = True
    puente.refrescar()
    assert puente.modoPrueba is True and puente.inicioCicloVisible is False
    assert espia.count() == 1
    puente.refrescar()                                  # sin cambio, sin señal
    assert espia.count() == 1
    campos["test_mode_active"] = False
    puente.refrescar()
    assert puente.inicioCicloVisible is True and espia.count() == 2


@pytest.mark.parametrize("kw", [{"listo": False}, {"estado": "FALLA"}, {"connected": False}])
def test_puente_oculto_sin_listo_en_falla_o_sin_conexion(kw):
    puente = UiBridge(_servicio({"test_mode_active": False}, **kw), door=1, iniciar=False)
    puente.refrescar()
    assert puente.inicioCicloVisible is False


# ── comando ─────────────────────────────────────────────────────────────────

class _Puente:
    def __init__(self, prueba):
        self.connected = True
        self.listoParaCiclo = True
        self.modoPrueba = prueba


@pytest.mark.parametrize("sin_registro", [False, True])
def test_comando_no_envia_con_modo_prueba(sin_registro):
    ui = MagicMock()
    cmd = ComandoIniciarCiclo(_Puente(True), ui, ejecutar=lambda t: t())
    (cmd.iniciarSinRegistro if sin_registro else cmd.iniciar)()
    ui.start_cycle.assert_not_called()
    assert cmd.ocupado is False


def test_comando_envia_sin_modo_prueba():
    ui = MagicMock()
    ui.start_cycle.return_value = True
    ComandoIniciarCiclo(_Puente(False), ui, ejecutar=lambda t: t()).iniciar()
    ui.start_cycle.assert_called_once_with()


# ── QML ─────────────────────────────────────────────────────────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
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
import "Pantallas"
Item {
    width: 1196; height: 1917
    QtObject { id: pf
        objectName: "puenteFalso"
        property bool connected: true
        property string machineState: "PREPARADO"
        property bool listoParaCiclo: true
        property bool inicioCicloVisible: true
        property bool modoPrueba: false
        property bool noAbrir: false
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property string estadoModuloEs: "ok"
    }
    PantallaPreciclo { objectName: "pantallaPre"; anchors.fill: parent; puente: pf }
}''', QUrl.fromLocalFile(qml_dir + "/prueba_t27_a3.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
pre = raiz.findChild(QObject, "pantallaPre")
pf = raiz.findChild(QObject, "puenteFalso")
desl = pre.findChild(QObject, "deslizadorIniciarCiclo")
modal = pre.findChild(QObject, "confirmarSinRegistro")
fila = pre.findChild(QObject, "filaModoPrueba")
r = {"hay_deslizador": desl is not None}
def estado(nombre):
    QTest.qWait(5)
    r[nombre] = {"visible": bool(desl.property("visible")),
                 "modal": bool(modal.property("visible")),
                 "fila_modo_prueba": (bool(fila.property("visible")) if fila is not None else None)}
estado("normal")
modal.setProperty("visible", True)
pf.setProperty("modoPrueba", True)
pf.setProperty("inicioCicloVisible", False)   # lo que publica UiBridge con test_mode_active
estado("prueba")
pf.setProperty("modoPrueba", False)
pf.setProperty("inicioCicloVisible", True)
estado("salida")
print(json.dumps({"avisos": avisos, **r}))
"""


@pytest.fixture(scope="module")
def qml():
    p = subprocess.run([sys.executable, "-c", _GUION, str(RAIZ_QML)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=RAIZ, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_qml_deslizador_desaparece_con_modo_prueba_y_vuelve(qml):
    assert qml["hay_deslizador"]
    assert qml["normal"]["visible"] is True
    assert qml["prueba"]["visible"] is False
    assert qml["prueba"]["modal"] is False      # la confirmación sin registro se cierra
    assert qml["salida"]["visible"] is True
    # la fila «Modo prueba» explica la ausencia del control
    assert qml["normal"]["fila_modo_prueba"] is False
    assert qml["prueba"]["fila_modo_prueba"] is True
    assert qml["salida"]["fila_modo_prueba"] is False


def test_qml_carga_sin_errores_de_referencia(qml):
    malos = [a for a in qml["avisos"] if "ReferenceError" in a or "TypeError" in a]
    assert malos == []


def test_fuente_el_unico_deslizador_de_inicio_depende_del_puente():
    usos = []
    for f in RAIZ_QML.rglob("*.qml"):
        if f.name == "DeslizadorInicio.qml":
            continue
        codigo = "\n".join(l.split("//", 1)[0] for l in f.read_text(encoding="utf-8").splitlines())
        if re.search(r"\bDeslizadorInicio\s*\{", codigo):
            usos.append(f.relative_to(RAIZ_QML).as_posix())
    # CAN-02 (tanda 34): Ciclo en curso lo usa para CANCELAR (variante "cancelar"),
    # que no inicia ciclos; el único deslizador de inicio sigue en Preciclo
    assert sorted(usos) == ["Pantallas/PantallaCicloEnCurso.qml", "Pantallas/PantallaPreciclo.qml"], usos
    ciclo = (RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(encoding="utf-8")
    m_c = re.search(r"DeslizadorInicio\s*\{(.*?)\n        \}", ciclo, re.S)
    assert m_c and 'variante: "cancelar"' in m_c.group(1)
    assert "iniciarCiclo" not in m_c.group(1)
    codigo = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    m = re.search(r"DeslizadorInicio\s*\{(.*?)\n    \}", codigo, re.S)
    assert m
    vis = re.search(r"^\s*visible:\s*(.+)$", m.group(1), re.M).group(1)
    assert "raiz.inicioCicloVisible" in vis
    assert "puente?.inicioCicloVisible ?? false" in codigo


# ── backend ─────────────────────────────────────────────────────────────────

def test_backend_rechaza_inicio_con_modo_prueba(entorno):  # noqa: F811
    client, ctx, _ = entorno
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    r = client.post("/cycle/start")
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == "modo_prueba_activo"
    assert ("START_CICLO", True) not in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_backend_sin_modo_prueba_no_rechaza_por_modo_prueba(entorno):  # noqa: F811
    client, ctx, _ = entorno
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    r = client.post("/cycle/start")
    assert r.status_code == 200 or r.json().get("codigo") != "modo_prueba_activo", r.text
