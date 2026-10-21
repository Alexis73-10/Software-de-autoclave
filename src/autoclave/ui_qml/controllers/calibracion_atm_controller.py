# ui_qml/controllers/calibracion_atm_controller.py
#
# OPCIONES › Mantenimiento › Calibración atmosférica (O2f, tanda 6; mockup 10
# de docs/mockups/tanda6/APROBADO.md) y las dos impresiones de Mantenimiento
# (página de prueba e "Imprimir ganancias y compensaciones").
#
# No mide ni decide nada: el backend corre la ventana (GET/POST
# /maintenance/atm-calibration[...]) y valida. Esta clase sondea el estado
# cada segundo mientras la pantalla está abierta y expone lo necesario para
# la vista. `midiendo` bloquea la navegación (todo salvo Cancelar).

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

RUTA = "/maintenance/atm-calibration"
SONDEO_MS = 1000

CONDICIONES = ("puerta_abierta", "temp_baja", "fuera_de_ciclo", "lecturas_validas")

# código del backend -> clave de texto
_MENSAJES = {
    "precondicion": "calibracion_atm.err_precondicion",
    "calibracion_en_curso": "calibracion_atm.err_en_curso",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}
_IMPRESION = {
    "ok": "calibracion_atm.impreso",
    "estado_no_permitido": "calibracion_atm.err_impresion_ciclo",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class CalibracionAtmController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._d: dict = {}
        self._mensaje = ""
        self._timer = QTimer(self)
        self._timer.setInterval(SONDEO_MS)
        self._timer.timeout.connect(self.cargar)

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── sondeo ─────────────────────────────────────────────────────────
    @Slot()
    def activar(self) -> None:
        self.cargar()
        self._timer.start()

    @Slot()
    def desactivar(self) -> None:
        self._timer.stop()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", RUTA)
        if r.ok and isinstance(r.datos, dict):
            self._d = r.datos
        self.datosChanged.emit()

    def _orden(self, accion: str) -> bool:
        r = self._s().enviar("POST", f"{RUTA}/{accion}")
        if r.ok and isinstance(r.datos, dict):
            self._d = r.datos
            self._fijar_mensaje("")
            self.datosChanged.emit()
            return True
        self.cargar()
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    @Slot(result=bool)
    def iniciar(self) -> bool:
        return self._orden("start")

    @Slot(result=bool)
    def cancelar(self) -> bool:
        return self._orden("cancel")

    @Slot(result=bool)
    def confirmar(self) -> bool:
        return self._orden("confirm")

    @Slot(result=bool)
    def descartar(self) -> bool:
        return self._orden("discard")

    # ── impresiones ───────────────────────────────────────────────────
    def _imprimir(self, ruta: str) -> bool:
        r = self._s().enviar("POST", ruta)
        if r.ok:
            self._fijar_mensaje(_IMPRESION["ok"])
            return True
        datos = r.datos if isinstance(r.datos, dict) else {}
        if r.estado_http == 503:
            self._fijar_mensaje("calibracion_atm.err_impresora")
        elif r.estado_http == 409:
            self._fijar_mensaje(_IMPRESION["estado_no_permitido"])
        else:
            self._fijar_mensaje(mensaje_de(datos.get("codigo") or r.causa))
        return False

    @Slot(result=bool)
    def imprimirPrueba(self) -> bool:
        return self._imprimir("/printer/test-page")

    @Slot(result=bool)
    def imprimirGanancias(self) -> bool:
        return self._imprimir("/maintenance/print/calibration")

    # ── propiedades ───────────────────────────────────────────────────
    @Property(str, notify=datosChanged)
    def estado(self) -> str:
        return str(self._d.get("estado") or "")

    @Property(bool, notify=datosChanged)
    def midiendo(self) -> bool:
        return self.estado == "midiendo"

    @Property(bool, notify=datosChanged)
    def porConfirmar(self) -> bool:
        return self.estado == "por_confirmar"

    @Property(str, notify=datosChanged)
    def motivo(self) -> str:
        return str(self._d.get("motivo") or "")

    @Property(int, notify=datosChanged)
    def muestras(self) -> int:
        v = self._d.get("muestras")
        return v if isinstance(v, int) else 0

    @Property(int, notify=datosChanged)
    def muestrasTotal(self) -> int:
        v = self._d.get("muestras_total")
        return v if isinstance(v, int) and v > 0 else 24

    @Property(float, notify=datosChanged)
    def transcurrido(self) -> float:
        return _num(self._d.get("transcurrido_s")) or 0.0

    @Property(float, notify=datosChanged)
    def duracion(self) -> float:
        return _num(self._d.get("duracion_s")) or 120.0

    @Property(str, notify=datosChanged)
    def tiempoTexto(self) -> str:
        def mmss(s):
            s = max(0, int(s))
            return f"{s // 60:02d}:{s % 60:02d}"
        return f"{mmss(self.transcurrido)} / {mmss(self.duracion)}"

    def _kpa(self, v) -> str:
        n = _num(v)
        return "—" if n is None else f"{n:.2f} kPa"

    @Property(str, notify=datosChanged)
    def promedio(self) -> str:
        return self._kpa(self._d.get("promedio"))

    @Property(str, notify=datosChanged)
    def dispersion(self) -> str:
        return self._kpa(self._d.get("dispersion"))

    @Property(str, notify=datosChanged)
    def referencia(self) -> str:
        return self._kpa((self._d.get("referencia") or {}).get("valor"))

    @Property(str, notify=datosChanged)
    def referenciaFecha(self) -> str:
        f = (self._d.get("referencia") or {}).get("fecha")
        return str(f)[:16].replace("T", " ") if f else ""

    @Property(str, notify=datosChanged)
    def referenciaUsuario(self) -> str:
        return str((self._d.get("referencia") or {}).get("usuario") or "")

    @Property("QVariantMap", notify=datosChanged)
    def condiciones(self) -> dict:
        c = self._d.get("condiciones")
        c = c if isinstance(c, dict) else {}
        return {k: c.get(k) is True for k in CONDICIONES}

    @Property(bool, notify=datosChanged)
    def condicionesCumplidas(self) -> bool:
        return all(self.condiciones.values())

    @Property(list, constant=True)
    def listaCondiciones(self) -> list:
        return list(CONDICIONES)

    @Property("QVariantMap", notify=datosChanged)
    def criterios(self) -> dict:
        c = self._d.get("criterios")
        return c if isinstance(c, dict) else {"promedio_min": 60, "promedio_max": 105,
                                               "dispersion_max": 1.5, "diferencia_confirmar": 5,
                                               "temp_max": 80}

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(CalibracionAtmController, "Autoclave.Controllers", 1, 0,
                "CalibracionAtmController")
