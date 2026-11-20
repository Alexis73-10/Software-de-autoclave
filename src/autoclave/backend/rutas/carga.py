# autoclave/backend/rutas/carga.py
#
# Catálogo de carga (RCB-08, registro de la carga con lector, 19-nov;
# docs/mis_plans/planeacion_registro_carga.md §9). Código → nombre de los
# elementos que se leen con el lector en la ventana «Carga del ciclo».
#
# - GET /carga/catalogo: sin rol, solo lectura (Preciclo muestra los nombres
#   en vivo; `?activos=true` solo los activos).
# - POST /carga/catalogo (alta), PATCH /carga/catalogo/{id} (nombre y/o baja /
#   reactivación), GET /carga/catalogo/usb (CSV en las USB) y
#   POST /carga/catalogo/importar (vista previa o aplicación, todo o nada):
#   ingeniero o admin.
# - Bitácora (categoría configuración): catalogo_carga_alta, _editado, _baja,
#   _reactivado e _importado (con conteos, sin la lista).
# Nada aquí toca el control del ciclo ni las salidas.

import logging
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StrictBool

from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO
from autoclave.backend.autenticacion import Sesion
from autoclave.backend.dependencias import RechazoApi, _auditar, context, requiere_rol
# mismo descubrimiento de unidades que el respaldo (un solo objeto: las pruebas
# lo parchean en los dos módulos a la vez)
from autoclave.backend.rutas.respaldo import _unidades_usb
from autoclave.core.runtime import registro_carga as rc

logger = logging.getLogger(__name__)

router = APIRouter()

_ROLES_CATALOGO = (ROL_INGENIERO, ROL_ADMIN)
_NOMBRE_CSV = re.compile(r"^[A-Za-z0-9 _.()\-]{1,120}\.csv$", re.IGNORECASE)
_MAX_CSV_POR_UNIDAD = 50


def _fila_api(f: dict) -> dict:
    return {"id": f["id"], "codigo": f["codigo"], "nombre": f["nombre"],
            "activo": bool(f["activo"]), "modificado": f.get("modificado") or "",
            "modificado_por": f.get("modificado_por") or ""}


def _rechazo_validacion(campo: str, motivo: str):
    raise RechazoApi(422, "validacion", "Datos inválidos",
                     extra={"errores": [{"campo": campo, "codigo": motivo}]})


@router.get("/carga/catalogo")
def listar_catalogo(activos: bool = False):
    """RCB-08.4: lectura libre (la usa Preciclo sin sesión)."""
    return {"elementos": [_fila_api(f)
                          for f in context.db.listar_catalogo_carga(solo_activos=activos)]}


class _AltaBody(BaseModel):
    codigo: str
    nombre: str


@router.post("/carga/catalogo")
def alta_catalogo(body: _AltaBody, sesion: Sesion = Depends(requiere_rol(*_ROLES_CATALOGO))):
    codigo, motivo = rc.validar_codigo(body.codigo)
    if motivo:
        _rechazo_validacion("codigo", motivo)
    nombre, motivo = rc.validar_nombre(body.nombre)
    if motivo:
        _rechazo_validacion("nombre", motivo)
    resultado, anterior = context.db.alta_catalogo_carga(codigo, nombre, sesion.usuario)
    if resultado == "existe":
        raise RechazoApi(409, "codigo_existe", "El código ya está en el catálogo",
                         extra={"nombre": anterior["nombre"] if anterior else ""})
    if resultado == "reactivado":
        _auditar("catalogo_carga_reactivado", sesion, entidad=codigo,
                 valor_anterior=anterior["nombre"], valor_nuevo=nombre)
    else:
        _auditar("catalogo_carga_alta", sesion, entidad=codigo, valor_nuevo=nombre)
    return {"ok": True, "codigo": codigo, "nombre": nombre, "reactivado": resultado == "reactivado"}


class _ModificarBody(BaseModel):
    nombre: str | None = None
    activo: StrictBool | None = None


