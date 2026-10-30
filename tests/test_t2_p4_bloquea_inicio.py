"""T2 / P-4 (tanda 6): PREPARADO consulta has_blocking_alarm() (campo
`bloquea_inicio` del catálogo de alarmas): una alarma activa que bloquea el
inicio impide quedar listo; una que no bloquea, no."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import (CATALOGO, CIC_09, SIS_04, SUM_06,
                                                      TARJETA_WATCHDOG)
from tests.test_t4_camara_segura import _preparado


def _con_alarmas(*activas):
    obj = _preparado(temp_camara=40.0)
    am = AlarmManager()
    for codigo, valores in activas:
        am.activar(codigo, **valores)
    obj.alarm_manager = am
    return obj


def test_sin_alarmas_queda_listo():
    assert _con_alarmas().esta_preparado() is True


def test_tarjeta_watchdog_fuera_de_ciclo_impide_iniciar():
    assert CATALOGO[TARJETA_WATCHDOG].bloquea_inicio is True
    obj = _con_alarmas((TARJETA_WATCHDOG, {"motivo": "WD"}))
    assert obj.esta_preparado() is False


def test_alarmas_que_no_bloquean_no_impiden_iniciar():
    for codigo in (SUM_06, SIS_04, CIC_09):
        assert CATALOGO[codigo].bloquea_inicio is False
    obj = _con_alarmas((SUM_06, {"estado": "Preparado"}), (SIS_04, {"motivo": "x"}),
                       (CIC_09, {"sensor": "s", "temp": 1.0, "minimo": 0.0, "maximo": 2.0}))
    assert obj.esta_preparado() is True


def test_alarma_resuelta_sin_reconocer_no_bloquea():
    obj = _con_alarmas((TARJETA_WATCHDOG, {"motivo": "WD"}))
    obj.alarm_manager.resolver(TARJETA_WATCHDOG)
    assert obj.esta_preparado() is True


def test_error_del_gestor_de_alarmas_bloquea():
    obj = _preparado(temp_camara=40.0)
    obj.alarm_manager = MagicMock()
    obj.alarm_manager.has_blocking_alarm.side_effect = RuntimeError("x")
    assert obj.esta_preparado() is False
