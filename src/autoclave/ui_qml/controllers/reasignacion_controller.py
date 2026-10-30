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

# Código del backend -> clave del catálogo (reasignacion.*). Tanda 24 (RSB-04):
# todo lo que pueden emitir /io/assignment, /factory y /verify (los propios de
# la reasignación llegan por sesion_backend.codigos_conocidos); el genérico
# queda solo para lo desconocido (lo vigila tests/test_t24_codigos_reasignacion.py).
_MENSAJES = {
    # validación de la asignación (422)
    "conflicto": "reasignacion.err_conflicto",
    "puerto_inexistente": "reasignacion.err_puerto_inexistente",
    "funcion_desconocida": "reasignacion.err_funcion_desconocida",
    "fabrica_invalida": "reasignacion.err_fabrica_invalida",
    "asignacion_invalida": "reasignacion.err_asignacion_invalida",
    "archivo_ilegible": "reasignacion.err_archivo",
    "archivo_invalido": "reasignacion.err_archivo",
    "puerto_sin_calibracion": "reasignacion.err_puerto_sin_calibracion",
    "sin_cambios": "reasignacion.err_sin_cambios",
    "validacion": "reasignacion.err_validacion",
    # confirmaciones (428/422)
    "confirmacion_requerida": "reasignacion.err_confirmacion_requerida",
    "confirmacion_reforzada": "reasignacion.err_confirmacion_reforzada",
    "nombre_no_coincide": "reasignacion.err_nombre",
    # sesión y reautenticación (401/403/429)
    "reautenticacion_fallida": "reasignacion.err_clave",
    "reautenticacion_requerida": "reasignacion.err_clave_requerida",
    "usuario_bloqueado": "reasignacion.err_bloqueado",
    "rol_sin_permiso": "reasignacion.err_rol",
    "sesion_invalida": "sesion.sesion_invalida",
    "clave_pendiente": "sesion.clave_pendiente",
    # estado del equipo (409; con `motivo` se muestra el motivo, ver _texto_rechazo)
    "estado_no_permitido": "reasignacion.err_estado",
    "configuracion_invalida": "reasignacion.err_configuracion_invalida",
    # guardado y reinicio
    "no_se_pudo_guardar": "reasignacion.err_guardar",
    "reinicio_en_curso": "reasignacion.err_reinicio_en_curso",
    "reinicio_pendiente": "reasignacion.err_reinicio_pendiente",
    # verificación (422/409)
    "no_pendiente": "reasignacion.err_no_pendiente",
    "sin_cambio_observado": "reasignacion.falta_sin_cambio_observado",
    "sin_prueba_de_salida": "reasignacion.falta_sin_prueba_de_salida",
    "sin_lectura": "reasignacion.falta_sin_lectura",
    "error": "reasignacion.falta_error",
    sesion_backend.BACKEND_NO_RESPONDE: "reasignacion.err_sin_respuesta",
}
# Motivos de 409 estado_no_permitido / GET "motivo" (RSB-02: solo estos cuatro)
_MOTIVOS = {"ciclo", "estado", "modo_prueba", "apagando"}
# Lo que falta para verificar (GET verificacion.funciones[].falta)
_FALTAS = {"sin_cambio_observado", "sin_prueba_de_salida", "sin_lectura",
           "puerto_sin_calibracion", "error"}
_ESTADOS_VERIF = {"pendiente", "trama_presente", "sin_respuesta", "verificada"}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "reasignacion.err_generico")


def _texto_rechazo(r) -> str:
    """Clave del catálogo para un rechazo: el motivo concreto de un 409
    estado_no_permitido (ciclo, modo prueba...) o el texto de su código."""
    datos = r.datos if isinstance(getattr(r, "datos", None), dict) else {}
    if r.causa == "estado_no_permitido" and datos.get("motivo") in _MOTIVOS:
        return f"reasignacion.motivo_{datos['motivo']}"
    return mensaje_de(r.causa)


def tipo_visible(fila: dict) -> str:
    """Tanda 24 (RSB-08): tipo que se muestra en Reasignación. «RTD» para las
    funciones del grupo de temperatura y «AI» para las de presión; DI y DO
    sin cambio. Solo presentación: el tipo interno sigue siendo "AI"."""
    return _PREFIJO_TIPO.get(grupo_de(fila), fila.get("tipo", ""))


