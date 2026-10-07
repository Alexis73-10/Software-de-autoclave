import sqlite3
from types import SimpleNamespace

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_01, PRE_06


def _db(tmp_path):
    return DbManager(db_path=tmp_path / "t.db")


def _gestor():
    return AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]))


def test_aparicion_resolucion_y_reconocimiento_quedan_en_bd(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am, ciclo_actual=lambda: None)
    am.activar(COM_01)
    am.resolver(COM_01)
    am.reconocer("COM-01", "cristian")
    [fila] = db.get_alarmas_historial()
    assert fila["codigo"] == "COM-01" and fila["nivel"] == "ALARMA"
    assert fila["titulo"] == "Sin comunicación con la tarjeta"
    assert fila["resuelta"] and fila["reconocida_por"] == "cristian"
    assert fila["descripcion_final"] == fila["descripcion_inicial"]


def test_valores_finales_y_reapertura(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am)
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(PRE_06, temp=80.0, maximo=65.0)
    am.resolver(PRE_06)
    [fila] = db.get_alarmas_historial()
    assert "70.0" in fila["descripcion_inicial"] and "80.0" in fila["descripcion_final"]
    assert '"temp": 80.0' in fila["valores_json"]

    am.activar(COM_01)
    am.resolver(COM_01)
    am.activar(COM_01)            # reactivación: misma fila, resuelta vuelve a NULL
    filas = [f for f in db.get_alarmas_historial() if f["codigo"] == "COM-01"]
    assert len(filas) == 1 and filas[0]["resuelta"] is None


def test_ciclo_id_se_toma_al_aparecer(tmp_path):
    db, am = _db(tmp_path), _gestor()
    ciclo_id = db.crear_ciclo(**_args_ciclo())
    HistorialAlarmas(db, am, ciclo_actual=lambda: ciclo_id)
    inst = am.activar(COM_01)
    assert inst.ciclo_id == ciclo_id
    assert db.get_alarmas_historial()[0]["ciclo_id"] == ciclo_id


def test_filtros_y_limite(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am)
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    assert [f["codigo"] for f in db.get_alarmas_historial(nivel="ALARMA")] == ["COM-01"]
    assert len(db.get_alarmas_historial(limite=1)) == 1
    assert db.get_alarmas_historial(desde="2999-01-01T00:00:00") == []


def test_fallo_de_escritura_no_propaga_y_activa_sis02_una_vez(tmp_path):
    class _DbRota:
        def insertar_alarma(self, *a, **k):
            raise sqlite3.OperationalError("disk I/O error")

    am = _gestor()
    HistorialAlarmas(_DbRota(), am)
    am.activar(COM_01)                      # no lanza
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    codigos = [i.codigo for i in am.activas()]
    assert codigos.count("SIS-02") == 1
    sis02 = next(i for i in am.activas() if i.codigo == "SIS-02")
    assert "disk I/O error" in sis02.descripcion


def test_bd_vieja_se_migra(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE ciclos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "numero_ciclo INTEGER, fecha_inicio TEXT)")
    con.commit()
    con.close()
    db = DbManager(db_path=ruta)
    columnas = {r[1] for r in db._conn.execute("PRAGMA table_info(ciclos)")}
    assert "codigo_fallo" in columnas
    assert db.get_alarmas_historial() == []


def _args_ciclo():
    return dict(numero=1, tipo="x", nombre="x", temp_ester=134.0, tiempo_ester=3.5,
                modelo="x", serie="x", version_sw="x")
