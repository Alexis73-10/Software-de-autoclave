# tests/test_o2f_calibracion_atm.py
#
# O2f (tanda 6): calibración de presión atmosférica, página de prueba de la
# impresora e impresión de ganancias. Sin hardware: reloj falso, contexto
# MagicMock e impresora doble.

import json
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import calibracion_atm as ca
from autoclave.devices.puertas.enum_doors import DoorState


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _lectura(**cambios):
    d = {"estado_maquina": "PREPARADO", "puertas": {"Puerta 1": DoorState.ABIERTO},
         "temp": 40.0, "pres": 75.0, "datos_vigentes": True}
    d.update(cambios)
    return d


class Banco:
    """CalibracionAtm con reloj falso; registra aplicaciones y auditoría."""
    def __init__(self, anterior=75.0, aplicar_falla=None):
        self.reloj = Reloj()
        self.lectura = _lectura()
        self.presiones = None           # iterador opcional de presiones por muestra
        self.aplicados = []
        self.eventos = []
        self.aplicar_falla = aplicar_falla
        self._anterior = anterior
        self.cal = ca.CalibracionAtm(self._leer, self._aplicar, self._auditar,
                                     lambda: self._anterior, reloj=self.reloj)

    def _leer(self):
        d = dict(self.lectura)
        if self.presiones is not None:
            d["pres"] = self.presiones(self.reloj.t)
        return d

    def _aplicar(self, valor, usuario):
        if self.aplicar_falla:
            raise self.aplicar_falla
        self.aplicados.append((valor, usuario))

    def _auditar(self, evento, usuario, rol, anterior, nuevo, detalle):
        self.eventos.append((evento, usuario, anterior, nuevo, detalle))

    def correr(self, hasta_s, cada=0.5):
        fin = self.reloj.t + hasta_s
        seguir = True
        while self.reloj.t < fin and seguir:
            self.reloj.t += cada
            seguir = self.cal.paso()
        return seguir


def test_constantes_de_la_instruccion():
    assert (ca.DURACION_S, ca.PERIODO_S, ca.MUESTRAS) == (120.0, 5.0, 24)
    assert (ca.PROMEDIO_MIN_KPA, ca.PROMEDIO_MAX_KPA, ca.DISPERSION_MAX_KPA) == (60.0, 105.0, 1.5)
    assert ca.DIFERENCIA_CONFIRMAR_KPA == 5.0 and ca.TEMP_MAX_C == 80.0


def test_ventana_completa_acepta_y_audita():
    b = Banco(anterior=74.0)
    assert b.cal.iniciar("tec", "tecnico", hilo=False) == (True, "")
    assert b.cal.en_curso
    b.correr(130)
    e = b.cal.estado()
    assert e["estado"] == ca.OK and e["muestras"] == 24
    assert b.aplicados == [(75.0, "tec")]
    ev = b.eventos[-1]
    assert ev[0] == "calibracion_atm_ok" and ev[2] == 74.0 and ev[3] == 75.0
    assert ev[4]["muestras"] == 24 and ev[4]["dispersion"] == 0.0


def test_no_termina_antes_de_120_s():
    b = Banco()
    b.cal.iniciar("tec", hilo=False)
    b.correr(119)
    assert b.cal.estado()["estado"] == ca.MIDIENDO and b.cal.estado()["muestras"] == 23
    assert b.aplicados == []


@pytest.mark.parametrize("cambio,motivo", [
    ({"puertas": {"Puerta 1": DoorState.CERRADO}}, "puerta_abierta"),
    ({"temp": 80.0}, "temp_baja"),
    ({"temp": None}, "temp_baja"),
    ({"estado_maquina": "CICLO"}, "fuera_de_ciclo"),
    ({"pres": None}, "lecturas_validas"),
    ({"pres": float("nan")}, "lecturas_validas"),
    ({"datos_vigentes": False}, "temp_baja"),
])
def test_perder_precondicion_aborta_sin_reintentar(cambio, motivo):
    b = Banco()
    b.cal.iniciar("tec", hilo=False)
    b.correr(30)
    b.lectura.update(cambio)
    assert b.correr(1) is False
    e = b.cal.estado()
    assert e["estado"] == ca.ABORTADA and e["motivo"] == motivo
    assert b.aplicados == [] and b.eventos[-1][0] == "calibracion_atm_abortada"
    b.lectura = _lectura()
    b.correr(200)                       # no reintenta sola
    assert b.cal.estado()["estado"] == ca.ABORTADA and b.aplicados == []


