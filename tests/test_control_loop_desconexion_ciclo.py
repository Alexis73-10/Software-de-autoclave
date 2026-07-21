from unittest.mock import patch
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_connectivity_ticket import _make_loop, _run_one_tick


def test_desconexion_durante_ciclo_aborta_el_ciclo():
    loop = _make_loop()
    loop.link_was_connected = True
    loop._link_ever_connected = True
    loop.estado.get_machine_state = lambda: GlobalState.CICLO

    _run_one_tick(loop, connected=False)

    loop.state_machine.ciclo.abortar_por_desconexion.assert_called_once()


def test_desconexion_fuera_de_ciclo_no_aborta_nada():
    loop = _make_loop()
    loop.link_was_connected = True
    loop._link_ever_connected = True
    loop.estado.get_machine_state = lambda: GlobalState.PREPARACION

    _run_one_tick(loop, connected=False)

    loop.state_machine.ciclo.abortar_por_desconexion.assert_not_called()


def test_conexion_estable_en_ciclo_no_aborta_nada():
    loop = _make_loop()
    loop.estado.get_machine_state = lambda: GlobalState.CICLO

    _run_one_tick(loop, connected=True)

    loop.state_machine.ciclo.abortar_por_desconexion.assert_not_called()
