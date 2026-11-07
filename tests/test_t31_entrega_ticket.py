# tests/test_t31_entrega_ticket.py
#
# Tanda 31 (ENT-06/07/08/10/11, planeacion_entrega_camara_fin_ciclo.md): el
# CycleLogger separa el resultado del ciclo de su cierre. En el resultado: fila
# «E», «Error de ciclo» y «F0 total» (si no es COMPLETADO), base y respaldo con
# fecha_resultado, sin pie ni fecha_fin. Durante la espera: filas «E» cada
# intervalo_impresion. En la entrega (o confirmación forzada / tras paro): fila
# final «E», pie con la hora de la entrega, fecha_fin y cierre del respaldo.
# Corte de energía durante la espera: conserva el resultado, fecha_fin del
# arranque y aviso; cuenta como ciclo interrumpido.

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.ticket_formatter import (
    CLAVE_ENTREGA_NO_REGISTRADA, format_ticket)
from autoclave.state_machine.machine.enum_global import GlobalState

MOTIVO_INT = "Ciclo interrumpido: corte"


class _Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class _Estado:
    def __init__(self):
        self.maquina = GlobalState.CICLO
        self.fase_ciclo = "ESTERILIZACION"
        self.sub_estado_ciclo = ""
        self.sensores_temp = {"temp_camara": 134.0}
        self.sensores_pres = {"pres_camara": 304.0}
        self.motivo_fallo = ""
        self.codigo_fallo = ""
        self.valores_fallo = None
        self.f0_acumulado = 0.0
        self.avisos_ciclo = []

    def get_machine_state(self):
        return self.maquina


class _Programa:
    id, name, number = "instrumental_134", "Instrumental 134", 2

    def __init__(self, f0=False):
        self._f0 = f0

    def get_param(self, seccion, nombre, default=None):
        return {("esterilizacion", "temperatura_esterilizacion"): 134,
                ("esterilizacion", "tiempo_esterilizacion"): 4,
                ("globals", "F0"): self._f0,
                ("globals", "F0_objetivo"): 12}.get((seccion, nombre), default)

    def instantanea(self):
        return {"id": self.id, "parameters": {"globals": {"F0_objetivo": {"value": 12}}}}


class _Impresora:
    def __init__(self):
        self.trozos = []

    def enqueue(self, texto):
        self.trozos.append(texto)

    def texto(self):
        return "\n".join(self.trozos)

    def filas(self):
        return [t for t in self.trozos if len(t) > 2 and t[1] == " " and t[0].isalpha()
                and "\n" not in t]


def _entorno(tmp_path, f0=False, db=None):
    from autoclave.installation.equipment import EquipmentClass
    db = db if db is not None else DbManager(tmp_path / "a.db")
    estado = _Estado()
    reloj = _Reloj()
    impresora = _Impresora()
    respaldo = RespaldoCiclos(tmp_path / "respaldo")
    perfil = SimpleNamespace(serial_number="S1", model_id="M1",
                             equipment_class=EquipmentClass.PISO_LAB)
    programa = _Programa(f0=f0)
    cl = CycleLogger(db, estado, {"intervalo_impresion": 180,
                                  "intervalo_impresion_esterilizacion": 99999},
                     perfil, SimpleNamespace(get_selected_cycle=lambda: programa),
                     printer=impresora, reloj_mono=reloj, respaldo=respaldo)
    return cl, db, estado, reloj, impresora, respaldo


def _avanzar(cl, reloj, segundos, paso=1.0):
    for _ in range(int(segundos / paso)):
        reloj.t += paso
        cl.update()


def _fallo_presurizado(cl, estado, reloj):
    cl.update()                                  # inicio
    cl.update()                                  # fila S
    _avanzar(cl, reloj, 10)
    estado.fase_ciclo = "FALLO_ESTERILIZACION"
    estado.codigo_fallo = "CIC-03"
    estado.motivo_fallo = "CIC-03 · x"
    estado.f0_acumulado = 7.25
    cl.update()                                  # resultado


# ── ENT-06: fallo con la cámara presurizada ────────────────────────────────

