# autoclave/backend/server_reasignacion.py
#
# R8 (tanda 8, D8-5.12; planeacion_opciones.md v4 R-03 y OPC-03): API de
# Opciones avanzadas = reasignación de entradas y salidas.
#
#   GET  /io/assignment          tabla: función, puerto actual, de fábrica,
#                                tipo, crítica; puertos ofrecidos y ocupados;
#                                verificación tras el último reinicio
#   POST /io/assignment          aplicar cambios {cambios, clave, confirmar, nombres}
#   POST /io/assignment/factory  restaurar la asignación de fábrica {clave, confirmar}
#
# Reglas (el backend es la autoridad, la UI solo las refleja):
#   - solo el INGENIERO (403 a técnico y admin);
#   - solo con el equipo en PREPARACION o PREPARADO, sin modo prueba, sin
#     apagado en curso y sin estado seguro actuando (409). En FALLA tampoco:
#     el protocolo de fallo puede estar venteando (DECISIÓN SIN CONFIRMAR);
#   - conflictos (dos funciones en el mismo puerto) y puertos inexistentes en
#     la tarjeta se rechazan aquí (422), no solo en la UI;
#   - doble confirmación: `confirmar` (alerta de criticidad, 428) y, para el
#     interlock de puerta, el paro de emergencia y los finales de carrera,
#     el nombre de la función escrito (428 / 422);
#   - reautenticación con la contraseña del usuario de la sesión (403; los
#     fallos suman al bloqueo del login, como en el cambio de contraseña);
#   - se guarda en la carpeta de datos (data/asignacion_io.json), se registra
#     cada cambio en audit_log (función, puerto anterior, nuevo, usuario) y se
#     reinicia el backend: la asignación nunca se aplica en caliente.
#
# Se importa al final de server.py (el nombre empieza por "server" para que
# tests/backend_doble.py lo recargue junto con server.py).

import json
import logging
import unicodedata

from fastapi import Depends
from pydantic import BaseModel, StrictBool, StrictInt

import sys

from autoclave.backend import reinicio
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime import io_names
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.ui_pyside.services.roles import ROL_INGENIERO

logger = logging.getLogger(__name__)

# El server.py que está importando este módulo (se importa al final de él).
# Por sys.modules y no con `from autoclave.backend import server`: tras recargar
# server.py (pruebas), el atributo del paquete seguiría apuntando al anterior.
srv = sys.modules["autoclave.backend.server"]

ENTIDAD = "/io/assignment"
ENTIDAD_FABRICA = "/io/assignment/factory"
_ESTADOS_PERMITIDOS = frozenset({GlobalState.PREPARACION, GlobalState.PREPARADO})


class _AplicarBody(BaseModel):
    cambios: dict[str, StrictInt] = {}
    clave: str = ""
    confirmar: StrictBool = False
    nombres: dict[str, str] = {}


class _FabricaBody(BaseModel):
    clave: str = ""
    confirmar: StrictBool = False


# ── utilidades ─────────────────────────────────────────────────────────────

def clave_nombre(funcion: str, tipo: str) -> str:
    """Clave del catálogo con el nombre visible de la función."""
    from autoclave import i18n
    funcion = aio.base(funcion)
    clave = f"io.{tipo.lower()}.{funcion}"
    return clave if i18n.existe(clave, "es") else f"reasignacion.funcion_{funcion}"


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", str(texto or ""))
                         if not unicodedata.combining(c))
    return " ".join(sin_tildes.casefold().split())


def nombre_coincide(funcion: str, tipo: str, escrito: str) -> bool:
    """El nombre escrito coincide con el visible (español o inglés), sin
    distinguir mayúsculas, tildes ni espacios repetidos."""
    from autoclave import i18n
    clave = clave_nombre(funcion, tipo)
    validos = {_normalizar(i18n.t(clave, idioma)) for idioma in ("es", "en")}
    validos.discard("")
    return bool(escrito) and _normalizar(escrito) in validos


