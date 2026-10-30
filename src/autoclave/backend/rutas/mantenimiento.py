# autoclave/backend/rutas/mantenimiento.py
#
# Mantenimiento y calibración atmosférica (/maintenance).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
import threading
from fastapi import Depends
from pydantic import BaseModel
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.config import load_config
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (CALIBRATION_PATH, RechazoApi, _auditar,
    _log_desarrollo, _rechazar, context, requiere_rol)
from autoclave.backend.rutas._comun import _encolar_en_impresora, _meta_equipo

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


# ── Mantenimiento (M1, tanda 3) ─────────────────────────────────────────────
# Solo informa: nunca bloquea ni interviene en un ciclo. La lectura es abierta
# (la ve el Menú Principal sin sesión); configurar y registrar exigen técnico o
# ingeniero y quedan en la bitácora.

class _MantenimientoConfigBody(BaseModel):
    intervalo_dias: int
    intervalo_ciclos: int


class _MantenimientoRegistroBody(BaseModel):
    tipo: str
    observaciones: str = ""


def _rechazo_mantenimiento(e, entidad: str, sesion) -> None:
    estado = 422 if e.codigo == "validacion" else 409
    _rechazar(estado, e.codigo, e.motivo, entidad, sesion)


@router.get("/maintenance")
def get_maintenance():
    """Próximo vencimiento, último mantenimiento, ciclos restantes y los
    intervalos configurados (por defecto 365 días y 1000 ciclos)."""
    return context.mantenimiento.resumen()


# MNT-04 (D8-3.25, tanda 8): el admin también consulta el historial (D-9 de
# planeacion_mantenimiento.md); registrar y configurar siguen siendo de técnico
# o ingeniero.
@router.get("/maintenance/records")
def get_maintenance_records(limite: int = 50,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO,
                                                                  ROL_ADMIN))):
    return {"registros": context.mantenimiento.historial(max(1, min(limite, 500)))}


