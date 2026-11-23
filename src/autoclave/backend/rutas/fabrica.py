# autoclave/backend/rutas/fabrica.py
#
# Modo fábrica, Etapa 5: cierre de fabricación, fase 1 (DF-05; §6 de
# planeacion_modo_fabrica.md). La lógica vive en core/runtime/cierre_fabrica.py;
# aquí van las precondiciones, el hilo, el estado publicado y el reinicio.
#
#   GET  /fabrica/cierre  resumen (qué se borra y qué queda), USB, precondiciones
#                         y estado del cierre en curso (etapa, error, resultado).
#   POST /fabrica/cierre  {clave, unidad?}: reautenticación y 202; el cierre
#                         corre en su hilo, fuera del lazo de control.
#
# Las dos solo en FÁBRICA y para el ingeniero (requiere_modo_fabrica: en
# ENTREGADO, 409 solo_modo_fabrica para todos, FAB-01). Mientras el cierre
# corre, server._compuerta_de_arranque responde 409 `cierre_en_curso` a toda
# escritura salvo la sesión, la actividad de la UI, el reconocimiento de
# alarmas y el apagado (cierre_en_curso()).
#
# Orden del hilo: revalidar → paquete en la USB y verificado → temporales →
# base nueva → detener el lazo con todo apagado (bloquear_para_reinicio; si se
# rechaza, se borran los temporales y nada cambió) → marca (punto de no
# retorno) → resultado publicado unos segundos → reinicio del software. La
# fase 2 la completa backend/main.py al arrancar.

import logging
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from autoclave.backend.autenticacion import Sesion
from autoclave.backend.dependencias import (RechazoApi, _rechazar, context, reautenticar,
                                            requiere_modo_fabrica)
from autoclave.backend.rutas import apagado
from autoclave.backend.rutas._comun import _salidas_sin_confirmar_pendiente
from autoclave.core.runtime import cierre_fabrica as cf
# mismo descubrimiento de unidades que el respaldo y el catálogo de carga (un
# solo objeto: las pruebas lo parchean en los tres módulos a la vez)
from autoclave.backend.rutas.respaldo import _unidades_usb  # noqa: E402
from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.state_machine.machine.enum_global import GlobalState

logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()

ENTIDAD = "/fabrica/cierre"
# Tiempo que el resultado (ruta del ZIP y hash) queda en pantalla antes del
# reinicio, con el lazo ya detenido y todo apagado (DECISIÓN SIN CONFIRMAR)
ESPERA_ANTES_DE_REINICIAR_S = 10.0
_ESTADOS_PERMITIDOS = (GlobalState.PREPARADO, GlobalState.PREPARACION)
_USB = ("usb_ausente", "usb_no_escribible", "usb_sin_espacio")

# Rutas de escritura que siguen durante el cierre (todas las demás: 409)
_PERMITIDAS_EN_CIERRE = frozenset({"/auth/login", "/auth/logout", "/ui/activity",
                                   "/ui/standby", "/system/shutdown", ENTIDAD,
                                   "/arranque/iniciar", "/arranque/interfaz-lista"})
_PREFIJOS_PERMITIDOS_EN_CIERRE = ("/alarms/",)

_lock = threading.Lock()
_estado = {"en_curso": False, "etapa": "", "error": None, "resultado": None}


def _publicar(**cambios) -> None:
    with _lock:
        _estado.update(cambios)


def _etapa(nombre: str) -> None:
    logger.info("Cierre de fabricación: etapa %s", nombre)
    _publicar(etapa=nombre)


def cierre_en_curso() -> bool:
    with _lock:
        return _estado["en_curso"] is True


def ruta_bloqueada_por_cierre(metodo: str, ruta: str) -> bool:
    """True si el cierre está en curso y la petición es una escritura que no
    está en la lista de permitidas."""
    if (metodo or "").upper() in ("GET", "HEAD", "OPTIONS") or not cierre_en_curso():
        return False
    if ruta in _PERMITIDAS_EN_CIERRE:
        return False
    return not any(ruta.startswith(p) for p in _PREFIJOS_PERMITIDOS_EN_CIERRE)


