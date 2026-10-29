# ui_qml/controllers/reasignacion_controller.py
#
# OPCIONES > Opciones avanzadas = reasignación de entradas y salidas (R8,
# tanda 8, D8-5.12; planeacion_opciones.md v4 R-03 y OPC-03). Sin mockup
# aprobado: sigue el estilo de Entradas / Salidas.
#
# Tabla función / puerto actual / puerto nuevo / tipo / crítica. Los cambios se
# eligen aquí y se envían juntos; la UI marca los conflictos que ya ve, pero el
# backend es la autoridad (rol, estado, conflictos, puertos inexistentes,
# confirmaciones y reautenticación; 403/409/422/428/429). Aplicar reinicia el
# control (el backend se relanza): la pantalla lo anuncia y vuelve a cargar.

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend

logger = logging.getLogger(__name__)

# Código del backend -> clave del catálogo (reasignacion.*)
_MENSAJES = {
    "conflicto": "reasignacion.err_conflicto",
    "puerto_inexistente": "reasignacion.err_puerto_inexistente",
    "funcion_desconocida": "reasignacion.err_funcion_desconocida",
    "sin_cambios": "reasignacion.err_sin_cambios",
    "reautenticacion_fallida": "reasignacion.err_clave",
    "reautenticacion_requerida": "reasignacion.err_clave_requerida",
    "nombre_no_coincide": "reasignacion.err_nombre",
    "confirmacion_reforzada": "reasignacion.err_nombre",
    "usuario_bloqueado": "reasignacion.err_bloqueado",
    "estado_no_permitido": "reasignacion.err_estado",
    # ESS-07, SAF-01 (29-oct)
    "sensor_camara_no_segura": "reasignacion.err_sensor_camara_no_segura",
    "rol_sin_permiso": "reasignacion.err_rol",
    "no_se_pudo_guardar": "reasignacion.err_guardar",
    "puerto_sin_calibracion": "reasignacion.err_puerto_sin_calibracion",
    "reinicio_en_curso": "reasignacion.err_reinicio_en_curso",
    "no_pendiente": "reasignacion.err_no_pendiente",
    "sin_cambio_observado": "reasignacion.falta_sin_cambio_observado",
    "sin_prueba_de_salida": "reasignacion.falta_sin_prueba_de_salida",
    "sin_lectura": "reasignacion.falta_sin_lectura",
    "calibracion_requerida": "reasignacion.falta_calibracion_requerida",
    sesion_backend.BACKEND_NO_RESPONDE: "reasignacion.err_sin_respuesta",
}
_MOTIVOS = {"ciclo", "estado", "modo_prueba", "apagando", "estado_seguro",
            # ESS-07 (29-oct)
            "estado_seguro_confirmar", "estado_seguro_liquido"}
_FALTAS = {"sin_cambio_observado", "sin_prueba_de_salida", "sin_lectura", "calibracion_requerida"}
_ESTADOS_VERIF = {"pendiente", "trama_presente", "sin_respuesta", "verificada"}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "reasignacion.err_generico")


def etiqueta(tipo: str, puerto) -> str:
    """"DO 04", como en Entradas / Salidas (igual que asignacion_io.etiqueta)."""
    try:
        return f"{tipo} {int(puerto):02d}"
    except (TypeError, ValueError):
        return ""


def conflictos(ocupados: dict, filas: list, pendientes: dict) -> list:
    """Conflictos que la UI ya ve: dos funciones en el mismo puerto tras
    aplicar `pendientes` ({funcion: puerto}) sobre la asignación guardada
    (`ocupados` {tipo: {"puerto": funcion}}, incluye las no habilitadas).
    Lista de {funcion, otra, tipo, puerto}. El backend vuelve a validar."""
    tipo_de = {f["funcion"]: f["tipo"] for f in filas}
    salida = []
    for tipo in ("DI", "DO", "AI"):
        por_puerto: dict[int, list] = {}
        for puerto, funcion in (ocupados.get(tipo) or {}).items():
            if funcion in pendientes:
                continue
            try:
                por_puerto.setdefault(int(puerto), []).append(funcion)
            except (TypeError, ValueError):
                continue
        for funcion, puerto in pendientes.items():
            if tipo_de.get(funcion) == tipo:
                por_puerto.setdefault(int(puerto), []).append(funcion)
        for puerto, funciones in sorted(por_puerto.items()):
            if len(funciones) > 1:
                movida = next((f for f in funciones if f in pendientes), funciones[0])
                otra = next(f for f in funciones if f != movida)
                salida.append({"funcion": movida, "otra": otra, "tipo": tipo, "puerto": puerto})
    return salida


