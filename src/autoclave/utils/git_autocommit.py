import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_NADA_QUE_COMITEAR = ("nothing to commit", "nada que confirmar", "nada agregado al commit")


def git_autocommit(path: str | Path, message: str) -> bool:
    """Comitea un único archivo justo después de escribirlo a disco (calibración,
    parámetros de ciclo) para que un `git reset`/`checkout` posterior no se lleve
    un cambio que solo vivía en el working tree sin commitear.

    Best-effort: el archivo ya quedó escrito correctamente en disco antes de
    llegar aquí, así que un fallo acá (sin repo git, git no instalado, nada que
    comitear) se registra como advertencia y no se propaga."""
    path = Path(path)
    try:
        subprocess.run(
            ["git", "add", str(path)],
            cwd=path.parent, check=True, capture_output=True, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        logger.warning("No se pudo autocomitear %s (git add falló): %s", path, exc)
        return False

    result = subprocess.run(
        ["git", "commit", "-m", message, "--", str(path)],
        cwd=path.parent, capture_output=True, text=True,
    )
    if result.returncode != 0:
        salida = (result.stdout + result.stderr).lower()
        if any(marca in salida for marca in _NADA_QUE_COMITEAR):
            return True
        logger.warning(
            "No se pudo autocomitear %s: %s", path, (result.stdout + result.stderr).strip()
        )
        return False

    return True