def _ctx():
    return srv.context


def _archivo():
    arch = getattr(_ctx(), "archivo_asignacion", None)
    return arch if isinstance(arch, aio.ArchivoAsignacion) else aio.ArchivoAsignacion()


def _fabrica() -> dict:
    f = getattr(_ctx(), "asignacion_fabrica", None)
    return f if isinstance(f, dict) else aio.fabrica()


def _guardada() -> tuple[dict, str]:
    """(asignación guardada en data/, código de error o ""). Un archivo dañado
    se trata como la de fábrica a efectos de editar: solo se puede reescribir."""
    try:
        asignacion, _ = aio.vigente(_fabrica(), _archivo())
        return asignacion, ""
    except aio.ErrorAsignacion as e:
        return _fabrica(), (e.errores[0].get("codigo") if e.errores else "archivo_invalido")


def _habilitadas() -> list[tuple[str, str, str]]:
    """(clave, tipo, nombre) de las funciones a listar: las habilitadas en el
    equipo (io_enabled) que la asignación conoce; sin io_enabled, todas. Un
    nombre que está en dos tipos (agua_bomba) da dos filas."""
    todas = aio.funciones()
    io = io_names.leer_io_enabled()
    claves = [aio.clave(t, n) for t in aio.TIPOS for n in io.get(t, [])]
    habilitadas = [c for c in dict.fromkeys(claves) if c in todas]
    return [(c, todas[c], aio.base(c)) for c in (habilitadas or list(todas))]


def _motivo_bloqueo() -> tuple[str, str]:
    """("", "") si se puede reasignar ahora; si no, (código, texto). Llamar
    con _sm_lock tomado para una decisión firme (lo hace _comprobar_estado)."""
    loop = _ctx().control_loop
    estado = _ctx().estado.get_machine_state()
    if estado == GlobalState.CICLO:
        return "ciclo", "No permitido con un ciclo en curso"
    if estado not in _ESTADOS_PERMITIDOS:
        return "estado", "Solo con el equipo en preparación o preparado"
    if getattr(loop, "test_mode_active", False) is True:
        return "modo_prueba", "Salga primero del modo prueba de salidas"
    if getattr(loop, "apagando", False) is True:
        return "apagando", "El equipo se está apagando"
    if srv._estado_seguro_en_marcha():
        return "estado_seguro", "La cámara se está llevando a estado seguro"
    return "", ""


def _comprobar_estado(entidad: str, sesion, al_pasar=None) -> None:
    """Rechaza (409) fuera de PREPARACION/PREPARADO, en modo prueba, apagando
    o con estado seguro actuando. Con `al_pasar`, lo ejecuta bajo el mismo
    _sm_lock que validó (p. ej. detener el lazo antes del reinicio)."""
    with srv.guard_estado(frozenset(), entidad, sesion):
        codigo, texto = _motivo_bloqueo()
        if codigo:
            raise srv._Rechazo(409, "estado_no_permitido", texto, extra={"motivo": codigo})
        if al_pasar is not None:
            al_pasar()


def _reautenticar(clave: str, sesion, entidad: str) -> None:
    """Contraseña del usuario de la sesión. Los fallos suman al contador del
    login (como /auth/change_password): al bloquearse, 429 y token invalidado."""
    if not clave:
        srv._rechazar(403, "reautenticacion_requerida", "Escriba su contraseña para confirmar",
                      entidad, sesion)
    if not srv.intentos_login.reservar_intento(sesion.usuario):
        srv._bloquear_por_cambio_clave(sesion, entidad)
    fila = _ctx().db.get_usuario_by_username(sesion.usuario)
    if fila is None or not srv.verificar_password(clave, fila.get("hash_pw")):
        if srv.intentos_login.bloqueado(sesion.usuario):
            srv._auditar("login_fallido", sesion, entidad=entidad,
                         detalle={"origen": "reasignacion_io", "bloqueado": True})
            srv._bloquear_por_cambio_clave(sesion, entidad)
        srv._rechazar(403, "reautenticacion_fallida", "Contraseña incorrecta", entidad, sesion)
    srv.intentos_login.registrar_exito(sesion.usuario)


