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
# D9-6 (tanda 9): la bitácora guarda solo eventos de seguridad, cambios de
# configuración y sesión. Retirados (quedan solo en el log de desarrollo):
# rechazo_401/403/409 (todo `_rechazar`), suspension_entra/sale, puerta_orden,
# puerta_orden_rechazada, PROGRAMA_SELECCIONADO, PROGRAMA_SELECCION_RECHAZADA,
# correo_prueba, impresora_prueba e impresion_ganancias.
EVENTOS = (
    "login_ok", "login_fallido", "login_bloqueado", "logout", "cambio_clave",
    "usuario_creado", "usuario_desactivado", "usuario_reactivado", "clave_restablecida",
    "operador_creado", "operador_desactivado", "operador_reactivado",
    "param_sistema_cambio", "idioma_configurado", "unidades_configuradas", "impresora_configurada",
    "mantenimiento_registrado", "mantenimiento_configurado",
    "falla_reconocida", "ciclo_interrumpido", "apagar_equipo",
    "modo_prueba_entra", "modo_prueba_sale", "modo_prueba_salida_forzada", "salida_prueba",
    "atrapamiento_orden_invertida", "ROLES_SENSOR",
    # O11 (tanda 11, D11-7.3): entradas quitadas al pasar un sensor a "No en uso"
    "entradas_mostradas",
    "calibracion_atm_ok", "calibracion_atm_abortada", "calibracion_atm_rechazada",
    "correo_configurado", "correo_enviado",
    "respaldo_exportado", "respaldo_rechazado", "respaldo_restaurado",
    "aire_atmosferico_cortado_prueba", "apagado_windows_rechazado",
    "param_ciclo_cambio",
    # P4 (tanda 16, D-14.4): reconocimiento de la carga NO CONFORME no liberable
    "ciclo_no_conforme_reconocido",
    # X9 (tanda 9, D9-13.3 TMG-01): el cambio registrado como "en_curso" no
    # llegó al ciclo en curso porque su fase inició antes de aplicarlo
    "param_ciclo_no_aplicado_en_curso",
    # R8 (tanda 8, D8-5.12): reasignación de E/S
    "reasignacion_io", "reasignacion_io_fabrica", "reasignacion_io_rechazada",
    "reasignacion_io_verificada", "reinicio_control",
    # R11 (tanda 11, D11-1): reinicio del software (p. ej. al cambiar la impresora)
    "software_reiniciado",
    # C9 (tanda 9, D9-10): Manejo de ciclos
    "programa_creado", "programa_duplicado", "programa_habilitado", "programa_borrado",
    # U11 (tanda 11, D11-6): cuentas del sistema Admin e Ingeniero
    "usuario_renombrado", "cuenta_sistema_rechazada",
    # LIC-02 (licencia L0): contraseña de Admin/Ingeniero fijada en el asistente
    "contrasena_fijada_instalacion",
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


def _clave_texto(evento: str, detalle, nuevo=None) -> str:
    # C9 (tanda 9): deshabilitar un programa tiene su propio texto (el valor
    # booleano no se muestra crudo)
    if evento == "programa_habilitado" and isinstance(nuevo, dict) and nuevo.get("habilitado") is False:
        return "bitacora.ev.programa_deshabilitado"
    # D8-5.7 (tanda 8): el cambio automático del modo de descompresión al
    # cambiar el tipo de carga se distingue del cambio hecho por el usuario
    if (evento == "param_ciclo_cambio" and isinstance(detalle, dict) and detalle.get("automatico") is True
            and str(detalle.get("causa") or "").endswith("/globals/tipo_carga")):
        return "bitacora.ev.param_ciclo_automatico"
    return f"bitacora.ev.{evento}" if evento in EVENTOS else "bitacora.ev_generico"


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
        "clave_texto": _clave_texto(evento, detalle, decodificar(fila.get("valor_nuevo"))),
    }
