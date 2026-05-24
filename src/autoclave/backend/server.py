# autoclave/backend/server.py



import logging
from fastapi import HTTPException, FastAPI, Body
from autoclave.backend.context import BackendContext

logger = logging.getLogger(__name__)

app = FastAPI(title="Autoclave Backend")

context = BackendContext()

@app.get("/status", response_model=None)
def get_status():
    estado = context.estado

    # ------------------------------
    # ESTADO DE LA MÁQUINA
    # ------------------------------
    machine_state = None
    try:
        machine_state = estado.get_machine_state().name
    except Exception:
        machine_state = "DESCONOCIDO"

    # ------------------------------
    # ESTADO DE PUERTAS
    # ------------------------------
    doors = {
        door_name: door_state.name
        for door_name, door_state in estado.estado_puertas.items()
    }

    # ------------------------------
    # SENSORES
    # ------------------------------
    sensors = {
        "temperature": {
            "camara": estado.sensores_temp.get("temp_camara"),
            "camara_2": estado.sensores_temp.get("temp_2_camara"),
            "ref": estado.sensores_temp.get("temp_ref"),
            "chaqueta": estado.sensores_temp.get("temp_chaqueta"),
            "drenaje": estado.sensores_temp.get("temp_drenaje"),
            "drenaje_camara": estado.sensores_temp.get("temp_drenaje_cam"),


        },
        "pressure": {
            "camara": estado.sensores_pres.get("pres_camara"),
            "chaqueta": estado.sensores_pres.get("pres_chaqueta"),
            "empaque_1": estado.sensores_pres.get("pres_empaque_1"),
            "empaque_2": estado.sensores_pres.get("pres_empaque_2"),
        },
        "digital_inputs": dict(estado.sensores_di),

        "digital_outputs": dict(estado.salidas_do),

        "flags": dict(estado.flags),
    }

    # ------------------------------
    # ALARMAS
    # ------------------------------
    alarms = [
        {
            "id": alarma.id,
            "level": alarma.type.name,
        }
        for alarma in estado.Alarmas_activas
    ]

    # ------------------------------
    # RESPUESTA FINAL (DTO)
    # ------------------------------
    return {
        "machine_state":        machine_state,
        "fase_ciclo":            getattr(estado, "fase_ciclo", ""),
        "fase_en_sostenimiento": getattr(estado, "fase_en_sostenimiento", False),
        "prevacio_progreso":     getattr(estado, "prevacio_progreso", ""),
        "doors":   doors,
        "sensors": sensors,
        "alarms":  alarms,
    }

@app.get("/global_params")
def get_global_params():
    return context.config_manager.get()


@app.get("/cycle")
def get_selected_cycle():
    cycle = context.cycle_manager.get_selected_cycle()

    if cycle is None:
        raise HTTPException(status_code=404, detail="No hay ciclo seleccionado")

    return {
        "id": cycle.id,
        "name": cycle.name,
        "parameters": cycle.parameters
    }

@app.get("/cycle/current/readings")
def get_current_cycle_readings():
    """
    Retorna todas las lecturas del ciclo activo (para la gráfica en vivo).
    Si no hay ciclo activo retorna lista vacía.
    """
    logger_svc = context.cycle_logger
    ciclo_id   = logger_svc.ciclo_id if logger_svc else None

    if ciclo_id is None:
        return {"ciclo_id": None, "lecturas": []}

    rows = context.db.get_lecturas_ciclo(ciclo_id)
    return {
        "ciclo_id": ciclo_id,
        "lecturas": [
            {
                "timestamp_rel": r["timestamp_rel"],
                "timestamp_abs": r["timestamp_abs"],
                "fase_codigo":   r["fase_codigo"],
                "temp_camara":   r["temp_camara"],
                "pres_camara":   r["pres_camara"],
            }
            for r in rows
        ],
    }


@app.get("/cycle/history")
def get_cycle_history(limite: int = 50):
    """Lista de ciclos registrados (más recientes primero)."""
    rows = context.db.get_ciclos_recientes(limite)
    return [
        {
            "id":            r["id"],
            "numero_ciclo":  r["numero_ciclo"],
            "fecha_inicio":  r["fecha_inicio"],
            "fecha_fin":     r["fecha_fin"],
            "nombre_ciclo":  r["nombre_ciclo"],
            "resultado":     r["resultado"],
        }
        for r in rows
    ]


