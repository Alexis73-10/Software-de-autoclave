"""U1 (tanda 2): los avisos de seguridad de E5 (paro, estado seguro, NO ABRIR,
modo prueba) están en el panel de la campana (PanelNotificaciones ›
SeccionEstadoSeguro), no en una franja superior. Mockup aprobado:
docs/mis_plans/mockup_estado_seguro.png (3 estados)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML = """
import QtQuick
import "Componentes"
Item {
    width: 600; height: 960
    property alias panel: pn
    QtObject {
        id: puenteFalso
        property bool noAbrir: false
        property string noAbrirMotivo: ""
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool modoPrueba: false
        property bool connected: true
    }
    QtObject {
        id: comandosFalsos
        property bool ocupado: false
        property string mensaje: ""
        property int confirmaciones: 0
        function confirmarEstadoSeguro() { confirmaciones += 1 }
    }
    ListModel { id: alarmasFalsas }
    property alias puente: puenteFalso
    property alias comandos: comandosFalsos
    property int alarmasAgregadas: 0
    onAlarmasAgregadasChanged: alarmasFalsas.append({id: "X", description: "x", priority: "baja"})
    PanelNotificaciones {
        id: pn
        objectName: "panelPrueba"
        alarmas: alarmasFalsas
        puente: puenteFalso
        comandosSistema: comandosFalsos
    }
}
"""

_SCRIPT = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
qml_dir, qml = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_avisos.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()
panel = raiz.findChild(QObject, "panelPrueba")
puente = raiz.property("puente")
comandos = raiz.property("comandos")

def obj(nombre):
    return raiz.findChild(QObject, nombre)

def visible(nombre):
    return bool(obj(nombre).property("visible"))

def p(nombre):
    return panel.property(nombre)

r = {}
r["sin_avisos_cerrado"] = (not p("visible") and p("conteoTotal") == 0
                           and not visible("filaParo") and not visible("botonConfirmarEstadoSeguro"))

# 1. paro activo: fila alta, sin botón; el panel se abre solo; insignia roja sin parpadeo
puente.setProperty("paroActivo", True)
r["1_abre_solo"] = bool(p("visible"))
r["1_fila_paro"] = visible("filaParo")
r["1_sin_boton"] = not visible("botonConfirmarEstadoSeguro")
r["1_insignia"] = p("conteoTotal") == 1 and p("urgente") and not p("parpadeo")
r["1_sin_no_abrir_duplicado"] = not visible("filaNoAbrir")

# el panel no se puede cerrar mientras dura el paro (revisión U1, SAF-01)
from PySide6.QtCore import QMetaObject
QMetaObject.invokeMethod(panel, "cerrar")
r["1_no_se_cierra"] = bool(p("visible")) and bool(p("bloqueado"))

# 2. paro liberado: aviso naranja y botón azul habilitado; insignia parpadeando
puente.setProperty("paroActivo", False)
puente.setProperty("estadoSeguroActivo", True)
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
r["2_abre_solo"] = bool(p("visible"))
r["2_fila"] = visible("filaEstadoSeguroPendiente") and not visible("filaParo")
r["2_aviso_naranja"] = visible("avisoParoLiberado")
boton = obj("botonConfirmarEstadoSeguro")
r["2_boton_habilitado"] = visible("botonConfirmarEstadoSeguro") and bool(boton.property("habilitado"))
r["2_parpadeo"] = p("urgente") and p("parpadeo")
r["2_sin_indicador"] = not visible("indicadorEnCurso")
# la petición en vuelo deshabilita el botón y muestra "En curso…"
comandos.setProperty("ocupado", True)
r["2_enviando_deshabilita"] = not bool(boton.property("habilitado")) and visible("indicadorEnCurso")
comandos.setProperty("ocupado", False)
comandos.setProperty("mensaje", "Sin conexión")
r["2_mensaje_rechazo"] = visible("mensajeConfirmar")
comandos.setProperty("mensaje", "")

# 3. en curso: el panel ya se puede cerrar: botón deshabilitado con indicador y nota NO ABRIR; insignia amarilla
puente.setProperty("estadoSeguroRequiereConfirmacion", False)
r["3_fila"] = visible("filaEstadoSeguroEnCurso") and not visible("filaEstadoSeguroPendiente")
r["3_boton_deshabilitado"] = visible("botonConfirmarEstadoSeguro") and not bool(boton.property("habilitado"))
r["3_indicador"] = visible("indicadorEnCurso") and visible("notaNoAbrirEnCurso")
r["3_insignia"] = p("avisoEnCurso") and not p("urgente") and not p("parpadeo")
r["3_se_cierra"] = not bool(p("bloqueado"))
puente.setProperty("estadoSeguroActivo", False)

# sin conexión: estado de seguridad desconocido, contado y sin bloquear
puente.setProperty("connected", False)
r["sin_conexion"] = visible("filaSeguridadDesconocida") and p("conteoTotal") == 1 and not p("bloqueado")
puente.setProperty("connected", True)

# NO ABRIR (cámara no segura) y modo prueba como filas, contadas en la insignia
puente.setProperty("noAbrir", True)
puente.setProperty("noAbrirMotivo", "Temperatura demasiado alta (95 °C)")
r["no_abrir"] = visible("filaNoAbrir") and "95" in obj("filaNoAbrir").property("descripcion")
puente.setProperty("modoPrueba", True)
r["modo_prueba"] = visible("filaModoPrueba") and p("conteoTotal") == 2 and not p("urgente")
raiz.setProperty("alarmasAgregadas", 1)
r["suma_alarmas"] = p("conteoTotal") == 3 and p("conteo") == 1

r["avisos"] = avisos
r["confirmaciones"] = comandos.property("confirmaciones")
print(json.dumps(r))
"""


def _correr(script, qml):
    raiz_repo = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "-c", script, str(RAIZ_QML), qml],
                       capture_output=True, text=True, encoding="utf-8", cwd=raiz_repo,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_avisos_de_seguridad_en_el_panel_de_la_campana():
    s = _correr(_SCRIPT, _QML)
    assert s.pop("avisos") == []
    s.pop("confirmaciones")
    assert all(s.values()), {k: v for k, v in s.items() if not v}


def test_no_queda_franja_superior_de_avisos():
    assert not (RAIZ_QML / "Componentes" / "AvisosSeguridad.qml").exists()
    for qml in RAIZ_QML.rglob("*.qml"):
        assert "AvisosSeguridad" not in qml.read_text(encoding="utf-8"), qml


@pytest.mark.parametrize("pantalla", [
    "Pantallas/PantallaPreciclo.qml", "Pantallas/PantallaCicloEnCurso.qml",
    "Pantallas/MenuPrincipal.qml", "Pantallas/Opciones.qml",
])
def test_cada_campana_recibe_puente_y_comandos(pantalla):
    """Las cuatro pantallas con campana pasan el puente y los comandos al panel
    (sin ellos no habría botón de confirmar) y usan InsigniaCampana."""
    texto = (RAIZ_QML / pantalla).read_text(encoding="utf-8")
    bloque = texto[texto.index("PanelNotificaciones {"):]
    bloque = bloque[:bloque.index("\n    }")]
    assert "puente: raiz.puente" in bloque and "comandosSistema: raiz.comandosSistema" in bloque
    assert "conteoTotal" in texto
