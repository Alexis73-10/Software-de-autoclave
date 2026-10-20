"""U1 (tanda 2): los avisos de seguridad de E5 (paro, estado seguro, NO ABRIR,
modo prueba) están en el panel de la campana (PanelNotificaciones ›
SeccionEstadoSeguro), no en una franja superior. Mockup aprobado:
docs/mis_plans/mockup_estado_seguro.png (3 estados).
U4 (tanda 2): el panel agrupa por nivel (Emergencia/Fallas, Alarmas, Avisos),
no se abre solo ni queda bloqueado, y distingue tarjeta desconectada o sin
datos del paro real. Las mismas filas van en la tarjeta de alarmas de Preciclo
y de Ciclo en curso."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_PUENTE = """
    QtObject {
        id: puenteFalso
        property bool noAbrir: false
        property string noAbrirMotivo: ""
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property string estadoSeguroBloqueadoMotivo: ""
        property bool modoPrueba: false
        property bool connected: true
        property string estadoTarjeta: "ok"
    }
    QtObject {
        id: comandosFalsos
        property bool ocupado: false
        property string mensaje: ""
        property int confirmaciones: 0
        property int asignaciones: 0
        function confirmarEstadoSeguro() { confirmaciones += 1 }
        function asignarSondaPrincipal() { asignaciones += 1 }
    }
    property alias puente: puenteFalso
    property alias comandos: comandosFalsos
"""

_QML = """
import QtQuick
import "Componentes"
Item {
    width: 600; height: 1600
    property alias panel: pn
""" + _PUENTE + """
    ListModel { id: alarmasFalsas }
    function agregar(nivel, prioridad) {
        alarmasFalsas.append({id: "X" + alarmasFalsas.count, description: "x",
                              level: nivel, priority: prioridad})
    }
    PanelNotificaciones {
        id: pn
        objectName: "panelPrueba"
        alarmas: alarmasFalsas
        puente: puenteFalso
        comandosSistema: comandosFalsos
    }
}
"""

_CABECERA = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
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
puente = raiz.property("puente")
comandos = raiz.property("comandos")
r = {}
"""

