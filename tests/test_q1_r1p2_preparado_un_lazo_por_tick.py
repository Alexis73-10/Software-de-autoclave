# Q1 / R1-P2 (tanda 7, decisión 1.3 de Cristian; hallazgo T1-01-C de la
# tanda 5): en PREPARADO, esta_preparado() usa el resultado de los lazos del
# tick y no vuelve a llamar a mantener_presion_camara (ni a chaqueta/drenaje).
# Con la doble llamada el debounce del aire (ConfirmadorApagado, 3 ticks)
# avanzaba de a 2 y el aire cerraba a los 1,5 ticks; ahora cierra a los 3
# ticks reales.

from unittest.mock import MagicMock

from autoclave.state_machine.states.preparado import preparado_state
from tests.test_adenda_estados import _make
from tests.test_t4_camara_segura import _CFG, _Config


def _preparado(**overrides):
    obj, am, set_do = _make(preparado_state, None, **overrides)
    obj.config = _Config({**_CFG, "presion_empaque": 300, "tiempo_estable_alarma": 0,
                          "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0})
    obj.camara_segura = lambda: True
    obj.alarm_manager.has_blocking_alarm.return_value = False
    return obj, set_do


def _contar(obj, nombre):
    original = getattr(obj, nombre)
    llamadas = []

    def envoltura(*a, **k):
        llamadas.append(1)
        return original(*a, **k)

    setattr(obj, nombre, envoltura)
    return llamadas


def test_cada_lazo_corre_una_sola_vez_por_tick():
    obj, _ = _preparado()
    presion = _contar(obj, "mantener_presion_camara")
    chaqueta = _contar(obj, "mantener_chaqueta")
    drenaje = _contar(obj, "mantener_drenaje")

    obj.run()

    assert (len(presion), len(chaqueta), len(drenaje)) == (1, 1, 1)


def test_el_aire_de_camara_cierra_a_los_3_ticks_reales():
    # Presión en banda (101 kPa con atm 101,3 ± 10): el aire debe apagarse solo
    # tras 3 ticks consecutivos "en banda" (ConfirmadorApagado).
    obj, set_do = _preparado()

    obj.run()
    obj.run()
    set_do.aire_admosferico_camara_off.assert_not_called()

    obj.run()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_esta_preparado_usa_el_resultado_del_tick():
    # El tick dice que la presión de cámara NO estaba lista: esta_preparado()
    # no la vuelve a evaluar (aunque el sensor ya esté en banda).
    obj, _ = _preparado()
    presion = _contar(obj, "mantener_presion_camara")

    assert obj.esta_preparado((True, False, True)) is False
    assert obj.esta_preparado((True, True, True)) is True
    assert presion == []


def test_run_queda_listo_con_todo_en_banda():
    obj, _ = _preparado()
    assert obj.run() is True


def test_run_no_listo_con_camara_fuera_de_banda():
    obj, _ = _preparado(pres_camara=130.0)
    assert obj.run() is False
