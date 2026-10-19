"""U4 (tanda 2): UiBridge publica el estado de la tarjeta de E/S y paroActivo
solo con el paro real (sin datos de la tarjeta no se afirma paro)."""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend  # noqa: E402
from autoclave.ui_qml.bridge.ui_bridge import UiBridge  # noqa: E402


def _puente(flags, campos, conectado=True):
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = conectado
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: flags.get(f, False)
    ui.get_campo.side_effect = lambda c, d=None: campos.get(c, d)
    ui.get_cycle.return_value = {}
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()
    return puente


@pytest.mark.parametrize("valor,esperado", [
    ("ok", "ok"), ("sin_tramas_validas", "sin_tramas_validas"),
    ("desconectada", "desconectada"), (None, "desconectada"), ("raro", "desconectada"),
])
def test_estado_tarjeta(valor, esperado):
    campos = {} if valor is None else {"estado_tarjeta": valor}
    assert _puente({}, campos).estadoTarjeta == esperado


def test_sin_conexion_con_el_backend_la_tarjeta_es_desconectada():
    assert _puente({}, {"estado_tarjeta": "ok"}, conectado=False).estadoTarjeta == "desconectada"


def test_paro_activo_solo_con_paro_real():
    sin_datos = _puente({"PARO_EMERGENCIA": True}, {"estado_tarjeta": "desconectada"})
    assert sin_datos.paroActivo is False
    real = _puente({"PARO_EMERGENCIA": True, "PARO_REAL": True}, {"estado_tarjeta": "ok"})
    assert real.paroActivo is True
