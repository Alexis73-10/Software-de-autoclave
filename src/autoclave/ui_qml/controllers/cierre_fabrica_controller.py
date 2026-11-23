# ui_qml/controllers/cierre_fabrica_controller.py
#
# Modo fábrica, Etapa 5: OPCIONES › Opciones avanzadas › Cierre de
# fabricación. Solo presenta lo que publica el backend (GET /fabrica/cierre):
# resumen de lo que se borra y lo que queda, USB, precondiciones y estado del
# cierre en curso (etapa, error, resultado). `iniciar(clave)` envía POST
# /fabrica/cierre con la contraseña del ingeniero; el backend decide todo
# (409/403) y el avance se sondea cada segundo mientras el cierre corre.
# Sin HTTP síncrono en la GUI. La pantalla nunca deduce el modo fábrica ni el
# rol: la muestra Opciones avanzadas con UiBridge.modoFabrica y la sesión.

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

RUTA = "/fabrica/cierre"
SONDEO_MS = 1000
PLAZO_POST_S = 15.0
ORDEN_CONTEOS = ("ciclos", "lecturas", "alarmas", "bitacora", "mantenimientos", "operadores",
                 "usuarios_prueba", "catalogo_carga")

# Errores publicados por el hilo del cierre (estado.error.codigo) -> texto
_ERRORES_CIERRE = {
    "usb_ausente": "cierre_fabrica.err_usb_ausente",
    "usb_no_escribible": "cierre_fabrica.err_usb_no_escribible",
    "usb_sin_espacio": "cierre_fabrica.err_usb_sin_espacio",
    "cierre_estado_no_permitido": "cierre_fabrica.err_estado",
    "marca_no_escrita": "cierre_fabrica.err_marca",
}
_ERRORES_PAQUETE = frozenset({"sin_base", "error_generacion", "ilegible", "sin_manifiesto",
                              "manifiesto_invalido", "manifiesto_alterado", "tipo_invalido",
                              "archivo_faltante", "archivo_no_declarado", "hash_invalido",
                              "paquete_no_verifica"})


def mensaje_error_cierre(codigo: str) -> str:
    if codigo in _ERRORES_CIERRE:
        return _ERRORES_CIERRE[codigo]
    if codigo in _ERRORES_PAQUETE:
        return "cierre_fabrica.err_paquete"
    return "cierre_fabrica.err_generico"


def mensaje_post(causa: str) -> str:
    """Texto de un rechazo de POST /fabrica/cierre."""
    if causa == "cierre_en_curso":
        return "fabrica.err_cierre_en_curso"
    return sesion_backend.clave_mensaje(causa, RUTA)


def _bytes(b) -> str:
    if not isinstance(b, (int, float)) or isinstance(b, bool):
        return ""
    return f"{b / 1e9:.1f} GB" if b >= 1e8 else f"{b / 1e6:.0f} MB"


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


