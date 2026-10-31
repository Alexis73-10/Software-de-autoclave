# autoclave/backend/rutas/alarmas.py
#
# Rutas de alarmas (/alarms).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

from datetime import datetime
from fastapi import HTTPException, Body
from autoclave.state_machine.alarms.catalogo import Nivel
from fastapi import APIRouter

from autoclave.backend.dependencias import context
from autoclave.backend.rutas._comun import _i18n_t

router = APIRouter()


@router.post("/alarms/{clave}/acknowledge")
def acknowledge_alarm(clave: str, body: dict = Body(default={})):
    """El operador reconoce una alarma ALARMA/FALLO_CRITICO (spec §7.2)."""
    usuario = str(body.get("usuario") or "").strip()
    if not usuario:
        raise HTTPException(status_code=422, detail="Falta el usuario que reconoce")
    inst = context.alarm_manager.obtener(clave)
    if inst is None:
        raise HTTPException(status_code=404, detail="La alarma no está activa")
    if not inst.nivel.requiere_reconocimiento:
        raise HTTPException(status_code=422, detail="Esta alarma no requiere reconocimiento")
    # T2-b (tanda 7): COM-02/03 solo se despejan con el enlace de vuelta en "ok"
    if context.alarm_manager.despeje_bloqueado(clave) is True:
        raise HTTPException(status_code=409, detail=_i18n_t("notificaciones.despejar_sin_enlace"))
    if not context.alarm_manager.reconocer(clave, usuario):
        if context.alarm_manager.despeje_bloqueado(clave) is True:   # el enlace cayó en medio
            raise HTTPException(status_code=409,
                                detail=_i18n_t("notificaciones.despejar_sin_enlace"))
        # Se resolvió y retiró entre obtener() y reconocer().
        raise HTTPException(status_code=404, detail="La alarma no está activa")
    return {"ok": True}


def _fecha_iso_o_422(valor: str | None, campo: str) -> str | None:
    if valor is None:
        return None
    try:
        datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo} no es una fecha ISO válida")
    return valor


@router.get("/alarms/history")
def alarm_history(desde: str | None = None, hasta: str | None = None,
                  nivel: str | None = None, limite: int = 200):
    if nivel is not None and nivel not in Nivel.__members__:
        raise HTTPException(status_code=422, detail="Nivel desconocido")
    filas = context.db.get_alarmas_historial(
        _fecha_iso_o_422(desde, "desde"), _fecha_iso_o_422(hasta, "hasta"),
        nivel, max(1, min(int(limite), 1000)),
    )
    return {"alarmas": filas}
