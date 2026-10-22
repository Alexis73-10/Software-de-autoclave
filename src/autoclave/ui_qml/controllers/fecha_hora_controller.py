# ui_qml/controllers/fecha_hora_controller.py
#
# OPCIONES › Fecha y hora (O2c, tanda 6; decisión 1.10 y mockup 7 con el
# cambio aprobado): SOLO LECTURA con la hora del PC (Windows). Muestra hora,
# fecha y zona horaria, y avisa si el reloj es anterior a la fecha de
# instalación (M1-01). No hay ajuste: no se implementa ninguna escritura.
#
# La hora que se ve es la del reloj de pared del PC donde corre la UI (la
# misma máquina que el backend en el equipo); GET /system/time aporta la
# zona, la fecha de instalación y el aviso calculado por el backend.

from datetime import datetime

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

_MENSAJES = {sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta"}


def _ahora():
    return datetime.now().astimezone()


def zona_de(dt: datetime) -> str:
    """"UTC-05:00 (nombre)" con el nombre de zona del sistema si lo hay."""
    off = dt.utcoffset()
    if off is None:
        return ""
    minutos = int(off.total_seconds() // 60)
    signo = "+" if minutos >= 0 else "-"
    h, m = divmod(abs(minutos), 60)
    nombre = dt.tzname() or ""
    base = f"UTC{signo}{h:02d}:{m:02d}"
    return f"{base} ({nombre})" if nombre and not nombre.startswith("UTC") else base


class FechaHoraController(QObject):
    relojChanged = Signal()
    datosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None, reloj=_ahora):
        super().__init__(parent)
        self._sesion = sesion
        self._reloj = reloj
        self._ahora = reloj()
        self._instalacion = ""
        self._anterior = False
        self._zona_backend = ""
        self._mensaje = ""
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.tic)
        self._timer.start()

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    @Slot()
    def tic(self) -> None:
        self._ahora = self._reloj()
        self.relojChanged.emit()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/system/time")
        if r.ok and isinstance(r.datos, dict):
            self._instalacion = str(r.datos.get("instalacion") or "")
            self._anterior = r.datos.get("reloj_anterior_instalacion") is True
            self._zona_backend = str(r.datos.get("zona") or "")
            nuevo = ""
        else:
            nuevo = _MENSAJES.get(r.causa, "opciones.err_generico")
        if nuevo != self._mensaje:
            self._mensaje = nuevo
            self.mensajeChanged.emit()
        self.tic()
        self.datosChanged.emit()

    @Property(str, notify=relojChanged)
    def hora(self) -> str:
        return self._ahora.strftime("%H:%M:%S")

    @Property(str, notify=relojChanged)
    def fechaIso(self) -> str:
        return self._ahora.strftime("%Y-%m-%d")

    @Property(str, notify=relojChanged)
    def zona(self) -> str:
        return self._zona_backend or zona_de(self._ahora)

    @Property(str, notify=datosChanged)
    def instalacion(self) -> str:
        return self._instalacion

    @Property(bool, notify=relojChanged)
    def relojAnterior(self) -> bool:
        """Aviso M1-01: del backend o, si se conoce la instalación, local."""
        if self._anterior:
            return True
        return bool(self._instalacion) and self.fechaIso < self._instalacion[:10]

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje


qmlRegisterType(FechaHoraController, "Autoclave.Controllers", 1, 0, "FechaHoraController")
