"""M8 (tanda 8): D8-3.25 de decisiones_tanda_8.md.

- "Último mantenimiento" pasa a llamarse "Último preventivo" (es/en).
- Se elimina el tipo `otro` (P-3) para registros nuevos; las filas viejas se
  rotulan "Otro (histórico)", con el mismo criterio que MNT-05.
- MNT-04: el admin consulta el historial (`GET /maintenance/records`)."""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import mantenimiento as m
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.servicio_mantenimiento import (
    TIPOS as TIPOS_SERVICIO, ErrorMantenimiento, ServicioMantenimiento)
from autoclave.services.domain.logging.db_manager import DbManager
from tests.backend_doble import cabecera, cargar_servidor

INST = datetime(2026, 10, 26, 9, 0)


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    hoy = {"d": date(2026, 10, 27)}
    contador = ContadorCiclos(tmp_path / "ciclo_contador.json")
    s = ServicioMantenimiento(tmp_path / "mantenimiento.json", db, INST, contador, MagicMock(),
                              hoy=lambda: hoy["d"])
    return s, db


@pytest.fixture
def api(entorno):
    s, db = entorno
    ctx = MagicMock()
    ctx.db = db
    ctx.mantenimiento = s
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), srv, s, db


def _catalogo(idioma):
    ruta = Path(m.__file__).resolve().parents[2] / "i18n" / f"{idioma}.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


# ── "Último preventivo" ─────────────────────────────────────────────────────

def test_rotulos_ultimo_preventivo():
    es, en = _catalogo("es"), _catalogo("en")
    assert es["menu"]["ultimo_mantenimiento"] == "Fecha del último preventivo"
    assert en["menu"]["ultimo_mantenimiento"] == "Date of last preventive maintenance"
    assert es["equipo"]["ultimo_mantenimiento"] == "Último preventivo"
    assert en["equipo"]["ultimo_mantenimiento"] == "Last preventive maintenance"


def test_ayuda_de_intervalos_cuenta_desde_el_ultimo_preventivo():
    assert "último preventivo" in _catalogo("es")["opciones"]["mant_intervalos_ayuda"]
    assert "last preventive maintenance" in _catalogo("en")["opciones"]["mant_intervalos_ayuda"]


# ── P-3: sin tipo `otro` para registros nuevos ──────────────────────────────

def test_otro_no_es_registrable_y_es_historico():
    assert m.TIPOS == ("preventivo", "correctivo")
    assert TIPOS_SERVICIO == m.TIPOS
    assert "otro" in m.TIPOS_HISTORICOS and "calibracion" in m.TIPOS_HISTORICOS
    assert not set(m.TIPOS_HISTORICOS) & set(m.TIPOS)


def test_servicio_rechaza_otro(entorno):
    s, db = entorno
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "otro", "")
    assert e.value.codigo == "validacion"
    assert db.listar_mantenimientos() == []


def test_post_otro_da_422_validacion(api):
    client, srv, s, db = api
    r = client.post("/maintenance/records", headers=cabecera(srv, "tecnico"),
                    json={"tipo": "otro", "observaciones": ""})
    assert r.status_code == 422 and r.json()["codigo"] == "validacion"
    assert db.listar_mantenimientos() == []


def test_controlador_no_ofrece_ni_envia_otro():
    from autoclave.ui_qml.controllers.mantenimiento_controller import MantenimientoController
    sesion = MagicMock()
    c = MantenimientoController(sesion=sesion)
    assert "otro" not in c.property("tipos")
    assert c.registrar("otro") is False
    sesion.enviar.assert_not_called()


def test_textos_de_otro_historico():
    assert _catalogo("es")["opciones"]["mant_tipo_otro"] == "Otro (histórico)"
    assert _catalogo("en")["opciones"]["mant_tipo_otro"] == "Other (historical)"


def test_fila_historica_otro_se_conserva_y_no_mueve_el_contador(entorno):
    s, db = entorno
    db.registrar_mantenimiento("2026-10-26", "tec", "otro", "viejo", 3)
    assert s.historial()[0]["tipo"] == "otro"
    assert s.estado().proximo_fecha == date(2027, 10, 26)   # base: instalación


# ── MNT-04: el admin consulta el historial ──────────────────────────────────

def test_admin_consulta_el_historial(api):
    client, srv, s, db = api
    db.registrar_mantenimiento("2026-10-27", "tec", "preventivo", "ok", 0)
    r = client.get("/maintenance/records", headers=cabecera(srv, "admin"))
    assert r.status_code == 200
    assert r.json()["registros"][0]["tipo"] == "preventivo"


def test_admin_no_registra_ni_configura(api):
    client, srv, s, db = api
    h = cabecera(srv, "admin")
    assert client.post("/maintenance/records", headers=h,
                       json={"tipo": "preventivo"}).status_code == 403
    assert client.put("/maintenance/config", headers=h,
                      json={"intervalo_dias": 90, "intervalo_ciclos": 0}).status_code == 403
    assert db.listar_mantenimientos() == []


def test_operador_sigue_sin_consultar_el_historial(api):
    client, srv, *_ = api
    assert client.get("/maintenance/records").status_code == 401
    assert client.get("/maintenance/records",
                      headers=cabecera(srv, "operador")).status_code == 403