def _estado_publicado() -> dict:
    with _lock:
        e = dict(_estado)
    etapa = e.get("etapa") or ""
    indice = cf.ETAPAS.index(etapa) + 1 if etapa in cf.ETAPAS else 0
    return {**e, "etapas": list(cf.ETAPAS),
            "progreso": round(indice / len(cf.ETAPAS), 3) if e["en_curso"] or etapa else 0.0}


# ── rutas y fuentes del equipo (las pruebas las sustituyen) ──────────────
def _rutas() -> cf.RutasCierre:
    cm = context.cycle_manager
    base = getattr(context.db, "_path", None)
    rutas = cf.rutas_del_equipo(carpeta_ciclos=Path(cm.carpeta("cycles")))
    if isinstance(base, Path):
        rutas = cf.RutasCierre(carpeta_datos=rutas.carpeta_datos,
                               carpeta_ciclos=rutas.carpeta_ciclos, ruta_base=base,
                               carpeta_logs=rutas.carpeta_logs,
                               ruta_registro_perfil=rutas.ruta_registro_perfil)
    return rutas


def _fuentes() -> pl.FuentesPaquete:
    return pl.fuentes_del_equipo(context)


def _serie() -> str:
    v = getattr(getattr(context, "profile", None), "serial_number", None)
    return v if isinstance(v, str) else ""


# ── precondiciones (§6.1) ────────────────────────────────────────────────
def _motivo(codigo: str, texto: str, **extra) -> dict:
    return {"codigo": codigo, "motivo": texto, **extra}


def _sin_base() -> bool:
    if getattr(context, "sin_base_de_datos", False) is not False or context.db is None:
        return True
    try:
        from autoclave.services.domain.logging.db_manager import marca_bd_bloqueada
        base = getattr(context.db, "_path", None)
        return isinstance(base, Path) and marca_bd_bloqueada(base).exists()
    except Exception:
        return True


def _motivos_camara() -> list[str]:
    """«Cámara sin presión» = el criterio de NO ABRIR: camara_segura.motivos
    vacío con datos vigentes. Ante un error, no segura (falla cerrada)."""
    try:
        from autoclave.core.runtime import camara_segura
        vigentes = getattr(context.control_loop, "datos_vigentes", False) is True
        motivos = camara_segura.motivos(
            context.estado, context.config_manager, context.programas_para_seguridad(),
            getattr(context, "profile", None), datos_vigentes=vigentes,
            temp_max_ciclo=context.temp_max_tras_ciclo())
        return [str(m) for m in motivos]
    except Exception:
        logger.exception("Cierre de fabricación: no se pudo evaluar la cámara; no segura")
        return ["No se pudo evaluar la cámara"]


def precondiciones_estado() -> list[dict]:
    """Motivos por los que el cierre no puede empezar ahora (vacío = puede),
    sin la USB. Falla cerrada: un error al leer cuenta como motivo."""
    from autoclave.backend import reinicio
    motivos = []
    if _sin_base():
        motivos.append(_motivo("sin_base", "Sin base de datos o base bloqueada"))
    loop = context.control_loop
    try:
        estado = context.estado.get_machine_state()
    except Exception:
        estado = None
    if estado == GlobalState.CICLO:
        motivos.append(_motivo("ciclo", "Hay un ciclo en curso"))
    elif estado == GlobalState.FALLA:
        motivos.append(_motivo("falla", "El equipo está en FALLA"))
    elif estado not in _ESTADOS_PERMITIDOS:
        motivos.append(_motivo("estado", "Solo en PREPARACION o PREPARADO"))
    try:
        paro = context.estado.get_flag("PARO_EMERGENCIA") is not False
    except Exception:
        paro = True
    if paro:
        motivos.append(_motivo("paro", "Paro de emergencia activo o sin verificar"))
    if getattr(getattr(loop, "estado_seguro", None), "requiere_confirmacion", False) is True:
        motivos.append(_motivo("confirmacion_pendiente", "Confirmación del paro pendiente"))
    if getattr(loop, "test_mode_active", False) is True or _salidas_sin_confirmar_pendiente():
        motivos.append(_motivo("modo_prueba", "Salga primero del modo prueba de salidas"))
    if getattr(loop, "apagando", False) is True or reinicio.solicitado():
        motivos.append(_motivo("apagando", "El equipo se está apagando o reiniciando"))
    camara = _motivos_camara()
    if camara:
        motivos.append(_motivo("camara_no_segura", "; ".join(camara), motivos_camara=camara))
    if not reinicio.disponible():
        motivos.append(_motivo("reinicio_no_disponible",
                               "Sin lanzador que vuelva a abrir el software"))
    return motivos


