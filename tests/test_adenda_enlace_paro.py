# tests/test_adenda_enlace_paro.py
#
# Adenda E0/E1 (docs/mis_plans/instruccion_claude_code_e0_e1_adenda.md),
# enlace, paro y modo prueba (las pruebas del sello DI en SerialLink se
# retiraron con el enlace serial en la tanda 20, T20-03):
#   A-3 (TMG-01, SAF-06)  vigencia de la trama DI: vencida = paro
#   A-6 (SAF-07)          aviso si llega puerta_2_cerrada=1 con door_count=1
#   A-7 (TMG-09)          ALL_OFF con el paro, a lo sumo 1/s salvo salidas activas
#   A-8 (TMG-05)          modo prueba rechazado con el enlace caído o datos viejos
#   A-9 (TMG-11)          suministro eléctrico sin get(..., 1)

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from tests.helpers.backend_doble import modulo_backend


# ---------------------------------------------------------------------------
# A-3: ControlLoop publica paro si la trama DI venció o el enlace está caído
# ---------------------------------------------------------------------------

def _loop(estado=None, profile=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = estado or EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock(), profile=profile)
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = True
    return loop, estado


@pytest.mark.parametrize("edad,paro", [(0.0, False), (1.4, False), (1.5, False),
                                       (1.51, True), (10.0, True), (None, True)])
def test_vigencia_de_la_trama_di(edad, paro):
    loop, estado = _loop()
    loop.link.edad_ultima_di.return_value = edad
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is paro


def test_enlace_sin_sello_di_es_paro():
    # un enlace que no informa la edad de la trama DI no se da por vigente
    loop, estado = _loop()
    loop.link.edad_ultima_di.return_value = "no numérico"
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is True


def test_paro_se_publica_mientras_el_enlace_esta_caido():
    loop, estado = _loop()
    loop.link.edad_ultima_di.return_value = 0.1
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is False
    loop.link.is_connected.return_value = False
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is True


def test_datos_vigentes():
    loop, _ = _loop()
    loop.link.edad_ultima_di.return_value = 0.2
    loop._tick()
    assert loop.datos_vigentes is True
    loop.link.edad_ultima_di.return_value = 3.0
    assert loop.datos_vigentes is False
    loop.link.edad_ultima_di.return_value = 0.2
    loop.link.is_connected.return_value = False
    loop._tick()
    assert loop.datos_vigentes is False


# ---------------------------------------------------------------------------
# A-9: suministro eléctrico sin valor por defecto 1
# ---------------------------------------------------------------------------

def test_suministro_electrico_ausente_en_la_trama_es_fallo():
    loop, estado = _loop()
    loop.link.edad_ultima_di.return_value = 0.1
    del estado.sensores_di["suministro_electrico"]
    loop._tick()
    assert estado.get_flag("FALLO_SUMINISTRO_ELECTRICO") is True


# ---------------------------------------------------------------------------
# A-6 (SAF-07): puerta 2 cerrada con door_count=1
# ---------------------------------------------------------------------------

def _avisos(caplog):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and "puerta_2_cerrada" in r.getMessage()]


def test_aviso_puerta_2_con_una_puerta_declarada(caplog):
    loop, estado = _loop(profile=SimpleNamespace(door_count=1))
    loop.link.edad_ultima_di.return_value = 0.1
    estado.sensores_di["puerta_2_cerrada"] = 1
    with caplog.at_level(logging.WARNING):
        loop._tick()
        loop._tick()
    assert len(_avisos(caplog)) == 1       # una vez por flanco, no por tick


def test_aviso_puerta_2_se_repite_tras_un_nuevo_flanco(caplog):
    loop, estado = _loop(profile=SimpleNamespace(door_count=1))
    loop.link.edad_ultima_di.return_value = 0.1
    with caplog.at_level(logging.WARNING):
        estado.sensores_di["puerta_2_cerrada"] = 1
        loop._tick()
        estado.sensores_di["puerta_2_cerrada"] = 0
        loop._tick()
        estado.sensores_di["puerta_2_cerrada"] = 1
        loop._tick()
    assert len(_avisos(caplog)) == 2