_SCRIPT = _CABECERA + r"""
panel = raiz.findChild(QObject, "panelPrueba")

def grupo(g):
    return panel.findChild(QObject, g)

def fila(g, nombre):
    return grupo(g).findChild(QObject, nombre)

def visible(g, nombre):
    return bool(fila(g, nombre).property("visible"))

def p(nombre):
    return panel.property(nombre)

def conteo(seccion):
    return panel.findChild(QObject, "cabecera_" + seccion).property("conteo")

E, A, V = "grupoEmergencia", "grupoAlarmas", "grupoAvisos"
r["sin_avisos_cerrado"] = not p("visible") and p("conteoTotal") == 0

# 1. paro real: el panel NO se abre solo (U4); insignia roja y parpadeando
puente.setProperty("paroActivo", True)
r["1_no_abre_solo"] = not p("visible")
r["1_insignia"] = p("conteoTotal") == 1 and p("urgente") and p("parpadeo")
QMetaObject.invokeMethod(panel, "abrir")
r["1_fila_paro_en_emergencia"] = visible(E, "filaParo") and conteo("emergencia") == 1
r["1_sin_boton"] = not visible(E, "botonConfirmarEstadoSeguro")
r["1_sin_no_abrir_duplicado"] = conteo("alarma") == 0
# se cierra con normalidad aunque dure el paro
QMetaObject.invokeMethod(panel, "cerrar")
r["1_se_cierra"] = not p("visible")
QMetaObject.invokeMethod(panel, "abrir")

# 2. paro liberado: aviso naranja y botón azul habilitado; insignia parpadeando
puente.setProperty("paroActivo", False)
puente.setProperty("estadoSeguroActivo", True)
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
r["2_fila"] = visible(E, "filaEstadoSeguroPendiente") and not visible(E, "filaParo")
r["2_aviso_naranja"] = visible(E, "avisoParoLiberado")
boton = fila(E, "botonConfirmarEstadoSeguro")
r["2_boton_habilitado"] = visible(E, "botonConfirmarEstadoSeguro") and bool(boton.property("habilitado"))
r["2_parpadeo"] = p("urgente") and p("parpadeo")
r["2_sin_indicador"] = not visible(E, "indicadorEnCurso")
comandos.setProperty("ocupado", True)
r["2_enviando_deshabilita"] = not bool(boton.property("habilitado")) and visible(E, "indicadorEnCurso")
comandos.setProperty("ocupado", False)
comandos.setProperty("mensaje", "Sin conexión")
r["2_mensaje_rechazo"] = visible(E, "mensajeConfirmar")
comandos.setProperty("mensaje", "")

# 3. en curso: botón deshabilitado con indicador y nota NO ABRIR; insignia amarilla
puente.setProperty("estadoSeguroRequiereConfirmacion", False)
r["3_fila"] = visible(E, "filaEstadoSeguroEnCurso") and not visible(E, "filaEstadoSeguroPendiente")
r["3_boton_deshabilitado"] = visible(E, "botonConfirmarEstadoSeguro") and not bool(boton.property("habilitado"))
r["3_indicador"] = visible(E, "indicadorEnCurso") and visible(E, "notaNoAbrirEnCurso")
r["3_insignia"] = p("avisoEnCurso") and not p("urgente") and not p("parpadeo")
# S4 (CIC-10): estado seguro detenido: aviso con la acción y botón de asignar sonda
r["s4_sin_bloqueo_oculto"] = (not visible(E, "avisoEstadoSeguroDetenido")
                              and not visible(E, "botonAsignarSonda"))
puente.setProperty("estadoSeguroBloqueadoMotivo", "Sensor Principal sin lectura")
r["s4_aviso"] = (visible(E, "avisoEstadoSeguroDetenido") and visible(E, "botonAsignarSonda")
                 and "Sensor Principal sin lectura" in fila(E, "avisoEstadoSeguroDetenido").property("texto")
                 and "Parámetros del ciclo" in fila(E, "avisoEstadoSeguroDetenido").property("texto"))
r["s4_sigue_no_abrir"] = visible(E, "filaEstadoSeguroEnCurso") and fila(E, "botonDeclararSegura") is None
puente.setProperty("estadoSeguroBloqueadoMotivo", "")
puente.setProperty("estadoSeguroActivo", False)

# sin conexión con el backend: seguridad desconocida, contada, roja fija
puente.setProperty("connected", False)
r["sin_conexion"] = (visible(E, "filaSeguridadDesconocida") and p("conteoTotal") == 1
                     and p("urgente") and not p("parpadeo"))
puente.setProperty("connected", True)

# U4: tarjeta desconectada / sin datos: fila propia, sin fila de paro, roja fija
puente.setProperty("noAbrir", True)
puente.setProperty("estadoTarjeta", "desconectada")
r["tarjeta_desconectada"] = (visible(E, "filaTarjetaDesconectada") and not visible(E, "filaParo")
                             and "Tarjeta desconectada" in fila(E, "filaTarjetaDesconectada").property("descripcion")
                             and p("conteoTotal") == 1 and p("urgente") and not p("parpadeo"))
puente.setProperty("estadoTarjeta", "sin_tramas_validas")
r["tarjeta_sin_datos"] = (visible(E, "filaTarjetaSinDatos") and not visible(E, "filaTarjetaDesconectada")
                          and p("conteoTotal") == 1)
puente.setProperty("estadoTarjeta", "ok")

# NO ABRIR en "Alarmas" y modo prueba en "Avisos", contados; plegados por defecto
puente.setProperty("noAbrirMotivo", "Temperatura demasiado alta (95 °C)")
r["no_abrir_contado"] = conteo("alarma") == 1 and not visible(A, "filaNoAbrir")
grupo(A).setProperty("expandido", True)
r["no_abrir"] = visible(A, "filaNoAbrir") and "95" in fila(A, "filaNoAbrir").property("descripcion")
puente.setProperty("modoPrueba", True)
grupo(V).setProperty("expandido", True)
r["modo_prueba"] = (visible(V, "filaModoPrueba") and conteo("aviso") == 1
                    and p("conteoTotal") == 2 and not p("urgente"))

# alarmas del modelo, cada una en el grupo de su nivel
for nivel, prioridad in (("EMERGENCIA", "alta"), ("FALLA", "media"), ("FALLA", "media"),
                         ("ALERTA", "baja")):
    QMetaObject.invokeMethod(raiz, "agregar", Q_ARG("QVariant", nivel), Q_ARG("QVariant", prioridad))
QTest.qWait(30)
r["grupos_cuentan"] = [conteo("emergencia"), conteo("alarma"), conteo("aviso")] == [1, 3, 2]
r["suma_alarmas"] = p("conteoTotal") == 6 and p("conteo") == 4
# al cerrar, Alarmas y Avisos vuelven a plegarse; Emergencia queda desplegado
QMetaObject.invokeMethod(panel, "cerrar")
r["pliega_al_cerrar"] = (not grupo(A).property("expandido") and not grupo(V).property("expandido")
                         and grupo(E).property("expandido"))

r["avisos"] = avisos
print(json.dumps(r))
"""

