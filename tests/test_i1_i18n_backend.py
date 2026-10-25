"""I1 (tanda 5): i18n F2 — alarmas por código + parámetros e idioma del equipo."""

import json
import string
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import alarmas_i18n
from autoclave.core.runtime.config_idioma import ConfigIdioma
from autoclave.state_machine.alarms.catalogo import CATALOGO
from tests.backend_doble import modulo_backend

RAIZ = Path(__file__).resolve().parents[1]


def _cat(lang):
    return json.loads((RAIZ / f"src/autoclave/i18n/{lang}.json").read_text(encoding="utf-8"))


def _campos(plantilla):
    return {c for _, c, _, _ in string.Formatter().parse(plantilla) if c}


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize("codigo", sorted(CATALOGO))
def test_cada_codigo_de_alarma_existe_con_sus_parametros(lang, codigo):
    entrada = _cat(lang)["alarmas"].get(codigo)
    assert isinstance(entrada, dict), (lang, codigo)
    for campo in ("titulo", "plantilla", "accion"):
        assert isinstance(entrada.get(campo), str) and entrada[campo].strip(), (lang, codigo, campo)
    assert _campos(entrada["plantilla"]) == CATALOGO[codigo].campos(), (lang, codigo)


def _valores(d):
    ejemplo = {"pres": 210.0, "minimo": 100.0, "maximo": 200.0, "objetivo": 150.0, "rango": 10.0,
               "temp": 90.5, "minutos": 12.0, "segundos": 5.0,
               # E12 (tanda 12): CIC-12/CIC-13 (saturación, K y °C con decimales)
               "tsat": 137.0, "dt": 2.5}
    return {c: ejemplo.get(c, "X") for c in d.campos()}


@pytest.mark.parametrize("codigo", sorted(CATALOGO))
def test_las_plantillas_se_renderizan_en_ambos_idiomas(codigo):
    d = CATALOGO[codigo]
    t = alarmas_i18n.por_idioma(d, _valores(d))
    assert t["es"]["descripcion"] and t["en"]["descripcion"]
    assert "{" not in t["en"]["descripcion"]


def test_texto_en_ingles_con_parametros():
    d = CATALOGO["PRE-04"]
    t = alarmas_i18n.textos(d, {"pres": 250.0, "maximo": 120.0}, "en")
    assert t["titulo"] == "High chamber pressure"
    assert t["descripcion"] == "The chamber is at 250 kPa, above 120 kPa."


def test_sin_valores_suficientes_cae_al_espanol_sin_lanzar():
    d = CATALOGO["PRE-04"]
    t = alarmas_i18n.textos(d, {}, "en")
    assert t["descripcion"]          # la plantilla del catálogo sin renderizar


def test_el_dto_de_status_lleva_codigo_valores_y_textos():
    from autoclave.backend import server
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    am = AlarmManager()
    am.activar("PRE-04", pres=250.0, maximo=120.0)
    dto = modulo_backend("rutas.sistema")._alarma_dto(am.activas()[0])
    assert dto["codigo"] == "PRE-04" and dto["valores"] == {"pres": 250.0, "maximo": 120.0}
    assert dto["textos"]["en"]["titulo"] == "High chamber pressure"
    assert "cámara" in dto["description"].lower()          # compatibilidad: español


def test_historico_con_texto_libre_sigue_mostrandose():
    """Compatibilidad hacia atrás: una alarma sin entrada en el catálogo i18n
    conserva el texto del catálogo de seguridad."""
    d = MagicMock(codigo="NO-EXISTE", titulo="T", accion="A", descripcion="D")
    d.renderizar.return_value = "D"
    assert alarmas_i18n.textos(d, {}, "en") == {"titulo": "T", "accion": "A", "descripcion": "D"}


# ── idioma ─────────────────────────────────────────────────────────────────

def test_config_idioma(tmp_path):
    c = ConfigIdioma(tmp_path / "idioma.json")
    assert c.leer() == "es"
    assert c.guardar("en") == "en" and c.leer() == "en"
    with pytest.raises(ValueError):
        c.guardar("fr")


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.config_idioma = ConfigIdioma(tmp_path / "idioma.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    return TestClient(srv.app), srv, ctx, cabecera


@pytest.mark.parametrize("rol", ["admin", "ingeniero"])   # decisión 1.9 (tanda 6)
def test_admin_e_ingeniero_cambian_el_idioma_aun_en_ciclo(api, rol):
    client, srv, ctx, cabecera = api
    r = client.put("/language", headers=cabecera(srv, rol), json={"idioma": "en"})
    assert r.status_code == 200
    assert client.get("/language").json() == {"idioma": "en"}
    assert any(f["evento"] == "idioma_configurado" for f in ctx.db.get_auditoria(limite=5))


def test_idioma_sin_sesion_o_invalido(api):
    client, srv, ctx, cabecera = api
    assert client.put("/language", json={"idioma": "en"}).status_code == 401
    assert client.put("/language", headers=cabecera(srv, "ingeniero"),
                      json={"idioma": "fr"}).status_code == 422
    assert client.put("/language", headers=cabecera(srv, "tecnico"),
                      json={"idioma": "en"}).status_code == 403   # decisión 1.9


def test_status_no_cae_por_textos_rotos(monkeypatch):
    """Revisión I1 (M-1, M-2, B-2)."""
    from autoclave import i18n
    def falla(*a, **k):
        raise ValueError("catálogo roto")
    monkeypatch.setattr(i18n, "valor", falla)
    d = CATALOGO["PRE-04"]
    assert alarmas_i18n.textos(d, {"pres": 1.0, "maximo": 2.0}, "en")["titulo"] == d.titulo
    assert alarmas_i18n.por_idioma(None, {}) == {}
    assert alarmas_i18n.valores_json({"x": float("nan"), "y": float("inf"), "z": 1.0}) == {
        "x": None, "y": None, "z": 1.0}
