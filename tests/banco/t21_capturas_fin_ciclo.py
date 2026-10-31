# tests/banco/t21_capturas_fin_ciclo.py
#
# Tanda 21, etapa G (planeacion_fin_de_ciclo.md): capturas a 800 × 1280 de
# cada estado de los mockups de docs/diseno/mockups/fin_de_ciclo/, con los
# mismos nombres, en docs/informes/tanda21/capturas/. No es una prueba
# automática: Cristian las compara con los mockups.
#
#   python tests/banco/t21_capturas_fin_ciclo.py            (plataforma de la PC)
#   QT_QPA_PLATFORM=offscreen python tests/banco/...        (sin ventana; MultiEffect
#                                                            no se dibuja)
#
# Usa el arnés Pruebas/PruebaFinDeCiclo.qml; los textos del panel salen de
# ui_qml/domain/fin_de_ciclo (los mismos que en el equipo), en español.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "informes" / "tanda21" / "capturas"

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave import i18n
    from autoclave.ui_qml.domain import fin_de_ciclo

    destino = sys.argv[1]
    i18n.fijar_idioma("es")
    qapp = QGuiApplication([])
    _cargar_fuentes()

    ALARMAS = [
        {"codigo": "PRE-01", "nivel": "AVISO", "titulo": "Presión de chaqueta baja", "descripcion": "",
         "valores": {"pres": 268, "minimo": 280, "objetivo": 300, "rango": 20},
         "aparecida": "2026-10-28T13:02:15", "resuelta": "2026-10-28T13:04:40"},
        {"codigo": "CIC-09", "nivel": "AVISO", "titulo": "Uniformidad térmica fuera de rango",
         "descripcion": "", "valores": {"sensor": "Referencia 1", "temp": 131.2, "minimo": 133.9,
                                         "maximo": 137.0},
         "aparecida": "2026-10-28T13:19:40", "resuelta": None},
    ]
    FALLO = {"tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 136.4, "dt": 2.3, "temp": 134.1},
             "motivo": "", "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07",
             "cancelado_por": None, "observaciones": []}
    CANCELADO = {"tipo": "cancelado", "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07",
                 "cancelado_por": "cristian", "observaciones": []}
    EMERGENCIA = {"tipo": "emergencia", "codigo": "SIS-01", "valores": {"estado": "CICLO"},
                  "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07", "observaciones": []}
    EXITOSO = {"tipo": "exitoso", "hora_fin": "2026-10-28T13:51:07", "observaciones": []}
    EXITOSO_OBS = {**EXITOSO, "observaciones": [{"sensor": "Referencia 1", "hora": "13:12",
                                                 "fase": "esterilizacion"}]}
    SEN11 = [{"codigo": "SEN-11", "nivel": "AVISO", "titulo": "Sensor de referencia sin lectura",
              "descripcion": "", "valores": {"sensor": "Referencia 1", "fase": "Esterilización"},
              "aparecida": "2026-10-28T13:12:03", "resuelta": None}]

    def fin(term, alarmas, resultado):
        t = fin_de_ciclo.normalizar_terminacion(term, resultado)
        return fin_de_ciclo.armar(t, fin_de_ciclo.normalizar_alarmas(alarmas), "es")

    def fases(fin_fase, estado_fin):
        orden = ["precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]
        salida, antes = [], True
        for f in orden:
            if f == fin_fase:
                salida.append({"fase": f, "estado": estado_fin}); antes = False
            else:
                salida.append({"fase": f, "estado": "completada" if antes else "pendiente"})
        return salida

    COMPLETAS = [{"fase": f, "estado": "completada"} for f in
                 ("precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado")]

    # (archivo, propiedades del arnés, acción tras cargar)
    ESCENARIOS = [
        ("01_fallo_panel", {"resultado": "fallo", "fin": fin(FALLO, ALARMAS, "fallo"),
                            "fases": fases("esterilizacion", "fallida")}, None),
        ("02_fallo_panel_otra_fila", {"resultado": "fallo", "fin": fin(FALLO, ALARMAS, "fallo"),
                                      "fases": fases("esterilizacion", "fallida")}, "fila2"),
        ("03_fallo_vista_grafica", {"resultado": "fallo", "fin": fin(FALLO, ALARMAS, "fallo"),
                                    "fases": fases("esterilizacion", "fallida")}, "grafica"),
        ("04_fallo_modal_confirmar", {"resultado": "fallo", "fin": fin(FALLO, ALARMAS, "fallo"),
                                      "fases": fases("esterilizacion", "fallida")}, "modalConfirmarCiclo"),
        ("05_cancelado_panel", {"resultado": "cancelado", "fin": fin(CANCELADO, ALARMAS[:1], "cancelado"),
                                "fases": fases("esterilizacion", "interrumpida")}, None),
        ("06_emergencia_panel", {"resultado": "fallo", "fin": fin(EMERGENCIA, ALARMAS[:1], "fallo"),
                                 "fases": fases("esterilizacion", "fallida")}, None),
        ("07_emergencia_modal", {"resultado": "fallo", "fin": fin(EMERGENCIA, ALARMAS[:1], "fallo"),
                                 "fases": fases("esterilizacion", "fallida"), "ackEstadoSeguro": True},
         "modalEstadoSeguro"),
        ("08_exitoso_modal", {"resultado": "exitoso", "fin": fin(EXITOSO, [], "exitoso"),
                              "fases": COMPLETAS}, "modalConfirmarCiclo"),
        ("09_exitoso_observacion_grafica", {"resultado": "exitoso", "fin": fin(EXITOSO_OBS, SEN11, "exitoso"),
                                            "fases": COMPLETAS}, None),
        ("10_exitoso_observacion_modal", {"resultado": "exitoso", "fin": fin(EXITOSO_OBS, SEN11, "exitoso"),
                                          "fases": COMPLETAS}, "modalConfirmarCiclo"),
        ("11_en_ejecucion_modal_cancelar", {"resultado": "", "fin": {},
                                            "fases": fases("esterilizacion", "activa")}, "modalCancelarCiclo"),
        ("preciclo_01_automatica_cerrada_hoy", {"pantalla": "preciclo", "conActuador": True,
                                                "estadoPuerta": "CERRADO"}, None),
        ("preciclo_02_manual_cerrada", {"pantalla": "preciclo", "estadoPuerta": "CERRADO"}, None),
        ("preciclo_03_manual_abierta", {"pantalla": "preciclo", "estadoPuerta": "ABIERTO"}, None),
        ("preciclo_04_manual_sin_datos", {"pantalla": "preciclo", "conectado": False}, None),
    ]

    for nombre, props, accion in ESCENARIOS:
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties(props)
        engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaFinDeCiclo.qml"))
        w = engine.rootObjects()[0]
        # sin marco: Windows no recorta la ventana al alto de la pantalla
        w.setFlags(w.flags() | Qt.FramelessWindowHint)
        w.setGeometry(0, 0, 800, 1280)
        w.show()
        QTest.qWait(500)
        def obj(n):
            return [o for o in w.findChildren(QObject) if o.objectName() == n][0]
        if accion == "fila2":
            obj("panelFinCiclo").setProperty("filaAbierta", 2)
        elif accion == "grafica":
            obj("pantallaCiclo").setProperty("vistaGrafica", True)
        elif accion:
            obj(accion).setProperty("visible", True)
        QTest.qWait(500)
        w.grabWindow().save(os.path.join(destino, nombre + ".png"))
        print("captura", nombre)
        w.close()
        engine.deleteLater()
        QTest.qWait(50)
''')


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    # 800 × 1280 px reales: sin el escalado de la pantalla (125 % en la PC de desarrollo)
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ),
           "QT_ENABLE_HIGHDPI_SCALING": "0"}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(DESTINO)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=300)
    print(p.stdout)
    if p.returncode != 0:
        print(p.stderr, file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
