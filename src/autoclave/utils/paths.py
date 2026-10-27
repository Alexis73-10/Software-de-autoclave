import shutil
import sys
from pathlib import Path

from autoclave.utils.resources import raiz_datos_exe, resource_path


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
        # INS-02 (tanda 17): instalado por el Setup, RutaDatos del registro
        # (X:\Especifika\Autoclave\datos); en Archivos de programa (disposición
        # anterior), %ProgramData%\Especifika\Autoclave; si no, junto al .exe.
        # Ver utils/resources.raiz_datos_exe.
        return Path(raiz_datos_exe())
    return Path(__file__).resolve().parents[3]


CALIBRACION_SERIAL = "calibration.yaml"
CALIBRACION_MODBUS = "calibration_modbus.yaml"


def nombre_calibracion(enlace: str | None = None) -> str:
    """Archivo de calibración del enlace de E/S (tanda 19, MOD-04): la escala
    de fábrica depende del enlace (cuentas del ADC de 12 bits en serial,
    décimas de °C y µA en Modbus). `enlace` None = el enlace activo."""
    from autoclave.config import enlace_io
    if enlace is None:
        enlace = enlace_io.enlace_activo()
    return CALIBRACION_MODBUS if enlace == enlace_io.ENLACE_MODBUS else CALIBRACION_SERIAL


def calibration_path() -> Path:
    """Ruta activa del archivo de calibración del enlace activo
    (`calibration.yaml` en serial, `calibration_modbus.yaml` en Modbus; tanda
    19, MOD-04) — se lee y se sobreescribe en cada recalibración (ver
    `rutas/io.py` / `calibration_writer.py`, que escribe en la ruta que se le
    pasa).

    En desarrollo es el archivo del repo, como siempre. En un build congelado,
    `resource_path()` apunta dentro del árbol de extracción de PyInstaller
    (temporal en modo onefile) — escribir ahí se perdería al cerrar el
    programa. Ahí se usa en cambio una copia en `data/`, junto al .exe,
    sembrada la primera vez desde la calibración de fábrica empaquetada. Cada
    enlace tiene su propia copia: cambiar de enlace no pisa la calibración del
    otro."""
    nombre = nombre_calibracion()
    bundled = Path(resource_path(f"autoclave/config/{nombre}"))
    if not getattr(sys, "frozen", False):
        return bundled

    active = app_root() / "data" / nombre
    if not active.exists():
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled, active)
    return active