@pytest.mark.parametrize("perfil", [SimpleNamespace(door_count=2), None])
def test_sin_aviso_con_dos_puertas(caplog, perfil):
    loop, estado = _loop(profile=perfil)
    loop.link.edad_ultima_di.return_value = 0.1
    estado.sensores_di["puerta_2_cerrada"] = 1
    with caplog.at_level(logging.WARNING):
        loop._tick()
    assert _avisos(caplog) == []


# ---------------------------------------------------------------------------
# A-7: ALL_OFF con el paro, limitado
# ---------------------------------------------------------------------------

def _setdo(salidas=None):
    from autoclave.devices.io.set_io import SetOutput
    estado = MagicMock()
    estado.salidas_do = dict(salidas or {"vapor_chaqueta": 0, "buzer_alarma": 0})
    io = MagicMock()
    io.all_off.return_value = True
    return SetOutput(io, estado), io, estado


def test_paro_primer_all_off_se_envia():
    setdo, io, _ = _setdo()
    with patch("autoclave.devices.io.set_io.time.monotonic", return_value=10.0):
        setdo.apagar_por_paro()
    io.all_off.assert_called_once()


def test_paro_no_repite_all_off_antes_de_un_segundo_sin_salidas_activas():
    setdo, io, _ = _setdo()
    with patch("autoclave.devices.io.set_io.time.monotonic", side_effect=[10.0, 10.5, 10.99]):
        setdo.apagar_por_paro()
        setdo.apagar_por_paro()
        setdo.apagar_por_paro()
    assert io.all_off.call_count == 1


def test_paro_repite_all_off_cada_segundo():
    setdo, io, _ = _setdo()
    with patch("autoclave.devices.io.set_io.time.monotonic", side_effect=[10.0, 11.0, 11.5, 12.0]):
        for _ in range(4):
            setdo.apagar_por_paro()
    assert io.all_off.call_count == 3


def test_paro_repite_all_off_si_el_do_reportado_tiene_una_salida_activa():
    setdo, io, estado = _setdo()
    with patch("autoclave.devices.io.set_io.time.monotonic", side_effect=[10.0, 10.5]):
        setdo.apagar_por_paro()
        estado.salidas_do["vapor_chaqueta"] = 1
        setdo.apagar_por_paro()
    assert io.all_off.call_count == 2


def test_paro_el_buzzer_no_cuenta_como_salida_activa():
    setdo, io, estado = _setdo()
    with patch("autoclave.devices.io.set_io.time.monotonic", side_effect=[10.0, 10.5]):
        setdo.apagar_por_paro()
        estado.salidas_do["buzer_alarma"] = 1
        setdo.apagar_por_paro()
    assert io.all_off.call_count == 1


def test_paro_sin_do_reportado_se_asume_activo():
    setdo, io, estado = _setdo()
    estado.salidas_do = None
    with patch("autoclave.devices.io.set_io.time.monotonic", side_effect=[10.0, 10.5]):
        setdo.apagar_por_paro()
        setdo.apagar_por_paro()
    assert io.all_off.call_count == 2


def test_reset_all_outputs_no_se_limita():
    setdo, io, _ = _setdo()
    setdo.reset_all_outputs()
    setdo.reset_all_outputs()
    assert io.all_off.call_count == 2


def _estado_paro():
    e = MagicMock()
    e.get_flag.side_effect = lambda f: f == "PARO_EMERGENCIA"
    return e


