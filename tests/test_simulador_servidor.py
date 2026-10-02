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


def test_reposo_listo_y_tarjeta_conectada(sim):
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
    assert client.post("/doors/Puerta 1/open", json={}).status_code == 403   # en ciclo


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
