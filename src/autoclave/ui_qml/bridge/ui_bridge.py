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
    Property, QAbstractListModel, QByteArray, QModelIndex, QObject, QTimer, Qt, Signal, Slot,
)

from autoclave.core.runtime.alarmas_i18n import clave_motivo_bloqueo
from autoclave.ui_qml.domain import entradas_mostradas
from autoclave.ui_qml.domain import pantalla_ciclo as dominio

ESTADO_DESCONOCIDO = "DESCONOCIDO"

# Nivel del backend (campo level, compatibilidad) -> prioridad IEC 60601-1-8.
# Decisión de Cristian (2026-09-29): EMERGENCIA alta, FALLA media, ALERTA baja.
_PRIORIDAD_POR_NIVEL = {"EMERGENCIA": "alta", "FALLA": "media", "ALERTA": "baja"}
# Estado de la tarjeta de E/S en /status (U4 de la tanda 2)
_ESTADOS_TARJETA = ("desconectada", "sin_tramas_validas", "ok")
# S9 (tanda 9, D9-1.2): causas del estado seguro que la UI sabe mostrar
_CAUSAS_ESTADO_SEGURO = ("paro_liberado", "arranque", "fallo", "cancelado", "completado")


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


def _descripciones(textos) -> dict:
    """U10b (tanda 10, D10-1.4): {idioma: descripción} desde `textos` del DTO
    de /status (alarmas_i18n.por_idioma). Solo textos no vacíos; cualquier
    otra forma se ignora (la pantalla usa entonces `description`)."""
    salida = {}
    if isinstance(textos, dict):
        for idioma, t in textos.items():
            d = t.get("descripcion") if isinstance(t, dict) else None
            if isinstance(idioma, str) and isinstance(d, str) and d != "":
                salida[idioma] = d
    return salida


def _campo_por_idioma(textos, campo: str) -> dict:
    """Tanda 17 (ALM-01): {idioma: textos[idioma][campo]} (título o acción) desde
    `textos` del DTO de /status; solo textos no vacíos."""
    salida = {}
    if isinstance(textos, dict):
        for idioma, t in textos.items():
            v = t.get(campo) if isinstance(t, dict) else None
            if isinstance(idioma, str) and isinstance(v, str) and v != "":
                salida[idioma] = v
    return salida


def estado_de_alarma(a) -> str:
    """Tanda 17 (ALM-01): estado para la ventana de detalle. "activa" |
    "reconocida" (con `reconocida_por`) | "resuelta" (RESUELTA_SIN_RECONOCER:
    la condición cesó y falta el reconocimiento) | "" (sin dato)."""
    if not isinstance(a, dict):
        return ""
    estado = a.get("estado")
    if estado == "RESUELTA_SIN_RECONOCER":
        return "resuelta"
    if a.get("reconocida_por"):
        return "reconocida"
    if estado == "ACTIVA":
        return "activa"
    return ""


def _rol_sesion() -> str | None:
    from autoclave.cliente.session_manager import SessionManager
    return SessionManager.current_role()


def visibles_para_rol(alarmas, rol: str | None):
    """LIC-02 (licencia L0): quita las alarmas que solo ven ciertos roles
    (`roles_visibles` del DTO, p. ej. SIS-07 para técnico e ingeniero) si el
    rol de la sesión de esta pantalla no está entre ellos; sin sesión, no se
    muestran. Bandeja de Preciclo y campana usan este mismo modelo."""
    if not isinstance(alarmas, list):
        return alarmas
    salida = []
    for a in alarmas:
        roles = a.get("roles_visibles") if isinstance(a, dict) else None
        if isinstance(roles, list) and roles and rol not in roles:
            continue
        salida.append(a)
    return salida


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
            "descripciones": _descripciones(a.get("textos")),
            # Tanda 17 (ALM-01): detalle de la ventana emergente, de los campos
            # que /status ya entrega (sistema._alarma_dto); ausentes quedan ""
            "codigo": _texto(a.get("codigo")),
            "titulo": _texto(a.get("titulo")),
            "titulos": _campo_por_idioma(a.get("textos"), "titulo"),
            "accion": _texto(a.get("accion")),
            "acciones": _campo_por_idioma(a.get("textos"), "accion"),
            "aparecida": _texto(a.get("aparecida")),
            "estado": estado_de_alarma(a),
            "requiere_reconocimiento": a.get("requiere_reconocimiento") is True,
        })
    return filas


