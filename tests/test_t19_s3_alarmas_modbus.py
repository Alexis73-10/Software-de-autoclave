"""Tanda 19 (P-s3, MOD-12): las alarmas nuevas del enlace Modbus
(TARJETA_CONFIG_SEGURIDAD, TARJETA_MODULOS_ORDEN) reciben en el ControlLoop el
mismo manejo que TARJETA_ALL_OFF_SIN_CONFIRMAR: en la conexión, FALLA
bloqueante que resuelve el evento "conectada"; en operación dentro de CICLO,
aborto con COM-03 y el id como origen y causa; fuera de ciclo, alarma
bloqueante. Mismo estilo que tests/test_e6_control_loop_modulo_es.py."""

from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.protocols.enlace import ALARMAS_MODBUS, EventoTarjeta
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_03, Nivel
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

pytestmark = pytest.mark.req("MOD-12")

_REFERENCIA = "TARJETA_ALL_OFF_SIN_CONFIRMAR"
_IDS = ["TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN", _REFERENCIA]


def _loop(estado_maquina=GlobalState.PREPARADO, conectado=True):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=AlarmManager(), cycle_manager=cm,
                           config_manager=MagicMock())
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = conectado
    loop.link.puerto_presente.return_value = True     # socket TCP abierto
    loop.link.edad_ultima_di.return_value = 0.1
    loop.link.tomar_eventos.return_value = []
    estado.get_machine_state = MagicMock(return_value=estado_maquina)
    return loop, estado


def _make_ciclo(alarm_manager):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0}
    estado.get_flag.return_value = False
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    ciclo = CicloState(estado, MagicMock(), cycle, config, alarm_manager)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, estado


def _activa(loop, codigo):
    return next((a for a in loop.alarm_manager.activas() if a.codigo == codigo), None)


def test_las_alarmas_nuevas_son_las_del_enlace_modbus():
    assert set(ALARMAS_MODBUS) == {"TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"}


def _resumen_conexion(alarm_id):
    """Fallo de la conexión (origen handshake) y luego "conectada"."""
    loop, _ = _loop(GlobalState.PREPARADO, conectado=False)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("handshake", alarm_id, "detalle")]
    loop._tick()
    alarma = _activa(loop, alarm_id)
    antes = (alarma.nivel, alarma.definicion.bloquea_inicio, alarma.descripcion,
             loop.alarm_manager.has_blocking_alarm())
    loop.link.is_connected.return_value = True
    loop.link.tomar_eventos.return_value = [EventoTarjeta("conectada", None, "ok")]
    loop._tick()
    inst = loop.alarm_manager.obtener(alarm_id)
    despues = (loop.alarm_manager.has_blocking_alarm(),
               inst is None or inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER)
    return antes, despues


@pytest.mark.parametrize("alarm_id", _IDS)
def test_fallo_de_conexion_bloquea_el_inicio_y_lo_resuelve_conectada(alarm_id):
    antes, despues = _resumen_conexion(alarm_id)
    assert antes == (Nivel.ALARMA, True, "detalle", True)
    assert despues == (False, True)


@pytest.mark.parametrize("alarm_id", ["TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"])
def test_conexion_igual_que_all_off_sin_confirmar(alarm_id):
    assert _resumen_conexion(alarm_id) == _resumen_conexion(_REFERENCIA)


@pytest.mark.parametrize("alarm_id", _IDS)
def test_fallo_de_conexion_bloquea_el_inicio_del_ciclo(alarm_id):
    loop, _ = _loop(GlobalState.PREPARADO, conectado=False)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("handshake", alarm_id, "m")]
    loop._tick()
    assert any(a.codigo == alarm_id and a.definicion.bloquea_inicio
               for a in loop.alarm_manager.activas())
    assert loop.alarm_manager.has_blocking_alarm()


