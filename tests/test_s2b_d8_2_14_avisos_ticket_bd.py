"""D8-2.14 (tanda 8, Q1-P5): las líneas de aviso del pie del ticket ("Sin datos
de la tarjeta: n s", avisos de uniformidad) se guardan en una columna JSON nueva
de `ciclos` (migración v10) para que la reimpresión sea idéntica al ticket
original. El F0 total ya estaba en `f0_final` y ahora también se reimprime."""

import json
import sqlite3

from unittest.mock import MagicMock

from autoclave.services.domain.logging import db_manager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.ticket_formatter import (
    Presentacion, format_footer, format_ticket)
from tests.test_t8_modo_sin_bd import _correr_ciclo, _logger

_ES = Presentacion(idioma="es")
_AVISO = "Uniformidad termica fuera de rango: Referencia 1 130.2 C"


def _ciclo(**extra):
    base = {"numero_ciclo": 3, "serie": "S", "modelo": "M", "version_sw": "1",
            "nombre_ciclo": "N", "tipo_ciclo": "t", "temp_esterilizacion": 134,
            "tiempo_esterilizacion": 4, "fecha_inicio": "2026-10-22T09:00:00",
            "fecha_fin": "2026-10-22T10:00:00", "resultado": "COMPLETADO",
            "operador": "ana"}
    base.update(extra)
    return base


def _pie(texto: str) -> list[str]:
    lineas = texto.split("\n")
    i = max(k for k, l in enumerate(lineas) if l.startswith("Temp. final"))
    return lineas[i:]


# ── base de datos ───────────────────────────────────────────────────────────

def test_esquema_v10_tiene_la_columna(tmp_path):
    db = DbManager(tmp_path / "t.db")
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION == 11   # v11: U11
    columnas = {r["name"] for r in db._conn.execute("PRAGMA table_info(ciclos)")}
    assert "avisos_ticket" in columnas
    db.close()


def test_base_anterior_migra_y_los_ciclos_viejos_quedan_vacios(tmp_path):
    ruta = tmp_path / "vieja.db"
    db = DbManager(ruta)
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db._conn.execute("ALTER TABLE ciclos DROP COLUMN avisos_ticket")
    db._conn.execute("PRAGMA user_version = 9")
    db._conn.commit()
    db.close()
    db = DbManager(ruta)
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION   # v10 y, desde U11, v11
    assert (db.get_ciclo(i)["avisos_ticket"] or "") == ""
    db.close()


def test_cerrar_ciclo_guarda_los_avisos_en_json(tmp_path):
    db = DbManager(tmp_path / "t.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db.cerrar_ciclo(i, "COMPLETADO", avisos_ticket={"sin_datos_s": 4.0, "avisos": [_AVISO]})
    guardado = json.loads(db.get_ciclo(i)["avisos_ticket"])
    assert guardado == {"sin_datos_s": 4.0, "avisos": [_AVISO]}
    db.close()


def test_cerrar_ciclo_sin_avisos_deja_vacio(tmp_path):
    db = DbManager(tmp_path / "t.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db.cerrar_ciclo(i, "COMPLETADO")
    assert (db.get_ciclo(i)["avisos_ticket"] or "") == ""
    db.close()


def test_reimportar_del_respaldo_conserva_los_avisos(tmp_path):
    db = DbManager(tmp_path / "t.db")
    cierre = {"fecha_fin": "2026-10-22T10:00:00", "resultado": "COMPLETADO",
              "avisos_ticket": {"sin_datos_s": 3.0, "avisos": []}}
    assert db.importar_ciclo_respaldo({"uuid": "u1", "numero": 4}, [], cierre, "x") == "importado"
    fila = db._conn.execute("SELECT avisos_ticket FROM ciclos WHERE uuid='u1'").fetchone()
    assert json.loads(fila["avisos_ticket"]) == {"sin_datos_s": 3.0, "avisos": []}
    db.close()


# ── CycleLogger: base y respaldo ────────────────────────────────────────────

def test_el_logger_pasa_los_avisos_a_la_base_y_al_respaldo(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    estado.sin_datos_tarjeta_s = 4.0
    estado.avisos_ciclo = [_AVISO]
    _correr_ciclo(cl, estado)
    esperado = {"sin_datos_s": 4.0, "avisos": [_AVISO]}
    assert db.cerrar_ciclo.call_args.kwargs["avisos_ticket"] == esperado
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["avisos_ticket"] == esperado


def test_sin_avisos_el_logger_no_pasa_el_argumento(tmp_path):
    """Dobles de base antiguos (sin el parámetro) siguen funcionando."""
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    _correr_ciclo(cl, estado)
    assert "avisos_ticket" not in db.cerrar_ciclo.call_args.kwargs


# ── reimpresión idéntica ────────────────────────────────────────────────────

def test_reimpresion_identica_al_pie_en_vivo():
    en_vivo = format_footer("COMPLETADO", "2026-10-22T10:00:00", temp_final=None,
                            f0_total=15.25, avisos=[_AVISO], operador="ana", p=_ES,
                            sin_datos_s=4.0)
    ciclo = _ciclo(f0_final=15.25,
                   avisos_ticket=json.dumps({"sin_datos_s": 4.0, "avisos": [_AVISO]}))
    assert _pie(format_ticket(ciclo, [], _ES)) == en_vivo.split("\n")


def test_ciclo_viejo_sin_columna_o_vacia_se_reimprime_como_antes():
    for ciclo in (_ciclo(), _ciclo(avisos_ticket=""), _ciclo(avisos_ticket=None)):
        texto = format_ticket(ciclo, [], _ES)
        assert "Sin datos de la tarjeta" not in texto and "Aviso:" not in texto


def test_json_danado_no_rompe_la_reimpresion():
    for basura in ("{", "[1,2]", '{"sin_datos_s": "x", "avisos": 5}', "null"):
        texto = format_ticket(_ciclo(avisos_ticket=basura), [], _ES)
        assert "Estado: COMPLETADO" in texto and "Sin datos de la tarjeta" not in texto


def test_avisos_no_texto_se_descartan():
    ciclo = _ciclo(avisos_ticket=json.dumps({"avisos": [_AVISO, 3, None]}))
    texto = format_ticket(ciclo, [], _ES)
    assert texto.count("Aviso:") == 1


def test_fila_sqlite_real_se_reimprime_con_los_avisos(tmp_path):
    db = DbManager(tmp_path / "t.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db.cerrar_ciclo(i, "FALLO", avisos_ticket={"sin_datos_s": 2.0, "avisos": [_AVISO]})
    texto = format_ticket(db.get_ciclo(i), [], _ES)
    assert "Sin datos de la tarjeta: 2 s" in texto and f"Aviso: {_AVISO}" in texto
    db.close()
