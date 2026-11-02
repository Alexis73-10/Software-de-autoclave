# ui_qml/sesion_backend.py
#
# Sesión de la ventana QML contra el backend (T-8; plan_t8_login_qml.md §3,
# planeacion_backend_autenticacion.md v7). Una por proceso, es decir, por
# ventana (decisión 8): `ventana()`.
#
# Capa pura (sin Qt): `llamar()` hace una petición con el transporte inyectable
# y la traduce a un Resultado con una causa estable: "ok", el `codigo` que
# envía el backend (credenciales_invalidas, usuario_bloqueado, sesion_invalida,
# clave_pendiente, ...), "backend_no_responde" o "error_generico" (código
# desconocido: se registra). La UI traduce la causa con es.json (clave_mensaje).
#
# Capa Qt:
#   - OperacionSesion: login y cambio de contraseña en un hilo de trabajo, una
#     sola operación en vuelo (`ocupado`) y plazo TOTAL de PLAZO_S medido en el
#     hilo de la GUI. Al vencer, la operación termina como backend_no_responde;
#     la respuesta que llegue después se descarta (con el login, además, se
#     invalida el token que traiga). El hilo nunca toca QML ni SessionManager.
#   - SesionVentana: abre y cierra la sesión en SessionManager, guarda el aviso
#     que debe mostrar el login (sesión inválida, bloqueo, clave que pudo
#     cambiar), envía las escrituras con el token y vigila la conexión mientras
#     una pantalla con token está en uso (§3.7). Cierra además la sesión tras
#     SESION_INACTIVIDAD_S sin toques ni teclas en ESTA ventana, en cualquier
#     estado del equipo (SAF-01: el standby no actúa en CICLO, FALLA ni
#     EMERGENCIA y toma la actividad de las dos pantallas).
#   - SesionVentana.enviar_async (AJUSTES 2026-11-02, paso 2 fase 1): la misma
#     escritura con token sin bloquear la GUI (_DespachadorEnvios); el
#     resultado y el trato de 401 / 429 llegan en el hilo de la GUI.
#
# El token nunca se registra: los logs llevan causa, ruta y código HTTP.

import logging
import math
import queue
import threading
import time
import weakref
from dataclasses import dataclass, field

import shiboken6
from PySide6.QtCore import Property, QEvent, QObject, QTimer, Signal, Slot

from autoclave.core.runtime.sesion_inactividad import (  # plazo único (B7)
    SESION_INACTIVIDAD_S, SESION_KEEPALIVE_S)
from autoclave.cliente.session_manager import SessionManager

# P1 (tanda 5): plazo de cada aviso previo al cierre de sesión. Si no alcanza,
# el modo prueba lo cierra el backend (vigilante de la sesión dueña, 2 s).
PLAZO_AVISO_CIERRE_S = 0.5

logger = logging.getLogger(__name__)

# Umbral (s) a partir del cual una llamada síncrona se registra como espera lenta.
_UMBRAL_ESPERA_LENTA_S = 0.1

PLAZO_S = 5.0                 # plazo total de login, logout y cambio de contraseña
PLAZO_SALIDA_S = 1.0          # logout al cerrar la aplicación: no retrasar el cierre
MAX_ENVIOS_EN_VUELO = 8       # enviar_async: peticiones simultáneas (las vencidas no cuentan)
_GUARDA_TARDIAS_S = 60.0      # cuánto se espera una respuesta tardía tras vencer el plazo
SIN_CONEXION_CIERRE_S = 15    # sin conexión continua con token en uso -> cerrar sesión
# SESION_INACTIVIDAD_S (importado arriba): sin actividad en esta ventana -> cerrar sesión (SAF-01).
# El backend caduca el token con ese plazo más dos avisos (B7); mientras el
# operador usa la ventana se le avisa cada KEEPALIVE_S (GET /auth/sesion).
KEEPALIVE_S = SESION_KEEPALIVE_S
_EVENTOS_ACTIVIDAD = {QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin,
                      QEvent.Type.KeyPress}

OK = "ok"
BACKEND_NO_RESPONDE = "backend_no_responde"
ERROR_GENERICO = "error_generico"

