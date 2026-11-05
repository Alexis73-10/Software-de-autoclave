# Reconexión con la Tarjeta ESP32 al Arrancar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que el software se reconecte solo con la tarjeta ESP32 al arrancar tras un cierre inesperado, sin requerir desconectar/reconectar el cable USB físicamente.

**Architecture:** Tres componentes independientes que se integran en dos puntos existentes (`SerialLink._connect()` y `main.py`): un módulo de limpieza de proceso backend huérfano por PID (`backend_guard.py`), un módulo de reset de dispositivo USB por PnP (`device_reset.py`) que se dispara desde `SerialLink` solo durante la conexión inicial, y una ventana de espera mínima en `main.py` que reutiliza la alarma `NO_HAY_CONEXION` ya existente.

**Tech Stack:** Python 3.14, pytest, `unittest.mock`, PowerShell (`Get-CimInstance`, `Get-PnpDevice`/`Disable-PnpDevice`/`Enable-PnpDevice`) y `taskkill` como herramientas de Windows ya disponibles (sin dependencias nuevas — `pywin32` ya es dependencia del proyecto pero no se usa aquí).

## Global Constraints

- Solo aplica a la rama `SOURCE_DOOR == 1` en `main.py` — la PC de puerta 2 no tiene backend ni `SerialLink` local.
- El reset de dispositivo (`device_reset.reset_usb_serial_device`) **nunca** puede dispararse una vez que `SerialLink` logró conectar exitosamente al menos una vez en el proceso (`_ever_connected`), y **como máximo una vez** por proceso (`_device_reset_attempted`) — no es negociable, es una decisión de seguridad aprobada explícitamente por el usuario (no resetear hardware con un ciclo en curso).
- `GEN_FAILURE_RESET_THRESHOLD = 5` intentos consecutivos con la firma de error Win32 `ERROR_GEN_FAILURE` (código 31) antes de disparar el reset — valor exacto del spec.
- `cleanup_stale_backend()` solo se invoca cuando `is_backend_alive()` ya dio `False` — nunca debe tocar un backend que sigue respondiendo sano.
- Sin dependencias nuevas en `pyproject.toml`.
- Spec de referencia: `docs/superpowers/specs/2026-07-16-reconexion-tarjeta-arranque-design.md`.

---

### Task 1: Módulo `backend_guard.py` — limpieza de proceso backend huérfano

**Files:**
- Create: `src/autoclave/installation/backend_guard.py`
- Test: `tests/test_backend_guard.py`

**Interfaces:**
- Produces: `write_backend_pid(pid: int, path: Path = _PID_FILE) -> None`,
  `read_backend_pid(path: Path = _PID_FILE) -> int | None`,
  `is_stale_backend_running(pid: int) -> bool`,
  `kill_stale_backend(pid: int) -> None`,
  `cleanup_stale_backend(path: Path = _PID_FILE) -> None` — consumidas por Task 4.

- [ ] **Step 1: Escribir los tests**

Crear `tests/test_backend_guard.py`:

```python
from unittest.mock import patch, MagicMock
from autoclave.installation import backend_guard


def test_write_and_read_backend_pid_roundtrip(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(4242, path)
    assert backend_guard.read_backend_pid(path) == 4242


def test_read_backend_pid_missing_file_returns_none(tmp_path):
    path = tmp_path / "does_not_exist.pid"
    assert backend_guard.read_backend_pid(path) is None


def test_read_backend_pid_corrupt_content_returns_none(tmp_path):
    path = tmp_path / "backend.pid"
    path.write_text("not-a-pid", encoding="utf-8")
    assert backend_guard.read_backend_pid(path) is None


def test_is_stale_backend_running_true_when_cmdline_matches():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="C:\\Python\\python.exe -m autoclave.backend.main\r\n"
        )
        assert backend_guard.is_stale_backend_running(1234) is True


def test_is_stale_backend_running_false_when_cmdline_different():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="notepad.exe\r\n")
        assert backend_guard.is_stale_backend_running(1234) is False


def test_is_stale_backend_running_false_when_subprocess_raises():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("powershell no disponible")
        assert backend_guard.is_stale_backend_running(1234) is False


def test_kill_stale_backend_calls_taskkill_con_pid():
    with patch("autoclave.installation.backend_guard.subprocess.run") as mock_run:
        backend_guard.kill_stale_backend(4321)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["taskkill", "/PID", "4321", "/F"]


def test_cleanup_stale_backend_mata_proceso_huerfano(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(9999, path)

    with patch("autoclave.installation.backend_guard.is_stale_backend_running", return_value=True) as mock_is_stale, \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_is_stale.assert_called_once_with(9999)
        mock_kill.assert_called_once_with(9999)


def test_cleanup_stale_backend_no_mata_si_no_esta_huerfano(tmp_path):
    path = tmp_path / "backend.pid"
    backend_guard.write_backend_pid(9999, path)

    with patch("autoclave.installation.backend_guard.is_stale_backend_running", return_value=False), \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_kill.assert_not_called()


def test_cleanup_stale_backend_no_hace_nada_sin_pid_file(tmp_path):
    path = tmp_path / "no_existe.pid"

    with patch("autoclave.installation.backend_guard.is_stale_backend_running") as mock_is_stale, \
         patch("autoclave.installation.backend_guard.kill_stale_backend") as mock_kill:
        backend_guard.cleanup_stale_backend(path)

        mock_is_stale.assert_not_called()
        mock_kill.assert_not_called()
```

- [ ] **Step 2: Correr los tests y confirmar que fallan (no existe el módulo)**

Run: `pytest tests/test_backend_guard.py -v`
Expected: `ModuleNotFoundError: No module named 'autoclave.installation.backend_guard'` (o `ImportError`) en todos los tests.

- [ ] **Step 3: Crear el módulo**

Crear `src/autoclave/installation/backend_guard.py`:

```python
from pathlib import Path
import subprocess
from autoclave.utils.logging import logger

_PID_FILE = Path(__file__).resolve().parents[3] / "data" / "backend.pid"


def write_backend_pid(pid: int, path: Path = _PID_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


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
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5)


def cleanup_stale_backend(path: Path = _PID_FILE) -> None:
    """Mata cualquier backend huérfano de una sesión anterior. Llamar antes de
    lanzar un backend nuevo, solo cuando is_backend_alive() ya dio False."""
    pid = read_backend_pid(path)
    if pid is not None and is_stale_backend_running(pid):
        logger.warning(
            "Backend huérfano detectado (PID %d) — terminando antes de arrancar uno nuevo", pid
        )
        kill_stale_backend(pid)
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_backend_guard.py -v`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/installation/backend_guard.py tests/test_backend_guard.py
git commit -m "feat: agregar backend_guard para limpiar procesos backend huérfanos"
```

---

### Task 2: Módulo `device_reset.py` — detección y reset PnP del dispositivo USB

**Files:**
- Create: `src/autoclave/protocols/device_reset.py`
- Test: `tests/test_device_reset.py`

**Interfaces:**
- Produces: `is_device_not_functioning_error(exc: Exception) -> bool`,
  `reset_usb_serial_device(port_name: str, timeout: float = 15.0) -> bool` —
  consumidas por Task 3.

- [ ] **Step 1: Escribir los tests**

Crear `tests/test_device_reset.py`:

```python
from unittest.mock import patch, MagicMock
from autoclave.protocols import device_reset


