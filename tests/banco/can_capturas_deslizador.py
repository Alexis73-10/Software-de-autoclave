# tests/banco/can_capturas_deslizador.py
#
# Tanda 34 (CAN-04, ESP-01): capturas de la barra inferior de Ciclo en curso.
#   can_<tema>_<ancho>_<idioma>_<estado>.png  deslizador rojo CANCELAR CICLO en
#       reposo y a medio arrastre (claro y oscuro, 1080x1920 y 1024x1638, es/en)
#   esp_<ancho>_<idioma>_<caso>.png  barra con el mensaje de espera de la cámara
#       (sin motivo) y la espera fija tras COMPLETADO (es/en, 1080 y 1024)
# Recorta la barra inferior; imprime una línea JSON por captura con las medidas
# de los textos (contenido frente a su cuadro) para revisar que nada se salga.
# No es una prueba automática. Ventana real (MultiEffect se dibuja).
#
#   python tests/banco/can_capturas_deslizador.py [--destino DIR]

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "informes" / "tanda34" / "capturas"
TAMANOS = [(1080, 1920), (1024, 1638)]

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QPointF, QRect, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    import autoclave.ui_qml.bridge.detalle_aviso_qml  # noqa: F401

    cfg = json.loads(sys.argv[1])
    w, h, destino, idioma = cfg["ancho"], cfg["alto"], cfg["destino"], cfg["idioma"]
    i18n.cargar(); i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()

    MOTIVO = {"es": "Temperatura 92 °C, máximo 80 °C", "en": "Temperature 92 °C, maximum 80 °C"}[idioma]
    ESPERA = i18n.t("ciclo.entrega_espera", idioma, tiempo="2:05")
    CON_MOTIVO = i18n.t("ciclo.entrega_motivo", idioma, motivo=MOTIVO)

    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        id: ventana
        width: %d; height: %d; visible: true
        color: Colores.fondoMarinoOscuro
        Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
        Binding { target: Escala; property: "altoLienzo"; value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor) }
        QtObject {
            id: comandos
            property bool ocupado: false
            property string error: ""
            property bool rolIngeniero: false
            function cancelar() {}
            function confirmar() {}
            function refrescarRol() {}
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
            property bool connected: true
            property string estadoModuloEs: "ok"
            property string cicloActivo: "03"
            property string programa: "BOWIE & DICK"
            property bool ackConfirmaEstadoSeguro: false
            property bool noAbrir: true
            property string noAbrirMotivo: ""
            property bool paroActivo: false
        }
        Item {
            width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoLienzo)
            anchors.centerIn: parent; clip: true
            PantallaCicloEnCurso {
                objectName: "pantalla"
                anchors.fill: parent
                comandos: comandos
                progreso: progresoFalso
                puente: puenteFalso
            }
        }
    }
    """ % (w, h)

    ruta = f"{QML_DIR}/_can_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    win = engine.rootObjects()[0]
    colores = engine.singletonInstance("Tema", "Colores")
    win.setFlags(win.flags() | Qt.FramelessWindowHint)
    win.setGeometry(0, 0, w, h)
    win.show()
    QTest.qWait(700)

    def obj(nombre, raiz=None):
        x = [o for o in (raiz or win).findChildren(QObject) if o.objectName() == nombre]
        return x[0] if x else None

    barra = obj("barraInferiorCicloEnCurso")
    desl = obj("deslizadorCancelarCiclo")
    manija = obj("manijaDeslizadorInicio", desl)
    progreso = obj("progresoFalso")

    def medidas(t):
        return {"texto": t.property("text"), "contentWidth": round(t.property("contentWidth"), 1),
                "width": round(t.property("width"), 1), "contentHeight": round(t.property("contentHeight"), 1),
                "height": round(t.property("height"), 1), "lineCount": t.property("lineCount"),
                "cabe": t.property("contentWidth") <= t.property("width") + 0.5
                        and t.property("contentHeight") <= t.property("height") + 0.5}

    def capturar(nombre, textos):
        QTest.qWait(500)
        p = barra.mapToScene(QPointF(0, 0))
        m = 30
        img = win.grabWindow().copy(QRect(int(p.x()) - m, int(p.y()) - m,
                                          int(barra.width()) + 2 * m, int(barra.height()) + 2 * m))
        img.save(os.path.join(destino, nombre))
        print("MEDIDAS=" + json.dumps({"captura": nombre, "textos": [medidas(t) for t in textos]},
                                      ensure_ascii=False))

    t_reposo = obj("textoDeslizadorInicio", desl)
    t_completado = obj("textoCompletadoDeslizadorInicio", desl)
    for tema in cfg["temas"]:
        colores.setProperty("oscuro", tema == "oscuro")
        manija.setProperty("x", desl.property("margen"))
        capturar(f"can_{tema}_{w}_{idioma}_reposo.png", [t_reposo, t_completado])
        medio = desl.property("margen") + (desl.property("maxX") - desl.property("margen")) * 0.5
        manija.setProperty("x", medio)
        capturar(f"can_{tema}_{w}_{idioma}_medio_arrastre.png", [t_reposo, t_completado])
        manija.setProperty("x", desl.property("maxX"))
        QTest.qWait(50)
        print("MEDIDAS=" + json.dumps({"captura": f"(extremo {tema} {w} {idioma})",
                                       "textos": [medidas(t_completado)]}, ensure_ascii=False))
        manija.setProperty("x", desl.property("margen"))

    if cfg["esp"]:
        colores.setProperty("oscuro", False)
        t_esp = obj("textoEntrega")
        progreso.setProperty("texto", CON_MOTIVO)
        progreso.setProperty("resultado", "fallo")
        progreso.setProperty("revisionFin", 1)
        capturar(f"esp_{w}_{idioma}_sin_motivo.png", [t_esp])
        progreso.setProperty("texto", ESPERA)
        progreso.setProperty("resultado", "exitoso")
        progreso.setProperty("revisionFin", 2)
        capturar(f"esp_{w}_{idioma}_espera_fija.png", [t_esp])
    win.close()
''')


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=str(DESTINO))
    a = ap.parse_args()
    Path(a.destino).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    env.pop("QT_QPA_PLATFORM", None)
    for ancho, alto in TAMANOS:
        for idioma in ("es", "en"):
            cfg = {"ancho": ancho, "alto": alto, "destino": a.destino, "idioma": idioma,
                   "temas": ["claro", "oscuro"], "esp": True}
            p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                               capture_output=True, text=True, encoding="utf-8", env=env,
                               cwd=RAIZ, timeout=300)
            print(p.stdout)
            if p.returncode != 0:
                print(p.stderr[-3000:], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
