import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_FILE = Path(__file__).resolve().parents[4] / "data" / "last_shutdown.json"


def write_timestamp(path: Path = _DEFAULT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"timestamp": datetime.now().isoformat()}),
        encoding="utf-8",
    )


def read_last_shutdown(path: Path = _DEFAULT_FILE) -> datetime | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(data["timestamp"])
    except Exception:
        return None


def _tick(interval: int, path: Path) -> None:
    try:
        write_timestamp(path)
    except Exception as exc:
        logger.warning("heartbeat: error al escribir timestamp: %s", exc)
    finally:
        t = threading.Timer(interval, _tick, args=(interval, path))
        t.daemon = True
        t.start()


def start(interval: int = 30, path: Path = _DEFAULT_FILE) -> None:
    _tick(interval, path)
