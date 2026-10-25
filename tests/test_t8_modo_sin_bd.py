"""T8 (tanda 2026-10-14): modo sin base de datos (planeacion_arranque_y_modo_sin_bd
§7 y §9; decisiones D-03, D-04, D-06, D-07)."""

import json
import sqlite3
import textwrap
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.ticket_formatter import format_header
from autoclave.state_machine.alarms.catalogo import DEFINICIONES, OPERANDO_SIN_BD
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import fijar_en_backend

UUID = "0f8fad5b-d9cb-469f-a165-70867728950e"


# ── Respaldo JSONL ──────────────────────────────────────────────────────────

def test_respaldo_encabezado_lecturas_y_cierre(tmp_path):
    r = RespaldoCiclos(tmp_path)
    assert r.encabezado(UUID, {"numero": 7, "nombre": "Instrumental"})
    assert r.lectura(UUID, {"fase_codigo": "H", "temp": 120.5})
    assert r.cierre(UUID, {"resultado": "COMPLETADO"})
    datos = r.leer(r.ruta(UUID))
    assert datos["encabezado"]["numero"] == 7 and datos["encabezado"]["uuid"] == UUID
    assert [l["temp"] for l in datos["lecturas"]] == [120.5]
    assert datos["cierre"]["resultado"] == "COMPLETADO"


def test_respaldo_descarta_la_ultima_linea_cortada(tmp_path):
    r = RespaldoCiclos(tmp_path)
    r.encabezado(UUID, {"numero": 1})
    r.lectura(UUID, {"temp": 100.0})
    with open(r.ruta(UUID), "a", encoding="utf-8") as f:
        f.write('{"registro": "lectura", "temp": 1')       # corte de energía
    datos = r.leer(r.ruta(UUID))
    assert len(datos["lecturas"]) == 1 and datos["cierre"] is None


def test_respaldo_que_no_puede_escribir_no_lanza(tmp_path):
    archivo = tmp_path / "no_es_directorio"
    archivo.write_text("x", encoding="utf-8")
    r = RespaldoCiclos(archivo)
    assert r.lectura(UUID, {"temp": 1.0}) is False
    assert r.ultimo_error


def test_respaldo_rechaza_uuid_con_ruta(tmp_path):
    with pytest.raises(ValueError):
        RespaldoCiclos(tmp_path).ruta("../fuera")


# ── Reimportación (idempotente por uuid) ───────────────────────────────────

def _db(tmp_path):
    return dbm.DbManager(tmp_path / "db" / "autoclave.db")


def test_reimporta_un_ciclo_del_respaldo(tmp_path):
    db = _db(tmp_path)
    r = RespaldoCiclos(tmp_path / "respaldo")
    r.encabezado(UUID, {"numero": 41, "tipo": "instrumental", "nombre": "Instrumental 134",
                        "fecha_inicio": "2026-10-15T10:00:00", "operador": "SIN OPERADOR / SIN BD"})
    r.lectura(UUID, {"timestamp_rel": "00:00:01", "fase_codigo": "H", "temp": 121.0,
                     "pres": 210.0, "para_imprimir": True, "temp_principal": 121.0})
    r.cierre(UUID, {"fecha_fin": "2026-10-15T11:00:00", "resultado": "COMPLETADO"})
    res = reimportar(r, db, "interrumpido")
    assert res["importados"] == [UUID]
    [fila] = db.get_ciclos_recientes()
    assert fila["numero_ciclo"] == 41 and fila["resultado"] == "COMPLETADO"
    assert fila["operador"] == "SIN OPERADOR / SIN BD"
    assert len(db.get_lecturas_ciclo(fila["id"])) == 1
    # archivado, no borrado
    assert r.pendientes() == []
    assert (tmp_path / "respaldo" / "importados" / f"{UUID}.jsonl").exists()
    # una segunda copia del mismo uuid no se duplica
    r.encabezado(UUID, {"numero": 41})
    assert reimportar(r, db, "interrumpido")["ya_registrados"] == [UUID]
    assert len(db.get_ciclos_recientes()) == 1


def test_respaldo_sin_cierre_se_importa_interrumpido(tmp_path):
    db = _db(tmp_path)
    r = RespaldoCiclos(tmp_path / "respaldo")
    r.encabezado(UUID, {"numero": 3})
    reimportar(r, db, "Ciclo interrumpido")
    [fila] = db.get_ciclos_recientes()
    assert fila["resultado"] == "INTERRUMPIDO" and fila["motivo_fallo"] == "Ciclo interrumpido"
    assert fila["fecha_fin"]


