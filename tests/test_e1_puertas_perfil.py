# tests/test_e1_puertas_perfil.py
#
# E1-2 (CR-FC-02, PF-14 / V-05): PREPARACION, PREPARADO y CICLO revisan las
# puertas que declara el perfil (door_count) y, con door_type=simple, no
# revisan presión de empaque. door_type=advanced conserva el comportamiento.

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.profile import numero_puertas, revisa_empaque
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state


def _perfil(door_count=2, door_type=DoorType.SIMPLE):
    return SimpleNamespace(door_count=door_count, door_type=door_type, supply_inputs=None)


def test_numero_puertas_y_empaque_por_perfil():
    assert numero_puertas(_perfil(1)) == 1
    assert numero_puertas(_perfil(2)) == 2
    assert numero_puertas(None) == 2              # sin perfil: como antes
    assert revisa_empaque(_perfil(door_type=DoorType.SIMPLE)) is False
    assert revisa_empaque(_perfil(door_type=DoorType.ADVANCED)) is True
    assert revisa_empaque(None) is True


def _estado(p1=1, p2=1, emp1=300.0, emp2=300.0):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": emp1, "pres_empaque_2": emp2}
    estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
                            "temp_drenaje": 25.0}
    estado.sensores_di = {"puerta_1_cerrada": p1, "puerta_2_cerrada": p2,
                          "agua_bomba": 1, "agua_generador": 1, "aire_comprimido": 1,
                          "vapor_suministro": 1, "suministro_electrico": 1,
                          "paro_emergencia": 1, "agua_camara": 0}
    estado.get_flag.return_value = False
    return estado


def _cycle():
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }.get(n, k.get("default"))
    return cycle


def _config():
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0, "presion_empaque": 300,
    }.get(k)
    return cfg


def _reportadas(alarm_mgr):
    return [c.args[0].id for c in alarm_mgr.report.call_args_list]


# ---------------------------------------------------------------------------
# PREPARADO: puertas_cerradas()
# ---------------------------------------------------------------------------

def test_una_puerta_ignora_la_segunda():
    am = MagicMock()
    p = preparado_state(am, _estado(p1=1, p2=0), MagicMock(), _cycle(), _config(),
                        profile=_perfil(door_count=1))
    assert p.puertas_cerradas() is True
    assert "PUERTA_2_ABIERTA" not in _reportadas(am)


@pytest.mark.parametrize("door_type", [DoorType.SIMPLE, DoorType.ADVANCED])
def test_dos_puertas_segunda_abierta_bloquea(door_type):
    am = MagicMock()
    p = preparado_state(am, _estado(p1=1, p2=0), MagicMock(), _cycle(), _config(),
                        profile=_perfil(door_count=2, door_type=door_type))
    assert p.puertas_cerradas() is False
    assert "PUERTA_2_ABIERTA" in _reportadas(am)


def test_una_puerta_abierta_bloquea_con_alarma_de_siempre():
    am = MagicMock()
    p = preparado_state(am, _estado(p1=0, p2=1), MagicMock(), _cycle(), _config(),
                        profile=_perfil(door_count=1))
    assert p.puertas_cerradas() is False
    assert "PUERTA_1_ABIERTA" in _reportadas(am)


# ---------------------------------------------------------------------------
# Sensores de empaque en PREPARACION / PREPARADO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_simple_sin_sensores_de_empaque_no_bloquea(clase):
    am = MagicMock()
    p = clase(am, _estado(emp1=0, emp2=0), MagicMock(), _cycle(), _config(),
              profile=_perfil(door_type=DoorType.SIMPLE))
    assert p.verificar_sensores() is True
    assert not [a for a in _reportadas(am) if "EMPAQUE" in a]


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("perfil", [None, _perfil(door_type=DoorType.ADVANCED)],
                         ids=["sin_perfil", "advanced"])
def test_advanced_sin_empaque_bloquea_como_antes(clase, perfil):
    am = MagicMock()
    p = clase(am, _estado(emp1=0, emp2=0), MagicMock(), _cycle(), _config(), profile=perfil)
    assert p.verificar_sensores() is False
    ids = _reportadas(am)
    assert "ERROR_AI_PRES_EMPAQUE_1" in ids and "ERROR_AI_PRES_EMPAQUE_2" in ids


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_advanced_una_puerta_no_exige_empaque_2(clase):
    am = MagicMock()
    p = clase(am, _estado(emp1=300.0, emp2=0), MagicMock(), _cycle(), _config(),
              profile=_perfil(door_count=1, door_type=DoorType.ADVANCED))
    assert p.verificar_sensores() is True
    assert "ERROR_AI_PRES_EMPAQUE_2" not in _reportadas(am)


# ---------------------------------------------------------------------------
# CICLO: _verificar_puertas()
# ---------------------------------------------------------------------------

def _ciclo(perfil, **kw):
    ciclo = CicloState(_estado(**kw), MagicMock(), _cycle(), _config(), MagicMock(),
                       profile=perfil)
    ciclo.reset()
    return ciclo


@pytest.mark.parametrize("emp", [0.0, None])
def test_ciclo_simple_sin_empaque_no_falla(emp):
    ciclo = _ciclo(_perfil(door_type=DoorType.SIMPLE), emp1=emp, emp2=emp)
    assert ciclo._verificar_puertas() == (True, "")


def test_ciclo_una_puerta_ignora_la_segunda():
    ciclo = _ciclo(_perfil(door_count=1), p2=0)
    assert ciclo._verificar_puertas() == (True, "")


@pytest.mark.parametrize("door_type", [DoorType.SIMPLE, DoorType.ADVANCED])
def test_ciclo_puerta_2_abierta_falla(door_type):
    ciclo = _ciclo(_perfil(door_type=door_type), p2=0)
    assert ciclo._verificar_puertas() == (False, "FALLO_PUERTA_2_ABIERTA")
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert "FALLO_PUERTA_2_ABIERTA" in _reportadas(ciclo.alarm_manager)


@pytest.mark.parametrize("perfil", [None, _perfil(door_type=DoorType.ADVANCED)],
                         ids=["sin_perfil", "advanced"])
def test_ciclo_advanced_empaque_bajo_falla_como_antes(perfil):
    ciclo = _ciclo(perfil, emp1=100.0)
    assert ciclo._verificar_puertas() == (False, "FALLO_PUERTA_1_EMPAQUE")


def test_ciclo_simple_primer_tick_sin_fallo_de_puerta():
    ciclo = _ciclo(_perfil(door_type=DoorType.SIMPLE), emp1=0.0, emp2=0.0)
    ciclo.run()
    assert not ciclo.estado.fase_ciclo.startswith("FALLO_PUERTA")
