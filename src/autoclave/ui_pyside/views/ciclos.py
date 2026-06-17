from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CalendarPicker,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TableWidget,
)


class CiclosView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Barra superior
        header_row = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header_row.addWidget(btn_back)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(SubtitleLabel("Historial de Ciclos"))

        # Filtro de fecha
        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("Desde:"))
        self._desde = CalendarPicker()
        self._desde.setDate(QDate.currentDate().addDays(-30))
        filter_row.addWidget(self._desde)

        filter_row.addWidget(BodyLabel("Hasta:"))
        self._hasta = CalendarPicker()
        self._hasta.setDate(QDate.currentDate())
        filter_row.addWidget(self._hasta)

        btn_filter = PushButton("Filtrar")
        btn_filter.clicked.connect(self._load_data)
        filter_row.addWidget(btn_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Tabla
        self._table = TableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["#", "Programa", "Fecha inicio", "Duración (min)", "Resultado"]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        # Botón imprimir
        btn_print = PrimaryPushButton("Imprimir")
        btn_print.setFixedWidth(160)
        btn_print.clicked.connect(self._print_table)
        layout.addWidget(btn_print, alignment=Qt.AlignmentFlag.AlignRight)

        self._load_data()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_data()

    def _load_data(self) -> None:
        from autoclave.services.domain.logging.db_manager import DbManager

        desde_q = self._desde.getDate()
        hasta_q = self._hasta.getDate()
        desde = desde_q.toString("yyyy-MM-dd") if desde_q.isValid() else None
        hasta = hasta_q.toString("yyyy-MM-dd") if hasta_q.isValid() else None

        rows = DbManager().get_ciclos_rango(desde=desde, hasta=hasta, limite=200)

        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            inicio = row["fecha_inicio"] or ""
            fin    = row["fecha_fin"] or ""
            try:
                t0  = datetime.fromisoformat(inicio)
                t1  = datetime.fromisoformat(fin)
                dur = str((t1 - t0).seconds // 60)
            except Exception:
                dur = "—"

            self._table.setItem(i, 0, QTableWidgetItem(str(row["numero_ciclo"])))
            self._table.setItem(i, 1, QTableWidgetItem(row["nombre_ciclo"] or ""))
            self._table.setItem(i, 2, QTableWidgetItem(inicio[:19]))
            self._table.setItem(i, 3, QTableWidgetItem(dur))
            self._table.setItem(i, 4, QTableWidgetItem(row["resultado"] or ""))

    def _print_table(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog  = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        doc = QTextDocument()
        doc.setHtml(self._build_html())
        doc.print_(printer)

    def _build_html(self) -> str:
        headers = ["#", "Programa", "Fecha inicio", "Duración (min)", "Resultado"]
        th_cells = "".join(
            f"<th style='padding:6px 8px; background:#5789a7; color:white;"
            f" border:1px solid #5789a7;'>{h}</th>"
            for h in headers
        )
        rows_html = ""
        for r in range(self._table.rowCount()):
            cells = "".join(
                f"<td style='padding:4px 8px; border:1px solid #ccc;'>"
                f"{self._table.item(r, c).text() if self._table.item(r, c) else ''}</td>"
                for c in range(self._table.columnCount())
            )
            rows_html += f"<tr>{cells}</tr>"

        return (
            "<html><body>"
            "<h2 style='font-family:Segoe UI;'>Historial de Ciclos — Especifika</h2>"
            "<table style='border-collapse:collapse; font-family:Segoe UI;"
            " font-size:12px; width:100%;'>"
            f"<thead><tr>{th_cells}</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table></body></html>"
        )