class CierreFabricaController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    enviandoChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._d: dict = {}
        self._mensaje = ""
        self._enviando = False
        self._gen = 0
        self._timer = QTimer(self)
        self._timer.setInterval(SONDEO_MS)
        self._timer.timeout.connect(self.cargar)
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── lectura ───────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen += 1
        gen = self._gen
        sesion_backend.enviar_async(self._s(), "GET", RUTA, None,
                                    lambda r: self._al_cargar(r, gen), dueno=self)

    def _al_cargar(self, r, gen: int) -> None:
        if gen != self._gen:
            return
        if r.ok and isinstance(r.datos, dict):
            anterior = self._cierre()
            self._d = r.datos
            cierre = self._cierre()
            error = cierre.get("error")
            if isinstance(error, dict) and error != anterior.get("error"):
                self._fijar_mensaje(mensaje_error_cierre(str(error.get("codigo") or "")))
            self.datosChanged.emit()
        elif not self._d:
            self._fijar_mensaje(sesion_backend.clave_mensaje(r.causa, RUTA))
        self._ajustar_sondeo()

    def _ajustar_sondeo(self) -> None:
        if self.enCurso and not self._timer.isActive():
            self._timer.start()
        elif not self.enCurso and self._timer.isActive():
            self._timer.stop()

    # ── iniciar ───────────────────────────────────────────────────────
    @Slot(str, result=bool)
    def iniciar(self, clave: str) -> bool:
        """POST con la contraseña; False sin enviar (vacía, ya enviando o con
        el cierre en curso). El resultado llega por `mensaje` y la lectura."""
        if not clave or self._enviando or self.enCurso:
            return False
        self._enviando = True
        self.enviandoChanged.emit()
        self._fijar_mensaje("")
        cuerpo = {"clave": clave}
        if self.unidad:
            cuerpo["unidad"] = self.unidad
        sesion_backend.enviar_async(self._s(), "POST", RUTA, cuerpo, self._al_iniciar,
                                    dueno=self, plazo_s=PLAZO_POST_S)
        return True

    def _al_iniciar(self, r) -> None:
        self._enviando = False
        self.enviandoChanged.emit()
        if not r.ok:
            self._fijar_mensaje(mensaje_post(r.causa))
        self.cargar()
        if r.ok and not self._timer.isActive():
            self._timer.start()

    # ── propiedades ───────────────────────────────────────────────────
    def _cierre(self) -> dict:
        c = self._d.get("cierre")
        return c if isinstance(c, dict) else {}

    def _usb(self) -> dict:
        u = self._d.get("usb")
        return u if isinstance(u, dict) else {}

    @Property(bool, notify=datosChanged)
    def cargado(self) -> bool:
        return bool(self._d)

    @Property("QVariantList", notify=datosChanged)
    def conteos(self) -> list:
        """[{clave: "cierre_fabrica.conteo_<x>", n}] en orden fijo."""
        resumen = self._d.get("resumen") if isinstance(self._d.get("resumen"), dict) else {}
        c = resumen.get("conteos") if isinstance(resumen.get("conteos"), dict) else {}
        return [{"clave": f"cierre_fabrica.conteo_{k}", "n": int(c[k])}
                for k in ORDEN_CONTEOS if isinstance(c.get(k), int)]

    @Property(str, notify=datosChanged)
    def unidad(self) -> str:
        return str(self._usb().get("unidad") or "")

    @Property(str, notify=datosChanged)
    def libre(self) -> str:
        return _bytes(self._usb().get("libre_bytes"))

    @Property(str, notify=datosChanged)
    def requerido(self) -> str:
        return _bytes(self._usb().get("requerido_bytes"))

    @Property(bool, notify=datosChanged)
    def precondicionesOk(self) -> bool:
        p = self._d.get("precondiciones")
        return isinstance(p, dict) and p.get("ok") is True

    @Property("QVariantList", notify=datosChanged)
    def motivos(self) -> list:
        """[{clave: "cierre_fabrica.motivo_<codigo>", detalle}]."""
        p = self._d.get("precondiciones") if isinstance(self._d.get("precondiciones"), dict) else {}
        lista = p.get("motivos") if isinstance(p.get("motivos"), list) else []
        salida = []
        for m in lista:
            if isinstance(m, dict):
                codigo = str(m.get("codigo") or "")
                salida.append({"clave": f"cierre_fabrica.motivo_{codigo}",
                               "detalle": str(m.get("motivo") or "")})
        return salida

    @Property(bool, notify=datosChanged)
    def enCurso(self) -> bool:
        return self._cierre().get("en_curso") is True

    @Property(str, notify=datosChanged)
    def etapa(self) -> str:
        return str(self._cierre().get("etapa") or "")

    @Property(float, notify=datosChanged)
    def progreso(self) -> float:
        p = self._cierre().get("progreso")
        return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) else 0.0

    def _resultado(self) -> dict:
        r = self._cierre().get("resultado")
        return r if isinstance(r, dict) else {}

    @Property(bool, notify=datosChanged)
    def terminado(self) -> bool:
        """Marca escrita: el resultado está y el software se va a reiniciar."""
        return bool(self._resultado()) and self.etapa == "reiniciando"

    @Property(str, notify=datosChanged)
    def rutaPaquete(self) -> str:
        return str(self._resultado().get("ruta_paquete") or "")

    @Property(str, notify=datosChanged)
    def hashPaquete(self) -> str:
        return str(self._resultado().get("hash_paquete") or "")

    @Property(bool, notify=enviandoChanged)
    def enviando(self) -> bool:
        return self._enviando

    @Property(bool, notify=datosChanged)
    def puedeIniciar(self) -> bool:
        return self.precondicionesOk and not self.enCurso and not self._enviando

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(CierreFabricaController, "Autoclave.Controllers", 1, 0, "CierreFabricaController")
