from unittest.mock import MagicMock

from autoclave.state_machine.states.falla import FallaState
from autoclave.state_machine.states.hibernacion import Hibernacion
from tests.alarmas_helpers import activaciones


def _estado(paro):
    estado = MagicMock()
    estado.get_flag.side_effect = lambda f: paro if f in ("PARO_EMERGENCIA", "PARO_REAL") else False  # U4: paro real
    return estado


def test_falla_con_paro_activa_sis01():
    am = MagicMock()
    FallaState(_estado(True), MagicMock(), am).run()
    assert activaciones(am) == [("SIS-01", None, {"estado": "Falla"})]


def test_hibernacion_con_paro_activa_sis01():
    am = MagicMock()
    Hibernacion(_estado(True), MagicMock(), am).run()
    assert activaciones(am) == [("SIS-01", None, {"estado": "Hibernación"})]
