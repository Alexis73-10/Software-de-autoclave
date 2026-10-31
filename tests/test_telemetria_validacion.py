# tests/test_telemetria_validacion.py
#
# Capa de validación de frontera (§6.1 principio 3 del plan de interfaz
# dual-pantalla): "Todo mensaje entrante se valida antes de entrar al
# estado de la UI. Un valor fuera de rango se descarta y se registra; no
# se pinta." Valida la FORMA del mensaje contra el contrato de §6.2 (tipos,
# claves requeridas, enum de `state`) — no inventa umbrales numéricos de
# plausibilidad física que el plan no especifica.

import pytest

from autoclave.ui_qml.domain.telemetria import validar_telemetria


def _mensaje_valido():
    # Estructura de referencia de §6.2 del plan.
    return {
        "ts": "2026-08-12T16:00:03Z",
        "tMonotonic": 923.412,
        "cycleId": 1043,
        "cycleNumber": "03",
        "state": "RUNNING",
        "stateReason": None,
        "program": {"id": 7, "name": "Botellones vacios"},
        "phasePlan": ["PURGA", "PRECALENTAMIENTO", "PREVACIO", "CALENTAMIENTO",
                      "ESTERILIZACION", "DESCOMPRESION", "SECADO"],
        "phaseStatus": {"PURGA": "COMPLETADA", "PRECALENTAMIENTO": "OMITIDA",
                         "PREVACIO": "COMPLETADA", "CALENTAMIENTO": "COMPLETADA",
                         "ESTERILIZACION": "ACTIVA", "DESCOMPRESION": "PENDIENTE",
                         "SECADO": "PENDIENTE"},
        "phase": {"code": "ESTERILIZACION", "index": 4, "elapsedS": 312},
        "isolation": {"active": True, "count": 2, "max": 5},
        "elapsedS": 923,
        "remainingS": 900,
        "metrics": {
            "t_camara": {"v": 121.3, "u": "C"},
            "t_chaqueta": {"v": 124.1, "u": "C"},
            "p_camara": {"v": 105.2, "u": "kPa", "ref": "manometrica"},
            "f0": {"v": 8.4, "u": "min"},
        },
        "doors": {
            "1": {"state": "CERRADA", "moving": False, "interlock": "BLOQUEADA"},
            "2": {"state": "CERRADA", "moving": False, "interlock": "BLOQUEADA"},
        },
        "alarms": [
            {"id": "SOBREPRESION_CAMARA", "severity": 2, "ts": "2026-08-12T16:00:00Z", "acked": False},
        ],
    }


# ── mensaje válido ───────────────────────────────────────────────────────

def test_mensaje_valido_completo_pasa():
    resultado = validar_telemetria(_mensaje_valido())
    assert resultado is not None
    assert resultado["state"] == "RUNNING"
    assert resultado["metrics"]["t_camara"]["v"] == 121.3


# ── descartes de mensaje completo (frontera de confianza) ────────────────

@pytest.mark.parametrize("basura", [None, "no es un dict", 42, [1, 2, 3]])
def test_mensaje_no_dict_se_descarta(basura):
    assert validar_telemetria(basura) is None


def test_falta_clave_requerida_se_descarta():
    mensaje = _mensaje_valido()
    del mensaje["metrics"]
    assert validar_telemetria(mensaje) is None


def test_estado_desconocido_se_descarta():
    mensaje = _mensaje_valido()
    mensaje["state"] = "ESTADO_INVENTADO"
    assert validar_telemetria(mensaje) is None


def test_metrics_no_dict_se_descarta():
    mensaje = _mensaje_valido()
    mensaje["metrics"] = "no es un dict"
    assert validar_telemetria(mensaje) is None


def test_doors_no_dict_se_descarta():
    mensaje = _mensaje_valido()
    mensaje["doors"] = ["no", "es", "dict"]
    assert validar_telemetria(mensaje) is None


def test_alarms_no_lista_se_descarta():
    mensaje = _mensaje_valido()
    mensaje["alarms"] = {"no": "es lista"}
    assert validar_telemetria(mensaje) is None


# ── métrica individual mal formada: se reemplaza por ausente, no tumba el mensaje ──

def test_metrica_con_valor_no_numerico_se_reemplaza_por_ausente():
    mensaje = _mensaje_valido()
    mensaje["metrics"]["t_camara"] = {"v": "no-numero", "u": "C"}
    resultado = validar_telemetria(mensaje)
    assert resultado is not None
    assert resultado["metrics"]["t_camara"]["v"] is None
    # El resto del mensaje sigue disponible — un sensor caído no tumba todo.
    assert resultado["metrics"]["p_camara"]["v"] == 105.2


def test_metrica_sin_clave_v_se_reemplaza_por_ausente():
    mensaje = _mensaje_valido()
    mensaje["metrics"]["t_camara"] = {"u": "C"}
    resultado = validar_telemetria(mensaje)
    assert resultado["metrics"]["t_camara"]["v"] is None


def test_metrica_con_v_null_se_preserva_como_ausente():
    # Sensor sin lectura es un estado legítimo (ver _temp_camara() -> None
    # en base_fase.py), no un error de formato — no debe tratarse distinto
    # de una métrica bien formada.
    mensaje = _mensaje_valido()
    mensaje["metrics"]["t_camara"] = {"v": None, "u": "C"}
    resultado = validar_telemetria(mensaje)
    assert resultado is not None
    assert resultado["metrics"]["t_camara"]["v"] is None


def test_metrica_no_dict_se_reemplaza_por_ausente():
    mensaje = _mensaje_valido()
    mensaje["metrics"]["t_camara"] = "totalmente mal formada"
    resultado = validar_telemetria(mensaje)
    assert resultado is not None
    assert resultado["metrics"]["t_camara"]["v"] is None
