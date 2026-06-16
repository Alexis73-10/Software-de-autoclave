import sys
import os
import pytest
from datetime import date

# Agregar tools/generador al path para importar db directamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "generador"))
import db as generador_db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(generador_db, "DB_PATH", tmp_path / "test.db")
    generador_db.init_db()


def test_fue_instalado_falso_sin_registros():
    assert not generador_db.fue_instalado("SN001")


def test_fue_instalado_verdadero_con_instalacion():
    generador_db.log_codigo("SN001", "instalacion", "admin")
    assert generador_db.fue_instalado("SN001")


def test_fue_instalado_verdadero_con_reinstalacion():
    generador_db.log_codigo("SN001", "reinstalacion", "admin")
    assert generador_db.fue_instalado("SN001")


def test_fue_instalado_falso_con_solo_fabrica():
    generador_db.log_codigo("SN001", "fabrica", "admin")
    assert not generador_db.fue_instalado("SN001")


def test_get_history_vacio():
    assert generador_db.get_history("SN001") == []


def test_get_history_contiene_registros_correctos():
    generador_db.log_codigo("SN001", "instalacion", "user1", date(2026, 1, 1))
    generador_db.log_codigo("SN001", "fabrica",     "user2", date(2026, 2, 1))
    hist = generador_db.get_history("SN001")
    assert len(hist) == 2
    assert hist[0]["tipo"] == "fabrica"       # más reciente primero
    assert hist[0]["usuario"] == "user2"
    assert hist[1]["tipo"] == "instalacion"


def test_get_history_solo_para_el_serial_dado():
    generador_db.log_codigo("SN001", "instalacion", "user1")
    generador_db.log_codigo("SN002", "instalacion", "user2")
    hist = generador_db.get_history("SN001")
    assert len(hist) == 1
    assert hist[0]["usuario"] == "user1"


def test_log_codigo_usa_fecha_hoy_por_defecto():
    generador_db.log_codigo("SN001", "fabrica", "admin")
    hist = generador_db.get_history("SN001")
    assert hist[0]["fecha"] == date.today().isoformat()
