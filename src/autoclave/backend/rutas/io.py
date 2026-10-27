# autoclave/backend/rutas/io.py
#
# Entradas/salidas: modo prueba, calibración de sensores y unidades
# (/io, /calibration, /units).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
import json
import os
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Literal
from fastapi import Depends, HTTPException, Body
from pydantic import BaseModel, StrictBool
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime import io_names
from autoclave.core.runtime import aire_atmosferico_prueba
from autoclave.core.runtime import salidas_prueba_seguridad
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
from autoclave.core.managers.catalogo_parametros import (evaluar_calibracion,
    evaluar_desviacion_acumulada)
from autoclave.config.calibration_writer import write_user_calibration
from autoclave.config import load_config
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (CALIBRATION_PATH, DISTINTO_DE_CICLO,
    DISTINTO_DE_CICLO_E_HIBERNACION, _MOTIVO_SESION_INVALIDA, _Rechazo, _auditar,
    _lock_archivos, _rechazar, context, guard_estado, requiere_rol, tokens)
from autoclave.backend.rutas._comun import (_contexto_ciclo, _motivo_paro, _p_atm_vigente,
    _reasignacion)

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


# Token de la sesión que activó el modo prueba: solo ella enciende salidas y
# sale (§5.4). Se lee y escribe con _sm_lock tomado (bloqueo_maquina).
_token_modo_prueba: str | None = None


# R1-P1 (tanda 7): ACK del ALL_OFF de la última salida del modo prueba, para la
# bitácora. Se escribe bajo _sm_lock en _salir_modo_prueba; quien registra
# modo_prueba_sale lo lee al soltar el lock (no hay otra salida en medio: para
# salir de nuevo habría que volver a entrar).
_ack_salida_prueba: bool | None = None


def _salir_modo_prueba() -> bool:
    """Apaga las salidas, reanuda la máquina y olvida la sesión dueña. Llamar
    con _sm_lock tomado; quien llama registra modo_prueba_sale al soltarlo
    (con `_detalle_salida_prueba`). Devuelve True si la tarjeta confirmó el
    ALL_OFF (R1-P1)."""
    global _token_modo_prueba, _ack_salida_prueba
    _ack_salida_prueba = context.control_loop.exit_test_mode() is True
    _token_modo_prueba = None
    _cierres_invertidos.clear()
    _cancelar_vigilancias_prueba()
    return _ack_salida_prueba


def _detalle_salida_prueba(motivo: str) -> dict:
    """Detalle de modo_prueba_sale con el ACK del ALL_OFF (R1-P1)."""
    return {"motivo": motivo, "all_off_confirmado": _ack_salida_prueba is True}


def _prueba_cancelada_por_paro() -> None:
    """Aviso del ControlLoop (hilo del loop, fuera de _sm_lock): el paro de
    emergencia canceló el modo prueba. Olvida la sesión dueña y lo registra."""
    global _token_modo_prueba
    with context.control_loop.bloqueo_maquina():
        if context.control_loop.test_mode_active:
            return   # ya se volvió a entrar: no es esta cancelación
        token, _token_modo_prueba = _token_modo_prueba, None
    _cancelar_vigilancias_prueba()
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None
    _auditar("modo_prueba_sale", sesion, usuario=dueno[0] if dueno else "",
             detalle={"motivo": "paro de emergencia"})


# SAF-01 (revisión de B7): si la sesión dueña del modo prueba caduca (o se
# invalida por otra vía que no lo cerró), el modo prueba no puede quedar con
# salidas manuales y la máquina pausada sin nadie que pueda salir: un vigilante
# del backend lo cierra igual que la salida normal (ALL_OFF y se reanuda la
# máquina). Orden de candados: _sm_lock -> tokens (nunca al revés).
VIGILANCIA_DUENO_PRUEBA_S = 2.0
_hilo_vigilancia_dueno = None


def _revisar_dueno_modo_prueba() -> bool:
    """Una pasada del vigilante. True si sacó del modo prueba. Nunca lanza
    hacia el hilo (el bucle lo protege)."""
    token = _token_modo_prueba
    if token is None or tokens.existe(token):
        return False
    with context.control_loop.bloqueo_maquina():
        if (not context.control_loop.test_mode_active or _token_modo_prueba != token
                or tokens.existe(token)):
            return False
        _salir_modo_prueba()
    dueno = tokens.quien_fue(token)
    logger.warning("Modo prueba cerrado: la sesión dueña (%s) ya no es válida",
                   dueno[0] if dueno else "?")
    _auditar("modo_prueba_sale", usuario=dueno[0] if dueno else "",
             detalle=_detalle_salida_prueba("sesión del dueño caducada o cerrada"))
    return True


def _vigilar_dueno_modo_prueba(cada_s: float = VIGILANCIA_DUENO_PRUEBA_S) -> None:
    while True:
        try:
            _revisar_dueno_modo_prueba()
        except Exception:
            logger.exception("Vigilancia del dueño del modo prueba")
        time.sleep(cada_s)


