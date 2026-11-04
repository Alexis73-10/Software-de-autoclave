# ui_pyside/views/nuevo_usuario/puente.py
#
# Puente entre la pantalla QML Nuevo Usuario y el backend
# (planeacion_backend_autenticacion.md, decisión 26, T-20; T-8). Crea el
# usuario con POST /usuarios a través de la sesión de la ventana
# (ui_qml/sesion_backend.py), que pone el token, rechaza sin red cuando no hay
# conexión y, ante un 401, cierra la sesión y avisa a la ventana.
#
# Desde T-8 vive en el proceso QML (OPCIONES › Usuarios). Los errores van por
# clave de es.json: {campo: {"clave": "seccion.clave", "valores": {...}}}, y
# "general" para los que no son de un campo; la pantalla los traduce.
#
# Control de acceso (NU-05): la pantalla solo se abre con una sesión que pueda
# crear usuarios, pero quien decide es el backend con el rol del token.
# La contraseña nunca se registra en el log ni se guarda en el objeto.
#
# FASE 6 (AJUSTES 2026-11-02): el alta va asíncrona y sin optimismo
# (OperacionCritica, clave "alta_usuario", 10 s). Sin respuesta se relee GET
# /usuarios: existe con ese rol y estado -> confirmada; si no -> sin confirmar.
# Nunca se reintenta sola.
# MENOR-4 (corrección tras revisión, 04-nov): antes de enviar se toma la lista
# de usuarios (GET /usuarios, plazo PLAZO_PREVIA_S); la relectura solo
# confirma si el usuario (nombre, rol y estado) NO estaba en esa lista previa.
# Sin lista previa (falló o no llegó) la relectura no confirma: sin confirmar.
# H1-H3 (3.er ciclo de corrección, 04-nov): cada alta lleva su contexto
# (usuario, rol, activo, creador, nombre y número de alta `alta`) en la
# OperacionCritica; el desenlace y la conciliación usan ESE contexto, nunca el
# del alta más reciente. Una confirmación tardía de un alta que ya no es la
# actual (hay otra en su lectura previa o vigente, o se envió otra después)
# solo va al log y a la relectura: ni `usuarioCreado` ni `guardadoResuelto`.
# Un fallo al pedir la lista previa devuelve rechazo local sin dejar el alta
# en curso; si la pantalla se abandona durante la lectura previa
# (`abandonarPreparacion`) el POST ya no sale.

import logging

import shiboken6
from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.auth.roles import ROLES, ROLES_CREABLES, etiqueta_rol
from autoclave.cliente.session_manager import SessionManager
from autoclave.auth.validacion_usuario import (
    NOMBRE_MAX, PASSWORD_MAX, PASSWORD_MIN, USUARIO_MAX, campo_pantalla,
    codigos_nuevo_usuario, error_ui,
)
from autoclave.ui_qml.cambio_optimista import SIN_LECTURA
from autoclave.ui_qml.operacion_critica import (
    CONFIRMADA, RECHAZADA, SIN_CONFIRMAR, OperacionCritica)

logger = logging.getLogger(__name__)

CLAVE_ALTA = "alta_usuario"
PLAZO_ALTA_S = 10.0
PLAZO_PREVIA_S = 5.0          # MENOR-4: lectura de la lista antes de enviar


def _general(clave: str) -> dict:
    return {"general": {"clave": clave, "valores": {}}}


