"""U1 (tanda 5): módulo único de unidades de presentación (core/runtime/unidades.py)."""

import ast
import math
from pathlib import Path

import pytest

from autoclave.core.runtime import unidades as u

RAIZ = Path(__file__).resolve().parents[1]
ATM = 74.6          # Bogotá, aprox.


@pytest.mark.parametrize("c", [-10.0, 0.0, 20.0, 121.0, 134.0, 137.5])
def test_temperatura_ida_y_vuelta(c):
    for unidad in u.TEMPERATURAS:
        assert math.isclose(u.temp_a_interna(u.temp_a_mostrar(c, unidad), unidad), c, abs_tol=1e-9)


def test_valores_conocidos_de_temperatura():
    assert u.formatear_temp(134.0, "F") == "273.2 °F"
    assert u.formatear_temp(121.1, "C") == "121.1 °C"
    assert u.formatear_temp(None, "C") == "—"


def test_diferencias_de_temperatura_sin_desplazamiento():
    assert u.dtemp_a_mostrar(3.0, "F") == pytest.approx(5.4)
    assert u.dtemp_a_mostrar(3.0, "F") != u.temp_a_mostrar(3.0, "F")
    assert u.dtemp_a_interna(5.4, "F") == pytest.approx(3.0)
    assert u.formatear_dtemp(0.3, "F") == "0.54 °F"


@pytest.mark.parametrize("kpa", [5.0, 50.0, ATM, 101.3, 210.0, 330.0])
@pytest.mark.parametrize("unidad", ["kPa", "bar", "mbar"])
def test_presion_absoluta_ida_y_vuelta(kpa, unidad):
    v, mostrada = u.pres_a_mostrar(kpa, unidad, ATM)
    assert mostrada == unidad
    assert math.isclose(u.pres_a_interna(v, unidad, ATM), kpa, abs_tol=1e-9)


@pytest.mark.parametrize("kpa", [5.0, 50.0, ATM - 0.01, ATM, ATM + 0.01, 210.0, 330.0])
def test_psi_a_ambos_lados_de_la_atmosferica(kpa):
    v, mostrada = u.pres_a_mostrar(kpa, "psi", ATM)
    assert v >= 0                                   # nunca un psi negativo
    assert mostrada == ("psig" if kpa >= ATM else "inHg")
    assert math.isclose(u.pres_a_interna(v, mostrada, ATM), kpa, abs_tol=1e-9)


def test_psi_justo_en_la_atmosferica_es_cero_psig():
    assert u.formatear_pres(ATM, "psi", ATM) == "0.0 psig"


def test_psi_valores_conocidos():
    # 134 °C saturado ≈ 304 kPa abs; con P_atm 101.325 son ≈ 29.4 psig
    assert u.formatear_pres(304.0, "psi", 101.325) == "29.4 psig"
    assert u.formatear_pres(101.325 - 3.386389 * 25, "psi", 101.325) == "25.0 inHg"


def test_sin_presion_atmosferica_en_psi_no_inventa():
    assert u.formatear_pres(200.0, "psi", None) == "—"
    assert u.pres_a_mostrar(200.0, "psi", float("nan"))[0] is None
    with pytest.raises(ValueError):
        u.pres_a_interna(10.0, "psig", None)
    assert u.formatear_pres(200.0, "kPa", None) == "200.0 kPa"      # kPa no la necesita


def test_psi_negativo_se_rechaza_al_ingresar():
    with pytest.raises(ValueError):
        u.pres_a_interna(-1.0, "psig", ATM)
    with pytest.raises(ValueError):
        u.pres_a_interna(-1.0, "inHg", ATM)


def test_diferencias_de_presion_sin_restar_la_atmosfera():
    v, mostrada = u.dpres_a_mostrar(6.894757, "psi")
    assert mostrada == "psi" and v == pytest.approx(1.0)
    assert u.dpres_a_interna(1.0, "psi") == pytest.approx(6.894757)
    assert u.dpres_a_mostrar(30.0, "bar")[0] == pytest.approx(0.3)
    assert u.formatear_dpres(2.0, "mbar") == "20 mbar"


def test_resolucion_por_unidad():
    assert u.formatear_pres(304.123, "bar") == "3.04 bar"
    assert u.formatear_pres(304.123, "mbar") == "3041 mbar"
    assert u.formatear_pres(304.123, "kPa") == "304.1 kPa"


def test_unidades_de_ingreso_psi_segun_el_rango():
    assert u.unidades_de_ingreso_psi(0, 1000, ATM) == ["psig", "inHg"]
    assert u.unidades_de_ingreso_psi(150, 400, ATM) == ["psig"]
    assert u.unidades_de_ingreso_psi(0, 50, ATM) == ["inHg"]
    assert u.unidades_de_ingreso_psi(0, 1000, None) == []


