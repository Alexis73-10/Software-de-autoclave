# tests/test_lanzar_ui_qml.py
#
# Lanzador de la UI QML (ui_qml/lanzar.py):
#   python -m autoclave.ui_qml.lanzar simulador  -> simulador + UI apuntada a él
#   python -m autoclave.ui_qml.lanzar real       -> UI contra el backend real
# Procesos y espera del backend simulados.

import sys

import pytest

from autoclave.ui_qml import lanzar


@pytest.fixture(autouse=True)
def _sin_relanzar(monkeypatch):
    """Estas pruebas miran qué se lanza; el relanzado (D-04) se prueba en
    test_doble_pantalla. Aquí cada pantalla se lanza una vez y se espera."""
    def vigilar(cmds, lanzar_cmd, **_k):
        for p in [lanzar_cmd(c) for c in cmds]:
            p.wait()
    monkeypatch.setattr(lanzar, "vigilar_pantallas", vigilar)


class _Proceso:
    def __init__(self, cmd, env):
        self.cmd, self.env = cmd, env
        self.terminado = False

    def wait(self):
        return 0

    def poll(self):
        return 0 if self.terminado else None

    def terminate(self):
        self.terminado = True


class _Popen:
    def __init__(self):
        self.procesos = []

    def __call__(self, cmd, cwd=None, env=None):
        p = _Proceso(cmd, env)
        self.procesos.append(p)
        return p


def _modulos(popen):
    return [p.cmd[p.cmd.index("-m") + 1] for p in popen.procesos]


def test_simulador_levanta_el_simulador_y_las_dos_pantallas(monkeypatch):
    monkeypatch.delenv("AUTOCLAVE_BACKEND_URL", raising=False)
    popen = _Popen()
    assert lanzar.main(["simulador", "--velocidad", "20"], popen=popen,
                       esperar=lambda url, s: True) == 0
    assert _modulos(popen) == ["autoclave.simulador", "autoclave.ui_qml.app", "autoclave.ui_qml.app"]
    sim, ui1, ui2 = popen.procesos
    assert sim.cmd[sim.cmd.index("--velocidad") + 1] == "20"
    assert sim.cmd[sim.cmd.index("--puerto") + 1] == "8001"
    for ui in (ui1, ui2):
        assert ui.env["AUTOCLAVE_BACKEND_URL"] == "http://127.0.0.1:8001"
    assert [ui.cmd[ui.cmd.index("--door") + 1] for ui in (ui1, ui2)] == ["1", "2"]
    assert sim.terminado is True        # al cerrar las pantallas se detiene el simulador


def test_simulador_una_pantalla():
    popen = _Popen()
    lanzar.main(["simulador", "--una-pantalla"], popen=popen, esperar=lambda url, s: True)
    assert _modulos(popen) == ["autoclave.simulador", "autoclave.ui_qml.app"]


def test_simulador_que_no_arranca_no_abre_la_ui():
    popen = _Popen()
    assert lanzar.main(["simulador"], popen=popen, esperar=lambda url, s: False) == 1
    assert _modulos(popen) == ["autoclave.simulador"]
    assert popen.procesos[0].terminado is True


def test_real_ignora_la_variable_del_simulador(monkeypatch):
    monkeypatch.setenv("AUTOCLAVE_BACKEND_URL", "http://127.0.0.1:8001")
    popen = _Popen()
    assert lanzar.main(["real"], popen=popen, esperar=lambda url, s: True) == 0
    assert _modulos(popen) == ["autoclave.ui_qml.app", "autoclave.ui_qml.app"]
    for ui in popen.procesos:
        assert "AUTOCLAVE_BACKEND_URL" not in ui.env


def test_real_sin_backend_avisa_pero_abre_la_ui(caplog):
    popen = _Popen()
    urls = []
    assert lanzar.main(["real", "--una-pantalla", "--door", "2"], popen=popen,
                       esperar=lambda url, s: urls.append(url) or False) == 0
    assert urls == ["http://127.0.0.1:8000"]
    assert "python -m autoclave.backend.main" in caplog.text
    ui = popen.procesos[0]
    assert ui.cmd[ui.cmd.index("--door") + 1] == "2"


def test_usa_el_mismo_interprete():
    popen = _Popen()
    lanzar.main(["real"], popen=popen, esperar=lambda url, s: True)
    assert all(p.cmd[0] == sys.executable for p in popen.procesos)


def test_subcomando_obligatorio():
    with pytest.raises(SystemExit):
        lanzar.main([], popen=_Popen(), esperar=lambda url, s: True)
