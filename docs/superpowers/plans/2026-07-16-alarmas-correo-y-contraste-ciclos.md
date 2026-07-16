# Envío de alarmas por correo + contraste en "Imprimir Ciclos" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir enviar por correo el snapshot de alarmas activas (igual que ya existe para ciclos), y corregir el contraste ilegible de la tabla en "Imprimir Ciclos" cuando Windows está en modo oscuro.

**Architecture:** Se extrae el diálogo de correo (`_EmailDialog` + envío SMTP) de `ciclos.py` a un módulo compartido `_email_dialog.py`, reutilizado desde `impresion_menu.py` para una nueva acción "Enviar Alarmas por Correo" que genera un PDF de una página. Por separado, `CiclosView` recibe un fondo/tarjeta con estilo explícito (mismo lenguaje visual que el resto de la app) para dejar de depender de la paleta del sistema operativo.

**Tech Stack:** PySide6 (QtWidgets/QtGui/QtPrintSupport), qfluentwidgets, `smtplib`/`email.mime`, `keyring`, pytest con fixture `qapp` (QApplication de sesión).

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-07-16-alarmas-correo-y-contraste-ciclos-design.md`.
- No se agrega historial de alarmas en DB — "Enviar Alarmas por Correo" envía siempre el snapshot de alarmas activas en ese momento, igual que "Imprimir Alarmas".
- El diálogo de correo compartido debe preservar el comportamiento exacto que ya tenía en `ciclos.py` (guardado de contraseña vía `keyring`, ajustes vía `QSettings("Especifika", "Autoclave")`).
- Ningún test existente debe romperse salvo los que se actualizan explícitamente en este plan (`test_impresion_menu_tiene_dos_opciones`).

---

### Task 1: Módulo compartido de diálogo de correo

**Files:**
- Create: `src/autoclave/ui_pyside/views/_email_dialog.py`
- Test: `tests/test_email_dialog.py`

**Interfaces:**
- Produces: `EmailDialog(QDialog)` con constructor `__init__(self, parent=None, title: str = "Enviar por correo")`, atributos de sólo lectura `to_addr`, `from_addr`, `password`, `smtp_server`, `smtp_port` (properties, igual que la clase original), y método interno `_load_saved_password(from_addr: str)`.
- Produces: `send_email(dlg: EmailDialog, attachment_path: str, subject: str, body: str, attachment_name: str) -> None` — construye el mensaje MIME y lo envía por SMTP usando `dlg.smtp_server`/`dlg.smtp_port`/`dlg.from_addr`/`dlg.password`/`dlg.to_addr`.

- [ ] **Step 1: Escribir el módulo (no hay comportamiento previo que testear con un test que falle primero — es extracción de código existente; se valida con los tests del Step 2)**

Crear `src/autoclave/ui_pyside/views/_email_dialog.py`:

```python
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
```

- [ ] **Step 2: Escribir los tests**

Crear `tests/test_email_dialog.py`:

```python
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_dialog(title="Enviar por correo", saved_from=""):
    from autoclave.ui_pyside.views._email_dialog import EmailDialog

    with patch("autoclave.ui_pyside.views._email_dialog.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default="": (
            saved_from if key == EmailDialog._S_FROM else default
        )
        mock_settings_cls.return_value = mock_settings
        with patch("autoclave.ui_pyside.views._email_dialog.keyring.get_password", return_value=None):
            dlg = EmailDialog(title=title)
    return dlg


def test_titulo_por_defecto():
    dlg = _make_dialog()
    assert dlg.windowTitle() == "Enviar por correo"


def test_titulo_personalizado():
    dlg = _make_dialog(title="Enviar alarmas por correo")
    assert dlg.windowTitle() == "Enviar alarmas por correo"


def test_carga_contrasena_guardada_al_construir():
    from autoclave.ui_pyside.views._email_dialog import EmailDialog

    with patch("autoclave.ui_pyside.views._email_dialog.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda key, default="": (
            "remitente@gmail.com" if key == EmailDialog._S_FROM else default
        )
        mock_settings_cls.return_value = mock_settings
        with patch("autoclave.ui_pyside.views._email_dialog.keyring.get_password", return_value="stored-pw"):
            dlg = EmailDialog()

    assert dlg.password == "stored-pw"
    assert dlg._btn_forget.isVisible()


