import os
import smtplib
import socket
import tempfile
import zipfile
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import keyring

from PySide6.QtCore import QDate, QMarginsF, QSettings, QSizeF, Qt
from PySide6.QtGui import QFont, QPainter, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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

from autoclave.devices.printer.win32_printer import PRINTER_NAME, print_raw
from autoclave.services.domain.logging.ticket_formatter import (
    format_footer,
    format_header,
    format_row,
)

_PAPER_W_MM   = 55.0
_MARGIN_H_MM  = 2.0
_MARGIN_V_MM  = 3.0
_CHARS_LINE   = 30      # max chars per line at 55 mm
_FONT_PT      = 7
_FONT_FAMILY  = "Courier New"


# ── Construcción de líneas de un ciclo ────────────────────────────────────────

def _build_cycle_lines(ciclo: dict, lecturas: list) -> list[str]:
    """Arma el ticket de un ciclo guardado reutilizando el mismo formato
    (header/row/footer) que usa la impresión en tiempo real, para que ambas
    salidas sean idénticas."""
    meta = {
        "numero_ciclo":          ciclo.get("numero_ciclo", 0),
        "serie":                 ciclo.get("serie", ""),
        "modelo":                ciclo.get("modelo", ""),
        "version_sw":            ciclo.get("version_sw", ""),
        "nombre_ciclo":          ciclo.get("nombre_ciclo") or "",
        "tipo_ciclo":            ciclo.get("tipo_ciclo") or "",
        "temp_esterilizacion":   ciclo.get("temp_esterilizacion"),
        "tiempo_esterilizacion": ciclo.get("tiempo_esterilizacion"),
        "fecha_inicio":          ciclo.get("fecha_inicio", ""),
    }

    temp_final = None
    if lecturas:
        tc = lecturas[-1].get("temp_camara")
        if tc is not None:
            temp_final = tc

    lines = format_header(meta).split("\n")
    lines += [format_row(lec) for lec in lecturas]
    lines += format_footer(
        ciclo.get("resultado", ""), ciclo.get("fecha_fin", ""),
        temp_final=temp_final, motivo=ciclo.get("motivo_fallo"),
    ).split("\n")
    return lines


