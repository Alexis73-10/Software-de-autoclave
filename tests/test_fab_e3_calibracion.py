# tests/test_fab_e3_calibracion.py
#
# Modo fábrica, Etapa 3 (D-08, FAB-08, DF-07, R-05, P-03): calibración de
# fábrica del equipo (`calibracion_fabrica_equipo.yaml`) por función de
# sensor, y «defecto» de POST /calibration/{tipo}/{sensor}/restaurar.
# Carpeta de datos en tmp_path; nunca toca data/ ni la calibración del repo.

import math
import textwrap

import pytest
import yaml
from unittest.mock import MagicMock

from autoclave.config import load_config
from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.core.runtime.status import EstadoAutoclave
from tests.helpers.backend_doble import cabecera, cargar_servidor, fijar_en_backend

_CALIB = textwrap.dedent("""
    calibration:
      user:
        temperature:
          - gain: 1.01
            offset: -0.4
          - gain: 1.0
            offset: 0.0
        pressure:
          - gain: 1.02
            offset: -1.5
          - gain: 0.98
            offset: 2.0
""")

_MAPAS = {"temperature": {"temp_camara": 0, "temp_2_camara": 1},
          "pressure": {"pres_camara": 0, "pres_chaqueta": 1}}


@pytest.fixture
def datos(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(fe, "carpeta_datos", lambda: d)
    return d


@pytest.fixture
def origen(tmp_path):
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text(_CALIB, encoding="utf-8")
    return ruta


def _guardar(datos, contenido) -> None:
    (datos / fe.NOMBRE_CALIBRACION).write_text(yaml.safe_dump(contenido), encoding="utf-8")


# ── funciones puras ─────────────────────────────────────────────────────

def test_escribir_por_funcion_con_canal(datos, origen):
    salida = fe.escribir_calibracion_fabrica_equipo(origen=origen, mapas=_MAPAS)
    leido = yaml.safe_load(fe.ruta_calibracion().read_text(encoding="utf-8"))
    assert leido == salida
    assert leido["formato"] == fe.FORMATO_CALIBRACION
    assert leido["pressure"]["pres_camara"] == {"canal": 0, "puerto": 1, "formato": 2,
                                                "gain": 1.02, "offset": -1.5, "poly": None}
    assert leido["temperature"]["temp_camara"]["gain"] == 1.01
    assert [p.name for p in datos.iterdir()] == [fe.NOMBRE_CALIBRACION]   # sin temporales


def test_escribir_con_la_asignacion_vigente(datos, origen):
    salida = fe.escribir_calibracion_fabrica_equipo(origen=origen)
    # canales fuera del archivo de prueba (2 entradas) no se guardan
    assert set(salida["pressure"]) <= set(EstadoAutoclave.map_pres)
    assert salida["pressure"]["pres_camara"]["canal"] == EstadoAutoclave.map_pres["pres_camara"]


def test_leer_entrada_valida(datos, origen):
    fe.escribir_calibracion_fabrica_equipo(origen=origen, mapas=_MAPAS)
    assert fe.entrada_calibracion_equipo("pressure", "pres_chaqueta", 1) == \
        {"gain": 0.98, "offset": 2.0, "poly": None}


def test_sin_archivo_o_sin_sensor_none(datos, origen):
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0) is None
    fe.escribir_calibracion_fabrica_equipo(origen=origen, mapas=_MAPAS)
    assert fe.entrada_calibracion_equipo("pressure", "pres_empaque_1", 2) is None
    assert fe.entrada_calibracion_equipo("otro", "pres_camara", 0) is None


def test_canal_cambiado_por_reasignacion_none(datos, origen):
    fe.escribir_calibracion_fabrica_equipo(origen=origen, mapas=_MAPAS)
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 5) is None


@pytest.mark.parametrize("entrada", [
    {"canal": 0, "gain": "x", "offset": 0.0},
    {"canal": 0, "gain": math.inf, "offset": 0.0},
    {"canal": 0, "gain": 1.0},
    {"canal": 0, "gain": 1.0, "offset": 0.0, "poly": "abc"},
    {"canal": 0, "gain": 1.0, "offset": 0.0, "poly": []},
    {"canal": 0, "gain": 1.6, "offset": 0.0},          # no plausible (rechazo)
    {"canal": True, "gain": 1.0, "offset": 0.0},
])
def test_entrada_invalida_none(datos, entrada):
    _guardar(datos, {"formato": 1, "pressure": {"pres_camara": entrada}})
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0) is None


@pytest.mark.parametrize("texto", ["formato: 99\n", "[1, 2]\n", ": : no yaml"])
def test_archivo_ilegible_o_de_otro_formato_none(datos, texto):
    (datos / fe.NOMBRE_CALIBRACION).write_text(texto, encoding="utf-8")
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0) is None


