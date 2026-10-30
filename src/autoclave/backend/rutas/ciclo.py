# autoclave/backend/rutas/ciclo.py
#
# Rutas del ciclo: programa activo, inicio, aborto, progreso, fallas, estado
# seguro y salidas (/cycle, /cycles, /fault, /safe-state, /outputs).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
from fastapi import HTTPException, Body, Header, Request
from pydantic import BaseModel
from autoclave.core.runtime import progreso_ciclo
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.state_machine.machine.enum_global import GlobalState
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, RechazoApi, _Rechazo, _auditar,
    _log_desarrollo, _nombre_estado, _rechazar, _rechazar_si_config_invalida, _token_de,
    context, guard_estado, tokens)
from autoclave.backend.rutas._comun import (_ai_habilitadas, _carga_liquida,
    _ciclo_de_pantalla, _i18n_t, _motivo_paro, _nombres_ciclo, _salidas_sin_confirmar_pendiente,
    _terminacion_y_alarmas)

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


@router.get("/cycle")
def get_selected_cycle():
    cycle = context.cycle_manager.get_selected_cycle()

    if cycle is None:
        raise HTTPException(status_code=404, detail="No hay ciclo seleccionado")

    return {
        "id": cycle.id,
        "name": cycle.name,
        "nombres": _nombres_ciclo(cycle),
        "number": getattr(cycle, "number", None),
        "parameters": cycle.parameters,
        **_entradas_mostradas_de(cycle),
    }


def _entradas_mostradas_de(cycle) -> dict:
    """O3 (tanda 6): entradas mostradas (1 a 3) del programa para Preciclo,
    Ciclo y gráfica, y las que tienen el sensor "No en uso" en el programa.
    Tanda 17 (SON-01, revierte O11 / D11-7): una sonda instalada No en uso se
    muestra y se registra como monitoreo; `entradas_no_en_uso` (solo las de
    sondas instaladas, AI habilitadas por el perfil) ya no filtra: la UI la
    usa para el rótulo «(monitoreo)». Solo presentación; ante cualquier
    error, la omisión del programa."""
    from autoclave.core.managers import gestion_programas as gp
    try:
        habilitadas = _ai_habilitadas()
    except Exception:
        habilitadas = None
    try:
        no_en_uso = gp.entradas_no_en_uso(cycle, habilitadas)
    except Exception:
        no_en_uso = []
    try:
        if habilitadas is None:
            raise ValueError("sin AI habilitadas")
        entradas = gp.entradas_de(cycle, habilitadas)
    except Exception:
        try:
            entradas = gp.entradas_por_omision(cycle)
        except Exception:
            entradas = [e for e in gp.ENTRADAS_POR_OMISION if e not in no_en_uso]
    return {"entradas_mostradas": entradas, "entradas_no_en_uso": no_en_uso}


@router.get("/cycles")
def list_cycles():
    return [
        {"id": c.id, "name": c.name, "nombres": _nombres_ciclo(c),
         "source": getattr(c, "source", "user")}
        for c in list(context.cycle_manager.cycles.values())
    ]


# S2 (tanda 2): origen declarado por el cliente (no autenticado) del cambio de
# programa, para la bitácora. Lista cerrada: un valor desconocido se rechaza.
ORIGENES_SELECCION = ("puerta_1", "puerta_2", "remoto", "desconocido")


class _SelectCycleBody(BaseModel):
    cycle_id: str
    # Opcional: el endpoint sigue sin sesión (decisión 2 de Cristian)
    origen: str | None = None


