# autoclave/backend/rutas/_comun.py
#
# Funciones auxiliares que usan varias áreas de rutas.
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py.

import logging
from datetime import date, datetime
from datetime import time as dt_time   # P1 (tanda 7): `time` es el módulo (time.sleep del vigilante)
from fastapi import HTTPException
from autoclave.core.runtime import io_names
from autoclave.core.runtime import motivos
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO
from autoclave.utils import periodos

from autoclave.backend.dependencias import context

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")


def _contexto_ciclo() -> dict:
    """Ciclo y fase en curso para el `detalle` de la bitácora; vacío fuera de CICLO."""
    if context.estado.get_machine_state() != GlobalState.CICLO:
        return {}
    return {
        "ciclo": _ciclo_de_pantalla(),
        "fase": getattr(context.estado, "fase_ciclo", ""),
        "programa": getattr(getattr(context.control_loop, "cycle", None), "id", None),
    }


def _campos_motivo(motivo) -> dict:
    """Código, parámetros y textos es/en de un motivo con código, en las
    unidades vigentes; {} si no tiene código o algo falla (nunca lanza)."""
    try:
        if not motivos.codigo_de(motivo):
            return {}
        from autoclave.core.runtime import unidades as u
        try:
            unidades = context.config_unidades.leer()
            t, p = unidades["temperatura"], unidades["presion"]
            u.validar(t, p)
        except Exception:
            t, p = "C", "kPa"
        try:
            p_atm = u.p_atm_valida(_p_atm_vigente())
        except Exception:
            p_atm = None
        return motivos.campos_respuesta(motivo, t, p, p_atm)
    except Exception:
        logger.exception("No se pudieron armar los textos del motivo")
        return {}


def _nombres_ciclo(cycle) -> dict:
    """I4 (tanda 6; D-14): nombre del ciclo en es y en (catálogo para los de
    fábrica). `name`/`nombre` siguen siendo el display_name."""
    try:
        return context.cycle_manager.nombres_de(cycle)
    except Exception:
        return {"es": cycle.name, "en": cycle.name}


def _ciclo_de_pantalla() -> int | None:
    """ID en BD del ciclo que muestra la pantalla de ciclo en curso, o None
    si la máquina no está en CICLO."""
    from autoclave.state_machine.machine.enum_global import GlobalState
    if context.estado.get_machine_state() != GlobalState.CICLO:
        return None
    logger_svc = context.cycle_logger
    return logger_svc.ciclo_id_pantalla if logger_svc else None


def _inicio_del_dia() -> str:
    """Medianoche local en el formato de ciclos.fecha_fin (ISO sin zona, hora
    local del equipo). Reloj de pared: solo para presentar "ciclos hoy", no
    temporiza nada del proceso (C-01)."""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _rango_del_periodo(periodo: str, fecha: date) -> tuple[str, str]:
    """Periodo de calendario que contiene `fecha` (Historial, utils/periodos.py):
    (desde, hasta) como medianoche local en el formato de la tabla ciclos; `hasta`
    es exclusivo (medianoche del primer día del periodo siguiente)."""
    inicio, fin = periodos.rango(periodo, fecha)
    return datetime.combine(inicio, dt_time()).isoformat(), datetime.combine(fin, dt_time()).isoformat()


def _ciclo_json(fila) -> dict:
    """Un ciclo de la tabla `ciclos` para el Menú Principal. El número de programa
    no se guarda en `ciclos`: se toma del programa actual con ese id (None si ya
    no existe o no tiene número)."""
    programa = context.cycle_manager.cycles.get(fila["tipo_ciclo"])
    return {
        "id":              fila["id"],   # para pedir su curva a /cycle/history/{id}/graph
        "numero_ciclo":    fila["numero_ciclo"],
        "fecha_inicio":    fila["fecha_inicio"],
        "fecha_fin":       fila["fecha_fin"],
        "programa_id":     fila["tipo_ciclo"],
        "programa_nombre": fila["nombre_ciclo"],
        "programa_numero": getattr(programa, "number", None),
        "resultado":       fila["resultado"],
        # CycleLogger hoy no lo guarda (siempre ''): queda None hasta que exista
        # el registro de operadores (B-02 de planeacion_menu_principal.md)
        "operador":        fila["operador"] or None,
        # P4 (tanda 16, D-14.4): NO CONFORME (Referencia sin verificar), según
        # avisos_ticket; el resultado técnico sigue siendo el guardado
        **_no_conforme_json(fila),
    }


def _no_conforme_json(fila) -> dict:
    """{"no_conforme": True, "motivo_no_conforme": clave} de un ciclo guardado
    (fila de `ciclos`) que quedó NO CONFORME; {} si es conforme, para que la
    respuesta de un ciclo conforme no cambie (DECISIÓN SIN CONFIRMAR: los
    clientes leen `no_conforme is True`). Nunca lanza."""
    if not _ciclo_no_conforme(fila):
        return {}
    return {"no_conforme": True, "motivo_no_conforme": _CLAVE_NO_CONFORME}


def _p_atm_vigente():
    try:
        v = context.config_manager.get("presion_admosferica")
    except Exception:
        return None
    from autoclave.core.runtime.unidades import p_atm_valida
    return p_atm_valida(v)       # fuera de 50-110 kPa: null (la UI no muestra psi)


def _meta_equipo() -> dict:
    perfil = getattr(context, "profile", None)
    serie = getattr(perfil, "serial_number", "")
    modelo = getattr(perfil, "model_id", "")
    return {"serie": serie if isinstance(serie, str) else "",
            "modelo": modelo if isinstance(modelo, str) else ""}


