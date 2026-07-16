import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_impresion_menu_instancia_sin_crash():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    view = ImpresionMenuView(nav_callback=lambda x: None)
    assert view is not None


def test_impresion_menu_tiene_dos_opciones():
    from autoclave.ui_pyside.views.impresion_menu import _PRINT_OPTIONS
    assert len(_PRINT_OPTIONS) == 2
    targets = [target for _, _, target in _PRINT_OPTIONS]
    assert "ciclos" in targets
    assert None in targets


def test_boton_ciclos_navega_a_vista_ciclos():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtWidgets import QPushButton

    nav_calls = []
    view = ImpresionMenuView(nav_callback=nav_calls.append)

    target_btn = next(
        b for b in view.findChildren(QPushButton)
        if "Imprimir Ciclos" in b.text()
    )
    target_btn.click()
    assert nav_calls == ["ciclos"]


def test_boton_back_navega_a_home():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtWidgets import QPushButton

    nav_calls = []
    view = ImpresionMenuView(nav_callback=nav_calls.append)

    back_btn = next(
        b for b in view.findChildren(QPushButton) if b.text() == "←"
    )
    back_btn.click()
    assert nav_calls == ["home"]


def test_build_alarms_ticket_lines_incluye_datos_de_la_alarma():
    from autoclave.ui_pyside.views.impresion_menu import _build_alarms_ticket_lines

    alarms = [{
        "id": "PUERTA_NO_CERRADA",
        "level": "FALLA",
        "description": "Puerta frontal no cerrada",
        "source_state": "PREPARACION",
    }]

    text = "\n".join(_build_alarms_ticket_lines(alarms))

    assert "ID: PUERTA_NO_CERRADA" in text
    assert "Nivel: FALLA" in text
    assert "Origen: PREPARACION" in text
    assert "Puerta frontal no cerrada" in text
    assert "Total: 1 alarma(s)" in text


def test_build_alarms_ticket_lines_lista_vacia_reporta_total_cero():
    from autoclave.ui_pyside.views.impresion_menu import _build_alarms_ticket_lines

    text = "\n".join(_build_alarms_ticket_lines([]))

    assert "Total: 0 alarma(s)" in text


def test_build_alarms_ticket_lines_multiples_alarmas():
    from autoclave.ui_pyside.views.impresion_menu import _build_alarms_ticket_lines

    alarms = [
        {"id": "A1", "level": "ALERTA", "description": "d1", "source_state": "CICLO"},
        {"id": "A2", "level": "EMERGENCIA", "description": "d2", "source_state": "CICLO"},
    ]

    text = "\n".join(_build_alarms_ticket_lines(alarms))

    assert "ID: A1" in text
    assert "ID: A2" in text
    assert "Total: 2 alarma(s)" in text


def test_print_alarms_sin_alarmas_muestra_aviso_no_imprime():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": []}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.print_raw") as mock_print:
        view._print_alarms()

        mock_box.information.assert_called_once()
        mock_print.assert_not_called()


def test_print_alarms_backend_no_disponible_muestra_aviso_no_imprime():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.side_effect = Exception("backend caído")

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.print_raw") as mock_print:
        view._print_alarms()

        mock_box.information.assert_called_once()
        mock_print.assert_not_called()


def test_print_alarms_con_alarmas_imprime_directo_sin_dialogo():
    from autoclave.ui_pyside.views.impresion_menu import (
        ImpresionMenuView,
        PRINTER_NAME,
        _build_alarms_ticket_lines,
    )

    alarms = [{
        "id": "X", "level": "ALERTA",
        "description": "desc", "source_state": "CICLO",
    }]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.print_raw") as mock_print:
        mock_print.return_value = True
        view._print_alarms()

        mock_box.information.assert_not_called()
        mock_box.warning.assert_not_called()
        mock_print.assert_called_once()

        text_arg, printer_arg = mock_print.call_args[0]
        assert printer_arg == PRINTER_NAME
        expected_text = "\n".join(_build_alarms_ticket_lines(alarms))
        assert "ID: X" in text_arg
        assert "Nivel: ALERTA" in text_arg
        assert "Origen: CICLO" in text_arg
        assert "Total: 1 alarma(s)" in text_arg
        # Compara la cantidad de líneas contra la construcción real (salvo el
        # timestamp, que puede variar en microsegundos entre ambas llamadas).
        assert len(text_arg.split("\n")) == len(expected_text.split("\n"))


def test_print_alarms_falla_impresion_muestra_aviso():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    alarms = [{
        "id": "X", "level": "ALERTA",
        "description": "desc", "source_state": "CICLO",
    }]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.print_raw") as mock_print:
        mock_print.return_value = False
        view._print_alarms()

        mock_print.assert_called_once()
        mock_box.warning.assert_called_once()
