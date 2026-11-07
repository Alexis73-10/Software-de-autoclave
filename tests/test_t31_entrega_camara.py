# tests/test_t31_entrega_camara.py
#
# Tanda 31 (planeacion_entrega_camara_fin_ciclo.md): entrega de la cámara al
# terminar el ciclo.
# - ENT-01/02: componente puro EntregaCamara (FALLO presurizado, cancelación,
#   COMPLETADO con espera y timeout, sensor perdido, datos no vigentes,
#   sellado, tramas AI repetidas) y su integración en CicloState (publicación
#   en estado.entrega_camara, CIC-07 una vez, limpieza en reset).
# - ENT-03/04/05: compuerta de POST /cycle/acknowledge (409
#   camara_no_entregada, forzar sin rol / sin reautenticación / correcto con
#   bitácora, excepción del paro soltado).
# - ENT-12: GET /cycle/current/progress publica `entrega` solo con resultado.

import threading
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.motivos import Motivo
from autoclave.state_machine.alarms.catalogo import CIC_07
from autoclave.state_machine.states import entrega_camara as ec
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from autoclave.state_machine.states.entrega_camara import EntregaCamara

_SOBREPRESION = Motivo("sobrepresion", "Sobrepresión en cámara: 250 kPa, máximo 121 kPa",
                       pres=250.0, pres_max=121.0)


# ── componente puro (ENT-01, ENT-02) ───────────────────────────────────────

@pytest.mark.req("ENT-01")
def test_fallo_presurizado_no_entrega_y_luego_entrega_sin_retirarse():
    e = EntregaCamara("FALLO", 0.0)
    e.actualizar(1.0, False, [_SOBREPRESION], seq_ai=1)
    assert not e.entregada and e.motivos == [_SOBREPRESION]
    assert e.publicar(1.0, True) == {"entregada": False, "motivos": [_SOBREPRESION],
                                     "espera_restante_s": None, "forzable": True}
    for i, seq in enumerate((2, 3, 4)):
        e.actualizar(2.0 + i, True, seq_ai=seq)
        assert e.entregada is (i == 2)
    # una vez entregada no se retira
    e.actualizar(10.0, False, [_SOBREPRESION], seq_ai=5)
    assert e.entregada and e.publicar(10.0, True)["forzable"] is False


@pytest.mark.req("ENT-01")
def test_misma_trama_ai_no_suma():
    e = EntregaCamara("FALLO", 0.0)
    for _ in range(5):
        e.actualizar(1.0, True, seq_ai=7)
    assert not e.entregada
    e.actualizar(1.5, True, seq_ai=8)
    e.actualizar(2.0, True, seq_ai=9)
    assert e.entregada


@pytest.mark.req("ENT-01")
def test_cancelacion_sin_espera():
    e = EntregaCamara("CANCELADO", 0.0, tiempo_espera_s=60, timeout_s=60)
    assert e.espera_restante_s(0.0) is None      # la espera fija es solo de COMPLETADO
    for t in (1, 2, 3):
        e.actualizar(float(t), True)
    assert e.entregada and not e.timeout_vencido


@pytest.mark.req("ENT-01")
def test_sensor_perdido_reinicia_la_cuenta_y_no_entrega():
    e = EntregaCamara("FALLO", 0.0)
    e.actualizar(1.0, True)
    e.actualizar(2.0, True)
    sin_temp = Motivo("sin_temp_camara", "Sin lectura válida de temperatura de cámara")
    e.actualizar(3.0, False, [sin_temp])
    assert e.motivos == [sin_temp] and not e.entregada
    e.actualizar(4.0, True)
    e.actualizar(5.0, True)
    assert not e.entregada
    e.actualizar(6.0, True)
    assert e.entregada


@pytest.mark.req("ENT-01")
def test_no_segura_sin_motivos_es_sin_dato():
    e = EntregaCamara("FALLO", 0.0)
    e.actualizar(1.0, False, [])
    assert [m.codigo for m in e.motivos] == ["sin_datos_vigentes"] and not e.entregada


@pytest.mark.req("ENT-01")
def test_datos_no_vigentes_no_cuentan():
    e = EntregaCamara("FALLO", 0.0)
    for t in range(1, 6):
        e.actualizar(float(t), True, ai_vigente=False)
    assert not e.entregada and [m.codigo for m in e.motivos] == ["sin_datos_vigentes"]


