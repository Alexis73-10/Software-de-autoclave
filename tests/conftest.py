# tests/conftest.py
#
# Recolección de basura en el hilo principal tras las pruebas que usan Qt.
#
# Las pruebas de UI dejan objetos Qt (QObject con QTimer, vistas, puentes) en
# ciclos de referencias de Python. Si se acumulan, el recolector se dispara en
# el hilo que esté reservando memoria en ese momento: por ejemplo, el hilo de
# AnyIO del TestClient de una prueba del backend. Destruir ahí un objeto Qt de
# otro hilo aborta el proceso ("Fatal Python error: Aborted"), de forma
# intermitente y en una prueba que no tiene nada que ver. Recolectar aquí, en
# el hilo principal y fuera de cualquier despacho de eventos, lo evita.
#
# Solo tras las pruebas de módulos que importan PySide6: recolectar tras cada
# una de las ~2100 pruebas triplicaba la duración de la suite.

import gc
from functools import lru_cache
from pathlib import Path

import pytest


@lru_cache(maxsize=None)
def _usa_qt(ruta: str) -> bool:
    try:
        return "PySide6" in Path(ruta).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True


@pytest.fixture(autouse=True)
def _recolectar_en_hilo_principal(request):
    yield
    if _usa_qt(str(request.node.fspath)):
        gc.collect()
