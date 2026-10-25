# tools/demos_qml/prueba_ciclo_en_curso.py (antes ui_qml/prueba_ciclo_en_curso.py; ORG-10, tanda 15)
#
# PRUEBA (Fase 2 de planeacion_pantalla_ciclo_en_curso.md): abre
# qml/Pruebas/PruebaCicloEnCurso.qml, la pantalla de ciclo en curso con datos de
# ejemplo, para la revisión visual frente al mockup; con --backend, la misma
# pantalla con datos reales del backend (solo lectura, sin comandos). No forma
# parte de la app ni de la navegación de producción.
#
#   python tools/demos_qml/prueba_ciclo_en_curso.py                    (600x960, 5:8)
#   python tools/demos_qml/prueba_ciclo_en_curso.py --ancho 540        (540x960, 9:16)
#   python tools/demos_qml/prueba_ciclo_en_curso.py --completa [--screen 1]
#   python tools/demos_qml/prueba_ciclo_en_curso.py --ancho 1200 --alto 1920 --captura salida.png
#   python tools/demos_qml/prueba_ciclo_en_curso.py --backend          (backend en BACKEND_URL
#                                                                        o AUTOCLAVE_BACKEND_URL)

import argparse
import sys
from pathlib import Path

# ORG-10 (tanda 15): demo fuera del paquete; el paquete autoclave se toma
# de src/; se lanza desde la raíz del repositorio, como antes con -m (QML_DIR
# sigue resolviendo src/autoclave/ui_qml/qml)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (rootObjects() -> QQuickWindow.grabWindow)

from autoclave.ui_qml.app import (QML_DIR, _cargar_fuentes, elegir_pantalla,
                                  forzar_tema_claro, url_backend)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PRUEBA: pantalla de ciclo en curso")
    parser.add_argument("--ancho", type=int, default=600, help="Ancho de la ventana")
    parser.add_argument("--alto", type=int, default=960, help="Alto de la ventana")
    parser.add_argument("--completa", action="store_true", help="Pantalla completa")
    parser.add_argument("--screen", type=int, default=0, help="Índice del monitor")
    parser.add_argument("--captura", help="Guarda un PNG de la ventana y sale")
    parser.add_argument("--backend", action="store_true", help="Datos reales del backend")
    parser.add_argument("--door", type=int, choices=(1, 2), default=1, help="Puerta (con --backend)")
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    propiedades = {}
    archivo = "PruebaCicloEnCurso.qml"
    if args.backend:
        from autoclave.cliente.backend_client import BackendClient
        from autoclave.cliente.ui_service_backend import UIServiceBackend
        from autoclave.ui_qml.bridge.info_equipo import InfoEquipo, cargar_perfil, version_software
        from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo
        from autoclave.ui_qml.bridge.ui_bridge import UiBridge
        backend = BackendClient(url_backend())
        ui_service = UIServiceBackend(backend)
        propiedades.update({
            "puente": UiBridge(ui_service, door=args.door),
            "progreso": ProgresoCiclo(backend),
            "infoEquipo": InfoEquipo(cargar_perfil(), args.door, backend, version_software()),
        })
        app.aboutToQuit.connect(ui_service.stop)
        archivo = "PruebaCicloEnCursoBackend.qml"
    engine.setInitialProperties(propiedades)
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/{archivo}"))
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
