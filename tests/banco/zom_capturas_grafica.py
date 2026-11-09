# tests/banco/zom_capturas_grafica.py
#
# Tanda 34 (ZOM-08): capturas de la gráfica del ciclo con zoom (15–25 min,
# 110–135 en el eje izquierdo) y la lupa indicadora, en tema claro y oscuro,
# a 1080 px (1080 x 1728) y a 1024 px (1024 x 1638), en
# docs/informes/tanda34/capturas/ con prefijo zom_. No es una prueba
# automática: Cristian las revisa a ojo. Usa la plataforma real (no offscreen):
# la lupa se dibuja con IconoColor (MultiEffect), que offscreen no se pinta.
#
#   python tests/banco/zom_capturas_grafica.py
#
# Fija PYTHONPATH al `src` de este árbol para usar el código de este checkout.

import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "informes" / "tanda34" / "capturas"

_SCRIPT = textwrap.dedent(r'''
    import os, sys
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401  (tipos de los objetos QML)
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave import i18n
    raiz, destino = sys.argv[1], sys.argv[2]
    assert os.path.normcase(QML_DIR).startswith(os.path.normcase(raiz)), (QML_DIR, raiz)
    i18n.fijar_idioma("es")
    qapp = QGuiApplication([])
    _cargar_fuentes()
    for tema in ("claro", "oscuro"):
        for ancho, alto in ((1080, 1728), (1024, 1638)):
            engine = QQmlApplicationEngine()
            engine.warnings.connect(lambda ws: [print("AVISO QML:", x.toString(), file=sys.stderr) for x in ws])
            engine.addImportPath(QML_DIR)
            engine.setInitialProperties({"zoomGrafica": True})
            engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaCicloEnCurso.qml"))
            if tema == "oscuro":
                engine.singletonInstance("Tema", "Colores").setProperty("oscuro", True)
            w = engine.rootObjects()[0]
            w.setFlags(w.flags() | Qt.FramelessWindowHint)
            w.setGeometry(0, 0, ancho, alto)
            w.show()
            QTest.qWait(900)
            g = [o for o in w.findChildren(QObject) if o.objectName() == "graficaCicloEnCurso"][0]
            lupa = [o for o in w.findChildren(QObject) if o.objectName() == "lupaZoomGrafica"][0]
            assert g.property("zoomActivo") and lupa.property("visible"), "sin zoom"
            img = w.grabWindow()
            base = f"zom_grafica_ampliada_{tema}_{ancho}"
            img.save(os.path.join(destino, base + ".png"))
            p = g.mapToScene(g.boundingRect().topLeft())
            img.copy(int(p.x()), int(p.y()), int(g.width()), int(g.height())).save(
                os.path.join(destino, base + "_tarjeta.png"))
            print("captura", base)
            w.close()
            engine.deleteLater()
            QTest.qWait(50)
''')


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    env = {**os.environ,
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ),
           "QT_ENABLE_HIGHDPI_SCALING": "0"}
    env.pop("QT_QPA_PLATFORM", None)   # plataforma real
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(RAIZ), str(DESTINO)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=600)
    print(p.stdout)
    if p.returncode != 0 or p.stderr.strip():
        print(p.stderr, file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