def lectura_visible(valor, temperatura: bool) -> str:
    """RSB-07: «101.3 kPa» / «25.5 °C»; "" sin lectura válida."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return ""
    return f"{float(valor):.1f} {'°C' if temperatura else 'kPa'}"


# Tanda 23 (AIN-01/02, AIN-R1): grupos de puertos y su prefijo visible.
# RTD 01-06 (temperatura) y AI 01-16 (presión) comparten números: todo se
# compara por grupo, nunca por tipo "AI".
GRUPOS = ("DI", "DO", "AI_TEMP", "AI_PRES")
_PREFIJO = {"DI": "DI", "DO": "DO", "AI_TEMP": "RTD", "AI_PRES": "AI"}
# RSB-08: el tipo visible de cada grupo (el mismo texto que el prefijo)
_PREFIJO_TIPO = _PREFIJO


def grupo_de(fila: dict) -> str:
    """Grupo de una fila de /io/assignment ("grupo"; si falta, del tipo y de
    "temperatura")."""
    g = fila.get("grupo")
    if g in GRUPOS:
        return g
    tipo = fila.get("tipo", "")
    if tipo != "AI":
        return tipo
    return "AI_TEMP" if fila.get("temperatura") else "AI_PRES"


def etiqueta(grupo: str, puerto) -> str:
    """"DO 04", "RTD 01", "AI 09", como en Entradas / Salidas (igual que
    asignacion_io.etiqueta_grupo). `grupo` "AI" (sin grupo) se muestra «AI»."""
    try:
        return f"{_PREFIJO.get(grupo, grupo)} {int(puerto):02d}"
    except (TypeError, ValueError):
        return ""


def conflictos(ocupados: dict, filas: list, pendientes: dict) -> list:
    """Conflictos que la UI ya ve: dos funciones en el mismo puerto DEL MISMO
    GRUPO tras aplicar `pendientes` ({funcion: puerto}) sobre la asignación
    guardada (`ocupados` {grupo: {"puerto": funcion}}, incluye las no
    habilitadas). Lista de {funcion, otra, tipo, grupo, puerto}. El backend
    vuelve a validar."""
    grupo_fila = {f["funcion"]: grupo_de(f) for f in filas}
    tipo_de = {f["funcion"]: f["tipo"] for f in filas}
    salida = []
    for grupo in GRUPOS:
        por_puerto: dict[int, list] = {}
        for puerto, funcion in (ocupados.get(grupo) or {}).items():
            if funcion in pendientes:
                continue
            try:
                por_puerto.setdefault(int(puerto), []).append(funcion)
            except (TypeError, ValueError):
                continue
        for funcion, puerto in pendientes.items():
            if grupo_fila.get(funcion) == grupo:
                por_puerto.setdefault(int(puerto), []).append(funcion)
        for puerto, funciones in sorted(por_puerto.items()):
            if len(funciones) > 1:
                movida = next((f for f in funciones if f in pendientes), funciones[0])
                otra = next(f for f in funciones if f != movida)
                salida.append({"funcion": movida, "otra": otra,
                               "tipo": tipo_de.get(movida, grupo if grupo in ("DI", "DO") else "AI"),
                               "grupo": grupo, "puerto": puerto})
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
            self._fijar_mensaje(_texto_rechazo(r))
        self.datosChanged.emit()

    # ── propiedades de la tabla ───────────────────────────────────────
    @Property("QVariantList", notify=datosChanged)
    def filas(self) -> list:
        f = self._d.get("filas")
        if not isinstance(f, list):
            return []
        # RSB-08: "tipo_visible" («RTD» en las temperaturas); "tipo" sigue
        # siendo el interno ("AI") para todo lo que compara
        return [{**x, "tipo_visible": tipo_visible(x)} for x in f if isinstance(x, dict)]

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
    def avisoCamara(self) -> bool:
        """RSB-03: aviso no bloqueante en los diálogos de Aplicar y Restaurar
        fábrica. Sin el campo (backend anterior o respuesta rara), True: falla
        hacia mostrar el aviso."""
        return self._d.get("aviso_camara") is not False

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
        """[{funcion, i18n, tipo, tipoVisible, estado, falta, puerto, pendiente,
        reforzada, lectura}] de las funciones reasignadas en el último arranque.
        estado: pendiente | trama_presente | sin_respuesta | verificada. falta:
        clave del catálogo con lo que falta para que el ingeniero la pueda
        verificar ("" = nada). lectura (RSB-07): la lectura actual de una
        analógica («101.3 kPa»), "" sin lectura válida."""
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
                           "tipoVisible": tipo_visible(fila) if fila else "",
                           "lectura": lectura_visible(dato.get("lectura"), bool(fila.get("temperatura"))),
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
        puertos = self._d.get("puertos") or {}
        # Tanda 23 (AIN-R1): puertos y ocupados del GRUPO de la función
        clave = grupo_de(fila)
        ocupados = dict((self._d.get("ocupados") or {}).get(clave) or {})
        # los pendientes también ocupan (y liberan su puerto guardado)
        for f, p in self._pendientes.items():
            otra = self._fila(f)
            if not otra or grupo_de(otra) != clave:
                continue
            ocupados = {k: v for k, v in ocupados.items() if v != f}
            ocupados[str(p)] = f
        i18n_de = {f["funcion"]: f["i18n"] for f in self.filas}
        elegido = self._pendientes.get(funcion, fila.get("puerto_guardado"))
        salida = []
        for p in puertos.get(clave) or []:
            otra = ocupados.get(str(p), "")
            otra = "" if otra == funcion else otra
            salida.append({"puerto": int(p), "etiqueta": etiqueta(clave, p),
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
        grupo_fila = {f["funcion"]: grupo_de(f) for f in self.filas}
        return {f: etiqueta(grupo_fila.get(f, ""), p) for f, p in self._pendientes.items()}

    @Property(int, notify=pendientesChanged)
    def cantidadCambios(self) -> int:
        return len(self._pendientes)

    @Property("QVariantList", notify=pendientesChanged)
    def conflictos(self) -> list:
        lista = conflictos((self._d.get("ocupados") or {}), self.filas, self._pendientes)
        i18n_de = {f["funcion"]: f["i18n"] for f in self.filas}
        return [{**c, "i18n": i18n_de.get(c["funcion"], ""),
                 "i18nOtra": i18n_de.get(c["otra"], f"reasignacion.funcion_{c['otra']}"),
                 "etiqueta": etiqueta(c["grupo"], c["puerto"])} for c in lista]

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
        self._fijar_mensaje(_texto_rechazo(r))
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
        exige la evidencia (cambio observado, prueba de salida o, en una
        analógica, lectura válida en el puerto nuevo: RSB-07)."""
        r = self._s().enviar("POST", "/io/assignment/verify",
                             {"funcion": funcion, "clave": clave, "nombre": nombre})
        if r.ok:
            self._fijar_mensaje("reasignacion.verificada_ok")
            self.cargar()
            return True
        self._fijar_mensaje(_texto_rechazo(r))
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
