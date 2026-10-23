"""P1 (tanda 7): primer arranque del ejecutable sin perfil (paso 1 y 3 del
recorrido de instalación). El lanzador abre solo el asistente, sin backend; al
terminarlo (código 3) sigue con el arranque normal, sin reiniciar a mano. Si
el asistente se cierra sin instalar, no se arranca nada."""

from types import SimpleNamespace

import pytest

from autoclave import exe_unico
from autoclave.installation import backend_guard
from autoclave.ui_qml import doble_pantalla
from autoclave.ui_qml.bridge import puente_instalacion


class _Proc:
    def __init__(self, codigo=0, pid=4321):
        self._codigo = codigo
        self.pid = pid

    def wait(self, timeout=None):
        return self._codigo

    def poll(self):
        return None

    def terminate(self):   # W10: la pantalla 2 de Reposo se cierra al terminar el asistente
        pass


@pytest.fixture
def lanzador(monkeypatch, tmp_path):
    lanzados, pantallas, perfil = [], [], {"falta": True}
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: None)
    monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    monkeypatch.setattr(backend_guard, "cleanup_stale_backend", lambda: None)
    monkeypatch.setattr(backend_guard, "write_backend_pid", lambda pid: None)
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: perfil["falta"])
    monkeypatch.setattr(doble_pantalla, "vigilar_pantallas",
                        lambda cmds, lanzar, barra=None: pantallas.extend(cmds))
    return SimpleNamespace(lanzados=lanzados, pantallas=pantallas, perfil=perfil,
                           monkeypatch=monkeypatch)


def _popen_con(lz, codigo_asistente, instala):
    def popen(cmd, cwd=None, env=None):
        lz.lanzados.append(cmd)
        if "--rol" in cmd and cmd[cmd.index("--rol") + 1] == "ui" and lz.perfil["falta"]:
            if instala:
                lz.perfil["falta"] = False
            return _Proc(codigo_asistente)
        return _Proc()
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)


def _roles(lz):
    return [c[c.index("--rol") + 1] for c in lz.lanzados]


def test_sin_perfil_abre_el_asistente_y_al_terminar_sigue_con_backend_y_pantallas(lanzador):
    _popen_con(lanzador, doble_pantalla.CODIGO_INSTALACION_TERMINADA, instala=True)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    # asistente (puerta 1) y Reposo de instalación (puerta 2, W10) primero, sin backend
    assert _roles(lanzador) == ["ui", "ui", "backend"]
    assert len(lanzador.pantallas) == 2                 # puerta 1 y puerta 2


def test_asistente_cerrado_sin_instalar_no_arranca_nada(lanzador):
    _popen_con(lanzador, 0, instala=False)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 1
    assert _roles(lanzador) == ["ui", "ui"]             # asistente y Reposo (W10), sin backend
    assert lanzador.pantallas == []


def test_con_perfil_arranca_directo(lanzador):
    lanzador.perfil["falta"] = False
    _popen_con(lanzador, 0, instala=False)
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla"])) == 0
    assert _roles(lanzador) == ["backend"]
    assert len(lanzador.pantallas) == 1
