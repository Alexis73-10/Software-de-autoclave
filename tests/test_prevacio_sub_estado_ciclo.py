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


def test_reset_deja_sub_estado_ciclo_vacio():
    _, _, estado = _make_fase()
    assert estado.sub_estado_ciclo == ""


def test_sub_estado_ciclo_sigue_el_paso_interno():
    fase, _, estado = _make_fase()

    fase.update()  # DECOMPRESION -> VACIO_BAJO (ya en presión atmosférica)
    assert fase._paso == "VACIO_BAJO"
    assert estado.sub_estado_ciclo == "VACIO_BAJO"

    estado.sensores_pres["pres_camara"] = 10  # <= presion_baja_pulso_a
    fase.update()  # VACIO_BAJO -> HOLD_BAJO
    assert estado.sub_estado_ciclo == "HOLD_BAJO"

    fase.update()  # tiempo_adicional_bajo_a=0 -> HOLD_BAJO -> APAGANDO_VACIO
    assert estado.sub_estado_ciclo == "APAGANDO_VACIO"


def test_sub_estado_ciclo_no_cambia_mientras_el_paso_no_cambia():
    fase, _, estado = _make_fase()

    fase.update()  # -> VACIO_BAJO
    assert estado.sub_estado_ciclo == "VACIO_BAJO"

    fase.update()  # sigue en VACIO_BAJO (no alcanzó presion_baja_pulso_a)
    assert fase._paso == "VACIO_BAJO"
    assert estado.sub_estado_ciclo == "VACIO_BAJO"


def test_completar_fase_limpia_sub_estado_ciclo():
    fase, _, estado = _make_fase(params_override={"conteo_pulso_a": 0})

    result = fase.update()

    from autoclave.state_machine.cycle_phases.base_fase import FaseResult
    assert result == FaseResult.COMPLETADO
    assert estado.sub_estado_ciclo == ""
