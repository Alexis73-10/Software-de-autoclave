# autoclave/backend/rutas/programas.py
#
# Programas: lista, secciones, gestión, entradas mostradas y sensores
# (/programas, /cycle/display-inputs, /cycle/sensors, /cycle/sensor-roles).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
from fastapi import Depends, HTTPException
from pydantic import BaseModel, StrictBool
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime.lectura import lectura_valida
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, _Rechazo, _auditar,
    _lock_archivos, _rechazar, context, guard_estado, requiere_rol)
from autoclave.backend.rutas._comun import (_ai_habilitadas, _carga_liquida,
    _escribir_json_programa, _nombres_ciclo, _puertas_simples)

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


# ── Opciones › Parámetros del ciclo, lectura (T12; opciones §5.1, §5.2, §6) ──

# Orden de la pantalla 1: fases del ciclo y, al final, Generales y Finalización
_SECCIONES_PROGRAMA = ("precalentamiento", "prevacio", "calentamiento", "esterilizacion",
                       "descompresion", "secado", "globals", "finalizacion")


def _no_se_ejecuta(cycle, seccion: str) -> bool:
    """Q-2: la fase con su parámetro de activación en 0 se muestra con "No se
    ejecuta" (precalentamiento, secado, tipos de pulso de vacío)."""
    if seccion == "precalentamiento":
        return not cycle.get_param("precalentamiento", "tiempo_precalentamiento")
    if seccion == "secado":
        return not cycle.get_param("secado", "tiempo_secado")
    if seccion == "prevacio":
        return not any(cycle.get_param("prevacio", f"conteo_pulso_{p}") for p in "abcd")
    return False


def _programa_editable(cycle) -> bool:
    return getattr(cycle, "source", "") == "user" and not getattr(cycle, "danado", None)


@router.get("/programas")
def get_programas():
    """Programas para Opciones (§6): número, nombre, origen, estado y sus
    secciones con la marca "No se ejecuta". Sin lectura de disco en la UI."""
    salida = []
    for cycle in list(context.cycle_manager.cycles.values()):
        if cycle.number is None:
            continue
        salida.append({
            "numero": cycle.number, "cycle_id": cycle.id, "nombre": cycle.name,
            "nombres": _nombres_ciclo(cycle),
            "origen": getattr(cycle, "source", ""), "danado": bool(getattr(cycle, "danado", None)),
            "editable": _programa_editable(cycle),
            "habilitado": getattr(cycle, "habilitado", True) is not False,
            "personalizado": getattr(cycle, "personalizado", False) is True,
            "secciones": [{"clave": s, "no_se_ejecuta": _no_se_ejecuta(cycle, s)}
                          for s in _SECCIONES_PROGRAMA if s in cycle.parameters],
        })
    return {"programas": sorted(salida, key=lambda p: p["numero"])}


def _param_programa(cycle, seccion: str, nombre: str):
    try:
        return cycle.get_param(seccion, nombre)
    except Exception:
        return None


