"""Asignación de numero_programa/tipo_ciclo a ciclos importados de Tuttnauer."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import asignar_programas_tuttnauer as asignar  # noqa: E402
import importar_ciclo_tuttnauer as importador  # noqa: E402
from autoclave.services.domain.logging.db_manager import DbManager  # noqa: E402

_TICKET = """Fecha: 05/ENE/2026
Hora: 08:00:00
Núm de serie: 123
Modelo: T
Ver de SoftW.: 1
Número de ciclo: {numero}
{nombre}
(Personalizado)
Temp. Ester. 121.0
Tiempo Ester 30
W 00:00:00 25.0 100.0
S 00:10:00 121.0 205.0
Ciclo acabado
Hora: 08:30:00
"""


def _bd(tmp_path):
    ruta = tmp_path / "autoclave.db"
    DbManager(ruta)
    return ruta


def _ticket(tmp_path, numero, nombre):
    f = tmp_path / f"cycle_{numero:06d}.txt"
    f.write_text(_TICKET.format(numero=numero, nombre=nombre), encoding="utf-8")
    return f


@pytest.mark.parametrize("nombre,numero,tipo", [
    ("TEXTILES", 5, "textiles"), ("Liquidos A", 4, "liquidos"),
    ("INSTRUMENTAL PL", 2, "134_instrumental")])
def test_importar_asigna_programa(tmp_path, nombre, numero, tipo):
    bd = _bd(tmp_path)
    importador.importar(_ticket(tmp_path, 1, nombre), bd)
    fila = sqlite3.connect(bd).execute(
        "SELECT numero_programa, tipo_ciclo, nombre_ciclo FROM ciclos").fetchone()
    assert fila == (numero, tipo, nombre)


def test_importar_nombre_desconocido_queda_sin_programa(tmp_path):
    bd = _bd(tmp_path)
    importador.importar(_ticket(tmp_path, 1, "OTRO"), bd)
    assert sqlite3.connect(bd).execute(
        "SELECT numero_programa, tipo_ciclo FROM ciclos").fetchone() == (None, "Personalizado")


def test_asignar_es_idempotente_y_respalda(tmp_path):
    bd = _bd(tmp_path)
    con = sqlite3.connect(bd)
    for n, nombre in enumerate(["TEXTILES", "TEXTILES", "Liquidos A", "INSTRUMENTAL PL", "X"], 1):
        con.execute("INSERT INTO ciclos (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,"
                    " uuid) VALUES (?,?,?,?,?)", (n, "2026-01-05T08:00:00", "", nombre, f"u{n}"))
    con.commit()
    con.close()
    assert Path(asignar.respaldar(bd)).is_file()
    assert asignar.asignar(bd) == {"INSTRUMENTAL PL": 1, "Liquidos A": 1, "TEXTILES": 2}
    assert asignar.asignar(bd) == {"INSTRUMENTAL PL": 0, "Liquidos A": 0, "TEXTILES": 0}
    filas = sqlite3.connect(bd).execute(
        "SELECT nombre_ciclo, numero_programa, tipo_ciclo FROM ciclos ORDER BY id").fetchall()
    assert filas[0] == ("TEXTILES", 5, "textiles") and filas[4] == ("X", None, "")
