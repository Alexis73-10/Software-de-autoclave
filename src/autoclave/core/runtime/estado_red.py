# core/runtime/estado_red.py
#
# Estado de red en SOLO LECTURA para OPCIONES › Conectividad (O2g, tanda 6):
# adaptadores (nombre, conectado, IPv4, velocidad), Wi-Fi conectado e
# intensidad de señal. Cambiar Wi-Fi o IP desde el software NO está habilitado
# (DECISIÓN SIN CONFIRMAR: requiere privilegios de administrador de Windows y
# un error puede dejar el equipo sin soporte remoto).
#
# Fuentes: psutil (adaptadores, sin privilegios) y `netsh wlan show interfaces`
# (SSID y señal; solo Windows, sin privilegios). Todo con plazo corto y cache
# de 10 s (time.monotonic) para que la pantalla no lance un proceso por sondeo.
# Nunca lanza: ante cualquier error devuelve lo que pudo leer.

import re
import subprocess
import sys
import threading
import time

CACHE_S = 10.0
PLAZO_NETSH_S = 3.0

_RE_CLAVE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*)$")


def _correr_netsh() -> str:
    if not sys.platform.startswith("win"):
        return ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True,
                       timeout=PLAZO_NETSH_S, creationflags=flags)
    for cod in ("utf-8", "cp850", "cp1252"):
        try:
            return r.stdout.decode(cod)
        except UnicodeDecodeError:
            continue
    return r.stdout.decode("latin-1", errors="replace")


def interpretar_netsh(texto: str) -> dict:
    """{"ssid", "senal" (0-100 o None), "conectado"} del primer adaptador Wi-Fi.
    Acepta la salida en inglés o en español."""
    datos = {}
    for linea in (texto or "").splitlines():
        m = _RE_CLAVE.match(linea)
        if not m:
            continue
        clave, valor = m.group(1).strip().lower(), m.group(2).strip()
        if clave == "ssid" and "ssid" not in datos:
            datos["ssid"] = valor
        elif clave in ("signal", "señal", "senal") and "senal" not in datos:
            n = re.match(r"(\d+)", valor)
            datos["senal"] = int(n.group(1)) if n else None
        elif clave in ("state", "estado") and "estado" not in datos:
            datos["estado"] = valor.lower()
    conectado = datos.get("estado", "") in ("connected", "conectado")
    return {"ssid": datos.get("ssid") if conectado else None,
            "senal": datos.get("senal") if conectado else None,
            "conectado": conectado}


def _adaptadores_psutil() -> list[dict]:
    import socket
    import psutil
    direcciones = psutil.net_if_addrs()
    estados = psutil.net_if_stats()
    lista = []
    for nombre, addrs in direcciones.items():
        st = estados.get(nombre)
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        if nombre.lower().startswith(("loopback", "lo")) or any(i.startswith("127.") for i in ipv4):
            continue
        lista.append({"nombre": nombre, "conectado": bool(st and st.isup),
                      "ipv4": ipv4[0] if ipv4 else None,
                      "velocidad_mbps": st.speed if st and st.speed else None,
                      "tipo": tipo_de(nombre)})
    lista.sort(key=lambda a: (not a["conectado"], a["nombre"].lower()))
    return lista


def tipo_de(nombre: str) -> str:
    n = nombre.lower()
    if any(k in n for k in ("wi-fi", "wifi", "wlan", "wireless", "inalámbrica")):
        return "wifi"
    if any(k in n for k in ("ethernet", "eth", "local")):
        return "ethernet"
    return "otro"


class EstadoRed:
    def __init__(self, adaptadores=_adaptadores_psutil, netsh=_correr_netsh,
                 reloj=time.monotonic):
        self._adaptadores = adaptadores
        self._netsh = netsh
        self._reloj = reloj
        self._lock = threading.Lock()
        self._cache = None
        self._t = None

    def leer(self) -> dict:
        with self._lock:
            if self._cache is not None and self._reloj() - self._t < CACHE_S:
                return self._cache
        try:
            adaptadores = self._adaptadores()
        except Exception:
            adaptadores = []
        try:
            wifi = interpretar_netsh(self._netsh())
        except Exception:
            wifi = {"ssid": None, "senal": None, "conectado": False}
        d = {"adaptadores": adaptadores, "wifi": wifi,
             "conectado": any(a["conectado"] and a["ipv4"] for a in adaptadores),
             "editable": False}
        with self._lock:
            self._cache, self._t = d, self._reloj()
        return d
