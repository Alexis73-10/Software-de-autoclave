# Protocolo de reconexión con la tarjeta ESP32 al arrancar

## Contexto

El usuario reporta que, después de un cierre inesperado de la app (crash, corte de
energía, cierre forzado), al reiniciar el software a veces no logra conectar con la
tarjeta ESP32 por el puerto COM — y el único arreglo que funciona en ese momento es
desconectar y reconectar físicamente el cable USB, algo inviable en un equipo
desatendido en campo.

Investigación sobre logs reales (`src/logs/autoclave.log`) y el código
(`src/autoclave/protocols/serial_link.py`, `src/autoclave/main.py`) confirmó **dos
causas distintas** bajo el mismo síntoma:

1. **Dispositivo USB atascado a nivel de driver de Windows** (causa confirmada y
   recurrente en los logs): `serial.Serial(port, ...)` falla con
   `PermissionError(13, 'Uno de los dispositivos conectados al sistema no
   funciona.', None, 31)` — Win32 `ERROR_GEN_FAILURE`. El watchdog actual de
   `SerialLink` (`_watchdog_loop`, cada 3s) reintenta `_connect()` indefinidamente,
   pero **reintentar el mismo `serial.Serial()` no puede arreglar este estado** —
   solo una re-enumeración del dispositivo lo hace (equivalente a desconectar y
   reconectar el cable). Esto explica por qué el reintento automático existente
   nunca se recupera solo, y por qué el arreglo manual que funciona es justamente
   la reconexión física.

2. **Proceso backend huérfano** (causa relacionada, con al menos una ocurrencia
   confirmada en logs, `PermissionError(13, 'Acceso denegado.', None, 5)` —
   `ERROR_ACCESS_DENIED`): `main.py` lanza el backend con `subprocess.Popen(...)`
   sin ningún mecanismo que lo ate al ciclo de vida del proceso padre (sin Job
   Object, sin `atexit`, sin manejo de señales). Si la app principal muere de forma
   abrupta, el subproceso backend puede quedar corriendo en segundo plano,
   invisible, con el puerto COM tomado. Un reinicio normal de la app entonces
   lanza un backend nuevo que choca contra ese huérfano.

Además, hoy ni el cierre normal ni un cierre abrupto llaman `serial.close()`
explícitamente — se depende enteramente de que Windows libere el handle cuando el
proceso muere. Y si la conexión con el hardware nunca se logra al arrancar, la UI
no muestra ningún aviso: arranca igual, sin datos (`main.py`, comentario "la UI
arrancará sin datos").

## Alcance

Aplica solo a la PC que posee la conexión física con la tarjeta (`SOURCE_DOOR == 1`
en `main.py`). La PC de la puerta 2 no lanza un backend local ni tiene un
`SerialLink` propio — queda fuera de alcance.

Tres componentes, cada uno resolviendo su parte del problema:

1. Limpieza de proceso backend huérfano antes de lanzar uno nuevo.
2. Reset del dispositivo USB por PnP, solo durante la conexión inicial de
   `SerialLink`, cuando el error coincide con la firma de "dispositivo no
   funcional" (Win32 `ERROR_GEN_FAILURE` / código 31).
3. Ventana de espera mínima en `main.py` mientras la tarjeta no esté conectada,
   reutilizando la alarma `NO_HAY_CONEXION` que ya existe.

## Componente 1 — Limpieza de proceso huérfano

**Archivo nuevo:** `src/autoclave/installation/backend_guard.py`, siguiendo el
mismo patrón de `src/autoclave/devices/printer/heartbeat.py` (módulo de funciones
simples con ruta por defecto vía `Path(__file__).resolve().parents[N]`).

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

**Integración en `main.py`** (bloque `# 2. Iniciar backend`, rama `SOURCE_DOOR == 1`):

```python
if is_backend_alive():
    logger.info("Backend ya estaba corriendo")
else:
    backend_guard.cleanup_stale_backend()
    logger.info("Iniciando backend...")
    backend_process = subprocess.Popen(...)   # sin cambios
    backend_guard.write_backend_pid(backend_process.pid)
    if not wait_for_backend(process=backend_process, max_wait=40):
        logger.error("Backend no respondió — la UI arrancará sin datos")
```

`cleanup_stale_backend()` solo se llama cuando `is_backend_alive()` ya dio `False`
— si un backend previo (huérfano o no) sigue realmente sano y respondiendo, se
reutiliza tal cual, sin tocarlo (comportamiento actual, sin cambios).

Sin dependencias nuevas — `taskkill` y `Get-CimInstance` son parte de Windows.

## Componente 2 — Reset del dispositivo USB por PnP

**Archivo nuevo:** `src/autoclave/protocols/device_reset.py`.

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
            logger.warning("reset_usb_serial_device: no se encontró/reseteó %s (%s)", port_name, result.stdout)
        return ok
    except Exception as exc:
        logger.warning("reset_usb_serial_device: error ejecutando reset de %s: %s", port_name, exc)
        return False
```

**Integración en `SerialLink`** (`src/autoclave/protocols/serial_link.py`):

Nuevo estado de instancia en `__init__`:

```python
self._ever_connected = False
self._device_reset_attempted = False
self._consecutive_gen_failures = 0
```

Nueva constante de clase junto a `DATA_TIMEOUT`/`HEARTBEAT_INTERVAL`:

```python
GEN_FAILURE_RESET_THRESHOLD = 5   # ~15s de reintentos (scan_interval=3.0) antes de resetear
```

`_connect()` pasa de:

```python
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

a:

```python
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

(`from autoclave.protocols import device_reset` agregado a los imports del
módulo, siguiendo el mismo estilo que `from autoclave.devices.printer import
heartbeat` en `main.py`.)

**Por qué solo en la conexión inicial:** el reset de dispositivo reinicia
físicamente la placa ESP32 (pierde estado). `self._ever_connected` empieza en
`False` y pasa a `True` para siempre en cuanto `_connect()` tiene éxito una vez —
a partir de ahí, **nunca** se vuelve a intentar un reset de dispositivo en esa
ejecución del proceso, sin importar cuántas veces se pierda la conexión después
(el `_watchdog_loop` sigue reintentando con la lógica simple de siempre, sin
tocar hardware). Esto cumple lo acordado: el reset de dispositivo no puede
dispararse con un ciclo en curso.

**Por qué solo una vez:** `self._device_reset_attempted` asegura un único intento
de reset por proceso — si el dispositivo sigue fallando después del reset (cable
dañado, placa con falla real), no se vuelve a resetear en loop; la alarma
`NO_HAY_CONEXION` queda como señal persistente y el watchdog sigue reintentando
la conexión simple indefinidamente, como hoy.

## Componente 3 — Ventana de espera mínima en el arranque

**Modificación en `main.py`**, agregada después del bloque existente de espera
del backend (`wait_for_backend`), solo en la rama `SOURCE_DOOR == 1`:

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

Se llama justo después del bloque `# 2. Iniciar backend` (rama `SOURCE_DOOR == 1`
únicamente), antes de `# 2b. Iniciar heartbeat`:

