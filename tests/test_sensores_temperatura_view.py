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

    def __init__(self, cycle_id="c1", name="Ciclo de prueba", sensor_roles=None):
        self.id = cycle_id
        self.name = name
        self.sensor_roles = sensor_roles or {}
        self.source = "user"


def _no_sonda_liquido():
    return patch(
        "autoclave.ui_pyside.views.params_ciclo.sensores_temperatura._equipo_tiene_sonda_liquido",
        return_value=False,
    )


# ── instanciación básica ────────────────────────────────────────────────


def test_view_instancia_sin_crash():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    assert view is not None


def test_boton_atras_navega_a_params_ciclo_menu():
    from PySide6.QtWidgets import QPushButton
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    nav_calls = []
    view = SensoresTemperaturaView(nav_callback=nav_calls.append)

    back_buttons = [btn for btn in view.findChildren(QPushButton) if btn.text() == "←"]
    assert len(back_buttons) == 1
    back_buttons[0].click()

    assert nav_calls == ["params_ciclo_menu"]


# ── _SensorRoleRow: set_role/get_role round-trip ────────────────────────


@pytest.mark.parametrize("rol", ["principal", "referencia", "no_en_uso"])
def test_sensor_role_row_set_get_role_roundtrip(rol):
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import _SensorRoleRow

    row = _SensorRoleRow("temp_camara", on_change=lambda s, r: None)
    row.set_role(rol)
    assert row.get_role() == rol


def test_sensor_role_row_rol_desconocido_cae_a_no_en_uso():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import _SensorRoleRow

    row = _SensorRoleRow("temp_camara", on_change=lambda s, r: None)
    row.set_role("rol_que_no_existe")
    assert row.get_role() == "no_en_uso"


def test_sensor_role_row_set_role_no_dispara_on_change():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import _SensorRoleRow

    calls = []
    row = _SensorRoleRow("temp_camara", on_change=lambda s, r: calls.append((s, r)))
    row.set_role("principal")
    row.set_role("referencia")

    # set_role() bloquea señales -- no debe disparar el callback de la fila
    assert calls == []


# ── mutua exclusión de "Principal" entre filas, vía click() real ───────


def test_click_principal_desmarca_principal_de_otra_fila():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "principal", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    assert view._rows["temp_camara"].get_role() == "principal"
    assert view._rows["temp_ref"].get_role() == "no_en_uso"

    with patch.object(view._client, "patch") as mock_patch:
        view._rows["temp_ref"]._buttons["principal"].click()

    # la mutua exclusión se disparó por la señal real de Qt, no por llamada directa
    assert view._rows["temp_ref"].get_role() == "principal"
    assert view._rows["temp_camara"].get_role() == "no_en_uso"

    mock_patch.assert_called_once()
    path, body = mock_patch.call_args[0][0], mock_patch.call_args[0][1]
    assert path == "/cycle/sensor-roles"
    assert body["cycle_id"] == cycle.id
    assert body["sensor_roles"]["temp_ref"] == "principal"
    assert body["sensor_roles"]["temp_camara"] == "no_en_uso"

    # el estado en memoria del ciclo también se actualizó
    assert cycle.sensor_roles["temp_ref"] == "principal"
    assert cycle.sensor_roles["temp_camara"] == "no_en_uso"


def test_click_no_en_uso_no_afecta_principal_de_otra_fila():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "principal", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    with patch.object(view._client, "patch"):
        view._rows["temp_ref"]._buttons["referencia"].click()

    assert view._rows["temp_camara"].get_role() == "principal"
    assert view._rows["temp_ref"].get_role() == "referencia"


# ── manejo de errores del PATCH: QMessageBox sin crash ──────────────────


def test_error_de_red_en_patch_muestra_messagebox_sin_crashear():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    with patch.object(
        view._client, "patch", side_effect=requests.ConnectionError("backend caído")
    ), patch(
        "autoclave.ui_pyside.views.params_ciclo.sensores_temperatura.QMessageBox"
    ) as mock_box:
        view._rows["temp_camara"]._buttons["referencia"].click()

    mock_box.critical.assert_called_once()
    # el cambio no se persistió en el estado en memoria del ciclo
    assert cycle.sensor_roles["temp_camara"] == "no_en_uso"


