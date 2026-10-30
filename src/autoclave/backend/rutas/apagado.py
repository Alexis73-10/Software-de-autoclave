# autoclave/backend/rutas/apagado.py
#
# Apagado del equipo y reinicio del software (/system/shutdown).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
import sys
import os
import threading
from fastapi import Body
from autoclave.backend import reinicio
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime import camara_segura
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, _Rechazo, _auditar,
    _cierre_ordenado_hecho, _rechazar, context, guard_estado)
from autoclave.backend.rutas._comun import _salidas_sin_confirmar_pendiente

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


# ── Apagar equipo (fin de ciclo §16, D-20; tanda E5) ───────────────────────

def _apagado_windows_habilitado() -> bool:
    """El apagado real de Windows solo corre en el ejecutable empaquetado o
    con AUTOCLAVE_APAGADO_REAL=1: nunca desde las pruebas ni en desarrollo."""
    import os
    return bool(getattr(sys, "frozen", False)) or os.environ.get("AUTOCLAVE_APAGADO_REAL") == "1"


# D8-3.21 (tanda 8): Windows rechazó el apagado. La pantalla lo consulta en
# GET /system/shutdown/estado y muestra "apáguelo manualmente" (catálogo).
_apagado_lock = threading.Lock()
_apagado_windows_rechazado = False


def _registrar_apagado_rechazado(detalle: dict) -> None:
    """Marca el rechazo para la pantalla y lo deja en la bitácora. La base ya
    se cerró en la secuencia: se escribe con una conexión propia."""
    global _apagado_windows_rechazado
    with _apagado_lock:
        _apagado_windows_rechazado = True
    logger.error("Apagar equipo: Windows rechazó el apagado: %s", detalle)
    real = getattr(context, "db_real", None)
    db = (real if getattr(context, "sin_base_de_datos", False) is True and real is not None
          else context.db)
    try:
        db.registrar_auditoria_tras_cierre(
            "apagado_windows_rechazado", entidad="/system/shutdown", detalle=detalle)
    except Exception:
        logger.exception("No se pudo registrar 'apagado_windows_rechazado' en audit_log")


