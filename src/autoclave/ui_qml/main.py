import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

BASE_DIR = Path(__file__).resolve().parent
QML_DIR = BASE_DIR / "qml"
FUENTES_DIR = BASE_DIR / "assets" / "fuentes"


def _cargar_fuentes() -> None:
    """Carga los .otf de Montserrat si la carpeta existe y tiene archivos."""
    if not FUENTES_DIR.exists():
        return
    for archivo in FUENTES_DIR.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(archivo))


def main() -> int:
    app = QGuiApplication(sys.argv)
    _cargar_fuentes()

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))  # visibiliza el módulo "Tema"
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