def _wrap(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


# ── Diálogo de correo ─────────────────────────────────────────────────────────

class _EmailDialog(QDialog):
    _S_FROM    = "email/from"
    _S_SMTP    = "email/smtp_server"
    _S_PORT    = "email/smtp_port"
    _KR_SVC    = "Especifika-Autoclave-Email"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enviar ciclos por correo")
        self.setMinimumWidth(400)

        cfg = QSettings("Especifika", "Autoclave")
        saved_from = cfg.value(self._S_FROM, "")

        form = QFormLayout()

        self._to = QLineEdit()
        self._to.setPlaceholderText("destinatario@ejemplo.com")
        form.addRow("Para:", self._to)

        self._from = QLineEdit(saved_from)
        self._from.setPlaceholderText("remitente@gmail.com")
        self._from.textChanged.connect(self._on_from_changed)
        form.addRow("De:", self._from)

        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setPlaceholderText("xxxx xxxx xxxx xxxx  (16 caracteres)")
        form.addRow("Contraseña de app:", self._pw)

        # Fila de estado del guardado + botón olvidar
        pw_status_row = QHBoxLayout()
        self._lbl_saved = QLabel()
        self._lbl_saved.setStyleSheet("color: #4caf50; font-size: 11px;")
        pw_status_row.addWidget(self._lbl_saved)
        pw_status_row.addStretch()
        self._btn_forget = QPushButton("Olvidar contraseña")
        self._btn_forget.setStyleSheet("font-size: 11px; color: #e57373; border: none;")
        self._btn_forget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forget.clicked.connect(self._forget_password)
        pw_status_row.addWidget(self._btn_forget)
        form.addRow("", pw_status_row)

        self._smtp = QLineEdit(cfg.value(self._S_SMTP, "smtp.gmail.com"))
        form.addRow("Servidor SMTP:", self._smtp)

        self._port = QLineEdit(cfg.value(self._S_PORT, "587"))
        form.addRow("Puerto:", self._port)

        note = QLabel(
            "<small><b>Gmail:</b> la contraseña de app se genera en<br>"
            "Cuenta Google → Seguridad → Verificación en 2 pasos<br>"
            "→ Contraseñas de aplicaciones (NO uses tu contraseña normal).</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; padding: 4px 0;")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(note)
        root.addWidget(btns)

        # Pre-cargar contraseña guardada si existe
        self._load_saved_password(saved_from)

    # ── Contraseña guardada ───────────────────────────────────────────

    def _load_saved_password(self, from_addr: str) -> None:
        if not from_addr:
            self._lbl_saved.setText("")
            self._btn_forget.setVisible(False)
            return
        stored = keyring.get_password(self._KR_SVC, from_addr)
        if stored:
            self._pw.setText(stored)
            self._lbl_saved.setText("✓ Contraseña guardada")
            self._btn_forget.setVisible(True)
        else:
            self._lbl_saved.setText("")
            self._btn_forget.setVisible(False)

    def _on_from_changed(self, text: str) -> None:
        self._pw.clear()
        self._load_saved_password(text.strip())

    def _forget_password(self) -> None:
        addr = self._from.text().strip()
        if addr:
            try:
                keyring.delete_password(self._KR_SVC, addr)
            except keyring.errors.PasswordDeleteError:
                pass
        self._pw.clear()
        self._lbl_saved.setText("")
        self._btn_forget.setVisible(False)

    # ── Aceptar ───────────────────────────────────────────────────────

    def _on_ok(self):
        if not self._to.text().strip() or not self._from.text().strip() or not self._pw.text():
            QMessageBox.warning(self, "Datos incompletos", "Complete todos los campos.")
            return
        addr = self._from.text().strip()
        cfg  = QSettings("Especifika", "Autoclave")
        cfg.setValue(self._S_FROM, addr)
        cfg.setValue(self._S_SMTP, self._smtp.text().strip())
        cfg.setValue(self._S_PORT, self._port.text().strip())
        keyring.set_password(self._KR_SVC, addr, self._pw.text())
        self.accept()

    @property
    def to_addr(self)     -> str: return self._to.text().strip()
    @property
    def from_addr(self)   -> str: return self._from.text().strip()
    @property
    def password(self)    -> str: return self._pw.text()
    @property
    def smtp_server(self) -> str: return self._smtp.text().strip()
    @property
    def smtp_port(self)   -> int:
        try:   return int(self._port.text().strip())
        except ValueError: return 587


# ── Vista principal ───────────────────────────────────────────────────────────

class CiclosView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback
        from autoclave.services.domain.logging.db_manager import DbManager as _DbManager
        self._db = _DbManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Cabecera
        header_row = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("impresion_menu"))
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

        # Botones de acción
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_print = PrimaryPushButton("Imprimir seleccionados")
        btn_print.setFixedWidth(200)
        btn_print.clicked.connect(self._print_selected)
        btn_row.addWidget(btn_print)

        self._btn_email = PushButton("Enviar por correo")
        self._btn_email.setFixedWidth(180)
        self._btn_email.setEnabled(False)
        self._btn_email.clicked.connect(self._email_selected)
        btn_row.addWidget(self._btn_email)

        layout.addLayout(btn_row)

    # ── Lifecycle ─────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_data()
        self._btn_email.setEnabled(self._has_internet())

    # ── Datos ─────────────────────────────────────────────────────────

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
                t0 = datetime.fromisoformat(inicio)
                t1 = datetime.fromisoformat(fin)
                dur = str((t1 - t0).seconds // 60)
            except Exception:
                dur = "—"

            chk = QTableWidgetItem()
            chk.setCheckState(Qt.CheckState.Unchecked)
            chk.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            chk.setData(Qt.ItemDataRole.UserRole, row["id"])
            self._table.setItem(i, 0, chk)
            self._table.setItem(i, 1, QTableWidgetItem(str(row["numero_ciclo"])))
            self._table.setItem(i, 2, QTableWidgetItem(row["nombre_ciclo"] or ""))
            self._table.setItem(i, 3, QTableWidgetItem(inicio[:19]))
            self._table.setItem(i, 4, QTableWidgetItem(dur))
            self._table.setItem(i, 5, QTableWidgetItem(row["resultado"] or ""))

    def _toggle_all(self, state: int) -> None:
        cs = (Qt.CheckState.Checked if state == Qt.CheckState.Checked.value
              else Qt.CheckState.Unchecked)
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                item.setCheckState(cs)

    def _get_selected_ids(self) -> list:
        ids = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _load_cycles_data(self, ciclo_ids: list) -> list:
        result = []
        for cid in ciclo_ids:
            ciclo    = self._db.get_ciclo(cid)
            lecturas = self._db.get_lecturas_para_imprimir(cid)
            if ciclo is not None:
                result.append((dict(ciclo), [dict(l) for l in lecturas]))
        return result

    # ── Impresión (QPainter — sin HTML) ──────────────────────────────

    def _print_selected(self) -> None:
        ids = self._get_selected_ids()
        if not ids:
            return
        cycles_data = self._load_cycles_data(ids)
        if not cycles_data:
            return
        text = "\n".join(
            line
            for ciclo, lecturas in cycles_data
            for line in _build_cycle_lines(ciclo, lecturas)
        )
        if not print_raw(text, PRINTER_NAME):
            QMessageBox.warning(self, "Imprimir", "No se pudo imprimir el ticket.")

    def _draw_cycles(self, printer: QPrinter, cycles_data: list) -> None:
        if not cycles_data:
            return
        painter = QPainter(printer)
        font = QFont(_FONT_FAMILY, _FONT_PT)
        painter.setFont(font)
        fm = painter.fontMetrics()

        page_rect  = printer.pageRect(QPrinter.Unit.DevicePixel)
        char_w     = fm.horizontalAdvance("M")
        chars_line = max(20, int(page_rect.width() // char_w))
        line_h     = fm.lineSpacing() + 1

        for idx, (ciclo, lecturas) in enumerate(cycles_data):
            if idx > 0:
                printer.newPage()
            y = page_rect.top() + fm.ascent()
            for raw in _build_cycle_lines(ciclo, lecturas):
                for seg in _wrap(raw, chars_line):
                    painter.drawText(int(page_rect.left()), int(y), seg)
                    y += line_h

        painter.end()

    # ── PDF por ciclo (para email) ────────────────────────────────────

    def _generate_cycle_pdf(self, ciclo: dict, lecturas: list, path: str) -> None:
        lines    = _build_cycle_lines(ciclo, lecturas)
        n_lines  = sum(len(_wrap(ln, _CHARS_LINE)) for ln in lines)
        h_mm     = max(60.0, n_lines * 3.6 + 10.0)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(
            QPageSize(QSizeF(_PAPER_W_MM, h_mm), QPageSize.Unit.Millimeter)
        )
        printer.setPageMargins(
            QMarginsF(_MARGIN_H_MM, _MARGIN_V_MM, _MARGIN_H_MM, _MARGIN_V_MM),
            QPageLayout.Unit.Millimeter,
        )
        self._draw_cycles(printer, [(ciclo, lecturas)])

    # ── Envío por correo ──────────────────────────────────────────────

    @staticmethod
    def _has_internet() -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except OSError:
            return False

    def _email_selected(self) -> None:
        ids = self._get_selected_ids()
        if not ids:
            return
        dlg = _EmailDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        cycles_data = self._load_cycles_data(ids)
        with tempfile.TemporaryDirectory() as tmp:
            pdf_paths = []
            for ciclo, lecturas in cycles_data:
                n    = ciclo.get("numero_ciclo", 0)
                path = os.path.join(tmp, f"ciclo_{n:06d}.pdf")
                self._generate_cycle_pdf(ciclo, lecturas, path)
                pdf_paths.append(path)

            zip_path = os.path.join(tmp, "ciclos_autoclave.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in pdf_paths:
                    zf.write(p, os.path.basename(p))

            try:
                self._send_email(dlg, zip_path)
                QMessageBox.information(
                    self, "Correo enviado",
                    f"Se enviaron {len(pdf_paths)} ciclo(s) a {dlg.to_addr}."
                )
            except Exception as exc:
                QMessageBox.critical(
                    self, "Error al enviar",
                    f"No se pudo enviar el correo:\n{exc}"
                )

    @staticmethod
    def _send_email(dlg: _EmailDialog, zip_path: str) -> None:
        msg            = MIMEMultipart()
        msg["From"]    = dlg.from_addr
        msg["To"]      = dlg.to_addr
        msg["Subject"] = "Historial de Ciclos — Especifika Autoclave"
        msg.attach(MIMEText(
            "Adjunto encontrará los ciclos de autoclave seleccionados en formato PDF.",
            "plain",
        ))
        with open(zip_path, "rb") as f:
            part = MIMEBase("application", "zip")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            'attachment; filename="ciclos_autoclave.zip"',
        )
        msg.attach(part)

        with smtplib.SMTP(dlg.smtp_server, dlg.smtp_port, timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(dlg.from_addr, dlg.password)
            srv.sendmail(dlg.from_addr, [dlg.to_addr], msg.as_string())
