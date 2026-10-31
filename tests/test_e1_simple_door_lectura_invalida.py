# tests/test_e1_simple_door_lectura_invalida.py
#
# E1-3 (HAZ-FC-02, PF-04): una lectura inválida de la puerta simple se trata
# como puerta abierta (posición segura), no conserva el último estado.

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.devices.puertas.simple_door import SimpleDoor


def _puerta(estado):
    return SimpleDoor("Puerta 1", {"cerrada": "puerta_1_cerrada",
                                   "abierta": "puerta_1_abierta"}, estado)


def test_lectura_none_tras_cerrada_pasa_a_abierta():
    estado = EstadoAutoclave()
    puerta = _puerta(estado)
    estado.sensores_di["puerta_1_cerrada"] = 1
    puerta.update()
    assert estado.get_door_state("Puerta 1") == DoorState.CERRADO

    estado.sensores_di["puerta_1_cerrada"] = None
    puerta.update()
    assert estado.get_door_state("Puerta 1") == DoorState.ABIERTO


def test_entrada_ausente_es_abierta():
    estado = EstadoAutoclave()
    del estado.sensores_di["puerta_1_cerrada"]
    puerta = _puerta(estado)
    puerta.update()
    assert estado.get_door_state("Puerta 1") == DoorState.ABIERTO
    assert not puerta.can_start_cycle()


def test_lecturas_validas_sin_cambio():
    estado = EstadoAutoclave()
    puerta = _puerta(estado)
    estado.sensores_di["puerta_1_cerrada"] = 0
    puerta.update()
    assert estado.get_door_state("Puerta 1") == DoorState.ABIERTO
    estado.sensores_di["puerta_1_cerrada"] = 1
    puerta.update()
    assert estado.get_door_state("Puerta 1") == DoorState.CERRADO
