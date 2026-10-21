# ui_qml/controllers/parametros_equipo_controller.py
#
# OPCIONES › Parámetros del equipo (P2, tanda 5; diseño PROVISIONAL). Por ahora
# el interruptor `impresora.habilitada` (decisión 3 de Cristian, 20-oct): lee
# GET /printer/config y escribe PUT /printer/config con el token de la ventana
# (técnico/ingeniero; el backend audita y ajusta el aviso SIS-05). No decide
# nada: el backend es la autoridad.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

_MENSAJES = {
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    "ARCHIVO_NO_ESCRIBIBLE": "opciones.equipo_err_guardar",
    "estado_no_permitido_unidades": "opciones.equipo_err_unidades_ciclo",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class ParametrosEquipoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._impresora = None          # None = se desconoce
        self._unidades = {"temperatura": "", "presion": ""}   # U1; "" = se desconoce
        self._mensaje = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/printer/config")
        valor = r.datos.get("habilitada") if r.ok and isinstance(r.datos, dict) else None
        self._impresora = valor if isinstance(valor, bool) else None
        if self._impresora is None:
            self._fijar_mensaje(mensaje_de(r.causa))
        ru = self._s().enviar("GET", "/units")
        datos = ru.datos if ru.ok and isinstance(ru.datos, dict) else {}
        self._unidades = {"temperatura": str(datos.get("temperatura") or ""),
                          "presion": str(datos.get("presion") or "")}
        self.datosChanged.emit()

    @Slot(bool, result=bool)
    def fijarImpresora(self, habilitada: bool) -> bool:
        r = self._s().enviar("PUT", "/printer/config", {"habilitada": bool(habilitada)})
        if r.ok:
            self._fijar_mensaje("")
            self.cargar()
            return True
        self.cargar()                  # sin respuesta el resultado es incierto: se relee
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    # ── unidades (U1, tanda 5): solo fuera de ciclo, técnico e ingeniero ──

    @Property(str, notify=datosChanged)
    def unidadTemperatura(self) -> str:
        return self._unidades["temperatura"]

    @Property(str, notify=datosChanged)
    def unidadPresion(self) -> str:
        return self._unidades["presion"]

    @Slot(str, str, result=bool)
    def fijarUnidades(self, temperatura: str, presion: str) -> bool:
        r = self._s().enviar("PUT", "/units", {"temperatura": temperatura, "presion": presion})
        self.cargar()
        try:                           # que las pantallas cambien ya, sin esperar el sondeo
            from autoclave.ui_qml.bridge import unidades_qml
            unidades_qml.instancia.refrescar()
        except Exception:
            pass
        if r.ok:
            self._fijar_mensaje("")
            return True
        self._fijar_mensaje("opciones.equipo_err_unidades_ciclo" if r.causa == "estado_no_permitido"
                            else mensaje_de(r.causa))
        return False

    @Property(bool, notify=datosChanged)
    def impresoraConocida(self) -> bool:
        return self._impresora is not None

    @Property(bool, notify=datosChanged)
    def impresoraHabilitada(self) -> bool:
        return bool(self._impresora)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ParametrosEquipoController, "Autoclave.Controllers", 1, 0,
                "ParametrosEquipoController")
