"""A2 (tanda 3): robustez ante cortes de energía abruptos (equipo sin UPS)."""

import json
import os
import sqlite3
from pathlib import Path

import pytest

from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos
from autoclave.devices.printer import heartbeat
from autoclave.installation import backend_guard
from autoclave.services.domain.logging.db_manager import (
    DbManager, es_base_corrupta)
from autoclave.utils import archivos
from autoclave.utils.archivos import escribir_texto_atomico


# ── escritura atómica ──────────────────────────────────────────────────────

def test_escribe_y_reemplaza(tmp_path):
    ruta = tmp_path / "a.json"
    escribir_texto_atomico(ruta, "uno")
    escribir_texto_atomico(ruta, "dos")
    assert ruta.read_text(encoding="utf-8") == "dos"
    assert list(tmp_path.glob("*.tmp")) == []


def test_un_corte_antes_del_reemplazo_deja_el_original(tmp_path, monkeypatch):
    ruta = tmp_path / "a.json"
    ruta.write_text("original", encoding="utf-8")

    def corte(*_a, **_k):
        raise OSError("corte de energía simulado")

    monkeypatch.setattr(archivos.os, "replace", corte)
    with pytest.raises(OSError):
        escribir_texto_atomico(ruta, "nuevo")
    assert ruta.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob("*.tmp")) == []


def test_respaldo_conserva_la_version_previa(tmp_path):
    ruta = tmp_path / "c.yaml"
    escribir_texto_atomico(ruta, "v1")
    escribir_texto_atomico(ruta, "v2", respaldo=True)
    assert ruta.read_text(encoding="utf-8") == "v2"
    assert (tmp_path / "c.yaml.bak").read_text(encoding="utf-8") == "v1"


def test_la_calibracion_se_escribe_de_forma_atomica(tmp_path, monkeypatch):
    from autoclave.config import calibration_writer as cw
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text(
        "calibration:\n  user:\n    temperature:\n      - gain: 1.0\n        offset: 0.0\n"
        "    pressure:\n      - gain: 1.0\n        offset: 0.0\n", encoding="utf-8")
    original = ruta.read_text(encoding="utf-8")
    monkeypatch.setattr(archivos.os, "replace",
                        lambda *_a, **_k: (_ for _ in ()).throw(OSError("corte")))
    with pytest.raises(OSError):
        cw.write_user_calibration(ruta, "temperature", 0, 1.1, 0.2, 100.0, 100.1, 134.0, 134.0)
    assert ruta.read_text(encoding="utf-8") == original


def test_heartbeat_atomico_y_lectura_de_archivo_corrupto(tmp_path):
    ruta = tmp_path / "last_shutdown.json"
    heartbeat.write_timestamp(ruta)
    assert heartbeat.read_last_shutdown(ruta) is not None
    ruta.write_text('{"timestamp": "2026-10-2', encoding="utf-8")     # truncado
    assert heartbeat.read_last_shutdown(ruta) is None
    ruta.write_bytes(b"\x00\x00\x00")
    assert heartbeat.read_last_shutdown(ruta) is None


def test_pid_atomico_y_corrupto_se_lee_como_ausente(tmp_path):
    ruta = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(4321, ruta)
    assert backend_guard.read_backend_pid(ruta) == 4321
    ruta.write_bytes(b"\x00\x00")
    assert backend_guard.read_backend_pid(ruta) is None


def test_contador_corrupto_se_recupera_con_la_base(tmp_path):
    ruta = tmp_path / "ciclo_contador.json"
    ruta.write_bytes(b'{"ultimo": 1')                       # truncado
    c = ContadorCiclos(ruta)
    assert c.sincronizar(41) == 41
    assert json.loads(ruta.read_text(encoding="utf-8"))["ultimo"] == 41
    assert c.siguiente() == 42


def test_contador_con_temporal_huerfano_de_un_corte(tmp_path):
    ruta = tmp_path / "ciclo_contador.json"
    c = ContadorCiclos(ruta)
    assert c.siguiente() == 1
    (tmp_path / "ciclo_contador.json.tmp").write_text("{basura", encoding="utf-8")
    assert c.siguiente() == 2


# ── respaldo JSONL ─────────────────────────────────────────────────────────

def test_respaldo_con_cola_de_bytes_basura_se_lee(tmp_path):
    r = RespaldoCiclos(tmp_path)
    uuid = "abcdef12-3456"
    assert r.encabezado(uuid, {"numero": 7})
    assert r.lectura(uuid, {"t": 1})
    with open(r.ruta(uuid), "ab") as f:
        f.write(b'{"registro": "lectura", "t": 2')           # línea cortada
        f.write(b"\xff\xfe\x00\x00")                          # basura de NTFS
    datos = RespaldoCiclos.leer(r.ruta(uuid))
    assert datos is not None and datos["encabezado"]["numero"] == 7
    assert len(datos["lecturas"]) == 1 and datos["cierre"] is None


# ── base de datos ──────────────────────────────────────────────────────────

def test_la_base_usa_wal_y_synchronous_full(tmp_path):
    db = DbManager(tmp_path / "t.db")
    try:
        assert db._conn.execute("PRAGMA synchronous").fetchone()[0] == 2   # FULL
        assert db._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        db.close()


def test_base_danada_se_detecta_al_abrir(tmp_path):
    ruta = tmp_path / "t.db"
    db = DbManager(ruta)
    for i in range(200):          # varias páginas, para tener qué dañar
        db.registrar_auditoria("evento", usuario="x", detalle={"i": i, "relleno": "z" * 200})
    db.close()
    datos = bytearray(ruta.read_bytes())
    assert len(datos) > 4096 * 4
    for i in range(4096 * 2, 4096 * 3):      # destruye una página interior
        datos[i] = 0xAB
    ruta.write_bytes(bytes(datos))
    with pytest.raises(sqlite3.DatabaseError) as e:
        DbManager(ruta)
    assert es_base_corrupta(e.value)


def test_base_sana_abre_normal(tmp_path):
    ruta = tmp_path / "t.db"
    DbManager(ruta).close()
    DbManager(ruta).close()
