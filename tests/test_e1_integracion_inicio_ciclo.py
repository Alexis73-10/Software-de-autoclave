# tests/test_e1_integracion_inicio_ciclo.py
#
# E1 (§11 prueba 1 y 11 de la spec): equipo de piso de laboratorio con 2
# puertas simples, sin sensores de empaque y solo aire comprimido cableado.
# PREPARACION → PREPARADO → CICLO sin FALLO_PUERTA_* ni alarmas de suministro.

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.door_type import DoorType
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine

_SOLO_AIRE = {"agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
              "vapor_suministro": False, "suministro_electrico": False}


def _estado_listo():
    estado = EstadoAutoclave()
    estado.sensores_pres.update({"pres_camara": 101.3, "pres_chaqueta": 300.0,
                                 "pres_empaque_1": 0.0, "pres_empaque_2": 0.0})
    estado.sensores_temp.update({k: 25.0 for k in estado.sensores_temp})
    # Entradas sin cablear leen 0; aire comprimido presente; paro NC cerrado
    estado.sensores_di.update({"aire_comprimido": 1, "paro_emergencia": 1,
                               "puerta_1_cerrada": 1, "puerta_2_cerrada": 1})
    return estado


from tests.helpers.alarmas_helpers import ids_viejos_activos


def _maquina(estado, perfil):
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }.get(n, k.get("default"))
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0, "presion_empaque": 300, "temp_max_apertura": 80.0,
    }.get(k)
    return StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                        config=config, profile=perfil)


def _ids(sm):
    return ids_viejos_activos(sm.alarm_manager)


def test_simple_sin_empaque_solo_aire_inicia_ciclo():
    estado = _estado_listo()
    sm = _maquina(estado, SimpleNamespace(door_count=2, door_type=DoorType.SIMPLE,
                                          supply_inputs=_SOLO_AIRE))
    sm.update()                                    # PREPARACION → PREPARADO
    assert estado.get_machine_state() == GlobalState.PREPARADO
    sm.update()                                    # PREPARADO listo
    assert estado.get_flag("LISTO_PARA_CICLO") is True
    estado.set_flag("START_CICLO", True)
    sm.update()                                    # → CICLO
    assert estado.get_machine_state() == GlobalState.CICLO
    sm.update()                                    # primer tick de CICLO
    assert not estado.fase_ciclo.startswith("FALLO_PUERTA")
    assert not [i for i in _ids(sm) if i.startswith("SUMINISTRO") or "EMPAQUE" in i]


def test_mismo_equipo_sin_perfil_queda_bloqueado_como_antes():
    estado = _estado_listo()
    sm = _maquina(estado, None)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION
    ids = _ids(sm)
    assert "ERROR_AI_PRES_EMPAQUE_1" in ids
    assert "SUMINISTRO_AGUA_BOMBA" in ids
