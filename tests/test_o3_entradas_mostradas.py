"""O3 (tanda 6): entradas mostradas del programa en Preciclo, Ciclo y gráfica."""
import json
from pathlib import Path

import pytest

from autoclave.ui_qml.domain import entradas_mostradas as em

SENSORS = {"temperature": {"camara": 121.04, "ref": 120.5, "drenaje": None, "camara_2": 119.0},
           "pressure": {"camara": 205.3, "chaqueta": 250.0, "empaque_1": None}}


def test_por_omision_si_lista_invalida():
    assert em.normalizar(None) == list(em.POR_OMISION)
    assert em.normalizar([]) == list(em.POR_OMISION)
    assert em.normalizar(["pres_chaqueta", "pres_chaqueta", 3, "temp_camara", "a", "b"]) == \
        ["pres_chaqueta", "temp_camara", "a"]


def test_construir_valores_en_kpa_y_celsius():
    filas = em.construir(["temp_camara", "pres_chaqueta"], SENSORS)
    assert [f["clave"] for f in filas] == ["temp_camara", "pres_chaqueta"]
    assert filas[0] == {"clave": "temp_camara", "tipo": "temp", "valor": "121.0",
                        "unidad": "°C", "enUso": True}
    assert filas[1]["valor"] == "250.0" and filas[1]["unidad"] == "kPa"


def test_construir_en_unidad_vigente():
    filas = em.construir(["temp_camara", "pres_camara"], SENSORS, t_unidad="F", p_unidad="bar")
    assert filas[0]["valor"] == "249.9" and filas[0]["unidad"] == "°F"
    assert filas[1]["valor"] == "2.05" and filas[1]["unidad"] == "bar"


def test_psi_sin_atmosferica_es_guion():
    fila = em.construir(["pres_camara"], SENSORS, p_unidad="psi")[0]
    assert fila["valor"] == "—"
    fila = em.construir(["pres_camara"], SENSORS, p_unidad="psi", p_atm=75.0)[0]
    assert fila["unidad"] == "psig" and fila["valor"] == "18.9"


@pytest.mark.parametrize("clave", ["temp_drenaje", "pres_empaque_1", "temp_drenaje_camara",
                                   "desconocida"])
def test_sin_lectura_o_desconocida_es_guion(clave):
    fila = em.construir([clave], SENSORS)[0]
    assert fila["valor"] == "—"


def test_no_en_uso_no_se_muestra():
    # O11 (tanda 11, D11-7.1): antes era una fila con "—"; ahora no aparece
    filas = em.construir(["temp_referencia", "pres_camara"], SENSORS, no_en_uso=["temp_referencia"])
    assert [f["clave"] for f in filas] == ["pres_camara"] and filas[0]["enUso"] is True


def test_sensors_mal_formado_no_rompe():
    for s in (None, [], {"temperature": "x"}, {"temperature": {"camara": float("nan")}}):
        assert em.construir(["temp_camara"], s)[0]["valor"] == "—"


def test_series_grafica():
    series = em.series_grafica(["pres_camara", "temp_referencia", "temp_drenaje"],
                               t_unidad="F", p_unidad="psi")
    assert [s["clave"] for s in series] == ["pres_camara", "temp_ref", "temp_drenaje"]
    assert [s["eje"] for s in series] == ["derecho", "izquierdo", "izquierdo"]
    assert [s["registrada"] for s in series] == [True, True, False]
    assert series[0]["unidad"] == "psia" and series[1]["unidad"] == "°F"
    assert len({s["color"] for s in series}) == 3


def test_convertir_datos_grafica():
    d = {"t_min": [0, 1], "temp_camara": [100.0, None], "temp_ref": [0.0, 10.0],
         "pres_camara": [101.325, None]}
    c = em.convertir_datos_grafica(d, "F", "mbar")
    assert c["temp_camara"] == [212.0, None] and c["temp_ref"] == [32.0, 50.0]
    assert c["pres_camara"][0] == pytest.approx(1013.25) and c["pres_camara"][1] is None
    assert em.convertir_datos_grafica(d, "C", "psi")["pres_camara"][0] == pytest.approx(14.696, abs=1e-3)
    assert c["t_min"] == [0, 1]