def test_error_http_en_patch_muestra_detail_del_backend():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    err = requests.HTTPError("422 Unprocessable Entity")
    err.response = MagicMock()
    err.response.json.return_value = {"detail": "Solo puede haber un sensor 'principal'"}

    with patch.object(view._client, "patch", side_effect=err), patch(
        "autoclave.ui_pyside.views.params_ciclo.sensores_temperatura.QMessageBox"
    ) as mock_box:
        view._rows["temp_camara"]._buttons["principal"].click()

    mock_box.critical.assert_called_once()
    _self_arg, _title, message = mock_box.critical.call_args[0]
    assert "Solo puede haber un sensor" in message


def test_error_en_patch_durante_degradacion_no_corrompe_estado():
    """Regresión: click en "Principal" sobre una fila mientras OTRA fila es
    "principal" (dispara la mutua exclusión) Y el PATCH falla. Antes del fix,
    self._cycle.sensor_roles del sensor degradado se mutaba de forma eager e
    incondicional ANTES del PATCH y nunca se revertía en el `except`, dejando
    el ciclo en memoria sin ningún sensor "principal" aunque el servidor
    nunca recibió el cambio."""
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "principal", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    with patch.object(
        view._client, "patch", side_effect=requests.ConnectionError("backend caído")
    ), patch(
        "autoclave.ui_pyside.views.params_ciclo.sensores_temperatura.QMessageBox"
    ) as mock_box:
        view._rows["temp_ref"]._buttons["principal"].click()

    mock_box.critical.assert_called_once()

    # el modelo en memoria del ciclo queda exactamente como estaba antes del click
    assert cycle.sensor_roles == {"temp_camara": "principal", "temp_ref": "no_en_uso"}

    # la fila degradada (temp_camara) nunca se tocó: su widget sigue en "principal"
    assert view._rows["temp_camara"].get_role() == "principal"

    # la fila CLICKEADA (temp_ref) revierte a su rol anterior -- Qt ya había
    # cambiado el radio button ANTES de que el handler corriera, así que sin
    # el revert explícito quedaría mostrando "principal" pese al PATCH fallido
    assert view._rows["temp_ref"].get_role() == "no_en_uso"


def test_click_referencia_desmarca_referencia_de_otra_fila():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={"temp_camara": "referencia", "temp_ref": "no_en_uso"}
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    assert view._rows["temp_camara"].get_role() == "referencia"
    assert view._rows["temp_ref"].get_role() == "no_en_uso"

    with patch.object(view._client, "patch") as mock_patch:
        view._rows["temp_ref"]._buttons["referencia"].click()

    # la mutua exclusión se disparó por la señal real de Qt, no por llamada directa
    assert view._rows["temp_ref"].get_role() == "referencia"
    assert view._rows["temp_camara"].get_role() == "no_en_uso"

    mock_patch.assert_called_once()
    path, body = mock_patch.call_args[0][0], mock_patch.call_args[0][1]
    assert path == "/cycle/sensor-roles"
    assert body["cycle_id"] == cycle.id
    assert body["sensor_roles"]["temp_ref"] == "referencia"
    assert body["sensor_roles"]["temp_camara"] == "no_en_uso"

    # el estado en memoria del ciclo también se actualizó
    assert cycle.sensor_roles["temp_ref"] == "referencia"
    assert cycle.sensor_roles["temp_camara"] == "no_en_uso"


# ── _candidatos(): filtro por capacidad de equipo ────────────────────────


def test_candidatos_incluye_temp_2_camara_si_equipo_tiene_sonda_liquido():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)

    fake_profile = MagicMock(equipment_class="MESA_B_LAB")
    fake_caps = MagicMock(has_liquid_sensor=True)

    with patch(
        "autoclave.installation.storage.exists", return_value=True
    ), patch(
        "autoclave.installation.storage.load", return_value=fake_profile
    ), patch(
        "autoclave.installation.equipment.get_capabilities", return_value=fake_caps
    ):
        candidatos = view._candidatos()

    assert candidatos == ["temp_camara", "temp_2_camara", "temp_ref"]