# Código del backend (o causa local) -> clave de es.json "seccion.clave"
_CLAVES = {
    "credenciales_invalidas": "sesion.credenciales_invalidas",
    "usuario_bloqueado": "sesion.usuario_bloqueado",
    "sesion_invalida": "sesion.sesion_invalida",
    "clave_pendiente": "sesion.clave_pendiente",
    "clave_actual_incorrecta": "sesion.clave_actual_incorrecta",
    "rol_sin_permiso": "sesion.rol_sin_permiso",
    "rol_no_creable": "usuarios.rol_no_creable",
    "usuario_existe": "usuarios.usuario_existe",
    # Opciones › Parámetros del ciclo y sensores (T12; opciones §5.4)
    "estado_no_permitido": "opciones.err_bloqueada",
    "VALOR_CAMBIO": "opciones.err_valor_cambio",
    "VALOR_INVALIDO": "opciones.err_valor_invalido",
    "PROGRAMA_NO_EDITABLE": "opciones.err_no_editable",
    "programa_de_fabrica": "opciones.err_no_editable",
    "BASE_OCUPADA": "opciones.err_base_ocupada",
    "f0_no_disponible": "opciones.err_f0",
    "apertura_automatica_no_disponible": "opciones.err_apertura_puertas_simples",
    "ASIGNACION_INVALIDA": "opciones.err_asignacion",
    "SENSOR_NO_DISPONIBLE": "opciones.err_sensor",
    "asignacion_desfasada": "opciones.err_valor_cambio",
    # D8-5.7 (tanda 8): reglas de carga líquida
    "MODO_NO_PERMITIDO_LIQUIDO": "opciones.err_modo_liquido",
    "COHERENCIA_LIQUIDO": "opciones.err_coherencia_liquido",
    # J12 (tanda 12): límites físicos de presión
    "LIMITE_PRESION_CAMARA": "opciones.err_limite_presion_camara",
    "LIMITE_CONSIGNA_CHAQUETA": "opciones.err_limite_consigna_chaqueta",
    "LIMITE_PRESION_CHAQUETA": "opciones.err_limite_presion_chaqueta",
    # Tanda 16: P1 (D-14.1) y PRG-01 (D-PRG-1)
    "COHERENCIA_RECUPERACION": "opciones.err_coherencia_recuperacion",
    "ROL_SONDA_NO_ACTIVA": "opciones.err_rol_sonda_no_activa",
    # Opciones › Entradas / Salidas (planeacion_opciones_entradas_salidas.md):
    # el texto del backend (`detail`) acompaña a estas claves en pantalla
    "modo_prueba_rechazado": "io.err_rechazado",
    "modo_prueba_inactivo": "io.err_rechazado",
    "modo_prueba_no_dueno": "io.err_rechazado",
    "modo_prueba_otra_sesion": "io.err_rechazado",
    "configuracion_invalida": "io.err_rechazado",
    "sin_conexion_modulo_es": "io.err_rechazado",
    "paro_emergencia": "io.err_rechazado",
    "apagado_en_curso": "io.err_rechazado",
    "fuente_vapor_no_instalada": "io.err_rechazado",
    # D8-3.19 (tanda 8): texto completo del catálogo, sin el del backend
    "aire_atmosferico_con_presion": "io.err_aire_con_presion",
    "aire_atmosferico_sin_presion": "io.err_aire_sin_presion",
    "aire_atmosferico_sin_referencia": "io.err_aire_sin_referencia",
    # S9 (tanda 9, revisión ★ SAF-01): salidas bloqueadas en modo prueba
    "salida_prueba_camara_no_segura": "io.err_puerta_camara_no_segura",
    "salida_prueba_estado_seguro": "io.err_salida_estado_seguro",
    # Tanda 17 (ESG-02): protecciones permanentes del modo prueba
    "salida_prueba_camara_presurizada": "io.err_puerta_camara_presurizada",
    "salida_prueba_puerta_abierta": "io.err_vapor_puerta_abierta",
    "sin_base_de_datos": "io.err_sin_base",
    "auditoria_no_disponible": "io.err_sin_base",
    "sin_calibracion_previa": "io.err_sin_previa",
    "CALIBRACION_REQUIERE_CONFIRMACION": "io.err_confirmacion",
    "CALIBRACION_IMPLAUSIBLE": "io.err_implausible",
    # TEC-ACC-05 (tanda 22): 403 de la reautenticación de Opciones avanzadas
    # (POST /io/assignment, /io/assignment/factory, /io/assignment/verify).
    # Es una contraseña mal escrita o vacía al confirmar, no una sesión
    # inválida: no cierra la sesión. Antes caían en "Respuesta no reconocida".
    "reautenticacion_fallida": "reasignacion.err_clave",
    "reautenticacion_requerida": "reasignacion.err_clave_requerida",
    BACKEND_NO_RESPONDE: "sesion.backend_no_responde",
    ERROR_GENERICO: "sesion.error_generico",
}
_CODIGOS_CONOCIDOS = frozenset(_CLAVES) - {BACKEND_NO_RESPONDE, ERROR_GENERICO} | {"validacion"}

# Tanda 24 (RSB-04): códigos propios de la reasignación de E/S
# (POST /io/assignment, /io/assignment/factory, /io/assignment/verify y GET
# /io/assignment). Se reconocen SOLO en esas rutas (vía equivalente a
# _CLAVES): fuera de ellas, códigos como "confirmacion_requerida" o
# "archivo_invalido" siguen siendo "error_generico" y ninguna otra pantalla
# cambia. Su texto lo pone ReasignacionController (_MENSAJES), no _CLAVES.
# tests/test_t24_codigos_reasignacion.py comprueba que cubren todo lo que
# esas rutas pueden emitir (RSB-05).
_CODIGOS_REASIGNACION = frozenset({
    "conflicto", "puerto_inexistente", "funcion_desconocida", "fabrica_invalida",
    "asignacion_invalida", "archivo_ilegible", "archivo_invalido", "sin_cambios",
    "confirmacion_requerida", "confirmacion_reforzada", "nombre_no_coincide",
    "puerto_sin_calibracion", "no_se_pudo_guardar", "reinicio_en_curso",
    "reinicio_pendiente", "no_pendiente", "sin_cambio_observado",
    "sin_prueba_de_salida", "sin_lectura", "error",
})
# Opciones › Usuarios (corrección tras revisión de la fase 1, B1): 409 propios
# de PUT /usuarios/{u}/activo y POST /operadores; solo en /usuarios y
# /operadores. Su texto lo pone UsuariosController (_MENSAJES).
_CODIGOS_USUARIOS = frozenset({
    "ultimo_ingeniero", "autodesactivacion", "cuenta_sistema", "operador_existe",
})
_CODIGOS_POR_RUTA = (("/io/assignment", _CODIGOS_REASIGNACION),
                     ("/usuarios", _CODIGOS_USUARIOS),
                     ("/operadores", _CODIGOS_USUARIOS))


def codigos_conocidos(ruta: str = "") -> frozenset:
    """Códigos que `interpretar` deja pasar en `ruta`: los globales y los
    propios de la ruta (RSB-04). La ruta se compara sin la consulta."""
    ruta = (ruta or "").split("?", 1)[0]
    extra = frozenset()
    for prefijo, codigos in _CODIGOS_POR_RUTA:
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            extra |= codigos
    return _CODIGOS_CONOCIDOS | extra


def clave_mensaje(causa: str) -> str:
    """Clave de es.json para una causa; las desconocidas, el mensaje genérico."""
    return _CLAVES.get(causa, _CLAVES[ERROR_GENERICO])


def formato_tiempo(segundos: float) -> str:
    """m:ss, redondeando hacia arriba (no muestra 0:00 mientras quede tiempo)."""
    s = max(0, math.ceil(segundos))
    return f"{s // 60}:{s % 60:02d}"


@dataclass(frozen=True)
class Resultado:
    causa: str
    # fuera del repr: el de un login correcto lleva el token (SAF-04)
    datos: dict = field(default_factory=dict, repr=False)
    estado_http: int | None = None

    @property
    def ok(self) -> bool:
        return self.causa == OK


# ── Capa pura ────────────────────────────────────────────────────────────────

def _url_backend() -> str:
    from autoclave.ui_qml.app import url_backend
    return url_backend()