def _iniciar_vigilancia_dueno_prueba() -> None:
    global _hilo_vigilancia_dueno
    if _hilo_vigilancia_dueno is not None:
        return
    _hilo_vigilancia_dueno = threading.Thread(
        target=_vigilar_dueno_modo_prueba, name="vigilancia-dueno-prueba", daemon=True)
    _hilo_vigilancia_dueno.start()


def _invalidar_sesion(sesion: Sesion) -> bool:
    """Invalida el token y, si esta sesión tenía el modo prueba, sale de él
    (decisión 30: nadie más podría salir). Bajo el lock: un /io/test/enter de
    esta misma sesión en vuelo vuelve a validar el token dentro del lock y se
    rechaza. Devuelve True si salió del modo prueba; quien llama lo registra."""
    with context.control_loop.bloqueo_maquina():
        tokens.invalidar(sesion.token)
        salio = (_token_modo_prueba == sesion.token
                 and context.control_loop.test_mode_active)
        if salio:
            _salir_modo_prueba()
    return salio


def _resolve_sensor_index(tipo: str, sensor: str) -> int:
    name_map = {"temperature": EstadoAutoclave.map_temp, "pressure": EstadoAutoclave.map_pres}.get(tipo)
    if name_map is None:
        raise HTTPException(status_code=404, detail=f"Tipo de sensor desconocido: {tipo}")
    if sensor not in name_map:
        raise HTTPException(status_code=404, detail=f"Sensor desconocido: {sensor}")
    return name_map[sensor]


@router.get("/calibration/{tipo}/{sensor}")
def get_calibration(tipo: str, sensor: str):
    # P1 (tanda 7): la pantalla QML pide el sensor con el nombre de /io/channels
    # (temp_referencia); se usa la clave canónica (temp_ref) para el canal, los
    # límites por canal y la auditoría
    sensor = io_names.clave_estado(sensor)
    index = _resolve_sensor_index(tipo, sensor)
    config = load_config(CALIBRATION_PATH)
    calib = (config.calibration.user.temperature if tipo == "temperature"
             else config.calibration.user.pressure)[index]
    last = _ultimo_cambio_calibracion(tipo, sensor)
    return {
        "sensor": sensor,
        "tipo": tipo,
        "is_poly": bool(calib.poly),
        "gain": calib.gain,
        "offset": calib.offset,
        "poly": calib.poly,
        "last_change": last,
    }


def _ultimo_cambio_calibracion(tipo: str, sensor: str) -> dict | None:
    """Último cambio: primero audit_log; si no hay, la tabla histórica
    sensor_calibration_audit (§5.10), que ya no recibe escrituras."""
    try:
        filas = context.db.get_auditoria(evento="calibracion_cambio",
                                         entidad=f"{tipo}/{sensor}", limite=1)
    except Exception:
        logger.exception("No se pudo leer audit_log")
        filas = []
    if isinstance(filas, list) and filas:
        fila = filas[0]
        try:
            ts = datetime.fromisoformat(fila["ts"]).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            ts = fila["ts"]
        return {"usuario": fila["usuario"], "timestamp": ts}
    return context.calibration_audit.get_last_change(tipo, sensor)


