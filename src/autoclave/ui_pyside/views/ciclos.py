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
    CheckBox,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TableWidget,
)

_MESES = {
    1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC",
}


class CiclosView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback
        from autoclave.services.domain.logging.db_manager import DbManager as _DbManager
        self._db = _DbManager()

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

        self._chk_all = CheckBox("Seleccionar todos")
        self._chk_all.stateChanged.connect(self._toggle_all)
        filter_row.addWidget(self._chk_all)

        layout.addLayout(filter_row)

        # Tabla
        self._table = TableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["✓", "#", "Programa", "Fecha inicio", "Duración (min)", "Resultado"]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 36)
        layout.addWidget(self._table, stretch=1)

        # Botón imprimir
        btn_print = PrimaryPushButton("Imprimir seleccionados")
        btn_print.setFixedWidth(200)
        btn_print.clicked.connect(self._print_selected)
        layout.addWidget(btn_print, alignment=Qt.AlignmentFlag.AlignRight)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_data()

    def _load_data(self) -> None:
        desde_q = self._desde.getDate()
        hasta_q = self._hasta.getDate()
        desde = desde_q.toString("yyyy-MM-dd") if desde_q.isValid() else None
        hasta = hasta_q.toString("yyyy-MM-dd") if hasta_q.isValid() else None

        rows = self._db.get_ciclos_rango(desde=desde, hasta=hasta, limite=200)

        self._chk_all.blockSignals(True)
        self._chk_all.setChecked(False)
        self._chk_all.blockSignals(False)

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

            chk_item = QTableWidgetItem()
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            chk_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self._table.setItem(i, 0, chk_item)

            self._table.setItem(i, 1, QTableWidgetItem(str(row["numero_ciclo"])))
            self._table.setItem(i, 2, QTableWidgetItem(row["nombre_ciclo"] or ""))
            self._table.setItem(i, 3, QTableWidgetItem(inicio[:19]))
            self._table.setItem(i, 4, QTableWidgetItem(dur))
            self._table.setItem(i, 5, QTableWidgetItem(row["resultado"] or ""))

    def _toggle_all(self, state: int) -> None:
        check = Qt.CheckState.Checked if state == Qt.CheckState.Checked.value else Qt.CheckState.Unchecked
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                item.setCheckState(check)

    def _print_selected(self) -> None:
        ciclo_ids = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                ciclo_ids.append(item.data(Qt.ItemDataRole.UserRole))
        if not ciclo_ids:
            return
        self._print_cycles(ciclo_ids)

    def _print_cycles(self, ciclo_ids: list) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog  = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        html_parts = []
        for i, ciclo_id in enumerate(ciclo_ids):
            ciclo    = self._db.get_ciclo(ciclo_id)
            lecturas = self._db.get_lecturas_para_imprimir(ciclo_id)
            if ciclo is None:
                continue
            is_last = (i == len(ciclo_ids) - 1)
            html_parts.append(
                self._build_cycle_html(dict(ciclo), [dict(l) for l in lecturas], is_last)
            )
        if not html_parts:
            return
        doc = QTextDocument()
        doc.setHtml("<html><body>" + "".join(html_parts) + "</body></html>")
        doc.print_(printer)

    def _build_cycle_html(self, ciclo: dict, lecturas: list, is_last: bool = False) -> str:
        try:
            t_inicio = datetime.fromisoformat(ciclo["fecha_inicio"])
            mes = _MESES[t_inicio.month]
            fecha_str     = f"{t_inicio.day:02d}/{mes}/{t_inicio.year}"
            hora_inicio   = t_inicio.strftime("%H:%M:%S")
        except Exception:
            fecha_str   = "—"
            hora_inicio = "—"

        try:
            t_fin     = datetime.fromisoformat(ciclo["fecha_fin"])
            hora_fin  = t_fin.strftime("%H:%M:%S")
        except Exception:
            hora_fin = "—"

        temp_final = "—"
        if lecturas:
            tc = lecturas[-1].get("temp_camara")
            if tc is not None:
                temp_final = f"{tc:.0f}"

        log_lines = ""
        for lec in lecturas:
            fase  = (lec.get("fase_codigo") or " ").ljust(1)
            ts    = lec.get("timestamp_rel") or ""
            tc    = lec.get("temp_camara")
            pc    = lec.get("pres_camara")
            tc_s  = f"{tc:06.1f}" if tc is not None else "  —   "
            pc_s  = f"{pc:06.1f}" if pc is not None else "  —   "
            log_lines += f"{fase} {ts}  {tc_s}  {pc_s}\n"

        numero   = f"{ciclo.get('numero_ciclo', 0):06d}"
        temp_e   = ciclo.get("temp_esterilizacion") or ""
        tiempo_e = ciclo.get("tiempo_esterilizacion") or ""
        pb = "" if is_last else "page-break-after: always;"

        return (
            f"<pre style=\"font-family: 'Courier New', monospace; font-size: 10pt; {pb}\">"
            f"\n \n"
            f"------------------------\n"
            f"Fecha: {fecha_str}\n"
            f"Hora: {hora_inicio}\n"
            f"Núm de serie: {ciclo.get('serie', '')}\n"
            f"Modelo: {ciclo.get('modelo', '')}\n"
            f"Ver de SoftW.: {ciclo.get('version_sw', '')}\n"
            f"Número de ciclo: {numero}\n"
            f"{ciclo.get('nombre_ciclo', '')}\n"
            f"({ciclo.get('tipo_ciclo', '')})\n"
            f"Temp. Ester. {temp_e} °C\n"
            f"Tiempo Ester {tiempo_e} min\n"
            f"Temperatura final {temp_final} °C\n"
            f"  Hora       °C      kPa\n"
            f"{log_lines}"
            f"Estado: {ciclo.get('resultado', '')}\n"
            f"Hora: {hora_fin}\n"
            f"Operador: ____________\n"
            f"------------------------\n"
            f" \n"
            f"</pre>"
        )
