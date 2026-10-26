# autoclave/backend/rutas/sistema.py
#
# Sistema: arranque, estado, hora, información, bitácora, parámetros del
# equipo, idioma, red y base de datos.
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

from types import SimpleNamespace
import logging
from datetime import date, datetime, timedelta
from typing import Literal
from fastapi import Depends
from pydantic import BaseModel, StrictBool, StrictFloat, StrictInt
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.catalogo import ROLES_VISIBLES
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime import camara_segura
from autoclave.installation.profile import (entradas_no_monitoreadas, sondas_no_vigiladas,
    tarjeta_emparejada)
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, RechazoApi, _auditar,
    _log_desarrollo, _rechazar, actividad_ui, context, guard_estado, registro_arranque,
    requiere_rol)
from autoclave.backend.rutas._comun import (_LEEN_CONECTIVIDAD, _campos_motivo, _no_conforme_status,
    _p_atm_vigente, _salidas_sin_confirmar_pendiente)
from autoclave.backend.rutas.mantenimiento import _calibracion_atm_en_curso

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


@router.get("/arranque")
def get_arranque():
    return registro_arranque.instantanea()


# ── Fecha y hora (O2c, tanda 6; decisión 1.10): SOLO LECTURA ──────────────
# No hay ajuste: el reloj es el de Windows. Se informa la hora, la zona y si
# el reloj es anterior a la fecha de instalación (M1-01, clock_guard).

