"""Tanda 17 (s3) — SON-01: sondas "No en uso" visibles (revierte O11, D11-7.1 a 7.5).

Fuente: docs/mis_plans/decisiones_tanda_17.md §SON-01.
- Una sonda instalada con rol No en uso se lee y se publica en /status.
- Se puede elegir en Entradas mostradas (máximo 3) y se rotula «(monitoreo)»:
  /cycle entradas_no_en_uso (solo las instaladas) y la fila `monitoreo`.
- Al pasar a No en uso ya no se quita de las Entradas mostradas (sin evento).
- Se registra en la gráfica del ciclo (actual e historial), el PDF y el correo;
  no en el ticket.
- No participa en control, fallas, F0, uniformidad, entrada a esterilización,
  cámara segura, SENSOR_AUSENTE ni SEN-03/SEN-11. Una sonda no instalada sigue
  oculta.
"""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.managers import gestion_programas as gp
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.installation.equipment import EquipmentClass
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import SEN_03
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.ui_qml.domain import entradas_mostradas as em
from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica
from tests.helpers.backend_doble import cabecera, parchear_en_backend
from tests.test_o1_gestion_programas import api, cm  # noqa: F401  (fixtures)
from tests.test_t3_endpoints_sensores import _CON_REF, _FABRICA, _put, entorno  # noqa: F401

pytestmark = pytest.mark.req("SON-01")

