"""S1 (tanda 8, D8-1.2 y 1.4): transductor de presión sin lectura con ciclo en
curso. FALLO con código propio (SEN-04 cámara, SEN-05 chaqueta), vapor
cortado y venteo solo por la lenta; nunca se interpreta como vacío ni se abre
el aire atmosférico por ese motivo."""

from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import presion_sin_lectura as psl
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from tests.alarmas_helpers import ultima_activacion


def _make_ciclo(monkeypatch, ai=("pres_camara", "pres_chaqueta")):
    monkeypatch.setattr(psl, "_ai_habilitadas", lambda: ai)
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 130.0}
    estado.sensores_pres = {"pres_camara": 290.0, "pres_chaqueta": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1, "vapor_suministro": 1}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado, set_do


def test_presion_camara_sin_lectura_falla_con_sen04_y_solo_lenta(monkeypatch):
    ciclo, estado, set_do = _make_ciclo(monkeypatch)
    estado.sensores_pres["pres_camara"] = None
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    codigo, _, valores = ultima_activacion(ciclo.alarm_manager)
    assert codigo == "SEN-04"
    assert "fase" in valores
    assert estado.codigo_fallo is not None
    proto = ciclo._protocolo
    assert proto.solo_lenta is True
    set_do.reset_all_outputs.assert_called()            # vapor cortado
    set_do.descompresion_lenta_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()


def test_protocolo_con_presion_sin_lectura_nunca_abre_aire_ni_rapida(monkeypatch):
    ciclo, estado, set_do = _make_ciclo(monkeypatch)
    estado.sensores_pres["pres_camara"] = None
    ciclo.run()
    for _ in range(50):
        ciclo.run()                                    # protocolo.update() en espera
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_presion_chaqueta_sin_lectura_falla_con_sen05_y_solo_lenta(monkeypatch):
    ciclo, estado, set_do = _make_ciclo(monkeypatch)
    estado.sensores_pres["pres_chaqueta"] = None
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert ultima_activacion(ciclo.alarm_manager)[0] == "SEN-05"
    assert ciclo._protocolo.solo_lenta is True
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_chaqueta_no_habilitada_en_io_enabled_no_falla_el_ciclo(monkeypatch):
    ciclo, estado, _ = _make_ciclo(monkeypatch, ai=("pres_camara",))
    estado.sensores_pres["pres_chaqueta"] = None
    ciclo.run()
    assert estado.fase_ciclo != "SENSOR_AUSENTE"


def test_sin_io_enabled_legible_la_chaqueta_se_vigila(monkeypatch):
    ciclo, estado, _ = _make_ciclo(monkeypatch, ai=None)
    estado.sensores_pres["pres_chaqueta"] = None
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert ultima_activacion(ciclo.alarm_manager)[0] == "SEN-05"


def test_camara_tiene_prioridad_sobre_chaqueta_y_sobre_temperatura(monkeypatch):
    ciclo, estado, _ = _make_ciclo(monkeypatch)
    estado.sensores_pres["pres_camara"] = None
    estado.sensores_pres["pres_chaqueta"] = None
    estado.sensores_temp["temp_camara"] = None
    ciclo.run()
    assert ultima_activacion(ciclo.alarm_manager)[0] == "SEN-04"
    assert ciclo._protocolo.solo_lenta is True


def test_solo_temperatura_sigue_con_sen02(monkeypatch):
    ciclo, estado, _ = _make_ciclo(monkeypatch)
    estado.sensores_temp["temp_camara"] = None
    ciclo.run()
    assert ultima_activacion(ciclo.alarm_manager)[0] == "SEN-02"


@pytest.mark.parametrize("canal", ["pres_camara", "pres_chaqueta"])
def test_presion_cero_valida_no_es_sin_lectura(monkeypatch, canal):
    """0 kPa con lectura (convertidor en rango) no se toma como sensor
    ausente: la detección es del convertidor, sobre la cuenta cruda."""
    ciclo, estado, _ = _make_ciclo(monkeypatch)
    estado.sensores_pres[canal] = 0.0
    ciclo.run()
    assert estado.fase_ciclo != "SENSOR_AUSENTE"