def test_clase_de_unidad_absolutos_y_diferencias():
    assert u.clase_de_unidad("°C", "temperatura_esterilizacion") == "temp"
    assert u.clase_de_unidad("�C", "rango_temperatura_ester") == "dtemp"
    assert u.clase_de_unidad("°C/min", "tasa_calentamiento") == "dtemp"
    assert u.clase_de_unidad("kPa", "presion_alta_pulso_a") == "pres"
    assert u.clase_de_unidad("kPa", "brecha_segura_presion") == "dpres"
    assert u.clase_de_unidad("kPa", "presion_add_esterilizacion") == "dpres"
    assert u.clase_de_unidad("kPa/min", "tasa_presion") == "dpres"
    assert u.clase_de_unidad("seg", "tiempo") is None


def test_validar():
    u.validar("F", "psi")
    for t, p in (("K", "kPa"), ("C", "atm"), ("c", "kPa")):
        with pytest.raises(ValueError):
            u.validar(t, p)


# ── prueba estática: el control nunca usa unidades de presentación ─────────

_PROHIBIDOS = ["src/autoclave/core/control", "src/autoclave/state_machine",
               "src/autoclave/services/domain/puertas", "src/autoclave/devices",
               "src/autoclave/core/managers/alarm_manager.py"]


def _importa_unidades(ruta: Path) -> bool:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and "runtime.unidades" in nodo.module:
            return True
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "autoclave.core.runtime" and any(
                a.name == "unidades" for a in nodo.names):
            return True
        if isinstance(nodo, ast.Import) and any("runtime.unidades" in a.name for a in nodo.names):
            return True
    return False


def test_ni_control_ni_puertas_ni_alarmas_importan_unidades():
    archivos = []
    for p in _PROHIBIDOS:
        ruta = RAIZ / p
        archivos += [ruta] if ruta.is_file() else list(ruta.rglob("*.py"))
    archivos += [f for f in (RAIZ / "src/autoclave").rglob("*.py")
                 if "control_loop" in f.name or "alarm" in f.name]
    assert archivos
    culpables = [str(f.relative_to(RAIZ)) for f in archivos if _importa_unidades(f)]
    assert culpables == []


def test_el_modulo_no_importa_qt():
    texto = (RAIZ / "src/autoclave/core/runtime/unidades.py").read_text(encoding="utf-8")
    assert "PySide6" not in texto


def test_config_por_defecto_y_robusta(tmp_path):
    c = u.ConfigUnidades(tmp_path / "unidades.json")
    assert c.leer() == {"temperatura": "C", "presion": "kPa"}
    (tmp_path / "unidades.json").write_text("{malo", encoding="utf-8")
    assert c.leer() == {"temperatura": "C", "presion": "kPa"}
    assert c.guardar("F", "psi") == {"temperatura": "F", "presion": "psi"}
    assert c.leer() == {"temperatura": "F", "presion": "psi"}
    with pytest.raises(ValueError):
        c.guardar("K", "kPa")
    assert c.leer()["temperatura"] == "F"


# ── endpoints ──────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.config_unidades = u.ConfigUnidades(tmp_path / "unidades.json")
    ctx.config_manager.get.side_effect = lambda k: {"presion_admosferica": ATM}.get(k)
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    return TestClient(srv.app), srv, ctx, cabecera


def test_api_lee_por_defecto_con_p_atm(api):
    client, *_ = api
    assert client.get("/units").json() == {"temperatura": "C", "presion": "kPa", "p_atm": ATM}


@pytest.mark.parametrize("rol, esperado", [("tecnico", 403), ("ingeniero", 200), ("admin", 403),
                                           ("operador", 403)])   # decisión 1.9 (tanda 6)
def test_api_permisos_y_auditoria(api, rol, esperado):
    client, srv, ctx, cabecera = api
    r = client.put("/units", headers=cabecera(srv, rol), json={"temperatura": "F", "presion": "psi"})
    assert r.status_code == esperado
    if esperado == 200:
        assert client.get("/units").json()["presion"] == "psi"          # en caliente
        assert any(f["evento"] == "unidades_configuradas" for f in ctx.db.get_auditoria(limite=5))


def test_api_sin_sesion_401(api):
    client, *_ = api
    assert client.put("/units", json={"temperatura": "F", "presion": "psi"}).status_code == 401


@pytest.mark.parametrize("rol", ["ingeniero"])
def test_api_rechaza_en_ciclo_tambien_al_ingeniero(api, rol):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cabecera = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.put("/units", headers=cabecera(srv, rol), json={"temperatura": "F", "presion": "psi"})
    assert r.status_code == 409
    assert client.get("/units").json()["temperatura"] == "C"


@pytest.mark.parametrize("cuerpo", [{"temperatura": "K", "presion": "kPa"},
                                    {"temperatura": "C", "presion": "atm"}, {"temperatura": "C"}])
def test_api_valores_invalidos_422(api, cuerpo):
    client, srv, ctx, cabecera = api
    assert client.put("/units", headers=cabecera(srv, "ingeniero"), json=cuerpo).status_code == 422


def test_api_sin_p_atm_publica_null(api):
    client, srv, ctx, cabecera = api
    ctx.config_manager.get.side_effect = lambda k: None
    assert client.get("/units").json()["p_atm"] is None
