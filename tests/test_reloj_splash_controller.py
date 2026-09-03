# tests/test_reloj_splash_controller.py
#
# Puente QObject entre domain/reloj_splash.py (funciones puras) y el
# componente QML PantallaInicio. `ahora_fn` es inyectable para no depender
# del reloj real ni de esperar al QTimer en las pruebas.

import sys
from datetime import datetime

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.controllers.reloj_splash_controller import RelojSplashController


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _controller(ahora):
    return RelojSplashController(ahora_fn=lambda: ahora)


def test_estado_inicial_ya_refleja_la_hora_inyectada():
    controller = _controller(datetime(2026, 8, 12, 16, 0))
    assert controller.horaActual == "16:00"
    assert controller.fechaActual == "12 ago - 2026"


def test_actualizar_refresca_hora_con_el_valor_inyectado_actual():
    hora = {"valor": datetime(2026, 8, 12, 16, 0)}
    controller = RelojSplashController(ahora_fn=lambda: hora["valor"])

    hora["valor"] = datetime(2026, 8, 12, 16, 1)
    controller.actualizar()

    assert controller.horaActual == "16:01"


def test_hora_changed_se_emite_al_actualizar_con_minuto_distinto():
    hora = {"valor": datetime(2026, 8, 12, 16, 0)}
    controller = RelojSplashController(ahora_fn=lambda: hora["valor"])
    spy = QSignalSpy(controller.horaActualChanged)

    hora["valor"] = datetime(2026, 8, 12, 16, 1)
    controller.actualizar()

    assert spy.count() == 1


def test_fecha_changed_no_se_emite_si_la_fecha_no_cambio():
    hora = {"valor": datetime(2026, 8, 12, 16, 0)}
    controller = RelojSplashController(ahora_fn=lambda: hora["valor"])
    spy = QSignalSpy(controller.fechaActualChanged)

    hora["valor"] = datetime(2026, 8, 12, 16, 1)
    controller.actualizar()

    assert spy.count() == 0


def test_fecha_changed_se_emite_al_cruzar_medianoche():
    hora = {"valor": datetime(2026, 8, 12, 23, 59)}
    controller = RelojSplashController(ahora_fn=lambda: hora["valor"])
    spy = QSignalSpy(controller.fechaActualChanged)

    hora["valor"] = datetime(2026, 8, 13, 0, 0)
    controller.actualizar()

    assert spy.count() == 1
    assert controller.fechaActual == "13 ago - 2026"