@router.post("/cycle/select")
def select_cycle(body: _SelectCycleBody, request: Request):
    """Cambia el programa activo. Sin sesión y permitido en FALLA (decisión 2
    de Cristian, 19-oct: ningún fallo exige técnico). Rechazado con un ciclo
    en curso en sentido amplio (ControlLoop._motivo_no_cambiar_ciclo), con un
    programa dañado (RB-04.4) y con un programa de líquidos en un equipo sin
    esa capacidad (T11). El cambio y todos sus rechazos quedan en audit_log
    con el origen DECLARADO (no autenticado), el cliente HTTP y el estado (S2).
    Lectura del programa anterior, cambio en el lazo y en el CycleManager van
    juntos bajo el lock de la máquina; la bitácora se escribe al soltarlo."""
    entidad = "/cycle/select"
    detalle = {"origen": body.origen or "desconocido",
               "origen_autenticado": False,
               "cliente": request.client.host if request.client else ""}
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    nombre = getattr(cycle, "name", None)

    def rechazar(status: int, codigo: str, motivo: str, anterior=None, estado=""):
        # D9-6 (tanda 9): solo log de desarrollo
        _log_desarrollo("PROGRAMA_SELECCION_RECHAZADA", entidad=entidad,
                        anterior=anterior, nuevo=body.cycle_id,
                        detalle={**detalle, "estado": estado or _nombre_estado(),
                                 "codigo": codigo, "motivo": motivo, "programa": nombre})
        raise RechazoApi(status, codigo, motivo)

    if detalle["origen"] not in ORIGENES_SELECCION:
        rechazar(422, "origen_invalido",
                 "Origen desconocido: %r (válidos: %s)"
                 % (detalle["origen"][:40], ", ".join(ORIGENES_SELECCION)))
    if cycle is None:
        rechazar(404, "programa_no_encontrado", f"Ciclo '{body.cycle_id}' no encontrado")
    if getattr(cycle, "source", "user") != "user":
        rechazar(422, "programa_de_fabrica", "Solo se pueden seleccionar ciclos de usuario")
    # RB-04.4 (T10): un programa dañado no es ejecutable
    if getattr(cycle, "danado", None):
        rechazar(409, "PROGRAMA_NO_EDITABLE",
                 f"Programa dañado (fuera del catálogo): {cycle.danado[0]}")
    # O1 (tanda 5): un programa deshabilitado no se selecciona
    if getattr(cycle, "habilitado", True) is False:
        rechazar(409, "programa_deshabilitado", "Programa deshabilitado")
    # T11 (revisión de S2): líquidos solo en equipos con esa capacidad
    if _carga_liquida(cycle) and getattr(getattr(context, "cap", None), "has_liquids", None) is False:
        rechazar(409, "carga_liquida_no_disponible",
                 "Este equipo no admite programas de carga líquida")

    loop = context.control_loop
    with loop.bloqueo_maquina():
        anterior = getattr(getattr(loop, "cycle", None), "id", None)
        estado = _nombre_estado()
        ok, reason = loop.set_active_cycle(cycle)
        if ok:
            context.cycle_manager.set_default_cycle(body.cycle_id)
    detalle["estado"] = estado
    if not ok:
        rechazar(409, "cambio_no_permitido", reason, anterior=anterior, estado=estado)

    # D9-6 (tanda 9): solo log de desarrollo
    _log_desarrollo("PROGRAMA_SELECCIONADO", entidad=entidad, anterior=anterior,
                    nuevo=body.cycle_id, detalle={**detalle, "programa": nombre})
    return {"ok": True, "id": cycle.id, "name": cycle.name}

@router.get("/cycle/current/readings")
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


