# ui_qml/controllers/mantenimiento_controller.py
#
# OPCIONES › Mantenimiento (M1, tanda 3; diseño PROVISIONAL): próximo
# vencimiento, último mantenimiento, ciclos restantes y "Registrar
# mantenimiento realizado". Lee GET /maintenance y escribe POST
# /maintenance/records con el token de la ventana (técnico/ingeniero). No
# calcula nada: el backend decide vencimientos y valida (y nunca bloquea un
# ciclo: esta pantalla solo informa).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import resumen_sistema as dominio

TIPOS = ("preventivo", "correctivo", "calibracion", "otro")

_MENSAJES = {
    "reloj_invalido": "opciones.mant_err_reloj",
    "validacion": "opciones.mant_err_validacion",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class MantenimientoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._datos = dominio.mantenimiento_presentable(None)
        self._estado = ""
        self._mensaje = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/maintenance")
        if r.ok and isinstance(r.datos, dict):
            self._datos = dominio.mantenimiento_presentable(r.datos)
            self._estado = str(r.datos.get("estado") or "")
        else:
            self._datos = dominio.mantenimiento_presentable(None)
            self._estado = ""
            self._fijar_mensaje(mensaje_de(r.causa))
        self.datosChanged.emit()

    @Slot(str, result=bool)
    def registrar(self, tipo: str) -> bool:
        """"Registrar mantenimiento realizado". True si el backend lo guardó."""
        if tipo not in TIPOS:
            return False
        r = self._s().enviar("POST", "/maintenance/records", {"tipo": tipo, "observaciones": ""})
        if r.ok:
            self._fijar_mensaje("")
            self.cargar()
            return True
        # sin respuesta el resultado es incierto: se recarga antes de informar
        self.cargar()
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    @Property(str, notify=datosChanged)
    def proximo(self) -> str:
        return self._datos["proximo"]

    @Property(bool, notify=datosChanged)
    def vencido(self) -> bool:
        return self._datos["vencido"]

    @Property(str, notify=datosChanged)
    def ultimo(self) -> str:
        return self._datos["ultimo"]

    @Property(str, notify=datosChanged)
    def ciclosRestantes(self) -> str:
        return self._datos["ciclos_restantes"]

    @Property(str, notify=datosChanged)
    def estado(self) -> str:
        return self._estado

    @Property(list, constant=True)
    def tipos(self) -> list:
        return list(TIPOS)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(MantenimientoController, "Autoclave.Controllers", 1, 0,
                "MantenimientoController")
