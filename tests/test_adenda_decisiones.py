# tests/test_adenda_decisiones.py
#
# Decisiones de Cristian sobre las preguntas de la adenda E0/E1 (2026-10-12):
#   P1  temp_drenaje_cam ya no existe; su entrada (posición 4) la ocupa
#       temp_drenaje. La posición 5 queda sin sensor.
#   P3  tras (re)conectar, la máquina de estados no corre hasta la primera
#       trama DI de la nueva conexión (máximo _VIGENCIA_DI_SEG).
#   P4  las salidas seguras del supervisor (A-2.2) se aplican también cuando
#       falla un suministro, no solo un sensor.

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.installation.profile import TEMPERATURE_PROBE_KEYS, validate_profile_data
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state


# ---------------------------------------------------------------------------
# P1: temp_drenaje en la posición 4; temp_drenaje_cam retirado
# ---------------------------------------------------------------------------

def test_mapa_de_temperaturas_sin_drenaje_de_camara():
    assert EstadoAutoclave.map_temp == {
        "temp_camara": 0, "temp_2_camara": 1, "temp_ref": 2, "temp_drenaje": 4,
    }


def test_temp_drenaje_se_lee_de_la_posicion_4():
    estado = EstadoAutoclave()
    estado.update({"temperature": [121.0, 120.5, 119.0, 99.9, 60.0, 40.0, 0.0, 0.0]})
    assert estado.sensores_temp["temp_drenaje"] == 60.0
    assert "temp_drenaje_cam" not in estado.sensores_temp


def test_sondas_del_perfil_son_las_cuatro_cableadas():
    assert TEMPERATURE_PROBE_KEYS == ("temp_camara", "temp_2_camara", "temp_ref", "temp_drenaje")


def test_perfil_con_temp_drenaje_cam_es_invalido():
    data = {
        "machine_id": "ACV-2026-SN1", "model_id": "SPK", "serial_number": "SN1",
        "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
        "cooling_level": 0, "door_id": 1, "role": "operator_front",
        "created_at": "2026-05-25T05:49:47", "locked": True,
        "temperature_probes": {"temp_drenaje_cam": False},
    }
    assert validate_profile_data(data) != []


def test_preparacion_no_vigila_temp_drenaje_cam():
    am = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0,
                            "temp_ref": 25.0, "temp_drenaje": 25.0}
    p = preparacion_state(am, estado, MagicMock(), MagicMock(), MagicMock())
    assert p.verificar_sensores() is True
    assert "ERROR_AI_TEMP_DRENAJE_CAM" not in [c.args[0].id for c in am.report.call_args_list]


# ---------------------------------------------------------------------------
# P3: sin máquina de estados hasta la primera DI de la nueva conexión
# ---------------------------------------------------------------------------

def _loop(estado_maquina=GlobalState.CICLO):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[MagicMock()],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock())
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    estado.get_machine_state = lambda: estado_maquina
    return loop, estado


def _reconectar(loop, reloj, edad):
    """Un tick desconectado y uno reconectado con `edad` de la trama DI."""
    loop.link.is_connected.return_value = False
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic", return_value=reloj):
        loop._tick()
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = edad
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic", return_value=reloj + 0.5):
        loop._tick()


def test_tras_reconectar_sin_di_no_corre_la_maquina_de_estados():
    loop, estado = _loop()
    _reconectar(loop, 100.0, edad=None)
    loop.state_machine.update.assert_not_called()
    loop.doors[0].update.assert_not_called()
    loop.set_do.buzer.update.assert_not_called()
    assert estado.get_flag("PARO_EMERGENCIA") is True          # flag publicado para la UI


def test_tras_reconectar_sin_di_no_marca_fallo_de_suministro():
    # di quedó en 0 al reconectar: sin la espera se leería "sin suministro"
    loop, estado = _loop()
    estado.sensores_di["suministro_electrico"] = 0
    _reconectar(loop, 100.0, edad=None)
    assert estado.get_flag("FALLO_SUMINISTRO_ELECTRICO") is False


def test_con_la_primera_di_la_maquina_de_estados_vuelve_a_correr():
    loop, estado = _loop()
    _reconectar(loop, 100.0, edad=None)
    loop.link.edad_ultima_di.return_value = 0.1
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic", return_value=101.0):
        loop._tick()
    loop.state_machine.update.assert_called_once()
    assert estado.get_flag("PARO_EMERGENCIA") is False


def test_si_la_di_no_llega_en_la_vigencia_se_corre_con_paro():
    # pasado _VIGENCIA_DI_SEG sin DI: "sin datos de las entradas = paro" y la
    # máquina de estados corre para aplicarlo
    loop, estado = _loop()
    _reconectar(loop, 100.0, edad=None)
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic", return_value=102.1):
        loop._tick()
    loop.state_machine.update.assert_called_once()
    assert estado.get_flag("PARO_EMERGENCIA") is True


def test_di_vieja_dentro_de_la_conexion_no_pausa_la_maquina_de_estados():
    # la espera solo aplica antes de la primera DI; una DI que deja de llegar
    # sigue siendo paro con la máquina de estados corriendo (A-3)
    loop, estado = _loop()
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 5.0
    loop._tick()
    loop.state_machine.update.assert_called_once()
    assert estado.get_flag("PARO_EMERGENCIA") is True


# ---------------------------------------------------------------------------
# P4: salidas seguras también con falla de suministro
# ---------------------------------------------------------------------------

def _make(clase, **di_overrides):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 60.0, "pres_chaqueta": 200.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0,
                            "temp_ref": 25.0, "temp_drenaje": 90.0}
    estado.sensores_di = {"paro_emergencia": 1, "agua_bomba": 1, "agua_generador": 1,
                          "aire_comprimido": 1, "vapor_suministro": 1,
                          "suministro_electrico": 1, "agua_camara": 0,
                          "puerta_1_cerrada": 1, "puerta_2_cerrada": 1, **di_overrides}
    estado.get_flag.return_value = False
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {"presion_admosferica": 101.3, "rango_presion_atm": 20.0,
                                     "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
                                     "tiempo_estable_alarma": 0}.get(k)
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0}.get(n)
    set_do = MagicMock()
    return clase(MagicMock(), estado, set_do, cycle, cfg), set_do


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("suministro", ["agua_bomba", "agua_generador", "aire_comprimido"])
def test_falla_de_suministro_apaga_vapor_y_sigue_con_los_demas_lazos(clase, suministro):
    obj, set_do = _make(clase, **{suministro: 0})
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()          # chaqueta fría, pero sin control
    set_do.aire_admosferico_camara_on.assert_called()     # presión de cámara sigue
    set_do.agua_intercambiador_on.assert_called()         # enfriamiento de drenaje sigue


def test_preparado_falla_electrica_apaga_vapor():
    obj, set_do = _make(preparado_state, suministro_electrico=0)
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