def test_poly_se_conserva(datos):
    _guardar(datos, {"formato": 1, "pressure": {"pres_camara": {
        "canal": 0, "gain": 1.0, "offset": 0.0, "poly": [0.0, 1.01, 0.0001]}}})
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0)["poly"] == [0.0, 1.01, 0.0001]


# ── ruta /restaurar con destino «defecto» ───────────────────────────────

@pytest.fixture
def cliente(tmp_path, datos):
    yaml_path = tmp_path / "activa.yaml"
    yaml_path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
    """), encoding="utf-8")
    ctx = MagicMock()
    ctx.db.get_auditoria.return_value = []
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    fijar_en_backend("CALIBRATION_PATH", yaml_path)
    from fastapi.testclient import TestClient
    return TestClient(srv.app, headers=cabecera(srv, "ingeniero")), ctx, yaml_path


def _restaurar(client):
    return client.post("/calibration/pressure/pres_camara/restaurar", json={"destino": "defecto"})


def _user_pres(yaml_path, i=0):
    return load_config(yaml_path).calibration.user.pressure[i]


def test_p03_defecto_restaura_la_del_equipo(cliente, datos, origen):
    client, ctx, yaml_path = cliente
    canal = EstadoAutoclave.map_pres["pres_camara"]
    fe.escribir_calibracion_fabrica_equipo(origen=origen, mapas={"pressure": {"pres_camara": canal}})
    r = _restaurar(client)
    assert r.status_code == 200, r.text
    assert (r.json()["gain"], r.json()["offset"], r.json()["origen"]) == (1.02, -1.5, "fabrica_equipo")
    c = _user_pres(yaml_path, canal)
    assert (c.gain, c.offset) == (1.02, -1.5)
    kw = ctx.db.registrar_auditoria.call_args.kwargs
    assert kw["valor_nuevo"] == {"gain": 1.02, "offset": -1.5}
    assert kw["detalle"]["origen"] == "fabrica_equipo"
    assert kw["detalle"]["accion"] == "restaurar_defecto"


def test_sin_archivo_neutro(cliente):
    client, ctx, yaml_path = cliente
    r = _restaurar(client)
    assert r.status_code == 200
    assert (r.json()["gain"], r.json()["offset"], r.json()["origen"]) == (1.0, 0.0, "neutro")
    assert ctx.db.registrar_auditoria.call_args.kwargs["detalle"]["origen"] == "neutro"
    c = _user_pres(yaml_path)
    assert (c.gain, c.offset) == (1.0, 0.0)


def test_canal_cambiado_neutro(cliente, datos, origen):
    client, ctx, _ = cliente
    canal = EstadoAutoclave.map_pres["pres_camara"]
    fe.escribir_calibracion_fabrica_equipo(origen=origen,
                                           mapas={"pressure": {"pres_camara": canal + 1}})
    r = _restaurar(client)
    assert r.status_code == 200
    assert r.json()["origen"] == "neutro" and r.json()["gain"] == 1.0


def test_defecto_con_poly(cliente, datos):
    client, ctx, yaml_path = cliente
    canal = EstadoAutoclave.map_pres["pres_camara"]
    _guardar(datos, {"formato": 1, "pressure": {"pres_camara": {
        "canal": canal, "gain": 1.0, "offset": 0.0, "poly": [1.01, 0.0]}}})
    # SAF-08: un polinomio plausible (1,01·x); [0, 1.01] era una constante
    r = _restaurar(client)
    assert r.status_code == 200 and r.json()["origen"] == "fabrica_equipo"
    assert _user_pres(yaml_path, canal).poly == [1.01, 0.0]
    assert ctx.db.registrar_auditoria.call_args.kwargs["valor_nuevo"]["poly"] == [1.01, 0.0]


def test_auditoria_fallida_revierte_tambien_con_la_del_equipo(cliente, datos, origen):
    client, ctx, yaml_path = cliente
    fe.escribir_calibracion_fabrica_equipo(
        origen=origen, mapas={"pressure": {"pres_camara": EstadoAutoclave.map_pres["pres_camara"]}})
    previo = yaml_path.read_text(encoding="utf-8")
    ctx.db.registrar_auditoria.side_effect = RuntimeError("bd")
    assert _restaurar(client).status_code == 503
    assert yaml_path.read_text(encoding="utf-8") == previo


def test_ultimo_no_cambia(cliente, datos, origen):
    client, ctx, _ = cliente
    fe.escribir_calibracion_fabrica_equipo(
        origen=origen, mapas={"pressure": {"pres_camara": EstadoAutoclave.map_pres["pres_camara"]}})
    r = client.post("/calibration/pressure/pres_camara/restaurar", json={"destino": "ultimo"})
    assert r.status_code == 409                      # sin audit_log, como siempre
    assert "sin_calibracion_previa" in r.text