# ── Conectividad (O2g, tanda 6; decisiones 1.4 y 1.9) ───────────────────────
# Red en SOLO LECTURA (cambiar Wi-Fi o IP no se habilita: DECISIÓN SIN
# CONFIRMAR). Correo de ciclos: admin, técnico e ingeniero leen; admin e
# ingeniero cambian destinatarios e interruptor (el técnico, 403) y envían el
# correo de prueba. La contraseña del relay nunca se devuelve ni se registra:
# solo `contrasena_configurada`. Cambios con ciclo en curso: 409 (R-01).

_LEEN_CONECTIVIDAD = (ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO)


def _encolar_en_impresora(tickets: list[str]) -> None:
    """Pone los tickets en la cola de la impresora térmica, la misma de la
    impresión en tiempo real. Se rechaza durante un ciclo (409): el ticket en
    vivo se imprime línea a línea por esa cola y lo nuevo quedaría intercalado
    en él. Y si Windows no reporta la impresora lista (503, detail.impresora =
    desconectada / sin_papel / no_instalada / error): Windows acepta el trabajo
    aunque esté desconectada y lo deja en su cola, así que se avisa en vez de
    encolar a ciegas."""
    from autoclave.state_machine.machine.enum_global import GlobalState
    if context.estado.get_machine_state() == GlobalState.CICLO:
        raise HTTPException(status_code=409, detail="No se puede imprimir durante un ciclo")
    estado_impresora = context.realtime_printer.estado()
    if estado_impresora != "lista":
        raise HTTPException(status_code=503, detail={"impresora": estado_impresora})
    for texto in tickets:
        context.realtime_printer.enqueue(texto)


def _carga_liquida(programa) -> bool:
    try:
        return programa.get_param("globals", "tipo_carga", default="solido") == "liquido"
    except Exception:
        return False


def _salidas_sin_confirmar_pendiente() -> bool:
    """D8-2.11: quedan reintentos del ALL_OFF de la salida del modo prueba.
    Ante cualquier duda, False (el doble de prueba sin el atributo)."""
    return getattr(context.control_loop, "salidas_sin_confirmar_pendiente", False) is True


def _i18n_t(clave: str) -> str:
    from autoclave import i18n
    return i18n.t(clave)
# U4 (tanda 2): el flag PARO_EMERGENCIA también bloquea sin datos de la
# tarjeta; el código de rechazo se conserva, el texto dice la causa real
_MOTIVO_SIN_DATOS_TARJETA = ("Sin datos válidos de la tarjeta de control: no se puede "
                             "verificar el paro de emergencia")


def _motivo_paro(texto_paro: str) -> str:
    if context.estado.get_flag("PARO_REAL"):
        return texto_paro
    return _MOTIVO_SIN_DATOS_TARJETA


def _puertas_simples() -> bool:
    from autoclave.installation.profile import puertas_simples
    return puertas_simples(getattr(context, "profile", None))


def _ai_habilitadas() -> list[str]:
    # D8-3.17: las AI que declara el perfil de instalación
    return io_names.leer_io_enabled(profile=getattr(context, "profile", None))["AI"]


def _escribir_json_programa(cycle, cambiar, con_respaldo: bool = True) -> None:
    """Lee el JSON del programa, aplica `cambiar(data)` y lo escribe de forma
    atómica (.tmp + fsync + os.replace): un corte a mitad de la escritura no
    deja el programa truncado (TMG-02 de T3). Si falla, borra el .tmp."""
    import json as _json
    import os as _os
    from pathlib import Path as _Path

    import shutil as _shutil

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    cambiar(data)
    # RB-04.2 (T10): la versión anterior queda como <nombre>.json.bak
    if con_respaldo:
        _shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            _os.fsync(f.fileno())
        _os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# ── R8 (tanda 8, D8-5.12): Opciones avanzadas = reasignación de E/S ───────────
# Sus rutas viven en server_reasignacion.py y se registran al final de
# server.py; io y respaldo usan sus funciones (ORG-12). Con import_module y no con `from
# autoclave.backend import ...`: este último devuelve el atributo del paquete,
# que tras recargar server.py (pruebas) seguiría siendo el módulo anterior.
import importlib as _importlib  # noqa: E402

_reasignacion = _importlib.import_module("autoclave.backend.server_reasignacion")


# ── P4 (tanda 16, D-14.4): NO CONFORME del ciclo en curso ──────────────

from autoclave.services.domain.logging.ticket_formatter import (  # noqa: E402
    CLAVE_NO_CONFORME as _CLAVE_NO_CONFORME, ciclo_no_conforme as _ciclo_no_conforme)


def _no_conforme_vigente(estado) -> bool:
    """El ciclo en curso (o recién terminado) está NO CONFORME: la bandera que
    publica CicloState o, por defensa en profundidad, su aviso en
    estado.avisos_ciclo (por si la bandera no se pudo publicar). Solo True
    estricto: un doble de prueba sin el atributo no cuenta."""
    if getattr(estado, "no_conforme", False) is True:
        return True
    avisos = getattr(estado, "avisos_ciclo", None)
    if not isinstance(avisos, list):
        return False
    return any(isinstance(a, dict) and a.get("clave") == _CLAVE_NO_CONFORME for a in avisos)


def _no_conforme_reconocido(estado) -> bool:
    return getattr(estado, "no_conforme_reconocido", False) is True


def _no_conforme_status(estado) -> dict:
    """Campos NO CONFORME de /status y de /cycle/current/progress."""
    nc = _no_conforme_vigente(estado)
    motivo = getattr(estado, "motivo_no_conforme", "") if nc else ""
    if nc and not (isinstance(motivo, str) and motivo):
        motivo = _CLAVE_NO_CONFORME
    return {
        "no_conforme": nc,
        "motivo_no_conforme": motivo if isinstance(motivo, str) else "",
        "no_conforme_reconocido": nc and _no_conforme_reconocido(estado),
    }
