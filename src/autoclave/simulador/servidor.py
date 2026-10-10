# simulador/servidor.py
#
# BACKEND SIMULADO para probar la UI QML sin tarjeta (herramienta de desarrollo).
# Responde los endpoints que usa la UI con un equipo "listo para ciclo" y, al
# iniciar, reproduce acelerado un ciclo COMPLETADO guardado (repeticion.py).
# No importa el control, la máquina de estados ni el hardware; no escribe la BD.
# Comportamiento de los comandos, como el backend real:
#   /cycle/start       solo con LISTO_PARA_CICLO (puertas cerradas)      -> CICLO
#   /cycle/abort       solo en CICLO; congela el ciclo en "CANCELADO"
#   /cycle/acknowledge solo en CICLO y con el ciclo ya terminado        -> PREPARADO
# Las alarmas siempre vienen vacías.
# Sesión y usuarios (T-14): mismo contrato que el backend real, ver
# autenticacion_simulada.py.

import time

from fastapi import Body, FastAPI, HTTPException

from autoclave.backend.actividad_ui import ActividadUI
from autoclave.core.runtime import progreso_ciclo
from autoclave.simulador.autenticacion_simulada import registrar_autenticacion

_PUERTAS = ("Puerta 1", "Puerta 2")


class _Estado:
    def __init__(self, repeticion, velocidad, reloj):
        self.rep = repeticion
        self.velocidad = float(velocidad)
        self.reloj = reloj
        self.en_ciclo = False
        self.t0 = None              # reloj real al iniciar
        self.t_cancelado = None     # segundos simulados al cancelar
        self.ciclo_id = 0
        self.puertas = {p: "CERRADO" for p in _PUERTAS}

    def t_sim(self) -> float:
        if not self.en_ciclo:
            return 0.0
        if self.t_cancelado is not None:
            return self.t_cancelado
        return min((self.reloj() - self.t0) * self.velocidad, float(self.rep.duracion_s))

    def fase_ciclo(self) -> str:
        if not self.en_ciclo:
            return ""
        if self.t_cancelado is not None:
            return "CANCELADO"
        t = self.t_sim()
        return "COMPLETADO" if t >= self.rep.duracion_s else self.rep.fase_en(t)

    def terminado(self) -> bool:
        return progreso_ciclo.resultado(self.fase_ciclo()) is not None

    def listo(self) -> bool:
        return not self.en_ciclo and all(e == "CERRADO" for e in self.puertas.values())