_HAB = ["temp_camara", "temp_2_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]
# perfil de laboratorio con las tres sondas del ciclo instaladas
_LAB = SimpleNamespace(equipment_class=EquipmentClass.PISO_LAB,
                       temperature_probes={"temp_camara": True, "temp_2_camara": True,
                                           "temp_ref": True})
# perfil sin la sonda de Cámara 2
_LAB_SIN_C2 = SimpleNamespace(equipment_class=EquipmentClass.PISO_LAB,
                              temperature_probes={"temp_camara": True, "temp_2_camara": False,
                                                  "temp_ref": True})


def _prog(sensores=None, entradas=None):
    return SimpleNamespace(sensores=sensores, entradas_mostradas=entradas)


# ── /status: la sonda No en uso se publica ────────────────────────────────

@pytest.fixture
def status_client():
    ctx = MagicMock()
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(
                ("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.estado.Alarmas_activas = []
    return TestClient(srv.app), ctx


def test_status_publica_las_tres_sondas_sin_mirar_el_rol(status_client):
    client, ctx = status_client
    ctx.estado.sensores_temp = {"temp_camara": 121.0, "temp_2_camara": 119.5, "temp_ref": 120.2}
    # programa con Cámara 2 y Referencia No en uso
    ctx.cycle_manager.get_selected_cycle.return_value = _prog(_FABRICA)
    temp = client.get("/status").json()["sensors"]["temperature"]
    assert temp["camara"] == 121.0 and temp["camara_2"] == 119.5 and temp["ref"] == 120.2


def test_estado_lee_las_sondas_no_en_uso():
    estado = EstadoAutoclave()
    lista = [0.0] * 8
    for nombre, i in EstadoAutoclave.map_temp.items():
        lista[i] = 100.0 + i
    estado.update({"temperature": lista})
    for s in ("temp_camara", "temp_2_camara", "temp_ref"):
        assert estado.sensores_temp[s] == 100.0 + EstadoAutoclave.map_temp[s]


# ── selección y rótulo ────────────────────────────────────────────────────

def test_no_en_uso_solo_las_instaladas():
    habilitadas = ["temp_camara", "temp_referencia", "pres_camara"]    # sin Cámara 2
    assert gp.entradas_no_en_uso(_prog(_FABRICA), habilitadas) == ["temp_referencia"]
    assert gp.entradas_no_en_uso(_prog(_FABRICA)) == ["temp_2_camara", "temp_referencia"]


def test_selector_ofrece_las_no_en_uso_pero_no_las_no_instaladas(api, monkeypatch):
    client, srv, ctx, _ = api
    habilitadas = ["temp_camara", "temp_referencia", "pres_camara"]    # Cámara 2 no instalada
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(habilitadas))
    d = client.get("/cycle/display-inputs?programa=2").json()
    assert d["disponibles"] == habilitadas
    assert d["no_en_uso"] == ["temp_referencia"]
    assert "temp_2_camara" not in d["disponibles"]


def test_put_acepta_no_en_uso_y_sigue_el_maximo_de_3(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    h = cabecera(srv, "tecnico")
    r = client.put("/cycle/display-inputs", headers=h,
                   json={"programa": 2, "entradas": ["temp_camara", "temp_2_camara",
                                                     "temp_referencia"]})
    assert r.status_code == 200, r.text
    r = client.put("/cycle/display-inputs", headers=h,
                   json={"programa": 2, "entradas": ["temp_camara", "temp_2_camara",
                                                     "temp_referencia", "pres_camara"]})
    assert r.status_code == 422
    # una no instalada sigue rechazada
    r = client.put("/cycle/display-inputs", headers=h,
                   json={"programa": 2, "entradas": ["temp_drenaje"]})
    assert r.status_code == 422


def test_get_cycle_rotula_y_no_filtra(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas",
                        lambda: ["temp_camara", "temp_referencia", "pres_camara"])
    c = gp.programa(ctx.cycle_manager, 2)
    c.entradas_mostradas = ["temp_referencia", "temp_2_camara", "pres_camara"]
    ctx.cycle_manager.selected_cycle = c
    d = client.get("/cycle").json()
    # Cámara 2 no instalada: oculta; la Referencia No en uso se muestra y se rotula
    assert d["entradas_mostradas"] == ["temp_referencia", "pres_camara"]
    assert d["entradas_no_en_uso"] == ["temp_referencia"]


def test_cambio_de_rol_no_toca_entradas_ni_audita(entorno):
    client, ctx, srv, prog, archivo = entorno
    assert _put(client, srv, _CON_REF).status_code == 200
    prog.entradas_mostradas = ["temp_referencia", "temp_camara"]
    assert _put(client, srv, _FABRICA, anterior=_CON_REF).status_code == 200
    assert prog.entradas_mostradas == ["temp_referencia", "temp_camara"]
    assert "entradas_mostradas" not in json.loads(archivo.read_text(encoding="utf-8"))
    assert ctx.db.get_auditoria(evento="entradas_mostradas") == []


def test_filas_y_series_con_monitoreo_y_guion_sin_lectura():
    sensors = {"temperature": {"camara": 121.0, "ref": None}, "pressure": {"camara": 205.0}}
    filas = em.construir(["temp_camara", "temp_referencia", "pres_camara"], sensors,
                         no_en_uso=["temp_referencia"])
    ref = filas[1]
    assert ref["clave"] == "temp_referencia" and ref["monitoreo"] is True and ref["valor"] == "—"
    series = em.series_grafica(["temp_2_camara", "pres_camara"], no_en_uso=["temp_2_camara"])
    assert series[0]["clave"] == "temp_2_camara" and series[0]["registrada"] is True
    assert series[0]["monitoreo"] is True and series[1]["monitoreo"] is False
    datos = em.convertir_datos_grafica({"temp_2_camara": [100.0, None]}, "F", "kPa")
    assert datos["temp_2_camara"] == [212.0, None]


# ── registro: gráfica del ciclo (actual e historial), PDF ──────────────────

@pytest.fixture
def grafica(tmp_path):
    db = DbManager(tmp_path / "g.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.cycle_logger.transcurrido_s.return_value = None
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(
                ("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo="x", nombre="x",
                         temp_ester=134, tiempo_ester=7, modelo="", serie="", version_sw="")
    db.insertar_lectura_grafica(cid, 0.0, "CALENTAMIENTO", 120.0, 119.0, 200.0, 118.5)
    ctx.cycle_logger.ciclo_id_pantalla = cid
    yield TestClient(srv.app), ctx, cid
    db.close()


@pytest.mark.parametrize("ruta", ["/cycle/current/graph", "/cycle/history/{cid}/graph"])
def test_grafica_incluye_la_sonda_de_camara_2_instalada(grafica, ruta):
    client, ctx, cid = grafica
    ctx.profile = _LAB
    lectura = client.get(ruta.format(cid=cid)).json()["lecturas"][0]
    assert lectura["temp_camara"] == 120.0 and lectura["temp_ref"] == 119.0
    assert lectura["temp_2_camara"] == 118.5


@pytest.mark.parametrize("ruta", ["/cycle/current/graph", "/cycle/history/{cid}/graph"])
def test_grafica_oculta_una_sonda_no_instalada(grafica, ruta):
    client, ctx, cid = grafica
    ctx.profile = _LAB_SIN_C2
    lectura = client.get(ruta.format(cid=cid)).json()["lecturas"][0]
    assert lectura["temp_2_camara"] is None and lectura["temp_ref"] == 119.0


def test_acumulador_guarda_la_serie_de_camara_2():
    acc = AcumuladorGrafica()
    acc.incorporar({"ciclo_db_id": 1, "lecturas": [
        {"id": 1, "t_s": 0.0, "fase_ui": None, "temp_camara": 120.0, "temp_ref": None,
         "pres_camara": 200.0, "temp_2_camara": 118.0}]})
    assert acc.datos()["temp_2_camara"] == [118.0]


def test_pdf_dibuja_camara_2_solo_con_lecturas():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.exportacion import pdf_ciclo
    con = {"t_min": [0, 1], "temp_camara": [1, 2], "temp_ref": [1, 2], "pres_camara": [1, 2],
           "temp_2_camara": [None, 118.0]}
    sin = dict(con, temp_2_camara=[None, None])
    assert "temp_2_camara" in [s[0] for s in pdf_ciclo._series_visibles(con)]
    assert "temp_2_camara" not in [s[0] for s in pdf_ciclo._series_visibles(sin)]
    assert [s[0] for s in pdf_ciclo._series_visibles({})] == ["temp_camara", "temp_ref",
                                                              "pres_camara"]


def test_ticket_no_cambia():
    """El ticket sigue con el Principal: SON-01 no toca ticket_formatter."""
    raiz = Path(__file__).resolve().parents[1]
    texto = (raiz / "src/autoclave/services/domain/logging/ticket_formatter.py").read_text(
        encoding="utf-8")
    assert "temp_2_camara" not in texto


# ── no participa en control, fallas ni alarmas ────────────────────────────

def test_no_en_uso_fuera_de_los_sensores_en_uso_y_de_la_seguridad():
    p = SimpleNamespace(sensores=dict(_FABRICA))
    assert sc.sensores_en_uso(p) == ["temp_camara"]
    estado = SimpleNamespace(sensores_temp={"temp_camara": 30.0, "temp_2_camara": 200.0,
                                            "temp_ref": None})
    # la sonda No en uso caliente no cambia la temperatura de seguridad
    assert sc.temp_seguridad(estado, [p], _LAB) == 30.0
    # sin lectura de las No en uso, el programa puede iniciar
    assert sc.verificar_inicio(p, _LAB, estado) is None


def test_sin_lectura_no_en_uso_no_da_sen03():
    alarmas = AlarmManager()
    p = SimpleNamespace(sensores=dict(_FABRICA))
    estado = SimpleNamespace(sensores_temp={"temp_camara": 30.0, "temp_2_camara": None,
                                            "temp_ref": None})
    sc.vigilar_en_uso_fuera_de_ciclo(alarmas, _LAB, estado, [p])
    assert not [i for i in alarmas.activas() if i.codigo == SEN_03]