@app.get("/cycle/history/{ciclo_id}/readings")
def get_cycle_readings(ciclo_id: int):
    """Todas las lecturas de un ciclo histórico."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_ciclo(ciclo_id)
    return {
        "ciclo": dict(ciclo),
        "lecturas": [dict(r) for r in rows],
    }


@app.get("/cycle/history/{ciclo_id}/ticket")
def get_cycle_ticket(ciclo_id: int):
    """Lecturas marcadas para_imprimir (formato ticket)."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_para_imprimir(ciclo_id)
    return {
        "ciclo":    dict(ciclo),
        "lecturas": [dict(r) for r in rows],
    }


@app.post("/cycle/start")
def start_cycle():
    """
    Solicita el inicio del ciclo de esterilización.
    Sólo tiene efecto cuando el sistema está en estado PREPARADO y
    la flag LISTO_PARA_CICLO es True.  La máquina de estados gestiona
    la transición real.
    """
    estado = context.estado

    if not estado.get_flag("LISTO_PARA_CICLO"):
        raise HTTPException(
            status_code=409,
            detail="El sistema no está listo para iniciar un ciclo"
        )

    estado.set_flag("START_CICLO", True)
    return {"ok": True, "action": "START_CICLO"}


@app.post("/cycle/abort")
def abort_cycle():
    """
    Solicita el aborto del ciclo en curso.
    Activa la flag CICLO_CANCELADO; el CicloState ejecutará el
    protocolo de fallo en el siguiente tick del control loop.
    """
    estado = context.estado

    from autoclave.state_machine.machine.enum_global import GlobalState
    if estado.get_machine_state() != GlobalState.CICLO:
        raise HTTPException(
            status_code=409,
            detail="No hay un ciclo en curso"
        )

    estado.set_flag("CICLO_CANCELADO", True)
    return {"ok": True, "action": "CICLO_CANCELADO"}


@app.post("/fault/reset")
def reset_fault():
    """Reconoce el estado de falla y solicita retornar a PREPARACION."""
    if context.estado.get_machine_state().name != "FALLA":
        raise HTTPException(
            status_code=409,
            detail="El sistema no está en estado de falla"
        )
    context.estado.set_flag("RESET_FALLA", True)
    return {"ok": True, "action": "RESET_FALLA"}


@app.post("/outputs/reset")
def reset_outputs():
    """
    Apaga todas las salidas digitales.
    Llamar antes de cerrar la aplicación o ante cualquier apagado seguro.
    """
    try:
        context.control_loop.stop()   # evita que el loop re-active salidas durante el reset
        context.setdo.reset_all_outputs()
        logger.info("outputs/reset: todas las salidas apagadas")
        return {"ok": True}
    except Exception as e:
        logger.error("outputs/reset error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cycle/acknowledge")
def acknowledge_cycle():
    """
    El operador confirmó que vio el resultado del ciclo.
    Activa CICLO_CONFIRMADO para que CicloState libere la transición.
    Solo tiene efecto mientras el estado sea CICLO (esperando confirmación).
    """
    estado = context.estado

    from autoclave.state_machine.machine.enum_global import GlobalState
    if estado.get_machine_state() != GlobalState.CICLO:
        raise HTTPException(
            status_code=409,
            detail="No hay un ciclo esperando confirmación"
        )

    estado.set_flag("CICLO_CONFIRMADO", True)

    # Si el ciclo terminó en fallo/emergencia el operador ya lo vio en CycleWindow.
    # Pre-armar RESET_FALLA para que la máquina salte el estado FALLA y vuelva
    # directo a PREPARACION sin requerir un segundo "RECONOCER FALLA".
    fase = getattr(estado, "fase_ciclo", "")
    if fase and (fase.startswith("FALLO_") or fase == "EMERGENCIA"):
        estado.set_flag("RESET_FALLA", True)

    return {"ok": True, "action": "CICLO_CONFIRMADO"}


@app.post("/doors/{door_name}/open")
def open_door(door_name: str, body: dict = Body(...)):
    source_door = body.get("source_door")

    ok, reason = context.servicio_puertas.request_open(door_name)
    if not ok:
        raise HTTPException(
            status_code=403,
            detail=reason or "Apertura de puerta no permitida"
        )

    return {
        "ok": True,
        "door": door_name,
        "action": "open",
        "source_door": source_door,
    }


@app.post("/doors/{door_name}/close")
def close_door(door_name: str, body: dict = Body(...)):
    source_door = body.get("source_door")

    ok, reason = context.servicio_puertas.request_close(door_name)
    if not ok:
        raise HTTPException(
            status_code=403,
            detail=reason or "Cierre de puerta no permitido"
        )

    return {
        "ok": True,
        "door": door_name,
        "action": "close",
        "source_door": source_door,
    }
