# ui_qml/bridge/selector_ciclo.py
#
# Selector de ciclo de Preciclo (B6, tanda 4). Dos llamadas, fuera del hilo de
# la GUI:
#   GET  /programas/seleccionables  -> lista ya ordenada (los 3 más usados
#                                      primero, marcados) y si hoy se puede cambiar
#   POST /cycle/select              -> el MISMO camino que ya usa el cambio de
#                                      programa (UIServiceBackend.select_cycle);
#                                      no exige sesión, como hoy.
# El backend decide si el cambio se permite (ciclo en curso, estado seguro,
# paro, modo prueba...); aquí solo se muestra su motivo, nunca un fallo genérico.

import logging
import threading

import requests
from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)


from autoclave.ui_qml.domain.nombres_ciclo import nombre_programa  # noqa: E402


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="selector-ciclo").start()


def _numero(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "—"


def _temp_vigente(v) -> str:
    """Temperatura del programa en la unidad vigente (U1), "—" sin número."""
    from autoclave.core.runtime import unidades as u
    from autoclave.ui_qml.domain.pantalla_ciclo import _vigentes
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "—"
    unidad = _vigentes()[0]
    return f"{round(u.temp_a_mostrar(float(v), unidad), 1):g} {u.simbolo_temp(unidad)}"


def fila_presentable(p: dict) -> dict | None:
    """Fila de la lista lista para QML; None si está mal formada."""
    if not isinstance(p, dict) or not p.get("cycle_id"):
        return None
    return {
        "cycleId": str(p["cycle_id"]),
        "numero": str(p.get("numero", "")),
        # I4 (tanda 6): nombre en el idioma vigente y temperatura en la unidad vigente
        "nombre": str(nombre_programa(p.get("nombre", ""), p.get("nombres")) or ""),
        "parametros": f"{_temp_vigente(p.get('temperatura'))} · {_numero(p.get('tiempo'))} min",
        "masUsado": p.get("mas_usado") is True,
        "seleccionado": p.get("seleccionado") is True,
    }


def motivo_de_rechazo(exc) -> str:
    """Texto del `detail` que devolvió el backend; "" si no hubo respuesta HTTP."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return ""
    try:
        detalle = resp.json().get("detail")
    except Exception:
        detalle = None
    return detalle if isinstance(detalle, str) and detalle else f"HTTP {resp.status_code}"


class SelectorCiclo(QObject):
    programasChanged = Signal()
    estadoChanged = Signal()
    ocupadoChanged = Signal()
    elegido = Signal()                     # el backend aceptó el cambio
    _lista_recibida = Signal(int, object)  # emitidas desde el hilo de trabajo
    _eleccion_terminada = Signal(bool, str, bool)

    def __init__(self, backend_client, door: int = 1, parent=None, ejecutar=_en_hilo,
                 ui_service=None):
        super().__init__(parent)
        self._backend = backend_client
        self._ui = ui_service           # para refrescar el caché de /cycle al cambiar
        self._origen = f"puerta_{door}" if door in (1, 2) else "desconocido"
        self._ejecutar = ejecutar
        self._programas: list = []
        self._seleccionable = False
        self._mensaje = ""
        self._sin_conexion = False
        self._ocupado = False
        self._pedido = 0
        self._lista_recibida.connect(self._al_recibir_lista)
        self._eleccion_terminada.connect(self._al_terminar_eleccion)

    # ── lista ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._pedido += 1
        numero = self._pedido

        def tarea():
            try:
                datos = self._backend.get("/programas/seleccionables")
            except Exception as e:
                logger.warning("Selector de ciclo: no se pudo leer la lista: %s", e)
                datos = None
            self._lista_recibida.emit(numero, datos)

        self._ejecutar(tarea)

    def _al_recibir_lista(self, numero: int, datos) -> None:
        if numero != self._pedido:
            return                              # respuesta vieja
        if not isinstance(datos, dict) or not isinstance(datos.get("programas"), list):
            self._programas, self._seleccionable = [], False
            self._sin_conexion, self._mensaje = True, ""
        else:
            self._programas = [f for f in map(fila_presentable, datos["programas"]) if f]
            self._seleccionable = datos.get("seleccionable") is True
            self._sin_conexion = False
            self._mensaje = "" if self._seleccionable else str(datos.get("motivo") or "")
        self.programasChanged.emit()
        self.estadoChanged.emit()

    # ── elegir ───────────────────────────────────────────────────────────
    @Slot(str)
    def elegir(self, cycle_id: str) -> None:
        if self._ocupado or not cycle_id:
            return
        self._fijar_ocupado(True)

        def tarea():
            try:
                self._backend.post("/cycle/select", {"cycle_id": cycle_id, "origen": self._origen})
            except requests.HTTPError as e:
                self._eleccion_terminada.emit(False, motivo_de_rechazo(e), False)
                return
            except Exception as e:
                logger.warning("Selector de ciclo: sin respuesta al elegir: %s", e)
                self._eleccion_terminada.emit(False, "", True)
                return
            try:
                if self._ui is not None:
                    self._ui.refrescar_cache()
            except Exception:
                logger.exception("Selector de ciclo: no se pudo refrescar el caché")
            self._eleccion_terminada.emit(True, "", False)

        self._ejecutar(tarea)

    def _al_terminar_eleccion(self, ok: bool, motivo: str, sin_conexion: bool) -> None:
        self._fijar_ocupado(False)
        self._sin_conexion = sin_conexion
        self._mensaje = "" if ok else motivo
        self.estadoChanged.emit()
        if ok:
            self.elegido.emit()

    @Slot()
    def limpiarMensaje(self) -> None:
        if self._mensaje or self._sin_conexion:
            self._mensaje, self._sin_conexion = "", False
            self.estadoChanged.emit()

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    @Property(list, notify=programasChanged)
    def programas(self) -> list:
        return self._programas

    @Property(bool, notify=estadoChanged)
    def seleccionable(self) -> bool:
        return self._seleccionable

    @Property(str, notify=estadoChanged)
    def mensaje(self) -> str:
        """Motivo textual que dio el backend (rechazo o por qué no se puede cambiar)."""
        return self._mensaje

    @Property(bool, notify=estadoChanged)
    def sinConexion(self) -> bool:
        return self._sin_conexion

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado
