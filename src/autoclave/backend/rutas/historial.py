# autoclave/backend/rutas/historial.py
#
# Historial de ciclos (/cycle/summary, /cycle/list, /cycle/history).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

from datetime import date, timedelta
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field
from autoclave.core.runtime import progreso_ciclo
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from fastapi import APIRouter

from autoclave.backend.dependencias import context
from autoclave.backend.rutas._comun import (_ciclo_json, _encolar_en_impresora,
    _inicio_del_dia, _no_conforme_json, _rango_del_periodo)

router = APIRouter()


@router.get("/cycle/summary")
def get_cycle_summary():
    """Resumen de solo lectura para el Resumen del Sistema del Menú Principal
    (planeacion_menu_principal_ui_qml.md, D-14)."""
    r = context.db.get_resumen_ciclos(_inicio_del_dia())
    ultimo = _ciclo_json(r["ultimo"]) if r["ultimo"] is not None else None
    return {
        "ciclos_totales": r["total"],   # TODO(MP-06a): último numero_ciclo, no contador persistente
        "ciclos_hoy":     r["hoy"],
        "ultimo_ciclo":   ultimo,
    }


@router.get("/cycle/list")
def get_cycle_list(periodo: Literal["dia", "semana", "mes"] = "dia",
                   fecha: date | None = None,
                   terminados: bool = False, limite: int = 500):
    """Ciclos del periodo de calendario que contiene `fecha` (por defecto hoy), más
    recientes primero; solo lectura. Lo usan la ventana de Ciclos hoy (periodo=dia,
    terminados=true: los mismos que cuenta /cycle/summary) y la de Historial (por
    fecha de inicio, con los interrumpidos). truncado = había más de `limite`;
    desde/hasta = primer y último día del periodo, para rotularlo."""
    limite = max(1, min(limite, 2000))
    if fecha is None:
        fecha = date.fromisoformat(_inicio_del_dia()[:10])
    desde, hasta = _rango_del_periodo(periodo, fecha)
    filas = context.db.get_ciclos_desde(desde, terminados, limite + 1, hasta=hasta)
    return {
        "periodo":   periodo,
        "desde":     desde[:10],
        "hasta":     (date.fromisoformat(hasta[:10]) - timedelta(days=1)).isoformat(),
        "ciclos":    [_ciclo_json(f) for f in filas[:limite]],
        "truncado":  len(filas) > limite,
    }


class _ImprimirCiclosBody(BaseModel):
    ids: list[int] = Field(min_length=1)


@router.post("/cycle/history/print")
def print_cycle_history(body: _ImprimirCiclosBody):
    """Reimprime en la impresora térmica el ticket de cada ciclo pedido, en ese
    orden (404 y nada impreso si alguno no existe; 409/503: _encolar_en_impresora)."""
    tickets = []
    for ciclo_id in body.ids:
        ciclo = context.db.get_ciclo(ciclo_id)
        if ciclo is None:
            raise HTTPException(status_code=404, detail=f"Ciclo {ciclo_id} no encontrado")
        lecturas = [dict(r) for r in context.db.get_lecturas_para_imprimir(ciclo_id)]
        tickets.append(format_ticket(dict(ciclo), lecturas))
    _encolar_en_impresora(tickets)
    return {"ok": True, "impresos": len(tickets)}


@router.get("/cycle/history/{ciclo_id}/graph")
def get_cycle_history_graph(ciclo_id: int):
    """Serie de la gráfica (lecturas_grafica, ~1 s, t_s monotónico) de un ciclo
    del historial, con el mismo formato que /cycle/current/graph. Solo lectura;
    la usa la ventana flotante de Último ciclo del Menú Principal (D-21)."""
    if context.db.get_ciclo(ciclo_id) is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    rows = context.db.get_lecturas_grafica(ciclo_id)
    return {
        "ciclo_db_id": ciclo_id,
        "lecturas": [
            {
                "id":          r["id"],
                "t_s":         r["t_s"],
                "fase":        r["fase"],
                "fase_ui":     progreso_ciclo.fase_ui(r["fase"]),
                "temp_camara": r["temp_camara"],
                "temp_ref":    r["temp_ref"],
                "pres_camara": r["pres_camara"],
            }
            for r in rows
        ],
    }


@router.get("/cycle/history")
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
            **_no_conforme_json(r),   # P4 (tanda 16, D-14.4)
        }
        for r in rows
    ]


@router.get("/cycle/history/{ciclo_id}/readings")
def get_cycle_readings(ciclo_id: int):
    """Todas las lecturas de un ciclo histórico."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_ciclo(ciclo_id)
    return {
        "ciclo": {**dict(ciclo), **_no_conforme_json(ciclo)},   # P4 (D-14.4)
        "lecturas": [dict(r) for r in rows],
    }


@router.get("/cycle/history/{ciclo_id}/ticket")
def get_cycle_ticket(ciclo_id: int):
    """Lecturas marcadas para_imprimir (formato ticket)."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_para_imprimir(ciclo_id)
    return {
        "ciclo":    {**dict(ciclo), **_no_conforme_json(ciclo)},   # P4 (D-14.4)
        "lecturas": [dict(r) for r in rows],
    }
