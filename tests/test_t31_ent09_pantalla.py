# tests/test_t31_ent09_pantalla.py
#
# Tanda 31, ENT-09 (planeacion_entrega_camara_fin_ciclo.md): pantalla de ciclo
# en curso con el resultado pendiente de la entrega de la cámara.
#   - domain/entrega_camara: normalización con falla cerrada y textos es/en.
#   - ProgresoCiclo: entregada / forzable / textoEntrega a partir del progreso.
#   - ComandosCicloEnCurso: confirmarForzado, rechazo y rol de ingeniero.
#   - PantallaCicloEnCurso real (offscreen): indicador en lugar de CONFIRMAR,
#     CONFIRMAR al entregar, botón forzado solo para el ingeniero, modal de
#     advertencia y contraseña por el teclado de acción, texto del rechazo.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytestmark = pytest.mark.req("T31-ENT-09")

from autoclave.ui_qml.domain import ciclo_en_curso, entrega_camara  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

MOTIVO = {"motivo_codigo": "temp_alta", "motivo_valores": {"temp": 92.0},
          "motivo_textos": {"es": "Temperatura 92 °C, máximo 80 °C",
                            "en": "Temperature 92 °C, maximum 80 °C"}}


def _entrega(**kw):
    base = {"entregada": False, "motivos": ["Temperatura 92 °C, máximo 80 °C"],
            "motivos_detalle": [MOTIVO], "espera_restante_s": None, "forzable": True}
    base.update(kw)
    return base


# ── dominio ──────────────────────────────────────────────────────────────

def test_sin_entrega_con_resultado_es_no_entregada_ni_forzable():
    for crudo in (None, {}, "x", {"entregada": "si"}):
        e = entrega_camara.normalizar_entrega(crudo, "fallo")
        assert e["entregada"] is False and e["forzable"] is False


def test_sin_resultado_no_hay_entrega():
    assert entrega_camara.normalizar_entrega(_entrega(entregada=True), None)["entregada"] is False


def test_entregada_solo_con_true_estricto():
    assert entrega_camara.normalizar_entrega(_entrega(entregada=True), "exitoso")["entregada"] is True
    assert entrega_camara.normalizar_entrega(_entrega(entregada=1), "exitoso")["entregada"] is False


def test_texto_motivo_es_en():
    e = entrega_camara.normalizar_entrega(_entrega(), "fallo")
    assert entrega_camara.texto_entrega(e, "es") == \
        "Esperando cámara segura: Temperatura 92 °C, máximo 80 °C"
    assert entrega_camara.texto_entrega(e, "en") == \
        "Waiting for safe chamber: Temperature 92 °C, maximum 80 °C"


def test_texto_espera_fija_con_minutos_y_segundos():
    e = entrega_camara.normalizar_entrega(
        _entrega(motivos=[], motivos_detalle=[], espera_restante_s=125, forzable=False), "exitoso")
    assert entrega_camara.texto_entrega(e, "es") == "Esperando condiciones de apertura: 2:05"
    assert entrega_camara.texto_entrega(e, "en") == "Waiting for opening conditions: 2:05"


def test_texto_sin_motivo_ni_espera():
    e = entrega_camara.normalizar_entrega(_entrega(motivos=[], motivos_detalle=[]), "fallo")
    assert entrega_camara.texto_entrega(e, "es") == "Esperando cámara segura"


def test_motivo_sin_detalle_usa_el_texto_del_backend():
    e = entrega_camara.normalizar_entrega(_entrega(motivos_detalle=[]), "fallo")
    assert entrega_camara.texto_entrega(e, "en").endswith("Temperatura 92 °C, máximo 80 °C")


def test_normalizar_progreso_incluye_entrega():
    base = {"activo": True, "resultado": "fallo", "fases": []}
    assert ciclo_en_curso.normalizar_progreso(base)["entrega"]["entregada"] is False
    con = ciclo_en_curso.normalizar_progreso({**base, "entrega": _entrega(entregada=True)})
    assert con["entrega"]["entregada"] is True


def test_texto_rechazo_agrega_el_motivo():
    t = entrega_camara.texto_rechazo("sesion.camara_no_entregada",
                                     {"motivo_textos": MOTIVO["motivo_textos"]}, "es")
    assert "Temperatura 92 °C" in t and t.startswith("La cámara aún no está")
    assert entrega_camara.texto_rechazo("sesion.camara_no_entregada", {}, "es").startswith("La cámara")


# ── puente ProgresoCiclo ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def test_progreso_ciclo_publica_entrega(qt_app):
    from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo
    p = ProgresoCiclo(MagicMock(), iniciar=False)
    assert p.entregada is False and p.forzable is False
    p._al_recibir({"activo": True, "resultado": "fallo", "fases": [], "entrega": _entrega()}, None)
    assert p.entregada is False and p.forzable is True
    assert p.textoEntrega("es").startswith("Esperando cámara segura: Temperatura 92")
    p._al_recibir({"activo": True, "resultado": "fallo", "fases": [],
                   "entrega": _entrega(entregada=True)}, None)
    assert p.entregada is True