def test_on_ok_guarda_contrasena_en_keyring_y_acepta():
    from autoclave.ui_pyside.views._email_dialog import EmailDialog

    dlg = _make_dialog()
    dlg._to.setText("destino@ejemplo.com")
    dlg._from.setText("remitente@gmail.com")
    dlg._pw.setText("xxxx xxxx xxxx xxxx")

    with patch("autoclave.ui_pyside.views._email_dialog.keyring.set_password") as mock_set:
        dlg._on_ok()

    mock_set.assert_called_once_with(
        EmailDialog._KR_SVC, "remitente@gmail.com", "xxxx xxxx xxxx xxxx"
    )
    assert dlg.result() == int(dlg.DialogCode.Accepted)


def test_on_ok_campos_incompletos_no_acepta():
    dlg = _make_dialog()
    dlg._to.setText("")
    dlg._from.setText("remitente@gmail.com")
    dlg._pw.setText("xxxx")

    with patch("autoclave.ui_pyside.views._email_dialog.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views._email_dialog.keyring.set_password") as mock_set:
        dlg._on_ok()

    mock_box.warning.assert_called_once()
    mock_set.assert_not_called()
    assert dlg.result() == 0  # no se aceptó


def test_send_email_arma_mensaje_y_envia_por_smtp(tmp_path):
    from autoclave.ui_pyside.views._email_dialog import send_email

    attachment = tmp_path / "reporte.pdf"
    attachment.write_bytes(b"contenido de prueba")

    dlg = MagicMock()
    dlg.from_addr   = "remitente@gmail.com"
    dlg.to_addr     = "destino@ejemplo.com"
    dlg.password    = "xxxx xxxx xxxx xxxx"
    dlg.smtp_server = "smtp.gmail.com"
    dlg.smtp_port   = 587

    with patch("autoclave.ui_pyside.views._email_dialog.smtplib.SMTP") as mock_smtp_cls:
        mock_srv = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_srv

        send_email(
            dlg, str(attachment),
            subject="Alarmas Activas — Especifika Autoclave",
            body="Adjunto encontrará el reporte de alarmas activas del autoclave.",
            attachment_name="alarmas_20260716.pdf",
        )

    mock_srv.ehlo.assert_called_once()
    mock_srv.starttls.assert_called_once()
    mock_srv.login.assert_called_once_with("remitente@gmail.com", "xxxx xxxx xxxx xxxx")

    assert mock_srv.sendmail.call_count == 1
    from_addr, to_addrs, raw_message = mock_srv.sendmail.call_args.args
    assert from_addr == "remitente@gmail.com"
    assert to_addrs == ["destino@ejemplo.com"]
    assert "Alarmas Activas" in raw_message
    assert 'filename="alarmas_20260716.pdf"' in raw_message
```

- [ ] **Step 3: Correr los tests**

Run: `pytest tests/test_email_dialog.py -v`
Expected: 6 tests PASS (`test_titulo_por_defecto`, `test_titulo_personalizado`, `test_carga_contrasena_guardada_al_construir`, `test_on_ok_guarda_contrasena_en_keyring_y_acepta`, `test_on_ok_campos_incompletos_no_acepta`, `test_send_email_arma_mensaje_y_envia_por_smtp`)

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/ui_pyside/views/_email_dialog.py tests/test_email_dialog.py
git commit -m "feat: extraer dialogo de correo compartido (EmailDialog, send_email)"
```

---

### Task 2: Migrar `ciclos.py` al módulo compartido

**Files:**
- Modify: `src/autoclave/ui_pyside/views/ciclos.py`

**Interfaces:**
- Consumes: `EmailDialog(parent=None, title: str = "Enviar por correo")` y `send_email(dlg, attachment_path, subject, body, attachment_name)` de `autoclave.ui_pyside.views._email_dialog` (Task 1).

- [ ] **Step 1: Confirmar que los tests existentes de ciclos.py pasan antes de tocar nada**

Run: `pytest tests/test_ciclos_print.py -v`
Expected: 4 tests PASS (estado previo a la migración — no referencian `_EmailDialog` directamente, así que deben seguir pasando después del cambio sin modificarlos)

- [ ] **Step 2: Reemplazar el bloque de imports de `ciclos.py`**

