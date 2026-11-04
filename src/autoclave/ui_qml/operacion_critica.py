# ui_qml/operacion_critica.py
#
# Operación crítica de Opciones (AJUSTES 2026-11-02, paso 2 FASE 6, P1): una
# orden al backend que NUNCA se da por buena sin un 200 o sin una relectura
# que coincida (sin optimismo). La usan los controladores con
# `sesion_backend.enviar_async`; todo corre en el hilo de la GUI.
#
# Por clave (una operación a la vez, sin cola):
#   iniciar -> ENVIANDO (fijado y notificado ANTES de enviar: los dobles
#   síncronos entregan dentro de la llamada).
#   200 -> al_ok(r) y CONFIRMADA.
#   Rechazo con la misma generación de sesión -> RECHAZADA (mensaje de
#   al_rechazo(r) o el de la causa).
#   La generación de sesión cambió sin 200 -> SIN_CONFIRMAR, sin relectura.
#   backend_no_responde -> VERIFICANDO: releer(al_leido) con plazo
#   PLAZO_RELECTURA_S y conciliar(leído) -> CONFIRMADA | RECHAZADA |
#   SIN_CONFIRMAR; sin lectura, sin releer o sin conciliar -> SIN_CONFIRMAR.
#   Respuesta tardía: tras SIN_CONFIRMAR (o tras una RECHAZADA de la
#   conciliación, m1), un 200 emite CONFIRMADA con
#   "operacion.confirmada_tarde", ejecuta al_ok y relee; cualquier otra solo
#   relee. El dueño NO debe tratar "confirmada_tarde" como la confirmación de
#   un pedido vigente (C1: puede ser de un pedido anterior).
#   MAYOR-1 (corrección tras revisión, 04-nov): cada operación lleva un id
#   único (`ultimo_id` tras iniciar; `id_resuelta` mientras se emite su
#   desenlace) y un `grupo` (por defecto su clave). Si al llegar el 200
#   tardío hay OTRA operación vigente del mismo grupo, no se ejecuta al_ok ni
#   se emite "confirmada_tarde" (se confundiría con la vigente): solo log y
#   relectura. `al_ok_tardio` (por defecto al_ok) es lo que corre con un 200
#   tardío válido, para quien no deba aplicar los datos viejos del 200.
# Tras emitir el estado final (operacionResuelta) la clave vuelve a INACTIVA.
# Además hay un tope total de plazo_s + PLAZO_RELECTURA_S: pasado ese tiempo
# la operación termina SIN_CONFIRMAR (el bloqueo de navegación no dura más).
#
# Registro de proceso `OperacionesCriticas` (singleton QML
# `Autoclave.Operaciones`, propiedad `bloqueaNavegacion`): cada instancia se
# registra al iniciar y se quita al destruirse (`destroyed`) o al `cancelar`.

import itertools
import logging

import shiboken6
from PySide6.QtCore import Property, QObject, QTimer, Signal
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonType

from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.cambio_optimista import SIN_LECTURA

logger = logging.getLogger(__name__)

URI = "Autoclave.Operaciones"

INACTIVA, ENVIANDO, VERIFICANDO = "inactiva", "enviando", "verificando"
CONFIRMADA, RECHAZADA, SIN_CONFIRMAR = "confirmada", "rechazada", "sin_confirmar"
_FINALES = (CONFIRMADA, RECHAZADA, SIN_CONFIRMAR)

PLAZO_RELECTURA_S = 5.0
MSG_CONFIRMADA_TARDE = "operacion.confirmada_tarde"
MSG_SIN_CONFIRMAR = "operacion.sin_confirmar"
# conciliar() devolvió RECHAZADA sin mensaje propio
MSG_NO_COINCIDE = "opciones.err_sin_respuesta"


def _ignorar(*_a) -> None:
    return None


# ── registro de proceso ─────────────────────────────────────────────────────