@router.get("/cycle/current/progress")
def get_current_cycle_progress():
    """Progreso del ciclo en curso para la pantalla QML (fases que aplican,
    fase activa, duración por fase, transcurrido y restante en segundos
    monotónicos). Separado de /status para no cargar su sondeo de 200 ms.
    Sigue respondiendo con el ciclo terminado mientras la máquina espera la
    confirmación del operador. Sin ciclo: {"activo": false}."""
    ciclo_id = _ciclo_de_pantalla()
    transcurrido = context.cycle_logger.transcurrido_s() if ciclo_id is not None else None
    if ciclo_id is None or transcurrido is None:
        return {"activo": False}

    # las fases que aplican salen de la copia con la que corre el ciclo (T-17)
    cycle = context.control_loop.programa_en_ejecucion()
    aplicables = progreso_ciclo.fases_aplicables(cycle, context.cap)
    filas = [dict(f) for f in context.db.get_fases_ciclo(ciclo_id)]

    fila_ciclo = context.db.get_ciclo(ciclo_id)
    tipo = fila_ciclo["tipo_ciclo"] if fila_ciclo is not None else getattr(cycle, "id", "")
    referencias = {}
    for fase, duracion in context.db.get_duraciones_referencia(tipo).items():
        fase_ui = progreso_ciclo.fase_ui(fase)
        if fase_ui is not None:
            referencias[fase_ui] = referencias.get(fase_ui, 0.0) + duracion

    fase_ciclo = getattr(context.estado, "fase_ciclo", "") or ""
    # C-13.7 (tanda 12): restante de exposición que publica ESTERILIZACION
    # (refleja el reinicio del conteo tras una excursión de Referencia)
    restante_exp = getattr(context.estado, "exposicion_restante_s", None)
    if not isinstance(restante_exp, (int, float)) or isinstance(restante_exp, bool):
        restante_exp = None
    progreso = progreso_ciclo.armar_progreso(aplicables, filas, fase_ciclo, transcurrido,
                                             referencias, restante_exp)
    # FC-06/FC-13 (tanda 21): con el ciclo terminado, la fase en que terminó,
    # cómo terminó y las alarmas del ciclo. P4 (NO CONFORME) se retiró (FC-08).
    if progreso.get("resultado") is not None:
        progreso.update(_terminacion_y_alarmas(ciclo_id, fase_ciclo, progreso))
    return {
        "activo": True,
        "ciclo_db_id": ciclo_id,
        "fase_ciclo": fase_ciclo,
        **progreso,
    }


@router.get("/cycle/current/graph")
def get_current_cycle_graph(desde_id: int | None = None):
    """Serie de la gráfica del ciclo en curso (~1 s, t_s monotónico, con
    temp_ref). Sin desde_id devuelve el histórico completo (al entrar o tras
    reiniciar la UI); con desde_id solo las lecturas posteriores a ese id."""
    ciclo_id = _ciclo_de_pantalla()
    if ciclo_id is None:
        return {"ciclo_db_id": None, "lecturas": []}
    rows = context.db.get_lecturas_grafica(ciclo_id, desde_id)
    # Tanda 17 (SON-01): las sondas instaladas, también las No en uso (monitoreo)
    sondas = sc.sondas_grafica(getattr(context, "profile", None))
    return {
        "ciclo_db_id": ciclo_id,
        "lecturas": [
            {
                "id":          r["id"],
                "t_s":         r["t_s"],
                "fase":        r["fase"],
                "fase_ui":     progreso_ciclo.fase_ui(r["fase"]),
                **sc.temperaturas_grafica(r, sondas),
                "pres_camara": r["pres_camara"],
            }
            for r in rows
        ],
    }


@router.post("/cycle/start")
def start_cycle(body: dict | None = Body(default=None),
                authorization: str | None = Header(None)):
    """
    Solicita el inicio del ciclo de esterilización.
    Sólo tiene efecto cuando el sistema está en estado PREPARADO y
    la flag LISTO_PARA_CICLO es True.  La máquina de estados gestiona
    la transición real.
    Sin base de datos (T8, §7.6) exige {"confirmar_sin_registro": true} en
    cada ciclo: queda sin operador y sin registro en la base (respaldo y ticket).
    O1 (tanda 3): si la petición trae un token de sesión válido, ese usuario es
    el operador del ciclo (se guarda en la base, el respaldo y el ticket). El
    inicio sigue sin exigir sesión: sin token (o con uno vencido) el ciclo queda
    sin operador identificado; el token no se valida como requisito.
    """
    sesion_operador = tokens.obtener(_token_de(authorization))
    estado = context.estado
    _rechazar_si_config_invalida("/cycle/start")
    if getattr(context, "sin_base_de_datos", False) is True:
        if not (isinstance(body, dict) and body.get("confirmar_sin_registro") is True):
            _rechazar(409, "confirmar_sin_registro",
                      "Base de datos no disponible: confirme que desea iniciar el ciclo "
                      "sin registro en la base", "/cycle/start")
        # SAF-01 de T8: sin base, el respaldo es el único registro electrónico
        error = context.respaldo_ciclos.probar_escritura()
        if error is not None:
            _rechazar(503, "respaldo_no_disponible",
                      f"Sin base de datos y sin respaldo del ciclo ({error}): no se puede "
                      "iniciar un ciclo", "/cycle/start")
    if getattr(context.control_loop, "apagando", False) is True:
        _rechazar(409, "apagado_en_curso", "El equipo se está apagando", "/cycle/start")

    # S2 (revisión): la validación del programa y START_CICLO van juntas bajo
    # el lock de la máquina: un /cycle/select concurrente no puede cambiar el
    # programa entre la validación y el inicio. La bitácora del rechazo se
    # escribe al soltar el lock.
    with context.control_loop.bloqueo_maquina():
        # TMG-04 / SAF-02 de la revisión S2b (D8-2.11): ni con el modo prueba
        # activo ni con el ALL_OFF de su salida sin confirmar (la máquina está
        # pausada: START_CICLO quedaría pendiente y el ciclo arrancaría solo)
        rechazo = _rechazo_salidas_pendientes() or _validar_inicio(estado)
        if rechazo is None:
            estado.operador_inicio = sesion_operador.usuario if sesion_operador else ""
            estado.set_flag("START_CICLO", True)
    if rechazo is not None:
        if rechazo[0] is None:
            raise HTTPException(status_code=409, detail=rechazo[1])
        _rechazar(409, rechazo[0], rechazo[1], "/cycle/start")
    return {"ok": True, "action": "START_CICLO"}