class ReasignacionController(QObject):
    datosChanged = Signal()
    pendientesChanged = Signal()
    mensajeChanged = Signal()
    reiniciandoChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._d: dict = {}
        self._pendientes: dict[str, int] = {}
        self._nombres: dict[str, str] = {}
        self._mensaje = ""
        self._reiniciando = False

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── carga ─────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/io/assignment")
        if r.ok and isinstance(r.datos, dict):
            self._d = r.datos
            if self._reiniciando:
                self._reiniciando = False
                self.reiniciandoChanged.emit()
                self._fijar_mensaje("")
            # un cambio pendiente que ya rige deja de serlo
            guardado = {f["funcion"]: f.get("puerto_guardado") for f in self.filas}
            antes = dict(self._pendientes)
            self._pendientes = {f: p for f, p in self._pendientes.items()
                                if f in guardado and guardado[f] != p}
            if self._pendientes != antes:
                self.pendientesChanged.emit()
        elif not self._reiniciando:
            self._d = {}
            self._fijar_mensaje(mensaje_de(r.causa))
        self.datosChanged.emit()

    # ── propiedades de la tabla ───────────────────────────────────────
    @Property("QVariantList", notify=datosChanged)
    def filas(self) -> list:
        f = self._d.get("filas")
        return [dict(x) for x in f if isinstance(x, dict)] if isinstance(f, list) else []

    @Property(bool, notify=datosChanged)
    def cargado(self) -> bool:
        return bool(self._d)

    @Property(bool, notify=datosChanged)
    def editable(self) -> bool:
        return self._d.get("editable") is True and not self._reiniciando

    @Property(str, notify=datosChanged)
    def motivo(self) -> str:
        """Clave del catálogo con el motivo por el que no se puede editar."""
        m = self._d.get("motivo") or ""
        return f"reasignacion.motivo_{m}" if m in _MOTIVOS else ""

    @Property(bool, notify=datosChanged)
    def reinicioPendiente(self) -> bool:
        return self._d.get("reinicio_pendiente") is True

    @Property(bool, notify=datosChanged)
    def bloqueado(self) -> bool:
        return bool(self._d.get("bloqueo")) or bool(self._d.get("error_archivo"))

    @Property(bool, notify=datosChanged)
    def hayCambiosGuardados(self) -> bool:
        return bool(self._d.get("cambios_guardados"))

    @Property("QVariantList", notify=datosChanged)
    def verificacion(self) -> list:
        """[{funcion, i18n, tipo, estado, falta, puerto, pendiente, reforzada}]
        de las funciones reasignadas en el último arranque. estado: pendiente |
        trama_presente | sin_respuesta | verificada. falta: clave del catálogo
        con lo que falta para que el ingeniero la pueda verificar ("" = nada)."""
        v = self._d.get("verificacion") or {}
        funciones = v.get("funciones") if isinstance(v, dict) else None
        if not isinstance(funciones, dict):
            return []
        pendientes = set(self._d.get("pendientes") or [])
        por_funcion = {f["funcion"]: f for f in self.filas}
        salida = []
        for funcion, dato in sorted(funciones.items()):
            dato = dato if isinstance(dato, dict) else {"estado": dato}
            estado = str(dato.get("estado") or "pendiente")
            falta = str(dato.get("falta") or "")
            fila = por_funcion.get(funcion, {})
            salida.append({"funcion": funcion, "i18n": fila.get("i18n", ""),
                           "tipo": fila.get("tipo", ""),
                           "estado": estado if estado in _ESTADOS_VERIF else "pendiente",
                           "falta": f"reasignacion.falta_{falta}" if falta in _FALTAS else "",
                           "puerto": fila.get("id_actual", ""),
                           "pendiente": funcion in pendientes,
                           "reforzada": bool(fila.get("reforzada"))})
        return salida

    @Property(int, notify=datosChanged)
    def cantidadSinVerificar(self) -> int:
        return len([f for f in (self._d.get("pendientes") or []) if isinstance(f, str)])

    # ── cambios pendientes ────────────────────────────────────────────
    def _fila(self, funcion: str) -> dict:
        return next((f for f in self.filas if f["funcion"] == funcion), {})

    @Slot(str, result="QVariantList")
    def puertosPara(self, funcion: str) -> list:
        """Puertos que admite la función: [{puerto, etiqueta, ocupadoPor,
        actual, fabrica}]. ocupadoPor es la clave i18n de la otra función."""
        fila = self._fila(funcion)
        if not fila:
            return []
        tipo = fila["tipo"]
        puertos = self._d.get("puertos") or {}
        clave = tipo if tipo != "AI" else ("AI_TEMP" if fila.get("temperatura") else "AI_PRES")
        ocupados = dict((self._d.get("ocupados") or {}).get(tipo) or {})
        # los pendientes también ocupan (y liberan su puerto guardado)
        for f, p in self._pendientes.items():
            otra = self._fila(f)
            if otra.get("tipo") != tipo:
                continue
            ocupados = {k: v for k, v in ocupados.items() if v != f}
            ocupados[str(p)] = f
        i18n_de = {f["funcion"]: f["i18n"] for f in self.filas}
        elegido = self._pendientes.get(funcion, fila.get("puerto_guardado"))
        salida = []
        for p in puertos.get(clave) or []:
            otra = ocupados.get(str(p), "")
            otra = "" if otra == funcion else otra
            salida.append({"puerto": int(p), "etiqueta": etiqueta(tipo, p),
                           "ocupadoPor": i18n_de.get(otra, f"reasignacion.funcion_{otra}") if otra else "",
                           "actual": int(p) == elegido,
                           "fabrica": int(p) == fila.get("puerto_fabrica")})
        return salida

    @Slot(str, int)
    def elegirPuerto(self, funcion: str, puerto: int) -> None:
        fila = self._fila(funcion)
        if not fila or not self.editable:
            return
        if puerto == fila.get("puerto_guardado"):
            self._pendientes.pop(funcion, None)
        else:
            self._pendientes[funcion] = int(puerto)
        self._nombres.pop(funcion, None)
        self._fijar_mensaje("")
        self.pendientesChanged.emit()

    @Slot()
    def descartar(self) -> None:
        if self._pendientes or self._nombres:
            self._pendientes, self._nombres = {}, {}
            self.pendientesChanged.emit()

    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """{funcion: etiqueta del puerto nuevo}."""
        tipo_de = {f["funcion"]: f["tipo"] for f in self.filas}
        return {f: etiqueta(tipo_de.get(f, ""), p) for f, p in self._pendientes.items()}

    @Property(int, notify=pendientesChanged)
    def cantidadCambios(self) -> int:
        return len(self._pendientes)

    @Property("QVariantList", notify=pendientesChanged)
    def conflictos(self) -> list:
        lista = conflictos((self._d.get("ocupados") or {}), self.filas, self._pendientes)
        i18n_de = {f["funcion"]: f["i18n"] for f in self.filas}
        return [{**c, "i18n": i18n_de.get(c["funcion"], ""),
                 "i18nOtra": i18n_de.get(c["otra"], f"reasignacion.funcion_{c['otra']}"),
                 "etiqueta": etiqueta(c["tipo"], c["puerto"])} for c in lista]

    @Property("QVariantList", notify=pendientesChanged)
    def criticasPendientes(self) -> list:
        """Claves i18n de las funciones críticas entre los cambios."""
        return [f["i18n"] for f in self.filas if f["funcion"] in self._pendientes and f.get("critica")]

    @Property("QVariantList", notify=pendientesChanged)
    def reforzadasPendientes(self) -> list:
        """[{funcion, i18n}] que exigen escribir el nombre."""
        return [{"funcion": f["funcion"], "i18n": f["i18n"]} for f in self.filas
                if f["funcion"] in self._pendientes and f.get("reforzada")]

    @Property(bool, notify=pendientesChanged)
    def hayAnalogicas(self) -> bool:
        return any(f["tipo"] == "AI" and f["funcion"] in self._pendientes for f in self.filas)

    @Slot(str, str)
    def fijarNombre(self, funcion: str, texto: str) -> None:
        self._nombres[funcion] = texto

    # ── aplicar / restaurar ───────────────────────────────────────────
    def _tras_envio(self, r) -> bool:
        if r.ok:
            datos = r.datos if isinstance(r.datos, dict) else {}
            self._pendientes, self._nombres = {}, {}
            self.pendientesChanged.emit()
            if datos.get("reinicio") is True:
                self._reiniciando = True
                self.reiniciandoChanged.emit()
                self._fijar_mensaje("reasignacion.reiniciando")
            else:
                self._fijar_mensaje("reasignacion.guardado_sin_reinicio")
            self.datosChanged.emit()
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        self._nombres = {}
        self.cargar()
        return False

    @Slot(str, result=bool)
    def aplicar(self, clave: str) -> bool:
        if not self._pendientes:
            self._fijar_mensaje("reasignacion.err_sin_cambios")
            return False
        if self.conflictos:
            self._fijar_mensaje("reasignacion.err_conflicto")
            return False
        r = self._s().enviar("POST", "/io/assignment",
                             {"cambios": dict(self._pendientes), "clave": clave, "confirmar": True,
                              "nombres": dict(self._nombres)})
        return self._tras_envio(r)

    @Slot(str, str, str, result=bool)
    def verificar(self, funcion: str, clave: str, nombre: str) -> bool:
        """El ingeniero da por verificada una función reasignada. El backend
        exige la evidencia (cambio observado, prueba de salida o calibración)."""
        r = self._s().enviar("POST", "/io/assignment/verify",
                             {"funcion": funcion, "clave": clave, "nombre": nombre})
        if r.ok:
            self._fijar_mensaje("reasignacion.verificada_ok")
            self.cargar()
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        self.cargar()
        return False

    @Slot(str, result=bool)
    def restaurarFabrica(self, clave: str) -> bool:
        r = self._s().enviar("POST", "/io/assignment/factory", {"clave": clave, "confirmar": True})
        return self._tras_envio(r)

    @Property(bool, notify=reiniciandoChanged)
    def reiniciando(self) -> bool:
        return self._reiniciando

    @Property(str, constant=True)
    def usuario(self) -> str:
        u = SessionManager.current_user() or {}
        return str(u.get("usuario") or u.get("nombre") or "")

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ReasignacionController, "Autoclave.Controllers", 1, 0, "ReasignacionController")
