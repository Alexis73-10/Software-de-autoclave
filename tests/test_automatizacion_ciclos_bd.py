# Instalación por automatización: columnas serie_original / modelo_original en
# `ciclos` (migración v12), CycleLogger y reimportación desde el respaldo JSONL.
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.services.domain.logging import db_manager
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.db_manager import DbManager

from tests.test_t8_modo_sin_bd import _Estado, _correr_ciclo

ORIG = ("SNAA0001", "MODELO ORIGINAL DE PRUEBA")


def _columnas(con):
    return [f[1] for f in con.execute("PRAGMA table_info(ciclos)")]


def _crear(db, uuid="u1", numero=1, **extra):
    return db.crear_ciclo(numero, "STD", "Ciclo", 134, 4, "M-1", "SN000001", "1.0",
                          uuid=uuid, **extra)


def _fila(db, ciclo_id):
    return dict(db._conn.execute("SELECT * FROM ciclos WHERE id=?", (ciclo_id,)).fetchone())


def test_bd_nueva_tiene_columnas_y_version_12(tmp_path):
    db = DbManager(tmp_path / "a.db")
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION == 12
    cols = _columnas(db._conn)
    assert "serie_original" in cols and "modelo_original" in cols


def test_bd_v11_se_migra_y_filas_viejas_quedan_null(tmp_path):
    ruta = tmp_path / "v11.db"
    db = DbManager(ruta)
    viejo = _crear(db)
    db.close()
    # simula una BD v11: sin las columnas nuevas y user_version = 11
    con = sqlite3.connect(ruta)
    con.execute("ALTER TABLE ciclos DROP COLUMN serie_original")
    con.execute("ALTER TABLE ciclos DROP COLUMN modelo_original")
    con.execute("PRAGMA user_version = 11")
    con.commit()
    assert "serie_original" not in _columnas(con)
    con.close()

    db2 = DbManager(ruta)
    assert db2.get_version_esquema() == 12
    fila = _fila(db2, viejo)
    assert fila["serie_original"] is None and fila["modelo_original"] is None
    nuevo = _crear(db2, uuid="u2", numero=2, serie_original=ORIG[0], modelo_original=ORIG[1])
    assert _fila(db2, nuevo)["serie_original"] == ORIG[0]
    db2.close()


def test_migracion_v12_es_idempotente(tmp_path):
    db = DbManager(tmp_path / "i.db")
    db_manager._migracion_v12(db._conn)
    db_manager._migracion_v12(db._conn)
    assert _columnas(db._conn).count("serie_original") == 1
    assert _columnas(db._conn).count("modelo_original") == 1
    db.close()


def test_ciclo_de_fabricacion_queda_con_columnas_null(tmp_path):
    db = DbManager(tmp_path / "f.db")
    fila = _fila(db, _crear(db))
    assert fila["serie"] == "SN000001" and fila["modelo"] == "M-1"
    assert fila["serie_original"] is None and fila["modelo_original"] is None


def test_ciclo_de_automatizacion_guarda_y_devuelve_originales(tmp_path):
    db = DbManager(tmp_path / "au.db")
    cid = _crear(db, serie_original=ORIG[0], modelo_original=ORIG[1])
    fila = _fila(db, cid)
    assert (fila["serie_original"], fila["modelo_original"]) == ORIG
    assert fila["serie"] == "SN000001" and fila["modelo"] == "M-1"   # conservan su significado


def test_importacion_con_y_sin_claves(tmp_path):
    db = DbManager(tmp_path / "imp.db")
    base = {"uuid": "x1", "numero": 5, "tipo": "STD", "nombre": "C", "temp_ester": 134,
            "tiempo_ester": 4, "modelo": "M-1", "serie": "SN000001", "version_sw": "1"}
    assert db.importar_ciclo_respaldo(base, [], None, "interrumpido") == "importado"
    con_claves = {**base, "uuid": "x2", "numero": 6, "serie_original": ORIG[0], "modelo_original": ORIG[1]}
    assert db.importar_ciclo_respaldo(con_claves, [], None, "interrumpido") == "importado"
    filas = {f["uuid"]: f for f in (dict(r) for r in db._conn.execute("SELECT * FROM ciclos"))}
    assert filas["x1"]["serie_original"] is None and filas["x1"]["modelo_original"] is None
    assert (filas["x2"]["serie_original"], filas["x2"]["modelo_original"]) == ORIG
    # con cierre también
    cierre = {"fecha_fin": "2026-10-30T10:00:00", "resultado": "COMPLETADO"}
    assert db.importar_ciclo_respaldo({**con_claves, "uuid": "x3", "numero": 7}, [], cierre, "i") == "importado"
    f3 = [dict(r) for r in db._conn.execute("SELECT * FROM ciclos WHERE uuid='x3'")][0]
    assert f3["resultado"] == "COMPLETADO" and f3["serie_original"] == ORIG[0]


