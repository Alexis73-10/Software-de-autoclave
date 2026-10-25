"""T2 / P-8 (tanda 6): HIBERNACION y EMERGENCIA se retiran de la máquina de
estados (inalcanzables, PF-07). Antes se verificó que la suspensión
(ui_qml/bridge/standby.py y el backend) no usa HIBERNACION."""

import importlib.util
from pathlib import Path

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import archivos_backend

_RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


def test_quedan_solo_los_cuatro_estados_alcanzables():
    assert [e.name for e in GlobalState] == ["PREPARACION", "PREPARADO", "CICLO", "FALLA"]


def test_modulos_de_los_estados_retirados_no_existen():
    for nombre in ("hibernacion", "emergencia"):
        assert importlib.util.find_spec(f"autoclave.state_machine.states.{nombre}") is None


def test_la_suspension_no_usa_hibernacion():
    for ruta in (_RAIZ / "ui_qml" / "bridge" / "standby.py", *archivos_backend(),
                 _RAIZ / "services" / "domain" / "loop" / "control_loop.py"):
        assert "GlobalState.HIBERNACION" not in ruta.read_text(encoding="utf-8"), ruta


def test_ningun_codigo_referencia_los_estados_retirados():
    for ruta in _RAIZ.rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        assert "GlobalState.HIBERNACION" not in texto and "GlobalState.EMERGENCIA" not in texto, ruta