def _orientar(errores: list[dict], cambios: dict) -> list[dict]:
    """En un conflicto, `funcion` es la que el usuario movió y `ocupado_por`
    la que ya estaba (validar() las ordena por nombre, no por quién cambió)."""
    salida = []
    for e in errores:
        if (e.get("codigo") == "conflicto" and e.get("funcion") not in cambios
                and e.get("ocupado_por") in cambios):
            e = {**e, "funcion": e["ocupado_por"], "ocupado_por": e["funcion"]}
        salida.append(e)
    return salida


def _rechazo_validacion(errores: list[dict]):
    codigo = errores[0].get("codigo", "asignacion_invalida") if errores else "asignacion_invalida"
    limpios = [{k: v for k, v in e.items() if k in ("codigo", "funcion", "puerto", "tipo", "ocupado_por")}
               for e in errores]
    raise srv.RechazoApi(422, codigo, "Asignación de E/S inválida", extra={"errores": limpios})


def _guardar_y_reiniciar(entidad: str, sesion, evento: str, nueva: dict, cambios: dict,
                         diferencias: dict) -> dict:
    """Escribe data/asignacion_io.json, vuelve a comprobar el estado bajo el
    lock (si ya no se puede, deshace la escritura), detiene el lazo en ese
    mismo bloque, audita y pide el reinicio."""
    arch = _archivo()
    previo = arch.ruta.read_text(encoding="utf-8") if arch.ruta.exists() else None
    pendiente = sorted(diferencias)
    try:
        arch.guardar(cambios, sesion.usuario, pendiente)
    except OSError:
        srv._rechazar(503, "no_se_pudo_guardar", "No se pudo guardar la asignación", entidad, sesion)
    disponible = reinicio.disponible()

    def detener_lazo():
        # TMG-01/SAF-01 de T7, como "Apagar equipo": ningún tick posterior
        # puede pasar a CICLO ni mover salidas
        if disponible:
            _ctx().control_loop.iniciar_apagado()
    try:
        _comprobar_estado(entidad, sesion, al_pasar=detener_lazo)
    except srv.RechazoApi:
        try:
            if previo is None:
                arch.ruta.unlink(missing_ok=True)
            else:
                arch.guardar_texto(previo)
        except OSError:
            logger.exception("No se pudo deshacer la escritura de la asignación de E/S")
        raise
    for funcion, (tipo, anterior, nuevo) in sorted(diferencias.items()):
        srv._auditar(evento, sesion, entidad=funcion,
                     valor_anterior=aio.etiqueta(tipo, anterior) if anterior else None,
                     valor_nuevo=aio.etiqueta(tipo, nuevo),
                     detalle={"tipo": tipo, "critica": aio.es_critica(funcion),
                              "reforzada": aio.es_reforzada(funcion)})
    srv._auditar("reinicio_control", sesion, entidad=entidad,
                 detalle={"motivo": evento, "funciones": pendiente, "reinicio": disponible})
    if disponible:
        disponible = reinicio.solicitar(f"{evento} por {sesion.usuario}")
    return {"ok": True, "reinicio": disponible,
            "cambios": [{"funcion": f, "tipo": d[0], "anterior": d[1], "nuevo": d[2]}
                        for f, d in sorted(diferencias.items())]}


# ── endpoints ──────────────────────────────────────────────────────────────

