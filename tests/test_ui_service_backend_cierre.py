# Cierre de la UI Tk con ciclo en curso (revisión de seguridad de la etapa 1 de
# autenticación, hallazgo B): /outputs/reset responde 409 en CICLO y la UI no
# debe terminar el backend, porque mataría el ciclo sin apagar las salidas.

import threading
from unittest.mock import MagicMock

import requests

from autoclave.cliente.ui_service_backend import UIServiceBackend


def _make_service(backend):
    service = object.__new__(UIServiceBackend)
    service.backend = backend
    service._force_static = threading.Event()
    return service


def _http_error(codigo):
    respuesta = MagicMock()
    respuesta.status_code = codigo
    return requests.HTTPError(response=respuesta)


def test_salidas_apagadas():
    backend = MagicMock()
    s = _make_service(backend)
    assert s.reset_outputs_al_cerrar() == "apagado"
    backend.post.assert_called_once_with(path="/outputs/reset")
    assert s.reset_outputs() is True


def test_ciclo_en_curso_409():
    backend = MagicMock()
    backend.post.side_effect = _http_error(409)
    s = _make_service(backend)
    assert s.reset_outputs_al_cerrar() == "ciclo"
    assert s.reset_outputs() is False


def test_otro_error_http():
    backend = MagicMock()
    backend.post.side_effect = _http_error(500)
    assert _make_service(backend).reset_outputs_al_cerrar() == "error"


def test_backend_inaccesible():
    backend = MagicMock()
    backend.post.side_effect = requests.ConnectionError("sin backend")
    assert _make_service(backend).reset_outputs_al_cerrar() == "error"
