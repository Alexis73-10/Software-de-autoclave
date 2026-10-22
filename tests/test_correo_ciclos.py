# tests/test_correo_ciclos.py
#
# Armado y envío del correo con los PDF de ciclos (ui_qml/exportacion/correo.py).

import io
import zipfile
from unittest.mock import MagicMock

from autoclave.ui_qml.exportacion import correo
from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo


def test_un_ciclo_va_como_pdf():
    assert correo.adjunto([("ciclo_000012.pdf", b"%PDF-1")], "ciclos.zip") == \
        ("ciclo_000012.pdf", b"%PDF-1", "pdf")


def test_varios_ciclos_van_en_un_zip():
    nombre, contenido, subtipo = correo.adjunto(
        [("ciclo_000012.pdf", b"%PDF-a"), ("ciclo_000013.pdf", b"%PDF-b")], "ciclos.zip")
    assert (nombre, subtipo) == ("ciclos.zip", "zip")
    z = zipfile.ZipFile(io.BytesIO(contenido))
    assert z.namelist() == ["ciclo_000012.pdf", "ciclo_000013.pdf"]
    assert z.read("ciclo_000013.pdf") == b"%PDF-b"


def test_mensaje_con_adjunto():
    m = correo.armar_mensaje("equipo@gmail.com", "mant@x.com", "Asunto", "Cuerpo",
                             ("ciclo_000012.pdf", b"%PDF-1", "pdf"))
    assert (m["From"], m["To"], m["Subject"]) == ("equipo@gmail.com", "mant@x.com", "Asunto")
    adjuntos = list(m.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "ciclo_000012.pdf"
    assert adjuntos[0].get_content_type() == "application/pdf"
    assert adjuntos[0].get_content() == b"%PDF-1"


def test_enviar_con_starttls_y_login():
    sesion = MagicMock()
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = sesion
    config = ConfigCorreo("equipo@gmail.com", "smtp.gmail.com", 587, [], "clave")
    sesion.send_message.return_value = {}
    mensaje = correo.armar_mensaje("equipo@gmail.com", "mant@x.com", "A", "C",
                                   ("c.pdf", b"%PDF", "pdf"))
    r = correo.enviar(config, mensaje, smtp=smtp)
    smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=20)
    sesion.starttls.assert_called_once()
    sesion.login.assert_called_once_with("equipo@gmail.com", "clave")
    # C2 (tanda 7): envelope explícito y resultado por destinatario
    sesion.send_message.assert_called_once_with(mensaje, from_addr="equipo@gmail.com",
                                                to_addrs=["mant@x.com"])
    assert r.aceptados == ("mant@x.com",) and r.rechazados == {}
