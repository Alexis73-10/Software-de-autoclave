# ui_qml/bridge/info_equipo.py
#
# Datos del equipo para la pantalla de ciclo: modelo y serie (recuadro inferior
# izquierdo) y el panel "Información del equipo" que abre al tocarlo.
#
# Fuentes:
#   - perfil de instalación (installation_profile.json, vía installation.storage)
#   - versión del software (autoclave._version, igual que el ticket de arranque; VER-03)
#   - ciclos realizados / último ciclo: GET /cycle/history?limite=1, consultado
#     fuera del hilo de la GUI al abrir el panel
#   - versión, ID y emparejamiento de la tarjeta de E/S: GET /status (campo
#     `tarjeta`, del último handshake; E6, FW-D2 y FW-D7), en la misma consulta
# Sin fuente en el código (se muestra como "No disponible"): fecha del último
# mantenimiento.

import logging
import threading
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.ui_qml.domain import resumen_sistema as resumen_dominio

logger = logging.getLogger(__name__)


def cargar_perfil():
    """Perfil de instalación o None. Solo para mostrar datos: no aplica el
    chequeo de reloj ni lanza el asistente (los hacen el backend y el
    lanzador)."""
    from autoclave.installation import storage
    try:
        return storage.load() if storage.exists() else None
    except Exception as e:
        logger.warning("No se pudo leer el perfil de instalación: %s", e)
        return None


def version_software() -> str | None:
    # VER-03/VER-05: fuente única, con el commit de la compilación
    from autoclave._version import version_completa
    return version_completa()


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


def _fila_enum(clave, prefijo, valor) -> dict:
    """I4 (tanda 6; D-17): el valor crudo del enum y, si existe, la etiqueta de
    catálogo `equipo.<prefijo><valor>` (la pantalla la muestra en su idioma)."""
    fila = _fila(clave, None if valor is None else _valor_enum(valor))
    if valor is not None:
        from autoclave import i18n
        candidata = f"{prefijo}{_valor_enum(valor)}"
        if i18n.existe(f"equipo.{candidata}"):
            fila["valorClave"] = candidata
    return fila


# FW-D7: emparejada -> clave del texto en la sección "equipo" de es.json
_TEXTO_EMPAREJAMIENTO = {True: "tarjeta_emparejada", False: "tarjeta_no_emparejada"}


def _filas_tarjeta(tarjeta) -> list[dict]:
    t = tarjeta if isinstance(tarjeta, dict) else {}
    emparejamiento = _fila("emparejamiento_tarjeta", None)
    clave = _TEXTO_EMPAREJAMIENTO.get(t.get("emparejada"))
    if clave is not None:
        emparejamiento["valorClave"] = clave
    return [
        _fila("version_tarjeta", t.get("version")),
        _fila("id_tarjeta", t.get("id")),
        emparejamiento,
    ]


def filas_equipo(perfil, door: int, version_sw, historial, tarjeta=None,
                 mantenimiento=None) -> list[dict]:
    """historial: None = aún no se pudo consultar; [] = sin ciclos; [fila] = último ciclo.
    tarjeta: campo `tarjeta` de /status ({version, id, emparejada}) o None.
    mantenimiento: GET /maintenance (M1, tanda 3) o None."""
    p = perfil
    mant = resumen_dominio.mantenimiento_presentable(mantenimiento)

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
        _fila_enum("clase", "clase_", p.equipment_class if p else None),
        _fila("puertas", p.door_count if p else None),
        _fila_enum("tipo_puerta", "tipo_puerta_", p.door_type if p else None),
        _fila("puerta_pantalla", door),
        _fila("enfriamiento", p.cooling_level if p else None),
        _fila("fecha_instalacion", p.created_at.strftime("%Y-%m-%d") if p else None),
        _fila("ciclos_realizados", ciclos),
        _fila("ultimo_ciclo", ultimo_ciclo),
        # M1: la fuente existe (GET /maintenance); O2d (tanda 6): mientras no
        # llega el dato se muestra "—", ya no "No disponible"
        _fila("ultimo_mantenimiento", mant["ultimo"] if mantenimiento is not None else None),
        _fila("ciclos_restantes", mant["ciclos_restantes"] if mantenimiento is not None else None),
        _fila("version_software", version_sw),
        *_filas_tarjeta(tarjeta),
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
        self._tarjeta = None
        self._mantenimiento = None
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
            try:
                status = self._backend.get("/status")
                tarjeta = status.get("tarjeta") if isinstance(status, dict) else None
            except Exception as e:
                logger.debug("estado de la tarjeta no disponible: %s", e)
                tarjeta = None
            try:
                mantenimiento = self._backend.get("/maintenance")
            except Exception as e:
                logger.debug("mantenimiento no disponible: %s", e)
                mantenimiento = None
            self._historial_recibido.emit((filas, tarjeta, mantenimiento))

        self._ejecutar(tarea)

    def _al_recibir(self, datos) -> None:
        self._consultando = False
        filas, tarjeta, mantenimiento = datos
        if isinstance(mantenimiento, dict):
            self._mantenimiento = mantenimiento
        if isinstance(filas, list):
            self._historial = filas
        if isinstance(tarjeta, dict):
            self._tarjeta = tarjeta
        # si falla, se conserva el último dato conocido
        nuevas = filas_equipo(self._perfil, self._door, self._version, self._historial,
                              self._tarjeta, self._mantenimiento)
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
