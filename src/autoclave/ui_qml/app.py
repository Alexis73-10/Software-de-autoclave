# ui_qml/app.py
#
# Punto de entrada de la UI QML en modo desarrollo (§8.2 del plan de
# interfaz dual-pantalla): ventana a escala reducida (scale=0.5 por
# defecto) en vez de pantalla completa sobre el QScreen resuelto por el
# lanzador — permite ejecutar la UI sin los paneles Faytech reales, sin
# depender de V-UI-01 (verificación de hardware, aún abierta). `--door`/
# `--screen` del contrato de línea de comandos del lanzador (§4.3) no se
# agregan aquí todavía: ninguna pantalla existente los necesita
# (PantallaInicio no muestra identidad de puerta).
#
# El tamaño de lienzo (Tokens.layout.canvas) no se duplica aquí como
# constante: se lee del propio ContenedorEscalado ya cargado
# (Main.qml le da objectName "contenedor") para que cambiarlo en
# tokens.json sea suficiente en toda la cadena.
#
# Uso: python -m autoclave.ui_qml.app [--dev] [--scale <f>]

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

import autoclave.ui_qml.design.register  # noqa: F401  (registra el singleton Tokens)
import autoclave.ui_qml.controllers.reloj_splash_controller  # noqa: F401  (registra tipos QML)

_MAIN_QML = Path(__file__).parent / "Main.qml"


def _parsear_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--scale", type=float, default=0.5)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parsear_args(argv if argv is not None else sys.argv[1:])

    app = QGuiApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    engine.load(str(_MAIN_QML))
    if not engine.rootObjects():
        return 1

    ventana = engine.rootObjects()[0]
    if args.dev:
        contenedor = ventana.findChild(QObject, "contenedor")
        lienzo_ancho = contenedor.property("lienzoAncho")
        lienzo_alto = contenedor.property("lienzoAlto")
        ventana.setWidth(int(lienzo_ancho * args.scale))
        ventana.setHeight(int(lienzo_alto * args.scale))
    else:
        ventana.showFullScreen()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
