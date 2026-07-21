from unittest.mock import MagicMock
from autoclave.devices.io.set_io import SetOutput


def _make_set_output():
    io = MagicMock()
    return SetOutput(io, estado=MagicMock()), io


def test_reset_all_outputs_retorna_true_si_all_off_confirma():
    set_do, io = _make_set_output()
    io.all_off.return_value = True

    assert set_do.reset_all_outputs() is True
    io.set_output.assert_not_called()


def test_reset_all_outputs_retorna_false_si_all_off_no_confirma():
    set_do, io = _make_set_output()
    io.all_off.return_value = False

    assert set_do.reset_all_outputs() is False
    assert io.set_output.call_count == 24