def test_respaldo_con_error_queda_para_el_proximo_arranque(tmp_path):
    db = MagicMock()
    db.importar_ciclo_respaldo.side_effect = sqlite3.IntegrityError("UNIQUE")
    r = RespaldoCiclos(tmp_path)
    r.encabezado(UUID, {"numero": 3})
    res = reimportar(r, db, "x")
    assert res["errores"] == [f"{UUID}.jsonl"] and len(r.pendientes()) == 1


# ── Base corrupta (§7.7) ───────────────────────────────────────────────────

def test_base_corrupta_se_aparta_y_bloquea_la_creacion(tmp_path):
    ruta = tmp_path / "autoclave.db"
    ruta.write_bytes(b"esto no es sqlite" * 100)
    with pytest.raises(sqlite3.DatabaseError) as e:
        dbm.DbManager(ruta)
    assert dbm.es_base_corrupta(e.value)
    destino = dbm.apartar_base_corrupta(ruta, datetime(2026, 10, 16, 1, 2, 3))
    assert destino.name == "autoclave.db.corrupta-20261016-010203" and destino.exists()
    assert not ruta.exists()
    assert dbm.marca_bd_bloqueada(ruta).exists()
    # no se recrea ni se siembra admin hasta que un técnico quite la marca
    with pytest.raises(dbm.BdBloqueadaError):
        dbm.DbManager(ruta)
    assert not ruta.exists()


def test_bloqueo_transitorio_no_es_corrupcion():
    assert not dbm.es_base_corrupta(sqlite3.OperationalError("database is locked"))
    assert not dbm.es_base_corrupta(OSError("disco"))
    assert dbm.es_base_corrupta(sqlite3.DatabaseError("database disk image is malformed"))


def test_arranque_con_base_corrupta_no_reintenta_y_degrada(monkeypatch, tmp_path):
    import autoclave.backend.context as ctx_mod
    ruta = tmp_path / "autoclave.db"
    ruta.write_bytes(b"x" * 4096)
    llamadas = []

    def abrir():
        llamadas.append(1)
        return dbm.DbManager(ruta)

    monkeypatch.setattr(ctx_mod, "DbManager", abrir)
    monkeypatch.setattr(ctx_mod, "DB_DEFAULT", ruta)
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB", MagicMock())
    ctx = ctx_mod.BackendContext()
    ctx._contador_ciclos = MagicMock()
    assert ctx.abrir_base_datos(3) == "ARR_SIN_BD"
    assert len(llamadas) == 1 and ctx.sin_base_de_datos is True
    assert dbm.marca_bd_bloqueada(ruta).exists()
    assert list(tmp_path.glob("autoclave.db.corrupta-*"))


# ── Alarma (D-03) ──────────────────────────────────────────────────────────

def test_operando_sin_bd_es_alerta_no_bloqueante():
    [d] = [x for x in DEFINICIONES if x.codigo == OPERANDO_SIN_BD]
    assert d.bloquea_inicio is False and d.despeje.value == "MANUAL"


# ── CycleLogger sin base y con la base fallando ────────────────────────────

class _Estado:
    def __init__(self):
        self.maquina = GlobalState.CICLO
        self.fase_ciclo = "CALENTAMIENTO"
        self.sub_estado_ciclo = ""
        self.sensores_temp = {"temp_camara": 121.0}
        self.sensores_pres = {"pres_camara": 210.0}
        self.motivo_fallo = ""
        self.codigo_fallo = ""
        self.f0_acumulado = 0.0
        self.avisos_ciclo = []

    def get_machine_state(self):
        return self.maquina


def _logger(tmp_path, db, sin_bd):
    programa = MagicMock()
    programa.id, programa.name, programa.number = "instrumental", "Instrumental 134", 2
    programa.get_param.side_effect = lambda s, n: {"temperatura_esterilizacion": 134,
                                                   "tiempo_esterilizacion": 4}.get(n)
    programa.instantanea.return_value = {"id": "instrumental"}
    cm = MagicMock()
    cm.get_selected_cycle.return_value = programa
    contador = MagicMock()
    contador.siguiente.return_value = 12
    printer = MagicMock()
    estado = _Estado()
    respaldo = RespaldoCiclos(tmp_path / "respaldo")
    cl = CycleLogger(db, estado, {}, MagicMock(serial_number="S1", model_id="M1"), cm,
                     printer=printer, contador=contador, respaldo=respaldo,
                     sin_base_de_datos=sin_bd)
    return cl, estado, printer, respaldo


def _correr_ciclo(cl, estado):
    cl.update()                       # inicio
    cl.update()                       # primera lectura
    estado.fase_ciclo = "COMPLETADO"
    cl.update()                       # cierre


