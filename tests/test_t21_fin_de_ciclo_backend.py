# tests/test_t21_fin_de_ciclo_backend.py
#
# Tanda 21, backend de la pantalla de fin de ciclo
# (docs/mis_plans/planeacion_fin_de_ciclo.md):
# - FC-06: fase_terminacion y estados "fallida" / "interrumpida";
# - FC-13: terminacion y alarmas_ciclo de GET /cycle/current/progress (fallo,
#   emergencia, cancelación con y sin token, exitoso con observación);
# - FC-12: POST /cycle/abort con token opcional (estado, bitácora y ticket);
# - FC-11: /status con puertas_con_actuador (SimpleDoor y AdvancedDoor);
# - FC-08: carga sólida con observación (ticket/PDF, sin NO CONFORME, sin
#   apertura automática), carga líquida → FALLO CIC-19; P8 y C-03 sin cambios.

import json
import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import progreso_ciclo as pc
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor

pytestmark = pytest.mark.req("FC-06", "FC-08", "FC-11", "FC-12", "FC-13")

_APLICA = ["vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]


def _filas(*fases):
    """Filas de ciclo_fases cerradas, de 10 s cada una."""
    return [{"fase": f, "inicio_s": 10.0 * i, "fin_s": 10.0 * (i + 1), "duracion_s": 10.0}
            for i, f in enumerate(fases)]


# ── FC-06: lógica pura ───────────────────────────────────────────────────────

def test_fallo_de_fase_marca_fallida_y_el_resto_segun_su_lugar():
    filas = _filas("PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION")
    p = pc.armar_progreso(_APLICA, filas, "FALLO_ESTERILIZACION", 30.0, {})
    assert p["fase_terminacion"] == "esterilizacion"
    assert [(f["fase"], f["estado"]) for f in p["fases"]] == [
        ("vacio", "completada"), ("calentamiento", "completada"),
        ("esterilizacion", "fallida"), ("descompresion", "pendiente"), ("secado", "pendiente")]
    assert p["fases"][2]["duracion_s"] == 10.0


@pytest.mark.parametrize("fase_ciclo", ["EMERGENCIA", "SENSOR_AUSENTE", "FALLO_CONEXION",
                                        "FALLO_PUERTA_1_ABIERTA", "FALLO_SUMINISTRO"])
def test_otros_cierres_usan_la_ultima_fase_registrada(fase_ciclo):
    p = pc.armar_progreso(_APLICA, _filas("PRE_VACIO", "CALENTAMIENTO"), fase_ciclo, 20.0, {})
    assert p["fase_terminacion"] == "calentamiento"
    assert [f["estado"] for f in p["fases"]] == [
        "completada", "fallida", "pendiente", "pendiente", "pendiente"]


def test_cancelacion_marca_interrumpida():
    p = pc.armar_progreso(_APLICA, _filas("PRE_VACIO", "CALENTAMIENTO"), "CANCELADO", 20.0, {})
    assert [f["estado"] for f in p["fases"]][:3] == ["completada", "interrumpida", "pendiente"]


def test_exitoso_sin_cambios_y_en_curso_sin_terminacion():
    filas = _filas("PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO")
    p = pc.armar_progreso(_APLICA, filas, "COMPLETADO", 50.0, {})
    assert p["fase_terminacion"] is None
    assert all(f["estado"] == "completada" for f in p["fases"])
    p = pc.armar_progreso(_APLICA, _filas("PRE_VACIO"), "CALENTAMIENTO", 10.0, {})
    assert p["fase_terminacion"] is None


def test_sin_filas_no_inventa_la_fase():
    p = pc.armar_progreso(_APLICA, [], "CANCELADO", 0.0, {})
    assert p["fase_terminacion"] is None
    assert all(f["estado"] == "pendiente" for f in p["fases"])


def test_fase_terminacion_prefiere_el_nombre_del_fallo():
    assert pc.fase_terminacion(_filas("PRE_VACIO", "CALENTAMIENTO"),
                               "FALLO_PRE_VACIO") == "vacio"


# ── FC-13: lógica pura ───────────────────────────────────────────────────────

def test_terminacion_por_tipo():
    t = pc.armar_terminacion("FALLO_ESTERILIZACION", "esterilizacion", "CIC-12",
                             {"tsat": 137.0}, "CIC-12 · ...", "2026-10-28T10:00:00", "ana", [])
    assert t == {"tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 137.0},
                 "motivo": "CIC-12 · ...", "fase": "esterilizacion",
                 "hora_fin": "2026-10-28T10:00:00", "cancelado_por": None, "observaciones": []}
    t = pc.armar_terminacion("EMERGENCIA", "calentamiento", "", {}, "", None, None, [])
    assert (t["tipo"], t["codigo"], t["fase"]) == ("emergencia", "SIS-01", "calentamiento")
    t = pc.armar_terminacion("CANCELADO", "vacio", "", {}, "", None, "luis", [])
    assert (t["tipo"], t["codigo"], t["cancelado_por"]) == ("cancelado", None, "luis")
    t = pc.armar_terminacion("COMPLETADO", None, "", {}, "", None, "luis", [])
    assert (t["tipo"], t["fase"], t["cancelado_por"]) == ("exitoso", None, None)
    assert pc.armar_terminacion("ESTERILIZACION", None, "", {}, "", None, None, []) is None


def test_fallo_sin_codigo_conserva_el_motivo_crudo():
    t = pc.armar_terminacion("FALLO_SECADO", "secado", "", {"x": 1}, "Fallo en la fase Secado: x",
                             None, None, [])
    assert t["codigo"] is None and t["valores"] == {}
    assert t["motivo"] == "Fallo en la fase Secado: x"


def test_observaciones_en_la_terminacion():
    avisos = [{"clave": tf.CLAVE_OBSERVACION_REFERENCIA, "sensor": "Referencia",
               "hora": "10:42", "fase": "ESTERILIZACION"},
              {"clave": "ticket_ciclo.aviso_excursion", "sensor": "x"}, "texto"]
    t = pc.armar_terminacion("COMPLETADO", None, "", {}, "", None, None, avisos)
    assert t["observaciones"] == [{"sensor": "Referencia", "hora": "10:42",
                                   "fase": "esterilizacion"}]


def test_alarmas_del_ciclo_quita_la_causa_y_elige_la_descripcion():
    filas = [
        {"codigo": "CIC-12", "nivel": "ALARMA", "titulo": "t", "descripcion_inicial": "a",
         "descripcion_final": "", "valores_json": "{}", "aparecida": "1", "resuelta": "2"},
        {"codigo": "PRE-06", "nivel": "AVISO", "titulo": "t", "descripcion_inicial": "ini",
         "descripcion_final": "fin", "valores_json": '{"temp": 70.0}', "aparecida": "3",
         "resuelta": None},
        {"codigo": "CIC-12", "nivel": "ALARMA", "titulo": "t", "descripcion_inicial": "causa",
         "descripcion_final": "", "valores_json": "dañado", "aparecida": "4", "resuelta": None},
    ]
    salida = pc.alarmas_del_ciclo(filas, "CIC-12")
    assert [a["aparecida"] for a in salida] == ["1", "3"]       # quita solo la última CIC-12
    assert salida[1] == {"codigo": "PRE-06", "nivel": "AVISO", "titulo": "t",
                         "descripcion": "fin", "valores": {"temp": 70.0},
                         "aparecida": "3", "resuelta": None}
    assert salida[0]["descripcion"] == "a"
    assert len(pc.alarmas_del_ciclo(filas, None)) == 3


# ── Endpoint ─────────────────────────────────────────────────────────────────

class _Estado:
    def __init__(self):
        self.flags = {}
        self.maquina = GlobalState.CICLO
        self.fase_ciclo = "PRE_VACIO"
        self.avisos_ciclo = []
        self.operador_inicio = "ana"
        self.codigo_fallo = ""
        self.valores_fallo = {}
        self.motivo_fallo = ""
        self.cancelado_por = None
        self.estado_puertas = {}
        self.sensores_temp = {}
        self.sensores_pres = {}
        self.sensores_di = {}
        self.salidas_do = {}
        self.exposicion_restante_s = None

    def get_machine_state(self):
        return self.maquina

    def get_flag(self, nombre):
        return self.flags.get(nombre, False)

    def set_flag(self, nombre, valor):
        self.flags[nombre] = valor


class _Ciclo:
    id = "instrumental_134"
    name = "Instrumental 134"

    def get_param(self, seccion, nombre, default=None):
        return {("prevacio", "conteo_pulso_a"): 4,
                ("secado", "tiempo_secado"): 15.0}.get((seccion, nombre), default)


@pytest.fixture
def entorno(tmp_path):
    from types import SimpleNamespace
    db = DbManager(db_path=tmp_path / "t.db")
    estado = _Estado()
    ctx = MagicMock()
    ctx.db = db
    ctx.estado = estado
    ctx.cap = SimpleNamespace(has_vacuum=True)
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.programa_en_ejecucion.return_value = _Ciclo()
    ctx.cycle_logger.ciclo_id_pantalla = None
    ctx.cycle_logger.transcurrido_s.return_value = None
    ctx.cycle_logger.hora_fin_pantalla = None
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), ctx, estado, db, srv
    db.close()