@pytest.mark.parametrize("cambio,codigo", [
    ({"puertas": {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ABRIENDO}}, "puerta_abierta"),
    ({"temp": 85.0}, "temp_baja"),
    ({"estado_maquina": "CICLO"}, "fuera_de_ciclo"),
    ({"pres": None}, "lecturas_validas"),
])
def test_precondiciones_al_iniciar(cambio, codigo):
    b = Banco()
    b.lectura.update(cambio)
    assert b.cal.iniciar("tec", hilo=False) == (False, codigo)
    assert not b.cal.en_curso


def test_doble_puerta_basta_una():
    b = Banco()
    b.lectura["puertas"] = {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ABIERTO}
    assert b.cal.iniciar("tec", hilo=False)[0]


def test_no_dos_a_la_vez():
    b = Banco()
    b.cal.iniciar("tec", hilo=False)
    assert b.cal.iniciar("otro", hilo=False) == (False, "en_curso")


def test_cancelar_aborta():
    b = Banco()
    b.cal.iniciar("tec", hilo=False)
    b.correr(20)
    assert b.cal.cancelar("ing", "ingeniero")
    assert b.cal.estado()["estado"] == ca.ABORTADA and b.cal.estado()["motivo"] == "cancelada"
    assert b.cal.paso() is False and b.aplicados == []
    assert not b.cal.cancelar()


def test_muestreo_atrasado_aborta():
    """La ventana debe ser continua: un hueco mayor a un periodo aborta."""
    b = Banco()
    b.cal.iniciar("tec", hilo=False)
    b.correr(12)
    b.reloj.t += 11                      # hilo detenido 11 s
    assert b.cal.paso() is False
    assert b.cal.estado()["motivo"] == "muestreo_irregular"


@pytest.mark.parametrize("pres,motivo", [(55.0, "fuera_de_rango"), (106.0, "fuera_de_rango")])
def test_promedio_fuera_de_rango_rechaza(pres, motivo):
    b = Banco(anterior=None)
    b.lectura["pres"] = pres
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    e = b.cal.estado()
    assert e["estado"] == ca.RECHAZADA and e["motivo"] == motivo and b.aplicados == []
    assert b.eventos[-1][0] == "calibracion_atm_rechazada"


def test_limites_del_promedio_aceptan():
    for pres in (60.0, 105.0):
        assert ca.validar_muestras([pres] * 24, pres)[0] == ca.OK
        # SAF-01 de O2f: sin valor anterior se pide confirmación
        assert ca.validar_muestras([pres] * 24, None)[0] == ca.POR_CONFIRMAR


def test_dispersion():
    base = [75.0] * 23
    assert ca.validar_muestras(base + [76.5], 75.0)[0] == ca.OK
    r = ca.validar_muestras(base + [76.6], 75.0)
    assert r[:2] == (ca.RECHAZADA, "inestable")


def test_dispersion_en_ventana_rechaza():
    b = Banco()
    b.presiones = lambda t: 75.0 if int(t) % 10 else 77.0
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    assert b.cal.estado()["motivo"] == "inestable" and b.aplicados == []


def test_diferencia_grande_pide_confirmacion():
    b = Banco(anterior=90.0)
    b.cal.iniciar("tec", "tecnico", hilo=False)
    b.correr(130)
    assert b.cal.estado()["estado"] == ca.POR_CONFIRMAR and b.aplicados == []
    assert b.cal.en_curso
    assert b.cal.confirmar("ing", "ingeniero") == (True, "")
    assert b.aplicados == [(75.0, "ing")] and b.cal.estado()["estado"] == ca.OK
    assert b.eventos[-1][1] == "ing" and b.eventos[-1][4]["iniciada_por"] == "tec"


def test_confirmar_revalida_condiciones():
    """SAF-03: con la puerta ya cerrada no se aplica."""
    b = Banco(anterior=90.0)
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    b.lectura["puertas"] = {"Puerta 1": DoorState.CERRADO}
    assert b.cal.confirmar("tec") == (False, "puerta_abierta") and b.aplicados == []


def test_vencimiento_no_pisa_aplicacion():
    """TMG-01: si vence mientras se aplica, gana la aplicación (OK auditado)."""
    b = Banco(anterior=90.0)
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    original = b._aplicar
    def aplicar_lento(valor, usuario):
        b.reloj.t += ca.PLAZO_CONFIRMACION_S + 5
        assert b.cal.paso() is False          # el sondeo ve el plazo vencido
        original(valor, usuario)
    b.cal._aplicar = aplicar_lento
    assert b.cal.confirmar("ing") == (True, "")
    assert b.cal.estado()["estado"] == ca.OK and b.eventos[-1][0] == "calibracion_atm_ok"


