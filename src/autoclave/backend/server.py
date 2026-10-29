# autoclave/backend/server.py
#
# Aplicación FastAPI del backend: `app`, ciclo de vida, compuerta de arranque,
# manejadores de excepción y registro de las rutas. Punto de entrada:
# autoclave.backend.server:app (backend/main.py).
#
# ORG-12 (tanda 15): las rutas viven en backend/rutas/<área>.py (un APIRouter
# por área) y lo compartido en backend/dependencias.py y backend/rutas/_comun.py;
# aquí solo se registran, en el orden de aparición que tenían en este archivo.

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autoclave.backend.arranque.secuencia import ejecutar_arranque
from autoclave.backend.arranque.sin_bd import BdNoDisponibleError
from autoclave.backend.dependencias import (RechazoApi, _cierre_ordenado_hecho,
    _contexto_operable, _detener_arranque, context, registro_arranque)
from autoclave.backend.rutas import (alarmas, apagado, ciclo, historial, mantenimiento,
    parametros_ciclo, programas, puertas, reportes, respaldo, sistema, usuarios)
from autoclave.backend.rutas import io as rutas_io
from autoclave.backend.rutas._comun import _reasignacion
from autoclave.backend.rutas.io import _iniciar_vigilancia_dueno_prueba, _prueba_cancelada_por_paro

# server_reasignacion.py lee estos nombres como `srv.<nombre>` en el momento de
# usarlos (srv = este módulo, por sys.modules): se importan aquí para conservar
# ese contrato sin tocar server_reasignacion.py (ORG-12).
from autoclave.backend.contrasenas import verificar_password  # noqa: F401
from autoclave.backend.dependencias import (CALIBRATION_PATH, _Rechazo,  # noqa: F401
    _auditar, _lock_archivos, _rechazar, guard_estado, intentos_login, requiere_rol)
from autoclave.backend.rutas.usuarios import _bloquear_por_cambio_clave  # noqa: F401
from autoclave.config import load_config  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _ciclo_de_vida(_app):
    yield
    # Apagado ordenado del backend (Ctrl+C, SIGTERM de uvicorn): detiene el
    # loop y apaga todas las salidas. Un TerminateProcess de Windows no pasa
    # por aquí; por eso la UI no termina el backend con un ciclo en curso
    # (revisión de la etapa 1 de autenticación, hallazgo B).
    _detener_arranque.set()
    if _cierre_ordenado_hecho.is_set():
        # R11: reiniciar_software ya corrió el cierre ordenado (lazo detenido,
        # ALL_OFF, puerto y base cerrados); otro stop() solo dejaría errores
        logger.info("Backend detenido tras el cierre ordenado del reinicio del software")
        return
    control_loop = getattr(context, "control_loop", None)
    if control_loop is None:
        # el arranque no llegó a construirlo: no hay loop ni orden al módulo E/S
        logger.info("Backend detenido antes de construir el control loop")
        return
    try:
        control_loop.stop()
        logger.info("Backend detenido: control loop parado y salidas apagadas")
    except Exception:
        logger.exception("Error al detener el control loop en el apagado del backend")


app = FastAPI(title="Autoclave Backend", lifespan=_ciclo_de_vida)
_compuerta_arranque = False
_hilo_arranque: threading.Thread | None = None
_RUTAS_SIN_COMPUERTA = frozenset({"/arranque", "/ui/activity"})


def preparar_arranque() -> None:
    """Activa la compuerta 503: llamar antes de abrir el puerto."""
    global _compuerta_arranque
    _compuerta_arranque = True


def iniciar_arranque() -> None:
    """Lanza la secuencia de etapas en su hilo. Llamar con el puerto ya
    enlazado (backend/main.py): si el enlace del puerto falla, nunca se abre el de E/S."""
    global _hilo_arranque
    if _hilo_arranque is not None:
        return
    _hilo_arranque = threading.Thread(
        target=ejecutar_arranque,
        args=(context, registro_arranque),
        kwargs={"al_cancelar_prueba": _prueba_cancelada_por_paro,
                "al_operable": _contexto_operable.set,
                "detener": _detener_arranque},
        name="arranque", daemon=True)
    _hilo_arranque.start()
    _iniciar_vigilancia_dueno_prueba()   # SAF-01 (revisión de B7)


@app.middleware("http")
async def _compuerta_de_arranque(request: Request, call_next):
    if (_compuerta_arranque and not _contexto_operable.is_set()
            and request.url.path not in _RUTAS_SIN_COMPUERTA):
        fallido = registro_arranque.fallo_bloqueante
        return JSONResponse(status_code=503, content={
            "detail": "Arranque fallido" if fallido else "Arranque en curso",
            "codigo": "arranque_fallido" if fallido else "arranque_en_curso",
        })
    return await call_next(request)


@app.exception_handler(BdNoDisponibleError)
def _responder_sin_bd(_request: Request, _e: BdNoDisponibleError):
    # PROVISIONAL hasta el modo sin BD (§7 de planeacion_arranque_y_modo_sin_bd.md)
    return JSONResponse(status_code=503, content={
        "detail": "Base de datos no disponible", "codigo": "sin_base_de_datos"})


@app.exception_handler(RechazoApi)
def _responder_rechazo(_request: Request, r: RechazoApi):
    return JSONResponse(status_code=r.status, headers=r.headers,
                        content={"detail": r.motivo, "codigo": r.codigo, **r.extra})


# Solo lo usa server_reasignacion.py (srv._estado_seguro_en_marcha).
def _estado_seguro_en_marcha() -> bool:
    """True si el protocolo de estado seguro está ACTUANDO sobre las válvulas.
    Pausado por un paro, esperando la confirmación del operador o sin datos de
    el módulo E/S no mueve nada: el equipo ya está quieto y se puede apagar (A1)."""
    es = context.control_loop.estado_seguro
    if getattr(es, "activo", False) is not True:
        return False
    if context.estado.get_flag("PARO_EMERGENCIA"):
        return False
    if getattr(es, "requiere_confirmacion", False) is True:
        return False
    return getattr(context.control_loop, "datos_vigentes", False) is True


# ORG-12: cada área entra en el orden de su primera ruta y, dentro de cada
# router, en el orden original. El orden global cambia (también el de `paths`
# en /openapi.json), pero ninguna URL coincide con dos rutas del mismo método,
# así que cada petición la atiende la misma ruta que antes;
# tests/test_t15_rutas_equivalentes.py lo comprueba.
app.include_router(sistema.router)
app.include_router(usuarios.router)
app.include_router(rutas_io.router)
app.include_router(ciclo.router)
app.include_router(mantenimiento.router)
app.include_router(reportes.router)
app.include_router(respaldo.router)
app.include_router(historial.router)
app.include_router(apagado.router)
app.include_router(alarmas.router)
app.include_router(puertas.router)
app.include_router(parametros_ciclo.router)
app.include_router(programas.router)

# ── R8 (tanda 8, D8-5.12): Opciones avanzadas = reasignación de E/S ───────────
# Sus rutas viven en server_reasignacion.py; se registran aquí, al final, con
# todo lo de este módulo ya definido (las usa). El módulo se carga en
# rutas/_comun.py (lo usan también io y respaldo).
_reasignacion.registrar(app)
