# tests/test_ciclo_sin_purga.py
#
# PURGA se eliminó del backend (decisión de Cristian, 2026-10-01): todos los
# perfiles la tenían en tiempo_purga=0, así que nunca corría.

import json
from pathlib import Path
from unittest.mock import MagicMock

from autoclave.state_machine.states.ciclo import CicloState

_PERFILES = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"


def test_pipeline_sin_purga():
    ciclo = CicloState(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert [f.name for f in ciclo._fases] == [
        "PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO",
        "ESTERILIZACION", "DESCOMPRESION", "SECADO",
    ]


def test_perfiles_sin_seccion_purga():
    perfiles = sorted(_PERFILES.glob("*/*.json"))
    assert perfiles
    for ruta in perfiles:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert "purga" not in datos["parameters"], ruta.name
