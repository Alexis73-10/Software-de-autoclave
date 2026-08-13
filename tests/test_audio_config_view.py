import sys
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_carga_config_inicial_desde_el_backend():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": False, "volume": 42, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)
        view.show()  # dispara showEvent(), que ahora es lo que arranca el refresh

    assert view._chk_enabled.isChecked() is False
    assert view._slider_volume.value() == 42
    assert "disponible" in view._lbl_available.text().lower()


def test_cambiar_slider_hace_patch_de_volumen():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": True, "volume": 80, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)

    with patch("autoclave.ui_pyside.views.audio_config.BackendClient.patch") as mock_patch:
        view._slider_volume.setValue(30)
        view._on_volume_released()
        mock_patch.assert_called_once_with("/audio/config", {"volume": 30})


def test_boton_probar_llama_al_endpoint_de_prueba():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        return_value={"enabled": True, "volume": 80, "available": True},
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)

    with patch("autoclave.ui_pyside.views.audio_config.BackendClient.post") as mock_post:
        view._on_test_clicked()
        mock_post.assert_called_once_with("/audio/test")


def test_backend_no_disponible_no_lanza_excepcion():
    from autoclave.ui_pyside.views.audio_config import AudioConfigView
    import requests

    with patch(
        "autoclave.ui_pyside.views.audio_config.BackendClient.get",
        side_effect=requests.RequestException("sin conexion"),
    ):
        view = AudioConfigView(nav_callback=lambda *_: None)  # no debe lanzar
        view.show()  # dispara showEvent(), que ahora es lo que arranca el refresh

    assert "sin conexión" in view._lbl_available.text().lower()
