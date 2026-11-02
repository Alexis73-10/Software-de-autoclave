# tests/test_dr_h06_correo_manual_punta_a_punta_qml.py
#
# DR-H06 (tanda dashboard-reportes, etapa F): diagnóstico de «un correo escrito
# a mano no llega aunque el software dice enviado» (reportado el 20-oct).
# Reproducción de punta a punta con el código actual y sin red:
#   SelectorDestino.qml + PanelTeclado.qml reales (teclas a 150 ms, como en el
#   equipo) -> AccionesCiclos real con su hilo de trabajo y un PDF lento (1 s)
#   -> correo.enviar con el smtplib real -> SMTP falso local (127.0.0.1).
# Se exige que el relay reciba UNA sola vez la dirección COMPLETA (nunca una
# parcial como «juan@gmail.c», la causa de C2 en la tanda 7) y que el aviso
# «enviado» nombre la dirección que el relay aceptó. Resultado y conclusión en
# docs/informes/dashboard_reportes/F_diagnostico_correo.md.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    property QtObject acciones: null
    property var elegidos: []
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    Item {
        anchors.fill: parent
        SelectorDestino {
            id: selector
            anchors.fill: parent
            escala: 0.5
            destinos: [{"nombre": "Mantenimiento", "correo": "mant@x.com"}]
            teclado: panel
            sesionActiva: true
            onElegido: correo => {
                ventana.elegidos = ventana.elegidos.concat([correo])
                ventana.acciones.enviarCorreo([12], correo)
            }
        }
        PanelTeclado { id: panel; objectName: "panelTeclado" }
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys, time
    from unittest.mock import MagicMock
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.exportacion import correo
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    from tests.helpers.smtp_falso import SMTPSinTLS, SmtpFalso

    qml_dir, qml, escenario = sys.argv[1], sys.argv[2], sys.argv[3]
    app = QGuiApplication([])

    def get(ruta, **k):
        i = int(ruta.split("/")[3])
        if ruta.endswith("/ticket"):
            return {"ciclo": {"id": i, "numero_ciclo": i, "serie": "S1", "modelo": "M",
                              "version_sw": "1", "nombre_ciclo": "Instrumental 134",
                              "tipo_ciclo": "instrumental_134", "temp_esterilizacion": 134,
                              "tiempo_esterilizacion": 4, "fecha_inicio": "2026-09-15T08:00:00",
                              "fecha_fin": "2026-09-15T08:40:00", "resultado": "COMPLETADO",
                              "motivo_fallo": None}, "lecturas": []}
        return {"ciclo_db_id": i, "lecturas": []}

    def pdf_lento(ruta, *a):
        time.sleep(1.0)               # el PDF real tarda segundos en el equipo
        with open(ruta, "wb") as f:
            f.write(b"%PDF-x")

    backend = MagicMock()
    backend.get.side_effect = get
    bitacora = []
    backend.post.side_effect = lambda ruta, body, **k: (bitacora.append(body), {"ok": True})[1]

    with SmtpFalso() as smtp:
        config = ConfigCorreo("equipo@x.com", "127.0.0.1", smtp.puerto,
                              [{"nombre": "Mantenimiento", "correo": "mant@x.com"}], "c")
        acciones = AccionesCiclos(backend, cargar_config=lambda: config, generar_pdf=pdf_lento,
                                  enviar=lambda c, m: correo.enviar(c, m, smtp=SMTPSinTLS),
                                  sesion_activa=lambda: True)   # hilo de trabajo real
        avisos_pantalla = []
        acciones.accionTerminada.connect(lambda e, m: avisos_pantalla.append([e, m]))

        engine = QQmlEngine()
        engine.addImportPath(qml_dir)
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        comp = QQmlComponent(engine)
        comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_dr_h06.qml"))
        w = comp.createWithInitialProperties({"acciones": acciones})
        assert w is not None, comp.errorString()
        w.show()
        QTest.qWait(200)

        def item(o, nombre):
            for h in o.childItems():
                if h.objectName() == nombre:
                    return h
                encontrado = item(h, nombre)
                if encontrado is not None:
                    return encontrado
            return None

        raiz = w.contentItem()
        def tocar(nombre):
            o = item(raiz, nombre)
            assert o is not None, nombre
            c = o.mapToScene(o.boundingRect().center()).toPoint()
            QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, c)
            QTest.qWait(30)

        from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import \
            TecladoAlfanumericoController
        ctrl = [o for o in item(raiz, "tecladoAlfanumerico").findChildren(QObject)
                if isinstance(o, TecladoAlfanumericoController)][0]
        panel = item(raiz, "panelTeclado")

        r = {}
        tocar("destinoOtro")
        for ch in "juan@gmail.com":
            ctrl.presionarCaracter(ch)
            QTest.qWait(150)            # ritmo de un operador en la pantalla táctil
        r["rcpt_al_escribir"] = list(smtp.rcpt)
        if escenario == "ocultar":
            from PySide6.QtCore import QMetaObject
            QMetaObject.invokeMethod(panel, "ocultar")
        else:
            ctrl.confirmar()
        QTest.qWait(100)
        r["texto_confirmacion"] = item(raiz, "textoCorreoManual").property("text")
        tocar("botonManualYGuardados" if escenario == "mixto" else "botonSoloManual")
        limite = time.monotonic() + 20
        while not avisos_pantalla and time.monotonic() < limite:
            QTest.qWait(50)
        QTest.qWait(300)                # por si llegara un segundo envío tardío
        r["elegidos"] = list(w.property("elegidos").toVariant()
                             if hasattr(w.property("elegidos"), "toVariant")
                             else w.property("elegidos"))
        r["rcpt"] = list(smtp.rcpt)
        r["entregados"] = [e["para"] for e in smtp.entregados]
        r["aviso"] = avisos_pantalla
        r["bitacora"] = [{k: b.get(k) for k in ("destinatarios", "manuales", "aceptados",
                                                 "resultado")} for b in bitacora]
        r["avisos_qml"] = avisos
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


def _correr(escenario):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, escenario],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          timeout=120, cwd=RAIZ_QML.parents[3])
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def _una_vez_completa(r, esperados):
    assert r["avisos_qml"] == []
    assert r["rcpt_al_escribir"] == []                  # nada sale mientras se escribe
    assert [e.lower() for e in r["elegidos"]] == [",".join(esperados)]
    assert [d.lower() for d in r["rcpt"]] == esperados   # una vez, dirección completa
    assert [[d.lower() for d in p] for p in r["entregados"]] == [esperados]
    assert len(r["aviso"]) == 1 and r["aviso"][0][0] is True
    for d in esperados:
        assert d in r["aviso"][0][1].lower()             # el aviso nombra lo aceptado
    assert len(r["bitacora"]) == 1 and r["bitacora"][0]["resultado"] == "enviado"


def test_manual_confirmada_llega_completa_una_vez():
    r = _correr("confirmar")
    assert r["texto_confirmacion"].lower() == "juan@gmail.com"
    _una_vez_completa(r, ["juan@gmail.com"])


def test_manual_tras_ocultar_el_teclado_llega_completa_una_vez():
    r = _correr("ocultar")
    _una_vez_completa(r, ["juan@gmail.com"])


def test_manual_y_guardadas_llegan_completas_una_vez():
    r = _correr("mixto")
    _una_vez_completa(r, ["juan@gmail.com", "mant@x.com"])