def crear_app(repeticion, cycle_manager, config: dict, velocidad: float = 10.0,
              reloj=time.monotonic) -> FastAPI:
    app = FastAPI(title="Autoclave — backend SIMULADO")
    est = _Estado(repeticion, velocidad, reloj)
    actividad = ActividadUI()
    registrar_autenticacion(app, reloj=reloj)

    def _referencias():
        ref = {}
        for fase, t0, t1 in repeticion.tramos:
            ui = progreso_ciclo.fase_ui(fase)
            ref[ui] = ref.get(ui, 0.0) + (t1 - t0)
        return ref

    aplicables = []
    for fase, _, _ in repeticion.tramos:
        ui = progreso_ciclo.fase_ui(fase)
        if ui not in aplicables:
            aplicables.append(ui)

    @app.get("/status")
    def status():
        m = repeticion.muestra(est.t_sim())
        return {
            "machine_state": "CICLO" if est.en_ciclo else "PREPARADO",
            "fase_ciclo": est.fase_ciclo(),
            "fase_en_sostenimiento": False,
            "prevacio_progreso": "",
            "card_connected": True,
            "test_mode_active": False,
            "ui_inactividad_s": actividad.inactividad_s(),
            "doors": dict(est.puertas),
            "sensors": {
                "temperature": {"camara": m["temp_camara"], "camara_2": None, "ref": m["temp_ref"],
                                "drenaje": None, "drenaje_camara": None},
                "pressure": {"camara": m["pres_camara"], "chaqueta": None,
                             "empaque_1": None, "empaque_2": None},
                "digital_inputs": {},
                "digital_outputs": {},
                "flags": {"LISTO_PARA_CICLO": est.listo()},
            },
            "alarms": [],
        }

    @app.post("/ui/activity")
    def ui_activity():
        actividad.registrar()
        return {"ok": True}

    @app.get("/global_params")
    def global_params():
        return config

    @app.get("/cycle")
    def cycle():
        c = cycle_manager.get_selected_cycle()
        return {"id": c.id, "name": c.name, "number": getattr(c, "number", None),
                "parameters": c.parameters}

    @app.get("/cycles")
    def cycles():
        return [{"id": c.id, "name": c.name, "source": getattr(c, "source", "user")}
                for c in cycle_manager.cycles.values()]

    @app.post("/cycle/start")
    def start():
        if not est.listo():
            raise HTTPException(status_code=409, detail="El sistema no está listo para iniciar un ciclo")
        est.en_ciclo, est.t0, est.t_cancelado = True, reloj(), None
        est.ciclo_id += 1
        return {"ok": True, "action": "START_CICLO"}

    @app.post("/cycle/abort")
    def abort():
        if not est.en_ciclo:
            raise HTTPException(status_code=409, detail="No hay un ciclo en curso")
        if not est.terminado():
            est.t_cancelado = est.t_sim()
        return {"ok": True, "action": "CICLO_CANCELADO"}

    @app.post("/cycle/acknowledge")
    def acknowledge():
        if not est.en_ciclo:
            raise HTTPException(status_code=409, detail="No hay un ciclo esperando confirmación")
        if est.terminado():
            est.en_ciclo, est.t0, est.t_cancelado = False, None, None
        return {"ok": True, "action": "CICLO_CONFIRMADO"}

    @app.get("/cycle/current/progress")
    def progress():
        if not est.en_ciclo:
            return {"activo": False}
        t = est.t_sim()
        fase = est.fase_ciclo()
        filas = []
        for f, t0, t1 in repeticion.tramos:
            if t0 > t or (t0 == t and filas):
                break
            cerrada = t1 <= t or progreso_ciclo.fase_ui(fase) != progreso_ciclo.fase_ui(f)
            fin = min(t1, t) if cerrada else None
            filas.append({"fase": f, "inicio_s": float(t0), "fin_s": fin,
                          "duracion_s": (fin - t0) if cerrada else None})
        return {"activo": True, "ciclo_db_id": est.ciclo_id, "fase_ciclo": fase,
                **progreso_ciclo.armar_progreso(aplicables, filas, fase, t, _referencias())}

    @app.get("/cycle/current/graph")
    def graph(desde_id: int | None = None):
        if not est.en_ciclo:
            return {"ciclo_db_id": None, "lecturas": []}
        lecturas = []
        for s in range(int(desde_id or 0), int(est.t_sim()) + 1):   # id = s + 1
            m = repeticion.muestra(s)
            lecturas.append({"id": s + 1, "t_s": float(s), "fase": m["fase"],
                             "fase_ui": progreso_ciclo.fase_ui(m["fase"]),
                             "temp_camara": m["temp_camara"], "temp_ref": m["temp_ref"],
                             "pres_camara": m["pres_camara"]})
        return {"ciclo_db_id": est.ciclo_id, "lecturas": lecturas}

    @app.get("/cycle/current/readings")
    def readings():
        return {"ciclo_id": None, "lecturas": []}

    @app.get("/cycle/history")
    def history(limite: int = 50):
        return []

    @app.post("/doors/{nombre}/open")
    def abrir(nombre: str, body: dict = Body(default={})):
        if nombre not in est.puertas:
            raise HTTPException(status_code=404, detail="Puerta desconocida")
        if est.en_ciclo:
            raise HTTPException(status_code=403, detail="Apertura de puerta no permitida durante el ciclo")
        est.puertas[nombre] = "ABIERTO"
        return {"ok": True, "door": nombre, "action": "open"}

    @app.post("/doors/{nombre}/close")
    def cerrar(nombre: str, body: dict = Body(default={})):
        if nombre not in est.puertas:
            raise HTTPException(status_code=404, detail="Puerta desconocida")
        est.puertas[nombre] = "CERRADO"
        return {"ok": True, "door": nombre, "action": "close"}

    @app.post("/fault/reset")
    def fault_reset():
        raise HTTPException(status_code=409, detail="El sistema no está en estado de falla")

    return app