```python
    if SOURCE_DOOR == 1:
        ...  # bloque existente, con backend_guard integrado (Componente 1)
        wait_for_hardware_connection(max_wait=40)
    else:
        ...
```

El resultado de `wait_for_hardware_connection()` no bloquea el arranque — la UI
se construye igual después, con o sin conexión, igual que el comportamiento
actual (`"la UI arrancará sin datos"`). Es solo feedback visual mientras se
espera; no cambia la política de permitir operar sin hardware.

## Fuera de alcance

- Pantalla de arranque definitiva (mencionada por el usuario como trabajo futuro
  separado) — esta ventana Tkinter es un placeholder mínimo, sin diseño visual
  elaborado.
- Cerrar `serial.close()` explícitamente en el shutdown normal de `main.py`
  (`on_close()`) — mejora relacionada pero independiente; no resuelve el caso de
  cierre abrupto que es el foco de este spec, y el componente 1 (limpieza de
  huérfanos) ya cubre la consecuencia práctica de que no se cierre.
- Manejo de señales/`atexit` en `main.py` para terminar el backend de forma más
  robusta ante crashes del proceso padre — el PID file (componente 1) ataca la
  misma consecuencia desde el lado del próximo arranque, que es donde el usuario
  puede observar y verificar el arreglo sin depender de instrumentar todos los
  posibles caminos de crash del proceso padre.
- Reset de dispositivo durante reconexiones en tiempo de ejecución (con un ciclo
  en curso) — explícitamente descartado por decisión del usuario, ver Componente 2.
- La PC de puerta 2 (`SOURCE_DOOR != 1`) — no tiene backend ni `SerialLink` local.

## Testing

- `tests/test_backend_guard.py` (nuevo): `write_backend_pid`/`read_backend_pid`
  con `tmp_path` (round-trip real de archivo); `is_stale_backend_running` y
  `kill_stale_backend` con `subprocess.run` mockeado (casos: proceso vivo con
  cmdline coincidente → True; proceso vivo con cmdline distinta → False; error
  de subprocess → False); `cleanup_stale_backend` orquestando ambos con mocks.
- `tests/test_device_reset.py` (nuevo): `is_device_not_functioning_error` contra
  el mensaje real observado en los logs (termina en `, 31)`) → True; contra el
  mensaje de `ERROR_ACCESS_DENIED` (termina en `, 5)`) → False; contra una
  excepción genérica sin ese patrón → False. `reset_usb_serial_device` con
  `subprocess.run` mockeado: verifica el comando invocado (`powershell`, script
  contiene el nombre de puerto), y el mapeo de `stdout`/excepción a `True`/`False`.
- `tests/test_serial_link_reset.py` (nuevo, primera cobertura unitaria real de
  `SerialLink`): con `serial.Serial` monkeypatcheado para lanzar la excepción con
  la firma de `ERROR_GEN_FAILURE` en cada intento, verificar que
  `device_reset.reset_usb_serial_device` se llama exactamente una vez tras
  `GEN_FAILURE_RESET_THRESHOLD` fallos consecutivos de `_connect()`, y que un
  fallo posterior (tras un `_connect()` exitoso simulado) nunca dispara un
  segundo reset. No se testea el `_watchdog_loop`/threading real — se llama
  `_connect()` directamente en el test, como unidad aislada.
- Suite completa (`pytest tests/ --ignore=tests/test_io_views.py`) debe seguir
  pasando.