Reemplazar las líneas 1–46 (desde `import os` hasta el bloque `from autoclave.services...import format_row)`) por:

```python
import os
import socket
import tempfile
import zipfile
from datetime import datetime

from PySide6.QtCore import QDate, QMarginsF, QSizeF, Qt
from PySide6.QtGui import QFont, QPainter, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QMessageBox,
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
from autoclave.ui_pyside.views._email_dialog import EmailDialog, send_email
```

(Nota: `QFrame` se agrega en la Task 4, no aquí — esta task sólo migra el correo.)

- [ ] **Step 3: Eliminar la clase `_EmailDialog` completa**

Eliminar el bloque desde el comentario `# ── Diálogo de correo ─...` hasta el final de la clase `_EmailDialog` (la propiedad `smtp_port`), justo antes de `# ── Vista principal ─...`. Ese comentario y `class CiclosView(QWidget):` quedan como estaban.

- [ ] **Step 4: Actualizar `_email_selected` y eliminar `_send_email`**

Reemplazar el método `_email_selected` actual por:

```python
    def _email_selected(self) -> None:
        ids = self._get_selected_ids()
        if not ids:
            return
        dlg = EmailDialog(self, title="Enviar ciclos por correo")
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
                send_email(
                    dlg, zip_path,
                    subject="Historial de Ciclos — Especifika Autoclave",
                    body="Adjunto encontrará los ciclos de autoclave seleccionados en formato PDF.",
                    attachment_name="ciclos_autoclave.zip",
                )
                QMessageBox.information(
                    self, "Correo enviado",
                    f"Se enviaron {len(pdf_paths)} ciclo(s) a {dlg.to_addr}."
                )
            except Exception as exc:
                QMessageBox.critical(
                    self, "Error al enviar",
                    f"No se pudo enviar el correo:\n{exc}"
                )
```

Y eliminar el `@staticmethod _send_email(...)` que le seguía (era el último método de la clase — el archivo termina en `_email_selected` ahora).

- [ ] **Step 5: Correr los tests de ciclos y el import del módulo completo**

Run: `pytest tests/test_ciclos_print.py -v`
Expected: 4 tests PASS (sin cambios de comportamiento)

Run: `python -c "import autoclave.ui_pyside.views.ciclos"`
Expected: sin errores (confirma que no quedaron referencias colgantes a `_EmailDialog`/`_send_email`/imports eliminados)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/ciclos.py
git commit -m "refactor: ciclos.py usa el dialogo de correo compartido"
```

---

### Task 3: "Enviar Alarmas por Correo" en `impresion_menu.py`

**Files:**
- Modify: `src/autoclave/ui_pyside/views/impresion_menu.py`
- Modify: `tests/test_impresion_menu.py`

**Interfaces:**
- Consumes: `EmailDialog`, `send_email` de `autoclave.ui_pyside.views._email_dialog` (Task 1).
- Consumes: `_build_alarms_ticket_lines(alarms: list[dict]) -> list[str]` (ya existente en este archivo).
- Produces: `_generate_alarms_pdf(alarms: list[dict], path: str) -> None` (función a nivel de módulo).
- Produces: `ImpresionMenuView._email_alarms(self) -> None`.

- [ ] **Step 1: Escribir los tests que fallarán (nueva función/método aún no existen)**

Reemplazar en `tests/test_impresion_menu.py` el test `test_impresion_menu_tiene_dos_opciones` por:

```python
def test_impresion_menu_tiene_tres_opciones():
    from autoclave.ui_pyside.views.impresion_menu import _PRINT_OPTIONS
    assert len(_PRINT_OPTIONS) == 3
    labels = [label for _, label, _ in _PRINT_OPTIONS]
    assert "Imprimir Ciclos" in labels
    assert "Imprimir Alarmas" in labels
    assert "Enviar Alarmas por Correo" in labels
    targets = [target for _, _, target in _PRINT_OPTIONS]
    assert "ciclos" in targets
    assert targets.count(None) == 2
```

Agregar al final de `tests/test_impresion_menu.py`:

```python
def test_generate_alarms_pdf_crea_archivo(tmp_path):
    from autoclave.ui_pyside.views.impresion_menu import _generate_alarms_pdf

    alarms = [{"id": "X", "level": "ALERTA", "description": "desc", "source_state": "CICLO"}]
    path = str(tmp_path / "alarmas.pdf")

    _generate_alarms_pdf(alarms, path)

    import os
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


