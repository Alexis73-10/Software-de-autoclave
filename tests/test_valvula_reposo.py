from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.valvula_reposo import (
    abrir_valvula_modo,
    cerrar_valvulas_descompresion,
)


def test_abrir_valvula_modo_0_usa_lenta():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 0)
    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()


def test_abrir_valvula_modo_1_usa_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 1)
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_2_usa_lenta():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 2)
    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_abrir_valvula_modo_3_usa_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 3)
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_4_usa_chaqueta_y_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 4)
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_5_usa_chaqueta_y_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 5)
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


def test_cerrar_valvulas_descompresion_apaga_las_tres():
    set_do = MagicMock()
    cerrar_valvulas_descompresion(set_do)
    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    set_do.descompresion_chaqueta_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()