class OperacionesCriticas(QObject):
    """Une el estado de todas las OperacionCritica vivas del proceso. Guarda
    solo id -> (en curso, bloquea): nunca toca un objeto ya destruido."""
    bloqueaNavegacionChanged = Signal()
    operacionEnCursoChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._estado: dict[int, tuple[bool, bool]] = {}
        self._conectados: set[int] = set()

    @Property(bool, notify=bloqueaNavegacionChanged)
    def bloqueaNavegacion(self) -> bool:
        return any(b for _, b in self._estado.values())

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        return any(e for e, _ in self._estado.values())

    def actualizar(self, oc: "OperacionCritica") -> None:
        ident = id(oc)
        if ident not in self._conectados:
            self._conectados.add(ident)
            oc.destroyed.connect(lambda *_a, i=ident: self.quitar(i))
        self._fijar(ident, (oc.en_curso(), oc.bloquea()))

    def quitar(self, oc_o_id) -> None:
        ident = oc_o_id if isinstance(oc_o_id, int) else id(oc_o_id)
        if isinstance(oc_o_id, int):
            self._conectados.discard(ident)   # destruido: id reutilizable
        self._fijar(ident, None)

    def registradas(self) -> int:
        return len(self._estado)

    def _fijar(self, ident: int, valor) -> None:
        antes_b, antes_e = self.bloqueaNavegacion, self.operacionEnCurso
        if valor is None:
            self._estado.pop(ident, None)
        else:
            self._estado[ident] = valor
        if self.operacionEnCurso != antes_e:
            self.operacionEnCursoChanged.emit()
        if self.bloqueaNavegacion != antes_b:
            self.bloqueaNavegacionChanged.emit()


registro = OperacionesCriticas()


def _fabrica(_motor):
    QQmlEngine.setObjectOwnership(registro, QQmlEngine.ObjectOwnership.CppOwnership)
    return registro


qmlRegisterSingletonType(OperacionesCriticas, URI, 1, 0, "Operaciones", _fabrica)


# ── operación ───────────────────────────────────────────────────────────────

_ids = itertools.count(1)       # MAYOR-1: id único de cada operación del proceso


class _Op:
    __slots__ = ("clave", "ruta", "estado", "gen", "al_ok", "al_rechazo", "releer", "conciliar",
                 "bloquea", "msg_sin_confirmar", "final", "no_salio", "cancelada",
                 "timer_total", "timer_relectura", "tarde_confirmada", "rechazo_conciliado",
                 "ident", "grupo", "al_ok_tardio", "contexto")

    def __init__(self, clave, al_ok, al_rechazo, releer, conciliar, bloquea, msg_sin_confirmar):
        self.ident = next(_ids)
        self.grupo = clave
        self.al_ok_tardio = al_ok
        self.contexto = None
        self.clave = clave
        self.ruta = ""
        self.estado = ENVIANDO
        self.gen = None
        self.al_ok, self.al_rechazo = al_ok, al_rechazo
        self.releer, self.conciliar = releer, conciliar
        self.bloquea = bool(bloquea)
        self.msg_sin_confirmar = msg_sin_confirmar or MSG_SIN_CONFIRMAR
        self.final = None
        self.no_salio = False
        self.cancelada = False
        self.timer_total = None
        self.timer_relectura = None
        self.tarde_confirmada = False
        self.rechazo_conciliado = False