def test_candidatos_excluye_temp_2_camara_si_equipo_no_tiene_sonda_liquido():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)

    fake_profile = MagicMock(equipment_class="MESA_N")
    fake_caps = MagicMock(has_liquid_sensor=False)

    with patch(
        "autoclave.installation.storage.exists", return_value=True
    ), patch(
        "autoclave.installation.storage.load", return_value=fake_profile
    ), patch(
        "autoclave.installation.equipment.get_capabilities", return_value=fake_caps
    ):
        candidatos = view._candidatos()

    assert candidatos == ["temp_camara", "temp_ref"]


def test_candidatos_sin_perfil_instalacion_no_lanza_excepcion():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)

    with patch("autoclave.installation.storage.exists", return_value=False):
        candidatos = view._candidatos()

    assert candidatos == ["temp_camara", "temp_ref"]


def test_candidatos_perfil_invalido_no_lanza_excepcion():
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)

    with patch("autoclave.installation.storage.exists", return_value=True), patch(
        "autoclave.installation.storage.load", side_effect=Exception("perfil corrupto")
    ):
        candidatos = view._candidatos()

    assert candidatos == ["temp_camara", "temp_ref"]


# ── sensor "principal" atascado fuera del filtro de capacidad ───────────


def test_sensor_principal_fuera_de_capacidad_se_muestra_y_se_puede_liberar():
    """Ciclo configurado con temp_2_camara="principal" en equipo que en ese
    momento tenía sonda de líquido, abierto luego en equipo SIN esa sonda.
    _candidatos() ya no incluye temp_2_camara, pero la fila debe seguir
    renderizada (marcada como no disponible) para que el operador pueda
    verla y degradarla, liberando el slot "principal" para otro sensor."""
    from autoclave.ui_pyside.views.params_ciclo.sensores_temperatura import (
        SensoresTemperaturaView,
    )

    view = SensoresTemperaturaView(nav_callback=lambda x: None)
    cycle = _FakeCycle(
        sensor_roles={
            "temp_camara": "no_en_uso",
            "temp_2_camara": "principal",
            "temp_ref": "no_en_uso",
        }
    )

    with _no_sonda_liquido():
        view._load_cycle(cycle)

    # La fila se renderiza aunque el equipo actual no tenga sonda de líquido.
    assert "temp_2_camara" in view._rows
    row = view._rows["temp_2_camara"]
    assert row.get_role() == "principal"
    assert row.no_disponible is True

    # El resto de filas normales siguen presentes y sin marcar.
    assert view._rows["temp_camara"].no_disponible is False
    assert view._rows["temp_ref"].no_disponible is False

    # Degradar la fila atascada a "No en uso" (click real) libera el slot
    # "principal" -- el PATCH debe ir sin error de validación en el mock.
    with patch.object(view._client, "patch") as mock_patch:
        row._buttons["no_en_uso"].click()

    mock_patch.assert_called_once()
    body = mock_patch.call_args[0][1]
    assert body["sensor_roles"]["temp_2_camara"] == "no_en_uso"
    assert cycle.sensor_roles["temp_2_camara"] == "no_en_uso"
    assert row.get_role() == "no_en_uso"

    # Ahora se puede asignar "principal" a otro sensor sin conflicto.
    with patch.object(view._client, "patch") as mock_patch_2:
        view._rows["temp_camara"]._buttons["principal"].click()

    mock_patch_2.assert_called_once()
    body_2 = mock_patch_2.call_args[0][1]
    assert body_2["sensor_roles"]["temp_camara"] == "principal"
    assert view._rows["temp_camara"].get_role() == "principal"
    assert cycle.sensor_roles["temp_camara"] == "principal"


# ── registro en main_window ──────────────────────────────────────────────


def test_main_window_registra_sensores_temperatura_ciclo():
    import ast
    from pathlib import Path

    src_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "autoclave"
        / "ui_pyside"
        / "main_window.py"
    )
    src = src_path.read_text(encoding="utf-8")

    assert "SensoresTemperaturaView" in src
    assert '"sensores_temperatura_ciclo": self._sensores_temperatura_ciclo' in src
