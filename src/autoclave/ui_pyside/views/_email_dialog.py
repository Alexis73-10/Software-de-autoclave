# ui_pyside/views/_email_dialog.py
#
# Diálogo de envío por correo (SMTP + credenciales en keyring), compartido
# entre CiclosView (historial de ciclos) e ImpresionMenuView (alarmas
# activas) para no duplicar el flujo completo de configuración SMTP.

import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import keyring

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class EmailDialog(QDialog):
    _S_FROM = "email/from"
    _S_SMTP = "email/smtp_server"
    _S_PORT = "email/smtp_port"
    _KR_SVC = "Especifika-Autoclave-Email"

    def __init__(self, parent=None, title: str = "Enviar por correo"):
        super().__init__(parent)
        self.setWindowTitle(title)
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


def send_email(dlg: EmailDialog, attachment_path: str, subject: str, body: str, attachment_name: str) -> None:
    """Envía `attachment_path` como adjunto por SMTP usando las credenciales
    capturadas en `dlg`. `attachment_name` es el nombre visible del adjunto
    (puede diferir del nombre del archivo temporal)."""
    msg            = MIMEMultipart()
    msg["From"]    = dlg.from_addr
    msg["To"]      = dlg.to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(attachment_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{attachment_name}"',
    )
    msg.attach(part)

    with smtplib.SMTP(dlg.smtp_server, dlg.smtp_port, timeout=15) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(dlg.from_addr, dlg.password)
        srv.sendmail(dlg.from_addr, [dlg.to_addr], msg.as_string())