def test_is_device_not_functioning_error_true_para_winerror_31():
    exc = Exception(
        "Cannot configure port, something went wrong. Original message: "
        "PermissionError(13, 'Uno de los dispositivos conectados al sistema no funciona.', None, 31)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is True


def test_is_device_not_functioning_error_false_para_winerror_5():
    exc = Exception(
        "could not open port 'COM4': PermissionError(13, 'Acceso denegado.', None, 5)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is False


def test_is_device_not_functioning_error_false_para_excepcion_generica():
    exc = Exception(
        "could not open port 'COM9': FileNotFoundError(2, 'El sistema no puede "
        "encontrar el archivo especificado.', None, 2)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is False


def test_reset_usb_serial_device_true_cuando_powershell_reporta_ok():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="OK\r\n", returncode=0)
        assert device_reset.reset_usb_serial_device("COM4") is True


def test_reset_usb_serial_device_false_cuando_no_encuentra_dispositivo():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="NOTFOUND\r\n", returncode=0)
        assert device_reset.reset_usb_serial_device("COM4") is False


def test_reset_usb_serial_device_false_cuando_subprocess_falla():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("powershell no disponible")
        assert device_reset.reset_usb_serial_device("COM4") is False


def test_reset_usb_serial_device_incluye_nombre_de_puerto_en_el_comando():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="OK\r\n", returncode=0)
        device_reset.reset_usb_serial_device("COM4")

        args = mock_run.call_args[0][0]
        assert args[0] == "powershell"
        script = args[-1]
        assert "COM4" in script
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `pytest tests/test_device_reset.py -v`
Expected: `ModuleNotFoundError: No module named 'autoclave.protocols.device_reset'` en todos los tests.

- [ ] **Step 3: Crear el módulo**

Crear `src/autoclave/protocols/device_reset.py`:

```python
import re
import subprocess
from autoclave.utils.logging import logger


def is_device_not_functioning_error(exc: Exception) -> bool:
    """True si el mensaje de la excepción corresponde a Win32 ERROR_GEN_FAILURE
    (31) — 'dispositivo no funciona' — la firma de un adaptador USB-serial
    atascado a nivel de driver, que ningún reintento de apertura puede resolver."""
    return bool(re.search(r",\s*31\)\s*$", str(exc)))


def reset_usb_serial_device(port_name: str, timeout: float = 15.0) -> bool:
    """Ejecuta un ciclo Disable/Enable PnP sobre el dispositivo Windows asociado
    a `port_name` (ej. 'COM4') — equivalente por software a desconectar y
    reconectar el cable USB. Requiere que el proceso corra como Administrador."""
    script = (
        f"$dev = Get-PnpDevice -Class Ports | "
        f"Where-Object {{ $_.FriendlyName -match '\\({re.escape(port_name)}\\)' }} | "
        f"Select-Object -First 1; "
        f"if ($dev) {{ "
        f"Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false; "
        f"Start-Sleep -Seconds 2; "
        f"Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false; "
        f"Write-Output 'OK' "
        f"}} else {{ Write-Output 'NOTFOUND' }}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
        )
        ok = "OK" in (result.stdout or "")
        if not ok:
            logger.warning(
                "reset_usb_serial_device: no se encontró/reseteó %s (%s)",
                port_name, result.stdout,
            )
        return ok
    except Exception as exc:
        logger.warning("reset_usb_serial_device: error ejecutando reset de %s: %s", port_name, exc)
        return False
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_device_reset.py -v`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/protocols/device_reset.py tests/test_device_reset.py
git commit -m "feat: agregar device_reset para reset PnP de adaptador USB-serial atascado"
```

---

### Task 3: Integrar `device_reset` en `SerialLink._connect()`

**Files:**
- Modify: `src/autoclave/protocols/serial_link.py`
- Test: `tests/test_serial_link_reset.py`

**Interfaces:**
- Consumes: `device_reset.is_device_not_functioning_error(exc: Exception) -> bool`,
  `device_reset.reset_usb_serial_device(port_name: str, timeout: float = 15.0) -> bool`
  (de Task 2).
- Produces: atributos de instancia `self._ever_connected: bool`,
  `self._device_reset_attempted: bool`, `self._consecutive_gen_failures: int`, y
  constante de clase `SerialLink.GEN_FAILURE_RESET_THRESHOLD = 5`.

- [ ] **Step 1: Escribir los tests**

Crear `tests/test_serial_link_reset.py`:

```python
from unittest.mock import patch, MagicMock
from autoclave.protocols.serial_link import SerialLink