# U4: el botón "Confirmar y llevar a estado seguro" funciona dentro de la
# sección compartida (tarjeta de alarmas de Preciclo), sin sesión
_QML_SECCION = """
import QtQuick
import "Componentes"
Item {
    width: 900; height: 1200
""" + _PUENTE + """
    SeccionEstadoSeguro {
        objectName: "seccion"
        width: 900
        puente: puenteFalso
        comandos: comandosFalsos
    }
}
"""

_SCRIPT_SECCION = _CABECERA + r"""
from PySide6.QtQuick import QQuickWindow
from PySide6.QtCore import QPointF
ventana = QQuickWindow()
ventana.resize(900, 1200)
raiz.setProperty("parent", ventana.contentItem())
ventana.show()
QTest.qWaitForWindowExposed(ventana)
puente.setProperty("estadoSeguroActivo", True)
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
QTest.qWait(50)
seccion = raiz.findChild(QObject, "seccion")
boton = seccion.findChild(QObject, "botonConfirmarEstadoSeguro")
centro = boton.mapToScene(QPointF(boton.property("width") / 2, boton.property("height") / 2))
QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, centro.toPoint())
r["confirmado_inline"] = comandos.property("confirmaciones") == 1
# con el paro real, sin botón (estado 1)
puente.setProperty("paroActivo", True)
QTest.qWait(20)
r["paro_sin_boton"] = not boton.property("visible")
r["avisos"] = avisos
print(json.dumps(r))
""".replace("from PySide6.QtCore import QPointF", "from PySide6.QtCore import QPointF, Qt")


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
    assert all(s.values()), {k: v for k, v in s.items() if not v}


def test_boton_confirmar_inline_en_la_seccion_compartida():
    s = _correr(_SCRIPT_SECCION, _QML_SECCION)
    assert s.pop("avisos") == []
    assert all(s.values()), {k: v for k, v in s.items() if not v}


def test_panel_sin_bloqueo_ni_apertura_automatica():
    texto = (RAIZ_QML / "Componentes" / "PanelNotificaciones.qml").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))
    assert "bloqueado" not in codigo and "abrir()" not in codigo
    assert "bloqueado" not in (RAIZ_QML / "Componentes" / "PanelModal.qml").read_text(encoding="utf-8")


def test_tarjetas_de_alarmas_usan_la_seccion_compartida():
    preciclo = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    zona = preciclo[preciclo.index("id: zonaAlarmas"):]
    assert "SeccionEstadoSeguro {" in zona and "comandos: raiz.comandosSistema" in zona
    ciclo = (RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(encoding="utf-8")
    bloque = ciclo[ciclo.index('objectName: "tarjetaSeguridadCiclo"'):]
    assert "SeccionEstadoSeguro {" in bloque and 'grupo: "emergencia"' in bloque
    assert "comandos: raiz.comandosSistema" in bloque


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


def test_aviso_critico_cierra_la_grafica_a_pantalla_completa():
    # revisión SAF-02 de U4: la pantalla completa tapa la tarjeta de seguridad
    ciclo = (RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(encoding="utf-8")
    assert "readonly property bool avisoCritico: seguridadCiclo.conteo > 0" in ciclo
    assert "onAvisoCriticoChanged: if (avisoCritico) pantallaCompleta = false" in ciclo


def test_filas_de_seguridad_de_preciclo_fijas_fuera_de_la_lista():
    # revisión SAF-04 de U4: no se desplazan con la lista de alarmas
    preciclo = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    assert "header: SeccionEstadoSeguro" not in preciclo
    assert "anchors.top: seguridadPreciclo.bottom" in preciclo
