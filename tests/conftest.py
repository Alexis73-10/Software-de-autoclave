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


@pytest.fixture(autouse=True)
def _sin_dialogo_de_login_modal(monkeypatch):
    """P3 (tanda 5): un 401 en una vista PySide abre un diálogo modal de login;
    en las pruebas se cancela (None) para no bloquear la suite. Las pruebas
    que necesitan otro comportamiento lo vuelven a parchear."""
    try:
        from autoclave.ui_pyside.services import renovacion_sesion
    except Exception:
        return
    monkeypatch.setattr(renovacion_sesion, "pedir_credenciales_dialogo", lambda padre: None)


@pytest.fixture(autouse=True)
def _ticket_sin_proveedor_global():
    """I3 (tanda 5): el arranque real del backend registra un proveedor global
    de idioma/unidades para el ticket; no debe filtrarse a otras pruebas."""
    yield
    try:
        from autoclave.services.domain.logging import ticket_formatter
    except Exception:
        return
    ticket_formatter.fijar_proveedor(None)


# LIC-01 (licencia L0): secretos de activación de PRUEBA, fijos. Las pruebas
# nunca leen el archivo de secretos real: ESPECIFIKA_SECRETOS apunta a una ruta
# inexistente. Las que necesitan otro caso (sin secretos, archivo propio)
# llaman a activation.configurar_secretos() o cambian la variable.
SECRETO_PRUEBA_INSTALACION = bytes(range(32))
SECRETO_PRUEBA_FABRICA = bytes(range(32, 64))
_RUTA_SECRETOS_INEXISTENTE = str(Path(__file__).parent / "_sin_archivo_de_secretos" / "activacion.json")


@pytest.fixture(autouse=True)
def _secretos_de_prueba(monkeypatch):
    from autoclave.installation import activation
    monkeypatch.setenv("ESPECIFIKA_SECRETOS", _RUTA_SECRETOS_INEXISTENTE)
    activation.configurar_secretos(SECRETO_PRUEBA_INSTALACION, SECRETO_PRUEBA_FABRICA)
    yield
    activation.configurar_secretos()