def _ciclo_en_pantalla(ctx, db, fases):
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo="instrumental_134", nombre="x",
                         temp_ester=134, tiempo_ester=4, modelo="", serie="", version_sw="")
    t = 0.0
    for fase in fases:
        db.abrir_fase(cid, fase, t)
        t += 10.0
        db.cerrar_fase_abierta(cid, t)
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = t
    return cid


def _alarma(db, cid, codigo, aparecida, nivel="ALARMA", resuelta=None, final=""):
    i = db.insertar_alarma(codigo, nivel, f"Título {codigo}", None, f"desc {codigo}",
                           json.dumps({"n": 1}), aparecida, resuelta, cid)
    if final:
        db.marcar_alarma_resuelta(i, resuelta or aparecida, final, json.dumps({"n": 2}))
    return i


def test_progreso_en_curso_no_trae_terminacion(entorno):
    cliente, ctx, estado, db, _ = entorno
    _ciclo_en_pantalla(ctx, db, ["PRE_VACIO"])
    body = cliente.get("/cycle/current/progress").json()
    assert body["resultado"] is None and body["fase_terminacion"] is None
    assert "terminacion" not in body and "alarmas_ciclo" not in body


def test_progreso_con_fallo(entorno):
    cliente, ctx, estado, db, _ = entorno
    cid = _ciclo_en_pantalla(ctx, db, ["PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION"])
    _alarma(db, cid, "SEN-11", "2026-10-28T10:05:00", nivel="AVISO",
            resuelta="2026-10-28T10:06:00", final="desc final")
    _alarma(db, cid, "PRE-06", "2026-10-28T10:01:00", nivel="AVISO")
    _alarma(db, cid, "CIC-12", "2026-10-28T10:07:00")
    _alarma(db, None, "COM-01", "2026-10-28T10:02:00")             # de otro contexto
    estado.fase_ciclo = "FALLO_ESTERILIZACION"
    estado.codigo_fallo, estado.valores_fallo = "CIC-12", {"tsat": 137.0, "temp": 134.5, "dt": 2.5}
    estado.motivo_fallo = "CIC-12 · Aire: ..."
    ctx.cycle_logger.hora_fin_pantalla = "2026-10-28T10:07:01"
    body = cliente.get("/cycle/current/progress").json()
    assert body["resultado"] == "fallo"
    assert body["fase_terminacion"] == "esterilizacion"
    assert [f["estado"] for f in body["fases"]] == [
        "completada", "completada", "fallida", "pendiente", "pendiente"]
    assert body["terminacion"] == {
        "tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 137.0, "temp": 134.5, "dt": 2.5},
        "motivo": "CIC-12 · Aire: ...", "fase": "esterilizacion",
        "hora_fin": "2026-10-28T10:07:01", "cancelado_por": None, "observaciones": []}
    alarmas = body["alarmas_ciclo"]
    assert [a["codigo"] for a in alarmas] == ["PRE-06", "SEN-11"]     # cronológico, sin la causa
    assert alarmas[1]["descripcion"] == "desc final" and alarmas[1]["valores"] == {"n": 2}
    assert alarmas[1]["resuelta"] == "2026-10-28T10:06:00"
    assert alarmas[0]["descripcion"] == "desc PRE-06" and alarmas[0]["resuelta"] is None
    assert set(alarmas[0]) == {"codigo", "nivel", "titulo", "descripcion", "valores",
                               "aparecida", "resuelta"}


