import time as time_module
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(vapor=1, pres_chaqueta=300.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"vapor_suministro": vapor}
    estado.sensores_pres = {"pres_chaqueta": pres_chaqueta}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    config.get.return_value = 5
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_vapor_mantener_chaqueta_retorna_true():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    assert p.mantener_chaqueta() is True
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparado(vapor=0)
    p.mantener_chaqueta()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_sigue_bloqueando():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=100.0)
    assert p.mantener_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_called()


def test_esta_preparado_true_sin_vapor_con_resto_ok():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    p.mantener_presion_camara = lambda: True
    p.mantener_drenaje = lambda: True
    p.puertas_cerradas = lambda: True
    p.estado.get_flag.side_effect = lambda f: False
    assert p.esta_preparado() is True


def test_valvula_enciende_bajo_objetivo_sin_disparar_alarma():
    # objetivo=300, rango=20 -> limite_inf=280. 299 esta bajo el objetivo
    # pero dentro de la banda: la valvula debe reaccionar, la alarma no.
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=299.0)
    resultado = p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    alarm_mgr.clear.assert_any_call("CHAQUETA_FRIA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" not in ids_reportados
    assert resultado is True


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_alarma_chaqueta_fria_dispara_bajo_limite_inferior():
    # tiempo_estable_alarma=0 -> generar_alarma_temporizada dispara en la
    # primera llamada (no hay que esperar tiempo real).
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=270.0)
    p.tiempo_estable = 0
    p.mantener_chaqueta()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" in ids_reportados


def test_timer_estabilidad_inmune_a_salto_de_reloj_de_pared(monkeypatch):
    fake_monotonic = [1000.0]
    monkeypatch.setattr(time_module, "monotonic", lambda: fake_monotonic[0])
    monkeypatch.setattr(time_module, "time", lambda: 10.0)

    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=270.0)
    p.tiempo_estable = 60
    p.mantener_chaqueta()  # arma timer_estabilidad con monotonic=1000.0
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" not in ids_reportados  # aún no pasó tiempo_estable

    fake_monotonic[0] += 61  # reloj monótono avanza 61s (tiempo_estable cumplido)
    alarm_mgr.report.reset_mock()
    p.mantener_chaqueta()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_apagado_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    p.estado.sensores_pres["pres_chaqueta"] = 299.0
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    p.estado.sensores_pres["pres_chaqueta"] = 300.0
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
