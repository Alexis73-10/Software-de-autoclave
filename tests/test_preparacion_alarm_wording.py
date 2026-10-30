from unittest.mock import MagicMock

from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_06, SEN_01, SIS_01, SUM_03,
)
from autoclave.state_machine.states.preparacion import preparacion_state
from tests.helpers.alarmas_helpers import activaciones, codigos_activados, codigos_resueltos


def _make_state(sensores_pres=None, sensores_temp=None, di=None):
    estado = MagicMock()
    estado.sensores_pres = sensores_pres or {
        "pres_camara": 101.3, "pres_chaqueta": 250.0,
        "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = sensores_temp or {
        "temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
        "temp_chaqueta": 25.0, "temp_drenaje_cam": 25.0, "temp_drenaje": 72.0}
    estado.sensores_di = di or {
        "paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 1,
        "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, **k: {"presion_chaqueta": 320,
                                                     "rango_presion_chaqueta": 50}[n]
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0}.get(k)
    return preparacion_state(MagicMock(), estado, MagicMock(), cycle, config)


def test_chaqueta_baja_activa_pre01_con_valores():
    s = _make_state()
    s.suministrar_vapor_chaqueta()
    [(codigo, origen, valores)] = [a for a in activaciones(s.alarm_manager) if a[0] == PRE_01]
    assert origen is None
    assert valores == {"pres": 250.0, "minimo": 270, "objetivo": 320, "rango": 50}


def test_drenaje_alto_activa_pre06_con_maximo_de_banda():
    s = _make_state()
    s.verificar_temperatura_drenaje()
    [(_, _, valores)] = [a for a in activaciones(s.alarm_manager) if a[0] == PRE_06]
    assert valores == {"temp": 72.0, "maximo": 65.0}


def test_sensor_en_cero_activa_sen01_con_nombre_legible():
    s = _make_state(sensores_pres={"pres_camara": 0, "pres_chaqueta": 300.0,
                                   "pres_empaque_1": 300.0, "pres_empaque_2": 300.0})
    s.verificar_sensores()
    sen = [a for a in activaciones(s.alarm_manager) if a[0] == SEN_01]
    assert sen == [(SEN_01, "Presión de cámara", {"sensor": "Presión de cámara", "valor": 0})]


def test_suministro_agua_bomba_activa_sum03():
    s = _make_state(di={"paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 0,
                        "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0})
    s.verificar_suministros()
    assert SUM_03 in codigos_activados(s.alarm_manager)


def test_paro_activa_y_resuelve_sis01():
    s = _make_state(di={"paro_emergencia": 1})
    # E1-5 (D-16): PREPARACION lee el flag publicado por EmergencyStop
    s.estado.get_flag.side_effect = lambda f: f in ("PARO_EMERGENCIA", "PARO_REAL")  # U4: paro real
    s.run()
    assert ("SIS-01", None, {"estado": "Preparación"}) in activaciones(s.alarm_manager)
    s.estado.sensores_di = {"paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 1,
                            "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0}
    s.estado.get_flag.side_effect = lambda f: False
    s.run()
    assert SIS_01 in codigos_resueltos(s.alarm_manager)