def test_diferencia_exactamente_5_no_pide():
    assert ca.validar_muestras([80.0] * 24, 75.0)[0] == ca.OK


def test_descartar_y_vencer_confirmacion():
    b = Banco(anterior=90.0)
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    assert b.cal.descartar("tec")
    assert b.cal.estado()["motivo"] == "descartada" and b.aplicados == []
    b2 = Banco(anterior=90.0)
    b2.cal.iniciar("tec", hilo=False)
    b2.correr(130)
    b2.correr(ca.PLAZO_CONFIRMACION_S + 2)
    assert b2.cal.estado()["motivo"] == "confirmacion_vencida" and b2.aplicados == []
    assert b2.cal.confirmar("tec") == (False, "sin_pendiente")


def test_aplicar_falla_rechaza_conservando():
    from autoclave.core.managers.config_manager import ErrorParametro
    b = Banco(aplicar_falla=ErrorParametro("incoherente"))
    b.cal.iniciar("tec", hilo=False)
    b.correr(130)
    e = b.cal.estado()
    assert e["estado"] == ca.RECHAZADA and e["motivo"] == "incoherente"


def test_hilo_real_cancela_rapido():
    b = Banco()
    assert b.cal.iniciar("tec")[0]
    assert b.cal.cancelar()
    b.cal._hilo.join(2)
    assert not b.cal._hilo.is_alive()


def test_usa_monotonic_por_defecto():
    import inspect
    import time
    assert inspect.signature(ca.CalibracionAtm).parameters["reloj"].default is time.monotonic
    assert "time.time" not in inspect.getsource(ca)


# ── API ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.sin_base_de_datos = False
    ctx.estado.estado_puertas = {"Puerta 1": DoorState.ABIERTO}
    ctx.estado.sensores_pres = {"pres_camara": 75.0}
    ctx.estado.sensores_temp = {"temp_camara": 40.0}
    ctx.control_loop.datos_vigentes = True
    ctx.programas_para_seguridad.return_value = [None]
    ctx.profile = None
    ctx.realtime_printer.estado.return_value = "lista"
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    obj = srv._calibracion_atm_obj
    if obj is not None:
        obj.cancelar()
    ctx.db.close()


ROLES = ["operador", "admin", "tecnico", "ingeniero"]


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_inicio(api, rol):
    client, srv, ctx, cab = api
    r = client.post("/maintenance/atm-calibration/start", headers=cab(srv, rol))
    assert r.status_code == (200 if rol in ("tecnico", "ingeniero") else 403)
    if r.status_code == 200:
        assert r.json()["estado"] == "midiendo"
        assert client.get("/status").json()["calibracion_atm_en_curso"] is True


@pytest.mark.parametrize("ruta", ["cancel", "confirm", "discard"])
@pytest.mark.parametrize("rol", ["operador", "admin"])
def test_matriz_otras_ordenes(api, ruta, rol):
    client, srv, ctx, cab = api
    assert client.post(f"/maintenance/atm-calibration/{ruta}", headers=cab(srv, rol)).status_code == 403


def test_sin_token_401(api):
    client, *_ = api
    assert client.post("/maintenance/atm-calibration/start").status_code == 401
    assert client.post("/printer/test-page").status_code == 401
    assert client.post("/maintenance/print/calibration").status_code == 401


def test_inicio_con_puerta_cerrada_409(api):
    client, srv, ctx, cab = api
    ctx.estado.estado_puertas = {"Puerta 1": DoorState.CERRADO}
    r = client.post("/maintenance/atm-calibration/start", headers=cab(srv, "tecnico"))
    assert r.status_code == 409 and r.json()["condicion"] == "puerta_abierta"


def test_inicio_en_ciclo_409(api):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cab = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.post("/maintenance/atm-calibration/start", headers=cab(srv, "ingeniero"))
    assert r.status_code == 409 and r.json()["condicion"] == "fuera_de_ciclo"


