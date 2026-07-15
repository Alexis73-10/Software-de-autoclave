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


def test_print_alarms_sin_alarmas_muestra_aviso_no_abre_dialogo():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": []}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.QPrintDialog") as mock_dialog:
        view._print_alarms()

        mock_box.information.assert_called_once()
        mock_dialog.assert_not_called()


def test_print_alarms_backend_no_disponible_muestra_aviso_no_abre_dialogo():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.side_effect = Exception("backend caído")

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.QPrintDialog") as mock_dialog:
        view._print_alarms()

        mock_box.information.assert_called_once()
        mock_dialog.assert_not_called()


def test_print_alarms_con_alarmas_dialogo_rechazado_no_dibuja_ticket():
    from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
    from PySide6.QtPrintSupport import QPrintDialog

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {
        "alarms": [{
            "id": "X", "level": "ALERTA",
            "description": "desc", "source_state": "CICLO",
        }]
    }

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.QPrintDialog") as mock_dialog_cls, \
         patch("autoclave.ui_pyside.views.impresion_menu._draw_ticket_lines") as mock_draw:
        # Se preserva el enum real para que la comparación de la clase mockeada
        # en producción (QPrintDialog.DialogCode.Accepted) siga funcionando.
        mock_dialog_cls.DialogCode = QPrintDialog.DialogCode
        mock_dialog_cls.return_value.exec.return_value = QPrintDialog.DialogCode.Rejected
        view._print_alarms()

        mock_dialog_cls.assert_called_once()
        mock_box.information.assert_not_called()
        mock_draw.assert_not_called()


def test_print_alarms_con_alarmas_dialogo_aceptado_dibuja_ticket():
    from autoclave.ui_pyside.views.impresion_menu import (
        ImpresionMenuView,
        _build_alarms_ticket_lines,
    )
    from PySide6.QtPrintSupport import QPrintDialog
    from PySide6.QtPrintSupport import QPrinter

    alarms = [{
        "id": "X", "level": "ALERTA",
        "description": "desc", "source_state": "CICLO",
    }]

    view = ImpresionMenuView(nav_callback=lambda x: None)
    view._client = MagicMock()
    view._client.get_status.return_value = {"alarms": alarms}

    with patch("autoclave.ui_pyside.views.impresion_menu.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.impresion_menu.QPrintDialog") as mock_dialog_cls, \
         patch("autoclave.ui_pyside.views.impresion_menu._draw_ticket_lines") as mock_draw:
        # Se preserva el enum real para que la comparación de la clase mockeada
        # en producción (QPrintDialog.DialogCode.Accepted) siga funcionando.
        mock_dialog_cls.DialogCode = QPrintDialog.DialogCode
        mock_dialog_cls.return_value.exec.return_value = QPrintDialog.DialogCode.Accepted
        view._print_alarms()

        mock_dialog_cls.assert_called_once()
        mock_box.information.assert_not_called()
        mock_draw.assert_called_once()

        printer_arg, lines_arg = mock_draw.call_args[0]
        assert isinstance(printer_arg, QPrinter)
        expected_text = "\n".join(_build_alarms_ticket_lines(alarms))
        actual_text = "\n".join(lines_arg)
        assert "ID: X" in actual_text
        assert "Nivel: ALERTA" in actual_text
        assert "Origen: CICLO" in actual_text
        assert "Total: 1 alarma(s)" in actual_text
        # Compara también contra la construcción real de líneas (salvo el
        # timestamp, que puede variar en microsegundos entre ambas llamadas).
        assert len(lines_arg) == len(expected_text.split("\n"))
