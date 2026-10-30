# autoclave/backend/rutas/parametros_ciclo.py
#
# Cambio de parámetros del programa (PATCH /cycle/parameter).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.managers import catalogo_parametros
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, _Rechazo, _lock_archivos,
    _lock_param_ciclo, _rechazar, context, guard_estado, requiere_rol)
from autoclave.backend.rutas._comun import (_contexto_ciclo, _escribir_json_programa,
    _puertas_simples)

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


_SIN_VALOR = object()


class _CycleParamValueBody(BaseModel):
    cycle_id: str
    fase: str
    path: list[str]
    value: object
    # RB-06 (T10): si viene y no coincide con el valor actual, 409 VALOR_CAMBIO.
    # Opcional para no romper los clientes actuales (PySide).
    valor_anterior_esperado: object = None
    model_config = {"extra": "ignore"}


def _valor_parametro(cycle, fase: str, path: list[str]):
    """Valor actual de un parámetro, o None si la ruta no existe."""
    nodo = cycle.parameters.get(fase) if isinstance(cycle.parameters, dict) else None
    for clave in path:
        if not isinstance(nodo, dict) or clave not in nodo:
            return None
        nodo = nodo[clave]
    return nodo.get("value") if isinstance(nodo, dict) else None


@router.patch("/cycle/parameter")
def update_cycle_parameter(body: _CycleParamValueBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    with _lock_param_ciclo:
        return _update_cycle_parameter(body, sesion)


def _update_cycle_parameter(body: _CycleParamValueBody, sesion: Sesion):
    """Actualiza un único parámetro (cualquier sección, incluido el secado) de
    cualquier ciclo cargado y persiste si es 'user'. Valida tipos estrictos y
    el rango efectivo (catálogo ∩ JSON, RB-05; T10) y las reglas entre
    parámetros (tipo_carga). Técnico e ingeniero (tanda §1.6; técnico fuera de
    CICLO). La auditoría es parte del cambio: si no se registra, el cambio se
    revierte (RB-03.5). En CICLO (§5.8, T-17) el cambio se guarda
    siempre en el programa almacenado y aplica también al ciclo en curso solo
    si es su programa y la fase del parámetro no ha iniciado; la respuesta
    lo indica en `aplica` ("en_curso" o "siguiente")."""
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")

    if not body.path:
        raise HTTPException(status_code=422, detail="'path' no puede estar vacío")

    entidad = f"{body.cycle_id}/{body.fase}/{'.'.join(body.path)}"
    if getattr(cycle, "danado", None):
        _rechazar(409, "PROGRAMA_NO_EDITABLE",
                  f"Programa dañado (fuera del catálogo): {cycle.danado[0]}", entidad, sesion)
    # RB-03.5: sin base de datos no hay auditoría; el cambio no se aplica
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "BASE_OCUPADA", "Base de datos no disponible: cambio no aplicado",
                  entidad, sesion)
    # F0 solo en equipos de laboratorio (tanda §1.1): fuera de lab no se ofrece
    # y el backend rechaza activarlo
    if (body.fase == "globals" and body.path == ["F0"] and bool(body.value)
            and not sc.f0_disponible(getattr(context, "profile", None))):
        _rechazar(422, "f0_no_disponible",
                  "F0 solo está disponible en equipos de laboratorio", entidad, sesion)
    # D9-3 (tanda 9): un equipo de puertas simples no abre solo la puerta (no
    # hay actuador); no se ofrece y el backend rechaza activarla
    if (body.fase == "finalizacion" and body.path == ["apertura_automatica"]
            and bool(body.value) and _puertas_simples()):
        _rechazar(422, "apertura_automatica_no_disponible",
                  "Apertura automática no disponible: el equipo tiene puertas simples",
                  entidad, sesion)
    with guard_estado(DISTINTO_DE_CICLO, "/cycle/parameter", sesion,
                      excepcion_ingeniero=True) as estado:
        en_ciclo = estado == GlobalState.CICLO
        programa_en_curso = getattr(getattr(context.control_loop, "cycle", None), "id", None)

        anterior = _valor_parametro(cycle, body.fase, body.path)
        if (body.valor_anterior_esperado is not None
                and body.valor_anterior_esperado != anterior):
            raise _Rechazo(409, "VALOR_CAMBIO", "El valor cambió desde que se leyó",
                           extra={"valor_actual": anterior})
        # D8-5.7: el tipo de carga arrastra el modo de descompresión (a líquido,
        # modo 4; de vuelta a sólido, el defecto sólido del programa o el 1)
        arrastres = _arrastres_tipo_carga(cycle, body.fase, body.path, body.value)
        anteriores_arrastre = [_valor_parametro(cycle, f, p) for f, p, _ in arrastres]
        previos = [(f, p, _valor_parametro(cycle, f, p)) for f, p in cycle.vinculados(body.fase, body.path)]
        previos += [(f, p, a) for (f, p, _), a in zip(arrastres, anteriores_arrastre)]
        # X9 (D9-13.3, revisión SAF-01): el cambio se valida y se calcula
        # sobre una copia; el programa almacenado no recibe ningún valor
        # hasta que la bitácora quede registrada (un ciclo que arranque en
        # medio copia el valor anterior, que sí está registrado).
        propuesta = cycle.copia()
        if hasattr(cycle, "_path"):
            propuesta._path = cycle._path
        # re-revisión X9 (SAF-02): escribir la propuesta no quita la marca
        # de valor sin bitácora (se quita tras registrar la bitácora)
        propuesta._propuesta_sin_registrar = True
        try:
            value = (propuesta.set_param(body.fase, body.path, body.value, arrastres=arrastres)
                     if arrastres else propuesta.set_param(body.fase, body.path, body.value))
        except KeyError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except catalogo_parametros.ErrorCoherencia as e:
            # tanda 12 (C-04.3, C-05.5, C-05.9): el máximo admisible o la
            # consigna calculada van en `valor` para el mensaje de la pantalla
            # DEU-01 (tanda 16): con los límites vigentes del equipo, para que
            # el texto de la pantalla no diga 385 si el equipo tiene otro alivio
            extra = dict(catalogo_parametros.limites_para_mensaje())
            if getattr(e, "valor", None) is not None:
                extra["valor"] = e.valor
            raise _Rechazo(422, e.codigo, str(e), extra=extra)
        except (TypeError, ValueError) as e:
            raise _Rechazo(422, "VALOR_INVALIDO", str(e))
        # tanda 12: advertencias no bloqueantes que dependen de este parámetro
        advertencias = _advertencias_parametro(propuesta, body.fase, body.path)
        # valores que escribe esta petición (cambio, vinculados y arrastres)
        escritos = [(f, p, _valor_parametro(propuesta, f, p)) for f, p, _ in previos]
        cambios_automaticos = [
            {"fase": f, "path": list(p), "clave": ".".join(p), "anterior": a,
             "nuevo": _valor_parametro(propuesta, f, p)}
            for (f, p, _), a in zip(arrastres, anteriores_arrastre)]

        # Fuera de CICLO, o en otro programa durante CICLO (§5.8, 5b), el
        # cambio solo rige desde el siguiente ciclo que use ese programa. El
        # ciclo en curso corre con una copia: solo una fase pendiente de su
        # programa recibe el cambio (§5.8, 4). X9 (D9-13.3, TMG-01): aquí,
        # bajo _sm_lock, solo se CONSULTA si la fase sigue pendiente; la copia
        # se toca después de registrar la bitácora (si la bitácora falla, el
        # ciclo en curso nunca recibió el valor).
        aplica = "siguiente"
        copia_en_curso = None
        if (en_ciclo and body.cycle_id == programa_en_curso
                and context.control_loop.fase_pendiente_en_curso(body.fase, body.path) is True):
            aplica = "en_curso"
            # revisión X9 (TMG-01/SAF-03): la copia concreta consultada; si al
            # aplicar ya es otra (otro ciclo arrancó entre medias), no se aplica
            copia_en_curso = context.control_loop.programa_en_ejecucion()
        detalle = {"programa": body.cycle_id, "fase": body.fase, "aplica": aplica}
        # parámetros vinculados que cambiaron con este (SAF-02 de T-17)
        vinculados = [f"{f}/{'.'.join(p)}" for f, p in cycle.vinculados(body.fase, body.path)[1:]]
        if vinculados:
            detalle["vinculados"] = vinculados
        if cambios_automaticos:
            detalle["arrastres"] = [f"{c['fase']}/{c['clave']}" for c in cambios_automaticos]
        if en_ciclo:
            ctx = _contexto_ciclo()
            detalle.update({"ciclo": ctx.get("ciclo"), "fase_en_curso": ctx.get("fase"),
                            "programa_en_curso": ctx.get("programa")})

    # RB-03.5 (T10): sin registro en audit_log el cambio no queda aplicado.
    # D8-5.7: cada cambio automático (arrastre) va en su propia fila, marcado
    # como automático y con su causa. X9 (D9-13.3, SAF-01): el cambio y sus
    # arrastres van en UNA transacción (registrar_auditoria_lote): todas las
    # filas o ninguna; si falla, se revierte todo.
    # Revisión D8-5.7 (Medio del timing-auditor): la escritura del JSON va en el
    # mismo try; si falla, tampoco queda el cambio en memoria sin bitácora.
    filas = [{"evento": "param_ciclo_cambio", "usuario": sesion.usuario, "rol": sesion.rol,
              "entidad": entidad, "valor_anterior": anterior, "valor_nuevo": value,
              "detalle": detalle}]
    filas += [{"evento": "param_ciclo_cambio", "usuario": sesion.usuario, "rol": sesion.rol,
               "entidad": f"{body.cycle_id}/{c['fase']}/{c['clave']}",
               "valor_anterior": c["anterior"], "valor_nuevo": c["nuevo"],
               "detalle": {"programa": body.cycle_id, "fase": c["fase"], "aplica": "siguiente",
                           "automatico": True, "causa": entidad}}
              for c in cambios_automaticos]
    json_escrito = False
    try:
        # El JSON (con la propuesta) se escribe fuera de _sm_lock (hallazgo D).
        if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
            with _lock_archivos:
                _save_cycle_json(propuesta)
            json_escrito = True
        context.db.registrar_auditoria_lote(filas)
    except Exception:
        logger.exception("Parámetro %s sin auditoría: no se aplica", entidad)
        # El programa almacenado y el ciclo en curso no se tocaron; solo el
        # JSON, si llegó a escribirse, vuelve al programa almacenado.
        json_ok = _reescribir_json_programa(cycle) if json_escrito else None
        if json_ok is False:
            # X9 (D9-13.3, SAF-02): doble falla. La memoria conserva el valor
            # registrado, pero el archivo quedó con el no registrado: se marca
            # para que, al recargarlo, el programa no sea ejecutable.
            _marcar_sin_bitacora(cycle, entidad)
        _rechazar(503, "BASE_OCUPADA", "No se pudo registrar el cambio: no se aplicó",
                  entidad, sesion)

    # Registrado: el cambio pasa al programa almacenado, bajo _sm_lock
    # (atómico respecto del tick que copia el programa al iniciar un ciclo).
    # _lock_param_ciclo serializa los PATCH: las hojas no cambiaron entre medias.
    with context.control_loop.bloqueo_maquina():
        for f, p, v in escritos:
            hoja = cycle._hoja(f, p)
            if hoja is not None:
                hoja["value"] = v
    if json_escrito:
        _quitar_marca_sin_bitacora(cycle)   # archivo = memoria = bitácora

    # X9 (D9-13.3, TMG-01): la bitácora ya está; recién ahora la copia del
    # ciclo en curso (bajo _sm_lock, dentro de aplicar_a_ciclo_en_curso). Si
    # la fase inició entre medias, el ciclo sigue con el valor anterior (el
    # registrado como anterior) y una fila propia corrige el `aplica`.
    if aplica == "en_curso" and context.control_loop.aplicar_a_ciclo_en_curso(
            body.fase, body.path, value, copia_esperada=copia_en_curso) is not True:
        aplica = "siguiente"
        logger.warning("Parámetro %s: la fase inició (o el ciclo cambió) antes de aplicarlo "
                       "al ciclo en curso; rige desde el siguiente ciclo", entidad)
        for intento in (1, 2):                    # revisión X9 (TMG-03/SAF-06)
            try:
                context.db.registrar_auditoria(
                    "param_ciclo_no_aplicado_en_curso", usuario=sesion.usuario, rol=sesion.rol,
                    entidad=entidad, valor_anterior=anterior, valor_nuevo=value,
                    detalle={"programa": body.cycle_id, "fase": body.fase, "aplica": "siguiente"})
                break
            except Exception:
                logger.exception("Parámetro %s: no se pudo registrar que no se aplicó al "
                                 "ciclo en curso (intento %d; la bitácora dice en_curso)",
                                 entidad, intento)
    respuesta = {"ok": True, "value": value, "aplica": aplica}
    if cambios_automaticos:
        respuesta["arrastres"] = cambios_automaticos
    if advertencias:
        respuesta["advertencias"] = advertencias
        logger.warning("Parámetro %s guardado con advertencia: %s", entidad,
                       "; ".join(a["mensaje"] for a in advertencias))
    return respuesta


