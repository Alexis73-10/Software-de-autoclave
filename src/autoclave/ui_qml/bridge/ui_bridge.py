# ui_qml/bridge/ui_bridge.py
#
# Puente de SOLO LECTURA entre UIServiceBackend y QML (F1 de
# planeacion_migracion_qml.md). No abre ningún sondeo HTTP propio: el hilo de
# fondo de UIServiceBackend ya mantiene el caché de /status, /global_params y
# /cycle; aquí un QTimer en el hilo de la GUI lee ese caché (getters con lock,
# sin red) y emite la señal NOTIFY solo cuando el valor cambia.
#
# Sin comandos: los de puerta viven en comandos_puerta.py; inicio de ciclo y
# reset aún no se conectan.

from PySide6.QtCore import (
    Property, QAbstractListModel, QByteArray, QModelIndex, QObject, QTimer, Qt, Signal,
)

from autoclave.ui_qml.domain import pantalla_ciclo as dominio

ESTADO_DESCONOCIDO = "DESCONOCIDO"

# Nivel del backend (AlarmType.name) -> prioridad IEC 60601-1-8.
# Decisión de Cristian (2026-09-29): EMERGENCIA alta, FALLA media, ALERTA baja.
_PRIORIDAD_POR_NIVEL = {"EMERGENCIA": "alta", "FALLA": "media", "ALERTA": "baja"}


# Estados de puerta que la pantalla presenta como "abierta" (acción disponible:
# cerrar). CERRADO, CERRANDO, ATRAPADA, ERROR y DESCONOCIDO -> acción abrir.
_PUERTA_ABIERTA = {"ABIERTO", "ABRIENDO"}


def puerta_abierta(estado_puerta) -> bool:
    return estado_puerta in _PUERTA_ABIERTA


def estado_equipo(machine_state, listo) -> str:
    """Clave de es.json -> estados.* para la columna ESTADO de la pantalla de ciclo."""
    if machine_state == "CICLO":
        return "ejecutando"
    if machine_state == "FALLA":
        return "fallo"
    if machine_state == "PREPARADO" and listo:
        return "listo"
    return "no_preparado"


def prioridad_de(nivel) -> str:
    """Nivel desconocido -> "alta": ante la duda, la presentación más llamativa."""
    return _PRIORIDAD_POR_NIVEL.get(nivel, "alta")


def _texto(valor) -> str:
    return "" if valor is None else str(valor)


def _normalizar_alarmas(alarmas) -> list[dict]:
    """Frontera de confianza: filas mal formadas se descartan, campos ausentes quedan en ""."""
    filas = []
    for a in alarmas if isinstance(alarmas, list) else []:
        if not isinstance(a, dict):
            continue
        nivel = _texto(a.get("level"))
        filas.append({
            "id": _texto(a.get("id")),
            "level": nivel,
            "description": _texto(a.get("description")),
            "source_state": _texto(a.get("source_state")),
            "priority": prioridad_de(nivel),
        })
    return filas


