# ui_qml/bridge/unidades_qml.py
#
# Singleton QML `Unidades` (módulo "Autoclave.Unidades" 1.0), U1 de la tanda 5:
# presentación y entrada de temperatura y presión en las unidades elegidas.
# Toda la conversión vive en core/runtime/unidades.py (neutral, también la usan
# ticket, PDF y correo); aquí solo se expone a QML y se sigue la configuración
# del backend (GET /units cada INTERVALO_MS, en un hilo: el cambio se ve en
# caliente en las dos pantallas del equipo de dos puertas).
#
# Uso en QML (el binding se re-evalúa al cambiar de unidad):
#   import Autoclave.Unidades
#   text: Unidades.temp(valor, Unidades.version)
#   text: Unidades.pres(valor, Unidades.version)

import math
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonType

from autoclave.core.runtime import unidades as u

URI = "Autoclave.Unidades"
INTERVALO_MS = 3000


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


class UnidadesQml(QObject):
    cambiado = Signal()
    _recibido = Signal(object)        # desde el hilo de consulta

    def __init__(self, parent=None, consultar=None, sondear: bool = True):
        super().__init__(parent)
        self._temperatura, self._presion = u.POR_DEFECTO["temperatura"], u.POR_DEFECTO["presion"]
        self._p_atm = None
        self._version = 0
        self._consultar = consultar or self._consultar_backend
        self._ocupado = False
        self._recibido.connect(self._aplicar)
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_MS)
        self._timer.timeout.connect(self.refrescar)
        if sondear:
            self._timer.start()

    # ── seguimiento del backend ────────────────────────────────────────

    @staticmethod
    def _consultar_backend():
        from autoclave.ui_qml.sesion_backend import transporte_http
        estado, datos = transporte_http("GET", "/units", None, None, 1.0)
        return datos if estado == 200 else None

    @Slot()
    def refrescar(self) -> None:
        if self._ocupado:
            return
        self._ocupado = True

        def trabajo():
            try:
                datos = self._consultar()
            except Exception:
                datos = None
            self._recibido.emit(datos)
        threading.Thread(target=trabajo, daemon=True, name="unidades").start()

    def aplicar(self, datos) -> None:
        """Aplica una respuesta de GET /units (también la usan las pruebas)."""
        self._ocupado = False
        if not isinstance(datos, dict):
            return                     # sin respuesta: se conservan las vigentes
        t, p = datos.get("temperatura"), datos.get("presion")
        try:
            u.validar(t, p)
        except ValueError:
            return
        p_atm = u.p_atm_valida(datos.get("p_atm"))
        if (t, p, p_atm) != (self._temperatura, self._presion, self._p_atm):
            self._temperatura, self._presion, self._p_atm = t, p, p_atm
            self._version += 1
            self.cambiado.emit()

    _aplicar = aplicar

    # ── propiedades ────────────────────────────────────────────────────

    @Property(int, notify=cambiado)
    def version(self) -> int:
        return self._version

    @Property(str, notify=cambiado)
    def temperatura(self) -> str:
        return self._temperatura

    @Property(str, notify=cambiado)
    def presion(self) -> str:
        return self._presion

    @Property(str, notify=cambiado)
    def simboloTemp(self) -> str:
        return u.simbolo_temp(self._temperatura)

    @Property(str, notify=cambiado)
    def simboloPres(self) -> str:
        return u.simbolo_pres(self._presion)

    # ── formato (el segundo argumento solo fuerza la re-evaluación) ───

    @Slot("QVariant", result=str)
    @Slot("QVariant", int, result=str)
    def temp(self, valor, _version=0) -> str:
        return u.formatear_temp(_num(valor), self._temperatura)

    @Slot("QVariant", result=str)
    @Slot("QVariant", int, result=str)
    def pres(self, valor, _version=0) -> str:
        return u.formatear_pres(_num(valor), self._presion, self._p_atm)

    @Slot("QVariant", result=str)
    @Slot("QVariant", int, result=str)
    def dtemp(self, valor, _version=0) -> str:
        return u.formatear_dtemp(_num(valor), self._temperatura)

    @Slot("QVariant", result=str)
    @Slot("QVariant", int, result=str)
    def dpres(self, valor, _version=0) -> str:
        return u.formatear_dpres(_num(valor), self._presion)

    @Slot("QVariant", str, str, result=str)
    @Slot("QVariant", str, str, str, result=str)
    def parametro(self, valor, unidad_json: str, nombre: str, clase: str = "") -> str:
        """Valor de un parámetro de ciclo según su clase (absoluto o
        diferencia); sin clase, el número con su unidad original."""
        clase = u.clase_de_unidad(unidad_json, nombre, clase)
        v = _num(valor)
        if clase == "temp":
            return u.formatear_temp(v, self._temperatura)
        if clase == "dtemp":
            return u.formatear_dtemp(v, self._temperatura)
        if clase == "pres":
            return u.formatear_pres(v, self._presion, self._p_atm)
        if clase == "dpres":
            return u.formatear_dpres(v, self._presion)
        return ""                      # sin conversión: el llamador usa su formato

    # ── entrada de datos ───────────────────────────────────────────────

    @Slot(str, str, result=str)
    @Slot(str, str, str, result=str)
    @Slot(str, str, str, int, result=str)
    def unidadIngreso(self, unidad_json: str, nombre: str, clase: str = "", _version=0) -> str:
        """Unidad en la que se teclea el parámetro ('' = la original del JSON)."""
        clase = u.clase_de_unidad(unidad_json, nombre, clase)
        if clase in ("temp", "dtemp"):
            return self._temperatura
        if clase == "pres":
            return "psig" if self._presion == "psi" else self._presion
        if clase == "dpres":
            return self._presion
        return ""

    @Slot("QVariant", str, str, result="QVariant")
    @Slot("QVariant", str, str, str, result="QVariant")
    def aMostrar(self, valor, unidad_json: str, nombre: str, clase: str = ""):
        """Número (sin formato) en la unidad de presentación; None si no se puede."""
        clase = u.clase_de_unidad(unidad_json, nombre, clase)
        v = _num(valor)
        if v is None or clase is None:
            return v
        if clase == "temp":
            return u.temp_a_mostrar(v, self._temperatura)
        if clase == "dtemp":
            return u.dtemp_a_mostrar(v, self._temperatura)
        if clase == "pres":
            return u.pres_a_mostrar(v, self._presion, self._p_atm)[0]
        return u.dpres_a_mostrar(v, self._presion)[0]

    @Slot(str, str, "QVariant", "QVariant", result="QVariantList")
    @Slot(str, str, "QVariant", "QVariant", str, result="QVariantList")
    def ingresosPsi(self, unidad_json: str, nombre: str, minimo=None, maximo=None, clase: str = ""):
        """psig y/o inHg para teclear un parámetro absoluto en psi (U1-2)."""
        if self._presion != "psi" or u.clase_de_unidad(unidad_json, nombre, clase) != "pres":
            return []
        return u.unidades_de_ingreso_psi(_num(minimo), _num(maximo), self._p_atm)

    @Slot(str, result=str)
    def simboloIngreso(self, unidad: str) -> str:
        return u.SIMBOLOS.get(unidad, unidad)

    @Slot("QVariant", str, str, str, result="QVariant")
    @Slot("QVariant", str, str, str, str, result="QVariant")
    def aMostrarEn(self, valor, unidad_json: str, nombre: str, unidad_ingreso: str,
                   clase: str = ""):
        """Número en la unidad de ingreso (psig o inHg aunque el valor esté del
        otro lado de la atmosférica: entonces 0, el teclado lo corrige)."""
        v = _num(valor)
        clase_hoja = clase
        clase = u.clase_de_unidad(unidad_json, nombre, clase_hoja)
        if v is None or clase != "pres" or unidad_ingreso not in ("psig", "inHg"):
            return self.aMostrar(valor, unidad_json, nombre, clase_hoja)
        if self._p_atm is None:
            return None
        if unidad_ingreso == "psig":
            return max(0.0, (v - self._p_atm) / u.KPA_POR_PSI)
        return max(0.0, (self._p_atm - v) / u.KPA_POR_INHG)

    @Slot("QVariant", str, str, str, result="QVariant")
    @Slot("QVariant", str, str, str, str, result="QVariant")
    def aInterna(self, valor, unidad_json: str, nombre: str, unidad_ingreso: str = "",
                 clase: str = ""):
        """Valor tecleado en `unidad_ingreso` (la fijada al abrir la ventana:
        'C'/'F', 'kPa'/'bar'/'mbar', 'psig'/'inHg'/'psi') → unidad interna
        (°C / kPa abs). Revisión U1 (SAF-02): no se usa la unidad vigente, que
        pudo cambiar con la ventana abierta. None si no se puede convertir."""
        clase_hoja = clase
        clase = u.clase_de_unidad(unidad_json, nombre, clase_hoja)
        v = _num(valor)
        if v is None or clase is None:
            return v
        unidad = unidad_ingreso or self.unidadIngreso(unidad_json, nombre, clase_hoja)
        try:
            if clase == "temp":
                if unidad not in u.TEMPERATURAS:
                    return None
                return u.temp_a_interna(v, unidad)
            if clase == "dtemp":
                if unidad not in u.TEMPERATURAS:
                    return None
                return u.dtemp_a_interna(v, unidad)
            if clase == "pres":
                return u.pres_a_interna(v, unidad, self._p_atm)
            return u.dpres_a_interna(v, unidad)
        except ValueError:
            return None


# Una sola instancia para todos los motores del proceso. El sondeo arranca la
# primera vez que un motor QML la pide (no al importar el módulo).
instancia = UnidadesQml(sondear=False)


def _fabrica(_motor):
    QQmlEngine.setObjectOwnership(instancia, QQmlEngine.ObjectOwnership.CppOwnership)
    if not instancia._timer.isActive():
        instancia._timer.start()
        instancia.refrescar()
    return instancia


qmlRegisterSingletonType(UnidadesQml, URI, 1, 0, "Unidades", _fabrica)