def test_fallo_resultado_sin_pie_filas_periodicas_y_pie_en_la_entrega(tmp_path):
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path, f0=True)
    _fallo_presurizado(cl, estado, reloj)
    cid = cl.ciclo_id
    # resultado: fila E + «Error de ciclo» + «F0 total», sin pie
    assert imp.trozos[-2].startswith("E ")
    assert imp.trozos[-1].split("\n") == ["Error de ciclo: CIC-03 - " + imp.trozos[-1]
                                          .split("CIC-03 - ", 1)[1].split("\n")[0],
                                          "F0 total: 7.2 min"]
    assert "Hora fin" not in imp.texto()
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["codigo_fallo"] == "CIC-03"
    assert fila["fecha_resultado"] and fila["fecha_fin"] is None
    assert fila["f0_final"] == pytest.approx(7.25)
    datos = respaldo.leer(respaldo.pendientes()[0])
    assert datos["resultado"]["resultado"] == "FALLO_ESTERILIZACION"
    assert datos["resultado"]["fecha_resultado"] == fila["fecha_resultado"]
    assert datos["cierre"] is None
    assert cl.activo and cl.ciclo_id == cid

    # espera: el F0 ya no cambia el ticket; fila E cada 180 s (también base)
    estado.f0_acumulado = 99.0
    n = len(imp.filas())
    _avanzar(cl, reloj, 179)
    assert len(imp.filas()) == n
    _avanzar(cl, reloj, 1)
    assert len(imp.filas()) == n + 1
    estado.sensores_temp["temp_camara"] = 96.7
    estado.sensores_pres["pres_camara"] = 101.0
    _avanzar(cl, reloj, 180)
    assert imp.filas()[-1].startswith("E 00:06:10 0096.7 0101.0")
    assert "Hora fin" not in imp.texto()

    # entrega: fila final E + pie con la hora de la entrega
    estado.sensores_temp["temp_camara"] = 70.0
    _avanzar(cl, reloj, 30)
    antes = datetime.now().replace(microsecond=0)
    estado.entrega_camara = {"entregada": True, "motivos": [], "espera_restante_s": None,
                             "forzable": False}
    cl.update()
    pie = imp.trozos[-1]
    assert imp.trozos[-2].startswith("E 00:06:40 0070.0")
    assert "Temp. final: 70 C" in pie and "Estado: FALLO_ESTERILIZACION" in pie
    assert "Motivo: CIC-03 - " in pie and "F0 total: 7.2 min" in pie
    hora = datetime.strptime(pie.split("Hora fin: ")[1][:8], "%H:%M:%S").time()
    assert hora >= antes.time()
    fila = db.get_ciclo(cid)
    assert fila["fecha_fin"] >= fila["fecha_resultado"]
    assert pie.split("Hora fin: ")[1][:8] == fila["fecha_fin"][11:19]
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["fecha_fin"] == fila["fecha_fin"]
    # ENT-10: el reloj se congela en la entrega
    assert cl.transcurrido_s() == 400.0
    _avanzar(cl, reloj, 20)
    assert cl.transcurrido_s() == 400.0
    assert not cl.activo
    assert imp.trozos[-1] == pie                 # nada más al ticket

    # la reimpresión es idéntica a lo impreso (filas E y «Error de ciclo»)
    lecturas = [dict(r) for r in db.get_lecturas_para_imprimir(cid)]
    reimpreso = format_ticket(dict(fila), lecturas)
    assert reimpreso.split("\n")[13:] == imp.texto().split("\n")[13:]
    assert reimpreso.count("Error de ciclo") == 1


def test_cancelacion_registra_resultado_y_espera(tmp_path):
    cl, db, estado, reloj, imp, _ = _entorno(tmp_path)
    cl.update()
    cl.update()
    estado.fase_ciclo = "CANCELADO"
    estado.cancelado_por = "ana"
    cl.update()
    assert imp.trozos[-1] == "Error de ciclo: CANCELADO"
    fila = db.get_ciclo(cl.ciclo_id)
    assert fila["resultado"] == "CANCELADO" and fila["fecha_fin"] is None
    estado.entrega_camara = {"entregada": True}
    cl.update()
    assert "Cancelado por: ana" in imp.trozos[-1]
    assert db.get_ciclo(fila["id"])["fecha_fin"] is not None