PRINCIPAL_SIN_LECTURA = "PRINCIPAL_SIN_LECTURA"


def _rechazo_principal_sin_lectura(estado) -> tuple | None:
    """(código, motivo) si el sensor Principal del programa seleccionado está
    declarado y sin lectura válida; None si lee (o no está declarado: ese
    caso lo rechaza verificar_inicio con su propio código, igual que un error
    al evaluar)."""
    seleccionado = getattr(context.control_loop, "cycle", None)
    try:
        principal = sc.sensor_principal(seleccionado)
        if sc.estado_sensor(getattr(context, "profile", None), estado, principal) != sc.SIN_SENAL:
            return None
    except Exception:
        # sin rechazo propio: verificar_inicio (RS-06) vuelve a exigir lectura
        logger.exception("/cycle/start: no se pudo evaluar el sensor Principal")
        return None
    from autoclave import i18n
    return PRINCIPAL_SIN_LECTURA, i18n.t("ciclo.principal_sin_lectura")


def _validar_inicio(estado) -> tuple | None:
    """(código, motivo) si el programa seleccionado no puede iniciarse; código
    None = rechazo sin código (no listo). Llamar bajo bloqueo_maquina()."""
    # P-2 (tanda 6): sin lectura válida del Principal del programa no se
    # inicia; el motivo se da antes que "no está listo" (con el estado seguro
    # de la pérdida del Principal en curso, el equipo nunca queda listo)
    principal_sin_lectura = _rechazo_principal_sin_lectura(estado)
    if principal_sin_lectura is not None:
        return principal_sin_lectura
    # S1 (tanda 8, D8-1.3): transductor de presión (cámara, o chaqueta si
    # io_enabled la declara) sin lectura: "llame a servicio", también antes
    # que "no está listo". Falla cerrada: un error al evaluar no inicia.
    try:
        from autoclave.core.runtime import presion_sin_lectura
        presion = presion_sin_lectura.rechazo_inicio(estado)
    except Exception:
        logger.exception("/cycle/start: no se pudo evaluar la presión sin lectura")
        presion = ("PRESION_NO_VERIFICABLE", _i18n_t("ciclo.presion_no_verificable"))
    if presion is not None:
        return presion
    if not estado.get_flag("LISTO_PARA_CICLO"):
        return None, "El sistema no está listo para iniciar un ciclo"

    # RB-04.4 (T10): un programa dañado no se inicia
    seleccionado = getattr(context.control_loop, "cycle", None)
    danado = getattr(seleccionado, "danado", None)
    if isinstance(danado, list) and danado:
        return "PROGRAMA_NO_EDITABLE", f"Programa dañado (fuera del catálogo): {danado[0]}"

    # T11: un programa de carga líquida solo en equipos con capacidad de líquidos
    if seleccionado is not None and _carga_liquida(seleccionado):
        cap = getattr(context, "cap", None)
        if cap is not None and getattr(cap, "has_liquids", None) is False:
            return "carga_liquida_no_disponible", "Este equipo no admite programas de carga líquida"

    # RS-06 (tanda §1.1): asignación de sensores válida y todos los sensores
    # en uso del programa seleccionado con lectura
    return sc.verificar_inicio(seleccionado, getattr(context, "profile", None), estado)


