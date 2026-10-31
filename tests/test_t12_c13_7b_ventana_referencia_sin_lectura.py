"""Tanda 12, C-13.7b (opción B): en la ventana de sostenimiento de
CALENTAMIENTO, `refs_en_consigna` ignora las Referencias sin lectura en vez
de bloquear la ventana; las que sí leen deben estar en consigna."""
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests import test_calentamiento_fase as tcal

_UNA_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_DOS_REF = {"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "referencia"}


def _ventana(asignacion, refs):
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.cycle.sensores = asignacion
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    for sensor, valor in refs.items():
        estado.sensores_temp[sensor] = valor
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)
    fase.update()
    return fase


def test_referencia_none_no_bloquea_la_ventana():
    fase = _ventana(_UNA_REF, {"temp_ref": None})
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_referencia_ausente_del_diccionario_no_bloquea():
    fase = _ventana(_UNA_REF, {})
    assert fase._timer_sostenido_desde is not None


def test_otra_referencia_que_lee_en_consigna_completa():
    fase = _ventana(_DOS_REF, {"temp_2_camara": None, "temp_ref": 134.3})
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_otra_referencia_que_lee_fria_sigue_bloqueando():
    fase = _ventana(_DOS_REF, {"temp_2_camara": None, "temp_ref": 130.0})
    assert fase._timer_sostenido_desde is None


def test_referencia_que_lee_fria_bloquea():
    fase = _ventana(_UNA_REF, {"temp_ref": 133.9})
    assert fase._timer_sostenido_desde is None