def registrar(app) -> None:
    requiere_ingeniero = srv.requiere_rol(ROL_INGENIERO)

    @app.get("/io/assignment")
    def get_io_assignment(sesion=Depends(requiere_ingeniero)):
        memoria = aio.en_memoria()
        fabrica = _fabrica()
        guardada, error = _guardada()
        filas = []
        for clave, tipo, nombre in _habilitadas():
            filas.append({
                "funcion": clave, "tipo": tipo, "i18n": clave_nombre(nombre, tipo),
                "puerto_actual": memoria[tipo][nombre], "id_actual": aio.etiqueta(tipo, memoria[tipo][nombre]),
                "puerto_guardado": guardada[tipo].get(nombre),
                "puerto_fabrica": fabrica[tipo].get(nombre),
                "id_fabrica": aio.etiqueta(tipo, fabrica[tipo][nombre]) if fabrica[tipo].get(nombre) else "",
                "critica": aio.es_critica(clave), "reforzada": aio.es_reforzada(clave),
                "temperatura": tipo == "AI" and aio.es_temperatura(nombre),
            })
        ocupados = {t: {str(p): aio.clave(t, f) for f, p in guardada[t].items()} for t in aio.TIPOS}
        codigo, _texto = _motivo_bloqueo()
        return {
            "filas": filas,
            "puertos": {"DI": list(aio.PUERTOS_DI), "DO": list(aio.PUERTOS_DO),
                        "AI_TEMP": list(aio.PUERTOS_AI_TEMP), "AI_PRES": list(aio.PUERTOS_AI_PRES)},
            "ocupados": ocupados,
            "cambios_guardados": aio.cambios_respecto_a(fabrica, guardada),
            "reinicio_pendiente": not error and guardada != memoria,
            "error_archivo": error,
            "bloqueo": getattr(_ctx(), "motivo_asignacion", "") or "",
            "verificacion": getattr(_ctx(), "verificacion_asignacion", None)
                            or {"estado": "sin_cambios", "funciones": {}},
            "editable": codigo == "", "motivo": codigo,
            "reinicio_disponible": reinicio.disponible(),
        }

    @app.post("/io/assignment")
    def post_io_assignment(body: _AplicarBody, sesion=Depends(requiere_ingeniero)):
        _comprobar_estado(ENTIDAD, sesion)
        if not body.cambios:
            raise srv.RechazoApi(422, "sin_cambios", "No hay cambios que aplicar")
        base, _error = _guardada()
        try:
            nueva = aio.combinar(base, body.cambios)
        except aio.ErrorAsignacion as e:
            _rechazo_validacion(e.errores)
        errores = _orientar(aio.validar(nueva), body.cambios)
        if errores:
            srv._auditar("reasignacion_io_rechazada", sesion, entidad=ENTIDAD,
                         detalle={"cambios": body.cambios, "errores": errores})
            _rechazo_validacion(errores)
        diferencias = aio.diferencias(base, nueva)
        if not diferencias:
            raise srv.RechazoApi(422, "sin_cambios", "No hay cambios que aplicar")
        criticas = sorted(f for f in diferencias if aio.es_critica(f))
        reforzadas = sorted(f for f in diferencias if aio.es_reforzada(f))
        if body.confirmar is not True:
            raise srv.RechazoApi(428, "confirmacion_requerida", "Confirme la reasignación",
                                 extra={"criticas": criticas, "reforzadas": reforzadas})
        sin_nombre = [f for f in reforzadas
                      if not nombre_coincide(f, diferencias[f][0], body.nombres.get(f, ""))]
        if sin_nombre:
            escritos = [f for f in sin_nombre if body.nombres.get(f)]
            raise srv.RechazoApi(422 if escritos else 428,
                                 "nombre_no_coincide" if escritos else "confirmacion_reforzada",
                                 "Escriba el nombre de la función para confirmar",
                                 extra={"funciones": sin_nombre})
        _reautenticar(body.clave, sesion, ENTIDAD)
        cambios = aio.cambios_respecto_a(_fabrica(), nueva)
        return _guardar_y_reiniciar(ENTIDAD, sesion, "reasignacion_io", nueva, cambios, diferencias)

    @app.post("/io/assignment/factory")
    def post_io_assignment_factory(body: _FabricaBody, sesion=Depends(requiere_ingeniero)):
        _comprobar_estado(ENTIDAD_FABRICA, sesion)
        base, error = _guardada()
        fabrica = _fabrica()
        diferencias = aio.diferencias(aio.en_memoria(), fabrica)
        if not diferencias and not error and not _archivo().existe():
            raise srv.RechazoApi(422, "sin_cambios", "Ya rige la asignación de fábrica")
        if body.confirmar is not True:
            raise srv.RechazoApi(428, "confirmacion_requerida", "Confirme la restauración",
                                 extra={"funciones": sorted(diferencias)})
        _reautenticar(body.clave, sesion, ENTIDAD_FABRICA)
        return _guardar_y_reiniciar(ENTIDAD_FABRICA, sesion, "reasignacion_io_fabrica",
                                    fabrica, {}, diferencias)


