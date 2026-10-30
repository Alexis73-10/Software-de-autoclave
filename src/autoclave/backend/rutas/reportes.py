# autoclave/backend/rutas/reportes.py
#
# Impresora, correo y reportes (/printer, /email, /report).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import logging
from datetime import date, datetime, timedelta
from typing import Literal
from fastapi import Depends, Header, Query
from pydantic import BaseModel, Field, StrictBool, StrictInt
from autoclave.backend.autenticacion import Sesion
from autoclave.services.domain.reportes import resumen_periodo
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (DISTINTO_DE_CICLO, RechazoApi, _auditar,
    _log_desarrollo, _rechazar, _token_de, context, guard_estado, requiere_rol, tokens)
from autoclave.backend.rutas._comun import (_LEEN_CONECTIVIDAD, _ciclo_json,
    _encolar_en_impresora, _inicio_del_dia, _meta_equipo, _rango_del_periodo)
from autoclave.backend.rutas.apagado import (_reinicio_lock, bloquear_para_reinicio,
    comprobar_reinicio_disponible, lanzar_reinicio)

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()


class _ImpresoraConfigBody(BaseModel):
    habilitada: StrictBool     # P2: solo el literal JSON true/false (SAF-06)
    # R11 (D11-1): la pantalla QML pide reiniciar el software para aplicarla
    reiniciar: StrictBool = False


@router.get("/printer/config")
def get_printer_config():
    return {"habilitada": context.config_impresora.habilitada()}


@router.put("/printer/config")
def put_printer_config(body: _ImpresoraConfigBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = "/printer/config"
    with _reinicio_lock:   # SAF-02: leer-guardar-bloquear sin intercalarse
        return _put_printer_config(body, sesion, entidad)


def _put_printer_config(body: _ImpresoraConfigBody, sesion: Sesion, entidad: str) -> dict:
    # R11 (D11-1.3): rechazado en CICLO, como el resto de Parámetros del equipo
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    if body.reiniciar:
        comprobar_reinicio_disponible(entidad, sesion)   # nada se guarda si no se puede
    anterior = context.config_impresora.habilitada()
    try:
        context.config_impresora.guardar(body.habilitada)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración",
                  entidad, sesion)
    estado = None
    if body.reiniciar:
        # guardar → cerrar → relanzar: si al volver a comprobar bajo el lock ya
        # no se puede (p. ej. empezó un ciclo), se devuelve la bandera (como R8)
        def deshacer():
            try:
                context.config_impresora.guardar(anterior)
            except Exception:
                # SAF-03: el cambio quedó escrito sin reinicio; que conste
                logger.exception("Reinicio rechazado y no se pudo devolver la bandera de impresora")
                _auditar("impresora_configurada", sesion, entidad=entidad,
                         valor_anterior={"habilitada": anterior},
                         valor_nuevo={"habilitada": body.habilitada},
                         detalle={"reinicio": "rechazado", "reversion_fallida": True})
        estado = bloquear_para_reinicio(entidad, sesion, deshacer=deshacer)
    _auditar("impresora_configurada", sesion, entidad=entidad,
             valor_anterior={"habilitada": anterior}, valor_nuevo={"habilitada": body.habilitada})
    if body.reiniciar:
        # la bandera rige al volver a abrir: no se aplica en pleno cierre
        lanzar_reinicio("impresora_configurada", estado, sesion, entidad,
                        detalle={"habilitada": body.habilitada})
        return {"ok": True, "habilitada": body.habilitada, "reiniciando": True}
    try:
        context.aplicar_config_impresora()   # el aviso SIS-05 sigue a la bandera
    except Exception:
        logger.exception("No se pudo aplicar la configuración de la impresora")
    return {"ok": True, "habilitada": body.habilitada, "reiniciando": False}


