# autoclave/backend/arranque/secuencia.py
#
# Secuencia de arranque por etapas (planeacion_arranque_y_modo_sin_bd.md §4-§5,
# planeacion_barra_arranque_real.md §7-§8). Corre en un hilo propio que
# server.iniciar_arranque() lanza cuando la UI lo pide (POST /arranque/iniciar,
# tanda 26, ARQ-D1; sin espera, en cuanto el puerto 8000 está enlazado); cada
# etapa publica su resultado en el RegistroArranque que lee GET /arranque.
#
# Tanda 26 (ARQ-D2/D3): el ControlLoop de la etapa 7 nace RETENIDO (todo
# apagado, máquina de estados quieta) y se libera al final, con las etapas
# terminadas sin fallo bloqueante y la interfaz lista (backend/arranque/retencion.py).
#
# Las etapas 1-6 solo leen archivos: un fallo bloqueante ahí detiene la
# secuencia sin abrir el enlace de E/S ni construir el ControlLoop (ninguna orden
# llega al módulo E/S). La etapa 7 construye el control (contexto operable) y
# luego espera las E/S: sin ellas no falla, reintenta con el código ARR_SIN_ES
# (D-E) y las etapas siguientes no corren hasta que conecten.
#
# Todo plazo usa time.monotonic().

import logging
import threading
import time

from autoclave.backend.arranque import retencion

logger = logging.getLogger(__name__)

# Códigos de etapa (docs/catalogo_alarmas.md, "Códigos de arranque")
ARR_PERFIL = "ARR_PERFIL"
ARR_RELOJ = "ARR_RELOJ"
ARR_CONFIG_ILEGIBLE = "ARR_CONFIG_ILEGIBLE"
ARR_CICLO_DEFECTO = "ARR_CICLO_DEFECTO"
ARR_CICLO_CORRUPTO = "ARR_CICLO_CORRUPTO"
CONFIGURACION_INVALIDA = "CONFIGURACION_INVALIDA"
ARR_CALIBRACION = "ARR_CALIBRACION"
ARR_SIN_BD = "ARR_SIN_BD"
ARR_SIN_ES = "ARR_SIN_ES"
ARR_ERROR_INTERNO = "ARR_ERROR_INTERNO"

ARR_SENSORES = "ARR_SENSORES"   # tanda 26 (ARQ-D8): etapa 8 degradada

PLAZO_ES_S = 15.0       # §4.7: a los 15 s sin E/S se anota ARR_SIN_ES (sigue reintentando)
INTENTOS_BD = 3         # §4.6
PAUSA_ES_S = 0.25
PLAZO_SENSORES_S = 10.0  # §4.8: 10 s tras la conexión (ARQ-D8, DECISIÓN SIN CONFIRMAR)
PAUSA_INTERFAZ_S = 0.1


class ErrorArranque(Exception):
    """Fallo bloqueante clasificado de una etapa."""
    def __init__(self, codigo: str, motivo: str = ""):
        super().__init__(motivo or codigo)
        self.codigo = codigo


def _correr_etapa(registro, clave: str, funcion) -> bool:
    """Ejecuta una etapa. `funcion` devuelve None (ok) o un código (degradado)
    y lanza ErrorArranque ante un fallo bloqueante. True si se puede seguir."""
    registro.iniciar(clave)
    try:
        degradado = funcion()
    except ErrorArranque as e:
        logger.error("Arranque: fallo en %s: %s", clave, e)
        registro.fallar(clave, e.codigo)
        return False
    except Exception:
        logger.exception("Arranque: error no previsto en %s", clave)
        registro.fallar(clave, ARR_ERROR_INTERNO)
        return False
    if degradado:
        registro.degradar(clave, degradado)
    else:
        registro.completar(clave)
    return True


def verificar_sensores(context, *, plazo_s: float = PLAZO_SENSORES_S,
                       detener: threading.Event | None = None, pausa_s: float = PAUSA_ES_S,
                       reloj=time.monotonic, dormir=time.sleep) -> str | None:
    """Etapa 8 (tanda 26, ARQ-D8, DECISIÓN SIN CONFIRMAR): lectura vigente en
    el Principal, la presión de cámara y la de chaqueta (si la hay) dentro de
    `plazo_s`. DEGRADABLE: sin ellas devuelve ARR_SENSORES (aviso en
    GET /arranque y en el log); las alarmas propias de cada sensor (SEN-01,
    SEN-06/07) las sigue dando PREPARACION al liberar. Nunca lanza: un error
    aquí degrada la etapa, no deja el equipo retenido para siempre."""
    detener = detener or threading.Event()
    t0 = reloj()
    faltan: list = []
    while True:
        try:
            faltan = list(context.sensores_arranque_sin_lectura())
        except Exception:
            logger.exception("Arranque: no se pudo verificar los sensores")
            return ARR_SENSORES
        if not faltan:
            return None
        if detener.is_set() or reloj() - t0 >= plazo_s:
            break
        dormir(pausa_s)
    logger.warning("Arranque: sensores sin lectura vigente en %.0f s: %s",
                   plazo_s, ", ".join(faltan))
    return ARR_SENSORES


