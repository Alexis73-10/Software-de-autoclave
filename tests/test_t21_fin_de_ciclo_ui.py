# tests/test_t21_fin_de_ciclo_ui.py
#
# Tanda 21, ola 2 (planeacion_fin_de_ciclo.md): datos de la UI del fin de
# ciclo, sin QML.
#   - normalizar_progreso: estados fallida/interrumpida (FC-06), terminacion y
#     alarmas_ciclo (FC-13) con falla cerrada ante datos mal formados; sin
#     NO CONFORME (FC-08).
#   - fin_de_ciclo.armar: fila de causa (FC-02) por tipo de terminación, filas
#     de alarmas (FC-03), modo observaciones (FC-07) y nota del modal (FC-09).
#   - Cancelar envía el token de la sesión si la hay (FC-12).
#   - UiBridge.puertaConActuador: solo True estricto (FC-11).

from unittest.mock import MagicMock

import pytest

from autoclave.ui_qml.domain import fin_de_ciclo
from autoclave.ui_qml.domain.ciclo_en_curso import normalizar_progreso

pytestmark = pytest.mark.req("T21-FC")

_BASE = {"activo": True, "ciclo_db_id": 7, "fase_ciclo": "FALLO_ESTERILIZACION",
         "resultado": "fallo", "fase_terminacion": "esterilizacion",
         "fases": [{"fase": "calentamiento", "estado": "completada", "duracion_s": 60},
                   {"fase": "esterilizacion", "estado": "fallida", "duracion_s": 30},
                   {"fase": "descompresion", "estado": "pendiente", "duracion_s": None}]}

_CIC12 = {"tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 136.4, "dt": 2.3, "temp": 134.1},
          "motivo": "x", "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07",
          "cancelado_por": None, "observaciones": []}

_ALARMAS = [
    {"codigo": "SEN-11", "nivel": "AVISO", "titulo": "Sensor de referencia sin lectura",
     "descripcion": "d", "valores": {"sensor": "Referencia 1", "fase": "Esterilización"},
     "aparecida": "2026-10-28T13:02:15", "resuelta": "2026-10-28T13:05:00"},
    {"codigo": "ZZZ-99", "nivel": "RARO", "titulo": "Algo guardado", "descripcion": "texto guardado",
     "valores": {}, "aparecida": "2026-10-28T13:19:40", "resuelta": None},
]


# ── normalizar_progreso ─────────────────────────────────────────────────────

def test_estados_nuevos_de_fase_y_fase_de_terminacion():
    r = normalizar_progreso({**_BASE, "terminacion": _CIC12, "alarmas_ciclo": []})
    assert [f["estado"] for f in r["fases"]] == ["completada", "fallida", "pendiente"]
    assert r["fase_terminacion"] == "esterilizacion"
    r = normalizar_progreso({**_BASE, "fases": [{"fase": "secado", "estado": "interrumpida"}]})
    assert r["fases"][0]["estado"] == "interrumpida"


def test_sin_no_conforme():
    r = normalizar_progreso({**_BASE, "no_conforme": True})
    assert not any(k.startswith("no_conforme") or k == "motivo_no_conforme" for k in r)


def test_terminacion_mal_formada_es_fallo_y_listas_vacias():
    for mala in (None, "x", {"tipo": "otro"}, {"tipo": 3, "observaciones": "x"}):
        r = normalizar_progreso({**_BASE, "terminacion": mala, "alarmas_ciclo": "no-lista"})
        assert r["terminacion"]["tipo"] == "fallo"
        assert r["terminacion"]["observaciones"] == []
        assert r["alarmas_ciclo"] == []


def test_exitoso_nunca_con_tipo_incoherente():
    # el resultado manda: un "exitoso" del backend con terminación de fallo no se
    # presenta como éxito, ni un fallo con terminación "exitoso"
    r = normalizar_progreso({**_BASE, "resultado": "fallo", "terminacion": {"tipo": "exitoso"}})
    assert r["terminacion"]["tipo"] == "fallo"
    r = normalizar_progreso({**_BASE, "resultado": "exitoso", "terminacion": {"tipo": "cancelado"}})
    assert r["terminacion"]["tipo"] == "fallo"