def transporte_http(metodo: str, ruta: str, cuerpo: dict | None, token: str | None,
                    plazo: float, base: str | None = None):
    """Petición real al backend; devuelve (código HTTP, cuerpo JSON o {}).
    `base` la fija SesionVentana al crearse (hilo de la GUI); sin ella se lee
    la configuración aquí. El `timeout` de requests es por fase (conexión y
    cada lectura): el plazo total lo imponen OperacionSesion y cerrar_al_salir."""
    import requests
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.request(metodo, f"{base or _url_backend()}{ruta}", json=cuerpo,
                         headers=cabeceras, timeout=plazo)
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    return r.status_code, datos


def interpretar(estado_http: int, datos, ruta: str = "") -> Resultado:
    datos = datos if isinstance(datos, dict) else {}
    if 200 <= estado_http < 300:
        return Resultado(OK, datos, estado_http)
    codigo = datos.get("codigo")
    if isinstance(codigo, str) and codigo in codigos_conocidos(ruta):
        return Resultado(codigo, datos, estado_http)
    # 422 de FastAPI, código desconocido o cuerpo no JSON
    logger.error("Respuesta no reconocida del backend: HTTP %s en %s (código %r)",
                 estado_http, ruta, codigo)
    return Resultado(ERROR_GENERICO, {}, estado_http)


def llamar(transporte, metodo: str, ruta: str, cuerpo: dict | None = None,
           token: str | None = None, plazo: float = PLAZO_S) -> Resultado:
    try:
        estado_http, datos = transporte(metodo, ruta, cuerpo, token, plazo)
    except Exception as e:
        logger.warning("Backend sin respuesta en %s %s: %s", metodo, ruta, type(e).__name__)
        return Resultado(BACKEND_NO_RESPONDE)
    return interpretar(estado_http, datos, ruta)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="sesion-backend").start()


# ── Operación en hilo con plazo total ────────────────────────────────────────

class OperacionSesion(QObject):
    """Una operación a la vez. `iniciar(tarea, al_terminar, al_tardio, nombre)`:
    `tarea()` corre en el hilo de trabajo y devuelve un Resultado;
    `al_terminar(resultado)` corre en el hilo de la GUI, una sola vez, con el
    resultado o con backend_no_responde si vence el plazo; `al_tardio(resultado)`
    (GUI) recibe la respuesta que llegó después del plazo o de cancelar().

    El hilo de trabajo no toca Qt: deja (id, resultado) en una cola de Python
    que el hilo de la GUI vacía con un QTimer mientras haya operaciones
    pendientes. Emitir una señal desde el hilo sobre un QObject ya destruido
    (cierre de la aplicación, objeto recolectado) tumba el proceso; con la
    cola, una respuesta huérfana simplemente no se lee.

    Al vencer o cancelar se libera la UI aunque el hilo siga esperando la red:
    puede salir otra petición mientras la anterior termina (se acepta; el
    backend cuenta los intentos que le lleguen)."""
    ocupadoChanged = Signal()

    def __init__(self, parent=None, ejecutar=_en_hilo, plazo_s: float = PLAZO_S):
        super().__init__(parent)
        self._ejecutar = ejecutar
        self._plazo_s = plazo_s
        self._en_vuelo = None          # (id, nombre, al_terminar, al_tardio)
        self._vencidas = {}            # id -> al_tardio (vencidas o canceladas)
        self._siguiente = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._vencer)
        self._cola = queue.SimpleQueue()   # (id, resultado) desde el hilo de trabajo
        self._timer_cola = QTimer(self)
        self._timer_cola.setInterval(20)
        self._timer_cola.timeout.connect(self._drenar)

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._en_vuelo is not None

    def iniciar(self, tarea, al_terminar, al_tardio=None, nombre: str = "") -> bool:
        if self._en_vuelo is not None:
            return False
        self._siguiente += 1
        ident = self._siguiente
        self._en_vuelo = (ident, nombre, al_terminar, al_tardio)
        self.ocupadoChanged.emit()
        self._timer.start(int(self._plazo_s * 1000))

        def trabajo():
            try:
                resultado = tarea()
            except Exception:
                logger.exception("Operación de sesión fallida")
                resultado = Resultado(ERROR_GENERICO)
            cola.put((ident, resultado))   # sin Qt en el hilo de trabajo

        cola = self._cola
        self._ejecutar(trabajo)
        self._drenar()                     # ejecutor síncrono: ya está en la cola
        if self._pendientes():
            self._timer_cola.start()
        return True

    def _pendientes(self) -> bool:
        return self._en_vuelo is not None or bool(self._vencidas)

    def _drenar(self) -> None:
        while True:
            try:
                ident, resultado = self._cola.get_nowait()
            except queue.Empty:
                break
            self._al_responder(ident, resultado)
        if not self._pendientes():
            self._timer_cola.stop()

    def _liberar(self) -> tuple:
        ident, _, al_terminar, al_tardio = self._en_vuelo
        self._timer.stop()
        self._en_vuelo = None
        self.ocupadoChanged.emit()
        return ident, al_terminar, al_tardio

    def _apartar(self, ident: int, al_tardio) -> None:
        self._vencidas[ident] = al_tardio
        while len(self._vencidas) > 20:   # hilos que nunca volvieron
            self._vencidas.pop(next(iter(self._vencidas)))

    def _terminar(self, resultado: Resultado) -> None:
        _, al_terminar, _ = self._liberar()
        al_terminar(resultado)

    def _vencer(self) -> None:
        if self._en_vuelo is None:
            return
        self._apartar(self._en_vuelo[0], self._en_vuelo[3])
        logger.warning("Operación de sesión sin respuesta en %.1f s", self._plazo_s)
        self._terminar(Resultado(BACKEND_NO_RESPONDE))

    def cancelar(self, nombres=None) -> None:
        """Abandona la operación en vuelo (todas, o solo las de `nombres`) sin
        llamar a al_terminar: su respuesta, si llega, va a al_tardio. Para
        cuando se cierra la sesión o se destruye la pantalla que la pidió."""
        if self._en_vuelo is None or (nombres is not None and self._en_vuelo[1] not in nombres):
            return
        nombre = self._en_vuelo[1]
        ident, _, al_tardio = self._liberar()
        self._apartar(ident, al_tardio)
        self._timer_cola.start()           # para entregar la respuesta tardía
        logger.info("Operación de sesión cancelada: %s", nombre or "sin nombre")

    def _al_responder(self, ident: int, resultado) -> None:
        if self._en_vuelo is not None and self._en_vuelo[0] == ident:
            self._terminar(resultado)
            return
        al_tardio = self._vencidas.pop(ident, None)
        if al_tardio is not None:
            al_tardio(resultado)


