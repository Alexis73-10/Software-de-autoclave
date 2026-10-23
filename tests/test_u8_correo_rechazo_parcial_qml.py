# tests/test_u8_correo_rechazo_parcial_qml.py
#
# U8 (tanda 8, D8-3.24): verificación de punta a punta de lo hecho en C2
# (tanda 7). Un rechazo PARCIAL del relay (acepta una dirección y rechaza
# otra) se muestra en la pantalla real (Menú Principal, Historial y Reportes)
# como aviso de ERROR (fondo y texto rojos de Colores.peligro*) y nombra la
# dirección rechazada. Usa el puente AccionesCiclos real, el smtplib real y el
# SMTP falso local (tests/smtp_falso.py), sin red. En subproceso para tener un
# QGuiApplication propio. El paso de confirmación de la dirección escrita a
# mano lo cubre tests/test_c2_selector_correo_manual_qml.py.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from datetime import date
    from unittest.mock import MagicMock
    from PySide6.QtCore import QObject, Qt, QUrl, QMetaObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
    from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema
    from autoclave.ui_qml.exportacion import correo
    from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo
    from tests.smtp_falso import SMTPSinTLS, SmtpFalso

    def fila(i):
        return {"id": i, "numero_ciclo": i, "fecha_inicio": "2026-10-12T08:00:00",
                "fecha_fin": "2026-10-12T08:40:00", "programa_id": "instrumental_134",
                "programa_nombre": "Instrumental 134", "programa_numero": 2,
                "resultado": "COMPLETADO", "operador": None}
    PERIODO = {"desde": "2026-10-12", "hasta": "2026-10-12", "serie": "S", "modelo": "M",
               "totales": {"total": 1, "completados": 1, "fallos": 0, "cancelados": 0,
                           "sin_cierre": 0}, "por_programa": [], "causas_fallo": []}

    def get(ruta, params=None):
        if ruta == "/cycle/list":
            return {"truncado": False, "ciclos": [fila(91)], "periodo": params["periodo"]}
        if ruta == "/report/summary":
            return {**PERIODO, "periodo": params["periodo"]}
        if ruta.endswith("/ticket"):
            return {"ciclo": {**fila(91), "nombre_ciclo": "Instrumental 134", "serie": "S",
                              "modelo": "M", "version_sw": "1",
                              "tipo_ciclo": "instrumental_134", "temp_esterilizacion": 134,
                              "tiempo_esterilizacion": 4, "motivo_fallo": None},
                    "lecturas": []}
        if ruta == "/cycle/summary":
            return {"ciclos_totales": 1, "ciclos_hoy": 1, "ultimo_ciclo": None}
        return {"ciclo_db_id": 91, "lecturas": []}

    backend = MagicMock()
    backend.get.side_effect = get
    backend.post.side_effect = lambda ruta, body, **k: {"ok": True}

    r = {}
    with SmtpFalso(rechazar={"malo@x.com"}) as smtp:
        app = QGuiApplication([])
        _cargar_fuentes()
        config = ConfigCorreo("equipo@x.com", "127.0.0.1", smtp.puerto,
                              [{"nombre": "Mantenimiento", "correo": "mant@x.com"},
                               {"nombre": "Calidad", "correo": "malo@x.com"}], "clave")
        pdf = lambda ruta, *a, **k: open(ruta, "wb").write(b"%PDF")
        acciones = AccionesCiclos(backend, cargar_config=lambda: config,
                                  ejecutar=lambda t: t(), generar_pdf=pdf,
                                  generar_pdf_resumen=pdf,
                                  enviar=lambda c, m: correo.enviar(c, m, smtp=SMTPSinTLS))
        hoy = lambda: date(2026, 10, 12)
        resumen = ResumenSistema(backend, ejecutar=lambda t: t())
        historial = CiclosHistorial(backend, ejecutar=lambda t: t(), hoy=hoy)
        reporte = ReporteResumen(backend, ejecutar=lambda t: t(), hoy=hoy)
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties({"resumen": resumen, "historial": historial,
                                     "acciones": acciones, "reporte": reporte})
        engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaMenuPrincipal.qml"))
        w = engine.rootObjects()[0]
        w.setWidth(1196); w.setHeight(1917); w.show()
        QTest.qWait(300)

        def obj(nombre):
            return w.findChild(QObject, nombre)

        def tocar(o):
            c = o.mapToScene(o.boundingRect().center()).toPoint()
            QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, c)
            QTest.qWait(30)

        def item(o, nombre):
            for h in o.childItems():
                if h.objectName() == nombre:
                    return h
                e = item(h, nombre)
                if e is not None:
                    return e
            return None

        def aviso(ventana, nombre):
            a = item(ventana, nombre)
            t = item(a, "textoAvisoAccion")
            return {"visible": a.isVisible(), "error": a.property("error"),
                    "fondo": a.property("color").name(),
                    "color_texto": t.property("color").name(), "texto": t.property("text")}

        # Historial: marcar el ciclo y enviarlo a "Todos los guardados"
        tocar(obj("tarjetaHistorial"))
        vhi = obj("ventanaHistorial")
        tocar(item(item(vhi, "listaHistorial"), "casilla_91"))
        tocar(item(vhi, "botonEnviarMarcados"))
        tocar(item(vhi, "destinoTodos"))
        r["historial"] = aviso(vhi, "avisoAccionHistorial")
        QMetaObject.invokeMethod(vhi, "cerrar")

        # Reportes: resumen del periodo a "Todos los guardados"
        tocar(obj("tarjetaReportes"))
        vr = obj("ventanaReportes")
        tocar(item(vr, "botonEnviarResumen"))
        tocar(item(item(vr, "selectorDestinoReportes"), "destinoTodos"))
        r["reportes"] = aviso(vr, "avisoAccionReportes")
        r["entregados"] = [e["para"] for e in smtp.entregados]
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")

_ROJO_FONDO = "#ffecec"     # Colores.peligroFondo
_ROJO_TEXTO = "#d00000"     # Colores.peligroTexto


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(_RAIZ)],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          timeout=90, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_solo_llega_a_la_direccion_aceptada(r):
    assert r["entregados"] == [["mant@x.com"], ["mant@x.com"]]


@pytest.mark.parametrize("ventana", ["historial", "reportes"])
def test_rechazo_parcial_en_rojo_con_la_direccion_rechazada(r, ventana):
    a = r[ventana]
    assert a["visible"] is True
    assert a["error"] is True
    assert a["fondo"] == _ROJO_FONDO and a["color_texto"] == _ROJO_TEXTO
    assert "malo@x.com" in a["texto"]          # nombra la rechazada
    assert "mant@x.com" in a["texto"]          # y la que sí la recibió