def test_email_alarms_sin_alarmas_muestra_aviso_no_abre_dialogo():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": []}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.EmailDialog") as mock_dialog_cls:
        view._email_alarms()

        mock_box.information.assert_called_once()
        mock_dialog_cls.assert_not_called()


def test_email_alarms_dialogo_cancelado_no_envia():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtWidgets import QDialog

    alarms = [{"id": "X", "level": "ALERTA", "description": "desc", "source_state": "CICLO"}]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.EmailDialog") as mock_dialog_cls, \
         patch("autoclave.ui_pyside.views.impresion_menu.send_email") as mock_send:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        mock_dialog_cls.return_value = mock_dlg

        view._email_alarms()

        mock_send.assert_not_called()


def test_email_alarms_envia_pdf_con_alarmas_activas():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtWidgets import QDialog

    alarms = [{"id": "CHAQUETA_FRIA", "level": "ALERTA",
               "description": "Alerta: CHAQUETA_FRIA en PREPARACION.", "source_state": "PREPARACION"}]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.EmailDialog") as mock_dialog_cls, \
         patch("autoclave.ui_pyside.views.impresion_menu.send_email") as mock_send, \
         patch("autoclave.ui_pyside.views.impresion_menu._generate_alarms_pdf") as mock_pdf, \
         patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.to_addr = "destino@ejemplo.com"
        mock_dialog_cls.return_value = mock_dlg

        view._email_alarms()

        mock_pdf.assert_called_once()
        pdf_args = mock_pdf.call_args.args
        assert pdf_args[0] == alarms

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["subject"] == "Alarmas Activas — Especifika Autoclave"
        assert "alarmas activas" in kwargs["body"]
        assert kwargs["attachment_name"].startswith("alarmas_")
        assert kwargs["attachment_name"].endswith(".pdf")

        mock_box.information.assert_called_once()
        mock_box.critical.assert_not_called()


def test_email_alarms_falla_envio_muestra_error():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtWidgets import QDialog

    alarms = [{"id": "X", "level": "ALERTA", "description": "desc", "source_state": "CICLO"}]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.EmailDialog") as mock_dialog_cls, \
         patch("autoclave.ui_pyside.views.impresion_menu.send_email", side_effect=Exception("smtp caido")), \
         patch("autoclave.ui_pyside.views.impresion_menu._generate_alarms_pdf"), \
         patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box:
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.to_addr = "destino@ejemplo.com"
        mock_dialog_cls.return_value = mock_dlg

        view._email_alarms()

        mock_box.critical.assert_called_once()
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `pytest tests/test_impresion_menu.py -v`
Expected: FAIL — `test_impresion_menu_tiene_tres_opciones` falla (`_PRINT_OPTIONS` todavía tiene 2 elementos), y los tests de `_email_alarms`/`_generate_alarms_pdf` fallan con `AttributeError`/`ImportError` porque aún no existen.

- [ ] **Step 3: Actualizar imports en `impresion_menu.py`**

Reemplazar el bloque de imports actual (líneas 1–18) por:

```python
import os
import tempfile
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QMarginsF, QSizeF, Qt
from PySide6.QtGui import QFont, QPainter, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from autoclave.devices.printer.win32_printer import PRINTER_NAME, print_raw
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.views._email_dialog import EmailDialog, send_email
```

- [ ] **Step 4: Agregar constantes de PDF y `_wrap`, y extender `_PRINT_OPTIONS`**

Ubicar el bloque `_PRINT_OPTIONS` actual:

```python
_PRINT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("📋", "Imprimir Ciclos",  "ciclos"),
    ("🚨", "Imprimir Alarmas", None),
]
```

Reemplazarlo por:

```python
_PRINT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("📋", "Imprimir Ciclos",  "ciclos"),
    ("🚨", "Imprimir Alarmas", None),
    ("📧", "Enviar Alarmas por Correo", None),
]

_PAPER_W_MM   = 55.0
_MARGIN_H_MM  = 2.0
_MARGIN_V_MM  = 3.0
_CHARS_LINE   = 30      # max chars per line at 55 mm
_FONT_PT      = 7
_FONT_FAMILY  = "Courier New"
```

