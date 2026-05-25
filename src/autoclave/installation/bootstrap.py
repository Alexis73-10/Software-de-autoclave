# src/autoclave/installation/bootstrap.py
import json
import logging
from .storage import exists, load
from .profile import ProfileValidationError
from .clock_guard import check_system_clock, ClockTamperedError

logger = logging.getLogger(__name__)


def get_installation_profile():
    """
    Return the InstallationProfile if valid, or None if the file doesn't exist
    or is corrupt. Raises ClockTamperedError if the system clock is before the
    installation date — callers must handle this explicitly.
    """
    if not exists():
        return None

    try:
        profile = load()
        check_system_clock(profile.created_at)
        return profile
    except ClockTamperedError:
        raise
    except (ProfileValidationError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Perfil de instalación corrupto o inválido: %s", e)
        return None