@router.put("/maintenance/config")
def put_maintenance_config(body: _MantenimientoConfigBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime.servicio_mantenimiento import ErrorMantenimiento
    entidad = "/maintenance/config"
    anterior = context.mantenimiento.configuracion()
    try:
        nueva = context.mantenimiento.guardar_configuracion(body.intervalo_dias,
                                                            body.intervalo_ciclos)
    except ErrorMantenimiento as e:
        _rechazo_mantenimiento(e, entidad, sesion)
    _auditar("mantenimiento_configurado", sesion, entidad=entidad,
             valor_anterior=anterior, valor_nuevo=nueva)
    context.mantenimiento.evaluar_alarma()
    return {"ok": True, "configuracion": nueva}


@router.post("/maintenance/records")
def post_maintenance_record(body: _MantenimientoRegistroBody,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """"Registrar mantenimiento realizado": desde ese momento la base del
    cálculo pasa a ser hoy y el contador de ciclos actual."""
    from autoclave.core.runtime.servicio_mantenimiento import ErrorMantenimiento
    entidad = "/maintenance/records"
    try:
        registro = context.mantenimiento.registrar(sesion.usuario, body.tipo, body.observaciones)
    except ErrorMantenimiento as e:
        _rechazo_mantenimiento(e, entidad, sesion)
    _auditar("mantenimiento_registrado", sesion, entidad=entidad, valor_nuevo=registro,
             detalle={"observaciones": body.observaciones[:200]})
    return {"ok": True, "registro": registro}


# ── Calibración atmosférica e impresiones de Mantenimiento (O2f, tanda 6) ──
# planeacion_opciones.md v4 §5 y planeacion_backend_parametros.md §8. Técnico e
# ingeniero. La medición corre en su hilo (core/runtime/calibracion_atm.py) y
# solo lee; la referencia se escribe con la función interna del ConfigManager
# (permitir_solo_lectura) y se publica en memoria dentro de _sm_lock (sin E/S),
# igual que un parámetro del equipo (TMG-01 de O2a). Mientras mide, los
# parámetros del equipo no se cambian (409 calibracion_en_curso).

_calibracion_atm_obj = None
_calibracion_atm_lock = threading.Lock()


def _leer_para_calibracion_atm() -> dict:
    # TMG-02 de O2f: instantánea coherente bajo _sm_lock (solo memoria)
    with context.control_loop.bloqueo_maquina():
        return _leer_para_calibracion_atm_sin_lock()


def _leer_para_calibracion_atm_sin_lock() -> dict:
    estado = context.estado
    try:
        maquina = estado.get_machine_state().name
    except Exception:
        maquina = ""
    try:
        programas = context.programas_para_seguridad()
        temp = sc.temp_seguridad(estado, programas, getattr(context, "profile", None))
    except Exception:
        temp = None
    return {"estado_maquina": maquina,
            "puertas": dict(getattr(estado, "estado_puertas", {}) or {}),
            "temp": temp,
            "pres": estado.sensores_pres.get("pres_camara"),
            "datos_vigentes": getattr(context.control_loop, "datos_vigentes", False) is True}


def _aplicar_presion_atmosferica(valor: float, usuario: str) -> None:
    """Escribe la referencia: base fuera del lock de la máquina; memoria
    dentro, y solo fuera de CICLO. Lanza ErrorParametro si no se puede."""
    from autoclave.core.managers.config_manager import ErrorParametro
    cm = context.config_manager
    with cm.lock_cambios:
        anterior, nuevo = cm.fijar("presion_atmosferica", valor, usuario,
                                   permitir_solo_lectura=True, aplicar=False)
        aplicado = False
        try:
            with context.control_loop.bloqueo_maquina():
                if context.estado.get_machine_state() == GlobalState.CICLO:
                    raise ErrorParametro("estado_no_permitido")
                cm.aplicar_valor("presion_atmosferica", nuevo, usuario)
                aplicado = True
        finally:
            if not aplicado:
                cm.revertir_bd("presion_atmosferica", anterior)


def _auditar_calibracion_atm(evento, usuario, rol, anterior, nuevo, detalle) -> None:
    context.db.registrar_auditoria(
        evento, usuario=usuario or "", rol=rol or "", entidad="presion_atmosferica",
        valor_anterior={"presion_atmosferica": anterior},
        valor_nuevo={"presion_atmosferica": nuevo} if nuevo is not None else None,
        detalle=detalle)


def _auditar_seguro(funcion, *args) -> None:
    try:
        funcion(*args)
    except Exception:
        logger.exception("No se pudo registrar la calibración atmosférica en audit_log")


def _calibracion_atm():
    global _calibracion_atm_obj
    with _calibracion_atm_lock:
        if _calibracion_atm_obj is None:
            from autoclave.core.runtime.calibracion_atm import CalibracionAtm
            _calibracion_atm_obj = CalibracionAtm(
                leer=_leer_para_calibracion_atm,
                aplicar=_aplicar_presion_atmosferica,
                auditar=lambda *a: _auditar_seguro(_auditar_calibracion_atm, *a),
                anterior=lambda: context.config_manager.get("presion_atmosferica"))
        return _calibracion_atm_obj


def _calibracion_atm_en_curso() -> bool:
    obj = _calibracion_atm_obj
    return obj is not None and obj.en_curso


def _estado_calibracion_atm() -> dict:
    d = _calibracion_atm().estado()
    try:
        ref = context.config_manager.describir("presion_atmosferica")
        um = ref.get("ultima_modificacion") or {}
        d["referencia"] = {"valor": ref.get("valor"), "usuario": um.get("usuario"),
                           "fecha": um.get("fecha")}
    except Exception:
        d["referencia"] = {"valor": None, "usuario": None, "fecha": None}
    return d


_MOTIVO_CONDICION_ATM = {
    "en_curso": "Ya hay una calibración en curso",
    "puerta_abierta": "La puerta debe estar abierta",
    "temp_baja": "La cámara debe estar por debajo de 80 °C",
    "fuera_de_ciclo": "No se puede calibrar con un ciclo en curso",
    "lecturas_validas": "Sin lectura válida de presión o temperatura de cámara",
}


@router.get("/maintenance/atm-calibration")
def get_atm_calibration():
    return _estado_calibracion_atm()


@router.post("/maintenance/atm-calibration/start")
def start_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = "/maintenance/atm-calibration/start"
    with context.config_manager.lock_cambios:      # TMG-03: no se cruza con un PATCH
        ok, codigo = _calibracion_atm().iniciar(sesion.usuario, sesion.rol)
    if not ok:
        _rechazar(409, "calibracion_en_curso" if codigo == "en_curso" else "precondicion",
                  _MOTIVO_CONDICION_ATM.get(codigo, "No se puede iniciar"), entidad, sesion,
                  extra={"condicion": codigo})
    return _estado_calibracion_atm()


@router.post("/maintenance/atm-calibration/cancel")
def cancel_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    if not _calibracion_atm().cancelar(sesion.usuario, sesion.rol):
        raise RechazoApi(409, "sin_calibracion", "No hay calibración en curso")
    return _estado_calibracion_atm()


@router.post("/maintenance/atm-calibration/confirm")
def confirm_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    ok, codigo = _calibracion_atm().confirmar(sesion.usuario, sesion.rol)
    if not ok:
        raise RechazoApi(409, codigo or "no_aplicada", "No se pudo aplicar la calibración")
    return _estado_calibracion_atm()


@router.post("/maintenance/atm-calibration/discard")
def discard_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    if not _calibracion_atm().descartar(sesion.usuario, sesion.rol):
        raise RechazoApi(409, "sin_pendiente", "No hay calibración por confirmar")
    return _estado_calibracion_atm()


@router.post("/maintenance/print/calibration")
def print_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Imprime ganancias y compensaciones (de usuario) de todos los sensores
    y la presión atmosférica de referencia."""
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    config = load_config(CALIBRATION_PATH)
    sensores = []
    for tipo, mapa, lista in (("temperature", EstadoAutoclave.map_temp,
                               config.calibration.user.temperature),
                              ("pressure", EstadoAutoclave.map_pres,
                               config.calibration.user.pressure)):
        for nombre, i in mapa.items():
            if i < len(lista):
                c = lista[i]
                sensores.append({"tipo": tipo, "sensor": nombre, "gain": c.gain,
                                 "offset": c.offset, "poly": bool(c.poly)})
    try:
        ref = context.config_manager.describir("presion_atmosferica")
    except Exception:
        ref = {}
    texto = tm.ganancias(_meta_equipo(), sensores, ref.get("valor"),
                         (ref.get("ultima_modificacion") or {}).get("fecha"))
    _encolar_en_impresora([texto])
    _log_desarrollo("impresion_ganancias", sesion, entidad="/maintenance/print/calibration",
                    sensores=len(sensores))   # D9-6
    return {"ok": True, "sensores": len(sensores)}