@pytest.mark.req("ENT-01")
def test_sellado_retiene_la_entrega():
    e = EntregaCamara("FALLO", 0.0)
    for t in range(1, 6):
        e.actualizar(float(t), True, sellado=True)
    assert not e.entregada and [m.codigo for m in e.motivos] == [ec.MOTIVO_SELLADO]


@pytest.mark.req("ENT-02")
def test_completado_espera_fija_y_luego_tres_lecturas():
    e = EntregaCamara("COMPLETADO", 100.0, tiempo_espera_s=60, timeout_s=1800)
    assert e.espera_restante_s(100.0) == 60
    assert e.espera_restante_s(130.2) == 30
    for t in (110.0, 140.0, 159.0):                 # seguro durante la espera: no cuenta
        e.actualizar(t, True)
    assert not e.entregada and e.publicar(159.0, True)["espera_restante_s"] == 1
    for t in (160.0, 161.0):
        e.actualizar(t, True)
    assert not e.entregada and e.espera_restante_s(161.0) is None
    e.actualizar(162.0, True)
    assert e.entregada


@pytest.mark.req("ENT-02")
def test_completado_timeout_de_temperatura():
    temp = Motivo("temp_alta", "Temperatura 95 °C, máximo 80 °C", temp=95.0, temp_max=80.0)
    e = EntregaCamara("COMPLETADO", 0.0, tiempo_espera_s=60, timeout_s=120)
    e.actualizar(170.0, False, [temp])
    assert not e.timeout_vencido
    e.actualizar(181.0, False, [temp])
    assert e.timeout_vencido and not e.entregada
    assert e.minutos_tras_espera(181.0) == pytest.approx(121 / 60)
    # sigue esperando
    for t in (182.0, 183.0, 184.0):
        e.actualizar(t, True)
    assert e.entregada


# ── CicloState (ENT-01/02/05/12) ───────────────────────────────────────────

_CONFIG = {"presion_admosferica": 101.3, "rango_presion_atm": 20.0, "temp_max_apertura": 80.0}


def _ciclo(resultado=CicloResultado.FALLO, temp=25.0, pres=101.3, tiempo_espera=60,
           timeout_min=30):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp}
    estado.sensores_pres = {"pres_camara": pres}
    estado.secando_tras_fallo = False
    estado.secado_tras_fallo = None
    flags = {}
    estado.get_flag.side_effect = lambda n: flags.get(n, False)
    estado.set_flag.side_effect = lambda n, v: flags.__setitem__(n, v)
    cycle = MagicMock()

    def _get_param(seccion, nombre, *resto, default=None):
        if resto:
            return default
        return {("finalizacion", "tiempo_espera_apertura"): tiempo_espera,
                ("finalizacion", "temp_max_apertura"): 80.0,
                ("finalizacion", "timeout_temperatura"): timeout_min}.get((seccion, nombre), default)

    cycle.get_param.side_effect = _get_param
    cycle.copia.return_value = cycle
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: _CONFIG.get(k, d)
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, MagicMock(), cycle, config, alarm_manager)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    ciclo._protocolo.sellado = False
    ciclo._resultado_pendiente = resultado
    ciclo.datos_vigentes = True
    return ciclo, estado, flags, alarm_manager


def _reloj(monkeypatch, t):
    import autoclave.state_machine.states.ciclo as mod
    monkeypatch.setattr(mod.time, "monotonic", lambda: t[0])


@pytest.mark.req("ENT-01")
def test_ciclostate_fallo_presurizado_publica_motivo_y_entrega_al_bajar(monkeypatch):
    t = [1000.0]
    _reloj(monkeypatch, t)
    ciclo, estado, _, _ = _ciclo(pres=250.0)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    pub = estado.entrega_camara
    assert pub["entregada"] is False and pub["forzable"] is True
    assert [m.codigo for m in pub["motivos"]] == ["sobrepresion"]
    assert pub["motivos"][0].valores["pres"] == 250.0
    estado.sensores_pres["pres_camara"] = 101.3
    for i in range(3):
        t[0] += 0.5
        ciclo.run()
        assert estado.entrega_camara["entregada"] is (i == 2)
    assert estado.entrega_camara == {"entregada": True, "motivos": [],
                                     "espera_restante_s": None, "forzable": False}
    # la presión vuelve a subir: sigue entregada
    estado.sensores_pres["pres_camara"] = 250.0
    ciclo.run()
    assert estado.entrega_camara["entregada"] is True