@pytest.mark.parametrize("construir", [
    lambda e, s: __import__("autoclave.state_machine.states.preparacion",
                            fromlist=["x"]).preparacion_state(MagicMock(), e, s, MagicMock(), MagicMock()),
    lambda e, s: __import__("autoclave.state_machine.states.preparado",
                            fromlist=["x"]).preparado_state(MagicMock(), e, s, MagicMock(), MagicMock()),
    lambda e, s: __import__("autoclave.state_machine.states.falla",
                            fromlist=["x"]).FallaState(e, s, MagicMock()),
], ids=["preparacion", "preparado", "falla"])   # P-8: HIBERNACION retirado
def test_estados_con_paro_usan_el_apagado_limitado(construir):
    set_do = MagicMock()
    construir(_estado_paro(), set_do).run()
    set_do.apagar_por_paro.assert_called()
    set_do.reset_all_outputs.assert_not_called()


def test_buzzer_usa_reloj_monotonico():
    from autoclave.devices.buzer import buzer
    on, off = MagicMock(), MagicMock()
    player = buzer.BuzzerPlayer(on, off)
    reloj = MagicMock()
    reloj.monotonic.side_effect = [100.0, 100.0, 100.3]
    reloj.time.side_effect = AssertionError("no debe usar time.time()")
    with patch.object(buzer, "time", reloj):
        player.play([(1, 0.2), (0, 0.2)])
        player.update()                     # 0 s: sigue en el primer paso
        player.update()                     # 0.3 s: avanza
    assert player.index == 1


# ---------------------------------------------------------------------------
# A-8: modo prueba rechazado con el enlace caído o datos viejos
# ---------------------------------------------------------------------------

@pytest.fixture
def entorno_prueba():
    from autoclave.devices.puertas.enum_doors import DoorState
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_pres = {"pres_camara": 101.0}
    ctx.estado.sensores_di = {"puerta_cerrada_1": 1, "puerta_abierta_1": 0}
    ctx.estado.get_door_state.return_value = DoorState.CERRADO
    ctx.config_manager.get.side_effect = {"presion_admosferica": 101.3,
                                          "rango_presion_atm": 5.0}.get
    puerta = MagicMock()
    puerta.name = "Puerta 1"
    puerta.di = {"cerrada": "puerta_cerrada_1", "abierta": "puerta_abierta_1"}
    ctx.doors = [puerta]
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.desconectado = False
    ctx.control_loop.datos_vigentes = True
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    modulo_backend("rutas.io")._token_modo_prueba = cab["Authorization"].split()[1]
    from fastapi.testclient import TestClient
    return TestClient(srv.app, headers=cab), ctx, srv


@pytest.mark.parametrize("desconectado,vigentes", [(True, True), (False, False), (True, False)])
def test_enter_rechazado_sin_enlace_o_con_datos_viejos(entorno_prueba, desconectado, vigentes):
    client, ctx, srv = entorno_prueba
    ctx.control_loop.test_mode_active = False
    modulo_backend("rutas.io")._token_modo_prueba = None
    ctx.control_loop.desconectado = desconectado
    ctx.control_loop.datos_vigentes = vigentes
    resp = client.post("/io/test/enter")
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "sin_conexion_modulo_es"
    ctx.control_loop.enter_test_mode.assert_not_called()


def test_enter_con_enlace_vigente_entra(entorno_prueba):
    client, ctx, srv = entorno_prueba
    ctx.control_loop.test_mode_active = False
    modulo_backend("rutas.io")._token_modo_prueba = None
    assert client.post("/io/test/enter").status_code == 200
    ctx.control_loop.enter_test_mode.assert_called_once()


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.parametrize("desconectado,vigentes", [(True, True), (False, False)])
def test_output_rechazado_sin_enlace_o_con_datos_viejos(entorno_prueba, value,
                                                        desconectado, vigentes):
    client, ctx, _ = entorno_prueba
    ctx.control_loop.desconectado = desconectado
    ctx.control_loop.datos_vigentes = vigentes
    resp = client.patch("/io/test/output/vapor_camara", json={"value": value})
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "sin_conexion_modulo_es"
    ctx.setdo.set_output.assert_not_called()


def test_output_con_enlace_vigente_acciona(entorno_prueba):
    client, ctx, _ = entorno_prueba
    assert client.patch("/io/test/output/vapor_camara", json={"value": True}).status_code == 200
    ctx.setdo.set_output.assert_called_once()