@router.post("/cycle/abort")
def abort_cycle(authorization: str | None = Header(None)):
    """
    Solicita el aborto del ciclo en curso.
    Activa la flag CICLO_CANCELADO; el CicloState ejecutará el
    protocolo de fallo en el siguiente tick del control loop.
    FC-12 (tanda 21): como /cycle/start (O1, tanda 3), acepta un token de
    sesión opcional en la cabecera `Authorization: Bearer <token>`. Si es
    válido, su usuario queda como `cancelado_por` (estado, bitácora y
    ticket). No es requisito: sin token o con uno vencido la cancelación
    funciona igual (plan §10) y queda sin usuario identificado.
    """
    sesion = tokens.obtener(_token_de(authorization))
    # P-7 (tanda 6): 409 con motivo cuando no tendría efecto (resultado ya
    # pendiente o paro); el indicador no queda puesto
    entidad = "/cycle/abort"
    with guard_estado(frozenset(), entidad) as actual:
        estado = context.estado
        if actual != GlobalState.CICLO:
            raise _Rechazo(409, "estado_no_permitido", "No hay un ciclo en curso")
        fase = getattr(estado, "fase_ciclo", "")
        pendiente = isinstance(fase, str) and progreso_ciclo.resultado(fase) is not None
        en_espera_datos = False
        if estado.get_flag("PARO_EMERGENCIA") is True:
            # R1-P5 (tanda 7): sin datos de las entradas pero dentro de la
            # tolerancia por DI vencida, la cancelación se acepta y queda en
            # espera; con el paro real (o fuera de la tolerancia), 409.
            # D8-2.13 (tanda 8): igual con el módulo E/S totalmente desconectado
            # antes de COM-02 (tolerancia de desconexión del ControlLoop)
            en_espera_datos = (not pendiente and estado.get_flag("PARO_REAL") is not True
                               and (_ciclo_en_tolerancia_di()
                                    or _desconexion_en_tolerancia()))
            if not en_espera_datos:
                raise _Rechazo(409, "paro_emergencia",
                               _motivo_paro("Paro de emergencia activado: el ciclo ya se detuvo"))
        if pendiente:
            raise _Rechazo(409, "resultado_pendiente",
                           "El ciclo ya terminó: confirme el resultado")
        # Idempotencia (revisión T21): comprobación y marcado atómicos bajo
        # _sm_lock. Si la cancelación ya está pedida y el tick aún no la
        # consumió, esta llamada no vuelve a auditar ni pisa `cancelado_por`.
        ya_pedida = estado.get_flag("CICLO_CANCELADO") is True
        if not ya_pedida:
            # FC-12: antes de la bandera, así CicloState y CycleLogger ya lo ven
            estado.cancelado_por = sesion.usuario if sesion is not None else None
            estado.set_flag("CICLO_CANCELADO", True)
        detalle = {"fase": fase if isinstance(fase, str) else ""}
        operador = getattr(estado, "operador_inicio", "") or ""
        detalle["operador_ciclo"] = operador if isinstance(operador, str) else ""
        if sesion is None:
            detalle["sin_sesion"] = True
        if en_espera_datos:
            detalle["en_espera_datos"] = True
    if not ya_pedida:
        ciclo_id = None
        try:
            ciclo_id = _ciclo_de_pantalla()
            fila = context.db.get_ciclo(ciclo_id) if isinstance(ciclo_id, int) else None
            if fila is not None:
                detalle["ciclo_db_id"] = ciclo_id
                detalle["numero_ciclo"] = fila["numero_ciclo"]
        except Exception as e:
            logger.debug("/cycle/abort: sin número de ciclo para la bitácora")
            # Sin base de datos (u otro fallo de lectura) la cancelación sigue
            # su curso, pero no queda fila ni número de ciclo: dejarlo claro
            logger.warning("/cycle/abort: cancelación aceptada, pero la bitácora queda sin "
                           "número de ciclo o sin fila (ciclo_id=%s): %s",
                           ciclo_id if ciclo_id is not None else "desconocido",
                           type(e).__name__)
        # FC-12 (tanda 21): fila de la cancelación, con el usuario si lo hay
        _auditar("ciclo_cancelado", sesion, entidad=entidad,
                 valor_nuevo=detalle.get("numero_ciclo"), detalle=detalle)
    else:
        logger.info("/cycle/abort: cancelación ya pedida; segunda llamada sin efecto "
                    "(usuario=%s)", sesion.usuario if sesion is not None else "-")
    if en_espera_datos:
        logger.warning("/cycle/abort: cancelación aceptada sin datos del módulo E/S "
                       "(tolerancia por DI vencida o desconexión antes de COM-02)")
        return {"ok": True, "action": "CICLO_CANCELADO", "pendiente": True,
                "codigo": "cancelacion_en_espera_datos",
                "mensaje": _i18n_t("ciclo.cancelacion_en_espera_datos")}
    return {"ok": True, "action": "CICLO_CANCELADO"}


