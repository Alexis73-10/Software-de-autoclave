from unittest.mock import MagicMock
import requests

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend


def _make_service(backend):
    service = object.__new__(UIServiceBackend)
    service.backend = backend
    return service


def test_list_user_cycles_filtra_solo_source_user():
    backend = MagicMock()
    backend.get.return_value = [
        {"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"},
        {"id": "fabrica_x", "name": "Fábrica X", "source": "factory"},
    ]
    service = _make_service(backend)

    result = service.list_user_cycles()

    assert result == [{"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"}]
    backend.get.assert_called_once_with(path="/cycles")


def test_list_user_cycles_retorna_vacio_si_falla_backend():
    backend = MagicMock()
    backend.get.side_effect = requests.RequestException("sin conexión")
    service = _make_service(backend)

    assert service.list_user_cycles() == []


def test_select_cycle_ok():
    backend = MagicMock()
    backend.post.return_value = {"ok": True, "id": "bowe_dick", "name": "Bowe & Dick"}
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert (ok, motivo) == (True, "")
    backend.post.assert_called_once_with(path="/cycle/select", body={"cycle_id": "bowe_dick"})


def test_select_cycle_error_http_extrae_detail():
    backend = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "detail": "No se puede cambiar de ciclo mientras hay uno en curso."
    }
    backend.post.side_effect = requests.HTTPError(response=response)
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert motivo == "No se puede cambiar de ciclo mientras hay uno en curso."


def test_select_cycle_error_conexion():
    backend = MagicMock()
    backend.post.side_effect = requests.RequestException("timeout")
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert "backend" in motivo.lower()


def test_select_cycle_error_inesperado_jsondecode():
    """Verifica que JSONDecodeError (respuesta 200 con body no JSON) sea capturado."""
    backend = MagicMock()
    backend.post.side_effect = ValueError("respuesta invalida")
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert "Error inesperado" in motivo
    assert "respuesta invalida" in motivo