def _advertencias_parametro(cycle, fase: str, path: list[str]) -> list[dict]:
    """Tanda 12 (C-04.3, C-05.5, C-05.9): advertencias no bloqueantes del
    programa que dependen del parámetro editado. Nunca lanza."""
    try:
        return [{"clave": c, "mensaje": m}
                for c, m in catalogo_parametros.advertencias_programa(cycle.parameters, fase, path)]
    except Exception:
        logger.exception("No se pudieron evaluar las advertencias del parámetro %s/%s",
                         fase, ".".join(path))
        return []


def _arrastres_tipo_carga(cycle, fase: str, path: list[str], valor) -> list:
    """D8-5.7: cambios automáticos del modo de descompresión si se edita el
    tipo de carga. El defecto sólido es el modo del perfil por defecto del
    programa (hospital o fábrica) solo si ese perfil es de carga sólida."""
    if fase != "globals" or list(path) != ["tipo_carga"] or not hasattr(cycle, "arrastres_tipo_carga"):
        return []
    modo_solido = None
    cm = context.cycle_manager
    numero = getattr(cycle, "number", None)
    defecto = (cm.defecto(numero) if numero is not None and callable(getattr(cm, "defecto", None))
               else None)
    if defecto is not None and defecto.get_param("globals", "tipo_carga", default="solido") == "solido":
        modo_solido = defecto.get_param("descompresion", "modo")
    return cycle.arrastres_tipo_carga(valor, modo_solido=modo_solido)


