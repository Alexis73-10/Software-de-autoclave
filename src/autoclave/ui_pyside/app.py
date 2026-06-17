import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from autoclave.ui_pyside.main_window import MainWindowFluent


def main():
    app = QApplication(sys.argv)
    window = MainWindowFluent()
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
    )
    window.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
