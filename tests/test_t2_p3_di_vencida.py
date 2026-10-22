"""T2 / P-3 (tanda 6): una trama DI vencida con el enlace activo (PARO_EMERGENCIA
sin PARO_REAL) durante el ciclo tiene una tolerancia antes de abortar y se
registra como fallo de comunicación (FALLO_CONEXION + COM-03), no como
EMERGENCIA. La tolerancia nunca supera el watchdog del firmware
(Hardware/Comunicacion_esclava_ESP32_V3, WD_TIMEOUT_MS) menos 1 s de margen."""

import re
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

_INO = (Path(__file__).resolve().parents[1] / "Hardware" / "Comunicacion_esclava_ESP32_V3"
        / "Comunicacion_esclava_ESP32_V3" / "Comunicacion_esclava_ESP32_V3.ino")


def _wd_firmware_s() -> float:
    texto = _INO.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"WD_TIMEOUT_MS\s*=\s*(\d+)", texto)
    assert m, "no se encontró WD_TIMEOUT_MS en el .ino"
    return int(m.group(1)) / 1000.0


def test_tolerancia_no_supera_el_watchdog_del_firmware_menos_un_segundo():
    wd = _wd_firmware_s()
    assert wd == 5.0                                   # valor leído el 20-oct (V3)
    tol = modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG
    assert 0 < tol <= wd - 1.0


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def _ciclo(flags):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 120.0}
    # S1 (tanda 8): la chaqueta también se vigila en ciclo (io_enabled)
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                            # S1: empaque sin lectura falla el ciclo (SEN-08)
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    estado.motivo_fallo = ""
    cycle = MagicMock()
    cycle.get_param.return_value = None
    cycle.copia.return_value = cycle
    cycle.sensores = None
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    ciclo._fases[0].update = MagicMock(return_value=None)
    return ciclo, estado, am


def test_dentro_de_la_tolerancia_no_aborta_ni_mueve_nada(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    for _ in range(3):
        assert ciclo.run() == CicloResultado.EN_CURSO
        reloj[0] += 1.0
    ciclo._protocolo.ejecutar.assert_not_called()
    ciclo._fases[0].update.assert_not_called()          # la fase no avanza con DI viejas
    assert am.activas() == []


def test_pasada_la_tolerancia_es_fallo_de_conexion_sin_valvulas(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    assert ciclo.run() == CicloResultado.EN_CURSO
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_CONEXION"           # no "EMERGENCIA"
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)
    assert [i.codigo for i in am.activas()] == ["COM-03"]
    assert ciclo._resultado_pendiente == CicloResultado.FALLO


def test_si_vuelven_las_tramas_la_tolerancia_se_reinicia(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    ciclo.run()
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG - 0.5
    flags["PARO_EMERGENCIA"] = False
    for _ in range(modulo_ciclo._TICKS_DI_VIGENTE_REINICIO):
        assert ciclo.run() == CicloResultado.EN_CURSO
    flags["PARO_EMERGENCIA"] = True
    reloj[0] += 1.0
    assert ciclo.run() == CicloResultado.EN_CURSO           # cuenta desde cero
    ciclo._protocolo.ejecutar.assert_not_called()


def test_trama_intermitente_no_renueva_la_tolerancia(reloj):
    # TMG-03 / SAF-01 de la revisión de T2
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    ciclo.run()
    reloj[0] += 3.0
    flags["PARO_EMERGENCIA"] = False
    ciclo.run()                                             # una sola trama buena
    flags["PARO_EMERGENCIA"] = True
    reloj[0] += 1.5
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_CONEXION"


def test_durante_la_tolerancia_se_corta_el_vapor(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    ciclo.run()
    ciclo.set_do.vapor_camara_off.assert_called()
    ciclo.set_do.vapor_chaqueta_off.assert_called()


def test_paro_real_sigue_siendo_inmediato(reloj):
    flags = {"PARO_EMERGENCIA": True, "PARO_REAL": True}
    ciclo, estado, am = _ciclo(flags)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "EMERGENCIA"
    assert [i.codigo for i in am.activas()] == ["SIS-01"]
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)


def test_paro_real_durante_la_tolerancia_aborta_al_instante(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, am = _ciclo(flags)
    ciclo.run()
    flags["PARO_REAL"] = True
    reloj[0] += 0.5
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "EMERGENCIA"


def test_cancelacion_durante_la_tolerancia_no_se_ejecuta(reloj):
    # con datos viejos no se sabe si hay paro: la cancelación espera
    flags = {"PARO_EMERGENCIA": True, "CICLO_CANCELADO": True}
    ciclo, estado, am = _ciclo(flags)
    assert ciclo.run() == CicloResultado.EN_CURSO
    ciclo._protocolo.ejecutar.assert_not_called()