def _reescribir_json_programa(cycle) -> bool:
    """X9 (D9-13.3, SAF-02): vuelve a escribir el JSON desde el programa
    almacenado (valores registrados), con un reintento. False si no pudo.
    Sin `.bak` (re-revisión SAF-01): el archivo que se reemplaza tiene la
    propuesta sin registrar y no debe quedar como respaldo."""
    def cambiar(data):
        data["parameters"] = cycle.parameters
    for intento in (1, 2):
        try:
            with _lock_archivos:
                _escribir_json_programa(cycle, cambiar, con_respaldo=False)
            _quitar_marca_sin_bitacora(cycle)
            return True
        except Exception:
            logger.exception("Programa %s: no se pudo reescribir el JSON (intento %d); "
                             "memoria y archivo difieren", getattr(cycle, "id", "?"), intento)
    return False


# X9 (tanda 9, D9-13.3 SAF-02): marca junto al JSON de un programa cuyo archivo
# quedó con un valor sin bitácora (falló la bitácora y luego la reversión del
# JSON). CycleManager carga un programa marcado como dañado (no se inicia ni
# se edita). En la misma sesión, el siguiente guardado correcto del programa
# quita la marca (_save_cycle_json). Tras un reinicio solo la quita un técnico
# a mano, tras revisar el archivo (PREGUNTA PARA CRISTIAN en el informe X9).
SUFIJO_SIN_BITACORA = ".sin_bitacora"