_WINERROR_31 = Exception(
    "Cannot configure port, something went wrong. Original message: "
    "PermissionError(13, 'Uno de los dispositivos conectados al sistema no funciona.', None, 31)"
)
_WINERROR_5 = Exception(
    "could not open port 'COM4': PermissionError(13, 'Acceso denegado.', None, 5)"
)


def _make_link():
    link = SerialLink()
    link._scan_ports = lambda: "COM4"
    return link


def test_reset_se_dispara_tras_threshold_fallos_consecutivos():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD - 1):
            assert link._connect() is False
        mock_reset.assert_not_called()

        assert link._connect() is False
        mock_reset.assert_called_once_with("COM4")


def test_reset_solo_se_dispara_una_vez():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 2):
            link._connect()

        mock_reset.assert_called_once()


def test_reset_no_se_dispara_tras_conexion_exitosa():
    link = _make_link()
    fake_serial = MagicMock()

    with patch("autoclave.protocols.serial_link.serial.Serial", return_value=fake_serial):
        assert link._connect() is True

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 2):
            link._connect()

        mock_reset.assert_not_called()


def test_falla_distinta_a_winerror_31_no_dispara_reset():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_5), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 3):
            link._connect()

        mock_reset.assert_not_called()
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `pytest tests/test_serial_link_reset.py -v`
Expected: `AttributeError: type object 'SerialLink' has no attribute 'GEN_FAILURE_RESET_THRESHOLD'`
(o `AttributeError: <module ...serial_link> does not have the attribute 'device_reset'`
al intentar patchear) en todos los tests.

- [ ] **Step 3: Agregar el import, la constante y el estado nuevo**

En `src/autoclave/protocols/serial_link.py`, agregar el import junto a los
existentes (después de `from autoclave.utils.logging import logger`):

```python
from autoclave.protocols import device_reset
```

En la clase `SerialLink`, agregar la constante junto a las existentes:

```python
class SerialLink:
    DATA_TIMEOUT       = 3.0  # segundos sin datos => comunicación caída
    HEARTBEAT_INTERVAL = 2.0  # segundos entre HB enviados al ESP32
    GEN_FAILURE_RESET_THRESHOLD = 5  # ~15s de reintentos (scan_interval=3.0) antes de resetear el dispositivo
```

En `__init__`, agregar junto al resto del estado (después de
`self._expected_ack: Optional[str] = None`):

```python
        self._ever_connected = False
        self._device_reset_attempted = False
        self._consecutive_gen_failures = 0
```

- [ ] **Step 4: Modificar `_connect()`**

Reemplazar:

```python
    def _connect(self) -> bool:
        port = self._scan_ports()
        if not port:
            return False

        try:
            self.serial = serial.Serial(port, self.baudrate, timeout=0.2)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            logger.info(f"Conectado a ESP32 en {port}")

            with self.data_lock:
                self.data["port_open"] = True
                self.data["data_alive"] = False
                self.data["last_update"] = None

            return True

        except Exception as e:
            logger.warning(f"Error abriendo puerto {port}: {e}")
            self.serial = None
            return False
```

por:

```python
    def _connect(self) -> bool:
        port = self._scan_ports()
        if not port:
            return False

        try:
            self.serial = serial.Serial(port, self.baudrate, timeout=0.2)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            logger.info(f"Conectado a ESP32 en {port}")

            with self.data_lock:
                self.data["port_open"] = True
                self.data["data_alive"] = False
                self.data["last_update"] = None

            self._ever_connected = True
            self._consecutive_gen_failures = 0
            return True

        except Exception as e:
            logger.warning(f"Error abriendo puerto {port}: {e}")
            self.serial = None

            if not self._ever_connected and not self._device_reset_attempted:
                if device_reset.is_device_not_functioning_error(e):
                    self._consecutive_gen_failures += 1
                    if self._consecutive_gen_failures >= self.GEN_FAILURE_RESET_THRESHOLD:
                        self._device_reset_attempted = True
                        logger.warning(
                            "SerialLink: %d intentos con dispositivo no funcional — "
                            "intentando reset PnP de %s",
                            self._consecutive_gen_failures, port,
                        )
                        device_reset.reset_usb_serial_device(port)
                        self._consecutive_gen_failures = 0
                else:
                    self._consecutive_gen_failures = 0

            return False
```