def test_progreso_con_emergencia(entorno):
    cliente, ctx, estado, db, _ = entorno
    cid = _ciclo_en_pantalla(ctx, db, ["PRE_VACIO", "CALENTAMIENTO"])
    _alarma(db, cid, "SIS-01", "2026-10-28T10:07:00", nivel="FALLO_CRITICO")
    estado.fase_ciclo = "EMERGENCIA"
    estado.codigo_fallo, estado.valores_fallo = "SIS-01", {"estado": "Ciclo"}
    body = cliente.get("/cycle/current/progress").json()
    t = body["terminacion"]
    assert (t["tipo"], t["codigo"], t["fase"]) == ("emergencia", "SIS-01", "calentamiento")
    assert body["fases"][1]["estado"] == "fallida"
    assert body["alarmas_ciclo"] == []
    # la hora de cierre sale de la base si el logger no la tiene
    assert t["hora_fin"] is None or isinstance(t["hora_fin"], str)


def test_progreso_exitoso_con_observacion(entorno):
    cliente, ctx, estado, db, _ = entorno
    cid = _ciclo_en_pantalla(ctx, db, ["PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION",
                                       "DESCOMPRESION", "SECADO"])
    _alarma(db, cid, "SEN-11", "2026-10-28T10:05:00", nivel="AVISO")
    estado.fase_ciclo = "COMPLETADO"
    estado.avisos_ciclo = [{"clave": tf.CLAVE_OBSERVACION_REFERENCIA, "sensor": "Referencia",
                            "hora": "10:05", "fase": "ESTERILIZACION"}]
    body = cliente.get("/cycle/current/progress").json()
    assert body["fase_terminacion"] is None
    assert all(f["estado"] == "completada" for f in body["fases"])
    t = body["terminacion"]
    assert (t["tipo"], t["codigo"], t["fase"]) == ("exitoso", None, None)
    assert t["observaciones"] == [{"sensor": "Referencia", "hora": "10:05",
                                   "fase": "esterilizacion"}]
    assert [a["codigo"] for a in body["alarmas_ciclo"]] == ["SEN-11"]


