# ui_qml/controllers/entradas_salidas_controller.py
#
# OPCIONES > Entradas / Salidas (planeacion_opciones_entradas_salidas.md): una
# sola lectura de /status por tick (D-ES-12) compartida por los cuatro
# segmentos, modo prueba de salidas y calibracion de un sensor. No decide nada
# de seguridad: el backend es la autoridad (D-ES-07, D-ES-15, D-ES-16) y la UI
# solo refleja y muestra el motivo de un rechazo.
#
# AJUSTES 2026-11-02: el tick ya no hace GET /status síncrono en el hilo de la
# GUI; lee el caché de UIServiceBackend (hilo de fondo, 5 Hz). Un caché sin
# conexión o con más de ANTIGUEDAD_MAX_S equivale al fallo de /status de antes
# ("Sin datos"). La señal cambioDatos solo se emite si algo cambió.
#
# FASE 6 (AJUSTES 2026-11-02, paso 2): entrada, salida y keepalive del modo
# prueba, GET /io/channels y la calibración de un sensor van asíncronos y SIN
# OPTIMISMO (OperacionCritica): nada se da por hecho sin un 200 o una
# relectura que coincida. Los slots devuelven True = «enviado» (el resultado
# llega por operacionResuelta) y False = rechazo local. Siguen síncronas, por
# decisión de Cristian, las salidas (PATCH /io/test/output, `accionar`, y su
# renovación de 500 ms) y la salida del modo prueba al cerrar sesión.

import logging
import math
import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.cliente import ui_service_backend
from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import SIN_LECTURA
from autoclave.ui_qml.domain import entradas_salidas as dominio
from autoclave.ui_qml.domain import permisos_opciones as permisos
from autoclave.ui_qml.operacion_critica import (
    CONFIRMADA, MSG_CONFIRMADA_TARDE, PLAZO_RELECTURA_S, RECHAZADA, SIN_CONFIRMAR,
    OperacionCritica)

logger = logging.getLogger(__name__)

# Claves de OperacionCritica (una operación a la vez por clave)
CLAVE_MODO_PRUEBA = "modo_prueba"      # entrada y salida (nunca a la vez)
CLAVE_KEEPALIVE = "keepalive"
CLAVE_CAL_CARGAR = "cal_cargar"
CLAVE_CAL_PUNTOS = "cal_puntos"
CLAVE_CAL_RESTAURAR = "cal_restaurar"
# las que ve la pantalla como «operación en curso» (el keepalive no)
_CLAVES_PANTALLA = (CLAVE_MODO_PRUEBA, CLAVE_CAL_CARGAR, CLAVE_CAL_PUNTOS, CLAVE_CAL_RESTAURAR)

PLAZO_MODO_PRUEBA_S = 5.0
PLAZO_KEEPALIVE_S = 5.0
PLAZO_CALIBRACION_S = 10.0
PLAZO_LECTURA_S = 5.0
# GET de relectura: antes de que venza la relectura de OperacionCritica
_PLAZO_RELECTURA_GET_S = PLAZO_RELECTURA_S - 1.0
_SONDEO_RELECTURA_MS = 200
MSG_PRUEBA_SIN_CONFIRMAR = "io.prueba_sin_confirmar"
MSG_PROCESANDO = "operacion.procesando"
# C1 (revisión FASE 6): aplicar/restaurar pedidos desde una pantalla cuyo
# sensor no es el de la calibración cargada (sin clave i18n propia: i18n fuera
# del alcance de la corrección)
MSG_CAL_OTRO_SENSOR = "operacion.sin_confirmar"
# la salida es idempotente: ya inactivo cuenta como salida hecha; con la
# sesión inválida lo cierra el backend por la sesión dueña (SAF-01)
_CAUSAS_SALIDA_HECHA = frozenset({"modo_prueba_inactivo", "sesion_invalida"})
# tolerancia para comparar ganancia y offset releídos con los calculados
_TOL_REL, _TOL_ABS = 1e-6, 1e-6


def _ignorar(*_a) -> None:
    return None

_CLAVE_CORTA_TEMP = {"temp_camara": "camara", "temp_2_camara": "camara_2",
                     "temp_ref": "ref", "temp_drenaje": "drenaje"}
_CLAVE_CORTA_PRES = {"pres_camara": "camara", "pres_chaqueta": "chaqueta",
                     "pres_empaque_1": "empaque_1", "pres_empaque_2": "empaque_2"}
_TIPO_API = {"temperatura": "temperature", "presion": "pressure"}

_CAUSAS_SOLO_CATALOGO = frozenset({"aire_atmosferico_con_presion",
                                   "aire_atmosferico_sin_presion",
                                   "aire_atmosferico_sin_referencia",
                                   # S9 (revisión ★ SAF-01)
                                   "salida_prueba_camara_no_segura",
                                   "salida_prueba_estado_seguro",
                                   # Tanda 17 (ESG-02): protecciones permanentes
                                   "salida_prueba_camara_presurizada",
                                   "salida_prueba_puerta_abierta"})

# D-ES-08: sin actividad del usuario en la seccion el modo prueba se cierra
INACTIVIDAD_UI_S = 5 * 60

# Un /status del caché más viejo que esto no se muestra como vigente (el
# sondeo es de 0,2 s con plazos de 0,8 s por petición)
ANTIGUEDAD_MAX_S = 3.0


