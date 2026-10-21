# ui_qml/app.py
#
# Punto de entrada de la UI QML (F1 de planeacion_migracion_qml.md):
#   python -m autoclave.ui_qml.app --door N --screen I
#
# Solo se conecta al backend en BACKEND_URL; no lo arranca ni lo apaga. Los
# únicos comandos que envía son abrir/cerrar la puerta de esta ventana, iniciar
# ciclo (con LISTO_PARA_CICLO) y, desde la pantalla de ciclo en curso,
# cancelar (con confirmación) y confirmar el fin del ciclo; no toca salidas.
# La sesión de la ventana (login, logout, cambio de contraseña, crear
# usuarios) va contra /auth/* y /usuarios con su token (sesion_backend, T-8);
# al salir se cierra con /auth/logout.
# El backend se lanza aparte con `python -m autoclave.backend.main`.
# Sin tarjeta, AUTOCLAVE_BACKEND_URL=http://127.0.0.1:8001 apunta la UI al backend
# simulado (`python -m autoclave.simulador`, herramienta de desarrollo).

import argparse
import logging
import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from autoclave import i18n
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.services.domain.puertas.door_command_service import DoorCommandService
from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge
from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo
from autoclave.ui_qml.bridge.comandos_falla import ComandoReconocerFalla
from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso
from autoclave.ui_qml.bridge.comandos_puerta import ComandosPuerta
from autoclave.ui_qml.bridge.selector_ciclo import SelectorCiclo
from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema
from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion, requiere_instalacion
from autoclave.ui_qml.bridge.info_equipo import InfoEquipo, cargar_perfil, version_software
from autoclave.ui_qml.bridge.lanzador_ajustes import LanzadorAjustes
from autoclave.ui_qml.bridge.progreso_arranque import (
    ProgresoArranqueBackend, SimuladorProgresoArranque, parse_simulacion,
)
from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo
from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema
from autoclave.ui_qml.bridge.standby import Standby
from autoclave.ui_qml.bridge.ui_bridge import UiBridge
from autoclave.ui_qml import sesion_backend
# Registra el singleton de textos I18n en Autoclave.I18n (al importar); lo usan
# todas las pantallas QML.
from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
# U1 (tanda 5): singleton Unidades en Autoclave.Unidades
from autoclave.ui_qml.bridge import unidades_qml  # noqa: F401
# Registran los controladores de los teclados en Autoclave.Controllers
# (qmlRegisterType al importar); los usa PanelTeclado de Main.qml.
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

# 127.0.0.1 y no "localhost": en Windows "localhost" se prueba primero como IPv6
# (::1), donde el backend no escucha, y cada petición tardaba 0.8–2 s.
BACKEND_URL = "http://127.0.0.1:8000"


def url_backend(entorno=os.environ) -> str:
    """BACKEND_URL, o AUTOCLAVE_BACKEND_URL si está definida (p. ej. el simulador)."""
    return (entorno.get("AUTOCLAVE_BACKEND_URL") or "").strip() or BACKEND_URL

QML_DIR = resource_path("autoclave/ui_qml/qml")
FUENTES_DIR = resource_path("autoclave/ui_qml/assets/fuentes")


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


