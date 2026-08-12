import json
import os
import tempfile
from pathlib import Path

DEFAULT_PREFERENCES_PATH = Path(__file__).resolve().parents[3] / "data" / "preferences.json"

_DEFAULTS = {"enabled": True, "volume": 80}


def load_preferences(path: Path | None = None) -> dict:
    path = path or DEFAULT_PREFERENCES_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}

    audio = data.get("audio") if isinstance(data, dict) else None
    if not isinstance(audio, dict):
        audio = {}
    enabled = audio.get("enabled", _DEFAULTS["enabled"])
    volume = audio.get("volume", _DEFAULTS["volume"])

    if not isinstance(enabled, bool):
        enabled = _DEFAULTS["enabled"]
    if not isinstance(volume, int) or isinstance(volume, bool) or not (0 <= volume <= 100):
        volume = _DEFAULTS["volume"]

    return {"audio": {"enabled": enabled, "volume": volume}}


def save_preferences(preferences: dict, path: Path | None = None) -> None:
    path = path or DEFAULT_PREFERENCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".preferences_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