def test_sin_resultado_no_hay_terminacion():
    r = normalizar_progreso({**_BASE, "resultado": None, "terminacion": _CIC12,
                             "alarmas_ciclo": _ALARMAS, "fase_terminacion": "secado"})
    assert r["terminacion"] is None and r["alarmas_ciclo"] == [] and r["fase_terminacion"] is None


def test_alarmas_ciclo_descarta_filas_sin_codigo():
    r = normalizar_progreso({**_BASE, "terminacion": _CIC12,
                             "alarmas_ciclo": [*_ALARMAS, {"nivel": "AVISO"}, "x"]})
    assert [a["codigo"] for a in r["alarmas_ciclo"]] == ["SEN-11", "ZZZ-99"]


# ── fin_de_ciclo.armar ──────────────────────────────────────────────────────

def _armar(term, alarmas=(), idioma="es", resultado=None):
    resultado = resultado or ("exitoso" if term.get("tipo") == "exitoso"
                              else "cancelado" if term.get("tipo") == "cancelado" else "fallo")
    t = fin_de_ciclo.normalizar_terminacion(term, resultado)
    return fin_de_ciclo.armar(t, fin_de_ciclo.normalizar_alarmas(list(alarmas)), idioma)


def test_causa_de_fallo_de_fase():
    d = _armar(_CIC12, _ALARMAS)
    c = d["causa"]
    assert d["modo"] == "fallo" and d["horaFin"] == "13:21"
    assert c["titulo"] == "Fallo en esterilización"
    assert c["subtitulo"] == "Aire o gases no condensables en la cámara"
    assert "136.4" in c["descripcion"] or "136,4" in c["descripcion"]
    assert not c["descripcion"].startswith("CIC-12")
    assert "Bowie" in c["queHacer"]
    assert c["meta"] == "Fase: Esterilización · 28-oct-2026 13:21:07 · Código CIC-12"
    assert c["nivel"] == "fallo" and c["hora"] == "13:21:07"
    assert d["cantidad"] == 3


def test_causa_en_ingles():
    c = _armar(_CIC12, idioma="en")["causa"]
    assert c["titulo"] == "Failure in sterilization"
    assert "Code CIC-12" in c["meta"]


def test_causa_de_emergencia():
    c = _armar({**_CIC12, "tipo": "emergencia", "codigo": "SIS-01", "valores": {}})["causa"]
    assert c["titulo"] == "Paro de emergencia"
    assert c["subtitulo"] == "Activado en la fase Esterilización"
    assert "fugas" in c["queHacer"] and "SIS-01" in c["meta"] and c["nivel"] == "fallo"


def test_causa_de_cancelacion_con_y_sin_usuario():
    term = {"tipo": "cancelado", "fase": "calentamiento", "hora_fin": "2026-10-28T09:00:00",
            "cancelado_por": "ana"}
    c = _armar(term)["causa"]
    assert c["titulo"] == "Ciclo cancelado por el operador"
    assert c["subtitulo"] == "Cancelado por ana en la fase Calentamiento"
    assert c["nivel"] == "cancelado" and "Reprocésela" in c["queHacer"]
    assert "Código" not in c["meta"]
    c = _armar({**term, "cancelado_por": None})["causa"]
    assert c["subtitulo"] == "Cancelado en la fase Calentamiento"


def test_fallo_sin_codigo_conocido_nunca_vacio():
    for codigo in (None, "XYZ-1"):
        c = _armar({"tipo": "fallo", "codigo": codigo, "motivo": "Fallo raro de la tarjeta",
                    "fase": None, "hora_fin": ""})["causa"]
        assert c["titulo"] == "Fallo del ciclo"
        assert c["descripcion"] == "Fallo raro de la tarjeta"
    c = _armar({"tipo": "fallo"})["causa"]
    assert c["titulo"] == "Fallo del ciclo"


def test_filas_de_alarmas():
    filas = _armar(_CIC12, _ALARMAS)["alarmas"]
    assert [f["hora"] for f in filas] == ["13:02:15", "13:19:40"]
    sen11, rara = filas
    assert sen11["titulo"] == "Sensor de referencia sin lectura" and sen11["nivel"] == "baja"
    assert "Referencia 1" in sen11["descripcion"]
    assert sen11["meta"] == "13:02:15 · Código SEN-11 · Se despejó a las 13:05:00"
    assert rara["titulo"] == "Algo guardado" and rara["descripcion"] == "texto guardado"
    assert rara["nivel"] == "alta"              # nivel desconocido: lo más llamativo
    assert rara["meta"].endswith("Sigue activa") and rara["queHacer"] == ""


