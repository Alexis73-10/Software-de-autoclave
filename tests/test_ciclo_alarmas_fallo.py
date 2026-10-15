from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState


def _ciclo(sensores_di=None, sensores_pres=None, sensores_temp=None, flags=None):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp or {"temp_camara": 100.0}
    estado.sensores_pres = sensores_pres or {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = sensores_di or {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                                         "vapor_suministro": 1}
    estado.get_flag.side_effect = lambda f: (flags or {}).get(f, False)
    cycle = MagicMock(); cycle.get_param.return_value = None
    cycle.copia.return_value = cycle            # T-17: el ciclo corre sobre la copia
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager()
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
    assert inst.codigo == "COM-02" and "6.2 s" in inst.descripcion
    assert estado.fase_ciclo == "FALLO_CONEXION"


def _activar_que_lanza(am):
    def lanza(*args, **kwargs):
        raise RuntimeError("activar roto")
    am.activar = lanza


def _forzar_fallo_de_fase(ciclo, estado):
    ciclo._fases[0].update = lambda: FaseResult.FALLO
    estado.motivo_fallo = ""


def _forzar_fallo_de_puerta(ciclo, estado):
    estado.sensores_pres["pres_empaque_2"] = 100.0


def _forzar_sensor_ausente(ciclo, estado):
    estado.sensores_temp["temp_camara"] = None


def _forzar_emergencia(ciclo, estado):
    estado.get_flag.side_effect = lambda f: f == "PARO_EMERGENCIA"


def _forzar_corte_electrico(ciclo, estado):
    estado.get_flag.side_effect = lambda f: f == "FALLO_SUMINISTRO_ELECTRICO"


@pytest.mark.parametrize("forzar, codigo", [
    (_forzar_fallo_de_fase, "CIC-01"),
    (_forzar_fallo_de_puerta, "PUE-03"),
    (_forzar_sensor_ausente, "SEN-02"),
    (_forzar_emergencia, "SIS-01"),
    (_forzar_corte_electrico, "SUM-01"),
])
def test_activar_que_lanza_no_impide_el_protocolo_de_fallo(forzar, codigo):
    ciclo, estado, am = _ciclo()
    _activar_que_lanza(am)
    forzar(ciclo, estado)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.ejecutar.assert_called_once()
    assert ciclo._resultado_pendiente == CicloResultado.FALLO
    assert estado.codigo_fallo == codigo
    assert codigo in estado.motivo_fallo


def test_activar_que_lanza_no_impide_el_protocolo_en_desconexion():
    ciclo, estado, am = _ciclo()
    _activar_que_lanza(am)
    ciclo.abortar_por_desconexion(segundos=6.2)
    ciclo._protocolo.ejecutar.assert_called_once()
    assert ciclo._resultado_pendiente == CicloResultado.FALLO
    assert estado.codigo_fallo == "COM-02"
    assert "COM-02" in estado.motivo_fallo


def test_fase_fuera_de_cic_por_fase_igual_ejecuta_el_protocolo():
    ciclo, estado, am = _ciclo()
    fase = ciclo._fases[0]
    fase.name = "FASE_DESCONOCIDA"
    def falla():
        estado.motivo_fallo = "Motivo propio de la fase"
        return FaseResult.FALLO
    fase.update = falla
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.ejecutar.assert_called_once()
    assert ciclo._resultado_pendiente == CicloResultado.FALLO
    assert "Motivo propio de la fase" in estado.motivo_fallo


def test_reset_limpia_codigo_fallo():
    ciclo, estado, _ = _ciclo()
    estado.codigo_fallo = "CIC-03"
    ciclo.reset()
    assert estado.codigo_fallo == ""
