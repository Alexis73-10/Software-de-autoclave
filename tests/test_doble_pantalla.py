# tests/test_doble_pantalla.py
#
# Lanzador de las dos pantallas QML (ui_qml/doble_pantalla.py): cada proceso
# lleva su propia puerta fija; Popen simulado.

import sys
from unittest.mock import MagicMock

from autoclave.ui_qml import doble_pantalla as mod


def _args(cmd):
    return dict(zip(cmd[3::2], cmd[4::2]))


def test_una_pantalla_por_puerta_sin_repetir():
    cmds = mod.comandos(0, 1)
    assert [c[:3] for c in cmds] == [[sys.executable, "-m", "autoclave.ui_qml.app"]] * 2
    assert [_args(c) for c in cmds] == [
        {"--door": "1", "--screen": "0"},
        {"--door": "2", "--screen": "1"},
    ]


def test_monitores_configurables():
    args = mod.parse_args(["--monitor-puerta1", "1", "--monitor-puerta2", "0"])
    cmds = mod.comandos(args.monitor_puerta1, args.monitor_puerta2)
    assert [_args(c) for c in cmds] == [
        {"--door": "1", "--screen": "1"},
        {"--door": "2", "--screen": "0"},
    ]


def test_main_lanza_ambas_desde_la_raiz_del_proyecto(monkeypatch):
    monkeypatch.setattr(mod, "RELANZAMIENTOS_MAX", 0)
    lanzados = []

    def popen(cmd, cwd):
        p = MagicMock()
        p.poll.return_value = 0
        lanzados.append((cmd, cwd))
        return p

    assert mod.main([], popen=popen, barra=_Barra()) == 0
    assert [_args(c)["--door"] for c, _ in lanzados] == ["1", "2"]
    assert all(cwd == str(mod.RAIZ_PROYECTO) for _, cwd in lanzados)
    assert (mod.RAIZ_PROYECTO / "src" / "autoclave" / "ui_qml" / "qml" / "Main.qml").exists()


def test_ctrl_c_termina_las_pantallas_abiertas():
    procesos = []

    def popen(cmd, cwd):
        p = MagicMock()
        p.poll.return_value = None
        procesos.append(p)
        return p

    def interrumpir(_s):
        raise KeyboardInterrupt

    mod.vigilar_pantallas(mod.comandos(0, 1), lambda c: popen(c, None), dormir=interrumpir)
    assert len(procesos) == 2 and all(p.terminate.called for p in procesos)


class _Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_d04_relanza_una_pantalla_cerrada_tres_veces_cada_5_s():
    """D-04 (T8): la pantalla que se cierra se relanza 3 veces, 5 s después
    de cada cierre; la otra sigue abierta."""
    reloj = _Reloj()
    lanzados = []
    abierta = MagicMock()
    abierta.poll.return_value = None

    def lanzar(cmd):
        if cmd[4] == "1":
            lanzados.append(reloj.t)
            p = MagicMock()
            p.poll.return_value = 1        # se cierra enseguida
            return p
        return abierta

    def dormir(s):
        reloj.t += s
        if reloj.t > 60:
            raise KeyboardInterrupt

    mod.vigilar_pantallas(mod.comandos(0, 1), lanzar, reloj=reloj, dormir=dormir)
    assert len(lanzados) == 4                       # 1 inicial + 3 relanzamientos
    assert all(b - a >= 5.0 for a, b in zip(lanzados, lanzados[1:]))
    abierta.terminate.assert_called_once()          # Ctrl+C cierra la que sigue abierta


def test_d04_termina_cuando_no_quedan_relanzamientos():
    reloj = _Reloj()
    cerrada = MagicMock()
    cerrada.poll.return_value = 0

    def dormir(s):
        reloj.t += s

    lanzados = []
    mod.vigilar_pantallas([["py", "-m", "app"]], lambda c: lanzados.append(c) or cerrada,
                          reloj=reloj, dormir=dormir)
    assert len(lanzados) == 4


class _Barra:
    def __init__(self):
        self.eventos = []

    def ocultar(self):
        self.eventos.append("ocultar")

    def mostrar(self):
        self.eventos.append("mostrar")


def test_barra_de_tareas_oculta_mientras_hay_pantallas_y_vuelve_al_terminar():
    barra = _Barra()
    p = MagicMock()
    p.poll.side_effect = [None, None, 0]
    mod.vigilar_pantallas([["py", "-m", "app"]], lambda c: p, relanzamientos=0,
                          dormir=lambda s: None, barra=barra)
    assert barra.eventos == ["ocultar"] * 3 + ["mostrar"]


def test_barra_de_tareas_vuelve_con_ctrl_c():
    barra = _Barra()
    p = MagicMock()
    p.poll.return_value = None

    def interrumpir(_s):
        raise KeyboardInterrupt

    mod.vigilar_pantallas([["py", "-m", "app"]], lambda c: p, dormir=interrumpir, barra=barra)
    assert barra.eventos == ["ocultar", "mostrar"]
    p.terminate.assert_called_once()
