from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, SubtitleLabel


class HomeView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        title = SubtitleLabel("MENÚ PRINCIPAL")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        cards_data = [
            (
                "⏱  Tiempo de Secado",
                "Ajusta el tiempo de secado del ciclo activo",
                "secado",
            ),
            (
                "🖨  Impresión General",
                "Imprime ciclos, alarmas y más",
                "impresion_menu",
            ),
            (
                "👤  Login",
                "Inicia sesión en el sistema",
                "login",
            ),
        ]

        grid = QGridLayout()
        grid.setSpacing(20)

        for idx, (title_text, desc_text, view_name) in enumerate(cards_data):
            card = self._make_card(title_text, desc_text, view_name)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)

        # Centrar la tercera card si hay número impar
        if len(cards_data) % 2 == 1:
            last_row = len(cards_data) // 2
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper.setLayout(grid)
        layout.addWidget(wrapper, stretch=1)

    def _make_card(self, title_text: str, desc_text: str, view_name: str) -> CardWidget:
        card = CardWidget()
        card.setMinimumSize(280, 140)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(24, 20, 24, 20)
        inner.setSpacing(8)

        lbl_title = SubtitleLabel(title_text)
        lbl_desc  = BodyLabel(desc_text)
        lbl_desc.setWordWrap(True)

        inner.addWidget(lbl_title)
        inner.addWidget(lbl_desc)
        inner.addStretch()

        # Capturar view_name en el closure con argumento default
        card.mousePressEvent = lambda e, vn=view_name: self._nav(vn)

        return card
