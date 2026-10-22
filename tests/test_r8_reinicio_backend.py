# tests/test_r8_reinicio_backend.py
#
# R8 (tanda 8, D8-5.12): aplicar una reasignación reinicia el backend. El
# backend se detiene de forma ordenada (lifespan: salidas apagadas) y termina
# con CODIGO_REINICIO; el lanzador del ejecutable único lo relanza.

import threading
from unittest.mock import MagicMock

from autoclave.backend import reinicio


def test_sin_mecanismo_registrado_no_reinicia():
    reinicio.registrar(None)
    assert reinicio.solicitar("prueba") is False
    assert reinicio.solicitado() is False


def test_solicitar_detiene_el_servidor_tras_el_retraso():
    servidor = MagicMock(should_exit=False)
    hecho = threading.Event()

    def detener():
        servidor.should_exit = True
        hecho.set()
    reinicio.registrar(detener)
    try:
        assert reinicio.solicitar("reasignación", retraso_s=0.0) is True
        assert reinicio.solicitado() is True
        assert hecho.wait(2)
        assert servidor.should_exit is True
    finally:
        reinicio.registrar(None)


class _Proc:
    def __init__(self, codigos):
        self._codigos = list(codigos)

    def poll(self):
        return self._codigos.pop(0) if self._codigos else None


def test_lanzador_relanza_solo_con_el_codigo_de_reinicio():
    actual = {"proc": _Proc([None, reinicio.CODIGO_REINICIO])}
    detener = threading.Event()
    relanzados = []

    def relanzar():
        relanzados.append(1)
        # el nuevo backend termina luego con otro código: no se relanza más
        actual["proc"] = _Proc([None, 1])
    reinicio.vigilar_reinicios(lambda: actual["proc"], relanzar, detener, pausa_s=0.0)
    assert relanzados == [1]


def test_lanzador_no_relanza_un_backend_que_termina_por_otra_causa():
    relanzar = MagicMock()
    reinicio.vigilar_reinicios(lambda: _Proc([0]), relanzar, threading.Event(), pausa_s=0.0)
    relanzar.assert_not_called()


def test_vigilancia_termina_al_cerrar_las_pantallas():
    detener = threading.Event()
    detener.set()
    relanzar = MagicMock()
    reinicio.vigilar_reinicios(lambda: _Proc([reinicio.CODIGO_REINICIO]), relanzar, detener)
    relanzar.assert_not_called()


def test_main_del_backend_termina_con_el_codigo_de_reinicio(monkeypatch):
    """backend/main.py: si se pidió el reinicio, al volver de run() sale con
    CODIGO_REINICIO (lo que el lanzador vigila)."""
    import pytest
    from autoclave.backend import main as backend_main
    servidor = MagicMock()

    def correr():
        reinicio.solicitar("prueba", retraso_s=0.0, dormir=lambda s: None)
        hilo_detenido.wait(2)
    hilo_detenido = threading.Event()
    servidor.run.side_effect = correr
    monkeypatch.setattr(backend_main.uvicorn, "Server", MagicMock(return_value=servidor))
    monkeypatch.setattr(backend_main.uvicorn, "Config", MagicMock())
    monkeypatch.setattr(backend_main.threading, "Thread", MagicMock())
    fake_server = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "autoclave.backend.server", fake_server)
    import autoclave.backend as paquete
    monkeypatch.setattr(paquete, "server", fake_server, raising=False)
    try:
        with pytest.raises(SystemExit) as e:
            backend_main.main()
        assert e.value.code == reinicio.CODIGO_REINICIO
    finally:
        reinicio.registrar(None)