def test_textos_i18n_es_en():
    base = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    for lang in ("es", "en"):
        d = json.loads((base / f"{lang}.json").read_text(encoding="utf-8"))
        for clave in em._RUTA_STATUS:
            assert d["ciclo"].get("entrada_corta_" + clave), (lang, clave)
        assert d["ciclo"]["serie_sin_registro"]


# ── backend: GET /cycle expone la selección del programa ──────────────────

from tests.test_o1_gestion_programas import api, cm  # noqa: E402,F401  (fixtures)
from autoclave.core.managers import gestion_programas as gp  # noqa: E402


def test_get_cycle_expone_entradas_y_no_en_uso(api, monkeypatch):
    client, srv, ctx, cabecera = api
    monkeypatch.setattr(srv, "_ai_habilitadas",
                        lambda: ["temp_camara", "temp_referencia", "pres_camara", "pres_chaqueta"])
    ctx.cycle_manager.selected_cycle = gp.programa(ctx.cycle_manager, 2)
    d = client.get("/cycle").json()
    # O11 (tanda 11, D11-7.4): de fábrica la Referencia está "No en uso" y
    # ya no entra en la omisión
    assert d["entradas_mostradas"] == ["temp_camara", "pres_camara"]
    assert "temp_referencia" in d["entradas_no_en_uso"]
    assert client.put("/cycle/display-inputs", headers=cabecera(srv, "tecnico"),
                      json={"programa": 2, "entradas": ["pres_chaqueta", "temp_camara"]}).status_code == 200
    assert client.get("/cycle").json()["entradas_mostradas"] == ["pres_chaqueta", "temp_camara"]


def test_get_cycle_sin_io_enabled_no_rompe(api, monkeypatch):
    client, srv, ctx, _ = api

    def falla():
        raise OSError("x")
    monkeypatch.setattr(srv, "_ai_habilitadas", falla)
    ctx.cycle_manager.selected_cycle = gp.programa(ctx.cycle_manager, 2)
    # O11: la omisión del programa (de fábrica: Cámara 1 y presión)
    assert client.get("/cycle").json()["entradas_mostradas"] == ["temp_camara", "pres_camara"]


# ── puente QML ─────────────────────────────────────────────────────────────

def test_ui_bridge_publica_entradas_del_programa_y_cambian():
    import os
    import sys
    from unittest.mock import MagicMock
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_flag.return_value = False
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    ui.get_campo.side_effect = lambda k, d=None: SENSORS if k == "sensors" else d
    ui.get_cycle.return_value = {"name": "A", "entradas_mostradas": ["pres_chaqueta"],
                                 "entradas_no_en_uso": []}
    b = UiBridge(ui, door=1, iniciar=False)
    b.refrescar()
    assert [f["clave"] for f in b.entradasMostradas] == ["pres_chaqueta"]
    assert b.entradasMostradas[0]["valor"] == "250.0"
    assert [s["entrada"] for s in b.seriesGrafica] == ["pres_chaqueta"]
    ui.get_cycle.return_value = {"name": "B", "entradas_mostradas": ["temp_referencia", "temp_drenaje"],
                                 "entradas_no_en_uso": ["temp_referencia"]}
    b.refrescar()
    # O11: la Referencia No en uso no aparece; temp_drenaje sin lectura sigue con "—"
    assert [(f["clave"], f["valor"]) for f in b.entradasMostradas] == [("temp_drenaje", "—")]
    ui.get_cycle.return_value = {}          # sin /cycle todavía: la omisión de fábrica
    b.refrescar()
    assert [f["clave"] for f in b.entradasMostradas] == list(em.POR_OMISION)