def _resumen_en_ciclo(alarm_id):
    """Evento de operación en CICLO con un CicloState real."""
    loop, _ = _loop(GlobalState.CICLO)
    ciclo, estado_ciclo = _make_ciclo(loop.alarm_manager)
    loop.state_machine.ciclo = ciclo
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "motivo")]
    loop._tick()
    activas = loop.alarm_manager.activas()
    [alarma] = activas
    estado_ciclo.get_flag.side_effect = lambda f: f == "CICLO_CONFIRMADO"
    return {
        "codigo": alarma.codigo, "nivel": alarma.nivel,
        "origen_es_id": alarma.origen == alarm_id,
        "id_en_descripcion": alarm_id in alarma.descripcion,
        "fase": estado_ciclo.fase_ciclo, "codigo_fallo": estado_ciclo.codigo_fallo,
        "protocolo": ciclo._protocolo.ejecutar.call_count,
        "resultado": ciclo.run(),
        "handshake": loop.link.solicitar_handshake.call_count,
        "alarma_propia": _activa(loop, alarm_id) is not None,
    }


@pytest.mark.parametrize("alarm_id", _IDS)
def test_en_ciclo_lleva_a_com03_con_el_id_como_origen(alarm_id):
    r = _resumen_en_ciclo(alarm_id)
    assert r["codigo"] == COM_03 and r["nivel"] is Nivel.FALLO_CRITICO
    assert r["origen_es_id"] and r["id_en_descripcion"]
    assert r["fase"] == "FALLO_IO" and r["codigo_fallo"] == COM_03
    assert r["protocolo"] == 1
    assert r["resultado"] == CicloResultado.FALLO
    # en CICLO no se repite la conexión (decisión 8: el ALL_OFF cerraría el venteo)
    assert r["handshake"] == 0
    assert r["alarma_propia"] is False


@pytest.mark.parametrize("alarm_id", ["TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"])
def test_en_ciclo_igual_que_all_off_sin_confirmar(alarm_id):
    assert _resumen_en_ciclo(alarm_id) == _resumen_en_ciclo(_REFERENCIA)


@pytest.mark.parametrize("alarm_id", _IDS)
def test_en_ciclo_llama_abortar_por_falla_io(alarm_id):
    loop, _ = _loop(GlobalState.CICLO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "motivo")]
    loop._tick()
    loop.state_machine.ciclo.abortar_por_falla_io.assert_called_once_with(alarm_id, "motivo")


@pytest.mark.parametrize("alarm_id", _IDS)
def test_en_operacion_fuera_de_ciclo_es_alarma_bloqueante(alarm_id):
    loop, _ = _loop(GlobalState.PREPARADO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "m")]
    loop._tick()
    loop.state_machine.ciclo.abortar_por_falla_io.assert_not_called()
    alarma = _activa(loop, alarm_id)
    assert alarma.nivel is Nivel.ALARMA and alarma.definicion.bloquea_inicio is True
    # la resuelve la siguiente conexión verificada
    loop.link.tomar_eventos.return_value = [EventoTarjeta("conectada", None, "ok")]
    loop._tick()
    assert not loop.alarm_manager.has_blocking_alarm()


@pytest.mark.parametrize("alarm_id", ["TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"])
def test_en_operacion_fuera_de_ciclo_pide_nueva_conexion(alarm_id):
    # DECISIÓN SIN CONFIRMAR (P-s3): segunda barrera además de la invalidación
    # que hace el propio enlace Modbus.
    loop, _ = _loop(GlobalState.PREPARADO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "m")]
    loop._tick()
    loop.link.solicitar_handshake.assert_called_once()


@pytest.mark.parametrize("alarm_id", ["TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"])
def test_en_ciclo_terminando_se_reporta_sin_repetir_la_conexion(alarm_id):
    # TMG-07 / decisión 8: con el resultado ya pendiente, alarma propia y sin
    # nueva conexión mientras siga en CICLO.
    loop, _ = _loop(GlobalState.CICLO)
    loop.state_machine.ciclo.abortar_por_falla_io.return_value = False
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "m")]
    loop._tick()
    assert _activa(loop, alarm_id) is not None
    loop.link.solicitar_handshake.assert_not_called()


@pytest.mark.parametrize("alarm_id", _IDS)
def test_fallo_de_conexion_con_el_socket_cerrado_se_descarta(alarm_id):
    # TMG-02 de U4: sin puerto (socket TCP no abre) la causa es COM-01
    loop, _ = _loop(GlobalState.PREPARADO, conectado=False)
    loop.link.puerto_presente.return_value = False
    loop.link.tomar_eventos.return_value = [EventoTarjeta("handshake", alarm_id, "m")]
    loop._tick()
    assert _activa(loop, alarm_id) is None