# ── respaldo y restauración (O2h) ──────────────────────────────────────────

RUTA_EN_RESPALDO = "asignacion_io.json"


def contenido_respaldo() -> bytes | None:
    """El archivo de la vigente, si existe (va con la parte perfil_calibracion)."""
    arch = _archivo()
    return arch.ruta.read_bytes() if arch.ruta.exists() else None


def validar_respaldo(datos: bytes) -> dict:
    """{funcion: puerto} del respaldo, validado contra la fábrica de este
    equipo. Lanza ErrorAsignacion si no es válido."""
    try:
        obj = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise aio.ErrorAsignacion([{"codigo": "archivo_ilegible", "funcion": "", "puerto": None}])
    if not isinstance(obj, dict) or obj.get("formato") != aio.FORMATO \
            or not isinstance(obj.get("cambios"), dict):
        raise aio.ErrorAsignacion([{"codigo": "archivo_invalido", "funcion": "", "puerto": None}])
    nueva = aio.combinar(_fabrica(), obj["cambios"])
    errores = aio.validar(nueva)
    if errores:
        raise aio.ErrorAsignacion(errores)
    return {str(f): p for f, p in obj["cambios"].items()}


def restaurar_respaldo(datos: bytes, sesion, entidad: str) -> dict:
    """Restaura la asignación del respaldo SOLO con rol ingeniero (la sección
    es solo suya); valida antes de escribir y la deja para el próximo
    arranque (no reinicia: la restauración pide reiniciar). Devuelve lo
    aplicado para la respuesta y la bitácora."""
    if sesion.rol != ROL_INGENIERO:
        return {"asignacion_io": False, "asignacion_io_omitida": "rol"}
    try:
        cambios = validar_respaldo(datos)
    except aio.ErrorAsignacion as e:
        srv._auditar("respaldo_rechazado", sesion, entidad=entidad,
                     detalle={"motivo": "asignacion_io_invalida", "errores": e.errores})
        raise srv.RechazoApi(422, "asignacion_io_invalida", "Respaldo inválido")
    actual, _ = _guardada()
    nueva = aio.combinar(_fabrica(), cambios)
    diferencias = aio.diferencias(actual, nueva)
    if not diferencias:
        return {"asignacion_io": False, "asignacion_io_omitida": "sin_cambios"}
    _archivo().guardar(cambios, sesion.usuario, sorted(diferencias))
    for funcion, (tipo, anterior, nuevo) in sorted(diferencias.items()):
        srv._auditar("reasignacion_io", sesion, entidad=funcion,
                     valor_anterior=aio.etiqueta(tipo, anterior) if anterior else None,
                     valor_nuevo=aio.etiqueta(tipo, nuevo),
                     detalle={"tipo": tipo, "origen": "respaldo"})
    return {"asignacion_io": True, "asignacion_io_funciones": sorted(diferencias)}