def test_completado_espera_filas_e_y_pie_sin_error_de_ciclo(tmp_path):
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    cl.update()
    cl.update()
    estado.fase_ciclo = "COMPLETADO"
    cl.update()
    assert imp.trozos[-1].startswith("E ")      # sin «Error de ciclo»
    _avanzar(cl, reloj, 180)
    assert imp.trozos[-1].startswith("E 00:03:00")
    assert db.get_ciclo(cl.ciclo_id)["fecha_fin"] is None
    estado.entrega_camara = {"entregada": True}
    cl.update()
    assert "Estado: COMPLETADO" in imp.trozos[-1]
    assert "Error de ciclo" not in imp.texto()
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["resultado"] == "COMPLETADO"


def test_entrega_en_el_mismo_tick_del_resultado_sin_fila_duplicada(tmp_path):
    cl, db, estado, reloj, imp, _ = _entorno(tmp_path)
    cl.update()
    cl.update()
    estado.fase_ciclo = "COMPLETADO"
    estado.entrega_camara = {"entregada": True}
    cl.update()
    assert [t[0] for t in imp.filas()].count("E") == 1
    assert "Hora fin" in imp.trozos[-1]


@pytest.mark.parametrize("entrega", [None, {"entregada": False}, {"entregada": 1},
                                     MagicMock(), "si"])
def test_sin_entrega_valida_no_se_cierra(tmp_path, entrega):
    cl, db, estado, reloj, imp, _ = _entorno(tmp_path)
    cl.update()
    cl.update()
    estado.fase_ciclo = "COMPLETADO"
    estado.entrega_camara = entrega
    _avanzar(cl, reloj, 5)
    assert "Hora fin" not in imp.texto() and cl.activo


# ── ENT-04/05: confirmación forzada y tras paro ────────────────────────────

def test_confirmacion_forzada_lleva_la_linea_al_pie_y_a_la_base(tmp_path):
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    cid = cl.ciclo_id
    _avanzar(cl, reloj, 30)
    estado.confirmacion_forzada = {"usuario": "ing1", "motivo": "Temperatura 105 C, máximo 80 C"}
    estado.maquina = GlobalState.PREPARACION       # CICLO_CONFIRMADO
    cl.update()
    pie = imp.trozos[-1]
    assert ("Confirmado sin condiciones seguras por ing1: Temperatura 105 C, máximo 80 C"
            in pie)
    assert imp.trozos[-2].startswith("E 00:00:40")
    avisos = json.loads(db.get_ciclo(cid)["avisos_ticket"])["avisos"]
    assert {"clave": "ticket_ciclo.confirmado_forzado", "usuario": "ing1",
            "motivo": "Temperatura 105 C, máximo 80 C"} in avisos
    lecturas = [dict(r) for r in db.get_lecturas_para_imprimir(cid)]
    assert "Confirmado sin condiciones seguras por ing1" in format_ticket(
        dict(db.get_ciclo(cid)), lecturas)
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["avisos_ticket"]["avisos"] == avisos


def test_confirmacion_tras_paro_lleva_su_linea(tmp_path):
    cl, db, estado, reloj, imp, _ = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    estado.confirmado_tras_paro = True
    estado.maquina = GlobalState.PREPARADO
    cl.update()
    assert "Confirmado tras paro de emergencia, cámara sin verificar" in imp.trozos[-1]


def test_lineas_de_aviso_en_ingles():
    from autoclave.services.domain.logging.ticket_formatter import (
        CLAVE_CONFIRMADO_FORZADO, CLAVE_CONFIRMADO_TRAS_PARO, Presentacion, _linea_aviso,
        lineas_resultado)
    p = Presentacion(idioma="en")
    assert _linea_aviso({"clave": CLAVE_CONFIRMADO_FORZADO, "usuario": "u", "motivo": "m"},
                        p) == "Confirmed without safe conditions by u: m"
    assert _linea_aviso({"clave": CLAVE_CONFIRMADO_TRAS_PARO}, p).startswith("Confirmed after")
    assert _linea_aviso({"clave": CLAVE_ENTREGA_NO_REGISTRADA}, p) == (
        "Chamber release not recorded (power outage)")
    assert lineas_resultado("FALLO_X", "CIC-03 - t", 1.0, p) == ["Cycle error: CIC-03 - t",
                                                                 "F0 total: 1.0 min"]
    assert lineas_resultado("COMPLETADO", None, 1.0, p) == []


# ── ENT-07: base, migración y corte de energía ─────────────────────────────