def _marcar_sin_bitacora(cycle, entidad: str) -> None:
    ruta = str(cycle._path) + SUFIJO_SIN_BITACORA
    logger.critical("Programa %s: el archivo quedó con %s sin bitácora (falló la bitácora y "
                    "la reversión del JSON); al recargarlo no será ejecutable hasta que un "
                    "guardado correcto lo reescriba", getattr(cycle, "id", "?"), entidad)
    try:
        with _lock_archivos:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(entidad + "\n")
    except Exception:
        logger.exception("Programa %s: tampoco se pudo escribir la marca %s",
                         getattr(cycle, "id", "?"), ruta)


def _quitar_marca_sin_bitacora(cycle) -> None:
    import os as _os
    marca = str(getattr(cycle, "_path", "")) + SUFIJO_SIN_BITACORA
    if not getattr(cycle, "_path", None) or not _os.path.exists(marca):
        return
    try:
        _os.remove(marca)
        logger.warning("Programa %s: reescrito desde los valores registrados; se quita %s",
                       getattr(cycle, "id", "?"), _os.path.basename(marca))
    except OSError:
        logger.exception("Programa %s: no se pudo quitar %s", getattr(cycle, "id", "?"), marca)


def _save_cycle_json(cycle) -> None:
    """Escribe cycle.parameters de vuelta al JSON del ciclo (solo ciclos user)."""
    def cambiar(data):
        data["parameters"] = cycle.parameters
    _escribir_json_programa(cycle, cambiar)
    # X9 (D9-13.3, SAF-02): el archivo ya refleja el programa almacenado
    # (valores registrados): la marca de valor sin bitácora deja de aplicar.
    # La propuesta de un PATCH aún no registrada no la quita.
    if not getattr(cycle, "_propuesta_sin_registrar", False):
        _quitar_marca_sin_bitacora(cycle)
