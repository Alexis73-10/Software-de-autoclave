import sys
from unittest.mock import MagicMock, patch

import pytest
import requests


# QApplication debe existir antes de crear cualquier widget
@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeCycle:
    """Doble mínimo de autoclave.core.managers.cycle_manager.Cycle para tests
    de UI que no necesitan tocar el filesystem/backend."""

    def __init__(self, cycle_id="c1", name="Ciclo de prueba", display_slots=None):
        self.id = cycle_id
        self.name = name
        self.display_slots = display_slots or [None, None, None]
        self.source = "user"


def _todos_los_sensores_esperados():
    from autoclave.core.runtime.status import EstadoAutoclave
    return set(EstadoAutoclave.map_temp.keys()) | set(EstadoAutoclave.map_pres.keys())


# ── instanciación básica ────────────────────────────────────────────────


def test_view_instancia_sin_crash():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    assert view is not None


def test_boton_atras_navega_a_params_ciclo_menu():
    from PySide6.QtWidgets import QPushButton
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    nav_calls = []
    view = EntradasExhibidasView(nav_callback=nav_calls.append)

    back_buttons = [btn for btn in view.findChildren(QPushButton) if btn.text() == "←"]
    assert len(back_buttons) == 1
    back_buttons[0].click()

    assert nav_calls == ["params_ciclo_menu"]


# ── construcción de los 3 combos ────────────────────────────────────────


def test_hay_exactamente_tres_combos_de_casilla():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    assert len(view._combos) == 3


def test_cada_combo_incluye_todos_los_sensores_mas_vacio():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    esperados = _todos_los_sensores_esperados()

    for combo in view._combos:
        assert combo.count() == len(esperados) + 1
        assert combo.itemText(0) == "— Vacío —"
        assert combo.itemData(0) is None

        datos = {combo.itemData(i) for i in range(1, combo.count())}
        assert datos == esperados


# ── carga de un ciclo: pre-selección de combos desde display_slots ─────


def test_load_cycle_preselecciona_combos_desde_display_slots():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=["temp_camara", "pres_camara", None])

    view._load_cycle(cycle)

    assert view._combos[0].currentData() == "temp_camara"
    assert view._combos[1].currentData() == "pres_camara"
    assert view._combos[2].currentData() is None


def test_load_cycle_con_display_slots_todo_vacio():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=[None, None, None])

    view._load_cycle(cycle)

    for combo in view._combos:
        assert combo.currentData() is None
        assert combo.currentIndex() == 0


def test_load_cycle_no_dispara_patch_por_las_preselecciones():
    """set_load_cycle bloquea señales -- pre-seleccionar los combos al
    cargar un ciclo no debe disparar _on_slot_changed / PATCH alguno."""
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=["temp_camara", "pres_camara", None])

    with patch.object(view._client, "patch") as mock_patch:
        view._load_cycle(cycle)

    mock_patch.assert_not_called()


# ── cambiar una casilla vía señal real de Qt ────────────────────────────


def test_cambiar_combo_envia_patch_con_payload_correcto_y_actualiza_modelo():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=[None, None, None])
    view._load_cycle(cycle)

    with patch.object(view._client, "patch") as mock_patch:
        idx = view._combos[0].findData("temp_camara")
        view._combos[0].setCurrentIndex(idx)

    mock_patch.assert_called_once()
    path, body = mock_patch.call_args[0][0], mock_patch.call_args[0][1]
    assert path == "/cycle/display-slots"
    assert body == {"cycle_id": cycle.id, "display_slots": ["temp_camara", None, None]}

    # el estado en memoria del ciclo se actualizó solo después del éxito del PATCH
    assert cycle.display_slots == ["temp_camara", None, None]


def test_cambiar_casilla_a_vacio_envia_none_en_esa_posicion():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=["temp_camara", "pres_camara", None])
    view._load_cycle(cycle)

    with patch.object(view._client, "patch") as mock_patch:
        # índice 0 del combo es siempre "— Vacío —" (data=None)
        view._combos[1].setCurrentIndex(0)

    mock_patch.assert_called_once()
    body = mock_patch.call_args[0][1]
    assert body["display_slots"] == ["temp_camara", None, None]
    assert cycle.display_slots == ["temp_camara", None, None]


