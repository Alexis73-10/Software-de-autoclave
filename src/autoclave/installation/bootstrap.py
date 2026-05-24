# src/autoclave/installation/bootstrap.py
import json
import logging
from .storage import exists, load
from .profile import ProfileValidationError

logger = logging.getLogger(__name__)


def get_installation_profile():
    """
    Return the InstallationProfile if valid, or None if:
    - the file doesn't exist (new installation needed)
    - the file is corrupt or missing fields (re-installation needed)
    Logs a warning in the corrupt case.
    """
    if not exists():
        return None

    try:
        return load()
    except (ProfileValidationError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Perfil de instalación corrupto o inválido: %s", e)
        return None