def _elegir_unidad(unidad: str | None) -> str | None:
    rutas = [u.get("ruta") for u in _unidades_usb() if isinstance(u, dict) and u.get("ruta")]
    if unidad:
        return unidad if unidad in rutas else None
    return rutas[0] if rutas else None


def _comprobar_usb(unidad: str | None, rutas: cf.RutasCierre) -> None:
    """Lanza pl.ErrorPaquete (usb_ausente, usb_no_escribible, usb_sin_espacio)."""
    if unidad is None:
        raise pl.ErrorPaquete("usb_ausente", "sin unidad USB detectada")
    pl.comprobar_usb_para_liberacion(unidad, cf.tamano_estimado(rutas))


# ── GET ──────────────────────────────────────────────────────────────────
@router.get("/fabrica/cierre")
def get_cierre(sesion: Sesion = Depends(requiere_modo_fabrica())):
    """Resumen del cierre de fabricación, USB, precondiciones y estado."""
    unidades = [u for u in _unidades_usb() if isinstance(u, dict)]
    unidad = unidades[0] if unidades else None
    try:
        estimado = cf.tamano_estimado(_rutas())
    except Exception:
        logger.exception("Cierre de fabricación: no se pudo estimar el tamaño del paquete")
        estimado = 0
    motivos = precondiciones_estado()
    if unidad is None:
        motivos.append(_motivo("usb_ausente", "Conecte una memoria USB"))
    elif isinstance(unidad.get("libre_bytes"), int) \
            and unidad["libre_bytes"] < pl.espacio_requerido(estimado):
        motivos.append(_motivo("usb_sin_espacio", "La memoria USB no tiene espacio suficiente"))
    return {
        "resumen": cf.resumen(context.db),
        "usb": {"unidades": unidades, "unidad": unidad.get("ruta") if unidad else None,
                "libre_bytes": unidad.get("libre_bytes") if unidad else None,
                "estimado_bytes": estimado, "requerido_bytes": pl.espacio_requerido(estimado)},
        "precondiciones": {"ok": not motivos, "motivos": motivos},
        "cierre": _estado_publicado(),
    }


# ── POST ─────────────────────────────────────────────────────────────────
class _CierreBody(BaseModel):
    clave: str = ""
    unidad: str | None = None


def _rechazo_estado(motivos: list[dict], sesion: Sesion):
    primero = motivos[0]
    _rechazar(409, "cierre_estado_no_permitido", primero["motivo"], ENTIDAD, sesion,
              extra={"motivo": primero["codigo"], "motivos": motivos})


@router.post("/fabrica/cierre", status_code=202)
def post_cierre(body: _CierreBody = Body(default=_CierreBody()),
                sesion: Sesion = Depends(requiere_modo_fabrica())):
    """Inicia el cierre de fabricación (contraseña del ingeniero). 202: el
    avance se consulta con GET /fabrica/cierre."""
    if cierre_en_curso():
        _rechazar(409, "cierre_en_curso", "Ya hay un cierre de fabricación en curso",
                  ENTIDAD, sesion)
    reautenticar(body.clave or "", sesion, ENTIDAD, origen="cierre_fabrica")
    motivos = precondiciones_estado()
    if motivos:
        _rechazo_estado(motivos, sesion)
    rutas = _rutas()
    unidad = _elegir_unidad(body.unidad)
    try:
        _comprobar_usb(unidad, rutas)
    except pl.ErrorPaquete as e:
        _rechazar(409, e.codigo, e.detalle or e.codigo, ENTIDAD, sesion)
    with _lock:
        if _estado["en_curso"]:
            raise RechazoApi(409, "cierre_en_curso", "Ya hay un cierre de fabricación en curso")
        _estado.update(en_curso=True, etapa="validando", error=None, resultado=None)
    try:
        threading.Thread(target=_ejecutar, args=(sesion, unidad, rutas),
                         name="CierreFabricacion", daemon=True).start()
    except Exception:
        _publicar(en_curso=False, etapa="", error={"codigo": "error_cierre", "detalle": "hilo"})
        raise
    logger.warning("Cierre de fabricación iniciado por %s en %s", sesion.usuario, unidad)
    return {"ok": True, "unidad": unidad}