@pytest.mark.req("ENT-01")
def test_ciclostate_datos_no_vigentes_no_entrega(monkeypatch):
    ciclo, estado, _, _ = _ciclo()
    ciclo.datos_vigentes = False
    for _ in range(5):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is False
    assert [m.codigo for m in estado.entrega_camara["motivos"]] == ["sin_datos_vigentes"]


@pytest.mark.req("ENT-01")
def test_ciclostate_trama_ai_vencida_no_entrega():
    ciclo, estado, _, _ = _ciclo()
    estado.lectura_ai = lambda: (False, 3)      # proveedor del ControlLoop
    for _ in range(5):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is False


@pytest.mark.req("ENT-01")
def test_ciclostate_principal_perdido_no_entrega():
    ciclo, estado, _, _ = _ciclo(temp=None)
    for _ in range(5):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is False
    assert "sin_temp_camara" in [m.codigo for m in estado.entrega_camara["motivos"]]


@pytest.mark.req("ENT-01")
def test_ciclostate_sellado_no_entrega():
    ciclo, estado, _, _ = _ciclo()
    ciclo._protocolo.sellado = True
    for _ in range(5):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is False


@pytest.mark.req("ENT-02")
def test_ciclostate_completado_espera_y_cic07_una_vez(monkeypatch):
    t = [5000.0]
    _reloj(monkeypatch, t)
    ciclo, estado, _, alarmas = _ciclo(CicloResultado.COMPLETADO, temp=95.0,
                                       tiempo_espera=60, timeout_min=1)
    ciclo.run()
    assert estado.entrega_camara["espera_restante_s"] == 60
    t[0] += 60 + 59
    ciclo.run()
    assert estado.entrega_camara["entregada"] is False
    assert not any(c.args and c.args[0] == CIC_07 for c in alarmas.activar.call_args_list)
    t[0] += 2
    ciclo.run()
    ciclo.run()
    activaciones = [c for c in alarmas.activar.call_args_list if c.args[0] == CIC_07]
    assert len(activaciones) == 1
    assert activaciones[0].kwargs["temp"] == 95.0 and activaciones[0].kwargs["maximo"] == 80.0
    # se enfría: se entrega y CIC-07 se resuelve
    estado.sensores_temp["temp_camara"] = 60.0
    for _ in range(3):
        t[0] += 0.5
        ciclo.run()
    assert estado.entrega_camara["entregada"] is True
    alarmas.resolver.assert_any_call(CIC_07)


@pytest.mark.req("ENT-02")
def test_entrega_resuelve_cic07_de_la_apertura_automatica(monkeypatch):
    """B2 (revisión tanda 31): CIC-07 activada por la apertura automática
    (marca compartida) se resuelve al entregar la cámara."""
    t = [5000.0]
    _reloj(monkeypatch, t)
    ciclo, estado, _, alarmas = _ciclo(CicloResultado.COMPLETADO, tiempo_espera=0)
    ciclo._apertura_auto_alarmado = True        # la activó _mantener_apertura_automatica
    ciclo._entrega_cic07 = False
    for _ in range(3):
        t[0] += 0.5
        ciclo.run()
    assert estado.entrega_camara["entregada"] is True
    alarmas.resolver.assert_any_call(CIC_07)


@pytest.mark.req("ENT-01")
@pytest.mark.parametrize("seq", [None, "3", 2.5, True])
def test_con_proveedor_sin_numero_de_trama_no_suma(seq):
    """B1 (revisión tanda 31): con proveedor de vigencia, una trama sin número
    entero no suma lecturas (falla cerrada)."""
    e = EntregaCamara("FALLO", 0.0)
    for t in range(1, 6):
        e.actualizar(float(t), True, seq_ai=seq, exige_seq=True)
    assert not e.entregada and [m.codigo for m in e.motivos] == ["sin_datos_vigentes"]
    # sin proveedor (dobles de prueba) se cuenta como antes
    e2 = EntregaCamara("FALLO", 0.0)
    for t in range(1, 4):
        e2.actualizar(float(t), True, seq_ai=None)
    assert e2.entregada


@pytest.mark.req("ENT-01")
def test_ciclostate_proveedor_sin_numero_de_trama_no_entrega():
    ciclo, estado, _, _ = _ciclo()
    estado.lectura_ai = lambda: (True, None)     # vigente, pero sin número
    for _ in range(5):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is False
    seqs = iter(range(10, 20))
    estado.lectura_ai = lambda: (True, next(seqs))
    for _ in range(3):
        ciclo.run()
    assert estado.entrega_camara["entregada"] is True


