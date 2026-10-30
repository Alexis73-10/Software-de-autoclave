# tests/test_e1_apertura_automatica_sin_actuador.py
#
# E1-4 (CR-FC-02, PF-05 / D-11): con una puerta sin actuador la apertura
# automática no se muestra en Opciones y el ciclo la ignora en silencio,
# aunque el JSON diga true.

from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.door_factory import tipo_tiene_actuador
from autoclave.devices.puertas.door_type import DoorType
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _ciclo(door_service):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 25.0}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.side_effect = lambda s, n, default=None: {
        ("finalizacion", "apertura_automatica"): True,
        ("finalizacion", "tiempo_espera_apertura"): 0,
        ("finalizacion", "temp_max_apertura"): 80.0,
        ("finalizacion", "timeout_temperatura"): 30,
    }.get((s, n), default)
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, MagicMock(), cycle, config, alarm_manager, door_service=door_service)
    ciclo.reset()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    return ciclo, estado, alarm_manager


def _servicio(tiene_actuador):
    ds = MagicMock()
    ds.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    ds.tiene_actuador.return_value = tiene_actuador
    ds.get_status.return_value = "CERRADO"
    ds.request_open.return_value = (True, "")
    return ds


def test_sin_actuador_sale_sin_reintentos_ni_alarma(monkeypatch):
    import autoclave.state_machine.states.ciclo as mod
    ds = _servicio(tiene_actuador=False)
    ciclo, estado, alarm_manager = _ciclo(ds)
    t = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: t[0])
    for _ in range(40):              # 200 s simulados, más que el aviso de 60 s
        ciclo._mantener_apertura_automatica()
        t[0] += 5.0
    ds.request_open.assert_not_called()
    assert "APERTURA_AUTOMATICA_DENEGADA" not in [c.args[0].id for c in alarm_manager.report.call_args_list]
    estado.set_flag.assert_not_called()


def test_con_actuador_sigue_intentando_abrir(monkeypatch):
    import autoclave.state_machine.states.ciclo as mod
    ds = _servicio(tiene_actuador=True)
    ciclo, _, _ = _ciclo(ds)
    monkeypatch.setattr(mod.time, "monotonic", lambda: 1000.0)
    ciclo._mantener_apertura_automatica()
    ds.request_open.assert_called_once_with("Puerta 2")


@pytest.mark.parametrize("door_type,esperado", [
    (DoorType.SIMPLE, False), (DoorType.ADVANCED, True), (DoorType.MOTORIZED, True),
    (DoorType.LOCKING, True), (DoorType.MOTORIZED_LOCKING, True),
])
def test_tipo_tiene_actuador(door_type, esperado):
    assert tipo_tiene_actuador(door_type) is esperado


def test_opciones_oculta_apertura_automatica_sin_actuador():
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo import _claves_ocultas
    assert _claves_ocultas("finalizacion", tiene_actuador=False) == {"apertura_automatica"}
    assert _claves_ocultas("finalizacion", tiene_actuador=True) == set()
    assert _claves_ocultas("globals", tiene_actuador=False) == set()


def test_iter_section_respeta_ocultas():
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo import _iter_section
    seccion = {"apertura_automatica": {"value": True}, "temp_max_apertura": {"value": 80}}
    nombres = [n for n, _ in _iter_section(seccion, None, ocultas={"apertura_automatica"})]
    assert nombres == ["temp_max_apertura"]
