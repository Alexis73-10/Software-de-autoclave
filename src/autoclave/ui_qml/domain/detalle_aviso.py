# ui_qml/domain/detalle_aviso.py
#
# Tanda 26 (ALD, planeacion en prompt_claude_code_tanda26.md §2): modelo de la
# ventana de detalle (VentanaDetalleAlarma) para las FILAS SINTÉTICAS: avisos
# que el operador ve como alarma pero que no son una alarma del catálogo
# (SeccionEstadoSeguro: NO ABRIR con su motivo, paro, estado seguro, módulo E/S
# sin conexión o sin datos, sin conexión con el equipo, modo prueba; y el fallo
# de arranque de Main.qml). Módulo puro (sin Qt): arma, con textos i18n es/en,
# una fila con la misma forma que `AlarmListModel.detalle` (id, level,
# priority, codigo, codigoVisible, titulos, descripciones, acciones, aparecida,
# estado) más `sintetica` True, para que la QML llame al mismo
# `abrirDesde(model)` y solo dibuje.
#
# NO ABRIR: cada motivo de core/runtime/camara_segura trae su valor medido y su
# límite (temperatura medida y `temp_max_apertura` vigente; presión medida y
# rango atm ± rango_presion_atm), en las unidades vigentes de la interfaz. Los
# límites los publica /status.camara_segura_limites (solo lectura).
#
# No hay botones que cambien estado: el detalle solo informa (ALM-01).

from datetime import datetime

from autoclave import i18n
from autoclave.core.runtime import unidades as u
from autoclave.state_machine.alarms.catalogo import codigo_visible
from autoclave.ui_qml.domain.pantalla_ciclo import _vigentes

SIN_DATO = u.SIN_DATO

# clave de fila → (id mostrado como código, nivel, prioridad, clave i18n de la
# descripción fija o "" si la arma el módulo)
_FILAS = {
    "sin_conexion": ("SIN_CONEXION", "EMERGENCIA", "alta", "sistema.seguridad_desconocida"),
    "modulo_es_desconectada": ("TARJETA_DESCONECTADA", "EMERGENCIA", "alta",
                               "sistema.modulo_es_desconectada"),
    "modulo_es_sin_datos": ("TARJETA_SIN_DATOS", "EMERGENCIA", "alta", "sistema.modulo_es_sin_datos"),
    "paro": ("PARO_EMERGENCIA", "EMERGENCIA", "alta", "sistema.paro_no_abrir"),
    "estado_seguro_pendiente": ("ESTADO_SEGURO_PENDIENTE", "EMERGENCIA", "alta",
                                "sistema.estado_seguro_pendiente"),
    "estado_seguro_en_curso": ("ESTADO_SEGURO", "EMERGENCIA", "media", "sistema.estado_seguro_en_curso"),
    "no_abrir": ("NO_ABRIR", "FALLA", "media", ""),
    "modo_prueba": ("MODO_PRUEBA", "ALERTA", "baja", "sistema.modo_prueba"),
    "arranque": ("ARRANQUE", "EMERGENCIA", "alta", ""),
}
CLAVES = tuple(_FILAS)

# Motivos de camara_segura con texto propio (aviso_detalle.no_abrir_motivos.*)
MOTIVOS_NO_ABRIR = ("temp_alta", "sobrepresion", "vacio", "sin_presion_camara", "sin_temp_camara",
                    "sin_datos_vigentes", "falta_config")


def sufijos_i18n() -> list:
    """Claves bajo `aviso_detalle.` que arma este módulo (test_i18n, familias
    dinámicas)."""
    salida = [f"{c}.{campo}" for c in CLAVES for campo in ("titulo", "accion")]
    salida += [f"no_abrir_motivos.{m}.{campo}" for m in MOTIVOS_NO_ABRIR
               for campo in ("descripcion", "accion")]
    return salida + ["no_abrir_motivos.generico.accion"]


