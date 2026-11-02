# simulador/reportes_sim.py
#
# Rutas de solo lectura de la pantalla Reportes en el backend SIMULADO:
# /report/dashboard, /report/calendar, /report/day-cycles, /report/failures,
# /maintenance y /maintenance/records. Usan la MISMA lógica del backend real
# (backend/rutas/reportes.py: armar_dashboard, armar_calendario, armar_dia;
# services/domain/reportes/dashboard.py) sobre una base abierta en SOLO LECTURA
# (uri mode=ro; no se crea ni se migra). Sin base: respuestas vacías coherentes.
# Sin ciclo activo real en este contexto (activo = None).

import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Query

from autoclave.core.runtime import progreso_ciclo
from autoclave.services.domain.logging import ticket_formatter
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.reportes import consultas as rep
from autoclave.utils import periodos

_Periodo = Literal["dia", "semana", "mes", "anio"]
_Fecha = Annotated[date | None, Query(ge=periodos.FECHA_MINIMA, le=periodos.FECHA_MAXIMA)]


class BdSoloLectura:
    """Reutiliza las consultas de DbManager sobre una conexión mode=ro. Si la
    base no existe (o no se puede abrir) todas devuelven vacío."""

    def __init__(self, ruta):
        self._db = None
        try:
            ruta = Path(ruta)
            if ruta.is_file():
                conn = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True,
                                       check_same_thread=False, timeout=5.0)
                conn.row_factory = sqlite3.Row
                db = DbManager.__new__(DbManager)   # sin __init__: no crea ni migra
                db._lock = threading.Lock()
                db._conn = conn
                self._db = db
        except Exception:
            self._db = None

    def _consulta(self, nombre, vacio, *args):
        if self._db is None:
            return vacio
        try:
            return getattr(self._db, nombre)(*args)
        except Exception:   # tabla ausente en una base antigua
            return vacio

    def get_ciclos_periodo(self, desde, hasta):
        return self._consulta("get_ciclos_periodo", [], desde, hasta)

    def get_alarmas_periodo(self, desde, hasta):
        return self._consulta("get_alarmas_periodo", [], desde, hasta)

    def get_ciclos_con_resultado(self, desde, hasta, resultado, limite, desplazamiento):
        return self._consulta("get_ciclos_con_resultado", ([], 0),
                              desde, hasta, resultado, limite, desplazamiento)


def _no_conforme_json(f) -> dict:
    """Mismo contenido que backend/rutas/_comun._no_conforme_json (nunca lanza)."""
    salida = {}
    try:
        if ticket_formatter.ciclo_no_conforme(f):
            salida.update({"no_conforme": True,
                           "motivo_no_conforme": ticket_formatter.CLAVE_NO_CONFORME})
        _, avisos = ticket_formatter.leer_avisos_ticket(f.get("avisos_ticket"))
        obs = progreso_ciclo.observaciones_de_avisos(avisos)
        if obs:
            salida["observaciones"] = obs
    except Exception:
        pass
    return salida


def registrar_reportes(app: FastAPI, cycle_manager, bd, ahora=datetime.now) -> None:
    db = bd if hasattr(bd, "get_ciclos_periodo") else BdSoloLectura(bd)

    def numeros() -> dict:
        return {t: getattr(c, "number", None) for t, c in list(cycle_manager.cycles.items())}

    def hoy() -> date:
        return ahora().date()

    def ciclo_json(f) -> dict:
        programa = cycle_manager.cycles.get(f["tipo_ciclo"])
        return {"id": f["id"], "numero_ciclo": f["numero_ciclo"],
                "fecha_inicio": f["fecha_inicio"], "fecha_fin": f["fecha_fin"],
                "programa_id": f["tipo_ciclo"], "programa_nombre": f["nombre_ciclo"],
                "programa_numero": getattr(programa, "number", None),
                "resultado": f["resultado"], "operador": f.get("operador") or None,
                **_no_conforme_json(f)}

    @app.get("/report/dashboard")
    def dashboard(periodo: _Periodo = "dia", fecha: _Fecha = None):
        return rep.armar_dashboard(db, periodo, fecha or hoy(), numeros())

    @app.get("/report/calendar")
    def calendar(periodo: _Periodo = "mes", fecha: _Fecha = None,
                 programa: int | None = Query(None, ge=1)):
        return rep.armar_calendario(db, periodo, fecha or hoy(), programa, numeros(),
                                    cycle_manager.cycles, None, hoy())

    @app.get("/report/day-cycles")
    def day_cycles(programa: int = Query(ge=1), fecha: _Fecha = None):
        return rep.armar_dia(db, programa, fecha or hoy(), numeros(), None, hoy(), ciclo_json)

    @app.get("/report/failures")
    def failures(causa: str = Query(min_length=1), periodo: _Periodo = "dia",
                 fecha: _Fecha = None, pagina: int = Query(1, ge=1),
                 por_pagina: int = Query(20, ge=1, le=100)):
        ini, fin = periodos.rango(periodo, fecha or hoy())
        desde, hasta = rep._iso(ini), rep._iso(fin)
        _, total = db.get_ciclos_con_resultado(desde, hasta, causa, 1, 0)
        paginas = max(1, -(-total // por_pagina))
        pagina = min(pagina, paginas)
        filas, total = db.get_ciclos_con_resultado(desde, hasta, causa, por_pagina,
                                                   (pagina - 1) * por_pagina)
        return {"periodo": periodo, "desde": ini.isoformat(),
                "hasta": (fin - timedelta(days=1)).isoformat(), "causa": causa,
                "total": total, "pagina": pagina, "paginas": paginas,
                "por_pagina": por_pagina, "ciclos": [ciclo_json(dict(f)) for f in filas]}

    @app.get("/maintenance")
    def maintenance():
        # sin mantenimiento registrado: mismo molde que el estado «sin dato» real
        from autoclave.core.runtime import mantenimiento as m
        return {**m.EstadoMantenimiento(m.SIN_DATO).a_dict(),
                "configuracion": {"intervalo_dias": m.INTERVALO_DIAS_DEFECTO,
                                  "intervalo_ciclos": m.INTERVALO_CICLOS_DEFECTO},
                "ciclos_actuales": None}

    @app.get("/maintenance/records")
    def maintenance_records(limite: int = 50):
        return {"registros": []}
