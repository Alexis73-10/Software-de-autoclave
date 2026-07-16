import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_view():
    from autoclave.ui_pyside.views.ciclos import CiclosView

    with patch("autoclave.services.domain.logging.db_manager.DbManager"):
        view = CiclosView(nav_callback=lambda x: None)
    return view


def test_print_selected_sin_seleccion_no_imprime():
    view = _make_view()
    view._get_selected_ids = MagicMock(return_value=[])

    with patch("autoclave.ui_pyside.views.ciclos.print_raw") as mock_print:
        view._print_selected()

        mock_print.assert_not_called()


def test_print_selected_imprime_directo_sin_dialogo():
    from autoclave.ui_pyside.views.ciclos import PRINTER_NAME, _build_cycle_lines

    view = _make_view()
    ciclo = {
        "numero_ciclo": 12, "serie": "SN1", "modelo": "MX-500",
        "version_sw": "1.0", "nombre_ciclo": "Instrumental 134",
        "tipo_ciclo": "instrumental_134", "temp_esterilizacion": 134,
        "tiempo_esterilizacion": 4, "resultado": "OK",
        "fecha_inicio": "2026-07-16T10:00:00", "fecha_fin": "2026-07-16T10:30:00",
    }
    lecturas = [{"fase_codigo": "S", "timestamp_rel": "00:01", "temp_camara": 134.0, "pres_camara": 220.0}]

    view._get_selected_ids = MagicMock(return_value=[1])
    view._load_cycles_data = MagicMock(return_value=[(ciclo, lecturas)])

    with patch("autoclave.ui_pyside.views.ciclos.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.ciclos.print_raw") as mock_print:
        mock_print.return_value = True
        view._print_selected()

        mock_box.warning.assert_not_called()
        mock_print.assert_called_once()

        text_arg, printer_arg = mock_print.call_args[0]
        assert printer_arg == PRINTER_NAME
        expected_text = "\n".join(_build_cycle_lines(ciclo, lecturas))
        assert text_arg == expected_text


def test_print_selected_multiples_ciclos_concatena_texto():
    view = _make_view()
    ciclo1 = {
        "numero_ciclo": 1, "serie": "SN1", "modelo": "MX-500", "version_sw": "1.0",
        "nombre_ciclo": "A", "tipo_ciclo": "a", "temp_esterilizacion": 134,
        "tiempo_esterilizacion": 4, "resultado": "OK",
        "fecha_inicio": "2026-07-16T10:00:00", "fecha_fin": "2026-07-16T10:30:00",
    }
    ciclo2 = dict(ciclo1, numero_ciclo=2, nombre_ciclo="B")

    view._get_selected_ids = MagicMock(return_value=[1, 2])
    view._load_cycles_data = MagicMock(return_value=[(ciclo1, []), (ciclo2, [])])

    with patch("autoclave.ui_pyside.views.ciclos.print_raw") as mock_print:
        mock_print.return_value = True
        view._print_selected()

        mock_print.assert_called_once()
        text_arg = mock_print.call_args[0][0]
        assert "Ciclo No.: 000001" in text_arg
        assert "Ciclo No.: 000002" in text_arg


def test_print_selected_falla_impresion_muestra_aviso():
    view = _make_view()
    ciclo = {
        "numero_ciclo": 1, "serie": "SN1", "modelo": "MX-500", "version_sw": "1.0",
        "nombre_ciclo": "A", "tipo_ciclo": "a", "temp_esterilizacion": 134,
        "tiempo_esterilizacion": 4, "resultado": "OK",
        "fecha_inicio": "2026-07-16T10:00:00", "fecha_fin": "2026-07-16T10:30:00",
    }
    view._get_selected_ids = MagicMock(return_value=[1])
    view._load_cycles_data = MagicMock(return_value=[(ciclo, [])])

    with patch("autoclave.ui_pyside.views.ciclos.QMessageBox") as mock_box, \
         patch("autoclave.ui_pyside.views.ciclos.print_raw") as mock_print:
        mock_print.return_value = False
        view._print_selected()

        mock_print.assert_called_once()
        mock_box.warning.assert_called_once()
