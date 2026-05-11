# installation/bootstrap.py

from .storage import exists, load


def get_installation_profile():
    if not exists():
        return None  # dispara wizard
    return load()
