from pathlib import Path
import subprocess
from autoclave.utils.logging import logger

_PID_FILE = Path(__file__).resolve().parents[3] / "data" / "backend.pid"


def write_backend_pid(pid: int, path: Path = _PID_FILE) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(pid), encoding="utf-8")
    except Exception as exc:
        logger.warning("write_backend_pid: no se pudo escribir %s: %s", path, exc)


def read_backend_pid(path: Path = _PID_FILE) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_stale_backend_running(pid: int) -> bool:
    """True si el PID sigue vivo y su línea de comandos corresponde al backend
    (evita matar un PID reciclado por otro proceso no relacionado)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
            capture_output=True, text=True, timeout=5,
        )
        cmdline = (result.stdout or "").strip()
        return "autoclave.backend.main" in cmdline
    except Exception:
        return False


def kill_stale_backend(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5)
    except Exception as exc:
        logger.warning("kill_stale_backend: no se pudo terminar PID %d: %s", pid, exc)


def cleanup_stale_backend(path: Path = _PID_FILE) -> None:
    """Mata cualquier backend huérfano de una sesión anterior. Llamar antes de
    lanzar un backend nuevo, solo cuando is_backend_alive() ya dio False."""
    pid = read_backend_pid(path)
    if pid is not None and is_stale_backend_running(pid):
        logger.warning(
            "Backend huérfano detectado (PID %d) — terminando antes de arrancar uno nuevo", pid
        )
        kill_stale_backend(pid)