def _fallar(codigo: str, detalle: str = "") -> None:
    logger.error("Cierre de fabricación abortado: %s %s", codigo, detalle)
    _publicar(en_curso=False, etapa="", error={"codigo": codigo, "detalle": detalle})


def _ejecutar(sesion: Sesion, unidad: str, rutas: cf.RutasCierre) -> None:
    """Hilo del cierre. Antes de la marca, cualquier fallo deja el equipo
    como estaba (temporales borrados, USB sin el paquete) y publica el error."""
    try:
        motivos = precondiciones_estado()
        if motivos:
            return _fallar("cierre_estado_no_permitido", motivos[0]["codigo"])
        _comprobar_usb(unidad, rutas)
        db = context.db
        resultado = cf.ejecutar_fase1(
            fuentes=_fuentes(), carpeta_usb=unidad, usuario=sesion.usuario, rol=sesion.rol,
            rutas=rutas, config_manager=context.config_manager,
            cycle_manager=context.cycle_manager, leer_base_vieja=db.datos_para_cierre_fabrica,
            serie=_serie(), progreso=_etapa)
    except pl.ErrorPaquete as e:
        return _fallar(e.codigo, e.detalle)
    except cf.ErrorCierre as e:
        return _fallar(e.codigo, e.detalle)
    except Exception as e:
        logger.exception("Cierre de fabricación: error en la fase 1")
        cf.limpiar_temporales(rutas)
        return _fallar("error_cierre", f"{type(e).__name__}: {e}")

    _etapa("marca")
    try:
        # mismo bloqueo que el reinicio del software: bajo _sm_lock revalida y
        # detiene el lazo con todo apagado; si se rechaza, nada cambió
        estado = apagado.bloquear_para_reinicio(ENTIDAD, sesion,
                                                deshacer=lambda: cf.limpiar_temporales(rutas))
    except RechazoApi as r:
        return _fallar(r.codigo, r.motivo)
    except Exception as e:
        logger.exception("Cierre de fabricación: no se pudo detener el lazo")
        cf.limpiar_temporales(rutas)
        return _fallar("error_cierre", f"{type(e).__name__}: {e}")
    try:
        cf.escribir_marca(rutas, resultado, sesion.usuario)
        _publicar(resultado={"ruta_paquete": str(resultado.ruta_paquete),
                             "nombre_paquete": resultado.nombre_paquete,
                             "hash_paquete": resultado.hash_paquete,
                             "fecha_liberacion": resultado.fecha_liberacion})
        detalle = {"paquete": resultado.nombre_paquete}
        motivo = "cierre de fabricación"
    except Exception as e:
        # sin marca no hay punto de no retorno: al arrancar se borran los
        # temporales y el equipo sigue en FÁBRICA, intacto. El lazo ya está
        # detenido: se reinicia igual
        logger.exception("Cierre de fabricación: no se pudo escribir la marca")
        cf.limpiar_temporales(rutas)
        _publicar(error={"codigo": "marca_no_escrita", "detalle": f"{type(e).__name__}: {e}"})
        detalle = {"error": "marca_no_escrita"}
        motivo = "cierre de fabricación sin completar"
    _etapa("reiniciando")
    time.sleep(ESPERA_ANTES_DE_REINICIAR_S)
    apagado.lanzar_reinicio(motivo, estado, sesion, entidad=ENTIDAD, detalle=detalle)