@router.post("/printer/test-page")
def print_test_page(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Página de prueba de la impresora térmica (409 en ciclo; 503 sin impresora)."""
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    _encolar_en_impresora([tm.pagina_prueba(_meta_equipo())])
    _log_desarrollo("impresora_prueba", sesion, entidad="/printer/test-page")   # D9-6
    return {"ok": True}
_EDITAN_CORREO = (ROL_ADMIN, ROL_INGENIERO)


class _CorreoConfigBody(BaseModel):
    envio_activo: StrictBool
    destinatarios: list[dict]


def _cargar_config_correo():
    from autoclave.ui_qml.exportacion import config_correo
    return config_correo.cargar()


def _enviar_correo(config, mensaje) -> None:
    """C2 (tanda 7): correo.enviar ya no lanza si el relay rechaza a todos
    (devuelve el resultado por destinatario); aquí eso sigue siendo un fallo."""
    import smtplib
    from autoclave.ui_qml.exportacion import correo
    r = correo.enviar(config, mensaje)
    if not isinstance(r, correo.ResultadoEnvio) or r.ninguno_aceptado:
        raise smtplib.SMTPRecipientsRefused(dict(getattr(r, "rechazados", {}) or {}))


# C2 (tanda 7): bitácora de los envíos del Historial y de Reportes. El envío lo
# hace la UI (ui_qml/bridge/acciones_ciclos.py), que no tiene la base; aquí
# solo se registra. Sin sesión obligatoria: el Menú Principal envía sin
# iniciar sesión, y el backend solo escucha en 127.0.0.1 (backend/main.py). Si
# llega un token válido, se anota el usuario. El cuerpo se valida a mano para
# que un 422 nunca repita lo recibido (podría traer algo que no debe salir).
_MAX_DIRECCIONES_REGISTRO = 20


class _CorreoEnviadoBody(BaseModel):
    model_config = {"extra": "forbid"}
    tipo: Literal["ciclos", "resumen", "consolidado"]
    destinatarios: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    manuales: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    ciclos: list[StrictInt] = Field(default_factory=list, max_length=500)
    aceptados: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    rechazados: dict[str, StrictInt] = Field(default_factory=dict,
                                              max_length=_MAX_DIRECCIONES_REGISTRO)
    resultado: Literal["enviado", "parcial", "rechazado", "error_conexion",
                       "error_autenticacion", "sin_confirmacion"]


@router.post("/email/sent")
def post_email_sent(body: dict, authorization: str | None = Header(None)):
    entidad = "/email/sent"
    try:
        datos = _CorreoEnviadoBody.model_validate(body)
    except Exception:
        raise RechazoApi(422, "validacion", "Datos inválidos")
    direcciones = (datos.destinatarios + datos.manuales + datos.aceptados
                   + list(datos.rechazados))
    if any(not isinstance(d, str) or len(d) > 254 for d in direcciones):
        raise RechazoApi(422, "validacion", "Datos inválidos")
    sesion = tokens.obtener(_token_de(authorization))
    # valor_nuevo: lo que la pantalla de Bitácora muestra ({nuevo}); el resto, en detalle
    _auditar("correo_enviado", sesion, entidad=entidad,
             valor_nuevo={"resultado": datos.resultado, "destinatarios": datos.destinatarios},
             detalle=datos.model_dump())
    return {"ok": True}


def _correo_dto() -> dict:
    from autoclave.core.runtime.config_correo_equipo import MAX_DESTINATARIOS
    equipo = context.config_correo_equipo.leer()
    try:
        base = _cargar_config_correo()
        remitente, servidor, puerto = base.remitente, base.servidor, base.puerto
        con_clave = bool(base.contrasena)
    except Exception:
        logger.exception("No se pudo leer la configuración de correo")
        remitente, servidor, puerto, con_clave = "", "", None, False
    return {"envio_activo": equipo["envio_activo"], "destinatarios": equipo["destinatarios"],
            "personalizado": equipo["personalizado"], "remitente": remitente,
            "servidor": servidor, "puerto": puerto, "contrasena_configurada": con_clave,
            "max_destinatarios": MAX_DESTINATARIOS}


@router.get("/email/config")
def get_email_config(sesion: Sesion = Depends(requiere_rol(*_LEEN_CONECTIVIDAD))):
    return _correo_dto()


@router.put("/email/config")
def put_email_config(body: _CorreoConfigBody,
                     sesion: Sesion = Depends(requiere_rol(*_EDITAN_CORREO))):
    from autoclave.core.runtime.config_correo_equipo import ErrorCorreo
    entidad = "/email/config"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    anterior = context.config_correo_equipo.leer()
    try:
        nuevo = context.config_correo_equipo.guardar(body.envio_activo, body.destinatarios)
    except ErrorCorreo as e:
        raise RechazoApi(422, e.codigo, "Destinatarios inválidos", extra={"campo": e.campo})
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración", entidad, sesion)
    _auditar("correo_configurado", sesion, entidad=entidad,
             valor_anterior={"envio_activo": anterior["envio_activo"],
                             "destinatarios": [d["correo"] for d in anterior["destinatarios"]]},
             valor_nuevo={"envio_activo": nuevo["envio_activo"],
                          "destinatarios": [d["correo"] for d in nuevo["destinatarios"]]})
    return _correo_dto()


@router.post("/email/test")
def post_email_test(sesion: Sesion = Depends(requiere_rol(*_EDITAN_CORREO))):
    """Correo de prueba a cada destinatario GUARDADO (nunca a uno escrito a mano)."""
    from autoclave import i18n
    from autoclave.ui_qml.exportacion.config_correo import correo_valido
    from email.message import EmailMessage
    entidad = "/email/test"
    config = _cargar_config_correo()
    if not config.envio_activo:
        raise RechazoApi(409, "envio_desactivado", "El envío de correo está desactivado")
    destinos = [d["correo"] for d in config.destinos if correo_valido(d.get("correo"))]
    if not destinos:
        raise RechazoApi(409, "sin_destinatarios", "No hay destinatarios guardados")
    if not config.configurado:
        raise RechazoApi(409, "correo_no_configurado", "Falta remitente, servidor o contraseña")
    meta = _meta_equipo()
    enviados, fallidos = 0, []
    for destino in destinos:
        m = EmailMessage()
        m["From"], m["To"] = config.remitente, destino
        m["Subject"] = i18n.t("conectividad.asunto_prueba", None, serie=meta["serie"] or "-")
        m.set_content(i18n.t("conectividad.cuerpo_prueba", None, serie=meta["serie"] or "-",
                             modelo=meta["modelo"] or "-",
                             fecha=datetime.now().strftime("%Y-%m-%d %H:%M")))
        try:
            _enviar_correo(config, m)
            enviados += 1
        except Exception as e:
            # el texto de la excepción no se devuelve ni se audita (podría
            # contener credenciales del servidor); solo su tipo
            logger.warning("Correo de prueba a %s fallido (%s)", destino, type(e).__name__)
            fallidos.append(destino)
    _log_desarrollo("correo_prueba", sesion, entidad=entidad,
                    enviados=enviados, fallidos=fallidos)   # D9-6
    if not enviados:
        raise RechazoApi(502, "envio_fallido", "No se pudo enviar el correo de prueba",
                         extra={"fallidos": fallidos})
    return {"ok": True, "enviados": enviados, "fallidos": fallidos}


def _resumen_periodo(periodo: str, fecha: date | None) -> dict:
    if fecha is None:
        fecha = date.fromisoformat(_inicio_del_dia()[:10])
    desde, hasta = _rango_del_periodo(periodo, fecha)
    numeros = {tipo: getattr(c, "number", None) for tipo, c in list(context.cycle_manager.cycles.items())}
    resumen = resumen_periodo.resumir(context.db.get_conteo_resultados(desde, hasta), numeros)
    perfil = context.profile
    return {
        "periodo": periodo,
        "serie":   getattr(perfil, "serial_number", "") or "",
        "modelo":  getattr(perfil, "model_id", "") or "",
        "desde":   desde[:10],
        "hasta":   (date.fromisoformat(hasta[:10]) - timedelta(days=1)).isoformat(),
        **resumen,
    }


@router.get("/report/summary")
def get_report_summary(periodo: Literal["dia", "semana", "mes"] = "dia", fecha: date | None = None):
    """Resumen de los ciclos iniciados en el periodo de calendario que contiene
    `fecha` (por defecto hoy): totales por resultado, por programa y causas de
    fallo (services/domain/reportes/resumen_periodo.py). Solo lectura."""
    return _resumen_periodo(periodo, fecha)


@router.get("/report/failures")
def get_report_failures(causa: str = Query(min_length=1),
                        periodo: Literal["dia", "semana", "mes"] = "dia",
                        fecha: date | None = None,
                        pagina: int = Query(1, ge=1),
                        por_pagina: int = Query(20, ge=1, le=100)):
    """D8-5.6: ciclos del periodo (por fecha de inicio, como /report/summary)
    que cerraron con el fallo `causa` (una de sus causas_fallo), más recientes
    primero y paginados; una página fuera de rango da la última. Cada ciclo con
    la forma de /cycle/list, para abrir su detalle como desde el Historial.
    Solo lectura."""
    if fecha is None:
        fecha = date.fromisoformat(_inicio_del_dia()[:10])
    desde, hasta = _rango_del_periodo(periodo, fecha)
    _, total = context.db.get_ciclos_con_resultado(desde, hasta, causa, 1, 0)
    paginas = max(1, -(-total // por_pagina))
    pagina = min(pagina, paginas)
    filas, total = context.db.get_ciclos_con_resultado(
        desde, hasta, causa, por_pagina, (pagina - 1) * por_pagina)
    return {
        "periodo":    periodo,
        "desde":      desde[:10],
        "hasta":      (date.fromisoformat(hasta[:10]) - timedelta(days=1)).isoformat(),
        "causa":      causa,
        "total":      total,
        "pagina":     pagina,
        "paginas":    paginas,
        "por_pagina": por_pagina,
        "ciclos":     [_ciclo_json(f) for f in filas],
    }


class _ImprimirResumenBody(BaseModel):
    periodo: Literal["dia", "semana", "mes"] = "dia"
    fecha: date | None = None


@router.post("/report/summary/print")
def print_report_summary(body: _ImprimirResumenBody):
    """Imprime el resumen del periodo en la impresora térmica (409/503:
    _encolar_en_impresora)."""
    r = _resumen_periodo(body.periodo, body.fecha)
    _encolar_en_impresora([resumen_periodo.format_ticket_resumen(
        r, r["desde"], r["hasta"], serie=r["serie"], modelo=r["modelo"])])
    return {"ok": True}
