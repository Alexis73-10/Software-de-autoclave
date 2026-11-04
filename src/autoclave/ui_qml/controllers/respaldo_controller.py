# ui_qml/controllers/respaldo_controller.py
#
# OPCIONES › Respaldo (O2h, tanda 6; mockup 12 de docs/mockups/tanda6/
# APROBADO.md): USB detectada, casillas de qué exportar, "Exportar a USB",
# lista de respaldos (Válido / Rechazado con el motivo) y "Restaurar
# seleccionado" con confirmación. El backend valida todo (manifiesto, versión,
# número de serie) y decide (403/409/422/428).
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 5): la lectura
# de la USB (GET) y exportar (POST) son asíncronos (`cargando`, `guardando`;
# un error de lectura conserva la última lista).
#
# Restaurar (FASE 6, P1): `OperacionCritica` sin optimismo. Plazo 60 s, bloquea
# la navegación, una sola a la vez. Solo un 200 es «restaurado»; sin respuesta
# NUNCA se da por hecho ni se reintenta: se relee la lista (solo para
# refrescarla) y queda «sin confirmar» (respaldo.restaurar_sin_confirmar). El
# slot devuelve True = «enviado»; el resultado llega por `operacionResuelta`.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import operacion_critica as oc
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import SIN_LECTURA

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


CLAVE_RESTAURAR = "restaurar"
PLAZO_RESTAURAR_S = 60.0
MENSAJE_RESTAURAR_SIN_CONFIRMAR = "respaldo.restaurar_sin_confirmar"


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "respaldo.err_invalido")


def _mensaje_restaurar(causa: str) -> str:
    """Texto de un rechazo de /backup/restore: el de la pantalla si lo tiene; si
    no, el propio de la ruta (formato, parámetros, calibración...)."""
    if causa in _MENSAJES:
        return _MENSAJES[causa]
    clave = sesion_backend.clave_mensaje(causa, "/backup/restore")
    return clave if clave.startswith("respaldo.") else "respaldo.err_invalido"


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


class RespaldoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    seleccionChanged = Signal()
    cargandoChanged = Signal()
    guardandoChanged = Signal()
    operacionEnCursoChanged = Signal()
    # clave, estado final (confirmada|rechazada|sin_confirmar), clave i18n del mensaje
    operacionResuelta = Signal(str, str, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._d: dict = {}
        self._mensaje = ""
        self._partes = {"perfil_calibracion": True, "parametros_programas": True,
                        "usuarios": True, "historial": False}
        self._seleccion = ""
        self._reinicio = False
        self._resuelto = None
        self._gen = 0
        self._cargando = False
        self._guardando = False
        self._op = oc.OperacionCritica(self, self._s)
        self._op.operacionEnCursoChanged.connect(self.operacionEnCursoChanged)
        self._op.operacionResuelta.connect(self._al_resolver)
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    @Property(bool, notify=guardandoChanged)
    def guardando(self) -> bool:
        """Exportación en vuelo («guardando…», botón bloqueado)."""
        return self._guardando

    def _fijar_cargando(self, v: bool) -> None:
        if v != self._cargando:
            self._cargando = v
            self.cargandoChanged.emit()

    def _fijar_guardando(self, v: bool) -> None:
        if v != self._guardando:
            self._guardando = v
            self.guardandoChanged.emit()

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @Slot()
    def cargar(self) -> None:
        self._gen += 1
        gen = self._gen
        self._fijar_cargando(True)
        sesion_backend.enviar_async(self._s(), "GET", "/backup/usb", None,
                                    lambda r: self._al_cargar(r, gen), dueno=self)

    def _al_cargar(self, r, gen: int) -> None:
        if gen != self._gen:
            return                         # una lectura posterior manda
        self._fijar_cargando(False)
        if r.ok and isinstance(r.datos, dict):
            self._d = r.datos
        else:
            # se conserva la última lista válida
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
        """False si no se puede lanzar (sin USB, o ya hay una exportación en
        vuelo). Con el resultado en el acto (sesión de prueba) devuelve el
        `ok` real; en vuelo, True («aceptado»): el desenlace llega por
        `mensaje`."""
        if self._guardando or self._op.en_curso():
            return False                   # MENOR-6: tampoco con una restauración en vuelo
        if not self.unidad:
            self._fijar_mensaje("respaldo.err_usb")
            return False
        self._resuelto = None
        self._fijar_guardando(True)
        sesion_backend.enviar_async(
            self._s(), "POST", "/backup/export", {"unidad": self.unidad, **self._partes},
            self._al_exportar, dueno=self)
        return True if self._resuelto is None else self._resuelto

    def _al_exportar(self, r) -> None:
        self._fijar_guardando(False)
        if r.ok:
            self._fijar_mensaje("respaldo.exportado")
            self._resuelto = True
            self.cargar()
        else:
            self._fijar_mensaje(mensaje_de(r.causa))
            self._resuelto = False

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

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        """Hay una restauración en vuelo (la pantalla bloquea los botones)."""
        return self._op.operacionEnCurso

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        """inactiva | enviando | verificando."""
        return self._op.estado(clave)

    @Slot(result=bool)
    def restaurar(self) -> bool:
        """True = enviada (el resultado llega por `operacionResuelta`); False
        sin enviar nada (sin selección o ya hay una restauración en curso).
        Sin respuesta nunca se reintenta."""
        if not self._seleccion or self._guardando:
            return False                   # MENOR-6: no con una exportación en vuelo
        archivo = self._seleccion
        cuerpo = {"unidad": self.unidad, "archivo": archivo, "confirmar": True}

        def al_ok(r) -> None:
            datos = r.datos if isinstance(r.datos, dict) else {}
            self._reinicio = bool(datos.get("reinicio_requerido"))
            self._fijar_mensaje("respaldo.restaurado_reinicio" if self._reinicio
                                else "respaldo.restaurado")
            self.cargar()

        return self._op.iniciar(
            CLAVE_RESTAURAR, "POST", "/backup/restore", cuerpo, plazo_s=PLAZO_RESTAURAR_S,
            al_ok=al_ok, al_rechazo=lambda r: _mensaje_restaurar(r.causa),
            releer=self._releer_lista, conciliar=lambda _leido: oc.SIN_CONFIRMAR,
            bloquea_navegacion=True, msg_sin_confirmar=MENSAJE_RESTAURAR_SIN_CONFIRMAR)

    def _releer_lista(self, al_leido) -> None:
        """Relectura de la lista de respaldos, solo para refrescarla: restaurar
        no se puede comprobar con ella, así que nunca concilia como éxito."""
        self._gen += 1
        gen = self._gen
        self._fijar_cargando(True)

        def leido(r) -> None:
            self._al_cargar(r, gen)
            al_leido(r.datos if r.ok and isinstance(r.datos, dict) else SIN_LECTURA)
        sesion_backend.enviar_async(self._s(), "GET", "/backup/usb", None, leido, dueno=self)

    def _al_resolver(self, clave: str, estado: str, mensaje: str) -> None:
        if estado == oc.CONFIRMADA:
            pass                      # al_ok ya fijó el mensaje y relee la lista
        else:
            self._fijar_mensaje(mensaje)
            if estado == oc.RECHAZADA:
                self.cargar()
        self.operacionResuelta.emit(clave, estado, mensaje)

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