def _rechazo_salidas_pendientes() -> tuple | None:
    """TMG-04 de la revisión S2b: (código, motivo) para /cycle/start con el
    modo prueba activo o con el ALL_OFF de su salida sin confirmar."""
    if getattr(context.control_loop, "test_mode_active", False) is True:
        return "modo_prueba_activo", "No permitido con el modo prueba activo"
    if _salidas_sin_confirmar_pendiente():
        return "salidas_sin_confirmar", _i18n_t("ciclo.salidas_sin_confirmar_pendiente")
    return None


def _ciclo_en_tolerancia_di() -> bool:
    """R1-P5: el ciclo está en la tolerancia por DI vencida. Llamar bajo
    _sm_lock. Ante cualquier duda, False (se rechaza como antes)."""
    try:
        return context.control_loop.state_machine.ciclo.tolerancia_di_activa is True
    except Exception:
        return False


def _desconexion_en_tolerancia() -> bool:
    """D8-2.13: el módulo E/S está desconectado y no venció la tolerancia de
    COM-02. Llamar bajo _sm_lock. Ante cualquier duda, False."""
    try:
        return context.control_loop.desconexion_en_tolerancia is True
    except Exception:
        return False


_MOTIVO_PARO = "Paro de emergencia activado: suéltelo antes de reconocer"


@router.post("/fault/reset")
def reset_fault():
    """Reconoce el estado de falla y solicita retornar a PREPARACION. Sin
    identificación (decisión 16). Con el paro de emergencia activo, 409 y no
    se guarda RESET_FALLA: tras soltarlo hay que reconocer de nuevo (§5.9)."""
    entidad = "/fault/reset"
    with guard_estado(frozenset(), entidad) as estado:
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro(_MOTIVO_PARO))
        # con el modo prueba la máquina está pausada: el reconocimiento se
        # aplicaría al salir, sin uno posterior a las pruebas (TMG-07)
        if context.control_loop.test_mode_active is True:
            raise _Rechazo(409, "modo_prueba_activo", "No permitido con el modo prueba activo")
        # SAF-01 de la revisión S2b (D8-2.11): igual mientras se reintenta el
        # ALL_OFF de la salida del modo prueba (la máquina sigue pausada)
        if _salidas_sin_confirmar_pendiente():
            raise _Rechazo(409, "salidas_sin_confirmar",
                           _i18n_t("ciclo.salidas_sin_confirmar_pendiente"))
        if estado != GlobalState.FALLA:
            raise _Rechazo(409, "estado_no_permitido", "El sistema no está en estado de falla",
                           extra={"estado": getattr(estado, "name", str(estado))})
        context.estado.set_flag("RESET_FALLA", True)
    # Fin de ciclo §15.2: reconocer la falla tras soltar el paro es también
    # "Confirmar y llevar a estado seguro" (fusionados, cualquier operador)
    context.control_loop.confirmar_estado_seguro()
    _auditar("falla_reconocida", entidad=entidad)
    return {"ok": True, "action": "RESET_FALLA"}


