# autoclave/backend/server.py



from fastapi import HTTPException, FastAPI, Body
from autoclave.backend.context import BackendContext

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
            "camara_2": estado.sensores_temp.get("temp_camara_2"),
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
        "machine_state": machine_state,
        "doors": doors,
        "sensors": sensors,
        "alarms": alarms,
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

@app.post("/doors/{door_name}/open")
def open_door(door_name: str, body: dict = Body(...)):
    source_door = body.get("source_door")

    if not context.servicio_puertas.request_open(door_name):
        raise HTTPException(
            status_code=403,
            detail="Apertura de puerta no permitida"
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

    if not context.servicio_puertas.request_close(door_name):
        raise HTTPException(
            status_code=403,
            detail="Cierre de puerta no permitido"
        )

    return {
        "ok": True,
        "door": door_name,
        "action": "close",
        "source_door": source_door,
    }