def test_exitoso_sin_y_con_observaciones():
    ok = {"tipo": "exitoso", "hora_fin": "2026-10-28T10:00:00", "observaciones": []}
    assert _armar(ok)["modo"] == ""
    d = _armar({**ok, "observaciones": [{"sensor": "Referencia 1", "hora": "09:40",
                                         "fase": "esterilizacion"}]}, _ALARMAS[:1])
    assert d["modo"] == "observaciones" and d["causa"] == {} and d["cantidad"] == 1
    assert d["notaObservaciones"] == ("Observación: Referencia 1 sin lectura desde las 09:40 "
                                      "(fase Esterilización).")


def test_armar_sin_terminacion():
    assert fin_de_ciclo.armar(None, [], "es")["modo"] == ""


def test_bridge_armar_fin_falla_cerrada(monkeypatch):
    from autoclave.ui_qml.bridge.progreso_ciclo import ProgresoCiclo
    p = ProgresoCiclo(MagicMock(), ejecutar=lambda t: t(), iniciar=False)
    p._al_recibir({**_BASE, "terminacion": _CIC12, "alarmas_ciclo": _ALARMAS}, None)
    assert p.faseTerminacion == "esterilizacion"
    assert p.armarFin("es")["modo"] == "fallo"
    monkeypatch.setattr(fin_de_ciclo, "armar", lambda *a: (_ for _ in ()).throw(RuntimeError()))
    d = p.armarFin("es")
    assert d["modo"] == "fallo" and d["cantidad"] == 1


# ── FC-12 y FC-11 ───────────────────────────────────────────────────────────

def test_cancelar_envia_el_token_de_la_sesion(monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.post.return_value = {"ok": True}
    monkeypatch.setattr(SessionManager, "token", classmethod(lambda cls: "tok9"))
    assert ui.abort_cycle() == {"ok": True}
    ui.backend.post.assert_called_once_with(path="/cycle/abort",
                                            headers={"Authorization": "Bearer tok9"})
    ui.backend.post.reset_mock()
    monkeypatch.setattr(SessionManager, "token", classmethod(lambda cls: None))
    ui.abort_cycle()
    ui.backend.post.assert_called_once_with(path="/cycle/abort")   # sin sesión: igual se cancela


def test_comandos_sin_reconocer_no_conforme():
    from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso
    assert not hasattr(ComandosCicloEnCurso, "reconocerNoConforme")


@pytest.mark.parametrize("mapa, esperado", [
    ({"Puerta 1": True}, True), ({"Puerta 1": False}, False), ({"Puerta 1": 1}, False),
    ({}, False), (None, False), ("x", False), ({"Puerta 2": True}, False)])
def test_puerta_con_actuador_solo_true_estricto(mapa, esperado):
    from autoclave.ui_qml.bridge.ui_bridge import puerta_con_actuador
    assert puerta_con_actuador(mapa, "Puerta 1") is esperado


# ── FC-08: la observación llega al cuerpo del correo ────────────────────────

def test_correo_lleva_la_observacion_y_no_marca_no_conforme():
    import json as _json
    from autoclave.services.domain.logging.ticket_formatter import CLAVE_OBSERVACION_REFERENCIA
    from autoclave.ui_qml.bridge.acciones_ciclos import _marcar_no_conforme
    aviso = {"clave": CLAVE_OBSERVACION_REFERENCIA, "sensor": "Referencia 1", "hora": "09:40",
             "fase": "ESTERILIZACION"}
    ciclo = {"numero_ciclo": 12, "resultado": "COMPLETADO",
             "avisos_ticket": _json.dumps({"avisos": [aviso]})}
    asunto, cuerpo = _marcar_no_conforme("Asunto", "Cuerpo", [ciclo, {"numero_ciclo": 13}])
    assert asunto == "Asunto"
    assert "000012" in cuerpo and "Referencia 1" in cuerpo and "09:40" in cuerpo
    assert "000013" not in cuerpo and "NO CONFORME" not in cuerpo
    assert _marcar_no_conforme("A", "C", [{"numero_ciclo": 13}]) == ("A", "C")
