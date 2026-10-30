# tests/test_t16_s3_protocolo_vapor.py
#
# s3 (tanda 16):
#   - V-02 (b): ProtocoloFallo.update() reafirma vapor_camara y vapor_chaqueta
#     en OFF en cada llamada una vez confirmado el ALL_OFF.
#   - VCH §8 punto 9: FALLO, cancelación y paro de emergencia cierran
#     vapor_camara y vapor_chaqueta (ALL_OFF del protocolo y, después, la
#     reafirmación o el apagado repetido del paro).

from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import presion_sin_lectura
from autoclave.installation.profile import MODO_CHAQUETA
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

pytestmark = pytest.mark.req("T16-S3")


def _estado():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 120.0}
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": 1}
    estado.motivo_fallo = ""
    return estado


def _cycle():
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda *a, default=None, **k: default
    cycle.copia.return_value = cycle
    cycle.sensores = None
    return cycle


def _config():
    config = MagicMock()
    config.get.return_value = None
    return config


def _protocolo(ack=True):
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = ack
    p = ProtocoloFallo(_estado(), set_do, _cycle(), _config())
    return p, set_do


# ── V-02 (b) ───────────────────────────────────────────────────────────────

def test_update_reafirma_vapor_off_en_cada_llamada():
    p, set_do = _protocolo(ack=True)
    p.ejecutar()
    set_do.reset_all_outputs.assert_called_once()
    set_do.reset_mock()
    for n in range(1, 4):
        p.update()
        assert set_do.vapor_camara_off.call_count == n
        assert set_do.vapor_chaqueta_off.call_count == n
    set_do.reset_all_outputs.assert_not_called()      # ya confirmado: no se repite
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_sin_ack_reintenta_el_all_off_y_luego_reafirma():
    p, set_do = _protocolo(ack=False)
    p.ejecutar()
    set_do.reset_mock()
    p.update()                                         # reintento, sin ACK
    set_do.reset_all_outputs.assert_called_once()
    set_do.reset_all_outputs.return_value = True
    p.update()                                         # reintento con ACK
    assert set_do.reset_all_outputs.call_count == 2
    set_do.reset_mock()
    p.update()
    set_do.vapor_camara_off.assert_called_once()
    set_do.vapor_chaqueta_off.assert_called_once()
    set_do.reset_all_outputs.assert_not_called()


def test_sin_ejecutar_no_hace_nada():
    p, set_do = _protocolo()
    p.update()
    assert set_do.mock_calls == []


def test_reafirma_tambien_con_la_camara_sellada():
    p, set_do = _protocolo()
    p.ejecutar()
    p._sellado = True
    set_do.reset_mock()
    p.update()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()


# ── VCH §8 punto 9: FALLO, cancelación y paro cierran las dos válvulas ─────

class _Fase:
    def __init__(self, name, set_do):
        self.name = name
        self.resultado = FaseResult.EN_CURSO
        self._set_do = set_do

    def reset(self):
        pass

    def update(self):
        # la fase deja el vapor abierto (modo chaqueta: cámara abierta y
        # chaqueta en control)
        self._set_do.vapor_camara_on()
        self._set_do.vapor_chaqueta_on()
        return self.resultado


def _ciclo(flags):
    estado = _estado()
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    ciclo = CicloState(estado, set_do, _cycle(), _config(), AlarmManager())
    ciclo.reset()
    estado.modo_vapor = MODO_CHAQUETA
    ciclo._pres_vigilados = [presion_sin_lectura.CAMARA]
    fase = _Fase("ESTERILIZACION", set_do)
    ciclo._fases = [fase]
    ciclo._fase_idx = 0
    assert ciclo.run() == CicloResultado.EN_CURSO
    set_do.reset_mock()
    return ciclo, estado, set_do, fase


def _ultimas(set_do):
    """Última orden de cada válvula de vapor; ALL_OFF cuenta como OFF de todas."""
    ultima = {}
    for c in set_do.mock_calls:
        if c[0] in ("reset_all_outputs", "apagar_por_paro"):
            ultima["camara"] = ultima["chaqueta"] = "off"
        elif c[0].startswith("vapor_camara_"):
            ultima["camara"] = c[0].rsplit("_", 1)[1]
        elif c[0].startswith("vapor_chaqueta_"):
            ultima["chaqueta"] = c[0].rsplit("_", 1)[1]
    return ultima


def test_fallo_de_fase_cierra_las_dos_valvulas():
    ciclo, estado, set_do, fase = _ciclo({})
    fase.resultado = FaseResult.FALLO
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert _ultimas(set_do) == {"camara": "off", "chaqueta": "off"}
    set_do.reset_mock()
    ciclo.run()                                        # protocolo en espera
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()
    assert _ultimas(set_do) == {"camara": "off", "chaqueta": "off"}


def test_cancelacion_cierra_las_dos_valvulas():
    flags = {}
    ciclo, estado, set_do, fase = _ciclo(flags)
    flags["CICLO_CANCELADO"] = True
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert ciclo._resultado_pendiente == CicloResultado.CANCELADO
    set_do.reset_all_outputs.assert_called()
    set_do.reset_mock()
    ciclo.run()
    assert _ultimas(set_do) == {"camara": "off", "chaqueta": "off"}


def test_paro_de_emergencia_cierra_las_dos_valvulas():
    flags = {}
    ciclo, estado, set_do, fase = _ciclo(flags)
    flags["PARO_EMERGENCIA"] = True
    flags["PARO_REAL"] = True
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    set_do.reset_all_outputs.assert_called()
    assert _ultimas(set_do) == {"camara": "off", "chaqueta": "off"}
    set_do.reset_mock()
    ciclo.run()                                        # paro activo, resultado pendiente
    set_do.apagar_por_paro.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
