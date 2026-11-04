"""Doble de sesión para las pruebas de las operaciones críticas de los
controladores de Opciones (FASE 6): guarda cada `enviar_async` y deja que la
prueba decida cuándo y qué entregar. El HTTP síncrono (`enviar`) falla."""
import sys

from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

OK = "ok"
NO_RESPONDE = BACKEND_NO_RESPONDE


def app():
    return QCoreApplication.instance() or QApplication(sys.argv)


def r(causa=OK, datos=None, estado=200):
    return Resultado(causa, {} if datos is None else datos, estado)


class SesionManual:
    generacion = 0

    def __init__(self):
        self.envios = []

    def enviar(self, metodo, ruta, cuerpo=None):          # pragma: no cover
        raise AssertionError(f"HTTP síncrono en la GUI: {metodo} {ruta}")

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        self.envios.append({"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo,
                            "al_terminar": al_terminar, "al_tardio": al_tardio,
                            "plazo_s": plazo_s, "entregado": False})
        return True

    def cancelar_envios(self, dueno):
        return 0

    # -- consulta --
    def indices(self, metodo, ruta):
        return [i for i, e in enumerate(self.envios) if (e["metodo"], e["ruta"]) == (metodo, ruta)]

    def cuenta(self, metodo, ruta):
        return len(self.indices(metodo, ruta))

    def ultimo(self, metodo, ruta):
        idx = self.indices(metodo, ruta)
        return idx[-1] if idx else None

    # -- entrega --
    def responder(self, i, resultado):
        self.envios[i]["entregado"] = True
        self.envios[i]["al_terminar"](resultado)

    def tardio(self, i, resultado):
        self.envios[i]["al_tardio"](resultado)

    def responder_ultimo(self, metodo, ruta, resultado):
        self.responder(self.ultimo(metodo, ruta), resultado)


class Resueltas:
    """Recoge `operacionResuelta(clave, estado, mensaje)` de un controlador."""

    def __init__(self, controlador):
        self.lista = []
        controlador.operacionResuelta.connect(lambda *a: self.lista.append(a))


_VIVOS = []


def conservar(obj: QObject):
    """Los controladores sin padre se destruirían al soltar la referencia."""
    _VIVOS.append(obj)
    return obj