- [ ] **Step 5: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_serial_link_reset.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Correr la suite completa**

Run: `pytest tests/ --ignore=tests/test_io_views.py -q`
Expected: todos los tests existentes siguen pasando, más los nuevos de Task 1-3.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/protocols/serial_link.py tests/test_serial_link_reset.py
git commit -m "feat: disparar reset PnP en SerialLink tras fallos de conexión inicial por dispositivo no funcional"
```

---

### Task 4: Integrar `backend_guard` en `main.py`

**Files:**
- Modify: `src/autoclave/main.py`

**Interfaces:**
- Consumes: `backend_guard.cleanup_stale_backend() -> None`,
  `backend_guard.write_backend_pid(pid: int) -> None` (de Task 1, usando el path
  por defecto `_PID_FILE`).

- [ ] **Step 1: Agregar el import**

En `src/autoclave/main.py`, agregar junto a los imports existentes de
`autoclave.installation` (después de
`from autoclave.installation.clock_guard import ClockTamperedError`):

```python
from autoclave.installation import backend_guard
```

- [ ] **Step 2: Integrar la limpieza antes de lanzar el backend**

Reemplazar el bloque `# ── 2. Iniciar backend` (dentro de `if SOURCE_DOOR == 1:`):

```python
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
```

por:

```python
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            backend_guard.cleanup_stale_backend()
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            backend_guard.write_backend_pid(backend_process.pid)
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
```

- [ ] **Step 3: Verificar sintaxis y que la suite completa sigue pasando**

Run: `python -c "import ast; ast.parse(open('src/autoclave/main.py', encoding='utf-8').read())"`
Expected: sin salida (sin errores de sintaxis).

Run: `pytest tests/ --ignore=tests/test_io_views.py -q`
Expected: todos los tests pasan (esta integración no tiene test propio — `main.py`
no tiene cobertura unitaria hoy, y la lógica que sí es testeable ya se cubrió en
Task 1; ver nota de Testing en el spec).

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/main.py
git commit -m "feat: limpiar backend huérfano y registrar PID antes de lanzar el backend"
```

---

### Task 5: Ventana de espera mínima por conexión de hardware en `main.py`

**Files:**
- Modify: `src/autoclave/main.py`
- Test: `tests/test_main_hardware_wait.py`

**Interfaces:**
- Produces: `_hardware_connected() -> bool`,
  `wait_for_hardware_connection(max_wait: int = 40) -> bool` en el módulo
  `autoclave.main`.

- [ ] **Step 1: Escribir los tests para `_hardware_connected()`**

Crear `tests/test_main_hardware_wait.py`:

```python
from unittest.mock import patch, MagicMock
import requests
from autoclave import main as main_module


def test_hardware_connected_true_sin_alarma_no_hay_conexion():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"alarms": []}
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is True


def test_hardware_connected_false_con_alarma_no_hay_conexion():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"alarms": [{"id": "NO_HAY_CONEXION"}]}
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is False


def test_hardware_connected_false_si_status_no_responde_200():
    resp = MagicMock(status_code=500)
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is False


def test_hardware_connected_false_si_request_lanza_excepcion():
    with patch("autoclave.main.requests.get", side_effect=requests.RequestException("boom")):
        assert main_module._hardware_connected() is False
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `pytest tests/test_main_hardware_wait.py -v`
Expected: `AttributeError: <module 'autoclave.main' ...> does not have the attribute '_hardware_connected'`
en los 4 tests.

- [ ] **Step 3: Agregar `_hardware_connected()` y `wait_for_hardware_connection()`**

En `src/autoclave/main.py`, agregar después de la función `wait_for_backend`
existente (antes de `def main():`):

