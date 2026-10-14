# tests/test_progreso_arranque.py
#
# Simulador de progreso del arranque para la intro (ui_qml/bridge/progreso_arranque.py,
# planeacion_animacion_arranque.md §6). Se avanza a mano con avanzar() /
# declarar_fallo() para no depender de los QTimer.

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.bridge.progreso_arranque import (
    ETAPAS_EJEMPLO,
    SimuladorProgresoArranque,
    parse_simulacion,
)

ES_JSON = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
           / "es.json")


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def test_estado_inicial():
    sim = SimuladorProgresoArranque()
    assert sim.fraccion == 0.0
    assert sim.proceso == "iniciando_servicios"
    assert sim.terminado is False
    assert sim.falloBloqueante is False


def test_cada_etapa_completada_avanza_la_fraccion_y_el_proceso():
    sim = SimuladorProgresoArranque()
    spy = QSignalSpy(sim.cambiado)
    vistos = []
    for _ in ETAPAS_EJEMPLO:
        sim.avanzar()
        vistos.append((sim.fraccion, sim.proceso, sim.terminado))
    assert vistos == [
        (0.25, "conectando_tarjeta", False),
        (0.5, "verificando_sensores", False),
        (0.75, "abriendo_base_datos", False),
        (1.0, "abriendo_base_datos", True),   # al terminar queda el último proceso
    ]
    assert spy.count() == 4
    sim.avanzar()                              # ya terminó: no cambia nada
    assert spy.count() == 4
    sim.detener()


def test_fallo_bloqueante_congela_el_progreso():
    sim = SimuladorProgresoArranque()
    sim.avanzar()
    sim.declarar_fallo()
    sim.avanzar()
    assert sim.falloBloqueante is True
    assert sim.fraccion == 0.25
    assert sim.terminado is False
    sim.detener()


def test_sin_progreso_no_publica_proceso():
    sim = SimuladorProgresoArranque(sin_progreso=True)
    sim.iniciar()
    assert sim.proceso == ""
    assert sim.fraccion == 0.0
    sim.detener()


@pytest.mark.parametrize("valor, esperado", [
    (None, {}),
    ("", {}),
    ("fallo:1.5", {"fallo_en_s": 1.5}),
    ("FALLO:0.3", {"fallo_en_s": 0.3}),
    ("sin_progreso", {"sin_progreso": True}),
    ("fallo:-1", {}),
    ("fallo:x", {}),
    ("otra", {}),
])
def test_parse_simulacion(valor, esperado):
    assert parse_simulacion(valor) == esperado


def test_es_json_trae_los_textos_de_todas_las_etapas():
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))["arranque"]
    claves = [c for c, _ in ETAPAS_EJEMPLO] + ["fallo_titulo", "fallo_bloqueante", "sin_progreso"]
    assert [c for c in claves if not isinstance(textos.get(c), str)] == []
