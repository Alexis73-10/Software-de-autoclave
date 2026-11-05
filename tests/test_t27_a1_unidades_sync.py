# tests/test_t27_a1_unidades_sync.py
#
# A1 (tanda 27): las unidades siguen al backend desde el arranque de la
# ventana (no solo al abrir Opciones), como idioma y tema.

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.ui_qml.bridge import unidades_qml
from autoclave.ui_qml.bridge.unidades_qml import UnidadesQml


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _par():
    """Dos 'ventanas' (instancias) que consultan el mismo backend simulado."""
    backend = {"temperatura": "C", "presion": "kPa", "p_atm": 100.0}
    return backend, UnidadesQml(consultar=lambda: dict(backend), sondear=False), \
        UnidadesQml(consultar=lambda: dict(backend), sondear=False)


def test_cambio_en_la_ventana_1_se_aplica_en_la_2():
    backend, v1, v2 = _par()
    v1.aplicar(dict(backend))
    v2.aplicar(dict(backend))
    backend.update(temperatura="F", presion="psi")       # PUT hecho desde la 1
    v1.refrescar()
    v2.aplicar(dict(backend))                            # siguiente sondeo de la 2
    assert (v2.temperatura, v2.presion) == ("F", "psi")
    assert v2.version > 0


def test_respuesta_invalida_no_cambia_nada():
    _, v1, _ = _par()
    v1.aplicar({"temperatura": "F", "presion": "bar", "p_atm": 100.0})
    version = v1.version
    for mala in (None, "x", [], {}, {"temperatura": "K", "presion": "kPa"},
                 {"temperatura": "C", "presion": "atm"}, {"temperatura": "C"}):
        v1.aplicar(mala)
        assert (v1.temperatura, v1.presion, v1.version) == ("F", "bar", version)


def test_iniciar_sondeo_arranca_el_timer_una_sola_vez():
    u = UnidadesQml(consultar=lambda: None, sondear=False)
    assert not u._timer.isActive()
    unidades_qml.iniciar_sondeo(u)
    assert u._timer.isActive()
    unidades_qml.iniciar_sondeo(u)                       # idempotente
    assert u._timer.isActive()
    u._timer.stop()


def test_app_arranca_el_sondeo_de_unidades_al_crear_la_ventana():
    fuente = Path(unidades_qml.__file__).parent.parent / "app.py"
    assert "unidades_qml.iniciar_sondeo()" in fuente.read_text(encoding="utf-8")
