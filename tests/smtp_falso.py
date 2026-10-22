# tests/smtp_falso.py
#
# C2 (tanda 7): servidor SMTP falso LOCAL (127.0.0.1, puerto libre) para
# probar el envío de correo con el smtplib real, sin red. Habla lo mínimo de
# RFC 5321 (EHLO/HELO, MAIL, RCPT, DATA, RSET, NOOP, QUIT) y anuncia
# STARTTLS/AUTH, pero `SMTPSinTLS` (abajo) se salta esos dos pasos: el falso
# no cifra. Los destinatarios de `rechazar` reciben 550 en RCPT TO, como un
# relay real que no acepta una dirección (smtplib NO lanza excepción si al
# menos uno se acepta: devuelve el dict de rechazados).
# No es una prueba: lo importan las pruebas de correo.

import smtplib
import socketserver
import threading


class _Manejador(socketserver.StreamRequestHandler):
    def _responder(self, linea: str) -> None:
        self.wfile.write((linea + "\r\n").encode("ascii"))
        self.wfile.flush()

    def handle(self) -> None:
        srv = self.server.falso
        self._responder("220 smtp-falso listo")
        remitente, destinatarios = None, []
        while True:
            crudo = self.rfile.readline()
            if not crudo:
                return
            linea = crudo.decode("utf-8", "replace").rstrip("\r\n")
            orden = linea[:4].upper()
            if orden in ("EHLO", "HELO"):
                self._responder("250-smtp-falso")
                self._responder("250-STARTTLS")
                self._responder("250 AUTH PLAIN LOGIN")
            elif orden == "MAIL":
                remitente, destinatarios = linea.split(":", 1)[1].strip().strip("<>"), []
                self._responder("250 OK")
            elif orden == "RCPT":
                dir_ = linea.split(":", 1)[1].strip().strip("<>")
                srv.rcpt.append(dir_)
                if dir_.lower() in srv.rechazar:
                    self._responder("550 5.1.1 buzon inexistente")
                else:
                    destinatarios.append(dir_)
                    self._responder("250 OK")
            elif orden == "DATA":
                if not destinatarios:
                    self._responder("554 sin destinatarios")
                    continue
                self._responder("354 fin con <CRLF>.<CRLF>")
                datos = []
                while True:
                    l = self.rfile.readline()
                    if not l or l in (b".\r\n", b".\n"):
                        break
                    datos.append(l)
                srv.entregados.append({"de": remitente, "para": list(destinatarios),
                                       "datos": b"".join(datos)})
                self._responder("250 OK entregado")
            elif orden == "RSET":
                remitente, destinatarios = None, []
                self._responder("250 OK")
            elif orden == "NOOP":
                self._responder("250 OK")
            elif orden == "QUIT":
                self._responder("221 adios")
                return
            else:
                self._responder("502 no implementado")


class _Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class SmtpFalso:
    """Uso: `with SmtpFalso(rechazar={"x@y.com"}) as s: ... s.puerto ...`."""

    def __init__(self, rechazar=()):
        self.rechazar = {r.lower() for r in rechazar}
        self.rcpt = []          # todas las direcciones pedidas en RCPT TO
        self.entregados = []    # [{"de", "para", "datos"}] por cada DATA aceptado
        self._srv = None

    def __enter__(self):
        self._srv = _Servidor(("127.0.0.1", 0), _Manejador)
        self._srv.falso = self
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._srv.shutdown()
        self._srv.server_close()

    @property
    def puerto(self) -> int:
        return self._srv.server_address[1]


class SMTPSinTLS(smtplib.SMTP):
    """smtplib.SMTP real, sin STARTTLS ni AUTH (el falso no cifra)."""

    def starttls(self, *a, **k):
        return (220, b"ok")

    def login(self, usuario, clave, **k):
        self.credenciales = (usuario, clave)
        return (235, b"ok")