@router.get("/programas/seleccionables")
def get_programas_seleccionables():
    """Programas que el operador puede elegir en Preciclo (B6, tanda 4), ya
    ordenados: primero los 3 con más ciclos terminados en el historial (de mayor
    a menor; el empate lo decide el orden predefinido, por número) marcados
    `mas_usado`, después el resto por número. Sin historial, o sin base de datos,
    todo en el orden predefinido y sin marcas. `seleccionable` y `motivo` dicen
    si hoy se puede cambiar de programa (la misma regla que /cycle/select). Solo
    lectura, sin sesión (como /cycle/select)."""
    cap = getattr(context, "cap", None)
    filas = []
    for cycle in list(context.cycle_manager.cycles.values()):
        if getattr(cycle, "number", None) is None or getattr(cycle, "source", "user") != "user":
            continue
        if getattr(cycle, "danado", None):
            continue
        if getattr(cycle, "habilitado", True) is False:      # O1: deshabilitado
            continue
        if _carga_liquida(cycle) and getattr(cap, "has_liquids", None) is False:
            continue
        filas.append({
            "numero": cycle.number, "cycle_id": cycle.id, "nombre": cycle.name,
            "nombres": _nombres_ciclo(cycle),
            "temperatura": _param_programa(cycle, "esterilizacion", "temperatura_esterilizacion"),
            "tiempo": _param_programa(cycle, "esterilizacion", "tiempo_esterilizacion"),
            "ciclos": 0, "mas_usado": False, "seleccionado": False,
        })
    filas.sort(key=lambda f: f["numero"])
    conteos = {}
    if getattr(context, "sin_base_de_datos", False) is not True:
        try:
            conteos = context.db.conteo_ciclos_por_programa()
        except Exception:
            logger.warning("Conteo de ciclos por programa no disponible: orden predefinido")
    for f in filas:
        f["ciclos"] = int(conteos.get(f["numero"], 0) or 0)
    usados = sorted((f for f in filas if f["ciclos"] > 0), key=lambda f: (-f["ciclos"], f["numero"]))[:3]
    for f in usados:
        f["mas_usado"] = True
    filas = usados + [f for f in filas if not f["mas_usado"]]
    loop = context.control_loop
    with loop.bloqueo_maquina():
        activo = getattr(getattr(loop, "cycle", None), "id", None)
        motivo = loop._motivo_no_cambiar_ciclo()
    for f in filas:
        f["seleccionado"] = f["cycle_id"] == activo
    return {"programas": filas, "seleccionable": motivo is None, "motivo": motivo or "",
            "orden": "uso" if usados else "predefinido"}


# D9-3 (tanda 9): en un equipo de puertas simples, Finalización no muestra la
# apertura automática ni su espera (temp_max_apertura sigue visible)
_FINALIZACION_SOLO_PUERTA_AUTOMATICA = frozenset({"tiempo_espera_apertura", "apertura_automatica"})


def _hojas_seccion(cycle, seccion: str) -> list[tuple[list[str], dict]]:
    """Parámetros (ruta, hoja) de la sección. Descompresión: el modo, la
    espera previa y solo los parámetros del modo activo (Q-3)."""
    nodo = cycle.parameters.get(seccion) or {}
    salida = []

    def recorrer(n, ruta):
        if isinstance(n, dict) and "value" in n and not isinstance(n.get("value"), dict):
            salida.append((ruta, n))
            return
        if isinstance(n, dict):
            for clave, sub in n.items():
                recorrer(sub, ruta + [clave])

    recorrer(nodo, [])
    if seccion == "finalizacion" and _puertas_simples():
        salida = [(r, h) for r, h in salida if r[-1] not in _FINALIZACION_SOLO_PUERTA_AUTOMATICA]
    if seccion == "descompresion":
        modo = cycle.get_param("descompresion", "modo")
        activo = f"modo_{modo}"
        salida = [(r, h) for r, h in salida if len(r) == 1 or r[0] == activo]
    return salida


def _ultimas_modificaciones(entidad_prefijo: str) -> dict:
    """{entidad: {usuario, rol, ts, valor_anterior, valor_nuevo}} con la última
    modificación auditada de cada parámetro del programa (RB-03.8)."""
    try:
        filas = context.db.get_auditoria(evento="param_ciclo_cambio", limite=2000)
    except Exception:
        return {}
    ultimas = {}
    for f in filas:                       # la más reciente primero
        entidad = f.get("entidad") or ""
        if entidad.startswith(entidad_prefijo) and entidad not in ultimas:
            ultimas[entidad] = {k: f.get(k) for k in
                                ("usuario", "rol", "ts", "valor_anterior", "valor_nuevo")}
    return ultimas