def esperar_interfaz_y_liberar(context, registro, *, detener: threading.Event,
                               plazo_sin_interfaz_s: float = retencion.PLAZO_SIN_INTERFAZ_S,
                               pausa_s: float = PAUSA_INTERFAZ_S,
                               reloj=time.monotonic, dormir=time.sleep) -> bool:
    """ARQ-D3/D4: con las etapas del backend terminadas sin fallo bloqueante,
    espera POST /arranque/interfaz-lista SIN TOPE (todo apagado) y libera el
    control. A los `plazo_sin_interfaz_s` anota ARR_SIN_INTERFAZ (informativo).
    Sale sin liberar si el backend se detiene (`detener`, apagado). True si
    liberó."""
    liberado = getattr(context, "arranque_liberado", None)
    if liberado is None:
        return False
    clave = "preparando_interfaz"
    registro.iniciar_espera_interfaz(clave)
    t0 = reloj()
    avisado = False
    while not registro.interfaz_lista.is_set():
        if detener.is_set():
            logger.info("Arranque: backend detenido esperando a la interfaz (control sin liberar)")
            return False
        if not avisado and reloj() - t0 >= plazo_sin_interfaz_s:
            avisado = True
            registro.anotar_si_en_curso(clave, retencion.ARR_SIN_INTERFAZ)
            logger.warning("Arranque: la interfaz no avisó en %.0f s; el control sigue retenido "
                           "con todo apagado [%s]", plazo_sin_interfaz_s, retencion.ARR_SIN_INTERFAZ)
        dormir(pausa_s)
    if registro.fallo_bloqueante:      # defensa: (a) también al liberar
        logger.error("Arranque: fallo bloqueante; el control no se libera")
        return False
    liberado.set()
    logger.info("Arranque: control liberado (etapas terminadas e interfaz lista, %.2f s de espera)",
                reloj() - t0)
    return True


def ejecutar_arranque(context, registro, *, al_cancelar_prueba, al_operable,
                      detener: threading.Event | None = None,
                      plazo_es_s: float = PLAZO_ES_S, intentos_bd: int = INTENTOS_BD,
                      pausa_es_s: float = PAUSA_ES_S,
                      esperar_interfaz: bool | None = None,
                      plazo_sensores_s: float = PLAZO_SENSORES_S,
                      plazo_sin_interfaz_s: float = retencion.PLAZO_SIN_INTERFAZ_S,
                      reloj=time.monotonic, dormir=time.sleep) -> None:
    detener = detener or threading.Event()
    # ARQ-D7: sin espera (desarrollo/pruebas fuera del compilado) el control
    # nace liberado, como antes de la tanda 26
    esperar = retencion.espera_interfaz_activa() if esperar_interfaz is None else esperar_interfaz
    liberado = getattr(context, "arranque_liberado", None)
    if not esperar and liberado is not None:
        logger.warning("Arranque sin retención (%s=0): el control actúa en cuanto conecte",
                       retencion.VARIABLE_ESPERA)
        liberado.set()

    # 1. El reloj sigue siendo del lanzador; el backend verifica su perfil (D-3)
    if not _correr_etapa(registro, "verificando_instalacion", context.verificar_instalacion):
        return
    # 2. Del lanzador: si el backend corre, ya se pasó (D-3)
    _correr_etapa(registro, "liberando_procesos", lambda: None)
    # 3. Este hilo solo arranca con el puerto ya enlazado (backend/main.py)
    _correr_etapa(registro, "iniciando_servicios", lambda: None)

    for clave, funcion in (
        ("cargando_configuracion", context.cargar_configuracion),
        ("verificando_calibracion", context.verificar_calibracion),
        ("abriendo_base_datos", lambda: context.abrir_base_datos(intentos_bd)),
    ):
        if not _correr_etapa(registro, clave, funcion):
            return

    # 7. Construye y arranca el control (contexto operable); luego espera las E/S
    clave = "conectando_modulos_es"
    registro.iniciar(clave)
    try:
        context.construir_control(al_cancelar_prueba)
    except Exception:
        logger.exception("Arranque: error no previsto al construir el control")
        registro.fallar(clave, ARR_ERROR_INTERNO)
        return
    al_operable()
    t0 = reloj()
    while not context.es_conectada():
        if detener.is_set():
            return
        if reloj() - t0 >= plazo_es_s:
            registro.anotar(clave, ARR_SIN_ES)
        dormir(pausa_es_s)
    registro.completar(clave)

    # 8. Tanda 26 (ARQ-D8): lectura vigente de los canales críticos, degradable
    if not _correr_etapa(registro, "verificando_sensores", lambda: verificar_sensores(
            context, plazo_s=plazo_sensores_s, detener=detener, pausa_s=pausa_es_s,
            reloj=reloj, dormir=dormir)):
        return

    # 9. ARQ-D3: retenido hasta que la UI avise (sin espera: ya liberado)
    if esperar:
        esperar_interfaz_y_liberar(context, registro, detener=detener,
                                   plazo_sin_interfaz_s=plazo_sin_interfaz_s,
                                   reloj=reloj, dormir=dormir)
