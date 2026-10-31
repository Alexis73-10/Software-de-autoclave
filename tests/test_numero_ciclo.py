# tests/test_numero_ciclo.py
#
# "cycle_number": indicativo de cada ciclo (se muestra como CICLO ACTIVO en la
# pantalla QML). Único entre ciclos distintos; la copia factory/ y user/ de un
# mismo cycle_id comparte número.

import json
from pathlib import Path

import pytest

from autoclave.core.managers.cycle_manager import Cycle, CycleManager, _numero_de_ciclo
from autoclave.ui_qml.domain.pantalla_ciclo import SIN_DATO, numero_de_ciclo

CICLOS = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"


def _perfiles():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CICLOS.glob("*/*.json"))]


def test_todos_los_perfiles_traen_numero_entero_positivo():
    for d in _perfiles():
        assert _numero_de_ciclo(d.get("cycle_number")) is not None, d["cycle_id"]


def test_numeros_unicos_entre_ciclos_distintos():
    numero_por_id = {}
    for d in _perfiles():
        previo = numero_por_id.setdefault(d["cycle_id"], d["cycle_number"])
        assert previo == d["cycle_number"], f"{d['cycle_id']}: factory y user difieren"
    numeros = list(numero_por_id.values())
    assert len(numeros) == len(set(numeros)), numero_por_id


def test_bowe_dick_es_el_01():
    assert {d["cycle_id"]: d["cycle_number"] for d in _perfiles()}["bowe_dick"] == 1


def test_cycle_manager_carga_el_numero():
    cm = CycleManager()
    cm.load_all_cycles()
    assert cm.cycles["bowe_dick"].number == 1
    assert all(c.number is not None for c in cm.cycles.values())


def test_numero_repetido_se_descarta_en_ambos_ciclos():
    cm = CycleManager()
    cm.cycles = {
        "a": Cycle("a", "A", {}, number=1),
        "b": Cycle("b", "B", {}, number=1),
        "c": Cycle("c", "C", {}, number=2),
    }
    cm._descartar_numeros_repetidos()
    assert (cm.cycles["a"].number, cm.cycles["b"].number, cm.cycles["c"].number) == (None, None, 2)


@pytest.mark.parametrize("valor, esperado", [
    (1, 1), (7, 7), (0, None), (-1, None), (True, None), ("1", None), (1.0, None), (None, None),
])
def test_numero_de_ciclo_valido(valor, esperado):
    assert _numero_de_ciclo(valor) == esperado


@pytest.mark.parametrize("ciclo, esperado", [
    ({"number": 1}, "01"), ({"number": 3}, "03"), ({"number": 10}, "10"),
    ({"number": None}, SIN_DATO), ({}, SIN_DATO), (None, SIN_DATO), ({"number": True}, SIN_DATO),
])
def test_formato_en_pantalla(ciclo, esperado):
    assert numero_de_ciclo(ciclo) == esperado
