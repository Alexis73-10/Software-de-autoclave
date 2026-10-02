# tests/test_simulador_repeticion.py
#
# Simulador de ciclo para probar la UI sin tarjeta (autoclave.simulador):
# reproducción de un ciclo COMPLETADO guardado en la BD (solo lectura).

import sqlite3

import pytest

from autoclave.simulador.repeticion import Repeticion, cargar_ciclo


def _bd(tmp_path, ciclos):
    """ciclos: [(id, tipo, resultado, [(rel, codigo, temp, pres), ...])]"""
    ruta = tmp_path / "a.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE ciclos (id INTEGER PRIMARY KEY, numero_ciclo INTEGER, tipo_ciclo TEXT,"
                " nombre_ciclo TEXT, resultado TEXT)")
    con.execute("CREATE TABLE lecturas (id INTEGER PRIMARY KEY AUTOINCREMENT, ciclo_id INTEGER,"
                " timestamp_rel TEXT, fase_codigo TEXT, temp_camara REAL, pres_camara REAL)")
    for cid, tipo, res, lecturas in ciclos:
        con.execute("INSERT INTO ciclos VALUES (?,?,?,?,?)", (cid, cid, tipo, tipo, res))
        for rel, cod, t, p in lecturas:
            con.execute("INSERT INTO lecturas (ciclo_id, timestamp_rel, fase_codigo, temp_camara, pres_camara)"
                        " VALUES (?,?,?,?,?)", (cid, rel, cod, t, p))
    con.commit()
    con.close()
    return ruta


_LECTURAS = [
    ("00:00:00", "PG", 30.0, 80.0),
    ("00:00:01", "PV", 31.0, 81.0),
    ("00:10:00", "PV", 100.0, 140.0),
    ("00:10:01", "H", 100.0, 140.0),
    ("00:12:00", "H", 121.0, 210.0),
    ("00:12:01", "S", 121.0, 210.0),
    ("00:27:00", "S", 122.0, 214.0),
    ("00:27:01", " ", 122.0, 214.0),
    ("00:37:00", "E", 60.0, 10.0),
    ("00:41:00", "E", 55.0, 70.0),   # tras la confirmación: no es parte del ciclo
] + [(f"00:{15 + i:02d}:00", "S", 121.5, 212.0) for i in range(12)]


def test_cargar_elige_el_ultimo_completado_con_lecturas_suficientes(tmp_path):
    ruta = _bd(tmp_path, [
        (1, "instrumental_121", "COMPLETADO", _LECTURAS),
        (2, "bowe_dick", "COMPLETADO", _LECTURAS[:5]),      # pocas lecturas
        (3, "instrumental_134", "CANCELADO", _LECTURAS),
    ])
    ciclo = cargar_ciclo(ruta)
    assert ciclo["id"] == 1 and ciclo["tipo_ciclo"] == "instrumental_121"


def test_cargar_ciclo_indicado(tmp_path):
    ruta = _bd(tmp_path, [(1, "a", "COMPLETADO", _LECTURAS), (2, "b", "COMPLETADO", _LECTURAS)])
    assert cargar_ciclo(ruta, ciclo_id=2)["id"] == 2


def test_cargar_no_modifica_la_bd(tmp_path):
    ruta = _bd(tmp_path, [(1, "a", "COMPLETADO", _LECTURAS)])
    antes = ruta.read_bytes()
    cargar_ciclo(ruta)
    assert ruta.read_bytes() == antes


def test_cargar_sin_ciclos_utiles_falla_claro(tmp_path):
    ruta = _bd(tmp_path, [(1, "a", "CANCELADO", _LECTURAS)])
    with pytest.raises(LookupError):
        cargar_ciclo(ruta)


def _rep(tmp_path):
    return Repeticion(cargar_ciclo(_bd(tmp_path, [(1, "a", "COMPLETADO", _LECTURAS)])))


def test_duracion_termina_en_la_primera_lectura_e(tmp_path):
    assert _rep(tmp_path).duracion_s == 37 * 60


def test_tramos_de_fase(tmp_path):
    rep = _rep(tmp_path)
    fases = [f for f, _, _ in rep.tramos]
    # PURGA ya no existe: su tramo inicial se cuenta como prevacío
    assert fases == ["PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO"]
    inicio = {f: (a, b) for f, a, b in rep.tramos}
    assert inicio["PRE_VACIO"] == (0, 601)
    assert inicio["CALENTAMIENTO"] == (601, 721)
    assert inicio["ESTERILIZACION"] == (721, 1621)
    # descompresión hasta que la presión cruza la atmosférica (101.3 kPa), luego secado
    d0, d1 = inicio["DESCOMPRESION"]
    assert d0 == 1621
    assert inicio["SECADO"] == (d1, 37 * 60)
    assert 1621 < d1 < 37 * 60


def test_muestra_interpola_entre_lecturas(tmp_path):
    rep = _rep(tmp_path)
    m = rep.muestra(5 * 60 + 0.5)            # mitad entre 00:00:01 y 00:10:00
    assert m["fase"] == "PRE_VACIO"
    assert m["temp_camara"] == pytest.approx(65.5, abs=0.2)
    assert m["pres_camara"] == pytest.approx(110.5, abs=0.2)


def test_muestra_temp_ref_simulada_sigue_a_la_camara_con_retraso(tmp_path):
    rep = _rep(tmp_path)
    t = 11 * 60
    assert rep.muestra(t)["temp_ref"] == pytest.approx(rep.muestra(t - 20)["temp_camara"])


def test_muestra_fuera_de_rango_se_recorta(tmp_path):
    rep = _rep(tmp_path)
    assert rep.muestra(-5)["temp_camara"] == 30.0
    assert rep.muestra(10 ** 6)["fase"] == "SECADO"
