# ui_qml/controllers/conectividad_controller.py
#
# OPCIONES › Conectividad (O2g, tanda 6; mockup 11 de docs/mockups/tanda6/
# APROBADO.md). Red en solo lectura (GET /network/status) y correo de ciclos
# (GET/PUT /email/config, POST /email/test). Los permisos los decide el
# backend (403); aquí solo se reflejan con permisos_opciones.motivo_destinatarios
# para deshabilitar los controles del técnico con el motivo (decisión 1.9).
# La contraseña del relay nunca llega a esta capa: el backend solo informa si
# está configurada.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import permisos_opciones as permisos

_MENSAJES = {
    "correo_invalido": "conectividad.err_correo_invalido",
    "duplicado": "conectividad.err_duplicado",
    "demasiados": "conectividad.err_demasiados",
    "nombre_largo": "conectividad.err_nombre_largo",
    "sin_destinatarios": "conectividad.err_sin_destinatarios",
    "correo_no_configurado": "conectividad.err_no_configurado",
    "envio_fallido": "conectividad.err_envio",
    "envio_desactivado": "conectividad.err_desactivado",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class ConectividadController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    rolChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._red: dict = {}
        self._correo: dict = {}
        self._mensaje = ""
        self._rol = ""
        self._estado = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── rol y estado (para el motivo de solo lectura) ─────────────────
    def _get_rol(self):
        return self._rol

    def _set_rol(self, v):
        if v != self._rol:
            self._rol = v or ""
            self.rolChanged.emit()

    rol = Property(str, _get_rol, _set_rol, notify=rolChanged)

    def _get_estado(self):
        return self._estado

    def _set_estado(self, v):
        if v != self._estado:
            self._estado = v or ""
            self.rolChanged.emit()

    estadoMaquina = Property(str, _get_estado, _set_estado, notify=rolChanged)

    @Property(str, notify=rolChanged)
    def motivoEdicion(self) -> str:
        return permisos.motivo_destinatarios(self._rol, self._estado)

    @Property(bool, notify=rolChanged)
    def puedeEditar(self) -> bool:
        return self.motivoEdicion == ""

    # ── carga ─────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/network/status")
        self._red = r.datos if r.ok and isinstance(r.datos, dict) else {}
        r = self._s().enviar("GET", "/email/config")
        if r.ok and isinstance(r.datos, dict):
            self._correo = r.datos
        else:
            self._correo = {}
            self._fijar_mensaje(mensaje_de(r.causa))
        self.datosChanged.emit()

    def _guardar(self, activo: bool, destinatarios: list) -> bool:
        r = self._s().enviar("PUT", "/email/config",
                             {"envio_activo": activo, "destinatarios": destinatarios})
        if r.ok and isinstance(r.datos, dict):
            self._correo = {**self._correo, **r.datos}
            self._fijar_mensaje("")
            self.datosChanged.emit()
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        self.cargar()
        return False

    @Slot(bool, result=bool)
    def fijarEnvio(self, activo: bool) -> bool:
        return self._guardar(bool(activo), self.destinatarios)

    @Slot(str, str, result=bool)
    def agregar(self, nombre: str, correo: str) -> bool:
        correo = (correo or "").strip()
        lista = self.destinatarios + [{"nombre": (nombre or "").strip() or correo, "correo": correo}]
        return self._guardar(self.envioActivo, lista)

    @Slot(int, result=bool)
    def quitar(self, indice: int) -> bool:
        lista = self.destinatarios
        if not 0 <= indice < len(lista):
            return False
        del lista[indice]
        return self._guardar(self.envioActivo, lista)

    @Slot(result=bool)
    def enviarPrueba(self) -> bool:
        r = self._s().enviar("POST", "/email/test")
        if r.ok:
            n = (r.datos or {}).get("enviados") if isinstance(r.datos, dict) else None
            self._fijar_mensaje("conectividad.prueba_enviada")
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    # ── propiedades ───────────────────────────────────────────────────
    @Property(bool, notify=datosChanged)
    def envioActivo(self) -> bool:
        return self._correo.get("envio_activo") is True

    @Property("QVariantList", notify=datosChanged)
    def destinatarios(self) -> list:
        lista = self._correo.get("destinatarios")
        return [dict(d) for d in lista if isinstance(d, dict)] if isinstance(lista, list) else []

    @Property(str, notify=datosChanged)
    def remitente(self) -> str:
        return str(self._correo.get("remitente") or "")

    @Property(str, notify=datosChanged)
    def servidor(self) -> str:
        s = str(self._correo.get("servidor") or "")
        p = self._correo.get("puerto")
        return f"{s}:{p}" if s and isinstance(p, int) else s

    @Property(bool, notify=datosChanged)
    def contrasenaConfigurada(self) -> bool:
        return self._correo.get("contrasena_configurada") is True

    @Property(int, notify=datosChanged)
    def maxDestinatarios(self) -> int:
        v = self._correo.get("max_destinatarios")
        return v if isinstance(v, int) else 10

    @Property("QVariantList", notify=datosChanged)
    def adaptadores(self) -> list:
        lista = self._red.get("adaptadores")
        return [dict(a) for a in lista if isinstance(a, dict)] if isinstance(lista, list) else []

    @Property(str, notify=datosChanged)
    def wifiSsid(self) -> str:
        return str((self._red.get("wifi") or {}).get("ssid") or "")

    @Property(int, notify=datosChanged)
    def wifiSenal(self) -> int:
        v = (self._red.get("wifi") or {}).get("senal")
        return v if isinstance(v, int) else -1

    @Property(bool, notify=datosChanged)
    def redConectada(self) -> bool:
        return self._red.get("conectado") is True

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ConectividadController, "Autoclave.Controllers", 1, 0, "ConectividadController")
