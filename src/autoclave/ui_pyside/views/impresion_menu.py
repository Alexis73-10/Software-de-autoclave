from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, QMarginsF, QSizeF
from PySide6.QtGui import QFont, QPainter, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from autoclave.ui.service_ui.backend_client import BackendClient

_PRINT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("📋", "Imprimir Ciclos",  "ciclos"),
    ("🚨", "Imprimir Alarmas", None),
]

_BACKEND_URL = "http://localhost:8000"

_PAPER_W_MM  = 55.0
_MARGIN_H_MM = 2.0
_MARGIN_V_MM = 3.0
_FONT_PT     = 7
_FONT_FAMILY = "Courier New"

_BTN_OPTION = """
    QPushButton {{
        background: {bg};
        color: #1a2a3a;
        border-radius: 12px;
        border: 1.5px solid #e8eaed;
        text-align: left;
        padding-left: 16px;
        font-size: 14px;
    }}
    QPushButton:hover   {{ background: #e8f0fe; border-color: #2563eb; }}
    QPushButton:pressed {{ background: #dbeafe; }}
"""

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""


def _build_alarms_ticket_lines(alarms: list[dict]) -> list[str]:
    now = datetime.now()
    lines: list[str] = [
        "------------------------",
        "ALARMAS ACTIVAS",
        f"Fecha: {now.strftime('%d/%m/%Y')}",
        f"Hora:  {now.strftime('%H:%M:%S')}",
        "------------------------",
    ]
    for alarma in alarms:
        lines += [
            f"ID: {alarma.get('id', '')}",
            f"Nivel: {alarma.get('level', '')}",
            f"Origen: {alarma.get('source_state', '')}",
            alarma.get("description") or "",
            "------------------------",
        ]
    lines.append(f"Total: {len(alarms)} alarma(s)")
    lines.append("------------------------")
    return lines


def _wrap(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


def _draw_ticket_lines(printer: QPrinter, lines: list[str]) -> None:
    painter = QPainter(printer)
    font = QFont(_FONT_FAMILY, _FONT_PT)
    painter.setFont(font)
    fm = painter.fontMetrics()

    page_rect  = printer.pageRect(QPrinter.Unit.DevicePixel)
    char_w     = fm.horizontalAdvance("M")
    chars_line = max(20, int(page_rect.width() // char_w))
    line_h     = fm.lineSpacing() + 1

    y = page_rect.top() + fm.ascent()
    for raw in lines:
        for seg in _wrap(raw, chars_line):
            painter.drawText(int(page_rect.left()), int(y), seg)
            y += line_h

    painter.end()


class ImpresionMenuView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)

        self.setStyleSheet("""
            ImpresionMenuView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("printCard")
        card.setStyleSheet("QFrame#printCard { background: white; border-radius: 20px; }")
        card.setMaximumWidth(460)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(10)

        top_row = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("home"))
        top_row.addWidget(btn_back)
        top_row.addSpacing(8)
        lbl_sub = QLabel("Menú Principal")
        lbl_sub.setFont(QFont("Segoe UI", 13))
        lbl_sub.setStyleSheet("color: #555; background: transparent;")
        top_row.addWidget(lbl_sub)
        top_row.addStretch()
        cl.addLayout(top_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        cl.addWidget(sep)

        title = QLabel("IMPRESIÓN GENERAL")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a2a3a; background: transparent;")
        cl.addWidget(title)
        cl.addSpacing(4)

        for icon, label, target in _PRINT_OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION.format(bg="#f8f9fa"))
            if target is not None:
                btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            else:
                btn.clicked.connect(self._print_alarms)
            cl.addWidget(btn)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch(1)

    # ── Impresión de alarmas ──────────────────────────────────────────

    def _print_alarms(self) -> None:
        try:
            status = self._client.get_status()
            alarms = status.get("alarms", [])
        except Exception:
            alarms = []

        if not alarms:
            QMessageBox.information(self, "Alarmas", "No hay alarmas activas.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(
            QPageSize(QSizeF(_PAPER_W_MM, 297.0), QPageSize.Unit.Millimeter)
        )
        printer.setPageMargins(
            QMarginsF(_MARGIN_H_MM, _MARGIN_V_MM, _MARGIN_H_MM, _MARGIN_V_MM),
            QPageLayout.Unit.Millimeter,
        )
        if QPrintDialog(printer, self).exec() != QPrintDialog.DialogCode.Accepted:
            return

        _draw_ticket_lines(printer, _build_alarms_ticket_lines(alarms))