def test_migracion_v14_agrega_fecha_resultado_idempotente(tmp_path, monkeypatch):
    ruta = tmp_path / "v.db"
    with monkeypatch.context() as m:
        m.setattr(dbm, "_MIGRACIONES", tuple(x for x in dbm._MIGRACIONES if x[0] <= 13))
        db = DbManager(db_path=ruta)
        assert db.get_version_esquema() == 13
        i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                           modelo="M", serie="S", version_sw="1")
        db.cerrar_ciclo(i, "COMPLETADO")
        db.close()
    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == dbm.ESQUEMA_VERSION == 14
    fila = db.get_ciclo(i)
    assert fila["fecha_resultado"] is None and fila["resultado"] == "COMPLETADO"
    db.close()
    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == 14
    db.close()


def test_corte_en_la_espera_conserva_resultado_y_cuenta_como_interrumpido(tmp_path):
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    _avanzar(cl, reloj, 180)
    cid = cl.ciclo_id
    # otro ciclo sin resultado (formato anterior): sigue a INTERRUMPIDO
    j = db.crear_ciclo(numero=99, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    # «corte»: el arranque cierra los ciclos sin fecha_fin
    cerrados = db.cerrar_ciclos_interrumpidos(MOTIVO_INT)
    assert [f["id"] for f in cerrados] == [cid, j]
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"] is not None
    assert fila["codigo_fallo"] == "CIC-03"
    avisos = json.loads(fila["avisos_ticket"])["avisos"]
    assert {"clave": CLAVE_ENTREGA_NO_REGISTRADA} in avisos
    assert db.get_ciclo(j)["resultado"] == "INTERRUMPIDO"
    # la reimpresión lleva las filas E, «Error de ciclo» y el aviso
    lecturas = [dict(r) for r in db.get_lecturas_para_imprimir(cid)]
    texto = format_ticket(dict(fila), lecturas)
    assert "Entrega de la cámara no registrada (corte de energía)" in texto
    assert texto.count("Error de ciclo") == 1
    assert [r["fase_codigo"] for r in lecturas][-2:] == ["E", "E"]
    # el respaldo sin cierre ya está en la base: no se vuelve a contar
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert r["interrumpidos"] == []
    assert db.cerrar_ciclos_interrumpidos(MOTIVO_INT) == []


def test_reimportar_respaldo_con_resultado_sin_cierre(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    cl, _, estado, reloj, imp, respaldo = _entorno(tmp_path, f0=True, db=BdNoDisponible())
    cl.sin_base_de_datos = True
    cl.contador = MagicMock()
    cl.contador.siguiente.return_value = 12
    _fallo_presurizado(cl, estado, reloj)
    _avanzar(cl, reloj, 180)
    db = DbManager(tmp_path / "b.db")
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert len(r["importados"]) == 1 and r["interrumpidos"] == r["importados"]
    fila = db._conn.execute("SELECT * FROM ciclos").fetchone()
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"]
    assert fila["fecha_resultado"] and fila["f0_final"] == pytest.approx(7.25)
    assert {"clave": CLAVE_ENTREGA_NO_REGISTRADA} in json.loads(fila["avisos_ticket"])["avisos"]
    db.close()


def test_completar_desde_respaldo_con_resultado_sin_cierre(tmp_path):
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    cid = cl.ciclo_id
    # la base perdió el resultado (p. ej. falló justo antes): fila sin él
    db._conn.execute("UPDATE ciclos SET resultado=NULL, fecha_resultado=NULL WHERE id=?",
                     (cid,))
    db._conn.execute("DELETE FROM lecturas WHERE ciclo_id=? AND fase_codigo='E'", (cid,))
    db._conn.commit()
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert r["completados"] and r["interrumpidos"] == r["completados"]
    fila = db.get_ciclo(cid)
    # M1 (revisión tanda 31): el resultado se aplica, la fila no se cierra aquí
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"] is None
    assert fila["fecha_resultado"]
    assert [f["id"] for f in db.cerrar_ciclos_interrumpidos(MOTIVO_INT)] == [cid]
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"]


def test_respaldo_completo_conserva_fecha_resultado_al_importar(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    cl, _, estado, reloj, imp, respaldo = _entorno(tmp_path, db=BdNoDisponible())
    cl.sin_base_de_datos = True
    cl.contador = MagicMock()
    cl.contador.siguiente.return_value = 12
    _fallo_presurizado(cl, estado, reloj)
    estado.entrega_camara = {"entregada": True}
    cl.update()
    db = DbManager(tmp_path / "b.db")
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert r["importados"] and r["interrumpidos"] == []
    fila = db._conn.execute("SELECT * FROM ciclos").fetchone()
    assert fila["fecha_resultado"] and fila["fecha_fin"] >= fila["fecha_resultado"]
    assert "avisos_ticket" not in fila.keys() or CLAVE_ENTREGA_NO_REGISTRADA not in (
        fila["avisos_ticket"] or "")
    db.close()


def test_respaldo_anterior_sin_registro_resultado_sigue_igual(tmp_path):
    respaldo = RespaldoCiclos(tmp_path / "r")
    respaldo.encabezado("abc12345", {"numero": 3, "fecha_inicio": "2026-11-01T10:00:00"})
    respaldo.lectura("abc12345", {"timestamp_rel": "00:00:00", "fase_codigo": "S"})
    db = DbManager(tmp_path / "c.db")
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert r["interrumpidos"] == ["abc12345"]
    fila = db._conn.execute("SELECT * FROM ciclos").fetchone()
    assert fila["resultado"] == "INTERRUMPIDO" and fila["fecha_resultado"] is None
    db.close()


# ── ENT-07: duración y ciclos no cerrados ──────────────────────────────────

def test_duracion_va_de_inicio_a_fecha_fin_de_la_entrega(tmp_path):
    from autoclave.services.domain.reportes import dashboard
    db = DbManager(tmp_path / "d.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db._conn.execute("UPDATE ciclos SET fecha_inicio='2026-11-07T08:00:00' WHERE id=?", (i,))
    db.registrar_resultado(i, "COMPLETADO", fecha_resultado="2026-11-07T08:40:00")
    db.cerrar_ciclo(i, "COMPLETADO", fecha_fin="2026-11-07T09:00:00")
    filas = db.get_ciclos_periodo("2026-11-07T00:00:00", "2026-11-08T00:00:00")
    assert dashboard.duracion_media(filas) == (3600.0, 0)
    fila = db.get_ciclo(i)
    assert fila["fecha_resultado"] == "2026-11-07T08:40:00"
    db.close()


def test_ciclo_con_resultado_sin_entrega_no_cuenta_como_terminado_hoy(tmp_path):
    db = DbManager(tmp_path / "e.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db.registrar_resultado(i, "FALLO_X", "m", "CIC-03")
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    assert db.get_resumen_ciclos(hoy)["hoy"] == 0
    assert db.get_ciclos_desde(hoy, terminados=True, limite=10) == []
    db.cerrar_ciclo(i, "FALLO_X", "m", "CIC-03")
    assert db.get_resumen_ciclos(hoy)["hoy"] == 1
    db.close()


# ── ENT-11: acciones de Historial sobre un ciclo sin fecha_fin ─────────────

def test_pdf_de_un_ciclo_sin_fecha_fin_no_se_genera():
    from autoclave.ui_qml.bridge import acciones_ciclos as ac
    acciones = ac.AccionesCiclos.__new__(ac.AccionesCiclos)
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, **k: ({"ciclo": {"id": 1, "numero_ciclo": 1,
                                                            "fecha_fin": None},
                                                  "lecturas": []}
                                                 if ruta.endswith("/ticket") else {"lecturas": []})
    acciones._backend = backend
    with pytest.raises(ac._ErrorConMensaje):
        acciones._datos_ciclo(1)


# ── ENT-08: el F0 no se acumula tras el resultado ──────────────────────────

@pytest.mark.parametrize("fase", ["FALLO_ESTERILIZACION", "CANCELADO", "COMPLETADO",
                                  "EMERGENCIA", "SENSOR_AUSENTE"])
def test_f0_no_se_acumula_despues_del_resultado(fase):
    from tests.test_control_loop_f0 import _make_loop
    loop, estado, _ = _make_loop()
    estado.fase_ciclo = "ESTERILIZACION"
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    acumulado = estado.f0_acumulado
    assert acumulado > 0.0
    estado.fase_ciclo = fase                       # resultado; sigue en CICLO
    for k in range(1, 6):
        loop._acumular_f0(now=1060.0 + 60.0 * k)
    assert estado.f0_acumulado == acumulado


def test_corte_en_la_espera_orden_del_arranque_reimportar_y_luego_cerrar(tmp_path):
    """Orden real del arranque (context._numeracion_y_ciclos_interrumpidos):
    primero la reimportación del respaldo, luego el cierre de los ciclos sin
    fecha_fin. El ciclo con resultado sin entrega conserva su resultado, recibe
    el aviso una sola vez y cuenta como interrumpido (A9-R3)."""
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    _avanzar(cl, reloj, 200)
    cid = cl.ciclo_id
    r = reimportar(respaldo, db, MOTIVO_INT)
    assert r["interrumpidos"] == r["completados"] and len(r["completados"]) == 1
    # M1: la fila la cierra cerrar_ciclos_interrumpidos, no la reimportación
    assert [f["id"] for f in db.cerrar_ciclos_interrumpidos(MOTIVO_INT)] == [cid]
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"]
    avisos = json.loads(fila["avisos_ticket"])["avisos"]
    assert avisos.count({"clave": CLAVE_ENTREGA_NO_REGISTRADA}) == 1


def _contexto_arranque(db, respaldo, monkeypatch):
    from autoclave.backend.context import BackendContext
    contador = MagicMock()
    contador.en_curso.return_value = None
    monkeypatch.setattr(BackendContext, "contador_ciclos", property(lambda self: contador))
    ctx = BackendContext()
    ctx.db = db
    ctx._respaldo_ciclos = respaldo
    ctx.sin_base_de_datos = False
    return ctx


def test_m1_arranque_con_base_y_respaldo_cierra_como_interrumpido(tmp_path, monkeypatch):
    """M1 (revisión tanda 31): corte en la espera con base Y respaldo sanos.
    El arranque real (reimportar y luego cerrar) audita ciclo_interrumpido,
    agrega el aviso una vez, deja la fila en _ciclo_interrumpido y
    hubo_ciclo_interrumpido() es True."""
    cl, db, estado, reloj, imp, respaldo = _entorno(tmp_path)
    _fallo_presurizado(cl, estado, reloj)
    _avanzar(cl, reloj, 200)
    cid = cl.ciclo_id
    ctx = _contexto_arranque(db, respaldo, monkeypatch)
    ctx._numeracion_y_ciclos_interrumpidos()
    fila = db.get_ciclo(cid)
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"]
    avisos = json.loads(fila["avisos_ticket"])["avisos"]
    assert avisos.count({"clave": CLAVE_ENTREGA_NO_REGISTRADA}) == 1
    eventos = [r[0] for r in db._conn.execute(
        "SELECT evento FROM audit_log WHERE entidad=?", (f"ciclo/{cid}",)).fetchall()]
    assert "ciclo_interrumpido" in eventos
    assert ctx._ciclo_interrumpido is not None and ctx._ciclo_interrumpido["id"] == cid
    assert ctx.hubo_ciclo_interrumpido() is True
    assert "Entrega de la cámara no registrada (corte de energía)" in format_ticket(
        dict(fila), [dict(x) for x in db.get_lecturas_para_imprimir(cid)])


def test_m1_arranque_solo_respaldo_importa_cerrado_con_aviso(tmp_path, monkeypatch):
    """Base perdida (sin fila): el ciclo importado se cierra con la fecha de
    la importación y el aviso; el arranque lo cuenta como interrumpido."""
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    cl, _, estado, reloj, imp, respaldo = _entorno(tmp_path, db=BdNoDisponible())
    cl.sin_base_de_datos = True
    cl.contador = MagicMock()
    cl.contador.siguiente.return_value = 12
    _fallo_presurizado(cl, estado, reloj)
    _avanzar(cl, reloj, 180)
    db = DbManager(tmp_path / "b.db")
    ctx = _contexto_arranque(db, respaldo, monkeypatch)
    ctx._numeracion_y_ciclos_interrumpidos()
    fila = db._conn.execute("SELECT * FROM ciclos").fetchone()
    assert fila["resultado"] == "FALLO_ESTERILIZACION" and fila["fecha_fin"]
    assert {"clave": CLAVE_ENTREGA_NO_REGISTRADA} in json.loads(fila["avisos_ticket"])["avisos"]
    assert ctx.hubo_ciclo_interrumpido() is True
    db.close()
