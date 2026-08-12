from unittest.mock import patch
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_connectivity_ticket import _make_loop, _run_one_tick


def test_desconexion_breve_dentro_de_la_tolerancia_no_aborta():
    """Una caída de menos de la tolerancia (p.ej. ruido momentáneo en el
    serial) no debe tirar el ciclo entero."""
    loop = _make_loop()
    loop.link_was_connected = True
    loop._link_ever_connected = True
    loop.estado.get_machine_state = lambda: GlobalState.CICLO
    loop.link.is_connected.return_value = False

    with patch("time.monotonic", side_effect=[0.0, 1.0, 2.0]):
        loop._tick()
        loop._tick()
        loop._tick()

    loop.state_machine.ciclo.abortar_por_desconexion.assert_not_called()


def test_desconexion_sostenida_mas_alla_de_la_tolerancia_aborta():
    loop = _make_loop()
    loop.link_was_connected = True
    loop._link_ever_connected = True
    loop.estado.get_machine_state = lambda: GlobalState.CICLO
    loop.link.is_connected.return_value = False

    with patch("time.monotonic", side_effect=[0.0, 3.0, 5.1]):
        loop._tick()
        loop._tick()
        loop._tick()

    loop.state_machine.ciclo.abortar_por_desconexion.assert_called_once()


def test_reconexion_dentro_de_la_tolerancia_reinicia_el_contador():
    """Si el link vuelve antes de agotar la tolerancia y se cae de nuevo, la
    ventana se cuenta desde la nueva caída, no se acumula con la anterior."""
    loop = _make_loop()
    loop.link_was_connected = True
    loop._link_ever_connected = True
    loop.estado.get_machine_state = lambda: GlobalState.CICLO
    loop.link.is_connected.side_effect = [False, True, False]

    with patch("time.monotonic", side_effect=[0.0, 1.0, 4.5]):
        loop._tick()  # cae en t=0.0
        loop._tick()  # reconecta en t=1.0
        loop._tick()  # cae de nuevo en t=4.5 (contador reinicia aquí)

    loop.state_machine.ciclo.abortar_por_desconexion.assert_not_called()


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
