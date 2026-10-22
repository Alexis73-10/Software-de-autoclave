# C1c / C1d (tanda 6): clase explícita de cada parámetro de presión o
# temperatura ("absoluto" | "diferencia" | "sin_conversion") y chaqueta
# absoluta (decisión 1.2 de Cristian).

import json
import logging
from pathlib import Path

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.runtime import unidades as u

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


def _archivos():
    archivos = []
    for carpeta in ("cycles/factory", "cycles/defecto", "cycles/user"):
        d = RAIZ / carpeta
        if d.is_dir():
            archivos += sorted(d.glob("*.json"))
    archivos.append(RAIZ / "config" / "global_params.json")
    return archivos


def _hojas(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict) and "value" in v:
            yield pre + k, v
        elif isinstance(v, dict):
            yield from _hojas(v, pre + k + ".")


def _parametros(ruta):
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return datos.get("parameters", datos)


def test_hay_archivos_que_revisar():
    assert len(_archivos()) >= 9


@pytest.mark.parametrize("ruta", _archivos(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_toda_hoja_de_presion_o_temperatura_tiene_clase(ruta):
    faltan = [n for n, h in _hojas(_parametros(ruta))
              if u.requiere_clase(h.get("unit", "")) and h.get("clase") not in u.CLASES]
    assert faltan == [], f"{ruta.name}: hojas sin 'clase' válida: {faltan}"


@pytest.mark.parametrize("ruta", _archivos(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_clase_solo_en_hojas_con_unidad_convertible(ruta):
    sobran = [n for n, h in _hojas(_parametros(ruta))
              if "clase" in h and not u.requiere_clase(h.get("unit", ""))]
    assert sobran == []


def test_catalogo_absolutos_coinciden_con_la_clase_de_los_json():
    """Las entradas del catálogo de límites marcadas como presión o
    temperatura absoluta del modelo deben tener clase "absoluto"."""
    absolutos = {k for k, (_mn, _mx, motivo) in cp.CATALOGO.items()
                 if motivo in ("presión absoluta del modelo", "temperatura del modelo")}
    assert absolutos
    for ruta in _archivos()[:-1]:
        params = _parametros(ruta)
        for fase, ruta_param in absolutos:
            hoja = params.get(fase, {})
            for parte in ruta_param.split("."):
                hoja = hoja.get(parte, {}) if isinstance(hoja, dict) else {}
            if "value" in hoja:
                assert hoja.get("clase") == "absoluto", (ruta.name, fase, ruta_param)


def test_rango_calentamiento_es_sin_conversion_en_todos():
    vistos = 0
    for ruta in _archivos():
        for n, h in _hojas(_parametros(ruta)):
            if n.split(".")[-1] == "rango_calentamiento":
                vistos += 1
                assert h["clase"] == "sin_conversion", ruta.name
    assert vistos >= 8


# ── el módulo usa la clase, no el nombre ────────────────────────────────────

def test_la_clase_manda_sobre_el_prefijo():
    assert u.clase_de_unidad("kPa", "rango_raro", "absoluto") == "pres"
    assert u.clase_de_unidad("kPa", "presion_x", "diferencia") == "dpres"
    assert u.clase_de_unidad("°C", "rango_x", "absoluto") == "temp"
    assert u.clase_de_unidad("°C", "temperatura_x", "diferencia") == "dtemp"
    assert u.clase_de_unidad("kPa", "presion_x", "sin_conversion") is None
    assert u.clase_de_unidad("°C/min", "tasa", "diferencia") == "dtemp"
    assert u.clase_de_unidad("kPa/min", "tasa", "diferencia") == "dpres"
    assert u.clase_de_unidad("seg", "tiempo", "absoluto") is None


def test_clase_desconocida_no_convierte_y_avisa(caplog):
    u._avisados.clear()
    with caplog.at_level(logging.WARNING, logger=u.__name__):
        assert u.clase_de_unidad("kPa", "presion_y", "manometrico") is None
    assert "desconocida" in caplog.text


def test_sin_clase_migra_por_prefijo_con_advertencia(caplog):
    u._avisados.clear()
    with caplog.at_level(logging.WARNING, logger=u.__name__):
        assert u.clase_de_unidad("kPa", "presion_viejo_c1c") == "pres"
        assert u.clase_de_unidad("kPa", "rango_viejo_c1c") == "dpres"
        assert u.clase_de_unidad("kPa", "rango_calentamiento") is None
    assert "sin \"clase\"" in caplog.text
    assert "presion_viejo_c1c" in caplog.text


def test_bridge_qml_usa_la_clase():
    from autoclave.ui_qml.bridge.unidades_qml import UnidadesQml
    un = UnidadesQml(sondear=False, consultar=lambda: None)
    un._aplicar({"temperatura": "F", "presion": "psi", "p_atm": 75.0})
    # un "rango_" declarado absoluto se muestra como absoluto (antes, diferencia)
    assert un.unidadIngreso("kPa", "rango_raro", "absoluto") == "psig"
    assert un.unidadIngreso("kPa", "presion_rara", "diferencia") == "psi"
    assert un.unidadIngreso("kPa", "presion_rara", "sin_conversion") == ""
    assert un.aInterna(212.0, "°C", "rango_x", "F", "absoluto") == pytest.approx(100.0)
    assert un.aInterna(18.0, "°C", "temperatura_x", "F", "diferencia") == pytest.approx(10.0)


def test_qml_pasa_la_clase_al_singleton():
    qml = (RAIZ / "ui_qml" / "qml" / "Pantallas" / "OpcionesParametrosCiclo.qml").read_text(encoding="utf-8")
    import re
    llamadas = re.findall(r"Unidades\.(unidadIngreso|parametro|aInterna|aMostrarEn|ingresosPsi)\(", qml)
    assert llamadas
    assert qml.count(".clase || \"\"") >= len(llamadas)


def test_endpoint_seccion_devuelve_la_clase():
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from autoclave.core.managers.cycle_manager import CycleManager
    from tests.backend_doble import cargar_servidor
    cm = CycleManager()
    cm.load_all_cycles()
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.db.get_auditoria.return_value = []
    srv, _ = cargar_servidor(ctx)
    r = TestClient(srv.app).get("/programas/4/seccion/esterilizacion")
    assert r.status_code == 200, r.text
    por_clave = {p["clave"]: p for p in r.json()["parametros"]}
    assert por_clave["temperatura_esterilizacion"]["clase"] == "absoluto"
    assert por_clave["brecha_segura_presion"]["clase"] == "diferencia"
    assert por_clave["tiempo_esterilizacion"]["clase"] is None
