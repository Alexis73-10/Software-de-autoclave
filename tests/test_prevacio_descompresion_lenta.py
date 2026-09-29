from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase


def _make_fase(params_override=None):
    params = {
        "conteo_pulso_a": 1,
        "conteo_pulso_b": 0,
        "conteo_pulso_c": 0,
        "conteo_pulso_d": 0,
        "presion_baja_pulso_a": 15,
        "tiempo_adicional_bajo_a": 0,
        "presion_alta_pulso_a": 180,
        "tiempo_adicional_alto_a": 0,
        "timeout_bajo": 10,
        "timeout_alto": 10,
    }
    if params_override:
        params.update(params_override)

    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 101.3}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: params.get(key)
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()
    cap = MagicMock()
    cap.has_vacuum = True

    fase = PrevacioFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, set_do, estado


def _avanzar_hasta_vapor_alto(fase, estado):
    fase.update()  # DECOMPRESION -> VACIO_BAJO (ya en presión atmosférica)
    assert fase._paso == "VACIO_BAJO"

    estado.sensores_pres["pres_camara"] = 10  # <= presion_baja_pulso_a
    fase.update()  # VACIO_BAJO -> HOLD_BAJO
    assert fase._paso == "HOLD_BAJO"

    fase.update()  # HOLD_BAJO -> APAGANDO_VACIO (tiempo_adicional_bajo_a=0)
    assert fase._paso == "APAGANDO_VACIO"

    import time as time_module
    fase._t_apagado_vacio = time_module.monotonic() - 10  # forzar fin del stagger
    fase.update()  # APAGANDO_VACIO -> VAPOR_ALTO
    assert fase._paso == "VAPOR_ALTO"


def test_pasos_de_vacio_no_activan_descompresion_lenta():
    fase, set_do, estado = _make_fase()

    fase.update()  # DECOMPRESION -> VACIO_BAJO
    estado.sensores_pres["pres_camara"] = 10
    fase.update()  # VACIO_BAJO -> HOLD_BAJO
    fase.update()  # HOLD_BAJO -> APAGANDO_VACIO

    set_do.descompresion_lenta_on.assert_not_called()


def test_vapor_alto_activa_descompresion_lenta():
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_vapor_alto(fase, estado)

    estado.sensores_pres["pres_camara"] = 50  # aún no alcanza presion_alta_pulso_a
    fase.update()

    set_do.descompresion_lenta_on.assert_called()


def test_hold_alto_mantiene_descompresion_lenta_activa():
    fase, set_do, estado = _make_fase({"tiempo_adicional_alto_a": 5})
    _avanzar_hasta_vapor_alto(fase, estado)

    estado.sensores_pres["pres_camara"] = 180  # >= presion_alta_pulso_a
    fase.update()  # VAPOR_ALTO -> HOLD_ALTO
    assert fase._paso == "HOLD_ALTO"

    set_do.descompresion_lenta_on.reset_mock()
    fase.update()  # dentro de HOLD_ALTO

    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_lenta_off.assert_not_called()


def test_fin_de_pulso_apaga_descompresion_lenta():
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_vapor_alto(fase, estado)

    estado.sensores_pres["pres_camara"] = 180  # >= presion_alta_pulso_a
    fase.update()  # VAPOR_ALTO -> HOLD_ALTO

    fase.update()  # tiempo_adicional_alto_a=0 -> hold vence de inmediato -> avanza pulso

    set_do.descompresion_lenta_off.assert_called()


def test_timeout_vapor_alto_apaga_descompresion_lenta(monkeypatch):
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_vapor_alto(fase, estado)

    t_fin = fase._timeout_alto_fin
    monkeypatch.setattr(
        "autoclave.state_machine.cycle_phases.prevacio.time.monotonic",
        lambda: t_fin + 1,
    )
    resultado = fase.update()

    from autoclave.state_machine.cycle_phases.base_fase import FaseResult
    assert resultado == FaseResult.FALLO
    set_do.descompresion_lenta_off.assert_called()