- [ ] **Step 5: Agregar `_wrap` y `_generate_alarms_pdf` después de `_build_alarms_ticket_lines`**

Justo después del cierre de la función `_build_alarms_ticket_lines` (antes de `class ImpresionMenuView`), agregar:

```python
def _wrap(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]


def _generate_alarms_pdf(alarms: list, path: str) -> None:
    lines   = _build_alarms_ticket_lines(alarms)
    n_lines = sum(len(_wrap(ln, _CHARS_LINE)) for ln in lines)
    h_mm    = max(60.0, n_lines * 3.6 + 10.0)

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
```

- [ ] **Step 6: Actualizar el bucle de construcción de botones para despachar por diccionario**

Reemplazar:

```python
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
```

por:

```python
        actions = {
            "Imprimir Alarmas": self._print_alarms,
            "Enviar Alarmas por Correo": self._email_alarms,
        }
        for icon, label, target in _PRINT_OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION.format(bg="#f8f9fa"))
            if target is not None:
                btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            else:
                btn.clicked.connect(actions[label])
            cl.addWidget(btn)
```

- [ ] **Step 7: Agregar `_email_alarms` después de `_print_alarms`**

```python
    def _email_alarms(self) -> None:
        try:
            status = self._client.get_status()
            alarms = status.get("alarms", [])
        except Exception:
            alarms = []

        if not alarms:
            QMessageBox.information(self, "Alarmas", "No hay alarmas activas.")
            return

        dlg = EmailDialog(self, title="Enviar alarmas por correo")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        with tempfile.TemporaryDirectory() as tmp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"alarmas_{timestamp}.pdf"
            path      = os.path.join(tmp, filename)
            _generate_alarms_pdf(alarms, path)

            try:
                send_email(
                    dlg, path,
                    subject="Alarmas Activas — Especifika Autoclave",
                    body="Adjunto encontrará el reporte de alarmas activas del autoclave.",
                    attachment_name=filename,
                )
                QMessageBox.information(
                    self, "Correo enviado",
                    f"Se enviaron las alarmas activas a {dlg.to_addr}."
                )
            except Exception as exc:
                QMessageBox.critical(
                    self, "Error al enviar",
                    f"No se pudo enviar el correo:\n{exc}"
                )
```

- [ ] **Step 8: Correr los tests**

Run: `pytest tests/test_impresion_menu.py -v`
Expected: 15 tests PASS — las 11 originales menos `test_impresion_menu_tiene_dos_opciones` (reemplazado) más `test_impresion_menu_tiene_tres_opciones`, `test_generate_alarms_pdf_crea_archivo`, `test_email_alarms_sin_alarmas_muestra_aviso_no_abre_dialogo`, `test_email_alarms_dialogo_cancelado_no_envia`, `test_email_alarms_envia_pdf_con_alarmas_activas`, `test_email_alarms_falla_envio_muestra_error`

- [ ] **Step 9: Commit**

```bash
git add src/autoclave/ui_pyside/views/impresion_menu.py tests/test_impresion_menu.py
git commit -m "feat: agregar envio de alarmas activas por correo"
```

---

### Task 4: Corregir contraste de `CiclosView`

**Files:**
- Modify: `src/autoclave/ui_pyside/views/ciclos.py`

- [ ] **Step 1: Agregar constante `_TABLE_STYLE` cerca de las otras constantes del módulo**

Ubicar el bloque de constantes al inicio del archivo:

```python
_PAPER_W_MM   = 55.0
_MARGIN_H_MM  = 2.0
_MARGIN_V_MM  = 3.0
_CHARS_LINE   = 30      # max chars per line at 55 mm
_FONT_PT      = 7
_FONT_FAMILY  = "Courier New"
```

Agregar justo después:

```python
_TABLE_STYLE = """
    QTableWidget {
        background: white;
        color: #1a2a3a;
        gridline-color: #e8eaed;
        alternate-background-color: #f8f9fa;
        selection-background-color: #dbeafe;
        selection-color: #1a2a3a;
        border: 1px solid #e8eaed;
        border-radius: 8px;
    }
    QHeaderView::section {
        background: #f0f2f5;
        color: #1a2a3a;
        font-weight: bold;
        padding: 6px;
        border: none;
        border-bottom: 1px solid #e8eaed;
    }
"""
```

