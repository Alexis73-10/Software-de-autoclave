# tests/test_r8_salidas_puertas.py
#
# R8 (tanda 8, D8-5.12): SetOutput y las puertas toman el canal físico de la
# asignación en memoria (antes, números fijos en el código).

from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import asignacion_io as aio
from autoclave.devices.factory.factory import build_doors_cfg
from autoclave.devices.io.set_io import SetOutput
from autoclave.devices.puertas.door_type import DoorType


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _reasignar(**cambios):
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), cambios))


def _canales(io):
    return [(c.args[0], c.args[1]) for c in io.set_output.call_args_list]


# Cada método on/off de SetOutput y el canal que debe usar con la fábrica
_FABRICA = {
    "vapor_generador": 1, "vapor_caldera": 2, "vapor_chaqueta": 3, "vapor_camara": 4,
    "descompresion_rapida": 5, "descompresion_lenta": 6, "descompresion_chaqueta": 7,
    "desbloqueo_puerta_1": 9, "desbloqueo_puerta_2": 10, "bloqueo_puerta_1": 11,
    "bloqueo_puerta_2": 12, "aire_comprimido_camara": 14,   # DO 13 libre (D11-2)
    "aire_admosferico_camara": 15, "agua_chaqueta": 16, "agua_intercambiador": 17,
    "agua_bomba": 18, "abrir_puerta_1": 20, "abrir_puerta_2": 21, "cerrar_puerta_1": 22,
    "cerrar_puerta_2": 23,
}


@pytest.mark.parametrize("nombre,canal", sorted(_FABRICA.items()))
def test_fabrica_sin_cambios(nombre, canal):
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    getattr(s, f"{nombre}_on")()
    getattr(s, f"{nombre}_off")()
    assert _canales(io) == [(canal, True), (canal, False)]


def test_vacio_bomba_y_buzzer_con_fabrica():
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.vacio_camara_on()
    s.buzer_on()
    assert _canales(io) == [(17, True), (8, True), (24, True)]


def test_salida_reasignada_va_a_su_canal_nuevo():
    _reasignar(vapor_camara=25, aire_atmosferico_camara=26, descompresion_lenta=27, buzer_alarma=28)
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.vapor_camara_on(); s.aire_admosferico_camara_on(); s.descompresion_lenta_on(); s.buzer_on()
    assert _canales(io) == [(25, True), (26, True), (27, True), (28, True)]


def test_fuente_de_vapor_bloqueada_sigue_a_la_funcion():
    """Con generador interno, vapor_generador y vapor_caldera nunca se
    encienden; si se reasignan, el bloqueo va con la función, no con DO1/DO2."""
    _reasignar(vapor_generador=30, vapor_caldera=31)
    io = MagicMock()
    perfil = MagicMock(vapor_source="generator")
    s = SetOutput(io, estado=MagicMock(), profile=perfil)
    s.vapor_generador_on(); s.vapor_caldera_on()
    assert _canales(io) == [(30, False), (31, False)]
    assert s.salida_bloqueada(30) and s.salida_bloqueada(31) and not s.salida_bloqueada(1)


def test_apagado_individual_cubre_los_canales_reasignados():
    _reasignar(vapor_camara=25)
    io = MagicMock()
    io.all_off.return_value = False
    s = SetOutput(io, estado=MagicMock())
    assert s.reset_all_outputs() is False
    apagados = {c for c, v in _canales(io) if v is False}
    assert 25 in apagados and set(range(1, 25)) <= apagados


def test_puertas_toman_el_canal_de_la_asignacion():
    _reasignar(abrir_puerta_1=25, cerrar_puerta_1=26, bloqueo_puerta_2=27, desbloqueo_puerta_2=28)
    perfil = MagicMock(door_type=DoorType.ADVANCED, door_count=2)
    p1, p2 = build_doors_cfg(perfil)
    assert p1["do"]["abrir"] == 25 and p1["do"]["cerrar"] == 26
    assert p1["do"]["bloquear"] == 11 and p1["do"]["desbloquear"] == 9
    assert p2["do"]["bloquear"] == 27 and p2["do"]["desbloquear"] == 28
    assert p2["do"]["abrir"] == 21


def test_puertas_con_fabrica_igual_que_antes():
    perfil = MagicMock(door_type=DoorType.ADVANCED, door_count=2)
    p1, p2 = build_doors_cfg(perfil)
    assert p1["do"] == {"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11}
    assert p2["do"] == {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12}


def test_funcion_inhibida_no_la_enciende_el_control_pero_si_el_modo_prueba():
    """SAF-02 de la re-revisión R8: una salida reasignada sin verificar no la
    enciende el control automático; el modo prueba (set_output directo) sí."""
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.inhibidas = frozenset({"vapor_camara"})
    s.vapor_camara_on()
    s.descompresion_lenta_on()
    assert _canales(io) == [(4, False), (aio.canal_do("descompresion_lenta"), True)]
    io.reset_mock()
    s.set_output(4, True)
    assert _canales(io) == [(4, True)]


def test_canales_inhibidos_de_puerta_y_la_puerta_no_los_acciona():
    """SAF-02 (3.ª vuelta R8): las puertas mandan por canal; una salida de
    puerta sin verificar tampoco la enciende la máquina de la puerta."""
    from autoclave.devices.puertas.advanced_door import AdvancedDoor
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.inhibidas = frozenset({"cerrar_puerta_1"})
    assert s.canales_inhibidos == frozenset({aio.canal_do("cerrar_puerta_1")})
    puerta = AdvancedDoor.__new__(AdvancedDoor)
    puerta.set_do = s
    puerta.do = {"abrir": 20, "cerrar": 22, "bloquear": 11, "desbloquear": 9}
    puerta.cerrar_on()
    puerta.abrir_on()
    puerta.cerrar_off()
    assert _canales(io) == [(22, False), (20, True), (22, False)]