# ── FC-12: cancelación con y sin token ───────────────────────────────────────

def _eventos(db, evento):
    return [dict(f) for f in db.get_auditoria(evento=evento, limite=100)]


def _detalle(fila):
    d = fila["detalle"]
    return json.loads(d) if isinstance(d, str) else d


def test_cancelar_con_token_identifica_al_usuario(entorno):
    cliente, ctx, estado, db, srv = entorno
    cid = _ciclo_en_pantalla(ctx, db, ["PRE_VACIO"])
    r = cliente.post("/cycle/abort", headers=cabecera(srv, "operador", "luis"))
    assert r.status_code == 200 and r.json()["action"] == "CICLO_CANCELADO"
    assert estado.get_flag("CICLO_CANCELADO") is True
    assert estado.cancelado_por == "luis"
    [fila] = _eventos(db, "ciclo_cancelado")
    assert fila["usuario"] == "luis" and fila["rol"] == "operador"
    detalle = _detalle(fila)
    assert detalle["fase"] == "PRE_VACIO" and detalle["operador_ciclo"] == "ana"
    assert detalle["numero_ciclo"] == db.get_ciclo(cid)["numero_ciclo"]
    assert "sin_sesion" not in detalle
    # la pantalla final lo publica
    estado.fase_ciclo = "CANCELADO"
    t = cliente.get("/cycle/current/progress").json()["terminacion"]
    assert (t["tipo"], t["cancelado_por"], t["fase"]) == ("cancelado", "luis", "vacio")


@pytest.mark.parametrize("cabeceras", [{}, {"Authorization": "Bearer vencido"},
                                       {"Authorization": "basura"}])
def test_cancelar_sin_token_valido_funciona_igual(entorno, cabeceras):
    cliente, ctx, estado, db, _ = entorno
    _ciclo_en_pantalla(ctx, db, ["PRE_VACIO"])
    estado.cancelado_por = "residuo"
    r = cliente.post("/cycle/abort", headers=cabeceras)
    assert r.status_code == 200 and r.json() == {"ok": True, "action": "CICLO_CANCELADO"}
    assert estado.get_flag("CICLO_CANCELADO") is True
    assert estado.cancelado_por is None
    [fila] = _eventos(db, "ciclo_cancelado")
    assert fila["usuario"] == "" and _detalle(fila)["sin_sesion"] is True
    estado.fase_ciclo = "CANCELADO"
    t = cliente.get("/cycle/current/progress").json()["terminacion"]
    assert t["tipo"] == "cancelado" and t["cancelado_por"] is None


