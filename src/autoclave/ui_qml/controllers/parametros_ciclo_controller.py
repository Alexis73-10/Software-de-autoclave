# ui_qml/controllers/parametros_ciclo_controller.py
#
# OPCIONES › Parámetros del ciclo, Fases 2 a 4 (planeacion_opciones_parametros_ciclo.md
# rev. 3.1 §4.2, §5.1 a §5.5; tanda 2026-10-14 T12):
#   - programas y secciones (GET /programas), parámetros de una sección con
#     valor por defecto, rango efectivo y última modificación
#     (GET /programas/{n}/seccion/{s});
#   - edición de un parámetro (PATCH /cycle/parameter) con
#     valor_anterior_esperado (RB-06) y el token de la ventana;
#   - roles de los sensores de temperatura (GET /cycle/sensors,
#     PUT /cycle/sensor-roles, todo o nada con asignacion_anterior_esperada).
#
# No calcula reglas de seguridad: el backend valida siempre (§4.2). Las
# peticiones son síncronas con plazo total (SesionVentana.enviar), como el
# puente de Nuevo usuario. Un resultado sin respuesta es INCIERTO: se recarga
# el valor antes de informar (§5.4, D-15).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

# Código del backend -> clave de es.json (opciones §5.4)
_MENSAJES = {
    "estado_no_permitido": "opciones.err_bloqueada",
    "VALOR_CAMBIO": "opciones.err_valor_cambio",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "VALOR_INVALIDO": "opciones.err_valor_invalido",
    "PROGRAMA_NO_EDITABLE": "opciones.err_no_editable",
    "programa_de_fabrica": "opciones.err_no_editable",
    "BASE_OCUPADA": "opciones.err_base_ocupada",
    "f0_no_disponible": "opciones.err_f0",
    "ASIGNACION_INVALIDA": "opciones.err_asignacion",
    "SENSOR_NO_DISPONIBLE": "opciones.err_sensor",
    "asignacion_desfasada": "opciones.err_valor_cambio",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class ParametrosCicloController(QObject):
    programasChanged = Signal()
    programaChanged = Signal()
    parametrosChanged = Signal()
    sensoresChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._programas: list = []
        self._numero = 0
        self._seccion = ""
        self._parametros: list = []
        self._editable_seccion = False
        self._sensores: list = []
        self._asignacion: dict = {}
        self._sensores_editable = False
        self._mensaje = ""
        self._detalle: dict = {}

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str, detalle: dict | None = None) -> None:
        self._mensaje = clave
        self._detalle = dict(detalle or {})
        self.mensajeChanged.emit()

    # ── programas ────────────────────────────────────────────────────

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/programas")
        if not r.ok:
            self._fijar_mensaje(mensaje_de(r.causa))
            return
        self._programas = list(r.datos.get("programas") or [])
        self.programasChanged.emit()
        if self._programas and not any(p["numero"] == self._numero for p in self._programas):
            self.elegirPrograma(self._programas[0]["numero"])
        else:
            self.programaChanged.emit()

    @Property("QVariantList", notify=programasChanged)
    def programas(self) -> list:
        return self._programas

    @Slot(int)
    def elegirPrograma(self, numero: int) -> None:
        if numero != self._numero:
            self._numero = numero
            self._parametros, self._seccion = [], ""
            self.parametrosChanged.emit()
        self.programaChanged.emit()

    def _programa(self) -> dict:
        return next((p for p in self._programas if p["numero"] == self._numero), {})

    @Property(int, notify=programaChanged)
    def numero(self) -> int:
        return self._numero

    @Property(str, notify=programaChanged)
    def nombrePrograma(self) -> str:
        return self._programa().get("nombre", "")

    @Property("QVariantList", notify=programaChanged)
    def secciones(self) -> list:
        return list(self._programa().get("secciones") or [])

    @Property(bool, notify=programaChanged)
    def programaEditable(self) -> bool:
        return bool(self._programa().get("editable"))

    # ── parámetros de una sección ────────────────────────────────────

    @Slot(str)
    def abrirSeccion(self, seccion: str) -> None:
        self._seccion = seccion
        r = self._s().enviar("GET", f"/programas/{self._numero}/seccion/{seccion}")
        if r.ok:
            self._parametros = list(r.datos.get("parametros") or [])
            self._editable_seccion = bool(r.datos.get("editable"))
        else:
            self._parametros, self._editable_seccion = [], False
            self._fijar_mensaje(mensaje_de(r.causa))
        self.parametrosChanged.emit()

    @Property(str, notify=parametrosChanged)
    def seccion(self) -> str:
        return self._seccion

    @Property("QVariantList", notify=parametrosChanged)
    def parametros(self) -> list:
        return self._parametros

    @Property(bool, notify=parametrosChanged)
    def seccionEditable(self) -> bool:
        return self._editable_seccion

    @Slot(str, "QVariant", result=bool)
    def guardar(self, clave: str, valor) -> bool:
        """PATCH del parámetro `clave` de la sección abierta. True si se guardó."""
        p = next((x for x in self._parametros if x["clave"] == clave), None)
        cycle_id = self._programa().get("cycle_id")
        if p is None or not cycle_id:
            return False
        if p.get("tipo") == "int" and isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        cuerpo = {"cycle_id": cycle_id, "fase": self._seccion, "path": p["path"],
                  "value": valor, "valor_anterior_esperado": p["valor"]}
        r = self._s().enviar("PATCH", "/cycle/parameter", cuerpo)
        if r.ok:
            self._fijar_mensaje("")
            self.abrirSeccion(self._seccion)
            self.cargar()            # "No se ejecuta" puede cambiar
            return True
        # Sin respuesta: resultado incierto; se recarga y se informa lo real (§5.4)
        self.abrirSeccion(self._seccion)
        if r.causa == sesion_backend.BACKEND_NO_RESPONDE:
            ahora = next((x for x in self._parametros if x["clave"] == clave), None)
            if ahora is not None and ahora.get("valor") == valor:
                self._fijar_mensaje("")
                return True
        self._fijar_mensaje(mensaje_de(r.causa), {"valor": r.datos.get("valor_actual")})
        return False

    # ── sensores (pantalla 4) ────────────────────────────────────────

    @Slot()
    def cargarSensores(self) -> None:
        r = self._s().enviar("GET", f"/cycle/sensors?programa={self._numero}")
        if r.ok:
            self._sensores = list(r.datos.get("sensores") or [])
            self._asignacion = dict(r.datos.get("asignacion") or {})
            self._sensores_editable = bool(r.datos.get("editable"))
        else:
            self._sensores, self._asignacion, self._sensores_editable = [], {}, False
            self._fijar_mensaje(mensaje_de(r.causa))
        self.sensoresChanged.emit()

    @Property("QVariantList", notify=sensoresChanged)
    def sensores(self) -> list:
        return self._sensores

    @Property("QVariantMap", notify=sensoresChanged)
    def asignacion(self) -> dict:
        return self._asignacion

    @Property(bool, notify=sensoresChanged)
    def sensoresEditable(self) -> bool:
        return self._sensores_editable

    @Slot("QVariantMap", result=bool)
    def guardarSensores(self, asignacion) -> bool:
        cuerpo = {"programa": self._numero, "asignacion": dict(asignacion),
                  "asignacion_anterior_esperada": dict(self._asignacion)}
        r = self._s().enviar("PUT", "/cycle/sensor-roles", cuerpo)
        self.cargarSensores()
        if r.ok:
            self._fijar_mensaje("")
            self.cargar()
            return True
        if r.causa == sesion_backend.BACKEND_NO_RESPONDE and self._asignacion == dict(asignacion):
            self._fijar_mensaje("")
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    # ── mensajes ─────────────────────────────────────────────────────

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def detalleMensaje(self) -> dict:
        return self._detalle

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ParametrosCicloController, "Autoclave.Controllers", 1, 0,
                "ParametrosCicloController")