# ── Envíos asíncronos (AJUSTES 2026-11-02, paso 2 fase 1) ────────────────────

def _referencia(dueno):
    """weakref al dueño (None si no hay); un objeto sin weakref se retiene."""
    if dueno is None:
        return None
    try:
        return weakref.ref(dueno)
    except TypeError:
        return lambda: dueno


def _dueno_vivo(ref) -> bool:
    if ref is None:
        return True
    dueno = ref()
    if dueno is None:
        return False
    try:
        return shiboken6.isValid(dueno) if isinstance(dueno, QObject) else True
    except Exception:
        return False


class _Envio:
    __slots__ = ("metodo", "ruta", "usuario", "gen", "al_terminar", "al_tardio",
                 "dueno", "dueno_id", "limite", "vencido", "cancelado")

    def __init__(self, metodo, ruta, usuario, gen, al_terminar, al_tardio, dueno, limite):
        self.metodo, self.ruta, self.usuario, self.gen = metodo, ruta, usuario, gen
        self.al_terminar, self.al_tardio = al_terminar, al_tardio
        self.dueno = _referencia(dueno)
        self.dueno_id = None if dueno is None else id(dueno)
        self.limite = limite
        self.vencido = False
        self.cancelado = False


class _DespachadorEnvios(QObject):
    """Peticiones con token sin bloquear la GUI (SesionVentana.enviar_async).

    El hilo de trabajo solo hace la petición y deja (id, Resultado) en una
    cola de Python; un QTimer de la GUI la vacía, vigila el plazo de cada
    envío (reloj monotónico) y entrega en el hilo de la GUI: primero el trato
    de sesión (401 / 429, una sola vez por generación de sesión), luego, si el
    dueño sigue vivo, `al_terminar`. Al vencer el plazo se entrega
    backend_no_responde y la respuesta que llegue después va a `al_tardio`
    (si lo hay y el dueño vive) o solo al log."""

    def __init__(self, sesion: "SesionVentana", ejecutar, reloj):
        super().__init__(sesion)
        self._sesion = sesion
        self._ejecutar = ejecutar
        self._reloj = reloj
        self._envios: dict[int, _Envio] = {}
        self._siguiente = 0
        self._cola = queue.SimpleQueue()
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._vaciar)

    def en_vuelo(self) -> int:
        return sum(1 for e in self._envios.values() if not e.vencido)

    def lanzar(self, tarea, envio: _Envio) -> bool:
        if self.en_vuelo() >= MAX_ENVIOS_EN_VUELO:
            logger.warning("Envío rechazado: %d peticiones en vuelo (%s %s)",
                           MAX_ENVIOS_EN_VUELO, envio.metodo, envio.ruta)
            return False
        self._siguiente += 1
        ident = self._siguiente
        self._envios[ident] = envio
        cola = self._cola

        def trabajo():                     # hilo de trabajo: sin Qt
            try:
                resultado = tarea()
            except Exception:
                logger.exception("Envío asíncrono fallido")
                resultado = Resultado(ERROR_GENERICO)
            cola.put((ident, resultado))

        self._ejecutar(trabajo)
        if not self._timer.isActive():
            self._timer.start()
        return True

    def cancelar(self, dueno_id: int) -> int:
        n = 0
        for envio in self._envios.values():
            if envio.dueno_id == dueno_id and not envio.cancelado:
                envio.cancelado = True
                n += 1
        if n:
            logger.info("Envíos cancelados por su dueño: %d", n)
        return n

    def _vaciar(self) -> None:
        while True:
            try:
                ident, resultado = self._cola.get_nowait()
            except queue.Empty:
                break
            envio = self._envios.pop(ident, None)
            if envio is None:
                continue
            if envio.vencido:
                self._tardio(envio, resultado)
            else:
                self._entregar(envio, resultado)
        ahora = self._reloj()
        for ident, envio in list(self._envios.items()):
            if not envio.vencido and ahora >= envio.limite:
                envio.vencido = True
                logger.warning("Envío sin respuesta en el plazo: %s %s", envio.metodo, envio.ruta)
                self._entregar(envio, Resultado(BACKEND_NO_RESPONDE))
            elif envio.vencido and ahora >= envio.limite + _GUARDA_TARDIAS_S:
                del self._envios[ident]    # hilo que nunca volvió
        if not self._envios:
            self._timer.stop()

    def _entregar(self, envio: _Envio, r: Resultado) -> None:
        if envio.gen != self._sesion._gen_sesion:
            # la sesión se cerró después de lanzar: un 200 es un hecho del
            # backend y se entrega tal cual; lo demás ya no vale (sin tratar
            # el rechazo: la sesión actual no es la del envío)
            if not r.ok:
                r = Resultado("sesion_invalida")
        else:
            self._sesion.tratar_rechazo_sesion(r, envio.metodo, envio.ruta, envio.usuario)
        if envio.cancelado or envio.al_terminar is None or not _dueno_vivo(envio.dueno):
            return
        try:
            envio.al_terminar(r)
        except Exception:
            logger.exception("Error al entregar %s %s", envio.metodo, envio.ruta)

    def _tardio(self, envio: _Envio, r: Resultado) -> None:
        logger.warning("Respuesta tardía de %s %s: %s", envio.metodo, envio.ruta, r.causa)
        if envio.cancelado or envio.al_tardio is None or not _dueno_vivo(envio.dueno):
            return
        if envio.gen != self._sesion._gen_sesion and not r.ok:
            r = Resultado("sesion_invalida")
        try:
            envio.al_tardio(r)
        except Exception:
            logger.exception("Error al entregar la respuesta tardía de %s %s",
                             envio.metodo, envio.ruta)


# ── Sesión de la ventana ─────────────────────────────────────────────────────

