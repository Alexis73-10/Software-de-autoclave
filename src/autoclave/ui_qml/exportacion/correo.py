# ui_qml/exportacion/correo.py
#
# Envío por SMTP (STARTTLS) de los PDF de ciclos del Historial, con el remitente
# de config_correo. Un ciclo va como PDF; varios, en un ZIP (como lo hacía
# ui_pyside/views/ciclos.py).

import io
import smtplib
import zipfile
from email.message import EmailMessage

from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo

_TIMEOUT_S = 20


def adjunto(pdfs: list[tuple[str, bytes]], nombre_zip: str) -> tuple[str, bytes, str]:
    """(nombre, contenido, subtipo MIME): el PDF solo, o todos en un ZIP."""
    if len(pdfs) == 1:
        nombre, contenido = pdfs[0]
        return nombre, contenido, "pdf"
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in pdfs:
            z.writestr(nombre, contenido)
    return nombre_zip, memoria.getvalue(), "zip"


def armar_mensaje(remitente: str, destino: str, asunto: str, cuerpo: str,
                  archivo: tuple[str, bytes, str]) -> EmailMessage:
    m = EmailMessage()
    m["From"] = remitente
    m["To"] = destino
    m["Subject"] = asunto
    m.set_content(cuerpo)
    nombre, contenido, subtipo = archivo
    m.add_attachment(contenido, maintype="application", subtype=subtipo, filename=nombre)
    return m


def enviar(config: ConfigCorreo, mensaje: EmailMessage, smtp=smtplib.SMTP) -> None:
    """Lanza la excepción de smtplib/socket si algo falla (la presenta el puente)."""
    with smtp(config.servidor, config.puerto, timeout=_TIMEOUT_S) as servidor:
        servidor.ehlo()
        servidor.starttls()
        servidor.login(config.remitente, config.contrasena)
        servidor.send_message(mensaje)