@router.patch("/carga/catalogo/{id_}")
def modificar_catalogo(id_: int, body: _ModificarBody,
                       sesion: Sesion = Depends(requiere_rol(*_ROLES_CATALOGO))):
    if body.nombre is None and body.activo is None:
        raise RechazoApi(422, "sin_cambios", "Nada que cambiar")
    nombre = None
    if body.nombre is not None:
        nombre, motivo = rc.validar_nombre(body.nombre)
        if motivo:
            _rechazo_validacion("nombre", motivo)
    anterior = context.db.modificar_catalogo_carga(id_, sesion.usuario, nombre=nombre,
                                                  activo=body.activo)
    if anterior is None:
        raise RechazoApi(404, "no_existe", "El elemento no existe")
    codigo = anterior["codigo"]
    if nombre is not None and nombre != anterior["nombre"]:
        _auditar("catalogo_carga_editado", sesion, entidad=codigo,
                 valor_anterior=anterior["nombre"], valor_nuevo=nombre)
    if body.activo is not None and bool(anterior["activo"]) != body.activo:
        _auditar("catalogo_carga_reactivado" if body.activo else "catalogo_carga_baja", sesion,
                 entidad=codigo, valor_anterior=anterior["nombre"],
                 valor_nuevo=nombre if nombre is not None else anterior["nombre"])
    fila = context.db.get_elemento_catalogo(id_)
    return {"ok": True, "elemento": _fila_api(fila) if fila else None}


# ── Importación desde USB (RCB-08.3) ───────────────────────────────────────

def _csv_de_unidad(ruta: str) -> list[dict]:
    try:
        archivos = sorted((p for p in Path(ruta).iterdir()
                           if p.is_file() and _NOMBRE_CSV.match(p.name)),
                          key=lambda p: p.name.lower())[:_MAX_CSV_POR_UNIDAD]
    except OSError:
        return []
    salida = []
    for p in archivos:
        try:
            salida.append({"archivo": p.name, "bytes": p.stat().st_size})
        except OSError:
            continue
    return salida


@router.get("/carga/catalogo/usb")
def listar_csv_usb(sesion: Sesion = Depends(requiere_rol(*_ROLES_CATALOGO))):
    """CSV en la raíz de cada USB detectada (mismo descubrimiento que el
    respaldo)."""
    return {"unidades": [{**u, "archivos": _csv_de_unidad(u["ruta"])} for u in _unidades_usb()]}


class _ImportarBody(BaseModel):
    unidad: str
    archivo: str
    aplicar: StrictBool = False
    huella: str | None = None


def _leer_csv(unidad: str, archivo: str) -> bytes:
    if unidad not in {u["ruta"] for u in _unidades_usb()}:
        raise RechazoApi(404, "usb_no_detectada", "Unidad USB no detectada")
    if not isinstance(archivo, str) or not _NOMBRE_CSV.match(archivo):
        raise RechazoApi(422, "archivo_invalido", "Nombre de archivo no válido")
    ruta = Path(unidad) / archivo
    try:
        if ruta.resolve().parent != Path(unidad).resolve():
            raise RechazoApi(422, "archivo_invalido", "Nombre de archivo no válido")
        if ruta.stat().st_size > rc.MAX_BYTES_CSV:
            raise RechazoApi(422, "csv_invalido", "El archivo no es válido",
                             extra={"motivo": "muy_grande"})
        return ruta.read_bytes()
    except OSError:
        raise RechazoApi(404, "archivo_no_encontrado", "No se pudo leer el archivo")


@router.post("/carga/catalogo/importar")
def importar_catalogo(body: _ImportarBody,
                      sesion: Sesion = Depends(requiere_rol(*_ROLES_CATALOGO))):
    """Sin `aplicar`: vista previa (altas, cambios de nombre, reactivaciones y
    líneas rechazadas con su motivo) y la huella del archivo. Con `aplicar` y
    la huella de la vista previa: aplica las filas válidas en una sola
    transacción (todo o nada); si el archivo cambió desde la vista previa,
    409 `csv_cambio` sin aplicar nada."""
    datos = _leer_csv(body.unidad, body.archivo)
    vista = rc.analizar_csv(datos, context.db.catalogo_carga_por_codigo())
    if not vista["ok"]:
        raise RechazoApi(422, "csv_invalido", "El archivo no es válido",
                         extra={"motivo": vista["error"]})
    if not body.aplicar:
        return {"ok": True, "aplicado": False, **vista}
    if body.huella != vista["huella"]:
        raise RechazoApi(409, "csv_cambio", "El archivo cambió desde la vista previa")
    filas = rc.filas_a_aplicar(vista)
    try:
        conteo = context.db.aplicar_catalogo_carga(filas, sesion.usuario)
    except sqlite3.Error:
        logger.exception("Importación del catálogo de carga fallida: no se aplicó nada")
        raise RechazoApi(503, "bd_no_disponible", "No se pudo guardar el catálogo")
    _auditar("catalogo_carga_importado", sesion, entidad=body.archivo,
             detalle={**conteo, "rechazadas": len(vista["rechazadas"]),
                      "sin_cambio": vista["sin_cambio"]})
    return {"ok": True, "aplicado": True, **conteo, "rechazadas": vista["rechazadas"]}
