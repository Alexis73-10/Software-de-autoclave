# ui_qml/prueba_menu_principal.py
#
# PRUEBA (planeacion_menu_principal_ui_qml.md): abre la galería de componentes
# del Menú Principal (qml/Pruebas/GaleriaMenuPrincipal.qml, Fase 1) o la pantalla
# completa en su arnés (qml/Pruebas/PruebaMenuPrincipal.qml, Fase 3). No forma
# parte de la app ni de la navegación de producción (Fase 4 diferida).
#
#   python -m autoclave.ui_qml.prueba_menu_principal                       galería (600x960)
#   python -m autoclave.ui_qml.prueba_menu_principal --pantalla            pantalla, datos de ejemplo
#   python -m autoclave.ui_qml.prueba_menu_principal --pantalla --backend  datos reales del backend
#
# Con --backend, Imprimir y Enviar por correo del Historial son REALES (impresora
# térmica del backend y correo con config/correo.json). Sin él, el Historial usa
# un backend simulado (historial_ejemplo.py): no imprime ni envía nada.
#   python -m autoclave.ui_qml.prueba_menu_principal --pantalla --ventana ultimo_ciclo
#   python -m autoclave.ui_qml.prueba_menu_principal --pantalla --sin-conexion
#   python -m autoclave.ui_qml.prueba_menu_principal --pantalla --ancho 1196 --alto 1917 --captura menu.png
#
# Captura: ventana sin marco (Windows no la recorta al monitor, a diferencia de
# una con marco) del tamaño pedido, reducida a ese tamaño lógico si el monitor
# tiene escala (p. ej. 125 %). Debe tomarse con la plataforma real: con
# QT_QPA_PLATFORM=offscreen MultiEffect no se dibuja y los iconos de color
# (IconoColor) quedan invisibles.

import argparse
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (rootObjects() -> QQuickWindow.grabWindow)

from autoclave.ui_qml.app import (BACKEND_URL, QML_DIR, _cargar_fuentes, cargar_textos,
                                  forzar_tema_claro)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PRUEBA: Menú Principal")
    parser.add_argument("--pantalla", action="store_true",
                        help="Pantalla completa en su arnés (por defecto: galería de componentes)")
    parser.add_argument("--backend", action="store_true",
                        help="Con --pantalla: datos reales del backend en BACKEND_URL (solo lectura)")
    parser.add_argument("--ventana", choices=("ultimo_ciclo", "mantenimiento", "ciclos_hoy", "historial",
                                              "reportes"),
                        help="Con --pantalla: abre esa ventana flotante al iniciar")
    parser.add_argument("--sin-conexion", action="store_true",
                        help="Con --pantalla y datos de ejemplo: simula el backend sin respuesta")
    parser.add_argument("--door", type=int, choices=(1, 2), default=1, help="Puerta (con --backend)")
    parser.add_argument("--ancho", type=int, default=None, help="Ancho de la ventana")
    parser.add_argument("--alto", type=int, default=None, help="Alto de la ventana")
    parser.add_argument("--captura", help="Guarda un PNG de la ventana y sale")
    args = parser.parse_args(argv)
    # con captura, por defecto el lienzo de diseño completo
    ancho = args.ancho or (1200 if args.captura else 600)
    alto = args.alto or (1920 if args.captura else 960)

    app = QGuiApplication(sys.argv[:1])
    forzar_tema_claro(app)
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    textos = cargar_textos()
    propiedades = {"textosJson": textos}
    archivo = "GaleriaMenuPrincipal.qml"
    if args.pantalla:
        archivo = "PruebaMenuPrincipal.qml"
        propiedades.update({"ventanaInicial": args.ventana or "",
                            "sinConexionEjemplo": args.sin_conexion})
        if args.backend:
            from autoclave.ui.service_ui.backend_client import BackendClient
            from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
            from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
            from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
            from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
            from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema
            from autoclave.ui_qml.bridge.ui_bridge import UiBridge
            backend = BackendClient(BACKEND_URL)
            ui_service = UIServiceBackend(backend)
            propiedades.update({
                "puente": UiBridge(ui_service, door=args.door),
                "resumen": ResumenSistema(backend),
                "historial": CiclosHistorial(backend),
                "acciones": AccionesCiclos(backend, textos),
                "reporte": ReporteResumen(backend),
            })
            app.aboutToQuit.connect(ui_service.stop)
        else:
            from autoclave.ui_qml import historial_ejemplo as ejemplo
            from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
            from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
            from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen
            backend = ejemplo.BackendEjemplo(sin_conexion=args.sin_conexion)
            propiedades.update({
                "historial": CiclosHistorial(backend),
                "acciones": AccionesCiclos(backend, textos, cargar_config=ejemplo.config_correo_ejemplo,
                                           enviar=ejemplo.enviar_ejemplo),
                "reporte": ReporteResumen(backend),
            })
    engine.setInitialProperties(propiedades)
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/{archivo}"))
    if not engine.rootObjects():
        return 1
    ventana = engine.rootObjects()[0]

    if args.captura:
        ventana.setFlags(ventana.flags() | Qt.WindowType.FramelessWindowHint)
        ventana.setGeometry(0, 0, ancho, alto)

        def capturar():
            imagen = ventana.grabWindow()
            if imagen.width() != ancho:
                imagen = imagen.scaled(ancho, alto, Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            app.exit(0 if imagen.save(args.captura) else 1)
        QTimer.singleShot(1200, capturar)
    else:
        ventana.setWidth(ancho)
        ventana.setHeight(alto)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
