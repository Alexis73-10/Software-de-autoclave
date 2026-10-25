# autoclave/backend/rutas/puertas.py
#
# Rutas de puertas (/doors).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

from fastapi import HTTPException, Body
from autoclave.core.runtime import motivos
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO_E_HIBERNACION, RechazoApi,
    _Rechazo, _log_desarrollo, _rechazar, _rechazar_si_config_invalida, context, guard_estado)
from autoclave.backend.rutas._comun import _campos_motivo

router = APIRouter()


def _orden_puerta(door_name: str, accion: str, source_door) -> dict:
    """Abrir o cerrar una puerta (§5.3, T-13 y T-18).

    Guard de estado: 409 en CICLO (P-8: sin HIBERNACION ni EMERGENCIA; en PREPARACION,
    PREPARADO y FALLA se permite). Las condiciones físicas las aplica
    ServicioPuertas, fallando cerradas; si las incumple, o si la puerta no
    acepta la orden (bloqueo mecánico, no está abierta), 409 con el motivo.
    La comprobación y la orden van bajo _sm_lock para no intercalarse con el
    tick. `sin_actuador`: la puerta no tiene actuador (SimpleDoor) y la orden
    no mueve nada.

    `source_door` (S3e, tanda 2): la puerta que controla la pantalla que manda
    la orden (1 o 2), DECLARADA por el cliente, no autenticada. Cada pantalla
    opera solo su puerta: otra puerta se rechaza (409 `puerta_ajena`), un valor
    fuera de rango es inválido (422 `source_door_invalido`) y cada orden,
    aceptada o rechazada, queda en audit_log con el origen. Ausente (clientes
    antiguos) se acepta y queda como "desconocido". `door_id` del perfil NO
    interviene: identifica la ventana principal del PC, no qué puerta opera
    cada pantalla."""
    entidad = f"/doors/{door_name}/{accion}"
    _rechazar_si_config_invalida(entidad)
    servicio = context.servicio_puertas
    if door_name not in servicio.doors:
        raise HTTPException(status_code=404, detail="Puerta desconocida")
    origen = "desconocido" if source_door is None else source_door

    def rechazo_origen(status: int, codigo: str, motivo: str):
        _log_desarrollo("puerta_orden_rechazada", entidad=door_name, accion=accion,
                        source_door=origen, codigo=codigo, motivo=motivo)   # D9-6
        raise RechazoApi(status, codigo, motivo)

    if source_door is not None:
        valido = (isinstance(source_door, int) and not isinstance(source_door, bool)
                  and 1 <= source_door <= len(servicio.doors))
        if not valido:
            rechazo_origen(422, "source_door_invalido",
                           f"source_door inválido: {str(source_door)[:20]!r} "
                           f"(1 a {len(servicio.doors)})")
        if door_name != f"Puerta {source_door}":
            rechazo_origen(409, "puerta_ajena",
                           f"La pantalla de la puerta {source_door} solo opera su puerta")
    rechazo_puerta = None
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, entidad):
        # con el modo prueba las puertas no se actualizan, y con el enlace
        # caído las lecturas son viejas: la orden quedaría para después sin
        # revalidar (revisión de seguridad de la etapa 2, SAF-04)
        if context.control_loop.test_mode_active is True:
            raise _Rechazo(409, "modo_prueba_activo", "No permitido con el modo prueba activo")
        if context.control_loop.desconectado is True:
            raise _Rechazo(409, "sin_conexion_tarjeta", "Sin conexión con la tarjeta de control")
        pedir = servicio.request_open if accion == "open" else servicio.request_close
        ok, reason = pedir(door_name)
        if not ok:
            rechazo_puerta = reason or motivos.Motivo("no_permitida", "Orden de puerta no permitida")
    if rechazo_puerta is not None:
        # I4 (tanda 6): el motivo viaja también con código, parámetros y textos
        # es/en (`detail` sigue siendo el español). Se arma con _sm_lock ya
        # libre: lee la configuración de unidades del disco.
        _rechazar(409, "puerta_rechazada", rechazo_puerta, entidad,
                  extra=_campos_motivo(rechazo_puerta))
    _log_desarrollo("puerta_orden", entidad=door_name, accion=accion,
                    source_door=origen)   # D9-6
    return {
        "ok": True,
        "door": door_name,
        "action": accion,
        "source_door": source_door,
        "sin_actuador": not servicio.tiene_actuador(door_name),
    }


@router.post("/doors/{door_name}/open")
def open_door(door_name: str, body: dict = Body(...)):
    return _orden_puerta(door_name, "open", body.get("source_door"))


@router.post("/doors/{door_name}/close")
def close_door(door_name: str, body: dict = Body(...)):
    return _orden_puerta(door_name, "close", body.get("source_door"))
