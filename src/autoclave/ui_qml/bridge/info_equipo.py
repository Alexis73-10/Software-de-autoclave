# ui_qml/bridge/info_equipo.py
#
# Datos del equipo para la pantalla de ciclo: modelo y serie (recuadro inferior
# izquierdo) y el panel "Información del equipo" que abre al tocarlo.
#
# Fuentes:
#   - perfil de instalación (installation_profile.json, vía installation.storage)
#   - versión del software (metadatos del paquete, igual que el ticket de arranque)
#   - ciclos realizados / último ciclo: GET /cycle/history?limite=1, consultado
#     fuera del hilo de la GUI al abrir el panel
# Sin fuente en el código (se muestran como "No disponible"): fecha del último
# mantenimiento y versión de la tarjeta.

import importlib.metadata
import logging
import threading
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)


def cargar_perfil():
    """Perfil de instalación o None. Solo para mostrar datos: no aplica el
    chequeo de reloj ni lanza el asistente (eso sigue en autoclave/main.py)."""
    from autoclave.installation import storage
    try:
        return storage.load() if storage.exists() else None
    except Exception as e:
        logger.warning("No se pudo leer el perfil de instalación: %s", e)
        return None


def version_software() -> str | None:
    try:
        return importlib.metadata.version("autoclave")
    except importlib.metadata.PackageNotFoundError:
        return None


def _valor_enum(v):
    return getattr(v, "value", v)


def _fecha_hora(texto) -> str | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return texto


def _fila(clave, valor, disponible=True) -> dict:
    """valor None = dato desconocido por ahora ("—"); disponible False = sin
    fuente en el software ("No disponible")."""
    return {"clave": clave, "valor": None if valor is None else str(valor), "disponible": disponible}


def filas_equipo(perfil, door: int, version_sw, historial) -> list[dict]:
    """historial: None = aún no se pudo consultar; [] = sin ciclos; [fila] = último ciclo."""
    p = perfil
    ultimo = historial[0] if historial else None
    if historial is None:
        ciclos = None
    elif ultimo is None:
        ciclos = 0
    else:
        ciclos = ultimo.get("numero_ciclo")

    ultimo_ciclo = None
    if ultimo is not None:
        fecha = _fecha_hora(ultimo.get("fecha_inicio"))
        resultado = ultimo.get("resultado") or ""
        ultimo_ciclo = f"{fecha or ''}  {resultado}".strip() or None

    return [
        _fila("modelo", p.model_id if p else None),
        _fila("serie", p.serial_number if p else None),
        _fila("id_maquina", p.machine_id if p else None),
        _fila("clase", _valor_enum(p.equipment_class) if p else None),
        _fila("puertas", p.door_count if p else None),
        _fila("tipo_puerta", _valor_enum(p.door_type) if p else None),
        _fila("puerta_pantalla", door),
        _fila("enfriamiento", p.cooling_level if p else None),
        _fila("fecha_instalacion", p.created_at.strftime("%Y-%m-%d") if p else None),
        _fila("ciclos_realizados", ciclos),
        _fila("ultimo_ciclo", ultimo_ciclo),
        _fila("ultimo_mantenimiento", None, disponible=False),
        _fila("version_software", version_sw),
        _fila("version_tarjeta", None, disponible=False),
    ]


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="info-equipo").start()


class InfoEquipo(QObject):
    filasChanged = Signal()
    _historial_recibido = Signal(object)   # emitida desde el hilo de trabajo

    def __init__(self, perfil, door: int, backend_client, version_sw, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._perfil = perfil
        self._door = door
        self._backend = backend_client
        self._version = version_sw
        self._ejecutar = ejecutar
        self._historial = None
        self._consultando = False
        self._filas = filas_equipo(perfil, door, version_sw, None)
        self._historial_recibido.connect(self._al_recibir)

    @Slot()
    def actualizar(self) -> None:
        """Consulta el historial (ciclos realizados / último ciclo) en segundo plano."""
        if self._consultando:
            return
        self._consultando = True

        def tarea():
            try:
                filas = self._backend.get("/cycle/history", params={"limite": 1})
            except Exception as e:
                logger.debug("historial de ciclos no disponible: %s", e)
                filas = None
            self._historial_recibido.emit(filas)

        self._ejecutar(tarea)

    def _al_recibir(self, filas) -> None:
        self._consultando = False
        if isinstance(filas, list):
            self._historial = filas
        # si falla, se conserva el último historial conocido
        nuevas = filas_equipo(self._perfil, self._door, self._version, self._historial)
        if nuevas != self._filas:
            self._filas = nuevas
            self.filasChanged.emit()

    @Property(str, constant=True)
    def modelo(self) -> str:
        return self._perfil.model_id if self._perfil else ""

    @Property(str, constant=True)
    def serie(self) -> str:
        return self._perfil.serial_number if self._perfil else ""

    @Property("QVariantList", notify=filasChanged)
    def filas(self) -> list:
        return self._filas
