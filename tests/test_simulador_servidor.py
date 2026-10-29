# tests/test_simulador_servidor.py
#
# Backend simulado (autoclave.simulador.servidor): mismos endpoints que usa la
# UI, con un ciclo COMPLETADO reproducido y acelerado. Reloj inyectado.

import pytest
from fastapi.testclient import TestClient

from autoclave.simulador.repeticion import Repeticion
from autoclave.simulador.servidor import crear_app

_CICLO = {
    "id": 76, "numero_ciclo": 76, "tipo_ciclo": "instrumental_121", "nombre_ciclo": "x",
    "lecturas": [
        {"t_s": 0, "codigo": "PV", "temp_camara": 30.0, "pres_camara": 80.0},
        {"t_s": 600, "codigo": "H", "temp_camara": 100.0, "pres_camara": 140.0},
        {"t_s": 720, "codigo": "S", "temp_camara": 121.0, "pres_camara": 210.0},
        {"t_s": 1620, "codigo": " ", "temp_camara": 122.0, "pres_camara": 214.0},
        {"t_s": 2220, "codigo": "E", "temp_camara": 60.0, "pres_camara": 10.0},
    ],
}


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class _Ciclo:
    id = "instrumental_121"
    name = "Instrumental 121"
    number = 3
    parameters = {"esterilizacion": {"temperatura_esterilizacion": {"value": 121.0}}}


class _GestorCiclos:
    def __init__(self):
        self.cycles = {"instrumental_121": _Ciclo()}

    def get_selected_cycle(self):
        return self.cycles["instrumental_121"]


@pytest.fixture
def sim():
    reloj = Reloj()
    app = crear_app(Repeticion(_CICLO), _GestorCiclos(), {"tiempo_standby": {"value": 5}},
                    velocidad=10.0, reloj=reloj)
    return TestClient(app), reloj


def test_reposo_listo_y_modulo_es_conectado(sim):
    client, _ = sim
    s = client.get("/status").json()
    assert s["machine_state"] == "PREPARADO"
    assert s["card_connected"] is True
    assert s["sensors"]["flags"]["LISTO_PARA_CICLO"] is True
    assert s["sensors"]["temperature"]["camara"] == 30.0
    assert s["alarms"] == []
    assert client.get("/cycle/current/progress").json() == {"activo": False}
    assert client.get("/cycle").json()["name"] == "Instrumental 121"


def test_ciclo_completo_acelerado(sim):
    client, reloj = sim
    assert client.post("/cycle/start").json()["ok"] is True
    reloj.t += 30          # 30 s reales = 300 s simulados
    s = client.get("/status").json()
    assert s["machine_state"] == "CICLO" and s["fase_ciclo"] == "PRE_VACIO"
    p = client.get("/cycle/current/progress").json()
    assert p["activo"] is True and p["fase_activa"] == "vacio"
    assert p["transcurrido_s"] == pytest.approx(300.0)
    assert p["restante_s"] == pytest.approx(2220 - 300.0)   # referencia = el ciclo reproducido
    g = client.get("/cycle/current/graph").json()
    assert len(g["lecturas"]) == 301
    assert g["lecturas"][0]["fase_ui"] == "vacio"
    assert g["lecturas"][-1]["temp_ref"] is not None
    nuevo = client.get(f"/cycle/current/graph?desde_id={g['lecturas'][-1]['id']}").json()
    assert nuevo["lecturas"] == []

    reloj.t += 300         # más allá del fin (2220 s simulados)
    s = client.get("/status").json()
    assert s["machine_state"] == "CICLO" and s["fase_ciclo"] == "COMPLETADO"
    p = client.get("/cycle/current/progress").json()
    assert p["resultado"] == "exitoso" and p["restante_s"] == 0.0
    assert p["transcurrido_s"] == pytest.approx(2220.0)

    assert client.post("/cycle/acknowledge").json()["ok"] is True
    assert client.get("/status").json()["machine_state"] == "PREPARADO"


