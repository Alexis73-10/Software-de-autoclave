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


def test_main_lanza_ambas_desde_la_raiz_del_proyecto():
    lanzados = []

    def popen(cmd, cwd):
        p = MagicMock()
        p.wait.return_value = 0
        lanzados.append((cmd, cwd))
        return p

    assert mod.main([], popen=popen) == 0
    assert [_args(c)["--door"] for c, _ in lanzados] == ["1", "2"]
    assert all(cwd == str(mod.RAIZ_PROYECTO) for _, cwd in lanzados)
    assert (mod.RAIZ_PROYECTO / "src" / "autoclave" / "ui_qml" / "qml" / "Main.qml").exists()


def test_ctrl_c_termina_las_pantallas_abiertas():
    procesos = []

    def popen(cmd, cwd):
        p = MagicMock()
        p.poll.return_value = None
        p.wait.side_effect = KeyboardInterrupt
        procesos.append(p)
        return p

    mod.main([], popen=popen)
    assert all(p.terminate.called for p in procesos)