def test_cancelar_rechazado_no_audita_ni_marca(entorno):
    cliente, ctx, estado, db, srv = entorno
    estado.fase_ciclo = "COMPLETADO"
    r = cliente.post("/cycle/abort", headers=cabecera(srv, "operador", "luis"))
    assert r.status_code == 409
    assert estado.cancelado_por is None and _eventos(db, "ciclo_cancelado") == []


def test_ticket_lleva_quien_cancelo(tmp_path):
    from tests.test_t8_modo_sin_bd import _logger
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    cl.update()
    cl.update()
    estado.cancelado_por = "luis"
    estado.fase_ciclo = "CANCELADO"
    cl.update()
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "Cancelado por: luis" in impreso
    avisos = db.cerrar_ciclo.call_args.kwargs["avisos_ticket"]["avisos"]
    assert {"clave": tf.CLAVE_CANCELADO_POR, "usuario": "luis"} in avisos
    # la reimpresión (y el PDF, que usa format_ticket) es idéntica
    pie = tf.format_footer("CANCELADO", "2026-10-28T10:00:00", avisos=avisos,
                           p=tf.Presentacion(idioma="en"))
    assert "Cancelled by: luis" in pie


def test_bitacora_conoce_el_evento_nuevo():
    from autoclave.core.runtime import bitacora
    assert bitacora.se_registra("ciclo_cancelado")
    assert bitacora.categoria_de("ciclo_cancelado") == "seguridad"


# ── FC-11: /status publica si cada puerta tiene actuador ────────────────────

def test_status_puertas_con_actuador(entorno):
    from autoclave.devices.puertas.enum_doors import DoorState
    from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
    from tests.test_servicio_puertas import CONFIG, Estado, _avanzada
    from autoclave.devices.puertas.simple_door import SimpleDoor
    cliente, ctx, estado, _, _ = entorno
    e = Estado()
    simple = SimpleDoor("Puerta 1", {"cerrada": "puerta_1_cerrada"}, e)
    avanzada = _avanzada("Puerta 2", e)
    ctx.servicio_puertas = ServicioPuertas([simple, avanzada], e, MagicMock(), dict(CONFIG))
    estado.maquina = GlobalState.PREPARADO
    estado.estado_puertas = {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ABIERTO}
    body = cliente.get("/status").json()
    assert body["puertas_con_actuador"] == {"Puerta 1": False, "Puerta 2": True}
    assert body["doors"] == {"Puerta 1": "CERRADO", "Puerta 2": "ABIERTO"}


def test_status_puerta_sin_dato_falla_cerrada(entorno):
    from autoclave.devices.puertas.enum_doors import DoorState
    cliente, ctx, estado, _, _ = entorno
    ctx.servicio_puertas.tiene_actuador.side_effect = RuntimeError("x")
    estado.estado_puertas = {"Puerta 1": DoorState.CERRADO}
    assert cliente.get("/status").json()["puertas_con_actuador"] == {"Puerta 1": False}


# ── FC-08: ticket y CICLO ────────────────────────────────────────────────────

def test_ticket_con_observacion_en_es_y_en_y_sin_no_conforme():
    aviso = {"clave": tf.CLAVE_OBSERVACION_REFERENCIA, "sensor": "Referencia",
             "hora": "10:42", "fase": "ESTERILIZACION"}
    pie = tf.format_footer("COMPLETADO", "2026-10-28T11:00:00", avisos=[aviso],
                           p=tf.Presentacion(idioma="es"))
    assert "Observación: Referencia sin lectura desde 10:42 (ESTERILIZACION)" in pie
    assert "CONFORME" not in pie and "NO ESTÉRIL" not in pie
    pie_en = tf.format_footer("COMPLETADO", "2026-10-28T11:00:00", avisos=[aviso],
                              p=tf.Presentacion(idioma="en"))
    assert "Observation: Referencia without reading since 10:42" in pie_en
    ciclo = {"numero_ciclo": 3, "serie": "S", "modelo": "M", "version_sw": "1",
             "nombre_ciclo": "N", "tipo_ciclo": "t", "temp_esterilizacion": 134,
             "tiempo_esterilizacion": 4, "fecha_inicio": "2026-10-28T10:00:00",
             "resultado": "COMPLETADO", "fecha_fin": "2026-10-28T11:00:00",
             "avisos_ticket": json.dumps({"avisos": [aviso]})}
    ticket = tf.format_ticket(ciclo, [], p=tf.Presentacion(idioma="es"))
    assert "Observación: Referencia sin lectura desde 10:42" in ticket
    assert "NO CONFORME" not in ticket
    assert tf.ciclo_no_conforme(ciclo) is False
    assert tf.ciclo_observaciones(ciclo) == [{"sensor": "Referencia", "hora": "10:42",
                                              "fase": "ESTERILIZACION"}]