@pytest.mark.req("ENT-05")
def test_ciclostate_paro_soltado_no_evalua_la_entrega():
    ciclo, estado, flags, _ = _ciclo()
    flags["PARO_EMERGENCIA"] = True
    ciclo.run()
    flags["PARO_EMERGENCIA"] = False
    for _ in range(5):
        ciclo.run()
    assert ciclo.ack_confirma_estado_seguro is True
    assert estado.entrega_camara["entregada"] is False
    assert estado.entrega_camara["forzable"] is True


@pytest.mark.req("ENT-05")
def test_ciclostate_paro_descarta_marcas_de_una_confirmacion():
    ciclo, estado, flags, _ = _ciclo()
    estado.confirmacion_forzada = {"usuario": "x", "motivo": "m"}
    estado.confirmado_tras_paro = True
    flags["PARO_EMERGENCIA"] = True
    ciclo.run()
    assert estado.confirmacion_forzada is None and estado.confirmado_tras_paro is False


@pytest.mark.req("ENT-12")
def test_ciclostate_confirmar_deja_de_ser_forzable_y_reset_limpia():
    ciclo, estado, flags, _ = _ciclo()
    ciclo.run()
    assert estado.entrega_camara["forzable"] is True
    flags["CICLO_CONFIRMADO"] = True
    assert ciclo.run() == CicloResultado.FALLO
    assert estado.entrega_camara["forzable"] is False
    estado.confirmacion_forzada = {"usuario": "x", "motivo": "m"}
    estado.confirmado_tras_paro = True
    ciclo.reset()
    assert estado.entrega_camara is None
    assert estado.confirmacion_forzada is None and estado.confirmado_tras_paro is False


def test_estado_autoclave_trae_los_valores_por_defecto():
    from autoclave.core.runtime.status import EstadoAutoclave
    e = EstadoAutoclave.__new__(EstadoAutoclave)
    EstadoAutoclave.__init__(e)
    assert e.entrega_camara is None and e.confirmacion_forzada is None
    assert e.confirmado_tras_paro is False


def test_state_machine_pasa_datos_vigentes_al_ciclo():
    import inspect
    from autoclave.state_machine import state_machine as sm
    fuente = inspect.getsource(sm.StateMachine.update)
    assert "self.ciclo.datos_vigentes = datos_vigentes is True" in fuente


# ── backend (ENT-03, ENT-04, ENT-05, ENT-12) ───────────────────────────────

class _Estado:
    def __init__(self):
        self.flags = {}
        self.fase_ciclo = "FALLO_ESTERILIZACION"
        self.entrega_camara = None
        self.confirmacion_forzada = None
        self.confirmado_tras_paro = False

    def get_machine_state(self):
        from autoclave.state_machine.machine.enum_global import GlobalState
        return GlobalState.CICLO

    def get_flag(self, n):
        return self.flags.get(n, False)

    def set_flag(self, n, v):
        self.flags[n] = v


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.backend.contrasenas import hash_password
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Inés", "ines_ing", hash_password("clave1234"), "ingeniero")
    db.crear_usuario("Tomás", "tomas_tec", hash_password("clave1234"), "tecnico")
    estado = _Estado()
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.estado = estado
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.state_machine.ciclo.ack_confirma_estado_seguro = False
    ctx.cycle_logger.ciclo_id_pantalla = None
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), srv, ctx, estado, db, cabecera
    db.close()


def _eventos(db, evento):
    return db.get_auditoria(evento=evento, limite=100)


@pytest.mark.req("ENT-03")
def test_ack_sin_entrega_409_con_motivo(api):
    client, _, _, estado, _, _ = api
    estado.entrega_camara = {"entregada": False, "motivos": [_SOBREPRESION],
                             "espera_restante_s": None, "forzable": True}
    r = client.post("/cycle/acknowledge")
    assert r.status_code == 409, r.text
    d = r.json()
    assert d["codigo"] == "camara_no_entregada" and "250 kPa" in d["detail"]
    assert d["motivo_codigo"] == "sobrepresion" and d["motivo_valores"]["pres"] == 250.0
    assert d["entrega"]["entregada"] is False and d["entrega"]["forzable"] is True
    assert not estado.get_flag("CICLO_CONFIRMADO") and not estado.get_flag("RESET_FALLA")