def _apagar_windows() -> None:
    import subprocess
    try:
        r = subprocess.run(["shutdown", "/s", "/t", "0"], check=False, timeout=30,
                           capture_output=True, errors="replace",
                           encoding="oem" if sys.platform == "win32" else None,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        # sin shutdown.exe, sin permiso o colgado: tampoco se apagó
        _registrar_apagado_rechazado({"error": f"{type(e).__name__}: {e}"})
        return
    if r.returncode != 0:
        # P1 (tanda 7): el lazo ya se detuvo; sin esto no quedaba el motivo
        _registrar_apagado_rechazado({"codigo": r.returncode,
                                      "mensaje": (r.stderr or r.stdout or "").strip()[:500]})


_TOPE_PASO_APAGADO_S = 8.0


def _paso_apagado(descripcion: str, paso, tope: float | None = None) -> None:
    """Un paso de la secuencia de apagado: un fallo se registra y NO impide
    los siguientes ni el apagado de Windows (A1, tanda 3). Con `tope`, el paso
    corre en un hilo auxiliar y, si no termina a tiempo, se sigue sin él."""
    if tope is None:
        try:
            paso()
        except BaseException:
            logger.exception("Apagar equipo: error en el paso '%s'", descripcion)
        return

    def ejecutar():
        try:
            paso()
        except BaseException:
            logger.exception("Apagar equipo: error en el paso '%s'", descripcion)

    hilo = threading.Thread(target=ejecutar, name="Apagado-" + descripcion[:20], daemon=True)
    hilo.start()
    hilo.join(tope)
    if hilo.is_alive():
        logger.error("Apagar equipo: el paso '%s' no terminó en %.0f s; se sigue", descripcion, tope)


def _secuencia_apagado(apagar_windows: bool = True) -> None:
    """ALL_OFF y parada del lazo (control_loop.stop: detiene el lazo, intenta
    ALL_OFF y cierra el enlace de E/S), historial de alarmas, base de datos y,
    si está habilitado, apagado de Windows. Corre en un hilo aparte para
    responder antes de cortar. Con degradación segura (A1): sin módulo E/S o con
    un paso fallido se registra y se sigue; el paro y el latido del módulo E/S
    dejan las salidas en seguro por hardware.

    R11 (D11-1.2): `reiniciar_software` usa esta misma secuencia con
    `apagar_windows=False`; los pasos de cierre no cambian."""
    _paso_apagado("detener el lazo de control", context.control_loop.stop, _TOPE_PASO_APAGADO_S)
    historial = getattr(context, "historial_alarmas", None)
    if historial is not None and hasattr(historial, "detener"):
        _paso_apagado("detener el historial de alarmas", lambda: historial.detener(2.0),
                      _TOPE_PASO_APAGADO_S)
    # S3d: vaciar las colas de escritura del respaldo y de la base ANTES de
    # cerrar la base (con el lazo ya detenido no entran tareas nuevas)
    logger_ciclo = getattr(context, "cycle_logger", None)
    if logger_ciclo is not None and hasattr(logger_ciclo, "detener"):
        _paso_apagado("vaciar la escritura del ciclo", lambda: logger_ciclo.detener(5.0),
                      _TOPE_PASO_APAGADO_S)

    def cerrar_base():
        # tras una falla de la base en caliente, context.db es BdNoDisponible
        real = getattr(context, "db_real", None)
        (real if getattr(context, "sin_base_de_datos", False) is True and real is not None
         else context.db).close()
    _paso_apagado("cerrar la base de datos", cerrar_base, _TOPE_PASO_APAGADO_S)
    if not apagar_windows:
        logger.warning("Reinicio del software: cierre ordenado hecho, sin apagar Windows")
    elif _apagado_windows_habilitado():
        logger.warning("Apagar equipo: apagando Windows")
        _paso_apagado("apagar Windows", _apagar_windows)
    else:
        logger.warning("Apagar equipo: apagado de Windows omitido (no es el ejecutable)")


@router.post("/system/shutdown")
def shutdown_system(body: dict = Body(default={})):
    """"Apagar equipo" / dejar fuera de servicio (§16, A1 de la tanda 3).
    Permitido en cualquier estado salvo ciclo en curso y salvo un apagado ya
    en marcha (S9, D9-1.3: también con el estado seguro actuando; el apagado
    deja todas las salidas en cero): con FALLA, EMERGENCIA, paro,
    sin módulo E/S o con la cámara NO segura también se apaga (sin UPS, el
    personal técnico puede pedir dejar el equipo fuera de servicio). Solo desde
    la ventana principal (la UI de la puerta 1 envía ventana="principal").
    Confirmación: la de la propia UI; la cámara no segura solo se avisa allí."""
    entidad = "/system/shutdown"
    if body.get("ventana") != "principal":
        _rechazar(403, "solo_ventana_principal",
                  "Solo la ventana principal puede apagar el equipo", entidad)
    with guard_estado(DISTINTO_DE_CICLO, entidad) as estado:
        # TMG-05 de T7: un segundo apagado (doble toque) no lanza otra secuencia
        if getattr(context.control_loop, "apagando", False) is True:
            raise _Rechazo(409, "apagado_en_curso", "El equipo ya se está apagando")
        # S9 (tanda 9, D9-1.3): con el estado seguro activo también se apaga
        # (antes 409 "estado_seguro_activo"); queda en la bitácora
        estado_seguro_activo = getattr(getattr(context.control_loop, "estado_seguro", None),
                                       "activo", False) is True
        # A1: solo informativo; ya no condiciona el apagado. Cualquier fallo al
        # evaluar cuenta como "no segura" (falla cerrada).
        try:
            vigentes = getattr(context.control_loop, "datos_vigentes", False) is True
            segura, _motivo = camara_segura.evaluar(
                context.estado, context.config_manager, context.programas_para_seguridad(),
                getattr(context, "profile", None), datos_vigentes=vigentes,
                temp_max_ciclo=context.temp_max_tras_ciclo())
            segura = segura is True
        except Exception:
            logger.exception("Apagar equipo: no se pudo evaluar la cámara; se asume no segura")
            segura = False
        try:
            paro = bool(context.estado.get_flag("PARO_EMERGENCIA"))
        except Exception:
            paro = None
        modulo_es_conectado = getattr(context.control_loop, "desconectado", True) is not True
        en_modo_prueba = getattr(context.control_loop, "test_mode_active", False) is True
        # TMG-01 / SAF-01 de T7: en el mismo bloque que validó, sin soltar el
        # lock: ningún tick posterior puede pasar a CICLO ni mover salidas
        context.control_loop.iniciar_apagado()
    _auditar("apagar_equipo", entidad=entidad,
             detalle={"estado": getattr(estado, "name", str(estado)),
                      "motivo": "fuera de servicio solicitado",
                      "camara_segura": segura, "tarjeta_conectada": modulo_es_conectado,  # persistido (MES-03.2)
                      "paro_emergencia": paro, "modo_prueba": en_modo_prueba,
                      "estado_seguro_activo": estado_seguro_activo})
    try:
        threading.Thread(target=_secuencia_apagado, name="ApagarEquipo", daemon=False).start()
    except Exception:
        # sin hilo nuevo: el lazo ya está detenido, se apaga en línea
        logger.exception("Apagar equipo: no se pudo lanzar el hilo; se apaga en línea")
        _secuencia_apagado()
    return {"ok": True, "apagado_windows": _apagado_windows_habilitado(),
            "camara_segura": segura}


@router.get("/system/shutdown/estado")
def shutdown_estado():
    """D8-3.21: estado del apagado para la pantalla (sin sesión, como el
    propio apagado). `windows_rechazado`: Windows no permitió apagar."""
    with _apagado_lock:
        rechazado = _apagado_windows_rechazado
    return {"apagando": getattr(context.control_loop, "apagando", False) is True,
            "windows_rechazado": rechazado}


# ── Reiniciar el software (R11, tanda 11, D11-1) ───────────────────────────
# Mecanismo reutilizable: el cierre ordenado de "Apagar equipo" (ALL_OFF y
# parada del lazo, historial, escritura del ciclo, base de datos) SIN apagar
# Windows; luego el backend termina con CODIGO_REINICIO_SOFTWARE y el lanzador
# del ejecutable único cierra las pantallas y vuelve a abrir Autoclave.exe (una
# sola instancia: la nueva espera a que este proceso y el lanzador terminen y
# el puerto quede libre, ver exe_unico.esperar_instancia_anterior).
# Rechazado en CICLO; permitido en PREPARACION, PREPARADO y FALLA (y en los
# demás estados distintos de CICLO, igual que "Apagar equipo").

# SAF-02 (revisión R11): lectura, guardado y bloqueo de una solicitud con
# reinicio no se intercalan con otra (orden de cerrojos: este, luego _sm_lock)
_reinicio_lock = threading.Lock()


def _motivo_no_reiniciable() -> tuple[str, str] | None:
    """SAF-01 (revisión R11), criterio de R8 (_motivo_bloqueo) ampliado: no
    se reinicia con el protocolo de estado seguro sin terminar (actuando,
    pausado por el paro o esperando la confirmación de D9-1.2, que se perdería
    al reiniciar) ni en modo prueba o con el ALL_OFF de su salida sin
    confirmar. Llamar con _sm_lock tomado para una decisión firme."""
    loop = context.control_loop
    if getattr(loop, "test_mode_active", False) is True or _salidas_sin_confirmar_pendiente():
        return "modo_prueba_activo", "Salga primero del modo prueba de salidas"
    es = getattr(loop, "estado_seguro", None)
    if getattr(es, "activo", False) is True:
        if getattr(es, "requiere_confirmacion", False) is True:
            return "confirmacion_pendiente", "Confirme primero el estado seguro"
        return "estado_seguro_activo", "La cámara se está llevando a estado seguro"
    return None


def comprobar_reinicio_disponible(entidad: str, sesion: Sesion | None = None) -> None:
    """409 si ya se está apagando o reiniciando, o si _motivo_no_reiniciable;
    503 si nadie relanzaría el software (backend sin el lanzador del
    ejecutable único, p. ej. arrancado a mano). Para rechazar ANTES de cambiar
    nada (bloquear_para_reinicio lo repite bajo el lock)."""
    if getattr(context.control_loop, "apagando", False) is True or reinicio.solicitado():
        _rechazar(409, "apagado_en_curso", "El equipo ya se está apagando o reiniciando",
                  entidad, sesion)
    motivo = _motivo_no_reiniciable()
    if motivo is not None:
        _rechazar(409, motivo[0], motivo[1], entidad, sesion)
    if not reinicio.disponible():
        _rechazar(503, "reinicio_no_disponible",
                  "Sin lanzador que vuelva a abrir el software: no se puede reiniciar desde aquí",
                  entidad, sesion)


def bloquear_para_reinicio(entidad: str, sesion: Sesion | None = None, deshacer=None):
    """Vuelve a comprobar el estado bajo _sm_lock y, en ese mismo bloque,
    detiene el lazo y apaga las salidas (iniciar_apagado, como "Apagar
    equipo": ningún tick posterior puede pasar a CICLO). Ante un rechazo o
    error llama a `deshacer` (p. ej. devolver la bandera ya guardada) y lo
    propaga. Devuelve el estado observado."""
    try:
        comprobar_reinicio_disponible(entidad, sesion)
        with guard_estado(DISTINTO_DE_CICLO, entidad, sesion) as estado:
            if getattr(context.control_loop, "apagando", False) is True:
                raise _Rechazo(409, "apagado_en_curso",
                               "El equipo ya se está apagando o reiniciando")
            motivo = _motivo_no_reiniciable()
            if motivo is not None:
                raise _Rechazo(409, motivo[0], motivo[1])
            context.control_loop.iniciar_apagado()
        return estado
    except BaseException:
        if deshacer is not None:
            try:
                deshacer()
            except Exception:
                logger.exception("Reinicio del software: no se pudo deshacer el cambio previo")
        raise


def _secuencia_reinicio(motivo: str) -> None:
    _secuencia_apagado(apagar_windows=False)
    _cierre_ordenado_hecho.set()
    if not reinicio.solicitar(f"reinicio del software: {motivo}", retraso_s=0.5,
                              codigo=reinicio.CODIGO_REINICIO_SOFTWARE):
        # disponible() se comprobó antes; aquí solo si se perdió el registro
        logger.error("Reinicio del software: no se pudo detener el backend para relanzarlo")


def lanzar_reinicio(motivo: str, estado, sesion: Sesion | None = None,
                    entidad: str = "", detalle: dict | None = None) -> None:
    """Audita `software_reiniciado` (con la base aún abierta) y lanza el
    cierre ordenado en su hilo (la respuesta HTTP sale antes de cortar)."""
    _auditar("software_reiniciado", sesion, entidad=entidad,
             detalle={"motivo": motivo, "estado": getattr(estado, "name", str(estado)),
                      **(detalle or {})})
    try:
        threading.Thread(target=_secuencia_reinicio, args=(motivo,), name="ReiniciarSoftware",
                         daemon=False).start()
    except Exception:
        logger.exception("Reinicio del software: no se pudo lanzar el hilo; se cierra en línea")
        _secuencia_reinicio(motivo)


def reiniciar_software(motivo: str, sesion: Sesion | None = None, *, entidad: str = "",
                       detalle: dict | None = None, deshacer=None) -> None:
    """Reinicia el software (D11-1.4). Lanza HTTPException (409/503) si no se
    puede; en ese caso no cambia nada (y llama a `deshacer`)."""
    estado = bloquear_para_reinicio(entidad, sesion, deshacer)
    lanzar_reinicio(motivo, estado, sesion, entidad, detalle)