@router.patch("/calibration/{tipo}/{sensor}")
def update_calibration(tipo: str, sensor: str, body: dict = Body(...),
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Técnico e ingeniero (tanda 2026-10-14 §1.1, C-5; antes solo ingeniero).
    Técnico solo fuera de CICLO; el ingeniero también en CICLO, donde aplica de
    inmediato (§5.8). El usuario sale del token: un `usuario` en el cuerpo se
    ignora."""
    # P1 (tanda 7): la pantalla QML pide el sensor con el nombre de /io/channels
    # (temp_referencia); se usa la clave canónica (temp_ref) para el canal, los
    # límites por canal y la auditoría
    sensor = io_names.clave_estado(sensor)
    index = _resolve_sensor_index(tipo, sensor)

    try:
        shown_low  = float(body["shown_low"]);  real_low  = float(body["real_low"])
        shown_high = float(body["shown_high"]); real_high = float(body["real_high"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="shown_low, real_low, shown_high, real_high son obligatorios y numericos",
        )
    origen_lectura = body.get("origen_lectura")
    if "origen_lectura" in body and not (
            isinstance(origen_lectura, dict) and set(origen_lectura) == {"bajo", "alto"}
            and all(v in ("capturada", "escrita") for v in origen_lectura.values())):
        raise HTTPException(
            status_code=422,
            detail='origen_lectura debe ser {"bajo": "capturada"|"escrita", "alto": "capturada"|"escrita"}',
        )
    entidad = f"{tipo}/{sensor}"

    # S3a (tanda 2): plausibilidad por tipo de canal (catálogo). Lo imposible
    # se rechaza; una corrección grande pide confirmación explícita
    nivel, motivo = evaluar_calibracion(tipo, body, sensor)
    if nivel == "rechazo":
        _rechazar(422, "CALIBRACION_IMPLAUSIBLE", f"Calibración no plausible: {motivo}",
                  f"/calibration/{entidad}", sesion)
    confirmado = body.get("confirmar_fuera_de_rango") is True
    if nivel == "aviso" and not confirmado:
        _rechazar(409, "CALIBRACION_REQUIERE_CONFIRMACION",
                  f"Calibración fuera del rango habitual: {motivo}",
                  f"/calibration/{entidad}", sesion)

    # Solo comprobación bajo _sm_lock: el guard solo deja pasar en CICLO al
    # ingeniero (el técnico recibe 409), así que la escritura no necesita ser
    # atómica con la comprobación. YAML y recarga van fuera del
    # lock para no detener el tick (revisión de la etapa 1, hallazgo D).
    # SAF-05 de T8: sin base no hay auditoría; no se toca el archivo
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "sin_base_de_datos", "Base de datos no disponible: calibración no aplicada",
                  f"/calibration/{entidad}", sesion)
    with guard_estado(DISTINTO_DE_CICLO, f"/calibration/{entidad}", sesion,
                      excepcion_ingeniero=True):
        contexto_ciclo = _contexto_ciclo()

    with _lock_archivos:
        config = load_config(CALIBRATION_PATH)
        user_list = (config.calibration.user.temperature if tipo == "temperature"
                     else config.calibration.user.pressure)
        old_calib = user_list[index]
        old_gain, old_offset = old_calib.gain, old_calib.offset

        try:
            fv_low  = invert_user_calibration(shown_low, old_calib.gain, old_calib.offset, old_calib.poly)
            fv_high = invert_user_calibration(shown_high, old_calib.gain, old_calib.offset, old_calib.poly)
            new_gain, new_offset = fit_two_point(fv_low, real_low, fv_high, real_high)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        # S3a (revisión): desviación ACUMULADA de la calibración resultante
        # respecto de la neutra, y canal con polinomio vigente (la recta nueva
        # lo reemplaza fuera de los puntos): aviso confirmable o rechazo
        nivel_acum, motivo_acum = evaluar_desviacion_acumulada(tipo, new_gain, new_offset, sensor)
        if old_calib.poly and nivel_acum is None:
            nivel_acum, motivo_acum = "aviso", ("el canal tiene un polinomio de calibración vigente: "
                                                 "la recta nueva lo reemplaza")
        if nivel_acum == "rechazo":
            _rechazar(422, "CALIBRACION_IMPLAUSIBLE", f"Calibración no plausible: {motivo_acum}",
                      f"/calibration/{entidad}", sesion)
        if nivel_acum == "aviso" and not confirmado:
            _rechazar(409, "CALIBRACION_REQUIERE_CONFIRMACION",
                      f"Calibración fuera del rango habitual: {motivo_acum}",
                      f"/calibration/{entidad}", sesion)
        if nivel_acum is not None and nivel is None:
            nivel, motivo = nivel_acum, motivo_acum

        # SAF-03 de T3: si un ciclo arrancó entre la comprobación y este
        # punto, el técnico no puede cambiar la calibración en curso
        if sesion.rol != ROL_INGENIERO:
            with context.control_loop.bloqueo_maquina():
                en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            if en_ciclo:
                raise HTTPException(status_code=409,
                                    detail="Hay un ciclo en curso: calibración no aplicada")
        detalle = {"puntos": {"shown_low": shown_low, "real_low": real_low,
                              "shown_high": shown_high, "real_high": real_high},
                   # R8: puerto físico calibrado (la calibración es por puerto)
                   "puerto": index + 1 + (8 if tipo == "pressure" else 0)}
        if nivel is not None:
            detalle["plausibilidad"] = {"nivel": nivel, "motivo": motivo,
                                        "confirmado": confirmado}
        if origen_lectura is not None:
            detalle["origen_lectura"] = dict(origen_lectura)
        detalle.update(contexto_ciclo)
        # BD-03 (T8, §7.6): sin registro en audit_log la calibración no queda
        # activa. Se guarda el archivo previo y se restaura si la auditoría falla.
        previo = Path(CALIBRATION_PATH).read_bytes()
        write_user_calibration(
            CALIBRATION_PATH, tipo, index, new_gain, new_offset,
            shown_low, real_low, shown_high, real_high,
        )
        context.units.reload_calibration(CALIBRATION_PATH)
        try:
            context.db.registrar_auditoria(
                "calibracion_cambio", usuario=sesion.usuario, rol=sesion.rol,
                entidad=entidad,
                valor_anterior={"gain": old_gain, "offset": old_offset},
                valor_nuevo={"gain": new_gain, "offset": new_offset},
                detalle=detalle)
        except Exception:
            logger.exception("Calibración %s sin auditoría: se revierte", entidad)
            # restauración atómica (SAF-05/TMG-05 de T8): temporal + fsync + replace
            ruta = Path(CALIBRATION_PATH)
            tmp = ruta.with_name(ruta.name + ".restaurar")
            with open(tmp, "wb") as f:
                f.write(previo)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ruta)
            context.units.reload_calibration(CALIBRATION_PATH)
            _rechazar(503, "auditoria_no_disponible",
                      "No se pudo registrar el cambio: calibración no aplicada",
                      f"/calibration/{entidad}", sesion)

        # R8 (revisión): evidencia de calibración EN ESTE ARRANQUE y en el
        # puerto vigente; dentro del lock de archivos (TMG-01, 4.ª vuelta)
        _reasignacion.evidencia_ai(tipo, sensor)
    return {"ok": True, "gain": new_gain, "offset": new_offset}


@router.post("/calibration/{tipo}/{sensor}/restaurar")
def restaurar_calibracion(tipo: str, sensor: str, body: dict = Body(...),
                          sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """B-ES-4 / §7.4: devuelve el sensor a la calibración neutra ("defecto":
    ganancia 1.0, offset 0.0) o a los valores previos a la última modificación
    ("ultimo", de valor_anterior en audit_log). Mismas reglas que el PATCH:
    rol, estado, auditoría obligatoria con reversión del archivo."""
    # P1 (tanda 7): la pantalla QML pide el sensor con el nombre de /io/channels
    # (temp_referencia); se usa la clave canónica (temp_ref) para el canal, los
    # límites por canal y la auditoría
    sensor = io_names.clave_estado(sensor)
    index = _resolve_sensor_index(tipo, sensor)
    destino = body.get("destino")
    if destino not in ("ultimo", "defecto"):
        raise HTTPException(status_code=422, detail='destino debe ser "ultimo" o "defecto"')
    entidad = f"{tipo}/{sensor}"
    ruta = f"/calibration/{entidad}/restaurar"

    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "sin_base_de_datos", "Base de datos no disponible: calibración no aplicada",
                  ruta, sesion)
    with guard_estado(DISTINTO_DE_CICLO, ruta, sesion, excepcion_ingeniero=True):
        contexto_ciclo = _contexto_ciclo()

    with _lock_archivos:
        if destino == "defecto":
            nuevo_gain, nuevo_offset = 1.0, 0.0
        else:
            try:
                filas = context.db.get_auditoria(evento="calibracion_cambio",
                                                 entidad=entidad, limite=1)
                # R8 (SEN-02 de la re-revisión): tras reasignar, el último
                # cambio puede ser del puerto viejo; no se copia al nuevo
                if filas and not _reasignacion.ultimo_es_del_puerto_vigente(tipo, sensor, filas[0]):
                    filas = []
                previo_json = filas[0]["valor_anterior"] if filas else None
                anterior = json.loads(previo_json) if isinstance(previo_json, str) else previo_json
                nuevo_gain, nuevo_offset = float(anterior["gain"]), float(anterior["offset"])
            except (IndexError, KeyError, TypeError, ValueError):
                _rechazar(409, "sin_calibracion_previa",
                          "No hay una calibración anterior que restaurar", ruta, sesion)

        config = load_config(CALIBRATION_PATH)
        user_list = (config.calibration.user.temperature if tipo == "temperature"
                     else config.calibration.user.pressure)
        old_gain, old_offset = user_list[index].gain, user_list[index].offset

        if sesion.rol != ROL_INGENIERO:
            with context.control_loop.bloqueo_maquina():
                en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            if en_ciclo:
                raise HTTPException(status_code=409,
                                    detail="Hay un ciclo en curso: calibración no aplicada")
        # R8 (3.ª vuelta, SEN): puerto físico también al restaurar
        detalle = {"accion": f"restaurar_{destino}",
                   "puerto": index + 1 + (8 if tipo == "pressure" else 0)}
        detalle.update(contexto_ciclo)
        # R8 (SEN 3.ª vuelta; TMG-01/SAF-01 4.ª vuelta): restaurar deja de
        # contar como calibración del puerto nuevo; se anula ANTES de escribir
        # y dentro del lock de archivos (si la auditoría falla y se revierte,
        # solo obliga a recalibrar)
        _reasignacion.anular_evidencia_ai(tipo, sensor)
        previo = Path(CALIBRATION_PATH).read_bytes()
        write_user_calibration(CALIBRATION_PATH, tipo, index, nuevo_gain, nuevo_offset,
                               0.0, 0.0, 0.0, 0.0, nota=f"restaurada ({destino})")
        context.units.reload_calibration(CALIBRATION_PATH)
        try:
            context.db.registrar_auditoria(
                "calibracion_cambio", usuario=sesion.usuario, rol=sesion.rol,
                entidad=entidad,
                valor_anterior={"gain": old_gain, "offset": old_offset},
                valor_nuevo={"gain": nuevo_gain, "offset": nuevo_offset},
                detalle=detalle)
        except Exception:
            logger.exception("Restauración %s sin auditoría: se revierte", entidad)
            archivo = Path(CALIBRATION_PATH)
            tmp = archivo.with_name(archivo.name + ".restaurar")
            with open(tmp, "wb") as f:
                f.write(previo)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, archivo)
            context.units.reload_calibration(CALIBRATION_PATH)
            _rechazar(503, "auditoria_no_disponible",
                      "No se pudo registrar el cambio: calibración no aplicada", ruta, sesion)

    return {"ok": True, "gain": nuevo_gain, "offset": nuevo_offset}


# ── Unidades de presentación (U1, tanda 5; decisión 6 de Cristian) ─────────
# Solo presentación y entrada de datos: el control, la BD, los JSON y esta API
# siguen en °C y kPa absolutos. P_atm es la calibrada del equipo; sin valor
# vigente se publica null y la UI no muestra psi.

class _UnidadesBody(BaseModel):
    temperatura: Literal["C", "F"]
    presion: Literal["kPa", "bar", "mbar", "psi"]


@router.get("/units")
def get_units():
    return {**context.config_unidades.leer(), "p_atm": _p_atm_vigente()}


@router.put("/units")
def put_units(body: _UnidadesBody,
              sesion: Sesion = Depends(requiere_rol(ROL_INGENIERO))):
    """Decisión 1.9 (tanda 6): solo el ingeniero, y solo fuera de ciclo (también el ingeniero: un
    cambio de unidades a mitad de ciclo se presta a leer mal un valor)."""
    entidad = "/units"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        anterior = context.config_unidades.leer()
    try:
        nuevo = context.config_unidades.guardar(body.temperatura, body.presion)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración",
                  entidad, sesion)
    _auditar("unidades_configuradas", sesion, entidad=entidad,
             valor_anterior=anterior, valor_nuevo=nuevo)
    return {"ok": True, **nuevo}


# Direct hardware access — bypasses control_loop, for bench validation only

class _OutputSetBody(BaseModel):
    value: bool
    momentanea: bool = False


# P-ES-3 / P-ES-4 (propuestas pendientes de confirmar): una salida momentánea
# se apaga sola si no se renueva, y el modo prueba se cierra sin actividad.
CADUCIDAD_MOMENTANEA_S = 1.5
INACTIVIDAD_MODO_PRUEBA_S = 90.0
_timers_momentaneas: dict[int, threading.Timer] = {}
_timer_inactividad: threading.Timer | None = None
_lock_vigilancias = threading.Lock()


def _cancelar_vigilancias_prueba() -> None:
    global _timer_inactividad
    with _lock_vigilancias:
        for t in _timers_momentaneas.values():
            t.cancel()
        _timers_momentaneas.clear()
        if _timer_inactividad is not None:
            _timer_inactividad.cancel()
            _timer_inactividad = None


def _nombre_do(canal: int) -> str:
    return next((n for n, i in EstadoAutoclave.map_do.items() if i + 1 == canal), str(canal))


# TMG-07 / revisión P1 (TMG-03): cada entrada al modo prueba es una generación
# nueva; un temporizador armado en otra generación (que ya pasó su chequeo de
# identidad mientras esperaba el candado) no actúa sobre la sesión actual.
_generacion_prueba = 0


def _caducar_momentanea(canal: int, timer: threading.Timer, generacion: int = -1) -> None:
    """Hilo del temporizador: sin renovación a tiempo, apaga la salida."""
    with _lock_vigilancias:
        if _timers_momentaneas.get(canal) is not timer:
            return   # renovada o cancelada mientras tanto
        del _timers_momentaneas[canal]
    with context.control_loop.bloqueo_maquina():
        if not context.control_loop.test_mode_active or generacion != _generacion_prueba:
            return
        context.setdo.set_output(canal, False)
        token = _token_modo_prueba
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None   # TMG-08
    _auditar("salida_prueba", sesion, usuario=dueno[0] if dueno else "",
             entidad=_nombre_do(canal), valor_nuevo=False,
             detalle={"motivo": "caducó sin renovación"})


def _armar_momentanea(canal: int) -> bool:
    """Arma o renueva la caducidad. Devuelve True si era una renovación."""
    with _lock_vigilancias:
        previo = _timers_momentaneas.pop(canal, None)
        if previo is not None:
            previo.cancel()
        generacion = _generacion_prueba
        timer = threading.Timer(CADUCIDAD_MOMENTANEA_S,
                                lambda: _caducar_momentanea(canal, timer, generacion))
        timer.daemon = True
        _timers_momentaneas[canal] = timer
        timer.start()
    return previo is not None


def _desarmar_momentanea(canal: int) -> None:
    with _lock_vigilancias:
        previo = _timers_momentaneas.pop(canal, None)
    if previo is not None:
        previo.cancel()


def _salir_por_inactividad(timer: threading.Timer, generacion: int = -1) -> None:
    global _timer_inactividad
    with _lock_vigilancias:
        if _timer_inactividad is not timer:
            return
        _timer_inactividad = None
    with context.control_loop.bloqueo_maquina():
        if not context.control_loop.test_mode_active or generacion != _generacion_prueba:
            return
        token = _token_modo_prueba
        _salir_modo_prueba()
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None   # TMG-08
    _auditar("modo_prueba_sale", sesion, usuario=dueno[0] if dueno else "",
             detalle=_detalle_salida_prueba("sin actividad de la sesión (keepalive)"))


def _marcar_actividad_prueba() -> None:
    """Rearma el plazo de inactividad del modo prueba (cada orden y keepalive)."""
    global _timer_inactividad
    with _lock_vigilancias:
        if _timer_inactividad is not None:
            _timer_inactividad.cancel()
        generacion = _generacion_prueba
        timer = threading.Timer(INACTIVIDAD_MODO_PRUEBA_S,
                                lambda: _salir_por_inactividad(timer, generacion))
        timer.daemon = True
        _timer_inactividad = timer
        timer.start()


_requiere_rol_prueba = requiere_rol(ROL_TECNICO, ROL_INGENIERO)


def _rechazar_si_sin_datos_vigentes() -> None:
    """Modo prueba con el enlace caído o con la trama DI vencida: las órdenes
    se darían sobre lecturas viejas (adenda E0/E1, A-8, TMG-05). Mismo código
    de rechazo que las órdenes de puerta con el enlace caído."""
    cl = context.control_loop
    if cl.desconectado is True or cl.datos_vigentes is False:
        raise _Rechazo(409, "sin_conexion_tarjeta",
                       "Sin conexión con la tarjeta de control o datos no vigentes")


@router.get("/io/channels")
def io_channels(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """B-ES-2: canales de Entradas / Salidas del equipo (io_enabled) con id
    físico, clave i18n y si la salida es momentánea (D-ES-02, D-ES-03, D-ES-09).
    D8-3.17: solo los canales que declara el perfil de instalación."""
    perfil = getattr(context, "profile", None)
    salidas = io_names.canales_digitales("DO", profile=perfil)
    for c in salidas:
        canal = EstadoAutoclave.map_do[c["estado_key"]] + 1
        # fuente de vapor que el equipo no usa (E1b / S1): se muestra deshabilitada
        c["bloqueada"] = context.setdo.salida_bloqueada(canal) is True
    return {
        "DI": io_names.canales_digitales("DI", profile=perfil),
        "DO": salidas,
        "temperature": io_names.sensores("temperature", profile=perfil),
        "pressure": io_names.sensores("pressure", profile=perfil),
    }


@router.post("/io/test/enter")
def io_test_enter(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Activa el modo prueba: pausa la máquina de estados (sin importar la
    fase — PREPARACION, PREPARADO o FALLA) y apaga todas las salidas para
    permitir control manual. Rechazado en CICLO o con
    el paro de emergencia activo. Recuerda la sesión que entró (§5.4).

    El ALL_OFF de enter_test_mode corre con _sm_lock tomado (espera el ACK
    hasta 1 s); es aceptable porque el guard excluye CICLO."""
    global _token_modo_prueba, _generacion_prueba
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, "/io/test/enter", sesion):
        motivo_config = context.control_loop.bloqueo_configuracion
        if isinstance(motivo_config, str) and motivo_config:
            raise _Rechazo(409, "configuracion_invalida",
                           f"Configuración inválida: {motivo_config}")
        _rechazar_si_sin_datos_vigentes()
        # un logout de esta sesión pudo llegar mientras esta petición esperaba
        if not tokens.existe(sesion.token):
            raise _Rechazo(401, "sesion_invalida", _MOTIVO_SESION_INVALIDA)
        # sin esto, otra sesión le quitaría la propiedad a la que entró
        if (context.control_loop.test_mode_active
                and _token_modo_prueba not in (None, sesion.token)):
            raise _Rechazo(409, "modo_prueba_otra_sesion",
                           "El modo prueba ya está activo en otra sesión")
        ya_activo = context.control_loop.test_mode_active
        ok, reason = context.control_loop.enter_test_mode()
        if not ok:
            raise _Rechazo(409, "modo_prueba_rechazado", reason)
        _token_modo_prueba = sesion.token
        if not ya_activo:     # reentrada de la misma sesión: misma generación
            _generacion_prueba += 1
        _marcar_actividad_prueba()
    _auditar("modo_prueba_entra", sesion)
    return {"ok": True}