def test_parametros_bloqueados_y_cancelar(api):
    client, srv, ctx, cab = api
    h = cab(srv, "tecnico")
    client.post("/maintenance/atm-calibration/start", headers=h)
    r = client.patch("/global_params/timeout_puerta", json={"valor": 90}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "calibracion_en_curso"
    assert client.post("/maintenance/atm-calibration/start", headers=h).status_code == 409
    r = client.post("/maintenance/atm-calibration/cancel", headers=h)
    assert r.status_code == 200 and r.json()["estado"] == "abortada"
    assert client.post("/maintenance/atm-calibration/cancel", headers=h).status_code == 409
    filas = ctx.db.get_auditoria(evento="calibracion_atm_abortada")
    assert filas and filas[0]["usuario"] == "usuario_tecnico"


def test_aplicacion_real_escribe_referencia(api):
    """Ventana completa con reloj falso sobre el servidor: escribe la
    referencia (sin pasar por la API de parámetros) y audita."""
    client, srv, ctx, cab = api
    reloj = Reloj()
    cal = srv._calibracion_atm()
    cal._reloj = reloj
    ctx.estado.sensores_pres = {"pres_camara": 74.2}
    assert cal.iniciar("usuario_tecnico", "tecnico", hilo=False)[0]
    while cal.paso():
        reloj.t += 0.5
    assert ctx.config_manager.get("presion_atmosferica") == 74.2
    assert ctx.db.listar_parametros_sistema()["presion_atmosferica"]["valor"] == 74.2
    fila = ctx.db.get_auditoria(evento="calibracion_atm_ok")[0]
    assert json.loads(fila["valor_nuevo"]) == {"presion_atmosferica": 74.2}
    e = client.get("/maintenance/atm-calibration").json()
    assert e["estado"] == "ok" and e["referencia"]["valor"] == 74.2
    assert e["referencia"]["usuario"] == "usuario_tecnico"


def test_aplicacion_en_ciclo_se_revierte(api):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cab = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    from autoclave.core.managers.config_manager import ErrorParametro
    with pytest.raises(ErrorParametro):
        srv._aplicar_presion_atmosferica(74.0, "x")
    assert ctx.config_manager.get("presion_atmosferica") == 75
    assert ctx.db.listar_parametros_sistema()["presion_atmosferica"]["valor"] == 75


def test_api_de_parametros_sigue_sin_poder(api):
    client, srv, ctx, cab = api
    r = client.patch("/global_params/presion_atmosferica", json={"valor": 74},
                     headers=cab(srv, "ingeniero"))
    assert r.status_code == 403


@pytest.mark.parametrize("ruta,evento", [("/printer/test-page", "impresora_prueba"),
                                         ("/maintenance/print/calibration", "impresion_ganancias")])
@pytest.mark.parametrize("rol", ROLES)
def test_impresiones_matriz(api, ruta, evento, rol):
    client, srv, ctx, cab = api
    r = client.post(ruta, headers=cab(srv, rol))
    if rol in ("tecnico", "ingeniero"):
        assert r.status_code == 200
        texto = ctx.realtime_printer.enqueue.call_args[0][0]
        texto.encode("cp437")
        assert ctx.db.get_auditoria(evento=evento)
    else:
        assert r.status_code == 403 and not ctx.realtime_printer.enqueue.called


def test_impresiones_en_ciclo_y_sin_impresora(api):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cab = api
    h = cab(srv, "tecnico")
    ctx.realtime_printer.estado.return_value = "sin_papel"
    assert client.post("/printer/test-page", headers=h).status_code == 503
    ctx.realtime_printer.estado.return_value = "lista"
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert client.post("/maintenance/print/calibration", headers=h).status_code == 409
    assert not ctx.realtime_printer.enqueue.called


# ── tickets ─────────────────────────────────────────────────────────────────

def test_tickets_es_en_cp437():
    from datetime import datetime
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    meta = {"serie": "ACV-1", "modelo": "M-1"}
    sens = [{"tipo": "temperature", "sensor": "temp_camara", "gain": 1.0123, "offset": -0.5,
             "poly": False},
            {"tipo": "pressure", "sensor": "pres_camara", "gain": 1.0, "offset": 0.0, "poly": True}]
    ahora = datetime(2026, 10, 21, 8, 0)
    for idioma in ("es", "en"):
        p = tm.pagina_prueba(meta, ahora, idioma)
        g = tm.ganancias(meta, sens, 74.25, "2026-10-21T07:00:00", ahora, idioma)
        p.encode("cp437"); g.encode("cp437")
        assert "ACV-1" in p and "1.0123" in g and "74.25 kPa abs" in g
        assert all(len(l) <= tm.ANCHO for l in (p + g).splitlines())
    assert "PAGINA DE PRUEBA" in tm.pagina_prueba(meta, ahora, "es")
    assert "TEST PAGE" in tm.pagina_prueba(meta, ahora, "en")
    assert "sin dato" in tm.ganancias(meta, [], None, None, ahora, "es")