class AlarmListModel(QAbstractListModel):
    """Alarmas activas. Roles: id, level, description, source_state, priority
    y descripciones ({idioma: descripción}, U10b); tanda 17 (ALM-01): codigo,
    titulo, titulos y acciones ({idioma: texto}), accion, aparecida (ISO),
    estado (estado_de_alarma) y requiere_reconocimiento."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    LevelRole = Qt.ItemDataRole.UserRole + 2
    DescriptionRole = Qt.ItemDataRole.UserRole + 3
    SourceStateRole = Qt.ItemDataRole.UserRole + 4
    PriorityRole = Qt.ItemDataRole.UserRole + 5
    DescripcionesRole = Qt.ItemDataRole.UserRole + 6
    CodigoRole = Qt.ItemDataRole.UserRole + 7
    TituloRole = Qt.ItemDataRole.UserRole + 8
    TitulosRole = Qt.ItemDataRole.UserRole + 9
    AccionRole = Qt.ItemDataRole.UserRole + 10
    AccionesRole = Qt.ItemDataRole.UserRole + 11
    AparecidaRole = Qt.ItemDataRole.UserRole + 12
    EstadoRole = Qt.ItemDataRole.UserRole + 13
    RequiereReconocimientoRole = Qt.ItemDataRole.UserRole + 14

    _CLAVES = {
        IdRole: "id",
        LevelRole: "level",
        DescriptionRole: "description",
        SourceStateRole: "source_state",
        PriorityRole: "priority",
        DescripcionesRole: "descripciones",
        CodigoRole: "codigo",
        TituloRole: "titulo",
        TitulosRole: "titulos",
        AccionRole: "accion",
        AccionesRole: "acciones",
        AparecidaRole: "aparecida",
        EstadoRole: "estado",
        RequiereReconocimientoRole: "requiere_reconocimiento",
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

    @Slot(str, result="QVariantMap")
    def detalle(self, id_alarma: str) -> dict:
        """Tanda 17 (ALM-01): la fila vigente de la alarma `id_alarma` ({} si ya
        no está activa); la ventana de detalle la relee al cambiar el modelo."""
        return next((dict(f) for f in self._filas if f["id"] == id_alarma), {})

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
    seguridadChanged = Signal()
    entradasChanged = Signal()

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
        self._datos_ciclo = self._datos(None, None, None, None)
        self._entradas = self._entradas_de(None, {})
        self._alarms = AlarmListModel(self)
        # E5 (tanda 2026-10-14): NO ABRIR, paro, estado seguro y modo prueba
        self._seguridad = self._seguridad_de({})

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.refrescar)
        if iniciar:
            self._timer.start()
            QTimer.singleShot(0, self.refrescar)

    @staticmethod
    def _datos(ciclo, temp, temp_ref, pres) -> dict:
        return {
            **dominio.parametros_de_ciclo(ciclo),
            "ciclo_activo": dominio.numero_de_ciclo(ciclo),
            "temp_camara": dominio.formatear_temp_camara(temp),
            "temp_referencia": dominio.formatear_temp_camara(temp_ref),
            "presion_camara": dominio.formatear_presion(pres),
            # I2 (tanda 5): símbolos de la unidad de presentación (U1)
            "presion_unidad": dominio.simbolo_presion(pres),
            "temp_unidad": dominio.simbolo_temperatura(),
        }

    @staticmethod
    def _entradas_de(ciclo, sensors) -> dict:
        """O3 (tanda 6): filas de las entradas mostradas del programa y las
        series de la gráfica, en la unidad vigente (U1)."""
        t, p, p_atm = dominio._vigentes()
        lista = ciclo.get("entradas_mostradas") if isinstance(ciclo, dict) else None
        no_en_uso = ciclo.get("entradas_no_en_uso") if isinstance(ciclo, dict) else None
        if not isinstance(no_en_uso, list):
            no_en_uso = []
        filas = entradas_mostradas.construir(lista, sensors, no_en_uso, t, p, p_atm)
        series = entradas_mostradas.series_grafica(lista, t, p, no_en_uso)
        # Tanda 17 (SON-01): una entrada de una sonda instalada con rol No en
        # uso (`entradas_no_en_uso` de /cycle) se rotula "(monitoreo)" en QML;
        # se respeta la marca `monitoreo` si el dominio ya la puso
        no = {e for e in no_en_uso if isinstance(e, str)}
        for f in filas:
            if isinstance(f, dict):
                f["monitoreo"] = f.get("monitoreo") is True or f.get("clave") in no
        for s in series:
            if isinstance(s, dict):
                s["monitoreo"] = s.get("monitoreo") is True or s.get("entrada") in no
        return {"filas": filas, "series": series}

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
        # Bandera LISTO_PARA_CICLO (la calcula el backend en PREPARADO)
        self._fijar("_listo", bool(self._ui.get_estado_flag("LISTO_PARA_CICLO")),
                    self.listoParaCicloChanged)
        self._fijar("_estado_equipo", estado_equipo(self._machine_state, self._listo),
                    self.estadoEquipoChanged)
        self._alarms.establecer(visibles_para_rol(self._ui.get_alarmas(), _rol_sesion()))

        ciclo = self._ui.get_cycle() or None   # {} = aún no se recibió /cycle
        temps = self._ui.get_sensores_temp()
        datos = self._datos(ciclo,
                            temps.get("temp_camara"),
                            temps.get("temp_ref"),
                            self._ui.get_sensores_pres().get("pres_camara"))
        self._fijar("_datos_ciclo", datos, self.datosCicloChanged)
        try:
            sensors = self._ui.get_campo("sensors", {})
        except Exception:
            sensors = {}
        self._fijar("_entradas", self._entradas_de(ciclo, sensors), self.entradasChanged)
        self._fijar("_seguridad", self._seguridad_de({
            "no_abrir": self._ui.get_campo("no_abrir", True),
            "motivo": self._ui.get_campo("camara_segura_motivo", ""),
            "motivo_textos": self._ui.get_campo("camara_segura_motivo_textos", None),
            "modo_prueba": self._ui.get_campo("test_mode_active", False),
            # U4: solo el paro real; sin datos de la tarjeta va en "tarjeta"
            "paro": self._ui.get_estado_flag("PARO_REAL"),
            "tarjeta": self._ui.get_campo("estado_tarjeta", "desconectada"),
            "estado_seguro": self._ui.get_campo("estado_seguro", {}),
            "sin_bd": self._ui.get_campo("sin_base_de_datos", False),
        }) if self._connected else self._seguridad_de({}), self.seguridadChanged)

    @staticmethod
    def _seguridad_de(datos: dict) -> dict:
        """Sin conexión o sin dato: NO ABRIR (falla cerrada, como el backend)."""
        es = datos.get("estado_seguro") if isinstance(datos.get("estado_seguro"), dict) else {}
        tarjeta = datos.get("tarjeta")
        return {
            "no_abrir": datos.get("no_abrir", True) is not False,
            "motivo": str(datos.get("motivo") or ""),
            # I4 (tanda 6): el mismo motivo en es/en, si el backend lo mandó
            "motivo_textos": {k: v for k, v in datos["motivo_textos"].items()
                              if isinstance(k, str) and isinstance(v, str) and v}
                             if isinstance(datos.get("motivo_textos"), dict) else {},
            "modo_prueba": datos.get("modo_prueba") is True,
            "paro": bool(datos.get("paro")),
            "es_activo": es.get("activo") is True,
            "es_confirmar": es.get("requiere_confirmacion") is True,
            # S9 (D9-1.2): por qué corre el estado seguro; "" si no se conoce
            "es_causa": es.get("causa") if es.get("causa") in _CAUSAS_ESTADO_SEGURO else "",
            # S4 (CIC-10): el protocolo no puede terminar solo; motivo o ""
            "es_bloqueado": str(es.get("bloqueado_motivo") or ""),
            # V8b (D8-5.11): el mismo motivo como clave del catálogo ("" si no se
            # conoce: la UI muestra el texto tal cual) y si lo causa la sonda Principal
            "es_bloqueado_clave": clave_motivo_bloqueo(es.get("bloqueado_motivo")),
            "es_bloqueado_sonda": "Principal" in str(es.get("bloqueado_motivo") or ""),
            # P-6 (tanda 6): el CONFIRMAR del ciclo confirma también el estado seguro
            "es_ack_confirma": es.get("ack_confirma_estado_seguro") is True,
            # T8: el backend vuelve a exigir la confirmación por ciclo
            "sin_bd": datos.get("sin_bd") is True,
            # U4: falla cerrada, sin dato o valor desconocido = desconectada
            "tarjeta": tarjeta if tarjeta in _ESTADOS_TARJETA else "desconectada",
        }

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

    @Property(bool, notify=seguridadChanged)
    def noAbrir(self) -> bool:
        return self._seguridad["no_abrir"]

    @Property(str, notify=seguridadChanged)
    def noAbrirMotivo(self) -> str:
        """Motivo de NO ABRIR en el idioma vigente (I4); sin traducción, el
        texto en español de siempre."""
        from autoclave import i18n
        return self._seguridad["motivo_textos"].get(i18n.idioma()) or self._seguridad["motivo"]

    @Property(bool, notify=seguridadChanged)
    def modoPrueba(self) -> bool:
        return self._seguridad["modo_prueba"]

    @Property(bool, notify=seguridadChanged)
    def paroActivo(self) -> bool:
        return self._seguridad["paro"]

    @Property(str, notify=seguridadChanged)
    def estadoTarjeta(self) -> str:
        """U4 (tanda 2): "desconectada", "sin_tramas_validas" u "ok"."""
        return self._seguridad["tarjeta"]

    @Property(bool, notify=seguridadChanged)
    def estadoSeguroActivo(self) -> bool:
        return self._seguridad["es_activo"]

    @Property(bool, notify=seguridadChanged)
    def estadoSeguroRequiereConfirmacion(self) -> bool:
        return self._seguridad["es_confirmar"]

    @Property(str, notify=seguridadChanged)
    def estadoSeguroCausa(self) -> str:
        """S9 (D9-1.2): "paro_liberado", "arranque", "fallo", "cancelado",
        "completado" o "" (desconocida)."""
        return self._seguridad.get("es_causa", "")

    @Property(str, notify=seguridadChanged)
    def estadoSeguroBloqueadoMotivo(self) -> str:
        """S4: motivo de CIC-10 (estado seguro detenido); "" si avanza."""
        return self._seguridad.get("es_bloqueado", "")

    @Property(str, notify=seguridadChanged)
    def estadoSeguroBloqueadoClave(self) -> str:
        """V8b: clave del catálogo del motivo de CIC-10 ("" si no se conoce)."""
        return self._seguridad.get("es_bloqueado_clave", "")

    @Property(bool, notify=seguridadChanged)
    def estadoSeguroBloqueoPorSonda(self) -> bool:
        """V8b: el estado seguro está detenido por la sonda Principal."""
        return self._seguridad.get("es_bloqueado_sonda", False)

    @Property(bool, notify=seguridadChanged)
    def ackConfirmaEstadoSeguro(self) -> bool:
        """P-6: CONFIRMAR del ciclo = "Confirmar y llevar a estado seguro"."""
        return self._seguridad.get("es_ack_confirma", False)

    @Property(bool, notify=seguridadChanged)
    def sinBaseDatos(self) -> bool:
        """T8 (§7): el backend opera sin base de datos (OPERANDO_SIN_BD)."""
        return self._seguridad["sin_bd"]

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
    def tempReferencia(self) -> str:
        return self._datos_ciclo["temp_referencia"]

    @Property(str, notify=datosCicloChanged)
    def presionCamara(self) -> str:
        return self._datos_ciclo["presion_camara"]

    @Property("QVariantList", notify=entradasChanged)
    def entradasMostradas(self) -> list:
        """O3: [{clave, tipo, valor, unidad, enUso}] del programa (1 a 3)."""
        return self._entradas["filas"]

    @Property("QVariantList", notify=entradasChanged)
    def seriesGrafica(self) -> list:
        """O3: [{clave, entrada, color, eje, unidad, registrada}] para GraficaCiclo."""
        return self._entradas["series"]

    @Property(str, notify=datosCicloChanged)
    def presionUnidad(self) -> str:
        return self._datos_ciclo["presion_unidad"]

    @Property(str, notify=datosCicloChanged)
    def tempUnidad(self) -> str:
        return self._datos_ciclo["temp_unidad"]