class NuevoUsuarioBridge(QObject):
    usuarioCreado = Signal(str)
    solicitudNavegar = Signal(str)
    sesionChanged = Signal()
    # FASE 6: desenlace del alta (estado de OperacionCritica, errores por clave,
    # clave i18n del desenlace y número del alta al que corresponde, H1)
    guardadoResuelto = Signal(str, "QVariantMap", str, int)
    operacionResuelta = Signal(str, str, str)   # clave, estado, clave i18n
    operacionEnCursoChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        if sesion is None:
            from autoclave.ui_qml import sesion_backend
            sesion = sesion_backend.ventana()
        self._sesion = sesion
        self._usuario_actual = ""
        self._rol_actual = ""
        self._n_alta = 0                     # H1: número del último alta enviado
        self._preparando = False             # MENOR-4: leyendo la lista previa
        self._op = OperacionCritica(self, lambda: self._sesion)
        self._op.operacionResuelta.connect(self._al_resolver)
        self._op.operacionResuelta.connect(self.operacionResuelta)
        self._op.operacionEnCursoChanged.connect(self.operacionEnCursoChanged)
        self.actualizarSesion()

    # ── Propiedades ──────────────────────────────────────────────────

    @Property("QVariantList", notify=sesionChanged)
    def roles(self):
        """Solo los roles que la sesión actual puede crear."""
        creables = ROLES_CREABLES.get(self._rol_actual, frozenset())
        # I4 (tanda 6): etiqueta de catálogo roles.<valor> en el idioma vigente
        return [{"valor": v, "etiqueta": etiqueta_rol(v, e)} for v, e in ROLES if v in creables]

    @Property(int, constant=True)
    def minLongitudPassword(self) -> int:
        return PASSWORD_MIN

    @Property("QVariantMap", constant=True)
    def longitudesMaximas(self):
        """Límite del teclado por campo, igual a las reglas de validación."""
        return {"nombre": NOMBRE_MAX, "usuario": USUARIO_MAX,
                "password": PASSWORD_MAX, "confirmacion": PASSWORD_MAX}

    @Property(str, notify=sesionChanged)
    def usuarioActual(self) -> str:
        return self._usuario_actual

    @Slot()
    def actualizarSesion(self) -> None:
        user = SessionManager.current_user()
        usuario = user["usuario"] if user else ""
        rol = user["rol"] if user else ""
        if (usuario, rol) != (self._usuario_actual, self._rol_actual):
            self._usuario_actual = usuario
            self._rol_actual = rol
            self.sesionChanged.emit()

    # ── Reglas ───────────────────────────────────────────────────────

    @Slot(result=bool)
    def puedeCrear(self) -> bool:
        return (SessionManager.is_authenticated()
                and SessionManager.current_role() in ROLES_CREABLES)

    @staticmethod
    def _errores_ui(codigos: dict) -> dict:
        return {campo_pantalla(c): error_ui(c, cod) for c, cod in codigos.items()}

    @Slot(str, str, str, str, str, result="QVariantMap")
    def validar(self, nombre, usuario, password, confirmacion, rol):
        """Validación local de formato para avisar sin ir al backend; la
        unicidad del usuario la decide el backend (409)."""
        return self._errores_ui(codigos_nuevo_usuario(
            nombre, usuario, password, confirmacion, rol, existe_usuario=lambda _u: False))

    @Slot(str, str, str, str, str, bool, result="QVariantMap")
    def guardar(self, nombre, usuario, password, confirmacion, rol, activo):
        """{"enviado": bool, "errores": {...}}. enviado=False: rechazo local
        (permiso, validación, alta ya en curso) con sus errores; True: el
        resultado llega por `guardadoResuelto(estado, errores)`. Nunca se
        reintenta solo (POST /usuarios no es idempotente)."""
        if not self.puedeCrear():
            logger.warning("Creación de usuario rechazada: la sesión no puede crear usuarios")
            return {"enviado": False, "errores": _general("usuarios.sin_permiso")}

        errores = self.validar(nombre, usuario, password, confirmacion, rol)
        if errores:
            return {"enviado": False, "errores": errores}
        if self._op.en_curso(CLAVE_ALTA) or self._preparando:
            return {"enviado": False, "errores": {}}     # doble toque: no hay segundo envío

        cuerpo = {"nombre": nombre.strip(), "usuario": usuario, "clave": password,
                  "confirmacion": confirmacion, "rol": rol, "activo": bool(activo)}
        creador = SessionManager.current_user()["usuario"]
        self._n_alta += 1
        # H1: contexto de ESTA alta; viaja con su operación (contexto_resuelta)
        ctx = {"alta": self._n_alta, "usuario": usuario, "rol": rol, "activo": bool(activo),
               "creador": creador, "nombre": nombre.strip(), "errores_rechazo": None}
        self._preparando = True
        self.operacionEnCursoChanged.emit()
        from autoclave.ui_qml import sesion_backend

        def previa(r) -> None:
            # H3: abandonada (pantalla cerrada) o sustituida por otra alta: no se envía
            if (not self._preparando or ctx["alta"] != self._n_alta
                    or not shiboken6.isValid(self)):
                logger.info("Alta de usuario %s: lectura previa sin envío (abandonada)",
                            ctx["usuario"])
                return
            lista = r.datos.get("usuarios") if r.ok and isinstance(r.datos, dict) else None
            previos = ({u.get("usuario") for u in lista if isinstance(u, dict)}
                       if isinstance(lista, list) else None)
            if previos is None:
                logger.warning("Alta de usuario: sin la lista previa; la relectura no confirmará")
            self._preparando = False
            # el cuerpo (con la contraseña) solo vive en este cierre hasta el envío
            if not self._op.iniciar(CLAVE_ALTA, "POST", "/usuarios", cuerpo,
                                    plazo_s=PLAZO_ALTA_S,
                                    al_rechazo=lambda resp: self._al_rechazo(resp, ctx),
                                    releer=self._releer_usuarios,
                                    conciliar=lambda leido: self._conciliar(leido, previos, ctx),
                                    bloquea_navegacion=True, contexto=ctx):
                self.operacionEnCursoChanged.emit()
        try:
            sesion_backend.enviar_async(self._sesion, "GET", "/usuarios", None, previa,
                                        dueno=self, plazo_s=PLAZO_PREVIA_S)
        except Exception:
            # H2: la lectura previa no pudo pedirse (sesión ausente, etc.)
            logger.exception("Alta de usuario: no se pudo pedir la lista previa")
            if self._preparando and ctx["alta"] == self._n_alta:
                self._preparando = False
                self.operacionEnCursoChanged.emit()
                return {"enviado": False, "errores": _general("usuarios.guardado_error")}
        return {"enviado": True, "errores": {}}

    @Slot()
    def abandonarPreparacion(self) -> None:
        """H3: la pantalla se cierra durante la lectura previa: el POST no
        saldrá (la respuesta de la lectura se ignora). Un alta ya enviada no
        se toca: su desenlace sigue su curso."""
        if self._preparando:
            logger.info("Alta de usuario abandonada antes de enviar (pantalla cerrada)")
            self._preparando = False
            self.operacionEnCursoChanged.emit()

    @Property(int, notify=operacionEnCursoChanged)
    def altaActual(self) -> int:
        """H1: número del último alta enviado (el de `guardadoResuelto`)."""
        return self._n_alta

    def _al_rechazo(self, r, ctx) -> str:
        ctx["errores_rechazo"] = self._errores_de(r)
        general = ctx["errores_rechazo"].get("general")
        return general["clave"] if general else "usuarios.guardado_error"

    def _releer_usuarios(self, al_leido) -> None:
        from autoclave.ui_qml import sesion_backend

        def leido(r):
            lista = r.datos.get("usuarios") if r.ok and isinstance(r.datos, dict) else None
            al_leido(lista if isinstance(lista, list) else SIN_LECTURA)
        sesion_backend.enviar_async(self._sesion, "GET", "/usuarios", None, leido, dueno=self)

    def _conciliar(self, usuarios: list, previos, ctx):
        """MENOR-4: CONFIRMADA solo si el usuario NO estaba en la lista previa
        y ahora está con el nombre, el rol y el estado pedidos. H1: `ctx` es
        el contexto de la operación que se concilia (no el del alta más
        reciente); OperacionCritica llama a conciliar fuera de `_con_id`, así
        que llega por el cierre de iniciar, que es el mismo objeto que
        `contexto`."""
        if not isinstance(ctx, dict):
            return SIN_CONFIRMAR
        usuario, rol, activo, nombre = ctx["usuario"], ctx["rol"], ctx["activo"], ctx["nombre"]
        if previos is None or usuario in previos:
            return SIN_CONFIRMAR             # sin lista previa, o ya existía: no prueba nada
        for u in usuarios:
            if isinstance(u, dict) and u.get("usuario") == usuario:
                if (u.get("rol") == rol and bool(u.get("activo")) == activo
                        and str(u.get("nombre") or "").strip() == nombre):
                    return CONFIRMADA
                return SIN_CONFIRMAR         # existe, pero no como se pidió
        return SIN_CONFIRMAR                 # no está: no se sabe si llegó (no se reintenta)

    def _al_resolver(self, clave: str, estado: str, mensaje: str) -> None:
        if clave != CLAVE_ALTA:
            return
        # H1: el contexto de la operación que se resuelve, nunca el del alta
        # más reciente
        ctx = self._op.contexto_resuelta
        if not isinstance(ctx, dict):
            logger.error("Alta de usuario: desenlace %s sin contexto; no se informa", estado)
            return
        usuario, rol, creador = ctx["usuario"], ctx["rol"], ctx["creador"]
        if not self._es_actual(ctx):
            # alta anterior (otra en lectura previa, vigente o enviada después):
            # solo log; OperacionCritica relee la lista. Ni éxito ni navegación.
            if estado == CONFIRMADA:
                logger.warning("usuario creado (confirmación tardía de un alta anterior, "
                               "n.º %s): %s, rol %s, por %s; no se avisa a la pantalla",
                               ctx["alta"], usuario, rol, creador)
            else:
                logger.warning("Alta de usuario anterior (n.º %s, %s): %s; no se avisa",
                               ctx["alta"], usuario, estado)
            return
        if estado == CONFIRMADA:
            logger.info("usuario creado: %s, rol %s, por %s", usuario, rol, creador)
            self.usuarioCreado.emit(usuario)
            errores = {}
        elif estado == RECHAZADA and ctx.get("errores_rechazo") is not None:
            errores = ctx["errores_rechazo"]
        else:
            if estado == RECHAZADA:
                logger.warning("Creación de usuario rechazada: %s", mensaje)
            else:
                logger.warning("Creación de usuario sin confirmar: %s", usuario)
            errores = _general(mensaje or "usuarios.guardado_error")
        ctx["errores_rechazo"] = None
        self.guardadoResuelto.emit(estado, errores, mensaje or "", ctx["alta"])

    def _es_actual(self, ctx) -> bool:
        """H1: el alta de `ctx` es la última enviada, no hay otra en su lectura
        previa y no hay otra operación de alta vigente."""
        vigente = self._op.id_de(CLAVE_ALTA)
        return (ctx.get("alta") == self._n_alta and not self._preparando
                and vigente in (0, self._op.id_resuelta))

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        return self._preparando or self._op.en_curso()

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        if clave == CLAVE_ALTA and self._preparando:
            return "enviando"
        return self._op.estado(clave)

    def _errores_de(self, r) -> dict:
        from autoclave.ui_qml.sesion_backend import clave_mensaje
        if r.causa == "validacion":
            # contrato v7: lista {campo, codigo} con los campos del cuerpo
            return self._errores_ui({e.get("campo", ""): e.get("codigo", "")
                                     for e in r.datos.get("errores", []) if isinstance(e, dict)})
        if r.causa == "usuario_existe":
            return {"usuario": {"clave": "usuarios.usuario_existe", "valores": {}}}
        if r.causa in ("ok", "error_generico"):
            return _general("usuarios.guardado_error")
        logger.warning("Creación de usuario rechazada: %s", r.causa)
        return _general(clave_mensaje(r.causa))

    # ── Navegación ───────────────────────────────────────────────────

    @Slot(str)
    def navegar(self, destino: str) -> None:
        self.solicitudNavegar.emit(destino)

