# ui_qml/bridge/registro_carga_qml.py
#
# Registro de la carga con lector (RCB-01, RCB-02, RCB-09; 19-nov). Puente de
# la ventana «Carga del ciclo» de Preciclo, solo en la pantalla de carga
# (puerta 1). La lógica está en ui_qml/domain/registro_carga.BorradorCarga;
# aquí solo el catálogo (GET /carga/catalogo?activos=true, fuera del hilo de
# la GUI, al abrir la ventana), las propiedades para QML y los avisos.
#
# - `leer(texto)`: una lectura del lector (HID con Enter; el QML solo la
#   entrega con la ventana abierta). `leerManual(texto)`: la del teclado en
#   pantalla, marcada «manual» (RCB-01.4).
# - El borrador vive solo en memoria (RCB-02.5): se limpia al iniciar el
#   ciclo con éxito (ComandoIniciarCiclo), con «Vaciar» y al entrar en standby.
# - `requerida`: el programa seleccionado exige la carga y falta (RCB-09.1);
#   se lee de los parámetros del programa (GET /cycle, caché del UIService).
# Nunca envía nada al backend salvo la lectura del catálogo.

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave import i18n
from autoclave.ui_qml.domain import registro_carga as dominio

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="catalogo-carga").start()


class RegistroCarga(QObject):
    cambiado = Signal()
    avisoChanged = Signal()
    requeridaChanged = Signal()
    _catalogo_recibido = Signal(object)

    def __init__(self, backend_client=None, ui_service=None, parent=None, ejecutar=_en_hilo,
                 t=None):
        super().__init__(parent)
        self._backend = backend_client
        self._ui = ui_service
        self._ejecutar = ejecutar
        self._t = t or (lambda clave, **p: i18n.t(clave, **p))
        self._b = dominio.BorradorCarga()
        self._aviso = ""
        self._aviso_tipo = ""
        self._requerida = False
        self._catalogo_recibido.connect(self._al_recibir_catalogo)

    # ── catálogo ─────────────────────────────────────────────────────────
    @Slot()
    def actualizarCatalogo(self) -> None:
        """Al abrir la ventana: nombres del catálogo activo. Sin respuesta se
        conserva el catálogo anterior (los códigos quedan «sin catálogo»)."""
        if self._backend is None:
            return

        def tarea():
            try:
                r = self._backend.get("/carga/catalogo", params={"activos": "true"})
                elementos = r.get("elementos") if isinstance(r, dict) else None
            except Exception as e:
                logger.debug("catálogo de carga no disponible: %s", e)
                elementos = None
            self._catalogo_recibido.emit(elementos)

        self._ejecutar(tarea)

    def _al_recibir_catalogo(self, elementos) -> None:
        if isinstance(elementos, list):
            self._b.fijar_catalogo(elementos)
            self.cambiado.emit()

    # ── lecturas y acciones ──────────────────────────────────────────────
    @Slot(str)
    def leer(self, texto: str) -> None:
        self._aplicar(self._b.leer(texto))

    @Slot(str)
    def leerManual(self, texto: str) -> None:
        self._aplicar(self._b.leer(texto, manual=True))

    def _aplicar(self, resultado) -> None:
        tipo, clave, params = resultado
        self._fijar_aviso(tipo, self._t(clave, **params))
        self.cambiado.emit()
        self.revisarRequerida()

    @Slot(str)
    def quitarUno(self, codigo: str) -> None:
        self._b.quitar_uno(codigo)
        self._fijar_aviso("", "")
        self.cambiado.emit()
        self.revisarRequerida()

    @Slot()
    def cambiarLote(self) -> None:
        self._b.cambiar_lote()
        self._fijar_aviso("", "")
        self.cambiado.emit()
        self.revisarRequerida()

    @Slot()
    def vaciar(self) -> None:
        self._b.vaciar()
        self._fijar_aviso("", "")
        self.cambiado.emit()
        self.revisarRequerida()

    @Slot()
    def limpiar(self) -> None:
        """Inicio aceptado o standby: el borrador no pasa a otro ciclo."""
        self.vaciar()

    def seguir_estado(self, estado) -> None:
        """HAZ-RCB-01 (revisión SAF-01): al entrar la máquina en CICLO el
        borrador se vacía aunque la respuesta 200 del inicio no haya llegado
        (plazo vencido, conexión cortada): el backend ya tomó la carga con
        ese inicio y el borrador no debe pasar al ciclo siguiente. Solo en la
        transición: lo que se lea durante el ciclo queda para el próximo."""
        anterior = getattr(self, "_estado_previo", None)
        self._estado_previo = estado
        if estado == "CICLO" and anterior != "CICLO" and not self._b.vacio():
            logger.info("Máquina en CICLO: se vacía el borrador de la carga")
            self.limpiar()

    def para_inicio(self) -> dict | None:
        return self._b.para_inicio()

    def _fijar_aviso(self, tipo: str, texto: str) -> None:
        if (tipo, texto) != (self._aviso_tipo, self._aviso):
            self._aviso_tipo, self._aviso = tipo, texto
            self.avisoChanged.emit()

    @Slot()
    def revisarRequerida(self) -> None:
        """Lee si el programa seleccionado exige la carga (Preciclo lo llama
        al cambiar el programa o los datos del ciclo)."""
        parametros = None
        try:
            ciclo = self._ui.get_cycle() if self._ui is not None else None
            parametros = ciclo.get("parameters") if isinstance(ciclo, dict) else None
        except Exception:
            parametros = None
        valor = dominio.carga_requerida_falta(parametros, self._b)
        if valor != self._requerida:
            self._requerida = valor
            self.requeridaChanged.emit()

    # ── propiedades para QML ─────────────────────────────────────────────
    @Property(str, notify=cambiado)
    def paso(self) -> str:
        return self._b.paso

    @Property(str, notify=cambiado)
    def lote(self) -> str:
        return self._b.lote

    @Property("QVariantList", notify=cambiado)
    def filas(self) -> list:
        return self._b.filas()

    @Property(int, notify=cambiado)
    def totalCodigos(self) -> int:
        return len(self._b.elementos)

    @Property(int, notify=cambiado)
    def totalUnidades(self) -> int:
        return self._b.total_unidades()

    @Property(bool, notify=cambiado)
    def vacio(self) -> bool:
        return self._b.vacio()

    @Property(str, notify=cambiado)
    def resumen(self) -> str:
        return dominio.resumen_boton(self._b, self._t)

    @Property(str, notify=avisoChanged)
    def aviso(self) -> str:
        return self._aviso

    @Property(str, notify=avisoChanged)
    def avisoTipo(self) -> str:
        """"ok", "error" o "" (sin aviso)."""
        return self._aviso_tipo

    @Property(bool, notify=requeridaChanged)
    def requerida(self) -> bool:
        return self._requerida
