# ui_qml/controllers/respaldo_controller.py
#
# OPCIONES › Respaldo (O2h, tanda 6; mockup 12 de docs/mockups/tanda6/
# APROBADO.md): USB detectada, casillas de qué exportar, "Exportar a USB",
# lista de respaldos (Válido / Rechazado con el motivo) y "Restaurar
# seleccionado" con confirmación. El backend valida todo (manifiesto, versión,
# número de serie) y decide (403/409/422/428).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

PARTES = ("perfil_calibracion", "parametros_programas", "usuarios", "historial")

_MENSAJES = {
    "usb_no_detectada": "respaldo.err_usb",
    "usb_no_escribible": "respaldo.err_usb_escritura",
    "sin_partes": "respaldo.err_sin_partes",
    "otra_serie": "respaldo.motivo_otra_serie",
    "version": "respaldo.motivo_version",
    "formato": "respaldo.motivo_formato",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "respaldo.err_invalido")


class RespaldoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    seleccionChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._d: dict = {}
        self._mensaje = ""
        self._partes = {"perfil_calibracion": True, "parametros_programas": True,
                        "usuarios": True, "historial": False}
        self._seleccion = ""
        self._reinicio = False

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/backup/usb")
        if r.ok and isinstance(r.datos, dict):
            self._d = r.datos
        else:
            self._d = {}
            self._fijar_mensaje(mensaje_de(r.causa))
        if self._seleccion and not any(f["archivo"] == self._seleccion for f in self.respaldos):
            self._seleccion = ""
            self.seleccionChanged.emit()
        self.datosChanged.emit()

    # ── exportar ──────────────────────────────────────────────────────
    @Slot(str, bool)
    def fijarParte(self, parte: str, valor: bool) -> None:
        if parte in PARTES:
            self._partes[parte] = bool(valor)
            self.seleccionChanged.emit()

    @Property("QVariantMap", notify=seleccionChanged)
    def partes(self) -> dict:
        return dict(self._partes)

    @Property(list, constant=True)
    def listaPartes(self) -> list:
        return list(PARTES)

    @Slot(result=bool)
    def exportar(self) -> bool:
        if not self.unidad:
            self._fijar_mensaje("respaldo.err_usb")
            return False
        r = self._s().enviar("POST", "/backup/export", {"unidad": self.unidad, **self._partes})
        if r.ok:
            self._fijar_mensaje("respaldo.exportado")
            self.cargar()
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    # ── restaurar ─────────────────────────────────────────────────────
    @Slot(str)
    def seleccionar(self, archivo: str) -> None:
        fila = next((f for f in self.respaldos if f["archivo"] == archivo), None)
        nuevo = archivo if fila and fila.get("valido") else ""
        if nuevo != self._seleccion:
            self._seleccion = nuevo
            self.seleccionChanged.emit()

    @Property(str, notify=seleccionChanged)
    def seleccion(self) -> str:
        return self._seleccion

    @Slot(result=bool)
    def restaurar(self) -> bool:
        if not self._seleccion:
            return False
        r = self._s().enviar("POST", "/backup/restore",
                             {"unidad": self.unidad, "archivo": self._seleccion, "confirmar": True})
        if r.ok:
            self._reinicio = bool((r.datos or {}).get("reinicio_requerido"))
            self._fijar_mensaje("respaldo.restaurado_reinicio" if self._reinicio
                                else "respaldo.restaurado")
            self.cargar()
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        self.cargar()
        return False

    # ── propiedades ───────────────────────────────────────────────────
    def _unidades(self) -> list:
        u = self._d.get("unidades")
        return [x for x in u if isinstance(x, dict)] if isinstance(u, list) else []

    @Property(str, notify=datosChanged)
    def unidad(self) -> str:
        u = self._unidades()
        return str(u[0].get("ruta") or "") if u else ""

    @Property(str, notify=datosChanged)
    def libre(self) -> str:
        u = self._unidades()
        b = u[0].get("libre_bytes") if u else None
        return f"{b / 1e9:.1f} GB" if isinstance(b, (int, float)) else ""

    @Property("QVariantList", notify=datosChanged)
    def respaldos(self) -> list:
        u = self._unidades()
        lista = u[0].get("respaldos") if u else None
        return [dict(f) for f in lista if isinstance(f, dict)] if isinstance(lista, list) else []

    @Property(str, notify=datosChanged)
    def serie(self) -> str:
        return str(self._d.get("serie") or "")

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(RespaldoController, "Autoclave.Controllers", 1, 0, "RespaldoController")