class SesionVentana(QObject):
    sesionChanged = Signal()
    ocupadoChanged = Signal()
    # 401 o 429 usuario_bloqueado en una escritura: la sesión ya se cerró; la
    # pantalla vuelve al login (que muestra el aviso guardado)
    sesionInvalida = Signal()
    conexionChanged = Signal()
    # 15 s sin conexión con token en uso; destino "login" (cambio obligatorio)
    # o "principal"
    cierrePorDesconexion = Signal(str)
    # SESION_INACTIVIDAD_S sin actividad en esta ventana: la sesión ya se cerró
    cierrePorInactividad = Signal()

    def __init__(self, parent=None, transporte=None, ejecutar=_en_hilo,
                 plazo_s: float = PLAZO_S, reloj=time.monotonic,
                 cierre_s: float = SIN_CONEXION_CIERRE_S, intervalo_ms: int = 250,
                 inactividad_s: float = SESION_INACTIVIDAD_S):
        super().__init__(parent)
        if transporte is None:
            base = _url_backend()   # se resuelve aquí, en el hilo de la GUI (TMG-09)
            transporte = lambda *a: transporte_http(*a, base=base)   # noqa: E731
        self._transporte = transporte
        self._ejecutar = ejecutar
        self._plazo_s = plazo_s
        self._reloj = reloj
        self._cierre_s = cierre_s
        self.operacion = OperacionSesion(self, ejecutar=ejecutar, plazo_s=plazo_s)
        self.operacion.ocupadoChanged.connect(self.ocupadoChanged)
        # la validación al reconectar no compite con login ni cambio de clave
        self._validacion = OperacionSesion(self, ejecutar=ejecutar, plazo_s=plazo_s)
        # enviar_async: generación de la sesión (sube en cada cerrar_local) y
        # despachador que entrega en el hilo de la GUI
        self._gen_sesion = 0
        self._envios = _DespachadorEnvios(self, ejecutar, reloj)
        self._aviso = None                # (clave es.json, segundos | None) para el login
        self._sin_conexion_desde = None    # reloj() del primer sondeo fallido
        # logout que no llegó: se reintenta al reconectar. Lo llena también el
        # hilo de trabajo (sin Qt), por eso va con candado propio.
        self._tokens_por_invalidar = []
        self._lock_tokens = threading.Lock()
        # P1 (tanda 5): avisos que corren ANTES del logout, con el token aún
        # válido (p. ej. salir del modo prueba de Entradas / Salidas)
        self._antes_de_cerrar = []
        self._conectado = True             # último estado visto por vigilar()
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self._revisar_conexion)
        self._inactividad_s = inactividad_s
        self._ultima_actividad = reloj()
        self._ultimo_keepalive = float("-inf")
        # Hay una pantalla con token a la vista (vigilar()). Fuera de ellas los
        # toques no prolongan la sesión (revisión de U2, tanda 2: Atrás/Home ya
        # no la cierran y la preciclo la usa cualquiera). True hasta el primer
        # vigilar(): comportamiento previo para quien no lo llame.
        self._en_uso = True
        self._timer_inactividad = QTimer(self)
        self._timer_inactividad.setInterval(intervalo_ms)
        self._timer_inactividad.timeout.connect(self._revisar_inactividad)   # solo con sesión

    # ── estado ───────────────────────────────────────────────────────

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self.operacion.ocupado

    @Property(bool, notify=sesionChanged)
    def sesionActiva(self) -> bool:
        return SessionManager.is_authenticated()

    @Property(bool, notify=sesionChanged)
    def cambioClavePendiente(self) -> bool:
        return SessionManager.debe_cambiar_clave()

    def tomar_aviso(self):
        """Aviso pendiente para el login (clave, segundos | None[, usuario
        bloqueado]); lo consume."""
        aviso, self._aviso = self._aviso, None
        return aviso

    def _peticion(self, metodo: str, ruta: str, cuerpo: dict | None = None,
                  token: str | None = None, plazo: float | None = None):
        """Tarea para el hilo de trabajo SIN referencias a este QObject: si el
        hilo soltara la última referencia, Python lo destruiría (con sus
        QTimer) fuera del hilo de la GUI y el proceso caería."""
        transporte = self._transporte
        plazo = self._plazo_s if plazo is None else plazo
        return lambda: llamar(transporte, metodo, ruta, cuerpo, token, plazo=plazo)

    # ── login, cambio de contraseña ──────────────────────────────────

    def iniciar_sesion(self, usuario: str, clave: str, al_terminar) -> bool:
        if self.operacion.ocupado:
            return False
        if SessionManager.is_authenticated():
            self.cerrar_sesion()   # un intento nuevo cierra la sesión previa de esta ventana
        cuerpo = {"usuario": usuario, "clave": clave}

        tarea = self._peticion("POST", "/auth/login", cuerpo)

        def terminar(r: Resultado):
            if r.ok:
                self._ultima_actividad = self._reloj()
                self._timer_inactividad.start()
                SessionManager.login(r.datos, token=r.datos.get("token"))
                self.sesionChanged.emit()
                logger.info("Inicio de sesión QML: %s (rol %s)", r.datos.get("usuario"),
                            r.datos.get("rol"))
                self._reintentar_logouts()
            elif r.causa == "usuario_bloqueado":
                logger.warning("Inicio de sesión QML rechazado para '%s': %s", usuario, r.causa)
            else:
                # sin el usuario tecleado: a veces es la contraseña escrita en ese campo (SAF-06)
                logger.warning("Inicio de sesión QML rechazado: %s", r.causa)
            al_terminar(r)

        def tardio(r: Resultado):
            token = r.datos.get("token") if r.ok else None
            if token:
                logger.warning("Login respondido tras el plazo o cancelado: se invalida ese token")
                self._logout_en_segundo_plano(token)

        return self.operacion.iniciar(tarea, terminar, tardio, nombre="login")

    def cambiar_clave(self, actual: str, nueva: str, confirmacion: str, al_terminar) -> bool:
        token = SessionManager.token()
        usuario = (SessionManager.current_user() or {}).get("usuario", "")
        cuerpo = {"clave_actual": actual, "clave_nueva": nueva, "confirmacion": confirmacion}

        tarea = self._peticion("POST", "/auth/change_password", cuerpo, token)

        def terminar(r: Resultado):
            if r.ok:
                SessionManager.clave_cambiada()
                self.sesionChanged.emit()
            elif r.causa == "usuario_bloqueado":
                # el backend ya invalidó el token (H-T8-01)
                self.cerrar_local(("sesion.usuario_bloqueado",
                                   r.datos.get("segundos_restantes"), usuario))
            elif r.causa == BACKEND_NO_RESPONDE:
                # sin reintento: pudo haberse cambiado (condición 6)
                self.cerrar_sesion(aviso=("sesion.clave_pudo_cambiar", None))
            elif r.causa == "sesion_invalida":
                self.cerrar_local(("sesion.sesion_invalida", None))
            al_terminar(r)

        def tardio(r: Resultado):
            # sin reintento ni cambio de estado: solo deja constancia
            logger.warning("Cambio de contraseña respondido tras el plazo o cancelado: %s",
                           r.causa)

        return self.operacion.iniciar(tarea, terminar, tardio, nombre="cambio_clave")

    # ── cierre de sesión ─────────────────────────────────────────────

    def cerrar_local(self, aviso=None) -> None:
        """Cierra la sesión solo en esta ventana, sin red (token ya inválido).
        Cancela además un login o cambio de clave en vuelo (TMG-01): si el
        login responde después, su token se invalida en vez de abrir sesión."""
        if aviso is not None:
            self._aviso = aviso
        # los envíos asíncronos de antes de este cierre entregan sesion_invalida
        # sin volver a cerrar la sesión
        self._gen_sesion += 1
        self.operacion.cancelar()
        self._timer_inactividad.stop()
        # P1 (revisión SAF-01): sin token válido ya no se puede salir del modo
        # prueba desde aquí; lo cierra el backend (plazo de inactividad o
        # vigilante de la sesión dueña). Un aviso viejo no debe dispararse
        # luego con la sesión de otro usuario.
        if self._antes_de_cerrar:
            logger.warning("Sesión cerrada sin token válido: el modo prueba lo cierra el backend")
            self._antes_de_cerrar.clear()
        if SessionManager.is_authenticated():
            SessionManager.logout()
            logger.info("Sesión cerrada en esta ventana")
            self.sesionChanged.emit()

    def al_cerrar_sesion(self, aviso) -> None:
        """Registra `aviso()` para que corra antes del próximo logout (P1)."""
        if aviso not in self._antes_de_cerrar:
            self._antes_de_cerrar.append(aviso)

    def quitar_al_cerrar_sesion(self, aviso) -> None:
        if aviso in self._antes_de_cerrar:
            self._antes_de_cerrar.remove(aviso)

    def _avisar_antes_de_cerrar(self) -> None:
        """Un aviso que falla no impide el cierre de sesión."""
        for aviso in list(self._antes_de_cerrar):
            try:
                aviso()
            except Exception:
                logger.exception("Aviso previo al cierre de sesión falló")

    def cerrar_sesion(self, aviso=None) -> None:
        """Cierra la sesión local de inmediato y pide /auth/logout en segundo
        plano; si el backend no responde, solo queda en el log local."""
        if SessionManager.token():
            self._avisar_antes_de_cerrar()
        token = SessionManager.token()
        self.cerrar_local(aviso)
        if token:
            self._logout_en_segundo_plano(token)

    def _logout_en_segundo_plano(self, token: str) -> None:
        pendientes, candado = self._tokens_por_invalidar, self._lock_tokens
        peticion = self._peticion("POST", "/auth/logout", None, token)

        def tarea():
            r = peticion()
            if r.ok or r.causa == "sesion_invalida":
                return
            logger.warning("Cierre de sesión sin confirmar del backend: %s", r.causa)
            if r.causa == BACKEND_NO_RESPONDE:
                with candado:
                    pendientes.append(token)   # se reintenta al reconectar (TMG-04)
        self._ejecutar(tarea)

    def _tomar_pendientes(self) -> list:
        with self._lock_tokens:
            tokens = list(self._tokens_por_invalidar)
            self._tokens_por_invalidar.clear()
        return tokens

    def _reintentar_logouts(self) -> None:
        for token in self._tomar_pendientes():
            self._logout_en_segundo_plano(token)

    def cerrar_al_salir(self, plazo_s: float = PLAZO_SALIDA_S) -> None:
        """Al cerrar la aplicación: logout de la sesión y de los tokens
        pendientes, en hilos, esperando como mucho `plazo_s` en total."""
        if SessionManager.token():
            self._avisar_antes_de_cerrar()
        self.operacion.cancelar()
        self._timer_inactividad.stop()
        tokens = self._tomar_pendientes()
        if SessionManager.token():
            tokens.append(SessionManager.token())
        SessionManager.logout()
        confirmados = []

        transporte = self._transporte

        def logout(token):
            r = llamar(transporte, "POST", "/auth/logout", None, token, plazo=plazo_s)
            if r.ok or r.causa == "sesion_invalida":
                confirmados.append(token)

        hilos = [threading.Thread(target=logout, args=(t,), daemon=True, name="logout-salida")
                 for t in tokens]
        for h in hilos:
            h.start()
        limite = time.monotonic() + plazo_s
        for h in hilos:
            h.join(max(0.0, limite - time.monotonic()))
        sin_confirmar = len(tokens) - len(confirmados)
        if sin_confirmar:
            logger.warning("Cierre de sesión al salir sin confirmar del backend (%d token/s)",
                           sin_confirmar)

    def descartar_token(self) -> None:
        """Cambio obligatorio sin conexión (R4-2): se descarta el token sin
        enviar nada; queda registro en el log local."""
        if SessionManager.is_authenticated():
            logger.warning("Token descartado sin conexión durante el cambio obligatorio de contraseña")
        self.cerrar_local()

    # ── escrituras con token ─────────────────────────────────────────

    def enviar(self, metodo: str, ruta: str, cuerpo: dict | None = None) -> Resultado:
        """Escritura síncrona con el token de la ventana (puentes que escriben).
        Sin conexión, se rechaza sin salir a la red. Un 401 cierra la sesión;
        un 429 usuario_bloqueado también, de inmediato y con el aviso de
        bloqueo (TEC-ACC-05): el backend ya invalidó el token (reautenticación
        fallida que bloquea, como H-T8-01 en el cambio de contraseña)."""
        if self.sinConexion:
            return Resultado(BACKEND_NO_RESPONDE)
        token = SessionManager.token()
        if not token:
            return Resultado("sesion_invalida")
        usuario = (SessionManager.current_user() or {}).get("usuario", "")
        r = self._llamar_con_plazo(metodo, ruta, cuerpo, token)
        self.tratar_rechazo_sesion(r, metodo, ruta, usuario)
        return r

    def enviar_async(self, metodo: str, ruta: str, cuerpo: dict | None = None,
                     al_terminar=None, *, dueno=None, al_tardio=None,
                     plazo_s: float | None = None) -> bool:
        """Como `enviar`, sin bloquear la GUI. Solo desde el hilo de la GUI.
        `al_terminar(Resultado)` corre siempre en el hilo de la GUI y nunca
        dentro de esta llamada: sin conexión (backend_no_responde), sin token
        (sesion_invalida, sin cerrar nada, como `enviar`) o por encima de
        MAX_ENVIOS_EN_VUELO (error_generico) se entrega en diferido. Con
        `dueno`, nada se entrega si ese objeto se destruyó o si se llamó a
        `cancelar_envios(dueno)`. Plazo total PLAZO_S (o `plazo_s`); la
        respuesta que llega después va a `al_tardio` o solo al log.
        Devuelve True si la petición salió."""
        ref = _referencia(dueno)
        if self.sinConexion:
            self._diferir(al_terminar, Resultado(BACKEND_NO_RESPONDE), ref)
            return False
        token = SessionManager.token()
        if not token:
            self._diferir(al_terminar, Resultado("sesion_invalida"), ref)
            return False
        usuario = (SessionManager.current_user() or {}).get("usuario", "")
        plazo = self._plazo_s if plazo_s is None else plazo_s
        tarea = self._peticion(metodo, ruta, cuerpo, token, plazo)
        envio = _Envio(metodo, ruta, usuario, self._gen_sesion, al_terminar, al_tardio,
                       dueno, self._reloj() + plazo)
        if not self._envios.lanzar(tarea, envio):
            self._diferir(al_terminar, Resultado(ERROR_GENERICO), ref)
            return False
        return True

    def cancelar_envios(self, dueno) -> int:
        """Los envíos en vuelo de `dueno` (objeto o su id()) ya no entregan
        nada; su respuesta solo va al log."""
        return self._envios.cancelar(dueno if isinstance(dueno, int) else id(dueno))

    def _diferir(self, al_terminar, r: Resultado, ref) -> None:
        if al_terminar is None:
            return

        def entregar():
            if _dueno_vivo(ref):
                al_terminar(r)
        # con este objeto como contexto, Qt lo cancela si se destruye antes
        QTimer.singleShot(0, self, entregar)

    def tratar_rechazo_sesion(self, r: Resultado, metodo: str, ruta: str,
                              usuario: str = "") -> None:
        """Tratamiento de `enviar` ante 401 o 429 usuario_bloqueado: cierra la
        sesión local y avisa. Solo en el hilo de la GUI; lo usan también los
        sondeos que hacen la petición en un hilo de trabajo y entregan el
        resultado a la GUI (AJUSTES 2026-11-02)."""
        if r.causa not in ("sesion_invalida", "usuario_bloqueado"):
            return
        if r.causa == "usuario_bloqueado":
            logger.warning("Usuario bloqueado en %s %s: sesión cerrada en esta ventana",
                           metodo, ruta)
            datos = r.datos if isinstance(r.datos, dict) else {}
            self.cerrar_local(("sesion.usuario_bloqueado",
                               datos.get("segundos_restantes"), usuario))
        else:
            self.cerrar_local(("sesion.sesion_invalida", None))
        # en diferido: la pantalla que llamó aún espera este valor de retorno;
        # con este objeto como contexto, Qt lo cancela si se destruye antes
        QTimer.singleShot(0, self, self.sesionInvalida.emit)

    def enviar_al_cerrar(self, metodo: str, ruta: str, cuerpo: dict | None = None) -> Resultado:
        """Escritura de un aviso previo al cierre de sesión (P1, revisión
        TMG-01/04): plazo corto (PLAZO_AVISO_CIERRE_S) para no retrasar el
        cierre y, ante un 401, sin cerrar la sesión ni navegar (ya se cierra)."""
        if self.sinConexion:
            return Resultado(BACKEND_NO_RESPONDE)
        token = SessionManager.token()
        if not token:
            return Resultado("sesion_invalida")
        return self._llamar_con_plazo(metodo, ruta, cuerpo, token, plazo_s=PLAZO_AVISO_CIERRE_S)

    def _llamar_con_plazo(self, metodo, ruta, cuerpo, token, plazo_s=None) -> Resultado:
        """Llamada síncrona con plazo TOTAL (SAF-05): la petición va en un
        hilo y se la espera como mucho el plazo; si no responde, se abandona."""
        resultado = []
        peticion = self._peticion(metodo, ruta, cuerpo, token)
        hilo = threading.Thread(daemon=True, name="sesion-escritura",
                                target=lambda: resultado.append(peticion()))
        plazo_s = self._plazo_s if plazo_s is None else plazo_s
        t0 = time.monotonic()
        hilo.start()
        hilo.join(plazo_s)
        espera_s = time.monotonic() - t0
        if (espera_s > _UMBRAL_ESPERA_LENTA_S
                and threading.current_thread() is threading.main_thread()):
            # Diagnóstico de lag: esta espera congela la interfaz entera (en
            # otro hilo no afecta a la GUI y no se registra).
            logger.warning("Espera lenta en la GUI: %.0f ms en %s %s",
                           espera_s * 1000, metodo, ruta)
        if not resultado:
            logger.warning("Escritura sin respuesta en %.1f s: %s %s", plazo_s, metodo, ruta)
            return Resultado(BACKEND_NO_RESPONDE)
        return resultado[0]

    # ── inactividad de la sesión (SAF-01) ────────────────────────────

    @Slot()
    def registrarActividad(self) -> None:
        """Toque o tecla en esta ventana; solo cuenta con una pantalla con
        token a la vista (OPCIONES, Nuevo usuario, Cambio de clave)."""
        if self._en_uso:
            self._ultima_actividad = self._reloj()
            self._renovar_en_servidor(self._ultima_actividad)

    def _renovar_en_servidor(self, ahora: float) -> None:
        """B7: el token del backend caduca tras SESION_INACTIVIDAD_S sin
        peticiones autenticadas; con la ventana en uso se renueva cada
        KEEPALIVE_S con GET /auth/sesion (un 401 cierra la sesión, como al
        reconectar)."""
        if not SessionManager.token() or ahora - self._ultimo_keepalive < KEEPALIVE_S:
            return
        self._ultimo_keepalive = ahora
        self._validar_sesion()

    def eventFilter(self, obj, evento) -> bool:
        if evento.type() in _EVENTOS_ACTIVIDAD:
            self.registrarActividad()
        return False   # nunca consume el evento

    def _revisar_inactividad(self) -> None:
        if not SessionManager.is_authenticated():
            return
        if self._reloj() - self._ultima_actividad < self._inactividad_s:
            return
        logger.warning("Sesión cerrada tras %s s sin actividad en esta ventana",
                       self._inactividad_s)
        self.cerrar_sesion(aviso=("sesion.sesion_expirada", None))
        self.cierrePorInactividad.emit()

    # ── vigilancia de la conexión (§3.7) ─────────────────────────────

    @Property(bool, notify=conexionChanged)
    def sinConexion(self) -> bool:
        return self._sin_conexion_desde is not None

    @Property(str, notify=conexionChanged)
    def tiempoParaCierre(self) -> str:
        if self._sin_conexion_desde is None:
            return ""
        return formato_tiempo(self._cierre_s - (self._reloj() - self._sin_conexion_desde))

    @Slot(bool, bool)
    def vigilar(self, conectado: bool, en_uso: bool) -> None:
        """Lo llama la ventana cuando cambia la conexión o la pantalla.
        `en_uso`: hay una pantalla con token a la vista (OPCIONES, Nuevo
        usuario, Cambio de clave)."""
        reconecta = conectado and not self._conectado
        self._conectado = conectado
        entra = bool(en_uso) and not self._en_uso
        self._en_uso = bool(en_uso)
        if entra:
            self._ultima_actividad = self._reloj()   # llegó a una pantalla con sesión
        if conectado:
            self._reintentar_logouts()
            if self._sin_conexion_desde is not None:
                self._fijar_sin_conexion(None)
            if reconecta:
                # en toda reconexión con sesión, aunque no hubiera pantalla con
                # token a la vista: el backend pudo reiniciarse (SAF-02)
                self._validar_sesion()
            return
        if not en_uso or not SessionManager.is_authenticated():
            self._fijar_sin_conexion(None)
            return
        if self._sin_conexion_desde is None:
            self._fijar_sin_conexion(self._reloj())

    def _fijar_sin_conexion(self, desde) -> None:
        if (desde is None) != (self._sin_conexion_desde is None):
            self._sin_conexion_desde = desde
            if desde is None:
                self._timer.stop()
            else:
                self._timer.start()
            self.conexionChanged.emit()

    def _revisar_conexion(self) -> None:
        if self._sin_conexion_desde is None:
            return
        if self._reloj() - self._sin_conexion_desde < self._cierre_s:
            self.conexionChanged.emit()   # cuenta regresiva
            return
        self._fijar_sin_conexion(None)
        if SessionManager.debe_cambiar_clave():
            self.descartar_token()
            self.cierrePorDesconexion.emit("login")
        else:
            if SessionManager.token():
                with self._lock_tokens:
                    self._tokens_por_invalidar.append(SessionManager.token())
            logger.warning("Sesión cerrada tras %s s sin conexión con el equipo", self._cierre_s)
            self.cerrar_local()
            self.cierrePorDesconexion.emit("principal")

    def _validar_sesion(self) -> None:
        """Una sola vez al reconectar: GET /auth/sesion. 401 cierra la sesión."""
        token = SessionManager.token()
        if not token:
            return

        tarea = self._peticion("GET", "/auth/sesion", None, token)

        def terminar(r: Resultado):
            if r.causa == "sesion_invalida" and SessionManager.token() == token:
                self.cerrar_local(("sesion.sesion_invalida", None))
                self.sesionInvalida.emit()

        if not self._validacion.iniciar(tarea, terminar, nombre="validacion"):
            logger.warning("Validación de la sesión omitida: otra validación en curso")