def test_cancelar_congela_y_espera_confirmacion(sim):
    client, reloj = sim
    client.post("/cycle/start")
    reloj.t += 10
    assert client.post("/cycle/abort").json()["ok"] is True
    reloj.t += 100
    s = client.get("/status").json()
    assert s["machine_state"] == "CICLO" and s["fase_ciclo"] == "CANCELADO"
    p = client.get("/cycle/current/progress").json()
    assert p["resultado"] == "cancelado"
    assert p["transcurrido_s"] == pytest.approx(100.0)
    client.post("/cycle/acknowledge")
    assert client.get("/status").json()["machine_state"] == "PREPARADO"


def test_rechazos_como_el_backend_real(sim):
    client, _ = sim
    assert client.post("/cycle/abort").status_code == 409
    assert client.post("/cycle/acknowledge").status_code == 409
    client.post("/doors/Puerta 1/open", json={})
    assert client.get("/status").json()["sensors"]["flags"]["LISTO_PARA_CICLO"] is False
    assert client.post("/cycle/start").status_code == 409
    client.post("/doors/Puerta 1/close", json={})
    assert client.post("/cycle/start").status_code == 200
    assert client.post("/doors/Puerta 1/open", json={}).status_code == 409   # en ciclo (T-13)


def test_confirmar_durante_el_ciclo_no_lo_termina(sim):
    client, reloj = sim
    client.post("/cycle/start")
    reloj.t += 10
    client.post("/cycle/acknowledge")
    assert client.get("/status").json()["fase_ciclo"] == "PRE_VACIO"


def test_cada_ciclo_tiene_id_propio(sim):
    client, reloj = sim
    client.post("/cycle/start"); reloj.t += 300
    primero = client.get("/cycle/current/progress").json()["ciclo_db_id"]
    client.post("/cycle/acknowledge")
    client.post("/cycle/start"); reloj.t += 1
    assert client.get("/cycle/current/progress").json()["ciclo_db_id"] != primero


# ── historial: un ciclo simulado (el reproducido), fechado hoy ─────────────

@pytest.fixture
def sim_historial():
    from datetime import datetime
    app = crear_app(Repeticion(_CICLO), _GestorCiclos(), {}, reloj=Reloj(),
                    ahora=lambda: datetime(2026, 10, 19, 12, 0, 0))
    return TestClient(app)


def test_historial_lista_el_ciclo_simulado_hoy(sim_historial):
    r = sim_historial.get("/cycle/list", params={"periodo": "dia", "fecha": "2026-10-19"}).json()
    assert [c["id"] for c in r["ciclos"]] == [76]
    c = r["ciclos"][0]
    assert c["resultado"] == "COMPLETADO" and c["programa_numero"] == 3
    assert c["fecha_fin"] == "2026-10-19T11:50:00"
    assert c["fecha_inicio"] == "2026-10-19T11:13:00"           # 2220 s antes
    otro_dia = sim_historial.get("/cycle/list", params={"periodo": "dia", "fecha": "2026-10-18"}).json()
    assert otro_dia["ciclos"] == []
    assert sim_historial.get("/cycle/summary").json()["ultimo_ciclo"]["id"] == 76
    assert sim_historial.get("/report/summary", params={"periodo": "mes"}).status_code == 200


def test_historial_curva_y_ticket(sim_historial):
    g = sim_historial.get("/cycle/history/76/graph").json()
    assert g["ciclo_db_id"] == 76 and len(g["lecturas"]) == 2221
    assert g["lecturas"][0]["fase_ui"] == "vacio"
    assert g["lecturas"][-1]["temp_camara"] == pytest.approx(60.0)
    t = sim_historial.get("/cycle/history/76/ticket").json()
    assert t["ciclo"]["resultado"] == "COMPLETADO"
    assert t["lecturas"][1]["timestamp_rel"] == "00:10:00"
    assert sim_historial.get("/cycle/history/5/graph").status_code == 404