# ── comandos ─────────────────────────────────────────────────────────────

class _Puente:
    connected = True


def _comandos(ack=True, rechazo=None):
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso
    ui = MagicMock(spec=UIServiceBackend)
    ui.acknowledge_cycle.return_value = ack
    ui.ultimo_rechazo_ack.return_value = rechazo
    tareas = []
    return ComandosCicloEnCurso(_Puente(), ui, ejecutar=tareas.append), ui, tareas


def _correr(tareas):
    from PySide6.QtCore import QCoreApplication
    tareas.pop(0)()
    QCoreApplication.processEvents()


def test_confirmar_forzado_envia_forzar_y_clave(qt_app):
    c, ui, tareas = _comandos()
    c.confirmarForzado("secreta")
    _correr(tareas)
    ui.acknowledge_cycle.assert_called_once_with(forzar=True, clave="secreta")
    assert c.error == ""


def test_rechazo_409_expone_clave_y_texto_con_motivo(qt_app):
    c, ui, tareas = _comandos(ack=False, rechazo=(409, {
        "codigo": "camara_no_entregada", "detail": "x", "motivo_textos": MOTIVO["motivo_textos"]}))
    c.confirmar()
    _correr(tareas)
    assert c.error == "confirmar"
    assert c.rechazo == "sesion.camara_no_entregada"
    assert "Temperatura 92 °C, máximo 80 °C" in c.textoRechazo("es")
    # el siguiente intento limpia el rechazo anterior
    ui.acknowledge_cycle.return_value = True
    c.confirmar()
    _correr(tareas)
    assert c.rechazo == ""


def test_rechazo_de_clave_usa_el_texto_existente(qt_app):
    c, ui, tareas = _comandos(ack=False, rechazo=(403, {"codigo": "reautenticacion_fallida"}))
    c.confirmarForzado("mala")
    _correr(tareas)
    assert c.rechazo == "reasignacion.err_clave"


def test_rechazo_desconocido_cae_en_el_texto_generico(qt_app):
    c, ui, tareas = _comandos(ack=False, rechazo=(500, {"codigo": "otra_cosa"}))
    c.confirmar()
    _correr(tareas)
    assert c.error == "confirmar" and c.rechazo == ""