def status_del_cache(fuente):
    """(/status vigente del caché de UIServiceBackend o None, monotonic del
    envío de su petición o None). None: sin servicio, sin conexión, sin datos,
    vencido o error al leer, el mismo trato que un GET /status sin respuesta.
    Un doble que no da el instante de envío (3 valores) da None en él."""
    if fuente is None:
        return None, None
    try:
        lectura = tuple(fuente.status_vigente())
        status, conectado, edad = lectura[:3]
        t_envio = lectura[3] if len(lectura) > 3 else None
    except Exception:
        logger.exception("Lectura del caché de /status fallida")
        return None, None
    if conectado is not True or not isinstance(status, dict) or not status:
        return None, None
    if not isinstance(edad, (int, float)) or edad < 0 or edad > ANTIGUEDAD_MAX_S:
        return None, None
    if not isinstance(t_envio, (int, float)):
        t_envio = None
    return status, t_envio


def mensaje_de(causa: str) -> str:
    return sesion_backend.clave_mensaje(causa)


# Tanda 17 (MPR-01 / ESG-02): avisos de salidas cortadas en el modo prueba.
# Contrato del backend: /status.avisos_corte_prueba = [{n, salida, codigo,
# aviso}], con `aviso` la clave i18n (io.ui.aviso_...) o "". Se aceptan
# también textos o dicts con "causa"/"motivo"/"codigo" (deducción por causa).
CLAVES_AVISOS_CORTE = ("avisos_corte_prueba",)
_AVISO_POR_CAUSA = (("puerta", "io.ui.aviso_vapor_cortado_puerta"),
                    ("presion", "io.ui.aviso_salida_cortada_presion"),
                    ("presuriz", "io.ui.aviso_salida_cortada_presion"),
                    ("camara_no_segura", "io.ui.aviso_salida_cortada_presion"))


def avisos_corte(status) -> list[dict]:
    """[{clave, salida, texto}]: `clave` i18n si se reconoce la causa; si no,
    `texto` con lo recibido (la pantalla lo muestra tal cual)."""
    if not isinstance(status, dict):
        return []
    lista = next((status[k] for k in CLAVES_AVISOS_CORTE if isinstance(status.get(k), list)), [])
    salida = []
    for e in lista:
        if isinstance(e, dict):
            causa = str(e.get("aviso") or e.get("causa") or e.get("motivo") or e.get("codigo") or "")
            nombre = str(e.get("salida") or "")
        elif isinstance(e, str):
            causa, nombre = e, ""
        else:
            continue
        if causa.startswith("io.ui."):
            clave = causa
        else:
            clave = next((c for frag, c in _AVISO_POR_CAUSA if frag in causa.lower()), "")
        if clave or causa:
            salida.append({"clave": clave, "salida": nombre, "texto": "" if clave else causa})
    return salida


