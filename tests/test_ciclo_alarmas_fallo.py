from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states.ciclo import CicloState


def _ciclo(sensores_di=None, sensores_pres=None, sensores_temp=None, flags=None):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp or {"temp_camara": 100.0}
    estado.sensores_pres = sensores_pres or {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = sensores_di or {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                                         "vapor_suministro": 1}
    estado.get_flag.side_effect = lambda f: (flags or {}).get(f, False)
    cycle = MagicMock(); cycle.get_param.return_value = None
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]))
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, estado, am


def test_fallo_de_fase_usa_motivo_de_la_fase():
    ciclo, estado, am = _ciclo()
    fase = ciclo._fases[0]
    def falla():
        estado.motivo_fallo = "Timeout: no se alcanzó 320 kPa en 10 min"
        return FaseResult.FALLO
    fase.update = falla
    ciclo.run()
    [inst] = am.activas()
    assert (inst.codigo, inst.origen) == ("CIC-01", "Precalentamiento")
    assert estado.motivo_fallo == ("CIC-01 · Fallo en precalentamiento: "
                                   "Timeout: no se alcanzó 320 kPa en 10 min")
    assert estado.codigo_fallo == "CIC-01"
    assert estado.fase_ciclo == "FALLO_PRECALENTAMIENTO"


def test_fallo_de_fase_sin_motivo_usa_texto_por_defecto():
    ciclo, estado, am = _ciclo()
    ciclo._fases[0].update = lambda: FaseResult.FALLO
    estado.motivo_fallo = ""
    ciclo.run()
    assert "el motivo detallado aún no se registra" in am.activas()[0].descripcion


def test_empaque_bajo_registra_pue03_con_presion_y_minimo():
    ciclo, estado, am = _ciclo(sensores_pres={"pres_camara": 200.0, "pres_chaqueta": 300.0,
                                              "pres_empaque_1": 300.0, "pres_empaque_2": 100.0})
    ciclo.run()
    [inst] = am.activas()
    assert (inst.codigo, inst.origen) == ("PUE-03", "Puerta 2")
    assert "100 kPa" in inst.descripcion and "Precalentamiento" in inst.descripcion
    assert estado.fase_ciclo == "FALLO_PUERTA_2_EMPAQUE"


def test_sensor_ausente_lista_nombres_legibles():
    ciclo, estado, am = _ciclo(sensores_temp={"temp_camara": None})
    ciclo.run()
    [inst] = am.activas()
    assert inst.codigo == "SEN-02" and "Temperatura de cámara" in inst.descripcion
    assert "temp_camara" not in inst.descripcion


def test_desconexion_registra_segundos():
    ciclo, estado, am = _ciclo()
    ciclo.abortar_por_desconexion(segundos=6.2)
    [inst] = am.activas()
    assert inst.codigo == "COM-02" and "6 s" in inst.descripcion
    assert estado.fase_ciclo == "FALLO_CONEXION"


def test_reset_limpia_codigo_fallo():
    ciclo, estado, _ = _ciclo()
    estado.codigo_fallo = "CIC-03"
    ciclo.reset()
    assert estado.codigo_fallo == ""
