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