def test_ciclo_sin_bd_va_al_respaldo_y_al_ticket(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    cl, estado, printer, respaldo = _logger(tmp_path, BdNoDisponible(), sin_bd=True)
    _correr_ciclo(cl, estado)
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "SIN OPERADOR / SIN BD" in impreso and "Ciclo No.: 000012" in impreso
    [ruta] = respaldo.pendientes()
    datos = respaldo.leer(ruta)
    assert datos["encabezado"]["numero"] == 12
    assert datos["encabezado"]["operador"] == "SIN OPERADOR / SIN BD"
    assert len(datos["lecturas"]) >= 2           # lectura del ciclo y la final (E)
    assert datos["cierre"]["resultado"] == "COMPLETADO"
    assert cl.sin_registro is True


def test_base_que_falla_a_mitad_de_ciclo_no_corta_el_registro(tmp_path):
    """BD-02: insertar_lectura/cerrar_ciclo que fallan no suben al tick."""
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    db.insertar_lectura.side_effect = sqlite3.OperationalError("disk I/O error")
    db.cerrar_ciclo.side_effect = sqlite3.OperationalError("disk I/O error")
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    _correr_ciclo(cl, estado)
    datos = respaldo.leer(respaldo.pendientes()[0])
    assert datos["cierre"]["resultado"] == "COMPLETADO"
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "SIN OPERADOR" not in impreso
    db.crear_ciclo.assert_called_once()
    assert db.crear_ciclo.call_args.kwargs["uuid"] == datos["encabezado"]["uuid"]


def test_base_que_falla_al_crear_el_ciclo_sigue_imprimiendo(tmp_path):
    db = MagicMock()
    db.crear_ciclo.side_effect = sqlite3.OperationalError("locked")
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    _correr_ciclo(cl, estado)
    assert cl.sin_registro is True
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"] is not None
    assert printer.enqueue.call_count >= 3      # encabezado, filas y pie


def test_ticket_sin_registro():
    meta = {"numero_ciclo": 1, "fecha_inicio": "2026-10-16T08:00:00"}
    assert "SIN OPERADOR / SIN BD" not in format_header(meta)
    assert "SIN OPERADOR / SIN BD" in format_header({**meta, "sin_registro": True})


# ── BD-03: calibración sin auditoría no queda activa ───────────────────────

def test_calibracion_sin_auditoria_se_revierte(tmp_path):
    from fastapi.testclient import TestClient
    from tests.backend_doble import cabecera, cargar_servidor
    yaml_path = tmp_path / "calibration.yaml"
    original = textwrap.dedent("""
        calibration:
          user:
            temperature:
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
    """)
    yaml_path.write_text(original, encoding="utf-8")
    ctx = MagicMock()
    ctx.db.registrar_auditoria.side_effect = sqlite3.OperationalError("disk I/O error")
    srv, _ = cargar_servidor(ctx)
    fijar_en_backend("CALIBRATION_PATH", yaml_path)
    client = TestClient(srv.app, headers=cabecera(srv, "ingeniero"))
    r = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0})
    assert r.status_code == 503 and r.json()["codigo"] == "auditoria_no_disponible"
    assert yaml_path.read_text(encoding="utf-8") == original
    assert ctx.units.reload_calibration.call_count == 2     # nueva y restaurada


# ── UI: puente y comando de inicio ─────────────────────────────────────────

def test_puente_y_comando_sin_registro():
    import os
    import sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge

    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_flag.return_value = None
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_cycle.return_value = {}
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    status = {"sin_base_de_datos": True}
    ui.get_campo.side_effect = lambda k, d=None: status.get(k, d)
    p = UiBridge(ui, door=1, iniciar=False)
    p.refrescar()
    assert p.sinBaseDatos is True
    ui.connected = False
    p.refrescar()
    assert p.sinBaseDatos is False

    puente = MagicMock(connected=True, listoParaCiclo=True)
    servicio = MagicMock()
    servicio.start_cycle.return_value = True
    c = ComandoIniciarCiclo(puente, servicio, ejecutar=lambda t: t())
    c.iniciarSinRegistro()
    servicio.start_cycle.assert_called_once_with(confirmar_sin_registro=True)
    servicio.start_cycle.reset_mock()
    c.iniciar()
    servicio.start_cycle.assert_called_once_with()


def test_start_cycle_envia_la_confirmacion():
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    assert ui.start_cycle(confirmar_sin_registro=True) is True
    ui.backend.post.assert_called_once_with(path="/cycle/start",
                                            body={"confirmar_sin_registro": True})


# ── Correcciones de los revisores de T8 ────────────────────────────────────

