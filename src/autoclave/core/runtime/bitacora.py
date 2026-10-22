# core/runtime/bitacora.py
#
# O2e (tanda 6): presentación de la bitácora de auditoría (audit_log). Pura:
# no toca la base. Cada fila se describe por su código de evento (texto
# `bitacora.ev.<evento>` en el idioma vigente, con parámetros) y sus valores
# anterior/nuevo, convertidos a la unidad vigente cuando se sabe su magnitud
# (parámetros del equipo: unidad y clase de global_params.json).

import json

from autoclave.core.runtime import unidades as u

# Eventos con texto propio en el catálogo (bitacora.ev.<evento>). Uno que no
# esté aquí se muestra con el texto genérico y su código.
EVENTOS = (
    "login_ok", "login_fallido", "login_bloqueado", "logout", "cambio_clave",
    "usuario_creado", "usuario_desactivado", "usuario_reactivado", "clave_restablecida",
    "operador_creado", "operador_desactivado", "operador_reactivado",
    "param_sistema_cambio", "idioma_configurado", "unidades_configuradas", "impresora_configurada",
    "mantenimiento_registrado", "mantenimiento_configurado",
    "falla_reconocida", "ciclo_interrumpido", "apagar_equipo",
    "modo_prueba_entra", "modo_prueba_sale", "modo_prueba_salida_forzada", "salida_prueba",
    "puerta_orden", "puerta_orden_rechazada", "atrapamiento_orden_invertida",
    "PROGRAMA_SELECCIONADO", "PROGRAMA_SELECCION_RECHAZADA", "ROLES_SENSOR",
    "calibracion_atm_ok", "calibracion_atm_abortada", "calibracion_atm_rechazada",
    "suspension_entra", "suspension_sale",
    "correo_configurado", "correo_prueba", "impresora_prueba", "impresion_ganancias",
    "respaldo_exportado", "respaldo_rechazado", "respaldo_restaurado",
    "rechazo_401", "rechazo_403", "rechazo_409",
)


def decodificar(texto):
    if texto is None or texto == "":
        return None
    if not isinstance(texto, str):
        return texto
    try:
        return json.loads(texto)
    except (TypeError, ValueError):
        return texto


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def formatear_valor(valor, meta: dict | None, unidades: dict, p_atm=None) -> str:
    """Un valor escalar en la unidad vigente si `meta` dice su magnitud
    ({"unidad": "°C"|"kPa"|..., "clase": "absoluto"|"diferencia"})."""
    if valor is None:
        return "—"
    if not _num(valor) or not isinstance(meta, dict):
        return str(valor)
    unidad = str(meta.get("unidad") or "")
    dif = meta.get("clase") == "diferencia"
    try:
        if unidad in ("°C", "C"):
            f = u.formatear_dtemp if dif else u.formatear_temp
            return f(valor, unidades.get("temperatura") or "C")
        if unidad == "kPa":
            if dif:
                return u.formatear_dpres(valor, unidades.get("presion") or "kPa")
            return u.formatear_pres(valor, unidades.get("presion") or "kPa", p_atm)
    except Exception:
        pass
    return f"{valor:g} {unidad}".strip() if isinstance(valor, float) else f"{valor} {unidad}".strip()


def formatear(valor, metas: dict, unidades: dict, p_atm=None) -> str:
    """Texto de un valor anterior/nuevo: dict {clave: v} (parámetros del
    equipo) o escalar; los dict sin metadatos se muestran como clave=valor."""
    valor = decodificar(valor)
    if isinstance(valor, dict):
        partes = []
        for k, v in valor.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            partes.append(formatear_valor(v, metas.get(k), unidades, p_atm) if len(valor) == 1
                          else f"{k}={formatear_valor(v, metas.get(k), unidades, p_atm)}")
        return ", ".join(partes)
    if isinstance(valor, list):
        return json.dumps(valor, ensure_ascii=False)
    return "" if valor is None else formatear_valor(valor, None, unidades, p_atm)


def presentar(fila: dict, metas: dict, unidades: dict, p_atm=None) -> dict:
    """Fila de la API: los campos de audit_log más `anterior`/`nuevo` ya en la
    unidad vigente y `clave_texto` (catálogo) con sus parámetros."""
    anterior = formatear(fila.get("valor_anterior"), metas, unidades, p_atm)
    nuevo = formatear(fila.get("valor_nuevo"), metas, unidades, p_atm)
    evento = fila.get("evento") or ""
    detalle = fila.get("detalle")
    if isinstance(detalle, str):
        detalle = decodificar(detalle)
    return {
        "id": fila.get("id"), "ts": fila.get("ts"), "usuario": fila.get("usuario") or "",
        "rol": fila.get("rol") or "", "evento": evento, "entidad": fila.get("entidad") or "",
        "anterior": anterior, "nuevo": nuevo,
        "detalle": detalle if isinstance(detalle, dict) else None,
        "clave_texto": f"bitacora.ev.{evento}" if evento in EVENTOS else "bitacora.ev_generico",
    }
