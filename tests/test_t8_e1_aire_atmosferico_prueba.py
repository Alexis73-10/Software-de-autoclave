"""E1 (tanda 8), D8-3.19 ★: en modo prueba, `aire_atmosferico_camara` es la
ÚNICA excepción a D-ES-15 (el modo prueba permite todas las salidas). Se
rechaza si la presión de cámara supera la atmosférica de referencia más la
brecha (`presion_admosferica + rango_presion_atm`) o si no hay lectura de
presión. El motivo va con texto del catálogo.

Además (DECISIÓN SIN CONFIRMAR de E1): si ya está abierta en modo prueba y la
condición deja de cumplirse (la cámara se presuriza o se pierde la lectura),
el lazo la cierra y lo registra en la bitácora."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import aire_atmosferico_prueba as aap
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor

_CONFIG = {"presion_atmosferica": 75.0, "rango_presion_atm": 5.0}


def _estado(pres):
    return SimpleNamespace(sensores_pres={"pres_camara": pres})


# ── Regla pura ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pres", [75.0, 80.0, 20.0, 1.0])
def test_permitido_en_atmosferica_hasta_el_borde_y_en_vacio(pres):
    assert aap.evaluar(_estado(pres), _CONFIG, senal_presente=True) == (True, "")


@pytest.mark.parametrize("pres", [80.1, 120.0, 300.0])
def test_rechazado_con_la_camara_por_encima_de_atm_mas_brecha(pres):
    assert aap.evaluar(_estado(pres), _CONFIG, senal_presente=True) == (False, aap.CON_PRESION)


# 0,0 kPa es lo que hoy entrega un lazo de 4-20 mA abierto (recorte de
# convert_pressures): piso físico de 1 kPa absoluto (revisión SEN-01)
@pytest.mark.parametrize("pres", [None, float("nan"), "x", True, 0.0, 0.99, -3.0])
def test_rechazado_sin_lectura_de_presion(pres):
    assert aap.evaluar(_estado(pres), _CONFIG, senal_presente=True) == (False, aap.SIN_PRESION)


@pytest.mark.parametrize("config", [{}, {"presion_atmosferica": 75.0},
                                    {"presion_atmosferica": None, "rango_presion_atm": 5.0}])
def test_rechazado_sin_referencia_atmosferica(config):
    assert aap.evaluar(_estado(75.0), config, senal_presente=True) == (False, aap.SIN_REFERENCIA)


def test_nombres_de_la_salida():
    assert aap.es_salida("aire_atmosferico_camara") is True
    assert aap.es_salida("aire_admosferico_camara") is True
    assert aap.es_salida("vapor_camara") is False


# ── PATCH /io/test/output ───────────────────────────────────────────────────

@pytest.fixture
def prueba():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_di = {}
    ctx.estado.sensores_pres = {"pres_camara": 75.0}
    ctx.config_manager.get.side_effect = lambda k, d=None: _CONFIG.get(k, d)
    ctx.doors = []
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = False
    ctx.control_loop.presion_vigente = True     # trama AI al día
    ctx.units.senal_presion_presente.return_value = True    # ADC sobre adc_min
    ctx.setdo.salida_bloqueada.return_value = False
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    srv._token_modo_prueba = cab["Authorization"].split()[1]
    return TestClient(srv.app, headers=cab), ctx


_CANAL = EstadoAutoclave.map_do["aire_admosferico_camara"] + 1


@pytest.mark.parametrize("nombre", ["aire_atmosferico_camara", "aire_admosferico_camara"])
def test_patch_permitido_en_atmosferica(prueba, nombre):
    client, ctx = prueba
    r = client.patch(f"/io/test/output/{nombre}", json={"value": True})
    assert r.status_code == 200, r.text
    ctx.setdo.set_output.assert_called_once_with(_CANAL, True)


@pytest.mark.parametrize("pres, codigo", [(120.0, aap.CON_PRESION), (None, aap.SIN_PRESION)])
def test_patch_rechazado_con_presion_o_sin_lectura(prueba, pres, codigo):
    client, ctx = prueba
    ctx.estado.sensores_pres = {"pres_camara": pres}
    r = client.patch("/io/test/output/aire_atmosferico_camara", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == codigo
    ctx.setdo.set_output.assert_not_called()


def test_patch_apagar_siempre_permitido(prueba):
    client, ctx = prueba
    ctx.estado.sensores_pres = {"pres_camara": None}
    r = client.patch("/io/test/output/aire_atmosferico_camara", json={"value": False})
    assert r.status_code == 200, r.text
    ctx.setdo.set_output.assert_called_once_with(_CANAL, False)


def test_patch_otras_salidas_siguen_sin_condicion_de_presion(prueba):
    """D-ES-15 se mantiene para todas las demás salidas."""
    client, ctx = prueba
    ctx.estado.sensores_pres = {"pres_camara": None}
    r = client.patch("/io/test/output/vapor_camara", json={"value": True})
    assert r.status_code == 200, r.text


# ── Vigilancia en el lazo (modo prueba) ─────────────────────────────────────

class _Estado:
    def __init__(self, pres, aire_on):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self.sensores_di = {"paro_emergencia": 1, "suministro_electrico": 1}
        self.sensores_pres = {"pres_camara": pres}
        self.salidas_do = {k: 0 for k in EstadoAutoclave.map_do}
        self.salidas_do["aire_admosferico_camara"] = 1 if aire_on else 0

    def get_machine_state(self):
        return GlobalState.PREPARADO

    def get_flag(self, n):
        return self._flags.get(n, False)

    def set_flag(self, n, v):
        self._flags[n] = v

    def update(self, _):
        pass


def _loop(estado):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get.side_effect = lambda k, d=None: _CONFIG.get(k, d)
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[], estado=estado,
                           link=MagicMock(), set_do=MagicMock(), alarm_manager=MagicMock(),
                           cycle_manager=MagicMock(), config_manager=cm)
    loop.link.edad_ultima_di.return_value = 0.0
    loop.link.edad_ultima_ai.return_value = 0.0
    loop.units.senal_presion_presente.return_value = True
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.is_connected.return_value = True
    loop.paro_emergencia.update(1)
    loop.al_evento_seguridad = MagicMock()
    loop._test_mode.set()
    loop._conectado_desde = 0.0
    loop.link_was_connected = True
    return loop


@pytest.mark.parametrize("pres", [120.0, None])
def test_lazo_cierra_el_aire_abierto_si_la_camara_deja_de_estar_segura(pres):
    estado = _Estado(pres, aire_on=True)
    loop = _loop(estado)
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)
    loop.al_evento_seguridad.assert_called_once()
    evento, detalle = loop.al_evento_seguridad.call_args.args
    assert evento == "aire_atmosferico_cortado_prueba"
    assert detalle["motivo"] in (aap.CON_PRESION, aap.SIN_PRESION)
    # en el tick siguiente, mientras la tarjeta lo siga reportando abierto,
    # se reafirma el cierre pero no se repite el registro
    loop._tick()
    assert loop.al_evento_seguridad.call_count == 1


def test_lazo_no_toca_el_aire_en_atmosferica():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop._tick()
    # S9, revisión ★ SAF-01: el lazo sí apaga apertura/desbloqueo de puertas
    # (aquí la cámara no es segura: sin temperatura), pero no el aire
    assert all(c.args[0] != _CANAL for c in loop.set_do.set_output.call_args_list)
    loop.al_evento_seguridad.assert_not_called()


def test_lazo_reafirma_el_cierre_aunque_la_tarjeta_no_lo_reporte_abierto():
    """SAF-02 / TMG-01: la trama DO puede llegar tarde o no llegar; mientras
    la condición sea insegura se ordena cerrar en cada tick (idempotente),
    pero sin registro en la bitácora si no estaba reportada abierta."""
    loop = _loop(_Estado(150.0, aire_on=False))
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)
    loop.al_evento_seguridad.assert_not_called()


def test_lazo_cierra_con_datos_no_vigentes():
    """Sin datos vigentes, la lectura guardada es vieja: se cierra. (En el
    tick, una DI vencida además activa el paro (A-3), que cancela el modo
    prueba y apaga todo.)"""
    loop = _loop(_Estado(75.0, aire_on=True))
    assert loop._vigilar_aire_atmosferico_prueba(vigentes=False) == aap.SIN_PRESION
    loop.set_do.set_output.assert_called_once_with(_CANAL, False)


def test_tick_con_di_vencida_apaga_todo():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop._di_vigente = lambda: False
    loop._tick()
    loop.set_do.reset_all_outputs.assert_called()


def test_lazo_cierra_si_la_evaluacion_falla():
    """TMG-06: un error al evaluar no aborta el tick; se cierra."""
    loop = _loop(_Estado(75.0, aire_on=True))
    loop.config_manager.get.side_effect = RuntimeError("config rota")
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)


def test_lazo_fuera_de_modo_prueba_no_vigila():
    loop = _loop(_Estado(150.0, aire_on=True))
    loop._test_mode.clear()
    loop._tick()
    assert _CANAL not in [c.args[0] for c in loop.set_do.set_output.call_args_list]


def test_nuevo_registro_tras_volver_a_cerrarse():
    estado = _Estado(150.0, aire_on=True)
    loop = _loop(estado)
    loop._tick()
    estado.salidas_do["aire_admosferico_camara"] = 0
    loop._tick()
    estado.salidas_do["aire_admosferico_camara"] = 1
    loop._tick()
    assert loop.al_evento_seguridad.call_count == 2


# ── Catálogo ────────────────────────────────────────────────────────────────

def test_codigos_con_texto_propio_del_catalogo():
    import json
    from pathlib import Path
    from autoclave.ui_qml import sesion_backend
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    for codigo in (aap.CON_PRESION, aap.SIN_PRESION, aap.SIN_REFERENCIA):
        clave = sesion_backend.clave_mensaje(codigo)
        assert clave.startswith("io.err_aire_"), clave
        for idioma in ("es", "en"):
            d = json.loads((raiz / f"{idioma}.json").read_text(encoding="utf-8"))
            seccion, nombre = clave.split(".", 1)
            assert d[seccion][nombre].strip(), (idioma, clave)


def test_controlador_no_agrega_el_texto_del_backend_a_estos_motivos():
    from autoclave.ui_qml.controllers.entradas_salidas_controller import EntradasSalidasController
    from autoclave.ui_qml.sesion_backend import Resultado
    c = EntradasSalidasController()
    c._fallo(Resultado(aap.CON_PRESION, {"detail": "texto del backend en español"}, 409))
    assert c.mensaje == "io.err_aire_con_presion"
    assert c.detalle == ""


# ── Vigencia de la trama AI (segunda revisión: SAF-01 / TMG-01 / SEN-01) ────
# La presión llega en la trama AI; si solo la DI está al día, pres_camara
# puede estar congelada (AI caída o malformada, o reconexión con la AI de la
# conexión anterior). Para el aire atmosférico se exige además AI vigente.

from autoclave.protocols.serial_link import SerialLink
from autoclave.protocols.serial_link_config import SerialLinkConfig
from tests.serial_doble import AI_OK, PuertoDoble, linea


def _link_real():
    link = SerialLink(config=SerialLinkConfig())
    link._rx_buf = bytearray()
    link.serial = PuertoDoble()
    link.data["port_open"] = True
    return link


def test_enlace_sin_trama_ai_la_edad_es_none():
    link = _link_real()
    link._alimentar(linea("DI:" + "1" * 56))
    assert link.edad_ultima_ai() is None


def test_enlace_trama_ai_fija_su_sello():
    link = _link_real()
    with patch("autoclave.protocols.serial_link.time.monotonic", return_value=100.0):
        link._alimentar(linea(AI_OK))
    assert link.edad_ultima_ai(now=101.0) == pytest.approx(1.0)


def test_enlace_ai_malformada_no_renueva_el_sello():
    link = _link_real()
    link._alimentar(linea("AI:1,2,3"))
    assert link.edad_ultima_ai() is None


def test_enlace_disconnect_borra_el_sello_ai():
    link = _link_real()
    link._alimentar(linea(AI_OK))
    link._disconnect()
    assert link.edad_ultima_ai() is None


def test_enlace_connect_borra_el_sello_ai():
    link = SerialLink(config=SerialLinkConfig())
    link._scan_ports = lambda: "COM4"
    link._ultima_ai_mono = 50.0
    with patch("autoclave.protocols.serial_link.serial.Serial", return_value=MagicMock()):
        assert link._connect() is True
    assert link.edad_ultima_ai() is None


@pytest.mark.parametrize("edad", [None, 5.0, "x", True])
def test_lazo_cierra_con_trama_ai_vencida(edad):
    loop = _loop(_Estado(75.0, aire_on=True))
    loop.link.edad_ultima_ai.return_value = edad
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)
    assert loop.al_evento_seguridad.call_args.args[1]["motivo"] == aap.SIN_PRESION


def test_lazo_no_cierra_con_trama_ai_vigente():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop.link.edad_ultima_ai.return_value = 0.2
    loop._tick()
    loop.al_evento_seguridad.assert_not_called()


@pytest.mark.parametrize("vigente", [False, None])
def test_patch_rechazado_con_trama_ai_vencida(prueba, vigente):
    client, ctx = prueba
    ctx.control_loop.presion_vigente = vigente
    r = client.patch("/io/test/output/aire_atmosferico_camara", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == aap.SIN_PRESION
    ctx.setdo.set_output.assert_not_called()


# ── Señal cruda del transductor (tercera revisión: SEN-01 / SEN-03) ─────────
# Con la calibración de fábrica (adc_min 5 → 2 kPa) un lazo abierto (ADC 0)
# se lee ~1,5 kPa, por encima del piso de 1 kPa; y los filtros tardan 2-3
# tramas en bajar. Se exige además ADC crudo del canal sobre su adc_min.

@pytest.mark.parametrize("senal", [None, False, "si", 1])
def test_regla_rechaza_sin_senal_cruda_confirmada(senal):
    assert aap.evaluar(_estado(75.0), _CONFIG, senal_presente=senal) == (False, aap.SIN_PRESION)


def test_regla_por_defecto_rechaza():
    assert aap.evaluar(_estado(75.0), _CONFIG) == (False, aap.SIN_PRESION)


def _trama(u, raw_canal):
    raw = [0] * 16
    raw[8 + 0] = raw_canal
    u.update_from_serial({"ai": raw})


def _units(raw_canal, factory=True, tramas=None):
    from autoclave.hal.measures.units import Units
    u = Units()
    if factory:
        u._config.calibration.factory.pressure[0].adc_min = 5
    for _ in range(Units.TRAMAS_SENAL_PRESION if tramas is None else tramas):
        _trama(u, raw_canal)
    return u


# Revisión final (SEN-01, media): tras un lazo abierto, la mediana de 5 y el
# filtro siguen en el valor bajo unas tramas; la señal cruda debe llevar al
# menos la profundidad de la mediana seguida sobre adc_min.

def test_units_senal_exige_tramas_seguidas_sobre_adc_min():
    from autoclave.hal.measures.units import Units
    n = Units.TRAMAS_SENAL_PRESION
    assert n >= 5                                  # profundidad de la mediana
    u = _units(2000, tramas=n - 1)
    assert u.senal_presion_presente(0) is False
    _trama(u, 2000)
    assert u.senal_presion_presente(0) is True
    _trama(u, 0)                                   # lazo abierto: vuelve a cero
    for _ in range(n - 1):
        _trama(u, 2000)
    assert u.senal_presion_presente(0) is False
    _trama(u, 2000)
    assert u.senal_presion_presente(0) is True


@pytest.mark.parametrize("raw, esperado", [(0, False), (5, False), (6, True), (2000, True)])
def test_units_senal_presente_sobre_adc_min(raw, esperado):
    assert _units(raw).senal_presion_presente(0) is esperado


def test_units_senal_ausente_con_indice_invalido():
    assert _units(2000).senal_presion_presente(99) is False


def test_units_sin_calibracion_de_fabrica_exige_adc_positivo():
    from autoclave.hal.measures.units import Units
    u = Units()
    u._config.calibration.factory.pressure = []
    for _ in range(Units.TRAMAS_SENAL_PRESION):
        _trama(u, 0)
    assert u.senal_presion_presente(0) is False
    for _ in range(Units.TRAMAS_SENAL_PRESION):
        _trama(u, 1)
    assert u.senal_presion_presente(0) is True


@pytest.mark.parametrize("senal", [False, None])
def test_lazo_cierra_sin_senal_cruda(senal):
    loop = _loop(_Estado(75.0, aire_on=True))
    loop.units.senal_presion_presente.return_value = senal
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)
    assert loop.al_evento_seguridad.call_args.args[1]["motivo"] == aap.SIN_PRESION


def test_lazo_cierra_si_units_lanza():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop.units.senal_presion_presente.side_effect = RuntimeError("x")
    loop._tick()
    loop.set_do.set_output.assert_any_call(_CANAL, False)


def test_lazo_consulta_el_canal_de_pres_camara():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop._tick()
    loop.units.senal_presion_presente.assert_any_call(
        EstadoAutoclave.map_pres["pres_camara"], leido_mono=loop.estado_leido_mono)


@pytest.mark.parametrize("senal", [False, None])
def test_patch_rechazado_sin_senal_cruda(prueba, senal):
    client, ctx = prueba
    ctx.units.senal_presion_presente.return_value = senal
    r = client.patch("/io/test/output/aire_atmosferico_camara", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == aap.SIN_PRESION
    ctx.setdo.set_output.assert_not_called()


def test_patch_rechazado_si_units_lanza(prueba):
    client, ctx = prueba
    ctx.units.senal_presion_presente.side_effect = RuntimeError("x")
    r = client.patch("/io/test/output/aire_atmosferico_camara", json={"value": True})
    assert r.status_code == 409, r.text
    ctx.setdo.set_output.assert_not_called()


# ── Vigencia del estado publicado (SAF-01 / TMG-01 de la segunda revisión) ──
# La trama AI puede estar al día mientras el tick no llega a publicar estado
# (excepción antes del paso 1): presion_vigente exige además que el paso 1
# haya corrido hace a lo sumo _VIGENCIA_DI_SEG.

def test_presion_vigente_exige_estado_publicado_reciente():
    loop = _loop(_Estado(75.0, aire_on=False))
    assert loop.presion_vigente is False          # aún no se publicó estado
    loop._tick()
    assert loop.presion_vigente is True
    loop._estado_publicado_mono -= loop._VIGENCIA_DI_SEG + 0.1
    assert loop.presion_vigente is False


# ── Re-revisión de E1 (22-oct, SEN-01 Alto / TMG-01 / SAF-01 / SEN-02) ─────
# El contador cuenta tramas AI NUEVAS (ai_seq de SerialLink, mismo criterio
# que S1 para la mediana), no las líneas DI/DO/ST que notifican con la misma AI.

def _trama_seq(u, raw_canal, seq, **extra):
    raw = [0] * 16
    raw[8 + 0] = raw_canal
    u.update_from_serial({"ai": raw, "ai_seq": seq, **extra})


def _units_seq():
    from autoclave.hal.measures.units import Units
    u = Units()
    u._config.calibration.factory.pressure[0].adc_min = 5
    return u


def test_units_lineas_no_ai_no_suben_el_contador():
    from autoclave.hal.measures.units import Units
    u = _units_seq()
    _trama_seq(u, 2000, 1)
    for _ in range(4 * Units.TRAMAS_SENAL_PRESION):     # DI, DO, ST... misma AI
        _trama_seq(u, 2000, 1)
    assert u.senal_presion_presente(0) is False
    for seq in range(2, Units.TRAMAS_SENAL_PRESION + 1):
        _trama_seq(u, 2000, seq)
    assert u.senal_presion_presente(0) is True


def test_units_ai_seq_cero_no_es_trama_real():
    from autoclave.hal.measures.units import Units
    u = _units_seq()
    for _ in range(2 * Units.TRAMAS_SENAL_PRESION):
        _trama_seq(u, 2000, 0)
    assert u.senal_presion_presente(0) is False


def test_units_desconexion_reinicia_el_contador():
    from autoclave.hal.measures.units import Units
    u = _units_seq()
    n = Units.TRAMAS_SENAL_PRESION
    for seq in range(1, n + 1):
        _trama_seq(u, 2000, seq)
    assert u.senal_presion_presente(0) is True
    _trama_seq(u, 2000, n, port_open=False)              # _disconnect() notifica
    assert u.senal_presion_presente(0) is False


def test_units_recargar_calibracion_reinicia_el_contador(tmp_path):
    from autoclave.hal.measures.units import Units
    u = _units_seq()
    for seq in range(1, Units.TRAMAS_SENAL_PRESION + 1):
        _trama_seq(u, 2000, seq)
    assert u.senal_presion_presente(0) is True
    with patch("autoclave.hal.measures.units.load_config", return_value=u._config):
        u.reload_calibration(tmp_path / "x.yaml")
    assert u.senal_presion_presente(0) is False


def test_units_estado_leido_antes_del_umbral_no_vale():
    """SAF-01/TMG-02: la presión publicada debe haberse leído de Units
    después de que la señal cumplió las tramas seguidas."""
    import time
    from autoclave.hal.measures.units import Units
    u = _units_seq()
    leido_antes = time.monotonic()
    for seq in range(1, Units.TRAMAS_SENAL_PRESION + 1):
        _trama_seq(u, 2000, seq)
    assert u.senal_presion_presente(0) is True
    assert u.senal_presion_presente(0, leido_mono=leido_antes) is False
    assert u.senal_presion_presente(0, leido_mono=time.monotonic()) is True
    assert u.senal_presion_presente(0, leido_mono="x") is False


def test_senal_camara_pasa_el_instante_de_lectura():
    units = MagicMock()
    units.senal_presion_presente.return_value = True
    assert aap.senal_camara(units, leido_mono=12.5) is True
    units.senal_presion_presente.assert_called_with(
        EstadoAutoclave.map_pres["pres_camara"], leido_mono=12.5)


def test_lazo_pasa_el_instante_de_lectura_del_estado():
    loop = _loop(_Estado(75.0, aire_on=True))
    loop._tick()
    kwargs = loop.units.senal_presion_presente.call_args.kwargs
    assert kwargs["leido_mono"] == loop.estado_leido_mono
    assert isinstance(loop.estado_leido_mono, float)


def test_serial_link_numera_las_tramas_ai():
    from autoclave.protocols.serial_link import SerialLink
    link = SerialLink.__new__(SerialLink)
    import threading
    link.data_lock = threading.Lock()
    link.data = {"ai": [0] * 16, "ai_seq": 0}
    link._ultima_ai_mono = None
    link._procesar_payload("AI:" + ",".join(["1"] * 16))
    link._procesar_payload("AI:" + ",".join(["2"] * 16))
    assert link.data["ai_seq"] == 2


def test_senal_camara_sin_instante_de_lectura_rechaza():
    units = MagicMock()
    units.senal_presion_presente.return_value = True
    assert aap.senal_camara(units) is False
    assert aap.senal_camara(units, leido_mono=None) is False