@pytest.mark.req("ENT-03")
@pytest.mark.parametrize("valor", [None, "x", {"entregada": "true"}, {}])
def test_ack_sin_dato_es_no_entregada(api, valor):
    client, _, _, estado, _, _ = api
    estado.entrega_camara = valor
    r = client.post("/cycle/acknowledge")
    assert r.status_code == 409 and r.json()["codigo"] == "camara_no_entregada"
    assert not estado.get_flag("CICLO_CONFIRMADO")


@pytest.mark.req("ENT-03")
def test_ack_con_entrega_como_antes(api):
    client, _, _, estado, db, _ = api
    estado.entrega_camara = {"entregada": True, "motivos": [], "espera_restante_s": None,
                             "forzable": False}
    r = client.post("/cycle/acknowledge")
    assert r.status_code == 200 and r.json() == {"ok": True, "action": "CICLO_CONFIRMADO"}
    assert estado.get_flag("CICLO_CONFIRMADO") and estado.get_flag("RESET_FALLA")
    assert estado.confirmacion_forzada is None and estado.confirmado_tras_paro is False
    assert _eventos(db, "ciclo_confirmado_sin_entrega") == []


@pytest.mark.req("ENT-03")
def test_ack_en_espera_de_completado_lleva_el_tiempo(api):
    client, _, _, estado, _, _ = api
    estado.fase_ciclo = "COMPLETADO"
    estado.entrega_camara = {"entregada": False, "motivos": [], "espera_restante_s": 42,
                             "forzable": True}
    r = client.post("/cycle/acknowledge")
    assert r.status_code == 409 and "42 s" in r.json()["detail"]


@pytest.mark.req("ENT-04")
def test_forzar_sin_sesion_401_y_sin_rol_403(api):
    client, srv, _, estado, _, cab = api
    estado.entrega_camara = {"entregada": False, "motivos": [_SOBREPRESION], "forzable": True}
    r = client.post("/cycle/acknowledge", json={"forzar": True, "clave": "clave1234"})
    assert r.status_code == 401
    r = client.post("/cycle/acknowledge", json={"forzar": True, "clave": "clave1234"},
                    headers=cab(srv, "tecnico", usuario="tomas_tec"))
    assert r.status_code == 403 and r.json()["codigo"] == "rol_sin_permiso"
    assert not estado.get_flag("CICLO_CONFIRMADO")


@pytest.mark.req("ENT-04")
@pytest.mark.parametrize("clave,codigo", [("", "reautenticacion_requerida"),
                                          ("mala", "reautenticacion_fallida")])
