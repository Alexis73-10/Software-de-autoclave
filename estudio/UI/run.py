# run.py    uso: python run.py archivo.qml
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.load(sys.argv[1])
if not engine.rootObjects():
    sys.exit(-1)
sys.exit(app.exec())