# B-ES-8: causas que la UI puede declarar al salir (lista cerrada, §6.5)
_CAUSAS_SALIDA_UI = frozenset({"salida solicitada", "abandono de la sección",
                               "inactividad de la interfaz", "cierre de sesión"})


@router.post("/io/test/exit")
def io_test_exit(sesion: Sesion = Depends(_requiere_rol_prueba),
                 body: dict | None = Body(None)):
    """Sale del modo prueba: apaga todas las salidas y reanuda la máquina de
    estados. 409 si no se estaba en modo prueba o si lo pide otra sesión.
    Comprobación y salida bajo _sm_lock: ninguna orden de encendido ya
    validada puede llegar después del apagado."""
    with guard_estado(frozenset(), "/io/test/exit", sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if _token_modo_prueba != sesion.token:
            raise _Rechazo(409, "modo_prueba_no_dueno",
                           "Solo la sesión que activó el modo prueba puede salir de él")
        confirmado = _salir_modo_prueba()
    causa = body.get("motivo") if isinstance(body, dict) else None
    if causa not in _CAUSAS_SALIDA_UI:
        causa = "salida solicitada"
    _auditar("modo_prueba_sale", sesion, detalle=_detalle_salida_prueba(causa))
    return {"ok": True, "all_off_confirmado": confirmado}


# canales cerrar_puerta_N cuya orden se invirtió y siguen pulsados (P-ES-8)
_cierres_invertidos: set[int] = set()


def _puerta_con_atrapamiento(canal_cerrar: int, encender: bool):
    """Seguro de atrapamiento en modo prueba (D-ES-16, §6.7). Devuelve
    (puerta, nueva): la puerta cuya orden de cerrar debe invertirse en abrir y
    si es la primera inversión de esta pulsación. Una vez invertida, sigue
    invertida hasta que el usuario suelta (OFF), aunque la señal se libere.
    Interpreta la entrada semántica (NC: 0 = atrapada), no el bit crudo."""
    if not encender:
        _cierres_invertidos.discard(canal_cerrar)
        return None, False
    for door in (context.doors or []):
        do, di = getattr(door, "do", None), getattr(door, "di", None)
        if not (isinstance(do, dict) and isinstance(di, dict)):
            continue
        if do.get("cerrar") != canal_cerrar or "atrapamiento" not in di or "abrir" not in do:
            continue
        if canal_cerrar in _cierres_invertidos:
            return door, False
        if context.estado.sensores_di.get(di["atrapamiento"]) == 0:
            _cierres_invertidos.add(canal_cerrar)
            return door, True
    return None, False


def _salidas_prueba_bloqueadas() -> dict:
    """S9, revisión ★ SAF-01: {salida: código} que el modo prueba no puede
    encender ahora (ControlLoop.salidas_prueba_bloqueadas). Falla cerrada:
    un error al evaluar o una respuesta que no es dict bloquean todas
    (revisión ★ pasada 2 R2-B1)."""
    try:
        bloqueadas = context.control_loop.salidas_prueba_bloqueadas()
    except Exception:
        logger.exception("Modo prueba: no se pudo evaluar las salidas bloqueadas")
        return salidas_prueba_seguridad.todas()
    if not isinstance(bloqueadas, dict):
        logger.error("Modo prueba: evaluación de salidas bloqueadas inválida; se bloquean todas")
        return salidas_prueba_seguridad.todas()
    return bloqueadas


@router.patch("/io/test/output/{name}")
def io_test_set_output(name: str, body: _OutputSetBody,
                       sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Acciona una salida en modo prueba. Apagar siempre se permite dentro del
    modo prueba; encender exige además ser la sesión dueña y R-02 (§5.4)."""
    # P1 (tanda 7): /io/channels da el nombre del YAML; la posición se busca con
    # la clave de EstadoAutoclave (errata aire_admosferico_camara)
    clave = io_names.clave_estado(name)
    if clave not in EstadoAutoclave.map_do:
        raise HTTPException(status_code=404, detail=f"Output '{name}' no encontrado")
    entidad = f"/io/test/output/{name}"
    if body.momentanea and name not in io_names.SALIDAS_MOMENTANEAS:
        raise HTTPException(status_code=422,
                            detail=f"'{name}' no es una salida momentánea")
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, entidad, sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro("Paro de emergencia activado"))
        _rechazar_si_sin_datos_vigentes()
        if body.value:
            if getattr(context.control_loop, "apagando", False) is True:   # A1
                raise _Rechazo(409, "apagado_en_curso", "El equipo se está apagando")
            # encender solo desde la sesión que está a cargo de la prueba;
            # apagar queda abierto a cualquier sesión de prueba (es lo seguro)
            if _token_modo_prueba != sesion.token:
                raise _Rechazo(409, "modo_prueba_no_dueno",
                               "Solo la sesión que activó el modo prueba puede encender salidas")
            # D-ES-15: en modo prueba se permiten todas las salidas; R-02
            # (presión atmosférica y puertas cerradas) ya no se exige aquí.
            # D8-3.19 (tanda 8): ÚNICA excepción, el aire atmosférico de la
            # cámara: con presión sobre atm + brecha o sin lectura, no se abre.
            if clave == aire_atmosferico_prueba.CLAVE_ESTADO:   # SAF-04: por la clave resuelta
                # presión con la trama AI al día (revisión SAF-01/TMG-01/SEN-01)
                if getattr(context.control_loop, "presion_vigente", False) is not True:
                    permitido, codigo = False, aire_atmosferico_prueba.SIN_PRESION
                else:
                    permitido, codigo = aire_atmosferico_prueba.evaluar(
                        context.estado, context.config_manager,
                        senal_presente=aire_atmosferico_prueba.senal_camara(
                            getattr(context, "units", None),
                            leido_mono=getattr(context.control_loop, "estado_leido_mono", None)))
                if not permitido:
                    raise _Rechazo(409, codigo, aire_atmosferico_prueba.MOTIVOS[codigo])
            # S9 (tanda 9), revisión ★ SAF-01 (DECISIÓN SIN CONFIRMAR): con el
            # estado seguro activo, la recuperación pendiente o la cámara no
            # segura, ni apertura ni desbloqueo de puertas; con el estado
            # seguro, tampoco rápida, chaqueta ni vapor de cámara
            codigo = _salidas_prueba_bloqueadas().get(clave)
            if codigo is not None:
                raise _Rechazo(409, codigo, salidas_prueba_seguridad.MOTIVOS[codigo])
        # map_do es 0-indexado (posición en el bitstream DO), pero
        # serial_link.set_output() espera el número de canal DO físico
        # 1-indexado (DO1..DO32), igual que SetOutput y la fábrica de puertas.
        index = EstadoAutoclave.map_do[clave]
        if body.value and context.setdo.salida_bloqueada(index + 1) is True:
            # E1b: salida de una fuente de vapor que el equipo no tiene; S1 (tanda
            # 2): con generador interno ni DO1 ni DO2 (el generador se controla solo)
            raise _Rechazo(409, "fuente_vapor_no_instalada",
                           "Esta salida de fuente de vapor no la usa este equipo (vapor_source)")
        puerta_atrapada, nueva = _puerta_con_atrapamiento(index + 1, body.value)
        if puerta_atrapada is not None:
            # S9, revisión ★ SAF-01: la inversión de D-ES-16 abriría la puerta;
            # con la apertura bloqueada solo se suelta el cierre
            canales = {EstadoAutoclave.map_do[k] + 1: c
                       for k, c in _salidas_prueba_bloqueadas().items()}
            codigo = canales.get(puerta_atrapada.do["abrir"])
            if codigo is not None:
                context.setdo.set_output(index + 1, False)
                _desarmar_momentanea(index + 1)
                raise _Rechazo(409, codigo, salidas_prueba_seguridad.MOTIVOS[codigo])
            # D-ES-16: la orden de cerrar con atrapamiento activo se convierte en abrir
            context.setdo.set_output(index + 1, False)
            context.setdo.set_output(puerta_atrapada.do["abrir"], True)
            _desarmar_momentanea(index + 1)
            if body.momentanea:
                _armar_momentanea(puerta_atrapada.do["abrir"])
            _marcar_actividad_prueba()
            if nueva:
                _auditar("atrapamiento_orden_invertida", sesion, entidad=name,
                         detalle={"puerta": getattr(puerta_atrapada, "name", None)})
            return {"ok": True, "name": name, "value": False, "invertida": True}
        context.setdo.set_output(index + 1, body.value)
        if body.value:
            # R8 (revisión): evidencia de la salida accionada EN ESTE ARRANQUE
            _reasignacion.evidencia_do(clave)
        renovacion = False
        if body.value and body.momentanea:
            renovacion = _armar_momentanea(index + 1)
        else:
            _desarmar_momentanea(index + 1)
        _marcar_actividad_prueba()
    # una salida momentánea registra solo el primer y último pulso, no cada renovación
    if not renovacion:
        _auditar("salida_prueba", sesion, entidad=name, valor_nuevo=body.value)
    return {"ok": True, "name": name, "value": body.value}


@router.post("/io/test/keepalive")
def io_test_keepalive(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """P-ES-4: la sesión dueña avisa que sigue ahí; sin avisos (ni órdenes) el
    backend sale solo del modo prueba."""
    with guard_estado(frozenset(), "/io/test/keepalive", sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if _token_modo_prueba != sesion.token:
            raise _Rechazo(409, "modo_prueba_no_dueno",
                           "Solo la sesión que activó el modo prueba puede mantenerlo")
        _marcar_actividad_prueba()
    return {"ok": True}


class _SalidaForzadaBody(BaseModel):
    confirmar: StrictBool = False         # SAF-06: solo el literal JSON true
    motivo: str = ""


@router.post("/io/test/force-exit")
def io_test_force_exit(body: _SalidaForzadaBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """B8 (tanda 4): salida forzada del modo prueba HUÉRFANO. Solo el dueño
    puede dejar el modo prueba; si ese usuario ya no tiene sesión (token vencido
    por inactividad, cierre de sesión, cambio de turno), un INGENIERO con sesión
    puede terminarlo con confirmación explícita (`confirmar: true`). Un técnico
    solo puede si es el mismo usuario dueño (SAF-03 de la revisión: salir es la
    dirección segura); otro técnico, 403. Con el dueño aún en sesión, 409: debe salir él (o esperar a
    que su sesión caduque). Misma salida que la normal: todas las salidas a
    seguro y se reanuda la máquina; un estado seguro en curso sigue su camino.
    Queda en audit_log quién fuerza, a quién se le sacó y por qué."""
    entidad = "/io/test/force-exit"
    if body.confirmar is not True:
        _rechazar(422, "confirmacion_requerida",
                  "Confirme explícitamente la salida forzada del modo prueba", entidad, sesion)
    motivo = (body.motivo or "").strip()[:200] or "modo prueba huérfano"
    with guard_estado(frozenset(), entidad, sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        dueno_token = _token_modo_prueba
        if (dueno_token is not None and dueno_token != sesion.token
                and tokens.existe(dueno_token)):
            raise _Rechazo(409, "modo_prueba_dueno_vigente",
                           "El dueño del modo prueba sigue con sesión: debe salir él")
        dueno = tokens.quien_fue(dueno_token)
        if sesion.rol != ROL_INGENIERO and (dueno is None or dueno[0] != sesion.usuario):
            raise _Rechazo(403, "rol_sin_permiso",
                           "Solo un ingeniero o el propio dueño pueden forzar la salida")
        estado_seguro = getattr(getattr(context.control_loop, "estado_seguro", None), "activo", False)
        _salir_modo_prueba()
    _auditar("modo_prueba_salida_forzada", sesion, entidad=entidad,
             valor_anterior={"dueno": dueno[0] if dueno else None,
                             "rol_dueno": dueno[1] if dueno else None},
             detalle={"motivo": motivo, "forzada_por": sesion.usuario,
                      "dueno": dueno[0] if dueno else None,
                      "estado_seguro_activo": estado_seguro is True})
    _auditar("modo_prueba_sale", sesion,
             detalle=_detalle_salida_prueba("salida forzada por ingeniero"))
    return {"ok": True, "dueno": dueno[0] if dueno else None}
