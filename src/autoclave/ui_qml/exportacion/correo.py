# ui_qml/exportacion/correo.py
#
# Envío por SMTP (STARTTLS) de los PDF de ciclos del Historial, con el remitente
# de config_correo. Un ciclo va como PDF; varios, en un ZIP (como lo hacía
# ui_pyside/views/ciclos.py).
#
# C2 (tanda 7): varios destinatarios por envío (los guardados y/o uno escrito
# a mano) y resultado POR DESTINATARIO. smtplib no lanza excepción si el relay
# acepta al menos uno: devuelve el dict de rechazados. Ese dict ya no se
# ignora: `enviar` devuelve qué aceptó el relay y qué rechazó, y quien llama
# decide el mensaje (nunca "enviado" sin aceptación).

import io
import re
import smtplib
import zipfile
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses

from autoclave.ui_qml.exportacion.config_correo import ConfigCorreo

_TIMEOUT_S = 20
_SEPARADORES = re.compile(r"[,;\s]+")


@dataclass(frozen=True)
class ResultadoEnvio:
    """Lo que el relay aceptó y rechazó (dirección -> código SMTP). Sin
    textos del servidor: podrían repetir datos de la sesión."""
    aceptados: tuple = ()
    rechazados: dict = field(default_factory=dict)

    @property
    def todos_aceptados(self) -> bool:
        return bool(self.aceptados) and not self.rechazados

    @property
    def ninguno_aceptado(self) -> bool:
        return not self.aceptados


def separar_destinos(destinos) -> list[str]:
    """Lista limpia de direcciones desde un texto ("a@x.com, b@y.com") o una
    lista: sin espacios, sin vacías y sin repetidas (sin distinguir mayúsculas),
    en el orden en que llegaron. No valida el formato."""
    if not destinos:
        return []
    partes = _SEPARADORES.split(destinos) if isinstance(destinos, str) else \
        [str(d) for d in destinos]
    vistos, salida = set(), []
    for p in partes:
        p = p.strip()
        if p and p.lower() not in vistos:
            vistos.add(p.lower())
            salida.append(p)
    return salida


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


def armar_mensaje(remitente: str, destino, asunto: str, cuerpo: str,
                  archivo: tuple[str, bytes, str]) -> EmailMessage:
    """`destino`: una dirección o una lista (van todas en To)."""
    m = EmailMessage()
    m["From"] = remitente
    m["To"] = ", ".join(separar_destinos(destino))
    m["Subject"] = asunto
    m.set_content(cuerpo)
    nombre, contenido, subtipo = archivo
    m.add_attachment(contenido, maintype="application", subtype=subtipo, filename=nombre)
    return m


def enviar(config: ConfigCorreo, mensaje: EmailMessage, smtp=smtplib.SMTP,
           destinatarios=None) -> ResultadoEnvio:
    """Envía y devuelve lo que el relay aceptó por destinatario. El envelope
    (RCPT TO) es `destinatarios` o, si no se da, las direcciones de To.
    Si el relay rechaza a TODOS devuelve un resultado sin aceptados (no
    lanza). Lanza las excepciones de smtplib/socket de conexión,
    autenticación o datos (las presenta quien llama)."""
    if destinatarios is None:
        destinatarios = [d for _, d in getaddresses(mensaje.get_all("To", [])) if d]
    destinatarios = separar_destinos(destinatarios)
    with smtp(config.servidor, config.puerto, timeout=_TIMEOUT_S) as servidor:
        servidor.ehlo()
        servidor.starttls()
        servidor.login(config.remitente, config.contrasena)
        try:
            rechazados = servidor.send_message(mensaje, from_addr=config.remitente,
                                               to_addrs=destinatarios)
        except smtplib.SMTPRecipientsRefused as e:
            rechazados = e.recipients
    rechazados = rechazados if isinstance(rechazados, dict) else {}
    codigos = {}
    for d, valor in rechazados.items():
        codigo = valor[0] if isinstance(valor, (tuple, list)) and valor else valor
        codigos[d] = codigo if isinstance(codigo, int) else 0
    rechazados_min = {d.lower() for d in codigos}
    aceptados = tuple(d for d in destinatarios if d.lower() not in rechazados_min)
    return ResultadoEnvio(aceptados, codigos)
