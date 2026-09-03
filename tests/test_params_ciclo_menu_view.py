import sys
import pytest


# QApplication debe existir antes de crear cualquier widget
@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_view_instancia_sin_crash():
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo_menu import (
        ParametrosCicloMenuView,
    )
    view = ParametrosCicloMenuView(nav_callback=lambda x: None)
    assert view is not None


def test_options_tiene_tres_entradas_correctas():
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo_menu import _OPTIONS

    assert len(_OPTIONS) == 3
    labels = [label for (_icon, label, _target) in _OPTIONS]
    targets = [target for (_icon, _label, target) in _OPTIONS]
    assert labels == [
        "Sensores de temperatura",
        "Entradas exhibidas",
        "Fases del ciclo",
    ]
    assert targets == [
        "sensores_temperatura_ciclo",
        "entradas_exhibidas_ciclo",
        "params_ciclo",
    ]


def test_boton_atras_navega_a_admin_menu():
    from PySide6.QtWidgets import QPushButton
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo_menu import (
        ParametrosCicloMenuView,
    )

    nav_calls = []
    view = ParametrosCicloMenuView(nav_callback=nav_calls.append)

    back_buttons = [
        btn for btn in view.findChildren(QPushButton) if btn.text() == "←"
    ]
    assert len(back_buttons) == 1
    back_buttons[0].click()

    assert nav_calls == ["admin_menu"]


def test_botones_de_opcion_navegan_al_target_correcto():
    from PySide6.QtWidgets import QPushButton
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo_menu import (
        ParametrosCicloMenuView,
        _OPTIONS,
    )

    nav_calls = []
    view = ParametrosCicloMenuView(nav_callback=nav_calls.append)

    option_buttons = [
        btn for btn in view.findChildren(QPushButton) if btn.text() != "←"
    ]
    assert len(option_buttons) == len(_OPTIONS)

    for btn, (icon, label, target) in zip(option_buttons, _OPTIONS):
        assert label in btn.text()
        assert icon in btn.text()
        nav_calls.clear()
        btn.click()
        assert nav_calls == [target]


def test_admin_menu_rutea_params_ciclo_a_params_ciclo_menu():
    from autoclave.ui_pyside.views.admin_menu import _OPTION_ROUTES

    assert _OPTION_ROUTES["Parámetros del ciclo"] == "params_ciclo_menu"