def _info_reloj(ahora: datetime | None = None) -> dict:
    ahora = (ahora or datetime.now()).astimezone()
    perfil = getattr(context, "profile", None)
    inst = getattr(perfil, "created_at", None) if perfil is not None else None
    inst = inst if isinstance(inst, datetime) else None
    off = ahora.utcoffset()
    minutos = int(off.total_seconds() // 60) if off is not None else 0
    signo = "+" if minutos >= 0 else "-"
    h, m = divmod(abs(minutos), 60)
    nombre = ahora.tzname() or ""
    zona = f"UTC{signo}{h:02d}:{m:02d}"
    if nombre and not nombre.startswith("UTC"):
        zona += f" ({nombre})"
    return {
        "ahora": ahora.isoformat(timespec="seconds"),
        "zona": zona,
        "utc_offset_min": minutos,
        "instalacion": inst.isoformat(timespec="seconds") if inst else None,
        "reloj_anterior_instalacion": bool(inst and ahora.date() < inst.date()),
        "ajuste_habilitado": False,
    }


@router.get("/system/time")
def get_system_time():
    return _info_reloj()


# ── Información del sistema (O2d, tanda 6; mockup 8): solo lectura ──────────
# Cada parte se lee por separado: un dato que falla queda en None ("—") sin
# afectar a los demás.

def _parte(lector):
    try:
        return lector()
    except Exception:
        logger.debug("Información del sistema: dato no disponible", exc_info=True)
        return None


def _hay_red() -> bool:
    """True si el PC tiene alguna dirección IPv4 distinta del loopback."""
    import socket
    nombre = socket.gethostname()
    return any(not ip.startswith("127.") for ip in socket.gethostbyname_ex(nombre)[2])


def _estado_impresora() -> str:
    if not context.config_impresora.habilitada():
        return "deshabilitada"
    estado = context.realtime_printer.estado()
    return estado if isinstance(estado, str) and estado else "desconocido"


@router.get("/system/info")
def get_system_info():
    from autoclave._version import version_completa   # VER-03/VER-05
    perfil = getattr(context, "profile", None)

    def de_perfil(attr):
        v = getattr(perfil, attr, None) if perfil is not None else None
        if isinstance(v, datetime):
            return v.isoformat(timespec="seconds")
        return getattr(v, "value", v) if isinstance(v, (str, int, float)) or hasattr(v, "value") else None

    tarjeta = _parte(_tarjeta_status) or {}
    capacidad = getattr(perfil, "capacidad_litros", None) if perfil is not None else None
    carga = getattr(perfil, "tipo_carga", None) if perfil is not None else None
    clase = getattr(perfil, "equipment_class", None) if perfil is not None else None
    clase = getattr(clase, "value", clase)
    unidades = _parte(context.config_unidades.leer)
    red = _parte(_hay_red)
    return {
        "equipo": {"modelo": de_perfil("model_id"), "serie": de_perfil("serial_number"),
                   "instalacion": de_perfil("created_at"), "fuente_vapor": de_perfil("vapor_source"),
                   # M1 (tanda 7): None en perfiles anteriores (la pantalla muestra "—")
                   "capacidad_litros": capacidad if type(capacidad) is int else None,
                   "tipo_carga": carga if carga in ("V", "H") else None,
                   # E2 (tanda 8; D8-0): valor interno; la pantalla lo traduce
                   "clase": clase if isinstance(clase, str) else None},
        "software": {"version": _parte(version_completa),
                     "firmware": tarjeta.get("version") if isinstance(tarjeta, dict) else None,
                     "id_tarjeta": tarjeta.get("id") if isinstance(tarjeta, dict) else None},
        "uso": {"ciclos": _parte(context.db.max_numero_ciclo),
                "mantenimiento": _parte(context.mantenimiento.resumen)},
        "configuracion": {"idioma": _parte(context.config_idioma.leer),
                          "unidades": unidades if isinstance(unidades, dict) else None,
                          "impresora": _parte(_estado_impresora),
                          "red": None if red is None else ("conectada" if red else "sin_red")},
    }


# ── Bitácora de auditoría (O2e, tanda 6): solo lectura ────────────────────
# La ven admin, técnico e ingeniero; nadie edita ni borra (audit_log es de
# solo anexar, migración v4). Valores en la unidad vigente.

_POR_PAGINA_MAX = 100


@router.get("/audit_log")
def get_audit_log(pagina: int = 1, por_pagina: int = 20, desde: date | None = None,
                  hasta: date | None = None, usuario: str | None = None, evento: str | None = None,
                  sesion: Sesion = Depends(requiere_rol(ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import bitacora
    pagina = max(1, pagina)
    por_pagina = max(1, min(por_pagina, _POR_PAGINA_MAX))
    filas, total = context.db.consultar_auditoria(
        desde=desde.isoformat() if desde else None,
        hasta=(hasta + timedelta(days=1)).isoformat() if hasta else None,
        usuario=usuario or None, evento=evento or None,
        limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina)
    usuarios, eventos = context.db.valores_auditoria()
    try:
        metas = {p["clave"]: p for p in context.config_manager.describir()}
    except Exception:
        metas = {}
    try:
        unidades = context.config_unidades.leer()
        unidades = unidades if isinstance(unidades, dict) else {}
    except Exception:
        unidades = {}
    p_atm = _parte(_p_atm_vigente)
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    return {"filas": [bitacora.presentar(f, metas, unidades, p_atm) for f in filas],
            "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "paginas": paginas, "usuarios": usuarios, "tipos": eventos}


class _SuspensionBody(BaseModel):
    activa: StrictBool
    pantalla: str = ""


@router.post("/ui/standby")
def registrar_suspension(body: _SuspensionBody):
    """O2e: una pantalla QML informa que entró o salió de suspensión (no
    cambia nada del equipo). D9-6 (tanda 9): solo log de desarrollo."""
    _log_desarrollo("suspension_entra" if body.activa else "suspension_sale", usuario="sistema",
                    entidad=body.pantalla[:40])
    return {"ok": True}


def _diagnostico_comunicacion() -> dict | None:
    """Contadores y estado del enlace serial con la tarjeta (diagnóstico)."""
    try:
        diag = context.serial.get_diagnostico()
    except Exception:
        return None
    return diag if isinstance(diag, dict) else None


def _tarjeta_status() -> dict:
    """Versión e ID de la tarjeta de E/S del último handshake y si coincide
    con la emparejada en el perfil (FW-D7: solo advertencia, no bloquea)."""
    try:
        info = context.serial.tarjeta()
    except Exception:
        info = None
    if not isinstance(info, dict):
        info = {}
    ident = info.get("id")
    return {
        "version": info.get("version"),
        "id": ident,
        "emparejada": tarjeta_emparejada(getattr(context, "profile", None), ident),
    }


def _hora_iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _alarma_dto(inst) -> dict:
    """Instancia de alarma → JSON de /status (spec 2026-10-06 §7.1). Los
    campos id/level/description/source_state mantienen compatible a la UI
    actual hasta la Parte C."""
    origen = inst.origen or ""
    from autoclave.core.runtime import alarmas_i18n
    return {
        # I1 (tanda 5): código + parámetros y los textos en cada idioma; la
        # descripción en español sigue siendo la registrada (compatibilidad)
        "valores": alarmas_i18n.valores_json(inst.valores),
        "textos": alarmas_i18n.por_idioma(inst.definicion, inst.valores or {}),
        "clave": inst.clave,
        "codigo": inst.codigo,
        "nivel": inst.nivel.name,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        # T10 (D10-3): la acción según la causa (CIC-10 sin presión de cámara)
        "accion": alarmas_i18n.accion(inst.definicion, inst.valores or {}),
        "origen": origen,
        "aparecida": _hora_iso(inst.aparecida),
        "estado": inst.estado.value,
        "requiere_reconocimiento": inst.nivel.requiere_reconocimiento,
        "reconocida_por": inst.reconocida_por,
        # LIC-02 (licencia L0): [] = la ven todos; si no, solo esos roles
        "roles_visibles": sorted(ROLES_VISIBLES.get(inst.codigo, ())),
        "id": inst.clave,
        "level": inst.nivel.nombre_compat,
        "description": inst.descripcion,
        "source_state": origen,
    }


def _evento_dto(inst) -> dict:
    return {
        "codigo": inst.codigo,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        "origen": inst.origen or "",
        "hora": _hora_iso(inst.aparecida),
    }


def _estado_seguro_status() -> dict:
    """Protocolo de estado seguro (fin de ciclo §15): activo y si espera la
    confirmación "Confirmar y llevar a estado seguro"."""
    es = getattr(context.control_loop, "estado_seguro", None)
    activo = getattr(es, "activo", False) is True
    motivo = getattr(es, "bloqueado_motivo", None) if activo else None
    # S9 (D9-1.2): paro_liberado / arranque / fallo / cancelado / completado
    causa = getattr(es, "causa", None) if activo else None
    try:
        ack_confirma = getattr(context.control_loop.state_machine.ciclo,
                               "ack_confirma_estado_seguro", False) is True
    except Exception:
        ack_confirma = False
    return {"activo": activo,
            # P-6 (tanda 6): el CONFIRMAR del ciclo también confirma el estado seguro
            "ack_confirma_estado_seguro": ack_confirma,
            "requiere_confirmacion": activo and getattr(es, "requiere_confirmacion", False) is True,
            # S4: CIC-10 (el protocolo no puede terminar solo); None si avanza
            "bloqueado_motivo": motivo if isinstance(motivo, str) else None,
            "causa": causa if isinstance(causa, str) else None}


def _camara_segura_status(estado) -> dict:
    try:
        programas = context.programas_para_seguridad()
        # S9, revisión ★ pasada 3 (R3-M1): con la presión al día (DI + AI +
        # estado publicado); con la trama AI vencida la presión puede estar
        # congelada. Falla cerrada.
        vigentes = getattr(context.control_loop, "presion_vigente", False) is True
        segura, motivo = camara_segura.evaluar(estado, context.config_manager, programas,
                                               getattr(context, "profile", None),
                                               datos_vigentes=vigentes,
                                               temp_max_ciclo=context.temp_max_tras_ciclo())
    except Exception as exc:
        logger.exception("/status: no se pudo evaluar camara_segura")
        segura, motivo = False, f"No se pudo evaluar: {exc}"
    campos = _campos_motivo(motivo)
    return {"camara_segura": segura, "no_abrir": not segura, "camara_segura_motivo": motivo,
            # I4 (tanda 6): código, parámetros y textos es/en del motivo (o None)
            "camara_segura_motivo_codigo": campos.get("motivo_codigo"),
            "camara_segura_motivo_valores": campos.get("motivo_valores"),
            "camara_segura_motivo_textos": campos.get("motivo_textos")}


def _sensores_programa(estado) -> dict:
    try:
        programa = context.programa_para_sensores()
    except Exception:
        programa = None
    # una sola lectura de la asignación (TMG-05 de T3)
    instantanea = SimpleNamespace(sensores=dict(sc.asignacion_de(programa)))
    principal = sc.sensor_principal(instantanea)
    return {
        "sensor": principal,
        "nombre": sc.NOMBRES[principal],
        "valor": estado.sensores_temp.get(principal),
        "referencias": [{"sensor": s, "nombre": sc.NOMBRES[s],
                         "valor": estado.sensores_temp.get(s)}
                        for s in sc.sensores_referencia(instantanea)],
    }


def _cuentas_adc() -> dict:
    """B-ES-1: cuentas ADC crudas por sensor (clave de EstadoAutoclave).
    raw_ai: 0-7 temperatura, 8-15 presión. None si no hay datos de la tarjeta."""
    try:
        raw = context.units.get_all()["raw_ai"]
        if not isinstance(raw, (list, tuple)):
            raw = []
    except Exception:
        raw = []

    def cuenta(i):
        return raw[i] if i < len(raw) else None

    adc = {k: cuenta(i) for k, i in EstadoAutoclave.map_temp.items()}
    adc.update({k: cuenta(8 + i) for k, i in EstadoAutoclave.map_pres.items()})
    return adc


@router.get("/status", response_model=None)
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
            "camara_2": estado.sensores_temp.get("temp_2_camara"),
            "ref": estado.sensores_temp.get("temp_ref"),
            "drenaje": estado.sensores_temp.get("temp_drenaje"),
        },
        # Tanda §1.1: sensor Principal del programa vigente (seleccionado; en
        # CICLO, el del ciclo en curso) y sus Referencias
        "principal": _sensores_programa(estado),
        "pressure": {
            "camara": estado.sensores_pres.get("pres_camara"),
            "chaqueta": estado.sensores_pres.get("pres_chaqueta"),
            "empaque_1": estado.sensores_pres.get("pres_empaque_1"),
            "empaque_2": estado.sensores_pres.get("pres_empaque_2"),
        },
        "adc": _cuentas_adc(),
        "digital_inputs": dict(estado.sensores_di),

        "digital_outputs": dict(estado.salidas_do),

        "flags": dict(estado.flags),
    }

    # ------------------------------
    # ALARMAS
    # ------------------------------
    # Hasta la Parte C (botón de reconocer en la UI) las pantallas actuales solo
    # ven las ACTIVA en "alarms"; las RESUELTA_SIN_RECONOCER van aparte.
    instancias = context.alarm_manager.activas()
    alarms = [_alarma_dto(inst) for inst in instancias
              if inst.estado is EstadoInstancia.ACTIVA]
    alarmas_sin_reconocer = [_alarma_dto(inst) for inst in instancias
                             if inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER]
    eventos_recientes = [_evento_dto(inst) for inst in context.alarm_manager.eventos_recientes()]

    # ------------------------------
    # RESPUESTA FINAL (DTO)
    # ------------------------------
    return {
        "machine_state":        machine_state,
        # T8 (§7.1): operación sin base de datos (alarma OPERANDO_SIN_BD)
        "sin_base_de_datos":    getattr(context, "sin_base_de_datos", False) is True,
        "fase_ciclo":            getattr(estado, "fase_ciclo", ""),
        "fase_en_sostenimiento": getattr(estado, "fase_en_sostenimiento", False),
        # P4 (tanda 16, D-14.4): ciclo NO CONFORME (Referencia sin verificar),
        # su motivo (clave i18n) y si el operador ya reconoció la carga no liberable
        **_no_conforme_status(estado),
        "prevacio_progreso":     getattr(estado, "prevacio_progreso", ""),
        # Del enlace serial, no de Units: Units solo se entera por on_update
        # y no refleja el handshake (ver planeacion_protocolo_serial_esp32.md).
        # E2 (fin de ciclo §5): falla cerrada; "NO ABRIR" en cualquier estado
        **_camara_segura_status(estado),
        "estado_seguro":         _estado_seguro_status(),
        "card_connected":        context.serial.is_connected(),
        # U4 (tanda 2): desconectada / sin_tramas_validas / ok
        "estado_tarjeta":        _estado_tarjeta(),
        "comunicacion":          _diagnostico_comunicacion(),
        "tarjeta":               _tarjeta_status(),
        "test_mode_active":      context.control_loop.test_mode_active,
        # D8-2.11 (TMG-03 de la revisión S2b): reintentos del ALL_OFF en curso
        "salidas_sin_confirmar_pendiente": _salidas_sin_confirmar_pendiente(),
        "calibracion_atm_en_curso": _calibracion_atm_en_curso(),   # O2f
        "ui_inactividad_s":      actividad_ui.inactividad_s(),
        "doors":   doors,
        "sensors": sensors,
        "alarms":  alarms,
        # Entradas de suministro que el perfil declara sin cablear (E1-1)
        "entradas_no_monitoreadas": entradas_no_monitoreadas(getattr(context, "profile", None)),
        # Canales de temperatura que el perfil declara sin sonda (A-2)
        "sondas_no_vigiladas": sondas_no_vigiladas(getattr(context, "profile", None)),
        "alarmas_sin_reconocer": alarmas_sin_reconocer,
        "eventos_recientes": eventos_recientes,
    }

@router.post("/ui/activity")
def registrar_actividad_ui():
    """Una pantalla QML informa un toque/tecla del operador. Reinicia el
    contador de inactividad común a ambas pantallas (standby simultáneo)."""
    actividad_ui.registrar()
    return {"ok": True}


@router.get("/global_params")
def get_global_params():
    cm = context.config_manager
    return cm.instantanea() if hasattr(cm, "instantanea") else cm.get()


# ── Parámetros del equipo (O2a, tanda 6; planeacion_opciones.md v4 §3.2) ──
# Lectura libre (como /global_params). Cambio y restablecimiento: técnico e
# ingeniero (el admin los ve en solo lectura: 403, decisión 1.5), solo fuera de
# CICLO para todos (409, también el ingeniero) y aplicados sin reiniciar: el
# ConfigManager escribe en system_params y en memoria, y cada lector consulta
# el valor vigente (OPC-11). Auditoría `param_sistema_cambio`.
# La presión atmosférica de referencia no se cambia por aquí (solo O2f).

class _ParametroSistemaBody(BaseModel):
    valor: StrictInt | StrictFloat


_CODIGO_PARAMETRO = {
    "no_existe": (404, "Parámetro desconocido"),
    "solo_lectura": (403, "Este parámetro no se puede modificar"),
    "tipo_invalido": (422, "Valor inválido para este parámetro"),
    "fuera_de_rango": (422, "Valor fuera del rango permitido"),
    "incoherente": (422, "Valor incompatible con otro parámetro del equipo (presión atmosférica, "
                    "empaque o límites de presión)"),
    "sin_base_de_datos": (503, "No se pudo guardar el parámetro"),
}


def _parametro_o_404(clave: str) -> dict:
    from autoclave.core.managers.config_manager import ErrorParametro
    try:
        return context.config_manager.describir(clave)
    except ErrorParametro:
        raise RechazoApi(404, "no_existe", "Parámetro desconocido")


@router.get("/system_params")
def get_system_params():
    """Lista para la pantalla: valor vigente, defecto, rango, unidad, clase,
    submenú y último cambio (usuario y fecha). D9-3 (tanda 9): `grupos` son
    los submenús que se muestran según el perfil (sin Puerta ni Empaque en un
    equipo de puertas simples), y solo van los parámetros de esos submenús."""
    from autoclave.core.managers.config_manager import grupos_visibles
    from autoclave.installation.profile import puertas_simples
    grupos = grupos_visibles(puertas_simples(getattr(context, "profile", None)))
    parametros = [p for p in context.config_manager.describir() if p.get("grupo") in grupos]
    return {"parametros": parametros, "grupos": grupos}


@router.get("/global_params/{clave}")
def get_global_param(clave: str):
    return _parametro_o_404(clave)


def _cambiar_parametro_sistema(clave: str, sesion: Sesion, valor=None, restablecer=False):
    from autoclave.core.managers.config_manager import ErrorParametro
    entidad = f"/global_params/{clave}"
    p = _parametro_o_404(clave)
    if p["solo_lectura"]:
        _rechazar(403, "solo_lectura", _CODIGO_PARAMETRO["solo_lectura"][1], entidad, sesion)
    error = None
    # TMG-01: validación y escritura en SQLite FUERA del guard (no detienen el
    # tick); dentro solo se comprueba el estado y se publica en memoria. Si
    # mientras tanto arrancó un ciclo: 409 y se deshace la escritura.
    if _calibracion_atm_en_curso():         # O2f: la referencia está midiéndose
        _rechazar(409, "calibracion_en_curso", "Calibración atmosférica en curso", entidad, sesion)
    cm = context.config_manager
    with cm.lock_cambios:
        return _cambiar_serializado(cm, clave, p, entidad, sesion, valor, restablecer)


def _cambiar_serializado(cm, clave, p, entidad, sesion, valor, restablecer):
    from autoclave.core.managers.config_manager import ErrorParametro
    if _calibracion_atm_en_curso():         # TMG-03 de O2f: de nuevo, bajo lock_cambios
        _rechazar(409, "calibracion_en_curso", "Calibración atmosférica en curso", entidad, sesion)
    error = None
    try:
        if restablecer:
            anterior, nuevo = cm.restablecer(clave, sesion.usuario, aplicar=False)
        else:
            anterior, nuevo = cm.fijar(clave, valor, sesion.usuario, aplicar=False)
    except ErrorParametro as e:
        error = e
    if error is None:
        try:
            with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
                cm.aplicar_valor(p["clave"], nuevo, sesion.usuario)
        except RechazoApi:
            cm.revertir_bd(p["clave"], anterior)
            raise
    if error is not None:
        status, motivo = _CODIGO_PARAMETRO.get(error.codigo, (422, "Valor inválido"))
        if status in (401, 403, 409):
            _rechazar(status, error.codigo, motivo, entidad, sesion)
        raise RechazoApi(status, error.codigo, motivo,
                         extra={"min": p["min"], "max": p["max"]} if error.codigo == "fuera_de_rango" else None)
    _auditar("param_sistema_cambio", sesion, entidad=entidad,
             valor_anterior={p["clave"]: anterior}, valor_nuevo={p["clave"]: nuevo},
             detalle={"clave": p["clave"], "accion": "restablecer" if restablecer else "cambio"})
    # R (tanda 16, V16-s4-01 / s3-03): un límite de presión del equipo nuevo
    # rige también para los programas ya cargados (DEU-01): los que ahora lo
    # incumplen quedan DAÑADOS sin esperar al próximo arranque
    from autoclave.core.managers.config_manager import CLAVES_LIMITES_PRESION
    if p["clave"] in CLAVES_LIMITES_PRESION:
        try:
            revalidar = getattr(context.cycle_manager, "revalidar_programas", None)
            if callable(revalidar):
                revalidar()
        except Exception:
            logger.exception("No se pudieron revalidar los programas tras cambiar %s", p["clave"])
    return {"ok": True, "parametro": context.config_manager.describir(p["clave"])}


@router.patch("/global_params/{clave}")
def patch_global_param(clave: str, body: _ParametroSistemaBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    return _cambiar_parametro_sistema(clave, sesion, valor=body.valor)


@router.post("/global_params/{clave}/reset")
def reset_global_param(clave: str,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    return _cambiar_parametro_sistema(clave, sesion, restablecer=True)


# ── Impresora (B5, tanda 4) ─────────────────────────────────────────────────
# `habilitada` solo gobierna la verificación de arranque y el aviso de impresora
# desconectada; no impide imprimir ni bloquea nada.

# ── Idioma (I1, tanda 5; planeacion_i18n.md §5 F2) ───────────────────────
# Admin e ingeniero (decisión 1.9, tanda 6), también en ciclo (no afecta al control). R-06
# sigue vigente: el inglés no se habilita en campo hasta cerrar la voz; el
# endpoint existe, pero ninguna pantalla de operador ofrece el selector.

class _IdiomaBody(BaseModel):
    idioma: Literal["es", "en"]


@router.get("/language")
def get_language():
    return {"idioma": context.config_idioma.leer()}


@router.put("/language")
def put_language(body: _IdiomaBody,
                 sesion: Sesion = Depends(requiere_rol(ROL_ADMIN, ROL_INGENIERO))):
    """Decisión 1.9 (tanda 6): admin e ingeniero; también en ciclo."""
    entidad = "/language"
    anterior = context.config_idioma.leer()
    try:
        context.config_idioma.guardar(body.idioma)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar el idioma", entidad, sesion)
    _auditar("idioma_configurado", sesion, entidad=entidad,
             valor_anterior={"idioma": anterior}, valor_nuevo={"idioma": body.idioma})
    return {"ok": True, "idioma": body.idioma}


@router.get("/network/status")
def get_network_status(sesion: Sesion = Depends(requiere_rol(*_LEEN_CONECTIVIDAD))):
    return context.estado_red.leer()


@router.get("/db/estado")
def get_db_estado():
    """T8 (§7.1): "OK" o "DEGRADADA" (sin base de datos: alarma
    OPERANDO_SIN_BD; los ciclos van al respaldo y al ticket)."""
    sin_bd = getattr(context, "sin_base_de_datos", False) is True
    return {"estado": "DEGRADADA" if sin_bd else "OK", "sin_base_de_datos": sin_bd}


def _estado_tarjeta() -> str:
    """U4: "desconectada", "sin_tramas_validas" u "ok"; falla cerrada."""
    valor = getattr(context.control_loop, "estado_tarjeta", None)
    return valor if valor in ("desconectada", "sin_tramas_validas", "ok") else "desconectada"