_ventana: SesionVentana | None = None


def ventana() -> SesionVentana:
    """Sesión de esta ventana (una por proceso); se crea al primer uso."""
    global _ventana
    if _ventana is None:
        _ventana = SesionVentana()
    return _ventana


def enviar_async(sesion, metodo: str, ruta: str, cuerpo: dict | None, al_terminar,
                 dueno=None, al_tardio=None) -> bool:
    """Envío asíncrono para los controladores. Con una sesión que no tiene
    `enviar_async` (dobles de prueba que solo tienen `enviar`) se llama a
    `enviar` y se entrega el resultado en el acto. Se mira el tipo y no la
    instancia para que un MagicMock no pase por asíncrono. `al_tardio` solo
    se pasa si se pidió (dobles con la firma anterior siguen valiendo)."""
    if callable(getattr(type(sesion), "enviar_async", None)):
        if al_tardio is None:
            return sesion.enviar_async(metodo, ruta, cuerpo, al_terminar, dueno=dueno)
        return sesion.enviar_async(metodo, ruta, cuerpo, al_terminar, dueno=dueno,
                                   al_tardio=al_tardio)
    al_terminar(sesion.enviar(metodo, ruta, cuerpo))
    return True


def cancelar_envios(sesion, dueno) -> None:
    """`cancelar_envios` de la sesión si la tiene (sin sesión, la del
    proceso si ya existe; nunca la crea)."""
    sesion = sesion if sesion is not None else _ventana
    if callable(getattr(type(sesion), "cancelar_envios", None)):
        sesion.cancelar_envios(dueno)


def instalar(sesion: SesionVentana | None) -> None:
    """Fija la sesión del proceso (app.py y pruebas); None la reinicia."""
    global _ventana
    _ventana = sesion