def test_ciclo_guardado_no_conforme_se_sigue_leyendo():
    ciclo = {"avisos_ticket": json.dumps({"avisos": [{"clave": tf.CLAVE_NO_CONFORME,
                                                      "sensor": "Referencia"}]})}
    assert tf.ciclo_no_conforme(ciclo) is True


def test_historial_expone_observaciones(entorno):
    cliente, _, estado, db, _ = entorno
    estado.maquina = GlobalState.PREPARADO
    aviso = {"clave": tf.CLAVE_OBSERVACION_REFERENCIA, "sensor": "Referencia",
             "hora": "10:42", "fase": "ESTERILIZACION"}
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1")
    db.cerrar_ciclo(i, "COMPLETADO", avisos_ticket={"sin_datos_s": None, "avisos": [aviso]})
    c = cliente.get("/cycle/list").json()["ciclos"][0]
    assert c["observaciones"] == [{"sensor": "Referencia", "hora": "10:42",
                                   "fase": "esterilizacion"}]
    assert "no_conforme" not in c
    c = cliente.get(f"/cycle/history/{i}/ticket").json()["ciclo"]
    assert c["observaciones"][0]["sensor"] == "Referencia"


_ASIG_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}


def _ciclo_ref(tipo_carga):
    from tests.test_t3_sensores_ciclo import _ciclo
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": 100.0, "temp_ref": None})
    estado.avisos_ciclo = []
    params = {("globals", "tipo_carga"): tipo_carga}
    ciclo.cycle.get_param.side_effect = lambda *k, default=None: params.get(k[:2], default)
    ciclo._fases[0].update = MagicMock(return_value=None)
    return ciclo, estado, am


def test_solido_sigue_con_observacion_y_sen11():
    from autoclave.state_machine.states.ciclo import CicloResultado
    ciclo, estado, am = _ciclo_ref("solido")
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert [i.codigo for i in am.activas()] == ["SEN-11"]
    inst = am.activas()[0]
    assert "controlado por el sensor Principal y la presión" in inst.descripcion
    assert "CONFORME" not in inst.descripcion
    [obs] = estado.avisos_ciclo
    assert obs["clave"] == tf.CLAVE_OBSERVACION_REFERENCIA and obs["sensor"] == "Referencia"
    ciclo._protocolo.ejecutar.assert_not_called()
    assert not hasattr(estado, "no_conforme") or not isinstance(estado.no_conforme, bool)


def test_liquido_falla_cic19():
    from autoclave.state_machine.states.ciclo import CicloResultado
    ciclo, estado, am = _ciclo_ref("liquido")
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    assert ciclo._resultado_pendiente == CicloResultado.FALLO
    assert [i.codigo for i in am.activas()] == ["CIC-19"]
    assert estado.codigo_fallo == "CIC-19"
    ciclo._protocolo.ejecutar.assert_called_once_with()
    ciclo._fases[0].update.assert_not_called()
    assert "SEN-11" not in [i.codigo for i in am.activas()]
    assert pc.tipo_terminacion(estado.fase_ciclo) == "fallo"


@pytest.mark.parametrize("tipo", ["Liquido", "líquido", "", "mixto"])
def test_tipo_de_carga_desconocido_se_trata_como_liquido(tipo):
    # revisión R (SAF-03): solo "solido" sigue con la observación; lo demás, CIC-19
    from autoclave.state_machine.states.ciclo import CicloResultado
    ciclo, estado, am = _ciclo_ref(tipo)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.codigo_fallo == "CIC-19"


def test_cic19_en_el_catalogo_es_bloqueante_como_cic12():
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    d19, d12 = CATALOGO["CIC-19"], CATALOGO["CIC-12"]
    assert d19.nivel is d12.nivel and d19.bloquea_inicio == d12.bloquea_inicio
    assert d19.titulo == "Sonda de referencia sin lectura"
    from autoclave import i18n
    assert i18n.t("alarmas.CIC-19.titulo", "en") == "Reference probe without reading"