class AlarmListModel(QAbstractListModel):
    """Alarmas activas. Roles: id, level, description, source_state, priority."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    LevelRole = Qt.ItemDataRole.UserRole + 2
    DescriptionRole = Qt.ItemDataRole.UserRole + 3
    SourceStateRole = Qt.ItemDataRole.UserRole + 4
    PriorityRole = Qt.ItemDataRole.UserRole + 5

    _CLAVES = {
        IdRole: "id",
        LevelRole: "level",
        DescriptionRole: "description",
        SourceStateRole: "source_state",
        PriorityRole: "priority",
    }

    countChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._filas)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._filas):
            return None
        clave = self._CLAVES.get(role)
        return None if clave is None else self._filas[index.row()][clave]

    def roleNames(self):
        return {rol: QByteArray(clave.encode()) for rol, clave in self._CLAVES.items()}

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._filas)

    def filas(self) -> list[dict]:
        return [dict(f) for f in self._filas]

    def establecer(self, alarmas) -> bool:
        """Reemplaza el contenido; True si cambió."""
        nuevas = _normalizar_alarmas(alarmas)
        if nuevas == self._filas:
            return False
        conteo_previo = len(self._filas)
        self.beginResetModel()
        self._filas = nuevas
        self.endResetModel()
        if len(nuevas) != conteo_previo:
            self.countChanged.emit()
        return True


class UiBridge(QObject):
    connectedChanged = Signal()
    machineStateChanged = Signal()
    doorStateChanged = Signal()
    estadoEquipoChanged = Signal()
    listoParaCicloChanged = Signal()
    datosCicloChanged = Signal()

    def __init__(self, ui_service, door: int, parent=None, intervalo_ms: int = 500, iniciar: bool = True):
        super().__init__(parent)
        self._ui = ui_service
        self._door = int(door)
        self._nombre_puerta = f"Puerta {self._door}"
        self._connected = False
        self._machine_state = ESTADO_DESCONOCIDO
        self._door_state = ESTADO_DESCONOCIDO
        self._listo = False
        self._estado_equipo = estado_equipo(None, False)
        self._datos_ciclo = self._datos(None, None, None)
        self._alarms = AlarmListModel(self)

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.refrescar)
        if iniciar:
            self._timer.start()
            QTimer.singleShot(0, self.refrescar)

    @staticmethod
    def _datos(ciclo, temp, pres) -> dict:
        return {
            **dominio.parametros_de_ciclo(ciclo),
            "ciclo_activo": dominio.numero_de_ciclo(ciclo),
            "temp_camara": dominio.formatear_temp_camara(temp),
            "presion_camara": dominio.formatear_presion(pres),
        }

    def detener(self) -> None:
        self._timer.stop()

    # ── lectura del caché (hilo de la GUI, sin red) ──────────────────────

    def refrescar(self) -> None:
        # Sin conexión, el caché conserva el último /status recibido: los
        # valores quedan congelados y QML los marca como no vigentes (§6.4).
        self._fijar("_connected", bool(self._ui.connected), self.connectedChanged)
        self._fijar("_machine_state",
                    self._ui.get_estado_global() or ESTADO_DESCONOCIDO,
                    self.machineStateChanged)
        self._fijar("_door_state",
                    self._ui.get_estado_puerta(self._nombre_puerta) or ESTADO_DESCONOCIDO,
                    self.doorStateChanged)
        # Misma bandera que _upd_listo de la UI tkinter (la calcula el backend en PREPARADO)
        self._fijar("_listo", bool(self._ui.get_estado_flag("LISTO_PARA_CICLO")),
                    self.listoParaCicloChanged)
        self._fijar("_estado_equipo", estado_equipo(self._machine_state, self._listo),
                    self.estadoEquipoChanged)
        self._alarms.establecer(self._ui.get_alarmas())

        ciclo = self._ui.get_cycle() or None   # {} = aún no se recibió /cycle
        datos = self._datos(ciclo,
                            self._ui.get_sensores_temp().get("temp_camara"),
                            self._ui.get_sensores_pres().get("pres_camara"))
        self._fijar("_datos_ciclo", datos, self.datosCicloChanged)

    def _fijar(self, atributo: str, valor, senal) -> None:
        if getattr(self, atributo) != valor:
            setattr(self, atributo, valor)
            senal.emit()

    # ── propiedades para QML (solo lectura) ──────────────────────────────

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(str, notify=machineStateChanged)
    def machineState(self) -> str:
        return self._machine_state

    @Property(str, notify=doorStateChanged)
    def doorState(self) -> str:
        return self._door_state

    @Property(bool, notify=doorStateChanged)
    def doorOpen(self) -> bool:
        return puerta_abierta(self._door_state)

    @Property(str, notify=estadoEquipoChanged)
    def estadoEquipo(self) -> str:
        return self._estado_equipo

    @Property(bool, notify=listoParaCicloChanged)
    def listoParaCiclo(self) -> bool:
        return self._listo

    @Property(int, constant=True)
    def door(self) -> int:
        return self._door

    @Property(QObject, constant=True)
    def alarms(self) -> AlarmListModel:
        return self._alarms

    @Property(str, notify=datosCicloChanged)
    def cicloActivo(self) -> str:
        return self._datos_ciclo["ciclo_activo"]

    @Property(str, notify=datosCicloChanged)
    def programa(self) -> str:
        return self._datos_ciclo["programa"]

    @Property(str, notify=datosCicloChanged)
    def tempEsterilizacion(self) -> str:
        return self._datos_ciclo["temp_esterilizacion"]

    @Property(str, notify=datosCicloChanged)
    def tiempoEsterilizacion(self) -> str:
        return self._datos_ciclo["tiempo_esterilizacion"]

    @Property(str, notify=datosCicloChanged)
    def tiempoSecado(self) -> str:
        return self._datos_ciclo["tiempo_secado"]

    @Property(str, notify=datosCicloChanged)
    def tempCamara(self) -> str:
        return self._datos_ciclo["temp_camara"]

    @Property(str, notify=datosCicloChanged)
    def presionCamara(self) -> str:
        return self._datos_ciclo["presion_camara"]
