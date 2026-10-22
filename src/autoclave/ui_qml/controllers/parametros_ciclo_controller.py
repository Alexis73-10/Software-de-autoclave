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
    # D8-5.7 (tanda 8): carga líquida
    "MODO_NO_PERMITIDO_LIQUIDO": "opciones.err_modo_liquido",
    "COHERENCIA_LIQUIDO": "opciones.err_coherencia_liquido",
    # O1 (tanda 5): gestión de programas
    "programa_activo": "opciones.err_programa_activo",
    "programa_deshabilitado": "opciones.err_programa_deshabilitado",
    "programa_existente": "opciones.err_generico",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class ParametrosCicloController(QObject):
    programasChanged = Signal()
    programaChanged = Signal()
    parametrosChanged = Signal()
    sensoresChanged = Signal()
    entradasChanged = Signal()
    mensajeChanged = Signal()
    avisoChanged = Signal()

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
        self._entradas: list = []
        self._entradas_habilitadas: list = []
        self._entradas_editable = False
        self._mensaje = ""
        self._detalle: dict = {}
        # D8-5.7: aviso informativo de un cambio automático (clave + datos)
        self._aviso = ""
        self._detalle_aviso: dict = {}

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

    # ── gestión de programas (O1, tanda 5) ───────────────────────────

    @Property(bool, notify=programaChanged)
    def programaHabilitado(self) -> bool:
        return self._programa().get("habilitado", True) is not False

    @Property(bool, notify=programaChanged)
    def programaPersonalizado(self) -> bool:
        return self._programa().get("personalizado") is True

    def _tras_gestion(self, r, numero_nuevo: int | None = None) -> bool:
        # sin respuesta el resultado es incierto: se relee la lista siempre
        self.cargar()
        if r.ok:
            self._fijar_mensaje("")
            if numero_nuevo:
                self.elegirPrograma(numero_nuevo)
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    @Slot(bool, result=bool)
    def fijarHabilitado(self, habilitado: bool) -> bool:
        r = self._s().enviar("PUT", f"/programas/{self._numero}/habilitado",
                             {"habilitado": bool(habilitado)})
        return self._tras_gestion(r)

    @Slot(str, result=bool)
    def duplicar(self, nombre: str) -> bool:
        r = self._s().enviar("POST", f"/programas/{self._numero}/duplicar", {"nombre": nombre})
        nuevo = r.datos.get("numero") if r.ok and isinstance(r.datos, dict) else None
        return self._tras_gestion(r, nuevo)

    @Slot(result=bool)
    def borrar(self) -> bool:
        r = self._s().enviar("DELETE", f"/programas/{self._numero}")
        if r.ok:
            self._numero = 0          # cargar() elige el primero
        return self._tras_gestion(r)

    # ── entradas mostradas (O1) ──────────────────────────────────────

    @Slot()
    def cargarEntradas(self) -> None:
        r = self._s().enviar("GET", f"/cycle/display-inputs?programa={self._numero}")
        if r.ok and isinstance(r.datos, dict):
            self._entradas = list(r.datos.get("entradas") or [])
            self._entradas_habilitadas = list(r.datos.get("habilitadas") or [])
            self._entradas_editable = bool(r.datos.get("editable"))
        else:
            self._entradas, self._entradas_habilitadas, self._entradas_editable = [], [], False
            self._fijar_mensaje(mensaje_de(r.causa))
        self.entradasChanged.emit()

    @Property("QVariantList", notify=entradasChanged)
    def entradas(self) -> list:
        return self._entradas

    @Property("QVariantList", notify=entradasChanged)
    def entradasHabilitadas(self) -> list:
        return self._entradas_habilitadas

    @Property(bool, notify=entradasChanged)
    def entradasEditable(self) -> bool:
        return self._entradas_editable

    @Slot("QVariantList", result=bool)
    def guardarEntradas(self, entradas) -> bool:
        lista = [str(e) for e in entradas]
        if not 1 <= len(lista) <= 3:
            self._fijar_mensaje("opciones.err_entradas_cantidad")
            return False
        r = self._s().enviar("PUT", "/cycle/display-inputs",
                             {"programa": self._numero, "entradas": lista})
        self.cargarEntradas()
        if r.ok:
            self._fijar_mensaje("")
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

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
        self._fijar_aviso("")
        # SAF-05 (revisión D8-5.7): el modo antes del cambio de tipo de carga,
        # para avisar del cambio automático aunque la respuesta no llegue
        modo_antes = self._modo_descompresion() if self._es_tipo_carga(p) else None
        r = self._s().enviar("PATCH", "/cycle/parameter", cuerpo)
        if r.ok:
            self._fijar_mensaje("")
            self._avisar_arrastres(r.datos.get("arrastres"), valor)
            self.abrirSeccion(self._seccion)
            self.cargar()            # "No se ejecuta" puede cambiar
            return True
        # Sin respuesta: resultado incierto; se recarga y se informa lo real (§5.4)
        self.abrirSeccion(self._seccion)
        if r.causa == sesion_backend.BACKEND_NO_RESPONDE:
            ahora = next((x for x in self._parametros if x["clave"] == clave), None)
            if ahora is not None and ahora.get("valor") == valor:
                self._fijar_mensaje("")
                modo_despues = self._modo_descompresion() if modo_antes is not None else None
                if modo_despues is not None and modo_despues != modo_antes:
                    self._avisar_arrastres([{"fase": "descompresion", "clave": "modo",
                                             "anterior": modo_antes, "nuevo": modo_despues}], valor)
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

    # ── aviso de cambios automáticos (D8-5.7) ────────────────────────

    def _fijar_aviso(self, clave: str, detalle: dict | None = None) -> None:
        if clave != self._aviso or dict(detalle or {}) != self._detalle_aviso:
            self._aviso = clave
            self._detalle_aviso = dict(detalle or {})
            self.avisoChanged.emit()

    def _es_tipo_carga(self, p: dict) -> bool:
        return self._seccion == "globals" and list(p.get("path") or []) == ["tipo_carga"]

    def _modo_descompresion(self):
        """Modo de descompresión vigente del programa (int) o None."""
        r = self._s().enviar("GET", f"/programas/{self._numero}/seccion/descompresion")
        if not r.ok or not isinstance(r.datos, dict):
            return None
        for x in r.datos.get("parametros") or []:
            if isinstance(x, dict) and x.get("clave") == "modo":
                v = x.get("valor")
                return v if isinstance(v, int) and not isinstance(v, bool) else None
        return None

    def _avisar_arrastres(self, arrastres, valor) -> None:
        """El backend cambió solo el modo de descompresión al cambiar el tipo
        de carga: la pantalla lo avisa con un texto del catálogo."""
        if not isinstance(arrastres, list):
            return
        for a in arrastres:
            if (isinstance(a, dict) and a.get("fase") == "descompresion"
                    and a.get("clave") == "modo" and isinstance(a.get("nuevo"), int)):
                clave = ("opciones.aviso_modo_liquido" if valor == "liquido"
                         else "opciones.aviso_modo_solido")
                self._fijar_aviso(clave, {"modo": a["nuevo"], "anterior": a.get("anterior")})
                return

    @Property(str, notify=avisoChanged)
    def aviso(self) -> str:
        return self._aviso

    @Property("QVariantMap", notify=avisoChanged)
    def detalleAviso(self) -> dict:
        return self._detalle_aviso

    @Slot()
    def limpiarAviso(self) -> None:
        self._fijar_aviso("")


qmlRegisterType(ParametrosCicloController, "Autoclave.Controllers", 1, 0,
                "ParametrosCicloController")