def test_rol_ingeniero_sigue_la_sesion(qt_app, monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    c, _ui, _t = _comandos()
    monkeypatch.setattr(SessionManager, "current_role", classmethod(lambda cls: "ingeniero"))
    c.refrescarRol()
    assert c.rolIngeniero is True
    monkeypatch.setattr(SessionManager, "current_role", classmethod(lambda cls: "tecnico"))
    c.refrescarRol()
    assert c.rolIngeniero is False


# ── pantalla real ────────────────────────────────────────────────────────

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        objectName: "comandosFalsos"
        property int confirmaciones: 0
        property int nClaves: 0
        property string ultimaClave: ""
        property bool ocupado: false
        property string error: ""
        property string rechazo: ""
        property bool rolIngeniero: false
        function cancelar() {}
        function confirmar() { confirmaciones++ }
        function confirmarForzado(c) { nClaves++; ultimaClave = c }
        function refrescarRol() {}
        function textoRechazo(idioma) { return "RECHAZO " + rechazo }
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        objectName: "progresoFalso"
        property string resultado: ""
        property bool entregada: false
        property bool forzable: false
        property bool activo: true
        property int revisionFin: 0
        property string texto: ""
        function textoEntrega(idioma) { return texto }
        function armarFin(idioma) { return ({}) }
    }
    QtObject {
        id: puenteFalso
        objectName: "puenteFalso"
        property bool connected: true
        property string estadoModuloEs: "ok"
        property string cicloActivo: "03"
        property bool ackConfirmaEstadoSeguro: false
    }
    QtObject {
        id: tecladoFalso
        objectName: "tecladoFalso"
        property int llamadas: 0
        property bool ocultar: false
        property var alConfirmar: null
        function abrirAlfanumericoAccion(titulo, valor, largo, ocultar_, cb) {
            llamadas++; ocultar = ocultar_
            alConfirmar = cb
        }
        function entregar(t) { alConfirmar(t) }
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        objectName: "pantalla"
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        puente: puenteFalso
        teclado: tecladoFalso
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl, QMetaObject, Q_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t31_ent09.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(250)

    def obj(nombre):
        return [o for o in ventana.findChildren(QObject) if o.objectName() == nombre][0]

    pantalla, progreso, comandos, teclado = (obj("pantalla"), obj("progresoFalso"),
                                             obj("comandosFalsos"), obj("tecladoFalso"))
    boton, indicador, forzado = obj("botonCancelarCiclo"), obj("indicadorEntrega"), obj("botonConfirmarForzado")
    modal_forzar, modal_confirmar, aviso = obj("modalConfirmarForzado"), obj("modalConfirmarCiclo"), obj("avisoComando")

    def pulsar(item):
        c = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(40)

    def poner(o, **kw):
        for k, v in kw.items():
            o.setProperty(k, v)
        QTest.qWait(60)

    def estado():
        return {"boton": boton.isVisible(), "indicador": indicador.isVisible(),
                "forzado": forzado.isVisible(), "texto": obj("textoEntrega").property("text")}

    def aceptar(modal):
        pulsar([o for o in modal.findChildren(QQuickItem) if o.objectName() == "botonAccionModal"][0])

    r = {}
    r["en_curso"] = estado()
    # resultado sin entrega: indicador con el motivo, sin botón
    poner(progreso, texto="Esperando cámara segura: Temperatura 92 °C, máximo 80 °C")
    poner(progreso, resultado="fallo", revisionFin=1)
    r["esperando"] = estado()
    r["toque_indicador"] = (pulsar(indicador), modal_confirmar.property("visible"))[1]
    # ingeniero, forzable: aparece el botón forzado
    poner(comandos, rolIngeniero=True)
    r["ingeniero_no_forzable"] = estado()
    poner(progreso, forzable=True)
    r["ingeniero_forzable"] = estado()
    pulsar(forzado)
    r["modal_forzar"] = modal_forzar.property("visible")
    r["nota_modal"] = modal_forzar.property("nota")
    aceptar(modal_forzar)
    r["teclado"] = [teclado.property("llamadas"), teclado.property("ocultar")]
    r["claves_antes"] = comandos.property("nClaves")
    QMetaObject.invokeMethod(teclado, "entregar", Q_ARG("QVariant", "mi-clave"))
    QTest.qWait(40)
    r["claves"] = [comandos.property("nClaves"), comandos.property("ultimaClave")]
    # técnico (no ingeniero): sin botón forzado
    poner(comandos, rolIngeniero=False)
    r["tecnico"] = estado()
    # entrega: aparece CONFIRMAR con su modal, sin indicador
    poner(progreso, entregada=True, revisionFin=2)
    r["entregada"] = estado()
    pulsar(boton)
    r["modal_confirmar"] = modal_confirmar.property("visible")
    # la cámara deja de estar entregada: el modal se cierra
    poner(progreso, entregada=False, revisionFin=3)
    r["modal_tras_perder"] = modal_confirmar.property("visible")
    r["tras_perder"] = estado()
    # paro soltado: CONFIRMAR del estado seguro sigue sin entrega (ENT-05)
    poner(obj("puenteFalso"), ackConfirmaEstadoSeguro=True)
    r["paro"] = estado()
    poner(obj("puenteFalso"), ackConfirmaEstadoSeguro=False)
    # rechazo: el aviso muestra el texto del rechazo
    poner(comandos, rechazo="sesion.camara_no_entregada", error="confirmar")
    r["aviso_visible"] = aviso.property("visible")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=True))
""")


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_mientras_corre_hay_cancelar_y_no_indicador(r):
    assert r["en_curso"]["boton"] is True and r["en_curso"]["indicador"] is False


def test_con_resultado_sin_entrega_indicador_en_lugar_de_confirmar(r):
    e = r["esperando"]
    assert e["indicador"] is True and e["boton"] is False and e["forzado"] is False
    assert e["texto"] == "Esperando cámara segura: Temperatura 92 °C, máximo 80 °C"
    assert r["toque_indicador"] is False   # no es botón


def test_forzado_solo_para_ingeniero_y_si_es_forzable(r):
    assert r["ingeniero_no_forzable"]["forzado"] is False
    assert r["ingeniero_forzable"]["forzado"] is True and r["ingeniero_forzable"]["indicador"] is True
    assert r["tecnico"]["forzado"] is False


def test_forzado_pide_advertencia_y_contrasena_por_el_teclado_de_accion(r):
    assert r["modal_forzar"] is True
    assert "Esperando cámara segura" in r["nota_modal"]
    assert r["teclado"] == [1, True]
    assert r["claves_antes"] == 0
    assert r["claves"] == [1, "mi-clave"]


def test_entregada_aparece_confirmar_con_su_modal(r):
    e = r["entregada"]
    assert e["boton"] is True and e["indicador"] is False and e["forzado"] is False
    assert r["modal_confirmar"] is True


def test_perder_la_entrega_cierra_el_modal_y_vuelve_el_indicador(r):
    assert r["modal_tras_perder"] is False
    assert r["tras_perder"]["indicador"] is True and r["tras_perder"]["boton"] is False


def test_paro_soltado_conserva_confirmar_sin_entrega(r):
    assert r["paro"]["boton"] is True and r["paro"]["indicador"] is False


def test_rechazo_abre_el_aviso(r):
    assert r["aviso_visible"] is True