def test_mismo_sensor_en_dos_casillas_distintas_no_lanza_error():
    """Sin exclusión mutua entre casillas: repetir el mismo sensor en dos
    combos debe funcionar sin error, a diferencia de sensores_temperatura."""
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=[None, None, None])
    view._load_cycle(cycle)

    with patch.object(view._client, "patch") as mock_patch:
        idx0 = view._combos[0].findData("temp_camara")
        view._combos[0].setCurrentIndex(idx0)
        idx1 = view._combos[1].findData("temp_camara")
        view._combos[1].setCurrentIndex(idx1)

    assert mock_patch.call_count == 2
    assert cycle.display_slots == ["temp_camara", "temp_camara", None]


# ── manejo de errores del PATCH: QMessageBox sin crash ──────────────────


def test_error_de_red_en_patch_muestra_messagebox_sin_crashear():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=[None, None, None])
    view._load_cycle(cycle)

    with patch.object(
        view._client, "patch", side_effect=requests.ConnectionError("backend caído")
    ), patch(
        "autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas.QMessageBox"
    ) as mock_box:
        idx = view._combos[0].findData("temp_camara")
        view._combos[0].setCurrentIndex(idx)

    mock_box.critical.assert_called_once()
    # el cambio no se persistió en el estado en memoria del ciclo
    assert cycle.display_slots == [None, None, None]


def test_error_http_en_patch_muestra_detail_del_backend():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=[None, None, None])
    view._load_cycle(cycle)

    err = requests.HTTPError("422 Unprocessable Entity")
    err.response = MagicMock()
    err.response.json.return_value = {"detail": "Sensor desconocido: 'foo'"}

    with patch.object(view._client, "patch", side_effect=err), patch(
        "autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas.QMessageBox"
    ) as mock_box:
        idx = view._combos[0].findData("temp_camara")
        view._combos[0].setCurrentIndex(idx)

    mock_box.critical.assert_called_once()
    _self_arg, _title, message = mock_box.critical.call_args[0]
    assert "Sensor desconocido" in message
    assert cycle.display_slots == [None, None, None]


def test_error_en_patch_durante_cambio_de_casilla_no_corrompe_estado():
    """Regresión (misma clase de bug corregido en sensores_temperatura,
    Task 10): si el PATCH falla, self._cycle.display_slots NO debe haberse
    mutado antes de la llamada de red -- el modelo en memoria debe quedar
    exactamente como estaba antes del cambio, para que un guardado
    posterior exitoso no reenvíe un estado corrupto (el endpoint reemplaza
    el arreglo completo, no aplica un patch parcial)."""
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle = _FakeCycle(display_slots=["temp_camara", "pres_camara", None])
    view._load_cycle(cycle)

    with patch.object(
        view._client, "patch", side_effect=requests.ConnectionError("backend caído")
    ), patch(
        "autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas.QMessageBox"
    ) as mock_box:
        idx = view._combos[2].findData("temp_ref")
        view._combos[2].setCurrentIndex(idx)

    mock_box.critical.assert_called_once()

    # el modelo en memoria del ciclo queda exactamente como estaba antes del cambio
    assert cycle.display_slots == ["temp_camara", "pres_camara", None]


# ── cambio de ciclo en el combo superior ────────────────────────────────


def test_on_cycle_changed_recarga_los_tres_combos():
    from autoclave.ui_pyside.views.params_ciclo.entradas_exhibidas import (
        EntradasExhibidasView,
    )

    view = EntradasExhibidasView(nav_callback=lambda x: None)
    cycle_a = _FakeCycle(cycle_id="a", name="Ciclo A", display_slots=["temp_camara", None, None])
    cycle_b = _FakeCycle(cycle_id="b", name="Ciclo B", display_slots=[None, "pres_camara", "temp_ref"])
    view._cycles = {"a": cycle_a, "b": cycle_b}

    view._combo_ciclo.blockSignals(True)
    view._combo_ciclo.clear()
    view._combo_ciclo.addItem(cycle_a.name, cycle_a.id)
    view._combo_ciclo.addItem(cycle_b.name, cycle_b.id)
    view._combo_ciclo.blockSignals(False)

    view._load_cycle(cycle_a)
    assert view._combos[0].currentData() == "temp_camara"

    view._on_cycle_changed(1)

    assert view._cycle is cycle_b
    assert view._combos[0].currentData() is None
    assert view._combos[1].currentData() == "pres_camara"
    assert view._combos[2].currentData() == "temp_ref"


# ── registro en main_window ──────────────────────────────────────────────


def test_main_window_registra_entradas_exhibidas_ciclo():
    from pathlib import Path

    src_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "autoclave"
        / "ui_pyside"
        / "main_window.py"
    )
    src = src_path.read_text(encoding="utf-8")

    assert "EntradasExhibidasView" in src
    assert '"entradas_exhibidas_ciclo": self._entradas_exhibidas_ciclo' in src
