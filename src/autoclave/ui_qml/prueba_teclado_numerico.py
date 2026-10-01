# ui_qml/prueba_teclado_numerico.py
#
# PRUEBA DESECHABLE (planeacion_teclados_qml.md, Paso 3): abre
# qml/Pruebas/PruebaTecladoNumerico.qml, el teclado numérico anclado al pie
# (mínimo -100, máximo 400, 1 decimal). No forma parte de la app ni de la
# navegación de producción; no se conecta al backend. Borrar al terminar.
#
#   python -m autoclave.ui_qml.prueba_teclado_numerico              (ventana 600x960)
#   python -m autoclave.ui_qml.prueba_teclado_numerico --completa   (pantalla completa)
#   python -m autoclave.ui_qml.prueba_teclado_numerico --completa --screen 1

import argparse
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

# Registra TecladoNumericoController en Autoclave.Controllers (qmlRegisterType al importar)
from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos, elegir_pantalla


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PRUEBA: teclado numérico QML")
    parser.add_argument("--completa", action="store_true", help="Pantalla completa")
    parser.add_argument("--screen", type=int, default=0, help="Índice del monitor")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"textosJson": cargar_textos()})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaTecladoNumerico.qml"))
    if not engine.rootObjects():
        return 1
    ventana = engine.rootObjects()[0]
    if args.completa:
        pantalla = elegir_pantalla(app.screens(), args.screen, app.primaryScreen())
        ventana.setScreen(pantalla)
        ventana.setGeometry(pantalla.geometry())
        ventana.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
