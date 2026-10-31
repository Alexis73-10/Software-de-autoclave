# tools/demos_qml/prueba_instalacion.py (antes ui_qml/prueba_instalacion.py; ORG-10, tanda 15)
#
# PRUEBA DESECHABLE (planeacion_menu_instalacion_ui.md): abre
# qml/Pruebas/PruebaInstalacion.qml, el asistente de instalación con un puente
# de EJEMPLO (no escribe installation_profile.json ni se conecta al backend).
# Código de activación aceptado por el puente de ejemplo: ABCDEFGHIJKL.
#
#   python tools/demos_qml/prueba_instalacion.py              (ventana 600x960)
#   python tools/demos_qml/prueba_instalacion.py --completa [--screen 1]

import argparse
import sys
from pathlib import Path

# ORG-10 (tanda 15): demo fuera del paquete; el paquete autoclave se toma
# de src/; se lanza desde la raíz del repositorio, como antes con -m (QML_DIR
# sigue resolviendo src/autoclave/ui_qml/qml)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication 
from PySide6.QtQml import QQmlApplicationEngine

# Registran los controladores en Autoclave.Controllers (qmlRegisterType al importar)
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
from autoclave.ui_qml.app import (QML_DIR, _cargar_fuentes, elegir_pantalla,
                                  forzar_tema_claro)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PRUEBA: asistente de instalación QML")
    parser.add_argument("--completa", action="store_true", help="Pantalla completa")
    parser.add_argument("--screen", type=int, default=0, help="Índice del monitor")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaInstalacion.qml"))
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