@router.get("/programas/{numero}/seccion/{seccion}")
def get_programa_seccion(numero: int, seccion: str):
    """Parámetros de una sección (§5.2, §6): valor, por defecto (perfil de
    fábrica del mismo número; "—" si no lo hay, Q-4), rango efectivo (catálogo
    ∩ JSON, RB-05.2), tipo, unidad, opciones, `modificado` y última
    modificación."""
    from autoclave.core.managers import catalogo_parametros as _cp
    cycle = _programa_por_numero(numero)
    if seccion not in _SECCIONES_PROGRAMA or seccion not in cycle.parameters:
        raise HTTPException(status_code=404, detail=f"Sección '{seccion}' no encontrada")
    # O1 (tanda 5): defecto del hospital (cycles/defecto) o, si no, el de fábrica
    cm = context.cycle_manager
    fabrica = (cm.defecto(numero) if callable(getattr(cm, "defecto", None))
               else getattr(cm, "fabrica", {}).get(numero))
    ultimas = _ultimas_modificaciones(f"{cycle.id}/{seccion}/")
    parametros = []
    for ruta, hoja in _hojas_seccion(cycle, seccion):
        defecto = fabrica.get_param(seccion, *ruta) if fabrica is not None else None
        minimo, maximo = _cp.rango_efectivo(hoja, seccion, ruta)
        valor = hoja.get("value")
        parametros.append({
            "path": ruta, "clave": ".".join(ruta), "tipo": hoja.get("type") or "int",
            "unidad": (hoja.get("unit") or "").replace("\ufffd", "°"),
            "clase": hoja.get("clase"),           # C1c (tanda 6): clase explícita de U1
            "valor": valor, "defecto": defecto, "min": minimo, "max": maximo,
            "opciones": hoja.get("options") or [],
            # D8-5.8: un parámetro "modo" se elige de esta lista (D8-5.7: con
            # carga líquida la descompresión solo admite 4, 5 y 0)
            "modos": _cp.modos_validos(cycle.parameters, seccion, ruta),
            "modificado": defecto is not None and defecto != valor,
            "ultima_modificacion": ultimas.get(f"{cycle.id}/{seccion}/{'.'.join(ruta)}"),
        })
    return {"numero": numero, "cycle_id": cycle.id, "nombre": cycle.name, "seccion": seccion,
            "editable": _programa_editable(cycle), "parametros": parametros}


# ── Gestión de programas (O1, tanda 5; planeacion_opciones.md v4 §3.1) ─────

class _HabilitadoBody(BaseModel):
    habilitado: StrictBool


class _DuplicarBody(BaseModel):
    nombre: str
    # C9 (tanda 9, D9-10): "Crear" en Manejo de ciclos = duplicar con nombre
    # nuevo; solo cambia el evento de la bitácora (programa_creado)
    crear: StrictBool = False


def _gestion(entidad: str, sesion: Sesion, operar, evento: str, auditoria, deshacer,
             confirmar=None, excepcion_ingeniero: bool = True):
    """Técnico fuera de CICLO; ingeniero también en CICLO (como los
    parámetros) salvo `excepcion_ingeniero=False` (C9, tanda 9, D9-10:
    crear, duplicar, habilitar y borrar programas solo fuera de ciclo, para
    todos los roles). El programa activo nunca se borra ni se deshabilita: la
    lectura del activo y el cambio van bajo el lock de la máquina (guard_estado),
    el mismo que /cycle/select. Los archivos son pequeños; la escritura queda
    dentro del lock a propósito para no abrir esa carrera.
    RB-03.5 (revisión O1, SAF-01): sin registro en audit_log el cambio no
    queda aplicado; `deshacer(resultado)` lo revierte."""
    from autoclave.core.managers import gestion_programas as gp
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "BASE_OCUPADA", "Base de datos no disponible: no se aplicó", entidad, sesion)
    # Revisión D8-5.7 (TMG-01): orden único de locks, _lock_archivos y luego
    # _sm_lock, como /cycle/sensor-roles, la calibración y la restauración; al
    # revés se interbloqueaba con ellos y detenía el tick del control loop.
    with _lock_archivos:
        with guard_estado(DISTINTO_DE_CICLO, entidad, sesion,
                          excepcion_ingeniero=excepcion_ingeniero):
            activo = getattr(getattr(context.control_loop, "cycle", None), "id", None)
            try:
                resultado = operar(gp, activo)
            except gp.ErrorPrograma as e:
                raise _Rechazo(e.estado_http, e.codigo, e.motivo)
    anterior, nuevo = auditoria(resultado)
    try:
        context.db.registrar_auditoria(evento, usuario=sesion.usuario, rol=sesion.rol,
                                       entidad=entidad, valor_anterior=anterior,
                                       valor_nuevo=nuevo, detalle=None)
    except Exception:
        logger.exception("%s sin auditoría: se revierte", entidad)
        with _lock_archivos, context.control_loop.bloqueo_maquina():
            deshacer(gp, resultado)
        _rechazar(503, "BASE_OCUPADA", "No se pudo registrar el cambio: no se aplicó",
                  entidad, sesion)
    if confirmar is not None:
        with _lock_archivos:
            confirmar(gp, resultado)
    return resultado