def test_saf02_completa_un_ciclo_que_quedo_incompleto_en_la_base(tmp_path):
    """La base falló a mitad de ciclo: la fila existe sin fin ni todas las
    lecturas; el respaldo la completa en vez de archivarse sin más."""
    db = _db(tmp_path)
    cid = db.crear_ciclo(numero=9, tipo="t", nombre="n", temp_ester=134, tiempo_ester=4,
                         modelo="m", serie="s", version_sw="v", uuid=UUID)
    l1 = {"timestamp_rel": "00:00:00", "timestamp_abs": "2026-10-16T08:00:00",
          "fase_codigo": "PH", "temp": 100.0, "pres": 101.0, "para_imprimir": True}
    db.insertar_lectura(ciclo_id=cid, temp_principal=None,
                        **{k: v for k, v in l1.items()})
    r = RespaldoCiclos(tmp_path / "respaldo")
    r.encabezado(UUID, {"numero": 9})
    r.lectura(UUID, l1)
    r.lectura(UUID, {**l1, "timestamp_rel": "00:03:00",
                     "timestamp_abs": "2026-10-16T08:03:00", "fase_codigo": "S"})
    r.cierre(UUID, {"fecha_fin": "2026-10-16T09:00:00", "resultado": "FALLO",
                    "motivo": "presión baja", "codigo": "FALLO_PRES_BAJA"})
    res = reimportar(r, db, "interrumpido")
    assert res["completados"] == [UUID]
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO" and fila["codigo_fallo"] == "FALLO_PRES_BAJA"
    assert len(db.get_lecturas_ciclo(cid)) == 2
    assert db.cerrar_ciclos_interrumpidos("x") == []


def test_saf02_una_fila_cerrada_conserva_su_resultado(tmp_path):
    db = _db(tmp_path)
    cid = db.crear_ciclo(numero=9, tipo="t", nombre="n", temp_ester=134, tiempo_ester=4,
                         modelo="m", serie="s", version_sw="v", uuid=UUID)
    db.cerrar_ciclo(cid, "COMPLETADO")
    r = RespaldoCiclos(tmp_path / "respaldo")
    r.encabezado(UUID, {"numero": 9})
    r.cierre(UUID, {"resultado": "FALLO"})
    assert reimportar(r, db, "x")["ya_registrados"] == [UUID]
    assert db.get_ciclo(cid)["resultado"] == "COMPLETADO"


def test_saf01_respaldo_que_falla_avisa(tmp_path):
    archivo = tmp_path / "no_es_directorio"
    archivo.write_text("x", encoding="utf-8")
    avisos = []
    r = RespaldoCiclos(archivo, al_fallar=avisos.append)
    assert r.probar_escritura() is not None
    r.lectura(UUID, {"temp": 1.0})
    assert len(avisos) == 1
    assert RespaldoCiclos(tmp_path / "ok").probar_escritura() is None
    assert not list((tmp_path / "ok").iterdir())        # la prueba no deja archivos


def test_saf01_alarma_sis03_desde_el_contexto():
    import autoclave.backend.context as ctx_mod
    ctx = ctx_mod.BackendContext()
    ctx._respaldo_fallido("No space left on device")
    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "SIS-03" and alarma.definicion.bloquea_inicio is False


def test_saf05_calibracion_sin_bd_no_toca_el_archivo(tmp_path):
    from fastapi.testclient import TestClient
    from tests.backend_doble import cabecera, cargar_servidor
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text("calibration: {}" + chr(10), encoding="utf-8")
    ctx = MagicMock()
    ctx.sin_base_de_datos = True
    srv, _ = cargar_servidor(ctx)
    fijar_en_backend("CALIBRATION_PATH", yaml_path)
    client = TestClient(srv.app, headers=cabecera(srv, "ingeniero"))
    r = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0})
    assert r.status_code == 503
    ctx.units.reload_calibration.assert_not_called()


def test_tmg01_la_base_se_escribe_fuera_del_tick(tmp_path):
    """Con un ejecutor diferido, el tick no llama a la base; el cortacircuito
    deja de escribir tras el primer error."""
    pendientes = []
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    db.insertar_lectura.side_effect = sqlite3.OperationalError("locked")
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    cl._ejecutar_bd = pendientes.append
    _correr_ciclo(cl, estado)
    db.crear_ciclo.assert_not_called()          # nada en el hilo del lazo
    for tarea in pendientes:
        tarea()
    db.crear_ciclo.assert_called_once()
    assert db.insertar_lectura.call_count == 1  # cortacircuito tras el primer error
    db.cerrar_ciclo.assert_not_called()
    assert cl.sin_registro is True
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["resultado"] == "COMPLETADO"


def test_escritor_bd_ejecuta_en_orden_y_se_detiene():
    from autoclave.services.domain.logging.cycle_logger import EscritorBD
    hechos = []
    e = EscritorBD()
    for i in range(5):
        e(lambda i=i: hechos.append(i))
    e.detener(2.0)
    assert hechos == [0, 1, 2, 3, 4]
