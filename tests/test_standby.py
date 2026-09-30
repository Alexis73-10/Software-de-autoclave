# tests/test_standby.py
#
# Standby simultáneo de las pantallas QML (ui_qml/bridge/standby.py).
# UIServiceBackend simulado, reloj monotónico inyectado y envío síncrono.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QSignalSpy

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.standby import (
    MINUTOS_DEFECTO, Standby, debe_estar_en_standby, minutos_standby,
)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Reloj:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


def _ui(connected=True, estado="PREPARADO", inactividad=None, minutos=5, alarmas=None):
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = connected
    ui.get_estado_global.return_value = estado
    ui.get_inactividad_ui.return_value = inactividad
    ui.get_config_param.side_effect = lambda n: minutos if n == "tiempo_standby" else None
    ui.get_alarmas.return_value = alarmas or []
    return ui


def _standby(ui, reloj=None, **kw):
    backend = MagicMock()
    s = Standby(ui, backend, reloj=reloj or _Reloj(), ejecutar=lambda t: t(), iniciar=False, **kw)
    return s, backend


# ── regla pura ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor, esperado", [
    (5, 5.0), (1, 1.0), (2.5, 2.5), (0, MINUTOS_DEFECTO), (-3, MINUTOS_DEFECTO),
    (None, MINUTOS_DEFECTO), (True, MINUTOS_DEFECTO), ("5", MINUTOS_DEFECTO),
])
def test_minutos_standby(valor, esperado):
    assert minutos_standby(valor) == esperado


def test_regla_usa_la_menor_inactividad():
    assert debe_estar_en_standby(True, 301, 400, 5, "PREPARADO") is True
    assert debe_estar_en_standby(True, 299, 400, 5, "PREPARADO") is False   # la otra pantalla tocó
    assert debe_estar_en_standby(True, 400, 10, 5, "PREPARADO") is False    # esta pantalla tocó
    assert debe_estar_en_standby(True, None, None, 5, "PREPARADO") is True  # nadie ha tocado


@pytest.mark.parametrize("estado", ["CICLO", "FALLA", "EMERGENCIA"])
def test_nunca_en_standby_con_ciclo_falla_o_emergencia(estado):
    assert debe_estar_en_standby(True, 10_000, 10_000, 5, estado) is False


def test_sin_conexion_solo_cuenta_la_inactividad_local():
    assert debe_estar_en_standby(False, 0, 301, 5, None) is True
    assert debe_estar_en_standby(False, 10_000, 10, 5, None) is False


# ── comportamiento ────────────────────────────────────────────────────────

def test_arranca_en_standby_hasta_el_primer_toque():
    s, _ = _standby(_ui())
    s.evaluar()
    assert s.activo is True


def test_toque_local_despierta_y_avisa_al_backend():
    s, backend = _standby(_ui())
    s.evaluar()
    espia = QSignalSpy(s.activoChanged)
    s.registrarActividad()
    assert s.activo is False
    assert espia.count() == 1
    backend.post.assert_called_once_with("/ui/activity")


def test_toque_en_la_otra_pantalla_despierta_esta():
    ui = _ui(inactividad=None)
    s, _ = _standby(ui)
    s.evaluar()
    assert s.activo is True
    ui.get_inactividad_ui.return_value = 0.3     # la otra pantalla informó un toque
    s.evaluar()
    assert s.activo is False


def test_cinco_minutos_sin_actividad_en_ninguna_pantalla():
    reloj = _Reloj()
    ui = _ui(inactividad=0.0)
    s, _ = _standby(ui, reloj)
    s.registrarActividad()
    assert s.activo is False

    reloj.t += 299
    ui.get_inactividad_ui.return_value = 299
    s.evaluar()
    assert s.activo is False

    reloj.t += 1
    ui.get_inactividad_ui.return_value = 300
    s.evaluar()
    assert s.activo is True


def test_tiempo_standby_se_lee_de_los_parametros_globales():
    reloj = _Reloj()
    ui = _ui(inactividad=0.0, minutos=1)
    s, _ = _standby(ui, reloj)
    s.registrarActividad()
    reloj.t += 60
    ui.get_inactividad_ui.return_value = 60
    s.evaluar()
    assert s.activo is True


def test_envio_limitado_a_uno_por_segundo_mientras_esta_despierto():
    reloj = _Reloj()
    s, backend = _standby(_ui(), reloj)
    s.registrarActividad()           # despierta: envía
    s.registrarActividad()           # < 1 s: no reenvía
    reloj.t += 1.0
    s.registrarActividad()           # >= 1 s: envía
    assert backend.post.call_count == 2


def test_cambio_de_estado_del_equipo_despierta_ambas():
    reloj = _Reloj()
    ui = _ui(estado="PREPARACION", inactividad=None)
    s, backend = _standby(ui, reloj)
    s.evaluar()                      # primera lectura: no es evento
    assert s.activo is True
    backend.post.assert_not_called()

    ui.get_estado_global.return_value = "PREPARADO"
    s.evaluar()
    assert s.activo is False
    backend.post.assert_called_with("/ui/activity")


def test_alarma_nueva_despierta_pero_la_misma_no():
    ui = _ui(inactividad=None, alarmas=[{"id": "A"}])
    s, backend = _standby(ui)
    s.evaluar()
    s.evaluar()
    assert s.activo is True
    backend.post.assert_not_called()

    ui.get_alarmas.return_value = [{"id": "A"}, {"id": "B"}]
    s.evaluar()
    assert s.activo is False


def test_menu_de_configuracion_abierto_mantiene_despierto():
    reloj = _Reloj()
    abierto = {"v": True}
    ui = _ui(inactividad=None)
    s, _ = _standby(ui, reloj, mantener_despierto=lambda: abierto["v"])
    s.evaluar()
    assert s.activo is False
    abierto["v"] = False
    reloj.t += 301
    ui.get_inactividad_ui.return_value = 301
    s.evaluar()
    assert s.activo is True


def test_sin_backend_el_envio_fallido_no_rompe():
    s, backend = _standby(_ui(connected=False))
    backend.post.side_effect = ConnectionError("sin backend")
    s.registrarActividad()
    assert s.activo is False


@pytest.mark.parametrize("tipo", [
    QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin, QEvent.Type.KeyPress,
])
def test_filtro_de_eventos_registra_toques_y_teclas_sin_consumirlos(tipo):
    s, _ = _standby(_ui())
    assert s.eventFilter(None, QEvent(tipo)) is False
    assert s.activo is False


def test_filtro_ignora_otros_eventos():
    s, _ = _standby(_ui())
    s.evaluar()
    assert s.eventFilter(None, QEvent(QEvent.Type.MouseMove)) is False
    assert s.activo is True