@router.put("/programas/{numero}/habilitado")
def put_programa_habilitado(numero: int, body: _HabilitadoBody,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}/habilitado"
    cm = context.cycle_manager
    anterior, nuevo = _gestion(
        entidad, sesion,
        lambda gp, activo: gp.fijar_habilitado(cm, numero, body.habilitado, activo),
        "programa_habilitado",
        lambda r: ({"habilitado": r[0]}, {"habilitado": r[1]}),
        lambda gp, r: gp.deshacer_habilitado(cm, numero, r[0]),
        excepcion_ingeniero=False)                     # C9 (D9-10): solo fuera de ciclo
    return {"ok": True, "numero": numero, "habilitado": nuevo}


@router.post("/programas/{numero}/duplicar")
def post_programa_duplicar(numero: int, body: _DuplicarBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}/duplicar"
    cm = context.cycle_manager
    nuevo = _gestion(
        entidad, sesion, lambda gp, activo: gp.duplicar(cm, numero, body.nombre),
        "programa_creado" if body.crear else "programa_duplicado",
        lambda c: ({"origen": numero}, {"numero": c.number, "cycle_id": c.id, "nombre": c.name}),
        lambda gp, c: gp.deshacer_duplicado(cm, c),
        excepcion_ingeniero=False)                     # C9 (D9-10): solo fuera de ciclo
    return {"ok": True, "numero": nuevo.number, "cycle_id": nuevo.id, "nombre": nuevo.name}


@router.delete("/programas/{numero}")
def delete_programa(numero: int,
                    sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}"
    cm = context.cycle_manager
    _gestion(entidad, sesion, lambda gp, activo: gp.borrar(cm, numero, activo),
             "programa_borrado",
             lambda c: ({"numero": numero, "cycle_id": c.id, "nombre": c.name}, None),
             lambda gp, c: gp.deshacer_borrado(cm, c),
             confirmar=lambda gp, c: gp.confirmar_borrado(c),
             excepcion_ingeniero=False)                # C9 (D9-10): solo fuera de ciclo
    return {"ok": True, "numero": numero}


class _EntradasBody(BaseModel):
    programa: int
    entradas: list


@router.get("/cycle/display-inputs")
def get_entradas_mostradas(programa: int):
    """Entradas mostradas del programa (1 a 3), las AI habilitadas del equipo y
    las que ofrece el selector (O11, D11-7.1: sin los sensores No en uso)."""
    from autoclave.core.managers import gestion_programas as gp
    cycle = _programa_por_numero(programa)
    habilitadas = _ai_habilitadas()
    return {"programa": programa, "entradas": gp.entradas_de(cycle, habilitadas),
            "habilitadas": habilitadas,
            "disponibles": gp.entradas_disponibles(cycle, habilitadas),
            "no_en_uso": gp.entradas_no_en_uso(cycle),
            "editable": getattr(cycle, "source", "") == "user"}