def _logger_con_perfil(tmp_path, db, perfil):
    programa = MagicMock()
    programa.id, programa.name, programa.number = "instrumental", "Instrumental 134", 2
    programa.get_param.side_effect = lambda s, n: {"temperatura_esterilizacion": 134,
                                                   "tiempo_esterilizacion": 4}.get(n)
    programa.instantanea.return_value = {"id": "instrumental"}
    cm = MagicMock()
    cm.get_selected_cycle.return_value = programa
    contador = MagicMock()
    contador.siguiente.return_value = 12
    estado = _Estado()
    respaldo = RespaldoCiclos(tmp_path / "respaldo")
    cl = CycleLogger(db, estado, {}, perfil, cm, printer=MagicMock(), contador=contador,
                     respaldo=respaldo, sin_base_de_datos=False)
    return cl, estado, respaldo


def _encabezado(cl, estado, respaldo):
    _correr_ciclo(cl, estado)
    cl.detener(5.0)
    [ruta] = respaldo.pendientes()
    return respaldo.leer(ruta)["encabezado"]


def test_cycle_logger_fabricacion_identico(tmp_path):
    db = DbManager(tmp_path / "cl1.db")
    perfil = SimpleNamespace(serial_number="SNAA0001", model_id="M1")
    cl, estado, respaldo = _logger_con_perfil(tmp_path, db, perfil)
    enc = _encabezado(cl, estado, respaldo)
    assert "serie_original" not in enc and "modelo_original" not in enc
    fila = dict(db._conn.execute("SELECT * FROM ciclos").fetchone())
    assert fila["serie_original"] is None and fila["modelo_original"] is None


def test_cycle_logger_perfil_mock_no_inventa_originales(tmp_path):
    db = DbManager(tmp_path / "cl2.db")
    cl, estado, respaldo = _logger_con_perfil(
        tmp_path, db, MagicMock(serial_number="S1", model_id="M1"))
    enc = _encabezado(cl, estado, respaldo)
    assert "serie_original" not in enc and "modelo_original" not in enc


def test_cycle_logger_automatizacion_guarda_en_bd_y_respaldo(tmp_path):
    db = DbManager(tmp_path / "cl3.db")
    perfil = SimpleNamespace(serial_number="SN000001", model_id="M1",
                             serial_original=ORIG[0], modelo_original=ORIG[1])
    cl, estado, respaldo = _logger_con_perfil(tmp_path, db, perfil)
    enc = _encabezado(cl, estado, respaldo)
    assert (enc["serie_original"], enc["modelo_original"]) == ORIG
    assert enc["serie"] == "SN000001" and enc["modelo"] == "M1"
    fila = dict(db._conn.execute("SELECT * FROM ciclos").fetchone())
    assert (fila["serie_original"], fila["modelo_original"]) == ORIG


def test_respaldo_automatizacion_se_reimporta_con_originales(tmp_path):
    db1 = DbManager(tmp_path / "o.db")
    perfil = SimpleNamespace(serial_number="SN000001", model_id="M1",
                             serial_original=ORIG[0], modelo_original=ORIG[1])
    cl, estado, respaldo = _logger_con_perfil(tmp_path, db1, perfil)
    _correr_ciclo(cl, estado)
    cl.detener(5.0)
    db2 = DbManager(tmp_path / "otra.db")
    res = reimportar(respaldo, db2, "interrumpido")
    assert len(res["importados"]) == 1
    fila = dict(db2._conn.execute("SELECT * FROM ciclos").fetchone())
    assert (fila["serie_original"], fila["modelo_original"]) == ORIG


def test_bd_con_version_mayor_no_rompe_lectura_por_nombre(tmp_path):
    ruta = tmp_path / "futura.db"
    db = DbManager(ruta)
    cid = _crear(db, serie_original=ORIG[0], modelo_original=ORIG[1])
    db.close()
    con = sqlite3.connect(ruta)
    con.execute("ALTER TABLE ciclos ADD COLUMN columna_futura TEXT")
    con.execute("PRAGMA user_version = 13")
    con.commit()
    con.close()
    db2 = DbManager(ruta)                     # no migra hacia atrás ni falla
    fila = _fila(db2, cid)
    assert fila["serie"] == "SN000001" and fila["serie_original"] == ORIG[0]
    assert "columna_futura" in fila
    db2.close()