class OperacionCritica(QObject):
    """`sesion_fn()` devuelve la sesión (SesionVentana o un doble); se pide
    en cada envío. `registro`: el de proceso por defecto."""
    operacionResuelta = Signal(str, str, str)   # clave, estado final, clave i18n ("" si ok)
    operacionEnCursoChanged = Signal()

    def __init__(self, parent, sesion_fn, *, registro=None):
        super().__init__(parent)
        self._sesion_fn = sesion_fn
        self._registro = registro if registro is not None else globals()["registro"]
        self._ops: dict[str, _Op] = {}
        self.ultimo_id = 0     # id de la última operación iniciada (MAYOR-1)
        self.id_resuelta = 0   # id de la operación cuyo al_ok o desenlace está corriendo
        self.contexto_resuelta = None   # su `contexto` (el que dio iniciar)

    def id_de(self, clave) -> int:
        """Id de la operación vigente de `clave` (0 si no hay)."""
        op = self._ops.get(clave)
        return 0 if op is None else op.ident

    def contexto_de(self, clave):
        """`contexto` de la operación vigente de `clave` (None si no hay)."""
        op = self._ops.get(clave)
        return None if op is None else op.contexto

    # ── consulta ─────────────────────────────────────────────────────
    def estado(self, clave) -> str:
        op = self._ops.get(clave)
        return INACTIVA if op is None else op.estado

    def en_curso(self, clave=None) -> bool:
        return bool(self._ops) if clave is None else clave in self._ops

    def bloquea(self) -> bool:
        return any(op.bloquea for op in self._ops.values())

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        return self.en_curso()

    @Property(bool, notify=operacionEnCursoChanged)
    def bloqueaNavegacion(self) -> bool:
        return self.bloquea()

    # ── inicio ───────────────────────────────────────────────────────
    def iniciar(self, clave, metodo, ruta, cuerpo=None, *, plazo_s, al_ok=None,
                al_rechazo=None, releer=None, conciliar=None, bloquea_navegacion=False,
                msg_sin_confirmar=MSG_SIN_CONFIRMAR, grupo=None, al_ok_tardio=None,
                contexto=None) -> bool:
        """False sin enviar nada si `clave` ya está en curso. Si no, True: el
        resultado llega siempre por `operacionResuelta` (también si la petición
        no pudo salir, como RECHAZADA con el mensaje de la causa). El id de la
        operación queda en `ultimo_id` antes de enviar. `grupo`: operaciones
        que se excluyen entre sí aunque tengan otra clave (guarda del 200
        tardío, MAYOR-1). `al_ok_tardio`: lo que corre con un 200 tardío válido
        (por defecto `al_ok`). `contexto`: objeto del dueño que vuelve en
        `contexto_resuelta` mientras corren al_ok y el desenlace."""
        if clave in self._ops:
            logger.info("Operación crítica ya en curso, se ignora: %s", clave)
            return False
        op = _Op(clave, al_ok, al_rechazo, releer, conciliar, bloquea_navegacion,
                 msg_sin_confirmar)
        if grupo:
            op.grupo = grupo
        if al_ok_tardio is not None:
            op.al_ok_tardio = al_ok_tardio
        op.contexto = contexto
        self.ultimo_id = op.ident
        op.ruta = ruta
        self._ops[clave] = op
        op.timer_total = self._temporizador(plazo_s + PLAZO_RELECTURA_S,
                                            lambda: self._vencer(op, "plazo_total"))
        self._notificar()
        try:
            sesion = self._sesion_fn()
            op.gen = getattr(sesion, "generacion", None)
            salio = sb.enviar_async(sesion, metodo, ruta, cuerpo,
                                    lambda r: self._al_terminar(op, r), dueno=self,
                                    al_tardio=lambda r: self._al_tardio(op, r),
                                    plazo_s=plazo_s)
        except Exception:
            logger.exception("Operación crítica %s: el envío falló (%s %s)", clave, metodo, ruta)
            if self._vigente(op):
                self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)
            return True
        if salio is False and self._vigente(op):
            op.no_salio = True     # al_terminar llegará en diferido
        return True

    def _temporizador(self, segundos: float, accion) -> QTimer:
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(accion)
        t.start(max(0, int(segundos * 1000)))
        return t

    def _vigente(self, op: _Op) -> bool:
        return not op.cancelada and op.final is None and self._ops.get(op.clave) is op

    def _gen_actual(self):
        try:
            return getattr(self._sesion_fn(), "generacion", None)
        except Exception:
            logger.exception("Operación crítica: no se pudo leer la sesión")
            return object()        # distinta de cualquiera: no se da por rechazo

    # ── respuesta ────────────────────────────────────────────────────
    def _al_terminar(self, op: _Op, r) -> None:
        if not self._vigente(op):
            return
        if getattr(r, "ok", False):
            self._confirmar(op, r, "")
            return
        causa = getattr(r, "causa", sb.ERROR_GENERICO)
        if op.no_salio:
            # no salió a la red (sin conexión, sin token, tope): nada cambió.
            # m3 (revisión FASE 6): también pasa por al_rechazo, para que el
            # dueño vea la causa (p. ej. sesion_invalida = salida hecha)
            self._resolver(op, RECHAZADA, self._mensaje_rechazo(op, r, causa))
        elif op.gen != self._gen_actual():
            logger.warning("Operación crítica %s: la sesión cambió sin 200 (%s)", op.clave, causa)
            self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)
        elif causa == sb.BACKEND_NO_RESPONDE:
            self._verificar(op)
        else:
            self._resolver(op, RECHAZADA, self._mensaje_rechazo(op, r, causa))

    def _mensaje_rechazo(self, op: _Op, r, causa) -> str:
        if op.al_rechazo is not None:
            try:
                msg = op.al_rechazo(r)
                if isinstance(msg, str) and msg:
                    return msg
            except Exception:
                logger.exception("Operación crítica %s: al_rechazo falló", op.clave)
        return sb.clave_mensaje(causa, op.ruta)

    def _confirmar(self, op: _Op, r, msg: str) -> None:
        try:
            if op.al_ok is not None:
                self._con_id(op, op.al_ok, r)
        except Exception:
            logger.exception("Operación crítica %s: al_ok falló", op.clave)
        finally:
            self._resolver(op, CONFIRMADA, msg)

    # ── verificación ─────────────────────────────────────────────────
    def _verificar(self, op: _Op) -> None:
        if op.releer is None:
            self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)
            return
        op.estado = VERIFICANDO
        op.timer_relectura = self._temporizador(PLAZO_RELECTURA_S,
                                                lambda: self._vencer(op, "relectura"))
        self._notificar()

        def al_leido(leido=SIN_LECTURA):
            self._al_leido(op, leido)
        try:
            op.releer(al_leido)
        except Exception:
            logger.exception("Operación crítica %s: releer falló", op.clave)
            if self._vigente(op):
                self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)

    def _al_leido(self, op: _Op, leido) -> None:
        if not self._vigente(op) or op.estado != VERIFICANDO:
            return
        if leido is SIN_LECTURA or op.conciliar is None:
            self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)
            return
        try:
            res = op.conciliar(leido)
        except Exception:
            logger.exception("Operación crítica %s: conciliar falló", op.clave)
            res = SIN_CONFIRMAR
        estado, msg = (res if isinstance(res, tuple) and len(res) == 2 else (res, None))
        if estado == CONFIRMADA:
            self._resolver(op, CONFIRMADA, msg or "")
        elif estado == RECHAZADA:
            # m1: rechazo por conciliación tras backend_no_responde (no un
            # rechazo del backend): un 200 tardío aún se notifica
            op.rechazo_conciliado = True
            self._resolver(op, RECHAZADA, msg or MSG_NO_COINCIDE)
        else:
            if estado != SIN_CONFIRMAR:
                logger.error("Operación crítica %s: conciliar devolvió %r", op.clave, estado)
            self._resolver(op, SIN_CONFIRMAR, msg or op.msg_sin_confirmar)

    def _vencer(self, op: _Op, cual: str) -> None:
        if not self._vigente(op):
            return
        logger.warning("Operación crítica %s sin confirmar: venció el plazo de %s", op.clave, cual)
        self._resolver(op, SIN_CONFIRMAR, op.msg_sin_confirmar)

    # ── respuesta tardía ─────────────────────────────────────────────
    def _al_tardio(self, op: _Op, r) -> None:
        if op.cancelada:
            return
        ok = bool(getattr(r, "ok", False))
        logger.warning("Operación crítica %s: respuesta tardía %s (estado %s)",
                       op.clave, getattr(r, "causa", "?"), op.final or op.estado)
        if self._vigente(op):
            # llegó mientras se verificaba: un 200 es un hecho del backend; un
            # rechazo no cambia nada (decide la relectura)
            if ok:
                self._confirmar(op, r, "")
            return
        # m1 (revisión FASE 6): igual tras una RECHAZADA que vino de la
        # conciliación tras un timeout (nunca tras un rechazo real del backend)
        tardio_valido = op.final == SIN_CONFIRMAR or (op.final == RECHAZADA
                                                      and op.rechazo_conciliado)
        otra = self._otra_vigente(op)
        if ok and tardio_valido and otra is not None:
            # MAYOR-1: hay otra operación vigente del mismo grupo; este 200 es
            # de una anterior y no se confunde con ella (ni al_ok ni aviso)
            logger.warning("Operación crítica %s (id %s): 200 tardío con otra vigente "
                           "(%s, id %s); solo se relee", op.clave, op.ident, otra.clave, otra.ident)
        elif ok and tardio_valido and not op.tarde_confirmada:
            op.tarde_confirmada = True
            try:
                if op.al_ok_tardio is not None:
                    self._con_id(op, op.al_ok_tardio, r)
            except Exception:
                logger.exception("Operación crítica %s: al_ok (tardío) falló", op.clave)
            self._emitir(op, CONFIRMADA, MSG_CONFIRMADA_TARDE)
        self._releer_sin_conciliar(op)

    def _otra_vigente(self, op: _Op):
        return next((o for o in self._ops.values() if o is not op and o.grupo == op.grupo), None)

    def _con_id(self, op: _Op, fn, *args):
        """Corre fn con `id_resuelta` = id de `op` (al_ok y el desenlace: el
        dueño guarda su contexto por operación, no por clave)."""
        antes = self.id_resuelta, self.contexto_resuelta
        self.id_resuelta, self.contexto_resuelta = op.ident, op.contexto
        try:
            return fn(*args)
        finally:
            self.id_resuelta, self.contexto_resuelta = antes

    def _emitir(self, op: _Op, estado: str, msg: str) -> None:
        self._con_id(op, self.operacionResuelta.emit, op.clave, estado, msg or "")

    def _releer_sin_conciliar(self, op: _Op) -> None:
        if op.releer is None:
            return
        try:
            op.releer(_ignorar)
        except Exception:
            logger.exception("Operación crítica %s: releer (tardío) falló", op.clave)

    # ── cierre ───────────────────────────────────────────────────────
    def _resolver(self, op: _Op, estado: str, msg: str) -> None:
        if op.final is not None:
            return
        op.final = op.estado = estado
        for t in (op.timer_total, op.timer_relectura):
            if t is not None:
                t.stop()
        if self._ops.get(op.clave) is op:
            del self._ops[op.clave]          # vuelve a INACTIVA
        self._notificar()
        self._emitir(op, estado, msg)

    def cancelar(self) -> None:
        """Abandona todo lo que esté en vuelo sin emitir nada (pantalla que se
        destruye): sus respuestas ya no se entregan."""
        for op in self._ops.values():
            op.cancelada = True
            for t in (op.timer_total, op.timer_relectura):
                if t is not None:
                    t.stop()
        hubo = bool(self._ops)
        self._ops.clear()
        try:
            sb.cancelar_envios(self._sesion_fn(), self)
        except Exception:
            logger.exception("Operación crítica: no se pudieron cancelar los envíos")
        if hubo:
            self.operacionEnCursoChanged.emit()
        self._registro.quitar(self)

    def _notificar(self) -> None:
        if not shiboken6.isValid(self):
            return
        self.operacionEnCursoChanged.emit()
        self._registro.actualizar(self)