def test_forzar_sin_reautenticacion_403(api, clave, codigo):
    client, srv, _, estado, _, cab = api
    estado.entrega_camara = {"entregada": False, "motivos": [_SOBREPRESION], "forzable": True}
    r = client.post("/cycle/acknowledge", json={"forzar": True, "clave": clave},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 403 and r.json()["codigo"] == codigo
    assert not estado.get_flag("CICLO_CONFIRMADO") and estado.confirmacion_forzada is None


@pytest.mark.req("ENT-04")
def test_forzar_ok_con_bitacora_y_marca(api):
    from autoclave.core.runtime import bitacora
    client, srv, _, estado, db, cab = api
    estado.entrega_camara = {"entregada": False, "motivos": [_SOBREPRESION], "forzable": True}
    r = client.post("/cycle/acknowledge", json={"forzar": True, "clave": "clave1234"},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 200, r.text
    assert estado.get_flag("CICLO_CONFIRMADO") and estado.get_flag("RESET_FALLA")
    assert estado.confirmacion_forzada == {"usuario": "ines_ing", "motivo": str(_SOBREPRESION)}
    [fila] = _eventos(db, "ciclo_confirmado_sin_entrega")
    assert fila["usuario"] == "ines_ing" and fila["valor_nuevo"] == str(_SOBREPRESION)
    assert bitacora.categoria_de("ciclo_confirmado_sin_entrega") == "seguridad"
    assert bitacora.se_registra("ciclo_confirmado_sin_entrega")


@pytest.mark.req("ENT-04")
def test_forzar_con_paro_activo_sigue_409_paro(api):
    client, srv, _, estado, _, cab = api
    estado.flags["PARO_EMERGENCIA"] = True
    r = client.post("/cycle/acknowledge", json={"forzar": True, "clave": "clave1234"},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"


@pytest.mark.req("ENT-05")
def test_paro_soltado_confirma_sin_entrega_y_marca(api):
    client, _, ctx, estado, db, _ = api
    ctx.control_loop.state_machine.ciclo.ack_confirma_estado_seguro = True
    estado.entrega_camara = {"entregada": False, "motivos": [], "forzable": True}
    r = client.post("/cycle/acknowledge")
    assert r.status_code == 200, r.text
    assert estado.get_flag("CICLO_CONFIRMADO") and estado.confirmado_tras_paro is True
    assert estado.confirmacion_forzada is None
    assert _eventos(db, "ciclo_confirmado_sin_entrega") == []
    assert len(_eventos(db, "falla_reconocida")) == 1       # bitácora como hoy


@pytest.mark.req("ENT-12")
def test_progress_publica_entrega_solo_con_resultado(api, monkeypatch):
    from tests.helpers.backend_doble import parchear_en_backend
    client, _, ctx, estado, _, _ = api
    parchear_en_backend(monkeypatch, "_ciclo_de_pantalla", lambda: 7)
    ctx.cycle_logger.transcurrido_s.return_value = 120.0
    from autoclave.core.runtime import progreso_ciclo
    monkeypatch.setattr(progreso_ciclo, "fases_aplicables", lambda c, cap: [])
    monkeypatch.setattr(progreso_ciclo, "detalle_fase", lambda *a, **k: None)
    parchear_en_backend(monkeypatch, "_terminacion_y_alarmas", lambda *a, **k: {})
    ctx.cap = None
    ctx.db = MagicMock()
    ctx.db.get_fases_ciclo.return_value = []
    ctx.db.get_ciclo.return_value = None
    ctx.db.get_duraciones_referencia.return_value = {}
    estado.entrega_camara = {"entregada": False, "motivos": [_SOBREPRESION],
                             "espera_restante_s": None, "forzable": True}
    estado.fase_ciclo = "ESTERILIZACION"
    assert "entrega" not in client.get("/cycle/current/progress").json()
    estado.fase_ciclo = "FALLO_ESTERILIZACION"
    p = client.get("/cycle/current/progress").json()
    assert p["entrega"]["entregada"] is False and p["entrega"]["forzable"] is True
    assert p["entrega"]["motivos"] == [str(_SOBREPRESION)]
    assert p["entrega"]["espera_restante_s"] is None
    assert p["entrega"]["motivos_detalle"][0]["motivo_codigo"] == "sobrepresion"


# ── cliente (ENT-03/04) ────────────────────────────────────────────────────

@pytest.mark.req("ENT-03")
def test_sesion_backend_reconoce_camara_no_entregada_solo_en_su_ruta():
    pytest.importorskip("PySide6")
    from autoclave import i18n
    from autoclave.ui_qml.sesion_backend import clave_mensaje, interpretar
    r = interpretar(409, {"codigo": "camara_no_entregada", "detail": "x"}, "/cycle/acknowledge")
    assert r.causa == "camara_no_entregada" and r.datos["detail"] == "x"
    assert interpretar(409, {"codigo": "camara_no_entregada"}, "/cycle/start").causa == "error_generico"
    for codigo in ("reautenticacion_requerida", "reautenticacion_fallida", "rol_sin_permiso"):
        assert interpretar(403, {"codigo": codigo}, "/cycle/acknowledge").causa == codigo
    clave = clave_mensaje("camara_no_entregada", "/cycle/acknowledge")
    assert clave == "sesion.camara_no_entregada"
    assert all(i18n.existe(clave, l) for l in ("es", "en"))


class _Resp:
    def __init__(self, status, datos):
        self.status_code = status
        self._datos = datos

    def json(self):
        return self._datos


def test_cliente_acknowledge_compatible_y_rechazo():
    import requests
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    servicio = UIServiceBackend.__new__(UIServiceBackend)
    servicio.backend = MagicMock()
    assert servicio.acknowledge_cycle() is True
    assert servicio.backend.post.call_args.kwargs["path"] == "/cycle/acknowledge"
    assert "body" not in servicio.backend.post.call_args.kwargs
    assert servicio.ultimo_rechazo_ack() is None
    err = requests.HTTPError("409")
    err.response = _Resp(409, {"codigo": "camara_no_entregada", "detail": "d"})
    servicio.backend.post.side_effect = err
    assert servicio.acknowledge_cycle(forzar=True, clave="k") is False
    assert servicio.backend.post.call_args.kwargs["body"] == {"forzar": True, "clave": "k"}
    assert servicio.ultimo_rechazo_ack() == (409, {"codigo": "camara_no_entregada", "detail": "d"})