- [ ] **Step 2: Agregar `QFrame` al import de `PySide6.QtWidgets`**

En el bloque de imports (modificado en la Task 2), cambiar:

```python
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
```

por:

```python
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 3: Envolver el contenido de `CiclosView.__init__` en fondo + tarjeta**

Reemplazar:

```python
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Cabecera
```

por:

```python
        self.setStyleSheet("""
            CiclosView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("ciclosCard")
        card.setStyleSheet("QFrame#ciclosCard { background: white; border-radius: 20px; }")
        root.addWidget(card, stretch=1)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Cabecera
```

(El resto del método sigue usando `layout.addWidget(...)`/`layout.addLayout(...)` sin cambios — ahora `layout` es el layout interno de `card` en vez de `self`.)

- [ ] **Step 4: Aplicar `_TABLE_STYLE` a la tabla**

Ubicar:

```python
        self._table.setColumnWidth(0, 36)
        layout.addWidget(self._table, stretch=1)
```

Reemplazar por:

```python
        self._table.setColumnWidth(0, 36)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table, stretch=1)
```

- [ ] **Step 5: Correr los tests existentes de ciclos (deben seguir pasando — sólo cambió estilo, no comportamiento)**

Run: `pytest tests/test_ciclos_print.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Verificación visual manual**

Ejecutar el script de captura usado durante el diagnóstico (adaptar ruta de salida si es necesario):

```python
import sys
from unittest.mock import patch

sys.path.insert(0, r"C:\Users\tecni\Documents\codigo_autoclave\src")

from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

app = QApplication.instance() or QApplication(sys.argv)
setTheme(Theme.LIGHT)

with patch("autoclave.services.domain.logging.db_manager.DbManager") as MockDb:
    instance = MockDb.return_value
    instance.get_ciclos_rango.return_value = [
        {"id": 1, "numero_ciclo": 49, "nombre_ciclo": "Bowe & Dick",
         "fecha_inicio": "2026-07-15T14:08:22", "fecha_fin": "2026-07-15T14:34:58",
         "resultado": "FALLO_ESTERILIZACION"},
        {"id": 2, "numero_ciclo": 48, "nombre_ciclo": "Instrumental 134",
         "fecha_inicio": "2026-07-14T09:00:00", "fecha_fin": "2026-07-14T09:45:00",
         "resultado": "COMPLETADO"},
    ]
    from autoclave.ui_pyside.views.ciclos import CiclosView
    view = CiclosView(nav_callback=lambda x: None)

view.resize(900, 600)
view.show()
app.processEvents()
view.grab().save("ciclos_view_after.png")
```

Run: `python ese_script.py`
Expected: `ciclos_view_after.png` muestra fondo azul con tarjeta blanca, y las filas de la tabla ("Bowe & ...", "26", "FALLO_ESTERILIZACION", etc.) legibles en texto oscuro sobre fondo blanco/gris claro — confirmar visualmente abriendo el PNG generado.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/ui_pyside/views/ciclos.py
git commit -m "fix: corregir contraste ilegible de la tabla en Imprimir Ciclos"
```

---

### Task 5: Verificación final

**Files:** ninguno (sólo verificación)

- [ ] **Step 1: Correr toda la suite de tests**

Run: `pytest tests/ -q --ignore=tests/test_io_views.py`
Expected: todos PASS (el `--ignore` excluye una suite rota desde antes de este trabajo, por una reorganización de módulos no relacionada — confirmado en la sesión anterior)

- [ ] **Step 2: Confirmar que no quedaron referencias a los nombres viejos**

Run: `grep -rn "_EmailDialog\b" src/ tests/`
Expected: sin resultados (todo quedó migrado a `EmailDialog`)

- [ ] **Step 3: Reportar resumen final al usuario**

Confirmar: tests pasando, captura de pantalla de "Imprimir Ciclos" mostrando el contraste corregido, y descripción de cómo probar manualmente "Enviar Alarmas por Correo" (requiere una alarma activa y credenciales SMTP reales para un envío real; los tests automatizados cubren la lógica con mocks).
