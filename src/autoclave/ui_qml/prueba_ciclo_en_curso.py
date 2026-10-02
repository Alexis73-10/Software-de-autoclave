# ui_qml/prueba_ciclo_en_curso.py
#
# PRUEBA (Fase 2 de planeacion_pantalla_ciclo_en_curso.md): abre
# qml/Pruebas/PruebaCicloEnCurso.qml, la pantalla de ciclo en curso con datos de
# ejemplo, para la revisión visual frente al mockup. No forma parte de la app ni
# de la navegación de producción; no se conecta al backend.
#
#   python -m autoclave.ui_qml.prueba_ciclo_en_curso                    (600x960, 5:8)
#   python -m autoclave.ui_qml.prueba_ciclo_en_curso --ancho 540        (540x960, 9:16)
#   python -m autoclave.ui_qml.prueba_ciclo_en_curso --completa [--screen 1]
#   python -m autoclave.ui_qml.prueba_ciclo_en_curso --ancho 1200 --alto 1920 --captura salida.png

import argparse
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (rootObjects() -> QQuickWindow.grabWindow)

from autoclave.ui_qml.app import (QML_DIR, _cargar_fuentes, cargar_textos, elegir_pantalla,
                                  forzar_tema_claro)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PRUEBA: pantalla de ciclo en curso")
    parser.add_argument("--ancho", type=int, default=600, help="Ancho de la ventana")
    parser.add_argument("--alto", type=int, default=960, help="Alto de la ventana")
    parser.add_argument("--completa", action="store_true", help="Pantalla completa")
    parser.add_argument("--screen", type=int, default=0, help="Índice del monitor")
    parser.add_argument("--captura", help="Guarda un PNG de la ventana y sale")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"textosJson": cargar_textos()})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaCicloEnCurso.qml"))
    if not engine.rootObjects():
        return 1
    ventana = engine.rootObjects()[0]
    ventana.setWidth(args.ancho)
    ventana.setHeight(args.alto)
    if args.completa:
        pantalla = elegir_pantalla(app.screens(), args.screen, app.primaryScreen())
        ventana.setScreen(pantalla)
        ventana.setGeometry(pantalla.geometry())
        ventana.showFullScreen()
    if args.captura:
        def capturar():
            ventana.grabWindow().save(args.captura)
            app.quit()
        QTimer.singleShot(1500, capturar)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
