import email
import sys
from email.header import decode_header, make_header
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
    # isVisible() refleja la jerarquia real de ventanas: sin mostrar el
    # dialogo, siempre es False sin importar setVisible(True) interno.
    dlg.show()
    assert dlg._btn_forget.isVisible()
    dlg.close()


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

    # El Subject tiene caracteres no-ASCII ("—"), por lo que el mensaje
    # crudo lo codifica RFC2047 (=?utf-8?q?...?=) — se decodifica para
    # comparar el valor real en vez de buscar el texto plano en el crudo.
    parsed = email.message_from_string(raw_message)
    subject_decodificado = str(make_header(decode_header(parsed["Subject"])))
    assert subject_decodificado == "Alarmas Activas — Especifika Autoclave"
    assert 'filename="alarmas_20260716.pdf"' in raw_message
