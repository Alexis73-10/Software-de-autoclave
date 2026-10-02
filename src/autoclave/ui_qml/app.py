# ui_qml/app.py
#
# Punto de entrada de la UI QML (F1 de planeacion_migracion_qml.md):
#   python -m autoclave.ui_qml.app --door N --screen I
#
# Solo se conecta al backend en BACKEND_URL; no lo arranca ni lo apaga. Los
# únicos comandos que envía son abrir/cerrar la puerta de esta ventana e
# iniciar ciclo (misma lógica que tkinter); no toca salidas. El backend se
# lanza aparte con `python -m autoclave.backend.main`.

import argparse
import json
import logging
import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.services.domain.puertas.door_command_service import DoorCommandService
from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo
from autoclave.ui_qml.bridge.comandos_puerta import ComandosPuerta
from autoclave.ui_qml.bridge.info_equipo import InfoEquipo, cargar_perfil, version_software
from autoclave.ui_qml.bridge.lanzador_ajustes import LanzadorAjustes
from autoclave.ui_qml.bridge.standby import Standby
from autoclave.ui_qml.bridge.ui_bridge import UiBridge
# Registran los controladores de los teclados en Autoclave.Controllers
# (qmlRegisterType al importar); los usa PanelTeclado de Main.qml.
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"

QML_DIR = resource_path("autoclave/ui_qml/qml")
FUENTES_DIR = resource_path("autoclave/ui_qml/assets/fuentes")
TEXTOS_ES = resource_path("autoclave/ui_qml/assets/textos/es.json")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Autoclave — interfaz de operador (QML)")
    parser.add_argument("--door", type=int, choices=(1, 2), default=None,
                        help="Puerta que representa esta ventana (defecto: 1)")
    parser.add_argument("--screen", type=int, default=0,
                        help="Índice del monitor en QGuiApplication.screens() (defecto: 0)")
    args = parser.parse_args(argv)
    if args.door is None:
        # --screen solo elige el monitor: la puerta NO se deduce de él
        logger.warning("Sin --door: esta ventana representa la PUERTA 1 (monitor %d)", args.screen)
        args.door = 1
    return args


def elegir_pantalla(pantallas, indice: int, primaria):
    """Pantalla por índice; si no existe, la primaria (y se registra aviso)."""
    if 0 <= indice < len(pantallas):
        return pantallas[indice]
    logger.warning("Monitor %d no existe (%d detectados) — se usa el primario",
                   indice, len(pantallas))
    return primaria


def cargar_textos(ruta: str = TEXTOS_ES) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _cargar_fuentes() -> None:
    if not os.path.isdir(FUENTES_DIR):
        logger.warning("Carpeta de fuentes no encontrada: %s", FUENTES_DIR)
        return
    for nombre in os.listdir(FUENTES_DIR):
        if nombre.lower().endswith(".otf"):
            QFontDatabase.addApplicationFont(os.path.join(FUENTES_DIR, nombre))


def forzar_tema_claro(app: QGuiApplication) -> None:
    """La UI usa siempre el tema claro del diseñador, aunque Windows esté en
    modo oscuro. Sin esto, los controles estándar de Qt (TextField, etc.)
    toman la paleta oscura del sistema y, por ejemplo, pintan el texto en
    blanco sobre los campos blancos."""
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()

    backend = BackendClient(BACKEND_URL)
    ui_service = UIServiceBackend(backend)
    puente = UiBridge(ui_service, door=args.door)
    comandos_puerta = ComandosPuerta(
        puente, DoorCommandService(backend_client=backend, source_door=args.door))
    comando_ciclo = ComandoIniciarCiclo(puente, ui_service)
    info_equipo = InfoEquipo(cargar_perfil(), args.door, backend, version_software())
    ajustes = LanzadorAjustes()
    standby = Standby(ui_service, backend, mantener_despierto=lambda: ajustes.abierto)

    def _al_salir():
        puente.detener()
        standby.detener()
        ajustes.cerrar()
        ui_service.stop()   # solo detiene el hilo de lectura; no toca salidas ni backend

    app.aboutToQuit.connect(_al_salir)

    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)   # visibiliza el módulo "Tema"
    engine.setInitialProperties({
        "puente": puente,
        "comandosPuerta": comandos_puerta,
        "comandoCiclo": comando_ciclo,
        "infoEquipo": info_equipo,
        "ajustes": ajustes,
        "standby": standby,
        "textosJson": cargar_textos(),
    })
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Main.qml"))
    if not engine.rootObjects():
        logger.error("No se pudo cargar %s/Main.qml", QML_DIR)
        _al_salir()
        return 1

    ventana = engine.rootObjects()[0]
    pantalla = elegir_pantalla(app.screens(), args.screen, app.primaryScreen())
    ventana.setScreen(pantalla)
    ventana.setGeometry(pantalla.geometry())
    ventana.showFullScreen()
    ventana.requestActivate()   # foco de teclado (login) aunque se lance desde una terminal
    ventana.installEventFilter(standby)   # todo toque/tecla de esta ventana cuenta como actividad
    ajustes.ventana = ventana
    logger.info("UI QML iniciada — puerta %d, monitor %s", args.door, pantalla.name())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
