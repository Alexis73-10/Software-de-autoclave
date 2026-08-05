import threading
import time
from unittest.mock import MagicMock
import requests

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend


def _make_service(backend):
    service = object.__new__(UIServiceBackend)
    service.backend = backend
    service._force_static = threading.Event()
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
    assert service._force_static.is_set() is True


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
    assert service._force_static.is_set() is False


def test_select_cycle_error_conexion():
    backend = MagicMock()
    backend.post.side_effect = requests.RequestException("timeout")
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert "backend" in motivo.lower()
    assert service._force_static.is_set() is False


def test_select_cycle_error_inesperado_jsondecode():
    """Verifica que JSONDecodeError (respuesta 200 con body no JSON) sea capturado."""
    backend = MagicMock()
    backend.post.side_effect = ValueError("respuesta invalida")
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert "Error inesperado" in motivo
    assert "respuesta invalida" in motivo
    assert service._force_static.is_set() is False


def test_loop_refresca_static_de_inmediato_cuando_force_static_esta_activo():
    """Cobertura ligera de _loop(): instancia un UIServiceBackend real (hilo
    de fondo real) y verifica que, tras un select_cycle() exitoso, el
    _cycle cacheado converge al nuevo valor en menos de un _STATUS_INTERVAL
    -- en vez de tener que esperar hasta _STATIC_EVERY iteraciones (~5s)."""
    backend = MagicMock()
    backend.get_status.return_value = {}
    backend.get_config.return_value = {}
    # Primer valor de /cycle (el que vería el cache antes de seleccionar).
    backend.get_cycle.return_value = {"id": "old_cycle", "name": "Ciclo viejo"}
    backend.post.return_value = {"ok": True}

    service = UIServiceBackend(backend)
    try:
        # Espera a que el primer _fetch_static() (counter == 0) corra.
        for _ in range(50):
            if service.get_cycle_param("id") == "old_cycle":
                break
            time.sleep(0.05)
        assert service.get_cycle_param("id") == "old_cycle"

        # Simula que el backend ya cambió de ciclo activo.
        backend.get_cycle.return_value = {"id": "new_cycle", "name": "Ciclo nuevo"}

        ok, motivo = service.select_cycle("new_cycle")
        assert (ok, motivo) == (True, "")

        # Debe converger dentro de ~1 _STATUS_INTERVAL (0.2s), muy por
        # debajo de los ~5s que tomaría esperar al próximo múltiplo de
        # _STATIC_EVERY.
        converged = False
        for _ in range(20):
            if service.get_cycle_param("id") == "new_cycle":
                converged = True
                break
            time.sleep(0.05)

        assert converged, "select_cycle() no forzó un refresh inmediato de /cycle"
    finally:
        service.stop()