@router.put("/cycle/display-inputs")
def put_entradas_mostradas(body: _EntradasBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/cycle/display-inputs/{body.programa}"
    cm = context.cycle_manager
    previas = []

    def operar(gp, activo):
        previas.append(getattr(gp.programa(cm, body.programa), "entradas_mostradas", None))
        return gp.fijar_entradas(cm, body.programa, body.entradas, _ai_habilitadas())
    anterior, nueva = _gestion(entidad, sesion, operar, "entradas_mostradas",
                               lambda r: (r[0], r[1]),
                               lambda gp, r: gp.deshacer_entradas(cm, body.programa, previas[0]))
    return {"ok": True, "entradas": nueva}


# ── Sensores del ciclo (tanda 2026-10-14 §1.1; RS-01, RS-02) ───────────────

def _programa_por_numero(numero: int):
    for cycle in list(context.cycle_manager.cycles.values()):
        if getattr(cycle, "number", None) == numero:
            return cycle
    raise HTTPException(status_code=404, detail=f"Programa {numero} no encontrado")


@router.get("/cycle/sensors")
def get_cycle_sensors(programa: int):
    """Sensores del programa N: id, nombre (ubicación), tipo, estado
    (disponible / sin_senal / no_instalado), lectura y rol. Un sensor
    no_instalado solo se lista si el programa le asigna un rol activo."""
    cycle = _programa_por_numero(programa)
    perfil = getattr(context, "profile", None)
    asignacion = sc.asignacion_de(cycle)
    sensores = []
    for s in sc.SENSORES:
        estado_s = sc.estado_sensor(perfil, context.estado, s)
        rol = asignacion.get(s, sc.NO_EN_USO)
        if estado_s == sc.NO_INSTALADO and rol == sc.NO_EN_USO:
            continue
        lectura = context.estado.sensores_temp.get(s)
        sensores.append({
            "id": s, "nombre": sc.NOMBRES[s], "tipo": sc.TIPOS[s], "estado": estado_s,
            "lectura": lectura if lectura_valida(lectura) else None, "rol": rol,
        })
    return {
        "programa": programa,
        "cycle_id": cycle.id,
        "asignacion": asignacion,
        "errores": sc.errores_asignacion(asignacion),
        "formato_antiguo": bool(getattr(cycle, "sensores_formato_antiguo", False)),
        "editable": getattr(cycle, "source", "") == "user",
        "sensores": sensores,
    }


class _SensorRolesBody(BaseModel):
    programa: int
    asignacion: dict
    asignacion_anterior_esperada: dict


def _normalizar_asignacion(asignacion: dict) -> dict:
    """Completa con no_en_uso los sensores del catálogo que falten; conserva
    las claves desconocidas para que la validación las rechace."""
    return {**{s: sc.NO_EN_USO for s in sc.SENSORES}, **asignacion}


_SIN_CAMBIO = object()


def _escribir_sensores_json(cycle, asignacion: dict, entradas=_SIN_CAMBIO) -> None:
    """Campo cycle_temperature_sensors del JSON (RS-02). O11 (D11-7.3): con
    `entradas`, también entradas_mostradas en la misma escritura atómica
    (None la quita)."""
    def cambiar(data):
        data["cycle_temperature_sensors"] = {s: asignacion[s] for s in sc.SENSORES}
        if entradas is not _SIN_CAMBIO:
            if entradas is None:
                data.pop("entradas_mostradas", None)
            else:
                data["entradas_mostradas"] = list(entradas)
    _escribir_json_programa(cycle, cambiar)


@router.put("/cycle/sensor-roles")
def put_sensor_roles(body: _SensorRolesBody,
                     sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Asigna los roles de los sensores de un programa: todo o nada, con
    control de concurrencia por asignacion_anterior_esperada y auditoría
    ROLES_SENSOR (RS-02). Técnico fuera de CICLO; ingeniero también en CICLO
    (el ciclo en curso conserva su instantánea, RS-03.4). Solo programas de
    usuario."""
    cycle = _programa_por_numero(body.programa)
    entidad = f"{cycle.id}/cycle_temperature_sensors"
    if getattr(cycle, "source", "") != "user" or not hasattr(cycle, "_path"):
        _rechazar(409, "programa_de_fabrica",
                  "Los programas de fábrica no se modifican", entidad, sesion)
    nueva = _normalizar_asignacion(body.asignacion)
    errores = sc.errores_asignacion(nueva)
    if errores:
        _rechazar(422, sc.ASIGNACION_INVALIDA, "; ".join(errores), entidad, sesion,
                  extra={"errores": errores})
    # PRG-01 (tanda 16, D-PRG-1): un rol (Principal o Referencia) sobre una
    # sonda no activa en el perfil de instalación se rechaza con código propio
    # (texto es/en en la pantalla: opciones.err_rol_sonda_no_activa)
    no_activas = sc.roles_sonda_no_activa(nueva, getattr(context, "profile", None))
    if no_activas:
        _rechazar(422, sc.ROL_SONDA_NO_ACTIVA, sc.motivo_sonda_no_activa(no_activas),
                  entidad, sesion, extra={"sensores": no_activas})
    esperada = _normalizar_asignacion(body.asignacion_anterior_esperada)

    propagado, motivo_propagacion = False, "sin_copias"
    with _lock_archivos:      # serializa escritores: la asignación no cambia entre pasos
        with guard_estado(DISTINTO_DE_CICLO, entidad, sesion, excepcion_ingeniero=True):
            anterior = dict(sc.asignacion_de(cycle))
            if sc.canonica(esperada) != sc.canonica(anterior):
                raise _Rechazo(409, "asignacion_desfasada",
                               "La asignación cambió desde que se leyó; vuelva a cargarla",
                               extra={"asignacion_actual": anterior})
            faltan = sc.errores_disponibilidad(nueva, getattr(context, "profile", None),
                                               context.estado)
            if faltan:
                raise _Rechazo(422, sc.SENSOR_NO_DISPONIBLE,
                               f"Sensores sin lectura o no instalados: {faltan}",
                               extra={"sensores": faltan})
        # O11 (D11-7.3): un sensor que pasa a No en uso sale de las entradas
        # mostradas del programa en la misma escritura (vacía -> el Principal)
        from autoclave.core.managers import gestion_programas as gp
        entradas_previas = getattr(cycle, "entradas_mostradas", None)
        entradas_nuevas = gp.entradas_tras_cambio_de_rol(entradas_previas, nueva)
        con_entradas = entradas_nuevas is not None
        # archivo fuera de _sm_lock (no detener el tick); si falla, nada cambió
        try:
            if con_entradas:
                _escribir_sensores_json(cycle, nueva, entradas_nuevas)
            else:
                _escribir_sensores_json(cycle, nueva)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo guardar el programa: {exc}")
        with context.control_loop.bloqueo_maquina():
            # SAF-05 de T3: el ciclo pudo arrancar mientras se escribía el
            # archivo; un técnico no modifica el programa en CICLO.
            en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            permitido = not en_ciclo or sesion.rol == ROL_INGENIERO
            if permitido:
                cycle.sensores = dict(nueva)
                cycle.sensores_formato_antiguo = False
                if con_entradas:
                    cycle.entradas_mostradas = list(entradas_nuevas)
                if not en_ciclo:
                    # S4: libera un estado seguro detenido por el Principal
                    # viejo, solo si la sonda nueva es segura (no más fría)
                    propagado, motivo_propagacion = context.control_loop.aplicar_roles_sensores(
                        cycle.id, nueva)
        if not permitido:
            if con_entradas:                               # revierte el archivo
                _escribir_sensores_json(cycle, anterior, entradas_previas)
            else:
                _escribir_sensores_json(cycle, anterior)
            _rechazar(409, "estado_no_permitido",
                      "Hay un ciclo en curso: no se aplicó el cambio", entidad, sesion)

    _auditar("ROLES_SENSOR", sesion, entidad=entidad,
             valor_anterior=sc.canonica(anterior), valor_nuevo=sc.canonica(nueva),
             detalle={"programa": cycle.id, "numero": body.programa,
                      "param": "cycle_temperature_sensors",
                      "estado_seguro_propagado": propagado,
                      "motivo_propagacion": motivo_propagacion,
                      **({"entradas_mostradas": entradas_nuevas} if con_entradas else {})})
    if con_entradas:
        # mismo evento y entidad que PUT /cycle/display-inputs
        _auditar("entradas_mostradas", sesion, entidad=f"/cycle/display-inputs/{body.programa}",
                 valor_anterior=list(entradas_previas), valor_nuevo=list(entradas_nuevas),
                 detalle={"motivo": "sensor_no_en_uso", "programa": cycle.id,
                          "numero": body.programa})
    return {"ok": True, "asignacion": nueva,
            "estado_seguro_propagado": propagado}
