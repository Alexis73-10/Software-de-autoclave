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
    assert aap.evaluar(_estado(pres), _CONFIG) == (True, "")


@pytest.mark.parametrize("pres", [80.1, 120.0, 300.0])
def test_rechazado_con_la_camara_por_encima_de_atm_mas_brecha(pres):
    assert aap.evaluar(_estado(pres), _CONFIG) == (False, aap.CON_PRESION)


# 0,0 kPa es lo que hoy entrega un lazo de 4-20 mA abierto (recorte de
# convert_pressures): piso físico de 1 kPa absoluto (revisión SEN-01)
@pytest.mark.parametrize("pres", [None, float("nan"), "x", True, 0.0, 0.99, -3.0])
def test_rechazado_sin_lectura_de_presion(pres):
    assert aap.evaluar(_estado(pres), _CONFIG) == (False, aap.SIN_PRESION)


@pytest.mark.parametrize("config", [{}, {"presion_atmosferica": 75.0},
                                    {"presion_atmosferica": None, "rango_presion_atm": 5.0}])
def test_rechazado_sin_referencia_atmosferica(config):
    assert aap.evaluar(_estado(75.0), config) == (False, aap.SIN_REFERENCIA)


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
    loop.set_do.set_output.assert_not_called()
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
