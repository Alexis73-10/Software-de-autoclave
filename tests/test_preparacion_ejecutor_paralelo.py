from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(paro_emergencia=0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"paro_emergencia": paro_emergencia}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def _stub_condiciones(p, chaqueta=True, presion=(True, False), drenaje=(True, False), temp=True):
    p.suministrar_vapor_chaqueta = lambda: chaqueta
    p.igualar_presion_camara = lambda: presion
    p.drenar_camara = lambda: drenaje
    p.verificar_temperatura_drenaje = lambda: temp


def test_valvula_rapida_abre_si_presion_la_pide_aunque_drenaje_no():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(False, True), drenaje=(True, False))
    p.ejecutor()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_rapida_off.assert_not_called()


def test_valvula_rapida_abre_si_drenaje_la_pide_aunque_presion_no():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(True, False), drenaje=(False, True))
    p.ejecutor()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_rapida_off.assert_not_called()


def test_valvula_rapida_cierra_si_ninguna_la_pide():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(True, False), drenaje=(True, False))
    p.ejecutor()
    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_ejecutor_retorna_true_solo_si_las_4_condiciones_ok():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, chaqueta=True, presion=(True, False), drenaje=(True, False), temp=True)
    assert p.ejecutor() is True


def test_ejecutor_retorna_false_si_alguna_condicion_falla():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, chaqueta=True, presion=(False, False), drenaje=(True, False), temp=True)
    assert p.ejecutor() is False


def test_ejecutor_evalua_las_4_condiciones_en_el_mismo_tick():
    # Antes (secuencial), drenar_camara/verificar_temperatura_drenaje ni se
    # llamaban si la chaqueta o la presion aun no estaban listas. Ahora deben
    # evaluarse siempre, sin importar el resultado de las demas.
    p, alarm_mgr, set_do = _make_preparacion()
    llamadas = []
    p.suministrar_vapor_chaqueta = lambda: (llamadas.append("chaqueta"), False)[1]
    p.igualar_presion_camara = lambda: (llamadas.append("presion"), (False, False))[1]
    p.drenar_camara = lambda: (llamadas.append("drenaje"), (True, False))[1]
    p.verificar_temperatura_drenaje = lambda: (llamadas.append("temp"), True)[1]

    p.ejecutor()

    assert set(llamadas) == {"chaqueta", "presion", "drenaje", "temp"}


def test_run_maneja_emergencia_sin_llamar_supervisor():
    p, alarm_mgr, set_do = _make_preparacion(paro_emergencia=1)

    def _supervisor_no_debe_llamarse():
        raise AssertionError("supervisor() no debe llamarse durante una emergencia")

    p.supervisor = _supervisor_no_debe_llamarse

    result = p.run()

    assert result is False
    set_do.reset_all_outputs.assert_called_once()
    set_do.buzer_emergencia.assert_called_once()


def test_valvula_abre_con_funciones_reales_presion_alta_sin_agua_residual():
    # Integración sin stubs: presión de cámara alta (igualar_presion_camara
    # real pide la válvula) y sin agua residual (drenar_camara real NO la
    # pide). Es el escenario que motivó pasar a OR en vez de sobreescritura
    # secuencial — si alguien revirtiera a "el último que corre gana", este
    # caso dejaría la válvula cerrada y PREPARACION nunca terminaría.
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {
        "paro_emergencia": 0,
        "vapor_suministro": 1,
        "agua_camara": 0,
    }
    estado.sensores_pres = {"pres_camara": 1030.0, "pres_chaqueta": 300.0}
    estado.sensores_temp = {"temp_drenaje": 20.0}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "presion_admosferica": 1013.0,
        "rango_presion_atm": 5.0,
        "temp_segura_drenaje": 40.0,
    }[key]
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)

    p.ejecutor()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_rapida_off.assert_not_called()


def test_preparacion_state_no_tiene_atributo_step():
    p, _, _ = _make_preparacion()
    assert not hasattr(p, "step")


def test_reset_no_falla_sin_step():
    p, _, _ = _make_preparacion()
    p.reset()  # no debe lanzar excepción