```python
def _hardware_connected() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=1)
        if r.status_code != 200:
            return False
        alarms = r.json().get("alarms", [])
        return not any(a.get("id") == "NO_HAY_CONEXION" for a in alarms)
    except requests.RequestException:
        return False


def wait_for_hardware_connection(max_wait=40) -> bool:
    """Ventana de espera mínima mientras la tarjeta no está conectada. Se cierra
    sola al conectar, o muestra un mensaje final y se cierra igual al agotar
    max_wait (no bloquea el arranque de la UI — placeholder hasta que se
    implemente la pantalla de arranque definitiva)."""
    if _hardware_connected():
        return True

    import tkinter as tk
    root = tk.Tk()
    root.title("Autoclave")
    root.geometry("360x120")
    label = tk.Label(root, text="Conectando con la tarjeta...", font=("Segoe UI", 12))
    label.pack(expand=True, padx=20, pady=20)

    start = time.time()
    connected = False

    def _poll():
        nonlocal connected
        if _hardware_connected():
            connected = True
            root.destroy()
            return
        if time.time() - start >= max_wait:
            label.config(
                text="No se pudo establecer comunicación con la tarjeta.\n"
                     "Verifique la conexión y reinicie el equipo."
            )
            root.after(5000, root.destroy)
            return
        root.after(1000, _poll)

    root.after(1000, _poll)
    root.mainloop()
    return connected
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_main_hardware_wait.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Llamar `wait_for_hardware_connection()` desde `main()`**

En el bloque `if SOURCE_DOOR == 1:` (rama `else` de `is_backend_alive()`, después
de la llamada a `wait_for_backend` integrada en Task 4), agregar la llamada al
final del bloque `if SOURCE_DOOR == 1:` (fuera del `if/else` de
`is_backend_alive()`, para que corra tanto si el backend ya estaba corriendo
como si se acaba de lanzar):

```python
    if SOURCE_DOOR == 1:
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            backend_guard.cleanup_stale_backend()
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            backend_guard.write_backend_pid(backend_process.pid)
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
        wait_for_hardware_connection(max_wait=40)
    else:
```

- [ ] **Step 6: Verificar sintaxis y correr la suite completa**

Run: `python -c "import ast; ast.parse(open('src/autoclave/main.py', encoding='utf-8').read())"`
Expected: sin salida.

Run: `pytest tests/ --ignore=tests/test_io_views.py -q`
Expected: todos los tests pasan.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/main.py tests/test_main_hardware_wait.py
git commit -m "feat: mostrar espera mínima hasta conectar con la tarjeta al arrancar"
```

---

## Self-Review Notes

- **Cobertura del spec:** Componente 1 (Task 1 + Task 4), Componente 2 (Task 2 +
  Task 3), Componente 3 (Task 5) — los tres componentes del spec tienen tareas
  dedicadas. Las constantes exactas (`GEN_FAILURE_RESET_THRESHOLD = 5`,
  `max_wait=40`) coinciden con el spec. El alcance a `SOURCE_DOOR == 1` está
  reflejado en Task 4/5 (ambas dentro de esa rama de `main.py`).
- **Placeholders:** ninguno — todo el código de cada step es el código final.
- **Consistencia de tipos/nombres:** `device_reset.is_device_not_functioning_error`
  / `device_reset.reset_usb_serial_device` se usan con la misma firma en Task 2
  (implementación) y Task 3 (consumo) — verificado. `backend_guard.cleanup_stale_backend`
  / `write_backend_pid` igual entre Task 1 y Task 4 — verificado.
  `_hardware_connected` / `wait_for_hardware_connection` consistentes entre
  Task 5's test y su implementación — verificado.
- **Orden de tareas:** Task 3 depende de Task 2 (import `device_reset`); Task 4
  depende de Task 1 (import `backend_guard`); Task 5 es independiente de 3/4 mas
  se ejecuta después por simplicidad (ambas tocan `main.py`).
- **Fuera de alcance explícito, no testeado:** el bucle `Tkinter.mainloop()` de
  `wait_for_hardware_connection` no tiene test automatizado — solo la lógica pura
  `_hardware_connected()`. Esto es consistente con que `main.py` no tenía ninguna
  cobertura de tests antes de este plan.