def _numero(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v and v not in (float("inf"), float("-inf")) else None


def _temp(v) -> str:
    n = _numero(v)
    return SIN_DATO if n is None else u.formatear_temp(n, _vigentes()[0])


def _pres(v) -> str:
    n = _numero(v)
    if n is None:
        return SIN_DATO
    _t, unidad, p_atm = _vigentes()
    return u.formatear_pres(n, unidad, p_atm)


def claves_activas(seguridad: dict, conectado: bool = True) -> set:
    """Claves de fila (CLAVES) activas según el diccionario de seguridad del
    puente (UiBridge._seguridad_de). Para registrar la hora de aparición; no
    decide qué muestra cada pantalla (eso lo hace SeccionEstadoSeguro)."""
    activas = set()
    if not conectado:
        return {"sin_conexion"}
    s = seguridad or {}
    modulo = s.get("modulo_es")
    if modulo == "desconectada":
        activas.add("modulo_es_desconectada")
    elif modulo == "sin_tramas_validas":
        activas.add("modulo_es_sin_datos")
    if s.get("paro"):
        activas.add("paro")
    elif s.get("es_confirmar"):
        activas.add("estado_seguro_pendiente")
    elif s.get("es_activo"):
        activas.add("estado_seguro_en_curso")
    if s.get("no_abrir") and not s.get("paro"):
        activas.add("no_abrir")
    if s.get("modo_prueba"):
        activas.add("modo_prueba")
    return activas


def actualizar_apariciones(previas: dict, activas: set, ahora: str) -> dict:
    """{clave: ISO} con la hora en que cada fila activa apareció: conserva la
    de las que siguen activas, estampa `ahora` en las nuevas y olvida las que
    se fueron."""
    previas = previas if isinstance(previas, dict) else {}
    return {c: (previas.get(c) or ahora) for c in sorted(activas)}


def ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _t(clave: str, idioma: str, **params) -> str:
    try:
        return i18n.t(clave, idioma, **params)
    except Exception:
        return ""


def _motivo_no_abrir(ctx: dict, idioma: str) -> tuple[str, str]:
    """(causa con valor y límite, qué hacer) del motivo de NO ABRIR en `idioma`."""
    codigo = ctx.get("codigo") if isinstance(ctx.get("codigo"), str) else ""
    valores = ctx.get("valores") if isinstance(ctx.get("valores"), dict) else {}
    lim = ctx.get("limites") if isinstance(ctx.get("limites"), dict) else {}
    textos = ctx.get("textos") if isinstance(ctx.get("textos"), dict) else {}
    if codigo not in MOTIVOS_NO_ABRIR:
        # sin código (error de evaluación, motivo desconocido): el texto tal
        # cual del backend y la acción genérica
        texto = textos.get(idioma) or str(ctx.get("motivo") or "")
        return texto, _t("aviso_detalle.no_abrir_motivos.generico.accion", idioma)
    atm, rango = _numero(lim.get("presion_atmosferica")), _numero(lim.get("rango_presion_atm"))
    minimo = SIN_DATO if atm is None or rango is None else _pres(atm - rango)
    maximo = SIN_DATO if atm is None or rango is None else _pres(atm + rango)
    base = f"aviso_detalle.no_abrir_motivos.{codigo}"
    params = {
        "valor": _temp(valores.get("temp")) if codigo == "temp_alta" else _pres(valores.get("pres")),
        "limite": _temp(lim.get("temp_max_apertura")),
        "minimo": minimo, "maximo": maximo,
        "claves": str(valores.get("claves") or ""),
    }
    return _t(base + ".descripcion", idioma, **params), _t(base + ".accion", idioma, **params)


def _textos_arranque(ctx: dict, idioma: str) -> tuple[str, str]:
    clave = "arranque.sin_progreso" if ctx.get("sinProgreso") else "arranque.fallo_bloqueante"
    return (_t("arranque.fallo_titulo", idioma) + ": " + _t(clave, idioma),
            _t("aviso_detalle.arranque.accion", idioma))


def armar(clave: str, contexto: dict | None = None) -> dict:
    """Fila de detalle de la fila sintética `clave` (CLAVES), con la forma de
    AlarmListModel.detalle; {} si la clave no existe. Nunca lanza."""
    try:
        return _armar(clave, contexto if isinstance(contexto, dict) else {})
    except Exception:
        return {}


def _armar(clave: str, contexto: dict) -> dict:
    if clave not in _FILAS:
        return {}
    ident, nivel, prioridad, clave_desc = _FILAS[clave]
    titulos, descripciones, acciones = {}, {}, {}
    for idioma in i18n.IDIOMAS:
        titulo = _t(f"aviso_detalle.{clave}.titulo", idioma)
        accion = _t(f"aviso_detalle.{clave}.accion", idioma)
        if clave == "no_abrir":
            no_abrir = contexto.get("noAbrir")
            desc, accion_motivo = _motivo_no_abrir(no_abrir if isinstance(no_abrir, dict) else {}, idioma)
            accion = accion_motivo or accion
        elif clave == "arranque":
            arr = contexto.get("arranque")
            desc, accion = _textos_arranque(arr if isinstance(arr, dict) else {}, idioma)
        else:
            desc = _t(clave_desc, idioma)
            causa = contexto.get("causa")
            if clave == "estado_seguro_en_curso" and isinstance(causa, str) and causa not in ("", "paro_liberado"):
                extra = _t("sistema.estado_seguro_causa_" + causa, idioma)
                desc = f"{desc}. {extra}" if extra else desc
        titulos[idioma], descripciones[idioma], acciones[idioma] = titulo, desc, accion
    apariciones = contexto.get("apariciones") if isinstance(contexto.get("apariciones"), dict) else {}
    base = i18n.IDIOMA_BASE
    return {
        "id": ident, "level": nivel, "priority": prioridad, "source_state": "",
        "description": descripciones[base], "descripciones": descripciones,
        "codigo": ident, "codigoVisible": codigo_visible(ident), "idVisible": codigo_visible(ident),
        "titulo": titulos[base], "titulos": titulos,
        "accion": acciones[base], "acciones": acciones,
        "aparecida": str(apariciones.get(clave) or contexto.get("aparecida") or ""),
        "estado": "activa", "requiere_reconocimiento": False,
        "sintetica": True,
    }
