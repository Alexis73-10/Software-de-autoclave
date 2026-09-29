import shutil
import sys
from pathlib import Path

from autoclave.utils.resources import resource_path


def app_root() -> Path:
    """Directorio base para datos persistentes (perfil de instalación, DB,
    tickets, PID del backend, último apagado).

    En un build congelado (PyInstaller) es la carpeta donde vive el .exe —
    ahí se crea `data/` como carpeta portátil junto al ejecutable, igual que
    en desarrollo. En desarrollo es la raíz del repo, donde ya vive `data/`.

    No usar `Path(__file__)` directamente para esto en otros módulos: dentro
    de un build congelado, `__file__` apunta al árbol de extracción de
    PyInstaller (temporal en modo onefile), no a una ubicación estable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def calibration_path() -> Path:
    """Ruta activa de `calibration.yaml` — se lee y se sobreescribe en cada
    recalibración (ver `server.py` / `calibration_writer.py`).

    En desarrollo es el archivo del repo, como siempre. En un build congelado,
    `resource_path()` apunta dentro del árbol de extracción de PyInstaller
    (temporal en modo onefile) — escribir ahí se perdería al cerrar el
    programa. Ahí se usa en cambio una copia en `data/`, junto al .exe,
    sembrada la primera vez desde la calibración de fábrica empaquetada."""
    bundled = Path(resource_path("autoclave/config/calibration.yaml"))
    if not getattr(sys, "frozen", False):
        return bundled

    active = app_root() / "data" / "calibration.yaml"
    if not active.exists():
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled, active)
    return active