def presion_camara(status):
    """MPR-01: presión de cámara (kPa abs) de /status con el módulo E/S en línea;
    None sin lectura (la pantalla muestra «—»)."""
    if not dominio.enlace_ok(status):
        return None
    pres = (status.get("sensors") or {}).get("pressure") if isinstance(status.get("sensors"), dict) else None
    v = pres.get("camara") if isinstance(pres, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


def _conciliar_puntos(leido, esperado) -> str:
    """Calibración releída tras un PATCH sin respuesta: CONFIRMADA solo si
    ganancia y offset coinciden con lo calculado (con tolerancia)."""
    if not (isinstance(esperado, dict) and esperado.get("valido")) or not isinstance(leido, dict):
        return SIN_CONFIRMAR
    try:
        g, o = float(leido.get("gain")), float(leido.get("offset"))
        ge, oe = float(esperado["gain"]), float(esperado["offset"])
    except (TypeError, ValueError, KeyError):
        return SIN_CONFIRMAR
    if (math.isclose(g, ge, rel_tol=_TOL_REL, abs_tol=_TOL_ABS)
            and math.isclose(o, oe, rel_tol=_TOL_REL, abs_tol=_TOL_ABS)):
        return CONFIRMADA
    return SIN_CONFIRMAR


class EntradasSalidasController(QObject):
    cambioDatos = Signal()
    modoPruebaChanged = Signal()
    mensajeChanged = Signal()
    calibracionChanged = Signal()
    salidasHabilitadasChanged = Signal()
    pruebaSinConfirmarChanged = Signal()
    operacionEnCursoChanged = Signal()
    operacionResuelta = Signal(str, str, str)   # clave, estado final, clave i18n

    def __init__(self, parent=None, sesion=None, fuente_estado=None):
        super().__init__(parent)
        self._sesion = sesion
        self._fuente_estado = fuente_estado   # UIServiceBackend (o doble); None = el del proceso
        self._ultimo = None                   # lo último publicado (para emitir solo si cambia)
        # monotonic de la respuesta a la última orden (modo prueba, salida): un
        # /status pedido antes no la refleja y se descarta (AJUSTES 2026-11-02)
        self._t_orden = None
        self._canales = {"DI": [], "DO": [], "temperature": [], "pressure": []}
        self._status = None
        self._entradas, self._salidas = [], []
        self._temperatura, self._presion = [], []
        self._modo_prueba = False
        self._estado_maquina = ""
        self._mensaje = ""           # clave i18n
        self._detalle = ""           # texto del backend, si lo hay
        self._calibracion = {}
        # FASE 6: modo prueba sin optimismo
        self._prueba_sin_confirmar = False   # entrada sin 200 ni relectura que la confirme
        self._salida_sin_confirmar = False   # salida sin 200 ni relectura que la confirme
        self._orden_tipo = None              # "entrar" | "salir" mientras va en vuelo
        self._causa_salida = ""
        self._ultima_causa = None            # causa del último rechazo de modo prueba
        self._salida_reintentada = False     # el reintento automático es uno solo
        self._salir_tras_entrar = None       # causa pedida con la entrada en vuelo
        self._habilitadas = False            # último salidasHabilitadas publicado
        self._gen_entrada = None             # generación de sesión al pedir la entrada (m2)
        # C1: generación del último GET de calibración pedido; un 200 de otro
        # pedido (tardío) no fija `_calibracion`
        self._cal_gen = 0
        self._cargando_canales = False
        self._lecturas_status = []           # al_leido pendientes de un /status nuevo
        self._t_relectura = 0.0
        self._timer_relectura = QTimer(self)
        self._timer_relectura.setInterval(_SONDEO_RELECTURA_MS)
        self._timer_relectura.timeout.connect(self._revisar_relectura)
        self._op = OperacionCritica(self, self._s)
        self._op.operacionEnCursoChanged.connect(self._al_cambiar_operacion)
        self._op.operacionResuelta.connect(self._al_resuelta)

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    @staticmethod
    def _rol() -> str:
        return (SessionManager.current_user() or {}).get("rol") or ""

    # -- mensajes -------------------------------------------------------

    def _fallo(self, r, ruta: str = "") -> None:
        self._mensaje = sesion_backend.clave_mensaje(r.causa, ruta)
        d = r.datos if isinstance(r.datos, dict) else {}
        # D8-3.19: estos motivos ya tienen su texto completo en el catálogo; el
        # del backend (en español) no se agrega
        self._detalle = ("" if r.causa in _CAUSAS_SOLO_CATALOGO
                         else str(d.get("detail") or ""))
        self.mensajeChanged.emit()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave and clave != self._mensaje:
            self._mensaje, self._detalle = clave, ""
            self.mensajeChanged.emit()

    def _limpiar_mensaje(self) -> None:
        if self._mensaje or self._detalle:
            self._mensaje, self._detalle = "", ""
            self.mensajeChanged.emit()

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property(str, notify=mensajeChanged)
    def detalle(self) -> str:
        return self._detalle

    @Slot()
    def limpiarMensaje(self) -> None:
        self._limpiar_mensaje()

    # -- lectura en vivo ------------------------------------------------

    @Slot()
    def cargarCanales(self) -> None:
        """Asíncrono (FASE 6); una sola petición a la vez."""
        if self._cargando_canales:
            return
        self._cargando_canales = True
        try:
            sesion_backend.enviar_async(self._s(), "GET", "/io/channels", None,
                                        self._al_canales, dueno=self, plazo_s=PLAZO_LECTURA_S)
        except Exception:
            logger.exception("GET /io/channels: el envío falló")
            self._cargando_canales = False

    def _al_canales(self, r) -> None:
        self._cargando_canales = False
        if r.ok and isinstance(r.datos, dict):
            self._canales = {k: list(r.datos.get(k) or []) for k in self._canales}
            self._limpiar_mensaje()
        else:
            self._fallo(r, "/io/channels")
        self._reconstruir()

    def _fuente(self):
        return self._fuente_estado or ui_service_backend.servicio_activo()

    @Slot()
    def actualizar(self) -> None:
        """Un tick de 1 s, sin red: lee el caché de /status. Sin datos
        vigentes, todo pasa a "Sin datos". Un /status vigente pedido antes de
        la última orden aún no la refleja: se conserva lo ya mostrado.
        Con una orden de modo prueba en vuelo el estado del modo prueba no se
        toca (solo cambia con su 200 o su relectura)."""
        status, t_envio = status_del_cache(self._fuente())
        if (status is not None and self._t_orden is not None
                and t_envio is not None and t_envio <= self._t_orden):
            return                               # aún sin dato nuevo
        self._status = status
        if self._status is not None:
            self._estado_maquina = str(self._status.get("machine_state") or "")
            if self._orden_tipo is None:
                self._adoptar(bool(self._status.get("test_mode_active")))
        self._reconstruir()

    def _adoptar(self, activo: bool) -> None:
        """Estado del modo prueba según un /status nuevo, sin orden en vuelo.
        Activo: se adopta CON el gancho de cierre de sesión (antes se adoptaba
        sin él); una salida sin confirmar sigue sin confirmar (salidas
        deshabilitadas) hasta un /status inactivo o una salida confirmada."""
        if activo:
            if not self._modo_prueba or self._prueba_sin_confirmar:
                self._fijar_prueba(True, sin_salida=self._salida_sin_confirmar)
        elif self._modo_prueba or self._prueba_sin_confirmar or self._salida_sin_confirmar:
            self._fijar_prueba(False)

    def _reconstruir(self) -> None:
        c, st = self._canales, self._status
        self._entradas = dominio.presentar_entradas(c["DI"], st)
        self._salidas = dominio.presentar_salidas(c["DO"], st)
        self._temperatura = dominio.presentar_sensores(c["temperature"], "temperature", st,
                                                       _CLAVE_CORTA_TEMP)
        self._presion = dominio.presentar_sensores(c["pressure"], "pressure", st,
                                                   _CLAVE_CORTA_PRES)
        # Solo si cambió algo de lo que cuelga de cambioDatos: reemplazar las
        # listas cada segundo hacía que los Repeater recrearan los delegados
        visible = (self._entradas, self._salidas, self._temperatura, self._presion,
                   presion_camara(st), avisos_corte(st), dominio.enlace_ok(st),
                   self._estado_maquina, self._rol())
        if visible != self._ultimo:
            self._ultimo = visible
            self.cambioDatos.emit()

    @Property("QVariantList", notify=cambioDatos)
    def entradas(self) -> list:
        return self._entradas

    @Property("QVariantList", notify=cambioDatos)
    def salidas(self) -> list:
        return self._salidas

    @Property("QVariantList", notify=cambioDatos)
    def temperatura(self) -> list:
        return self._temperatura

    @Property("QVariantList", notify=cambioDatos)
    def presion(self) -> list:
        return self._presion

    @Property("QVariant", notify=cambioDatos)
    def presionCamara(self):
        """MPR-01 (tanda 17): kPa absolutos o None («—» en la pantalla)."""
        return presion_camara(self._status)

    @Property("QVariantList", notify=cambioDatos)
    def avisosCorte(self) -> list:
        """MPR-01 / ESG-02 (tanda 17): salidas cortadas por las protecciones
        del modo prueba (ver CLAVES_AVISOS_CORTE)."""
        return avisos_corte(self._status)

    @Property(bool, notify=cambioDatos)
    def enlace(self) -> bool:
        return dominio.enlace_ok(self._status)

    @Property(str, notify=cambioDatos)
    def estadoMaquina(self) -> str:
        return self._estado_maquina

    # -- permisos (reflejan al backend) ---------------------------------

    @Property(bool, notify=cambioDatos)
    def puedeProbar(self) -> bool:
        return permisos.puede_modo_prueba(self._rol(), self._estado_maquina)

    @Property(bool, notify=cambioDatos)
    def puedeCalibrar(self) -> bool:
        return permisos.puede_calibrar(self._rol(), self._estado_maquina)

    # -- modo prueba ----------------------------------------------------

    def _marcar_orden(self) -> None:
        """Tras la respuesta del backend a una orden: todo /status pedido antes
        de este instante queda viejo para la pantalla. Se toma al volver la
        respuesta (no al enviarla) porque un /status pedido mientras la orden
        está en curso tampoco la refleja con certeza."""
        self._t_orden = time.monotonic()

    @Property(bool, notify=modoPruebaChanged)
    def modoPrueba(self) -> bool:
        return self._modo_prueba

    @Property(bool, notify=salidasHabilitadasChanged)
    def salidasHabilitadas(self) -> bool:
        """FASE 6: las salidas (y la renovación de 500 ms) solo con el modo
        prueba confirmado, sin orden de modo prueba en vuelo y sin dudas."""
        return self._calcular_habilitadas()

    def _calcular_habilitadas(self) -> bool:
        return (self._modo_prueba and self._orden_tipo is None
                and not self._prueba_sin_confirmar and not self._salida_sin_confirmar)

    @Property(bool, notify=pruebaSinConfirmarChanged)
    def pruebaSinConfirmar(self) -> bool:
        """M1 (revisión FASE 6): entrada o salida del modo prueba sin confirmar.
        La pantalla sigue ofreciendo el APAGADO de una salida sostenida
        encendida (accionar(False) sale siempre); encender exige
        salidasHabilitadas."""
        return self._prueba_sin_confirmar or self._salida_sin_confirmar

    def _publicar_habilitadas(self) -> None:
        valor = self._calcular_habilitadas()
        if valor != self._habilitadas:
            self._habilitadas = valor
            self.salidasHabilitadasChanged.emit()

    def _fijar_prueba(self, activo: bool, *, sin_entrada: bool = False,
                      sin_salida: bool = False) -> None:
        """Único lugar que cambia el estado local del modo prueba. El gancho de
        cierre de sesión queda puesto mientras el modo prueba pueda estar
        activo en el backend (activo o entrada sin confirmar)."""
        cambio = bool(activo) != self._modo_prueba
        dudas_antes = self._prueba_sin_confirmar or self._salida_sin_confirmar
        self._modo_prueba = bool(activo)
        self._prueba_sin_confirmar = bool(sin_entrada)
        self._salida_sin_confirmar = bool(sin_salida)
        self._avisar_cierre(self._modo_prueba or self._prueba_sin_confirmar)
        if cambio:
            self.modoPruebaChanged.emit()
        if (self._prueba_sin_confirmar or self._salida_sin_confirmar) != dudas_antes:
            self.pruebaSinConfirmarChanged.emit()
        self._publicar_habilitadas()

    # -- operaciones (OperacionCritica) ---------------------------------

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        return any(self._op.en_curso(k) for k in _CLAVES_PANTALLA)

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        return self._op.estado(clave)

    def _al_cambiar_operacion(self) -> None:
        # siempre (también enviando -> verificando): la QML relee estadoDe()
        self.operacionEnCursoChanged.emit()

    def _al_resuelta(self, clave: str, estado: str, msg: str) -> None:
        reintentar = False
        if clave == CLAVE_MODO_PRUEBA:
            if msg == MSG_CONFIRMADA_TARDE:
                # 200 tardío de una orden ya resuelta: no fija estado; la
                # relectura ya marcó la orden y decide el primer /status nuevo
                logger.warning("Modo prueba: respuesta tardía; se espera el /status")
            else:
                tipo, self._orden_tipo = self._orden_tipo, None
                self._marcar_orden()
                if tipo == "entrar":
                    self._resuelta_entrar(estado, msg)
                elif tipo == "salir":
                    estado, msg, reintentar = self._resuelta_salir(estado, msg)
                self._publicar_habilitadas()
        elif clave == CLAVE_KEEPALIVE:
            if estado != CONFIRMADA:
                # sin respuesta: solo log (el rechazo con respuesta ya se mostró)
                logger.warning("Keepalive del modo prueba %s", estado)
        elif clave in (CLAVE_CAL_CARGAR, CLAVE_CAL_PUNTOS, CLAVE_CAL_RESTAURAR):
            if estado == CONFIRMADA and msg != MSG_CONFIRMADA_TARDE:
                self._limpiar_mensaje()
            elif estado in (RECHAZADA, SIN_CONFIRMAR):
                self._fijar_mensaje(msg)
        self.operacionResuelta.emit(clave, estado, msg)
        if reintentar:
            logger.warning("Salida del modo prueba sin confirmar: reintento único")
            self._lanzar_salida(self._causa_salida)
        elif clave == CLAVE_MODO_PRUEBA and self._salir_tras_entrar is not None \
                and self._orden_tipo is None:
            causa, self._salir_tras_entrar = self._salir_tras_entrar, None
            if self._modo_prueba or self._prueba_sin_confirmar:
                self._salida_reintentada = False
                self._lanzar_salida(causa)

    # -- modo prueba ----------------------------------------------------

    @Slot(result=bool)
    def entrarModoPrueba(self) -> bool:
        """True = enviada; el resultado llega por operacionResuelta
        ("modo_prueba"). modoPrueba no cambia hasta el 200 o la relectura."""
        if self._orden_tipo is not None or self._op.en_curso(CLAVE_MODO_PRUEBA):
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        self._orden_tipo = "entrar"
        self._ultima_causa = None
        self._gen_entrada = self._generacion()
        self._publicar_habilitadas()
        # m2 (revisión FASE 6): el gancho de cierre de sesión se pone al INICIAR
        # la entrada (un logout con la entrada en vuelo pide la salida); se
        # quita si la entrada se rechaza o se confirma inactiva
        self._avisar_cierre(True)
        # m6 (revisión FASE 6), LIMITACIÓN: /status solo publica
        # test_mode_active, sin la sesión dueña; una relectura activa puede ser
        # el modo prueba de OTRA sesión y aquí se toma como confirmada. Las
        # salidas de una sesión que no es la dueña las rechaza el backend
        # (modo_prueba_dueno_vigente). No se cambia más hasta que /status
        # publique el dueño.
        if not self._op.iniciar(
                CLAVE_MODO_PRUEBA, "POST", "/io/test/enter", None,
                plazo_s=PLAZO_MODO_PRUEBA_S,
                al_rechazo=self._rechazo_modo_prueba("/io/test/enter"),
                releer=self._releer_status,
                conciliar=lambda activo: (CONFIRMADA if activo
                                          else (SIN_CONFIRMAR, MSG_PRUEBA_SIN_CONFIRMAR)),
                msg_sin_confirmar=MSG_PRUEBA_SIN_CONFIRMAR):
            self._orden_tipo = None
            self._avisar_cierre(self._modo_prueba or self._prueba_sin_confirmar)
            self._publicar_habilitadas()
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        return True

    def _generacion(self):
        try:
            return getattr(self._s(), "generacion", None)
        except Exception:
            logger.exception("Modo prueba: no se pudo leer la generación de la sesión")
            return None

    def _resuelta_entrar(self, estado: str, msg: str) -> None:
        if estado in (CONFIRMADA, SIN_CONFIRMAR) and self._generacion() != self._gen_entrada:
            # m2: la sesión cambió con la entrada en vuelo (el cierre ya pidió
            # la salida; el backend cierra el modo prueba de la sesión dueña,
            # SAF-01): ni gancho ni salidas en la sesión del usuario nuevo
            logger.warning("Modo prueba: entrada resuelta (%s) tras un cambio de sesión", estado)
            self._fijar_prueba(False)
            if estado == SIN_CONFIRMAR:
                self._fijar_mensaje(msg or MSG_PRUEBA_SIN_CONFIRMAR)
            return
        if estado == CONFIRMADA:
            self._limpiar_mensaje()
            self._fijar_prueba(True)
        elif estado == SIN_CONFIRMAR:
            # no se sabe si entró: salidas deshabilitadas, gancho de cierre
            # puesto; decide el primer /status nuevo (actualizar -> _adoptar)
            self._fijar_prueba(False, sin_entrada=True)
            self._fijar_mensaje(msg or MSG_PRUEBA_SIN_CONFIRMAR)
        else:
            # rechazada: se vuelve al estado previo (quita el gancho puesto al
            # iniciar si no había modo prueba ni dudas)
            self._fijar_prueba(self._modo_prueba, sin_entrada=self._prueba_sin_confirmar,
                               sin_salida=self._salida_sin_confirmar)
            self._fijar_mensaje(msg)   # el de al_rechazo (con detalle) o el de la causa

    def _resuelta_salir(self, estado: str, msg: str):
        """(estado, msg, reintentar) que se publica. Un rechazo
        modo_prueba_inactivo / sesion_invalida es una salida hecha."""
        if estado == RECHAZADA and self._ultima_causa in _CAUSAS_SALIDA_HECHA:
            estado, msg = CONFIRMADA, ""
        if estado == CONFIRMADA:
            self._limpiar_mensaje()
            self._fijar_prueba(False)
            return estado, msg, False
        if estado == SIN_CONFIRMAR:
            if not (self._modo_prueba or self._prueba_sin_confirmar):
                return estado, msg, False        # ya limpiado (cierre de sesión)
            # salidas deshabilitadas, keepalive detenido, gancho puesto
            self._fijar_prueba(self._modo_prueba, sin_entrada=self._prueba_sin_confirmar,
                               sin_salida=True)
            self._fijar_mensaje(msg or MSG_PRUEBA_SIN_CONFIRMAR)
            reintentar = not self._salida_reintentada
            self._salida_reintentada = True
            return estado, msg, reintentar
        self._fijar_mensaje(msg)
        return estado, msg, False

    def _rechazo_modo_prueba(self, ruta: str):
        def al_rechazo(r):
            self._ultima_causa = r.causa
            if ruta == "/io/test/exit" and r.causa in _CAUSAS_SALIDA_HECHA:
                return ""
            self._fallo(r, ruta)
            return self._mensaje
        return al_rechazo

    def _releer_status(self, al_leido) -> None:
        """Relectura del modo prueba: el primer /status del caché pedido
        DESPUÉS de este instante (test_mode_active). Sin uno en
        PLAZO_RELECTURA_S, SIN_LECTURA. También marca la orden: un /status
        anterior ya no se muestra (también ante una respuesta tardía)."""
        self._marcar_orden()
        self._lecturas_status.append(al_leido)
        self._t_relectura = time.monotonic()
        self._revisar_relectura()
        if self._lecturas_status and not self._timer_relectura.isActive():
            self._timer_relectura.start()

    def _revisar_relectura(self) -> None:
        if not self._lecturas_status:
            self._timer_relectura.stop()
            return
        status, t_envio = status_del_cache(self._fuente())
        if (status is not None and t_envio is not None and self._t_orden is not None
                and t_envio > self._t_orden):
            valor = bool(status.get("test_mode_active"))
        elif time.monotonic() - self._t_relectura > PLAZO_RELECTURA_S:
            valor = SIN_LECTURA
        else:
            return
        pendientes, self._lecturas_status = self._lecturas_status, []
        self._timer_relectura.stop()
        for al_leido in pendientes:
            try:
                al_leido(valor)
            except Exception:
                logger.exception("Relectura del modo prueba: entrega fallida")

    def _al_cerrar_sesion(self) -> None:
        """Corre antes del logout (síncrona, plazo corto, por decisión de
        Cristian). Sea cual sea la respuesta, la sesión muere: el estado local
        queda limpio y, si la salida no se confirmó, la cierra el backend al
        invalidarse la sesión dueña (SAF-01)."""
        s = self._s()
        enviar = getattr(s, "enviar_al_cerrar", s.enviar)
        if self._modo_prueba or self._prueba_sin_confirmar or self._orden_tipo is not None:
            r = enviar("POST", "/io/test/exit", {"motivo": "cierre de sesión"})
            self._marcar_orden()
            if not (r.ok or r.causa == "modo_prueba_inactivo"):
                logger.warning("Salida del modo prueba al cerrar sesión sin confirmar (%s)", r.causa)
        self._salir_tras_entrar = None
        self._fijar_prueba(False)

    def _avisar_cierre(self, activo: bool) -> None:
        """P1: con el modo prueba activo, el cierre de sesión sale primero."""
        s = self._s()
        metodo = getattr(s, "al_cerrar_sesion" if activo else "quitar_al_cerrar_sesion", None)
        if metodo is not None:
            metodo(self._al_cerrar_sesion)

    @Slot(str, result=bool)
    def salirModoPrueba(self, causa: str = "salida solicitada") -> bool:
        """True = enviada o nada que hacer; el resultado llega por
        operacionResuelta ("modo_prueba"). Primero baja salidasHabilitadas
        (la pantalla suelta la momentánea, con su OFF síncrono) y luego lanza
        la salida; todo en el hilo de la GUI. Con la entrada en vuelo, la
        salida sale en cuanto esta se resuelva."""
        if self._orden_tipo == "salir":
            return True
        if self._orden_tipo == "entrar":
            self._salir_tras_entrar = causa
            return True
        if not (self._modo_prueba or self._prueba_sin_confirmar or self._salida_sin_confirmar):
            return True
        self._salida_reintentada = False
        return self._lanzar_salida(causa)

    def _lanzar_salida(self, causa: str) -> bool:
        self._causa_salida = causa
        self._orden_tipo = "salir"
        self._ultima_causa = None
        self._publicar_habilitadas()     # antes de enviar: sin salidas a medio dar
        if not self._op.iniciar(
                CLAVE_MODO_PRUEBA, "POST", "/io/test/exit", {"motivo": causa},
                plazo_s=PLAZO_MODO_PRUEBA_S,
                al_rechazo=self._rechazo_modo_prueba("/io/test/exit"),
                releer=self._releer_status,
                conciliar=lambda activo: (CONFIRMADA if not activo
                                          else (SIN_CONFIRMAR, MSG_PRUEBA_SIN_CONFIRMAR)),
                msg_sin_confirmar=MSG_PRUEBA_SIN_CONFIRMAR):
            self._orden_tipo = None
            self._publicar_habilitadas()
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        return True

    @Slot(str)
    def abandonar(self, causa: str) -> None:
        """La pantalla se destruye: la salida se lanza igual (sus respuestas ya
        no tendrán a quién entregarse, pero la petición sale; nadie la
        cancela) y después se quita el gancho de cierre de sesión, que
        apuntaría a este objeto destruido. Si la entrada aún va en vuelo, la
        salida va aparte, sin dueño; el respaldo es el plazo de inactividad del
        backend (INACTIVIDAD_MODO_PRUEBA_S)."""
        entrando = self._orden_tipo == "entrar"
        self.salirModoPrueba(causa)
        if entrando:
            try:
                sesion_backend.enviar_async(self._s(), "POST", "/io/test/exit",
                                            {"motivo": causa}, _ignorar,
                                            plazo_s=PLAZO_MODO_PRUEBA_S)
            except Exception:
                logger.exception("Salida del modo prueba al destruir la pantalla: envío fallido")
        self._salir_tras_entrar = None
        self._avisar_cierre(False)

    @Slot()
    def keepalive(self) -> None:
        """Asíncrono: uno a la vez; sin respuesta solo va al log."""
        if not self._calcular_habilitadas() or self._op.en_curso(CLAVE_KEEPALIVE):
            return
        self._op.iniciar(CLAVE_KEEPALIVE, "POST", "/io/test/keepalive", None,
                         plazo_s=PLAZO_KEEPALIVE_S,
                         al_rechazo=self._rechazo_simple("/io/test/keepalive"))

    def _rechazo_simple(self, ruta: str):
        def al_rechazo(r):
            self._fallo(r, ruta)
            return self._mensaje
        return al_rechazo

    @Slot(str, bool, bool, result=bool)
    def accionar(self, nombre: str, encender: bool, momentanea: bool) -> bool:
        """Enciende o apaga una salida (SÍNCRONA, decisión de Cristian). Si el
        backend rechaza, se muestra su motivo; el estado real lo corrige el
        siguiente tick. FASE 6: encender exige salidasHabilitadas (si no,
        False sin enviar); apagar sale siempre."""
        if encender and not self._calcular_habilitadas():
            logger.info("Salida %s: encendido rechazado sin modo prueba confirmado", nombre)
            return False
        cuerpo = {"value": bool(encender)}
        if momentanea and encender:
            cuerpo["momentanea"] = True
        r = self._s().enviar("PATCH", f"/io/test/output/{nombre}", cuerpo)
        self._marcar_orden()
        if not encender and r.causa == "modo_prueba_inactivo":
            return True          # sin modo prueba el backend ya apagó todo
        if not r.ok:
            self._fallo(r)
            return False
        self._limpiar_mensaje()
        return True

    # -- calibracion de un sensor ---------------------------------------

    @Slot(str, str, result=bool)
    def cargarCalibracion(self, segmento: str, sensor: str) -> bool:
        """True = pedida; la pantalla se abre con operacionResuelta
        ("cal_cargar", "confirmada"). False = rechazo local."""
        tipo = _TIPO_API.get(segmento)
        if tipo is None:
            return False
        if self._cal_en_curso():
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        ruta = f"/calibration/{tipo}/{sensor}"
        # C1 (revisión FASE 6): solo el 200 del ÚLTIMO pedido fija la
        # calibración; uno tardío de un pedido anterior (otro sensor) se descarta
        self._cal_gen += 1
        gen = self._cal_gen
        return self._op.iniciar(
            CLAVE_CAL_CARGAR, "GET", ruta, None, plazo_s=PLAZO_LECTURA_S,
            al_ok=lambda r: self._al_cargar_ok(gen, tipo, sensor, r),
            al_rechazo=self._rechazo_simple(ruta),
            msg_sin_confirmar=sesion_backend.clave_mensaje(sesion_backend.BACKEND_NO_RESPONDE))

    def _al_cargar_ok(self, gen: int, tipo: str, sensor: str, r) -> None:
        if gen != self._cal_gen:
            logger.warning("Calibración %s/%s: 200 de un pedido anterior, se descarta",
                           tipo, sensor)
            return
        self._fijar_calibracion(tipo, sensor, r.datos)

    @Slot(str, str, result=bool)
    def calibracionEs(self, segmento: str, sensor: str) -> bool:
        """C1: True si la calibración cargada es la de (segmento|tipo, sensor)."""
        tipo = _TIPO_API.get(segmento, segmento)
        c = self._calibracion
        return bool(tipo) and bool(sensor) and (c.get("tipo"), c.get("sensor")) == (tipo, sensor)

    def _rechazar_otro_sensor(self, accion: str, segmento: str, sensor: str) -> bool:
        """C1: False (y mensaje) si la pantalla pide `accion` para un sensor que
        no es el de la calibración cargada. La pantalla siempre los pasa (la
        firma del slot los exige); solo una llamada desde Python sin ellos
        (None) usa la cargada. Vacíos desde la pantalla: rechazo."""
        if segmento is None and sensor is None:
            return True
        if self.calibracionEs(segmento, sensor):
            return True
        c = self._calibracion
        logger.error("Calibración: %s pedido para %s/%s con %s/%s cargada; rechazado",
                     accion, segmento, sensor, c.get("tipo"), c.get("sensor"))
        self._fijar_mensaje(MSG_CAL_OTRO_SENSOR)
        return False

    def _fijar_calibracion(self, tipo: str, sensor: str, d, *, solo_vigente: bool = False) -> None:
        if not isinstance(d, dict):
            return
        c = self._calibracion
        if solo_vigente and (c.get("tipo"), c.get("sensor")) != (tipo, sensor):
            return               # ya se mira otro sensor
        self._calibracion = {"tipo": tipo, "sensor": sensor, "gain": d.get("gain"),
                             "offset": d.get("offset"), "poly": bool(d.get("is_poly")),
                             "ultimo": d.get("last_change")}
        self.calibracionChanged.emit()

    def _releer_calibracion(self, tipo: str, sensor: str, al_leido) -> None:
        """GET asíncrono de la calibración vigente: la muestra (son los valores
        del backend) y la entrega a `al_leido` (SIN_LECTURA si no hay)."""
        def entregar(r):
            if r.ok and isinstance(r.datos, dict):
                self._fijar_calibracion(tipo, sensor, r.datos, solo_vigente=True)
                al_leido(r.datos)
            else:
                al_leido(SIN_LECTURA)
        sesion_backend.enviar_async(self._s(), "GET", f"/calibration/{tipo}/{sensor}", None,
                                    entregar, dueno=self, plazo_s=_PLAZO_RELECTURA_GET_S)

    @Property("QVariantMap", notify=calibracionChanged)
    def calibracion(self) -> dict:
        return self._calibracion

    @Slot(float, float, float, float, result="QVariantMap")
    def calcular(self, lectura_baja: float, real_bajo: float,
                 lectura_alta: float, real_alto: float) -> dict:
        """Ganancia y offset resultantes, con la misma formula del backend."""
        c = self._calibracion
        try:
            g, o = dominio.calcular_calibracion(
                lectura_baja, real_bajo, lectura_alta, real_alto,
                c.get("gain", 1.0), c.get("offset", 0.0))
        except (ValueError, TypeError):
            return {"valido": False}
        return {"valido": True, "gain": g, "offset": o}

    @Slot(float, float, float, float, str, str, bool, str, str, result=bool)
    def aplicarPuntos(self, lectura_baja: float, real_bajo: float,
                      lectura_alta: float, real_alto: float,
                      origen_bajo: str, origen_alto: str, confirmar: bool,
                      segmento: str = None, sensor: str = None) -> bool:
        """True = enviada; el resultado llega por operacionResuelta
        ("cal_puntos"). Los valores mostrados siguen siendo los del backend
        hasta el 200 (luego se releen). Sin respuesta: relectura; coincide
        con lo calculado -> confirmada; si no, sin confirmar con lo leído.
        C1: `segmento` y `sensor` son los de la pantalla; si no son los de la
        calibración cargada, False sin enviar."""
        if self._cal_en_curso():
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        if not self._rechazar_otro_sensor("aplicar", segmento, sensor):
            return False
        c = self._calibracion
        tipo, sensor = c.get("tipo"), c.get("sensor")
        if not tipo or not sensor:
            return False
        esperado = self.calcular(lectura_baja, real_bajo, lectura_alta, real_alto)
        cuerpo = {"shown_low": lectura_baja, "real_low": real_bajo,
                  "shown_high": lectura_alta, "real_high": real_alto,
                  "origen_lectura": {"bajo": origen_bajo, "alto": origen_alto}}
        if confirmar:
            cuerpo["confirmar_fuera_de_rango"] = True
        ruta = f"/calibration/{tipo}/{sensor}"
        return self._op.iniciar(
            CLAVE_CAL_PUNTOS, "PATCH", ruta, cuerpo, plazo_s=PLAZO_CALIBRACION_S,
            al_ok=lambda _r: self._tras_escribir_calibracion(tipo, sensor),
            al_rechazo=self._rechazo_simple(ruta),
            releer=lambda al_leido: self._releer_calibracion(tipo, sensor, al_leido),
            conciliar=lambda leido: _conciliar_puntos(leido, esperado),
            bloquea_navegacion=True)

    @Slot(str, str, str, result=bool)
    def restaurar(self, destino: str, segmento: str = None, sensor: str = None) -> bool:
        """True = enviada ("cal_restaurar"). Sin respuesta: se relee y se
        muestra lo leído, pero queda sin confirmar. C1: como aplicarPuntos,
        rechaza en local si la pantalla no es la del sensor cargado."""
        if self._cal_en_curso():
            self._fijar_mensaje(MSG_PROCESANDO)
            return False
        if not self._rechazar_otro_sensor("restaurar", segmento, sensor):
            return False
        c = self._calibracion
        tipo, sensor = c.get("tipo"), c.get("sensor")
        if not tipo or not sensor:
            return False
        ruta = f"/calibration/{tipo}/{sensor}/restaurar"
        return self._op.iniciar(
            CLAVE_CAL_RESTAURAR, "POST", ruta, {"destino": destino},
            plazo_s=PLAZO_CALIBRACION_S,
            al_ok=lambda _r: self._tras_escribir_calibracion(tipo, sensor),
            al_rechazo=self._rechazo_simple(ruta),
            releer=lambda al_leido: self._releer_calibracion(tipo, sensor, al_leido),
            conciliar=lambda _leido: SIN_CONFIRMAR,
            bloquea_navegacion=True)

    def _tras_escribir_calibracion(self, tipo: str, sensor: str) -> None:
        """Tras el 200: relee (asíncrono) los valores vigentes del backend."""
        self._limpiar_mensaje()
        self._releer_calibracion(tipo, sensor, _ignorar)

    def _cal_en_curso(self) -> bool:
        return any(self._op.en_curso(k)
                   for k in (CLAVE_CAL_CARGAR, CLAVE_CAL_PUNTOS, CLAVE_CAL_RESTAURAR))

    @Property(bool, notify=mensajeChanged)
    def requiereConfirmacion(self) -> bool:
        return self._mensaje == "io.err_confirmacion"


qmlRegisterType(EntradasSalidasController, "Autoclave.Controllers", 1, 0,
                "EntradasSalidasController")
