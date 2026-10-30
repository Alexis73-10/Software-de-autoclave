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

# Tanda 20 (T20-03): el enlace serial y la selección de enlace se retiraron;
# el único enlace es Modbus y no hay fixture de enlace autouse.


@pytest.fixture
def enlace_doble():
    """Tanda 20 (F1): doble en memoria de EnlaceES (tests/helpers/enlace_doble.py),
    el doble común de las pruebas que no prueban el protocolo Modbus."""
    from tests.helpers.enlace_doble import EnlaceDoble
    return EnlaceDoble()


@lru_cache(maxsize=None)
def _usa_qt(ruta: str) -> bool:
    try:
        return "PySide6" in Path(ruta).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True


@pytest.fixture(scope="session", autouse=True)
def _qapplication_de_la_sesion():
    """Cierre 1.0: una sola QApplication por proceso, creada antes de cualquier prueba.

    Varias pruebas de QML/controladores hacen `QCoreApplication.instance() or
    QCoreApplication(sys.argv)`. Si una de ellas corre primero en un worker, la
    instancia única del proceso queda siendo una QCoreApplication y la siguiente
    prueba de widgets (`QApplication.instance() or QApplication(...)` devuelve esa
    QCoreApplication) aborta el proceso al crear un QWidget: el worker de xdist
    cae ("node down: Not properly terminated") y la prueba en curso falla, solo
    con ciertos órdenes de reparto. QApplication es subclase de QCoreApplication,
    así que las pruebas que solo piden `.instance()` siguen funcionando."""
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        yield None
        return
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


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
