# autoclave/backend/arranque/secuencia.py
#
# Secuencia de arranque por etapas (planeacion_arranque_y_modo_sin_bd.md §4-§5,
# planeacion_barra_arranque_real.md §7-§8). Corre en un hilo propio que
# server.iniciar_arranque() lanza cuando el puerto 8000 ya está enlazado; cada
# etapa publica su resultado en el RegistroArranque que lee GET /arranque.
#
# Las etapas 1-6 solo leen archivos: un fallo bloqueante ahí detiene la
# secuencia sin abrir el enlace de E/S ni construir el ControlLoop (ninguna orden
# llega a la tarjeta). La etapa 7 construye el control (contexto operable) y
# luego espera las E/S: sin ellas no falla, reintenta con el código ARR_SIN_ES
# (D-E) y las etapas siguientes no corren hasta que conecten.
#
# Todo plazo usa time.monotonic().

import logging
import threading
import time

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

PLAZO_ES_S = 15.0       # §4.7: a los 15 s sin E/S se anota ARR_SIN_ES (sigue reintentando)
INTENTOS_BD = 3         # §4.6
PAUSA_ES_S = 0.25


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


def ejecutar_arranque(context, registro, *, al_cancelar_prueba, al_operable,
                      detener: threading.Event | None = None,
                      plazo_es_s: float = PLAZO_ES_S, intentos_bd: int = INTENTOS_BD,
                      pausa_es_s: float = PAUSA_ES_S,
                      reloj=time.monotonic, dormir=time.sleep) -> None:
    detener = detener or threading.Event()

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

    # 8. PROVISIONAL (D-6): la verificación de sensores (§6) va en otro paso
    def _sensores():
        logger.warning("Arranque: verificación de sensores (§6) pendiente; etapa marcada ok")

    _correr_etapa(registro, "verificando_sensores", _sensores)
