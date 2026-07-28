from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.prevacio import (
    PrevacioFase,
    _STAGGER_APAGADO_VACIO,
)


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


def _avanzar_hasta_hold_bajo(fase, estado):
    fase.update()  # DECOMPRESION -> VACIO_BAJO (ya en presión atmosférica)
    assert fase._paso == "VACIO_BAJO"

    estado.sensores_pres["pres_camara"] = 10  # <= presion_baja_pulso_a
    fase.update()  # VACIO_BAJO -> HOLD_BAJO
    assert fase._paso == "HOLD_BAJO"


def test_hold_bajo_apaga_bomba_vacio_y_espera_antes_de_apagar_camara(monkeypatch):
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_hold_bajo(fase, estado)

    fase.update()  # tiempo_adicional_bajo_a=0 -> hold vence de inmediato

    assert fase._paso == "APAGANDO_VACIO"
    set_do.bomba_vacio_off.assert_called_once()
    set_do.vacio_camara_off.assert_not_called()


def test_apagando_vacio_no_apaga_camara_antes_del_stagger(monkeypatch):
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_hold_bajo(fase, estado)
    fase.update()  # -> APAGANDO_VACIO, marca self._t_apagado_vacio

    t0 = fase._t_apagado_vacio
    monkeypatch.setattr(
        "autoclave.state_machine.cycle_phases.prevacio.time.time",
        lambda: t0 + (_STAGGER_APAGADO_VACIO / 2),
    )
    fase.update()

    assert fase._paso == "APAGANDO_VACIO"
    set_do.vacio_camara_off.assert_not_called()


def test_apagando_vacio_apaga_camara_y_avanza_tras_el_stagger(monkeypatch):
    fase, set_do, estado = _make_fase()
    _avanzar_hasta_hold_bajo(fase, estado)
    fase.update()  # -> APAGANDO_VACIO

    t0 = fase._t_apagado_vacio
    monkeypatch.setattr(
        "autoclave.state_machine.cycle_phases.prevacio.time.time",
        lambda: t0 + _STAGGER_APAGADO_VACIO + 0.01,
    )
    fase.update()

    set_do.vacio_camara_off.assert_called_once()
    assert fase._paso == "VAPOR_ALTO"