def _abrir_instalacion(app: QGuiApplication, args) -> int:
    puente_instalacion = PuenteInstalacion()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puenteInstalacion": puente_instalacion})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/InstalacionVentana.qml"))
    if not engine.rootObjects():
        logger.error("No se pudo cargar %s/InstalacionVentana.qml", QML_DIR)
        return 1
    ventana = engine.rootObjects()[0]
    pantalla = elegir_pantalla(app.screens(), args.screen, app.primaryScreen())
    ventana.setScreen(pantalla)
    ventana.setGeometry(pantalla.geometry())
    ventana.showFullScreen()
    ventana.requestActivate()
    logger.warning("Sin perfil de instalación: se abre el asistente de instalación")
    return app.exec()


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)

    # Sin catálogos de textos (es/en) la UI no arranca
    i18n.cargar()
    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()

    # T9 (ARR-02 / MIG-07): sin perfil de instalación (o inválido), la ventana
    # principal abre el asistente en lugar del menú; la puerta 2 sigue al
    # menú, donde el arranque informa ARR_PERFIL
    if args.door == 1 and requiere_instalacion():
        return _abrir_instalacion(app, args)

    backend = BackendClient(url_backend())

    # Intro de arranque: sigue las etapas reales del backend (GET /arranque),
    # en paralelo con todo lo demás; no espera ni condiciona nada. Con
    # AUTOCLAVE_INTRO_SIMULACION, el simulador de tiempos fijos (pruebas).
    simulacion = os.environ.get("AUTOCLAVE_INTRO_SIMULACION")
    if simulacion:
        progreso_arranque = SimuladorProgresoArranque(**parse_simulacion(simulacion))
    else:
        progreso_arranque = ProgresoArranqueBackend(lambda: backend.get("/arranque"))
    progreso_arranque.iniciar()
    version = version_software()

    ui_service = UIServiceBackend(backend)
    puente = UiBridge(ui_service, door=args.door)
    comandos_puerta = ComandosPuerta(
        puente, DoorCommandService(backend_client=backend, source_door=args.door))
    comando_ciclo = ComandoIniciarCiclo(puente, ui_service)
    selector_ciclo = SelectorCiclo(backend, door=args.door, ui_service=ui_service)   # B6: cambio de programa en Preciclo
    comando_falla = ComandoReconocerFalla(puente, ui_service)   # T-16
    # E5: Confirmar y llevar a estado seguro; Apagar equipo (solo puerta 1)
    comandos_sistema = ComandosSistema(puente, ui_service, args.door)
    info_equipo = InfoEquipo(cargar_perfil(), args.door, backend, version)
    ajustes = LanzadorAjustes()
    standby = Standby(ui_service, backend, mantener_despierto=lambda: ajustes.abierto)
    progreso = ProgresoCiclo(backend)
    comandos_en_curso = ComandosCicloEnCurso(puente, ui_service)
    # Resumen del Sistema del Menú Principal: solo lectura; sondea solo mientras el menú está visible
    resumen = ResumenSistema(backend)
    # Listados de Ciclos hoy e Historial del menú: solo lectura, bajo demanda
    historial = CiclosHistorial(backend)
    # Historial: reimprimir en la térmica o enviar por correo los ciclos marcados
    acciones = AccionesCiclos(backend)
    # Reportes: resumen de ciclos por periodo, solo lectura, bajo demanda
    reporte = ReporteResumen(backend)
    # Sesión de esta ventana contra el backend (token solo en memoria) y el
    # puente de Nuevo usuario de OPCIONES › Usuarios, que escribe con ese token
    sesion = sesion_backend.SesionVentana()
    sesion_backend.instalar(sesion)
    puente_nuevo_usuario = NuevoUsuarioBridge(sesion=sesion)

    def _al_salir():
        puente.detener()
        standby.detener()
        progreso.detener()
        resumen.detener()
        ajustes.cerrar()
        progreso_arranque.detener()
        sesion.cerrar_al_salir()   # /auth/logout con plazo corto (decisión 31)
        ui_service.stop()   # solo detiene el hilo de lectura; no toca salidas ni backend

    app.aboutToQuit.connect(_al_salir)

    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)   # visibiliza el módulo "Tema"
    engine.setInitialProperties({
        "puente": puente,
        "comandosPuerta": comandos_puerta,
        "comandoCiclo": comando_ciclo,
        "selectorCiclo": selector_ciclo,
        "comandoFalla": comando_falla,
        "comandosSistema": comandos_sistema,
        "infoEquipo": info_equipo,
        "ajustes": ajustes,
        "standby": standby,
        "progreso": progreso,
        "comandosCicloEnCurso": comandos_en_curso,
        "resumen": resumen,
        "historial": historial,
        "acciones": acciones,
        "reporte": reporte,
        "sesion": sesion,
        "puenteNuevoUsuario": puente_nuevo_usuario,
        "progresoArranque": progreso_arranque,
        "versionSoftware": version or "",
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
    # Solo la puerta 1 pide el foco: si ambas ventanas (procesos distintos) lo
    # piden, Windows se lo niega a una y hace parpadear su icono, lo que saca
    # la barra de tareas sobre la pantalla completa. La otra lo toma al tocarla.
    if args.door == 1:
        ventana.requestActivate()   # foco de teclado (login) aunque se lance desde una terminal
    ventana.installEventFilter(standby)   # todo toque/tecla de esta ventana cuenta como actividad
    ventana.installEventFilter(sesion)    # y mantiene viva la sesión de esta ventana (SAF-01)
    ajustes.ventana = ventana
    logger.info("UI QML iniciada — puerta %d, monitor %s", args.door, pantalla.name())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