@router.post("/safe-state/confirm")
def confirm_safe_state():
    """"Confirmar y llevar a estado seguro" (fin de ciclo §15.2): tras soltar
    el paro, el protocolo de estado seguro no avanza hasta esta confirmación.
    Cualquier operador, sin rol. 409 con el paro activo o si no hace falta."""
    entidad = "/safe-state/confirm"
    if context.estado.get_flag("PARO_EMERGENCIA"):
        _rechazar(409, "paro_emergencia",
                  _motivo_paro("Paro de emergencia activado: suéltelo antes de confirmar"),
                  entidad)
    if context.control_loop.confirmar_estado_seguro() is not True:
        _rechazar(409, "sin_confirmacion_pendiente",
                  "No hay un estado seguro pendiente de confirmación", entidad)
    return {"ok": True}


@router.post("/outputs/reset")
def reset_outputs():
    """
    Apaga todas las salidas digitales y detiene el control loop.
    Llamar antes de cerrar la aplicación o ante cualquier apagado seguro.
    409 en CICLO: para detener un ciclo existe /cycle/abort.
    """
    # Solo la comprobación va dentro de _sm_lock: stop() espera al hilo del
    # loop, que puede estar esperando ese mismo lock. Si un ciclo arrancara
    # justo después, stop() lo deja con todo apagado (estado seguro).
    with guard_estado(DISTINTO_DE_CICLO, "/outputs/reset"):
        pass
    try:
        context.control_loop.stop()   # evita que el loop re-active salidas durante el reset
        context.setdo.reset_all_outputs()
        logger.info("outputs/reset: todas las salidas apagadas")
        return {"ok": True}
    except Exception as e:
        logger.error("outputs/reset error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cycle/acknowledge")
def acknowledge_cycle():
    """
    El operador confirmó que vio el resultado del ciclo.
    Activa CICLO_CONFIRMADO para que CicloState libere la transición.
    Solo tiene efecto mientras el estado sea CICLO (esperando confirmación).
    """
    entidad = "/cycle/acknowledge"
    with guard_estado(frozenset(), entidad) as actual:
        if actual != GlobalState.CICLO:
            raise _Rechazo(409, "estado_no_permitido", "No hay un ciclo esperando confirmación",
                           extra={"estado": getattr(actual, "name", str(actual))})
        # §5.9: con el paro activo no se confirma ni se guarda RESET_FALLA
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro(_MOTIVO_PARO))
        # solo con el ciclo ya terminado: una confirmación a mitad de ciclo
        # quedaba guardada y la máquina salía al terminar sin que el operador
        # viera el resultado (TMG-03/SAF-07)
        fase = getattr(context.estado, "fase_ciclo", "")
        if progreso_ciclo.resultado(fase) is None:
            raise _Rechazo(409, "sin_resultado", "No hay un ciclo esperando confirmación")
        # FC-08 (tanda 21): se retiró el 409 no_conforme_sin_reconocer (P4)

        context.estado.set_flag("CICLO_CONFIRMADO", True)

        # El operador ya vio el resultado en la pantalla del ciclo: si terminó
        # en cualquier FALLO (FALLO_*, EMERGENCIA, SENSOR_AUSENTE, ...), se
        # pre-arma RESET_FALLA para no exigir un segundo reconocimiento
        # (§5.9; antes solo FALLO_* y EMERGENCIA, y SENSOR_AUSENTE dejaba la
        # máquina en FALLA sin salida desde QML, OPC-22).
        reconoce_falla = progreso_ciclo.resultado(fase) == "fallo"
        if reconoce_falla:
            context.estado.set_flag("RESET_FALLA", True)
    if reconoce_falla:
        _auditar("falla_reconocida", entidad=entidad, detalle={"fase": fase})
    return {"ok": True, "action": "CICLO_CONFIRMADO"}


# ── P4 (tanda 16, D-14.4) retirado en la tanda 21 (FC-08): ya no existen
# POST /cycle/acknowledge-no-conforme ni el 409 no_conforme_sin_reconocer.
# El evento de bitácora ciclo_no_conforme_reconocido se conserva solo para
# leer las filas históricas.
