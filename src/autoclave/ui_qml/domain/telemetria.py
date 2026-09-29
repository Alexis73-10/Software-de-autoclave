# ui_qml/domain/telemetria.py
#
# Capa de validación de frontera (§6.1 principio 3 del plan de interfaz
# dual-pantalla): "Todo mensaje entrante se valida antes de entrar al
# estado de la UI. Un valor fuera de rango se descarta y se registra; no
# se pinta." Valida la forma del mensaje de telemetría contra el contrato
# de §6.2 — no umbrales numéricos de plausibilidad física, que el plan no
# especifica.

_ESTADOS_VALIDOS = {
    "IDLE", "NOT_READY", "READY", "RUNNING", "PAUSED",
    "COMPLETED", "ABORTED", "FAULT",
}

_CLAVES_REQUERIDAS = {
    "ts", "tMonotonic", "state", "elapsedS", "remainingS",
    "metrics", "doors", "alarms", "phasePlan", "phaseStatus",
    "phase", "isolation",
}


def _metrica_valida(valor) -> bool:
    if not isinstance(valor, dict) or "v" not in valor or "u" not in valor:
        return False
    v = valor["v"]
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))


def validar_telemetria(mensaje) -> dict | None:
    """Valida un mensaje de telemetría entrante. Si la forma general del
    mensaje no es la esperada, se descarta por completo (None) — nunca
    entra a medias al estado de la UI. Dentro de `metrics`, una métrica
    individual mal formada se reemplaza por ausente (v=None) en vez de
    descartar todo el mensaje: un sensor caído no debe tumbar el resto de
    la telemetría."""
    if not isinstance(mensaje, dict):
        return None
    if not _CLAVES_REQUERIDAS.issubset(mensaje.keys()):
        return None
    if mensaje["state"] not in _ESTADOS_VALIDOS:
        return None
    if not isinstance(mensaje["metrics"], dict):
        return None
    if not isinstance(mensaje["doors"], dict):
        return None
    if not isinstance(mensaje["alarms"], list):
        return None

    metrics_validadas = {}
    for nombre, valor in mensaje["metrics"].items():
        if _metrica_valida(valor):
            metrics_validadas[nombre] = valor
        else:
            unidad = valor.get("u", "") if isinstance(valor, dict) else ""
            metrics_validadas[nombre] = {"v": None, "u": unidad}

    resultado = dict(mensaje)
    resultado["metrics"] = metrics_validadas
    return resultado
