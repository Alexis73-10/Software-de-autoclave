# autoclave/estacion/digimon.py
#
# EST-06 (tanda 17): valores de la asociación táctil → monitor en
# HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon, su respaldo y su escritura.
#
# ── Formato de los valores (lo que deja MultiDigitizer.exe) ─────────────────
# Fuente: no hay en el repositorio una exportación de la clave de un equipo
# donde MultiDigitizer haya funcionado (se buscó en tools/estacion,
# 06_asociar_tactiles.ps1 / Get-ValoresDigimon, el .iss y docs/informes de las
# tandas 9, 11 y 17: solo dicen "un valor por táctil" y cuentan los valores).
# El formato se documenta con lo conocido de Windows (calibración de Tablet
# PC, "Configuración de Tablet PC > Configurar"; exportaciones .reg de esa
# clave publicadas en foros de soporte de Microsoft y de fabricantes de
# paneles táctiles):
#   - un valor por digitalizador asociado;
#   - NOMBRE del valor: "<n>-" + ruta de interfaz del dispositivo HID del
#     digitalizador, tal como la da Raw Input (GetRawInputDeviceInfoW con
#     RIDI_DEVICENAME), p. ej.
#       20-\\?\HID#VID_222A&PID_0001&Col01#7&1d1dfc1&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}
#     ({4d1e55b2-...} = GUID_DEVINTERFACE_HID). El prefijo numérico observado
#     en esas exportaciones es "20-";
#   - DATO (REG_SZ): ruta de interfaz del monitor, la que da
#     EnumDisplayDevicesW(..., EDD_GET_DEVICE_INTERFACE_NAME), p. ej.
#       \\?\DISPLAY#AUO22EC#4&2a5d4cd&0&UID265988#{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}
#     ({e6f07b5f-...} = GUID_DEVINTERFACE_MONITOR).
# Mayúsculas/minúsculas: se escriben TAL CUAL las devuelve Windows (no se
# cambian); las comparaciones (duplicados) no distinguen mayúsculas.
# DECISIÓN SIN CONFIRMAR: el prefijo "20-". Revisión R2 (V17-s2-05): se usa
# siempre "20-", salvo que todos los valores existentes tengan la forma
# completa con un mismo prefijo y uno de ellos sea un táctil tocado en esta
# pasada (elegir_prefijo); otros prefijos observados solo se avisan. Verificación manual
# pendiente en el PC de prueba: comparar con una exportación de la clave hecha
# por MultiDigitizer (hoja de banco).
#
# ── Respaldo (compatible con 06_revertir_asociar_tactiles.ps1) ──────────────
# respaldo_06_asociar_tactiles.json = {"DigimonAntes": {nombre: {"Valor": v,
# "Tipo": "String"|"ExpandString"|"DWord"|"QWord"|"MultiString"|"Binary"}},
# "DigimonExistia": bool, ...otras claves del paso se conservan}. Se escribe
# solo si aún no tiene DigimonAntes (la primera ejecución manda, igual que el
# script). La herramienta nunca BORRA valores (el inverso solo restaura los
# que siguen existiendo): solo crea o reemplaza.

import json
import os
import re
from dataclasses import dataclass, field

RUTA_DIGIMON = r"SOFTWARE\Microsoft\Wisp\Pen\Digimon"
PREFIJO_POR_DEFECTO = "20-"
NOMBRE_RESPALDO = "respaldo_06_asociar_tactiles.json"

GUID_HID = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
GUID_MONITOR = "{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}"

# \\?\HID#<hardware>#<instancia>#{GUID}  (ningún segmento vacío ni con \ / espacios)
_RE_HID = re.compile(r"^\\\\\?\\HID#[^\\/#\s]+#[^\\/#\s]+#" + re.escape(GUID_HID) + r"$", re.I)
_RE_MONITOR = re.compile(r"^\\\\\?\\DISPLAY#[^\\/#\s]+#[^\\/#\s]+#" + re.escape(GUID_MONITOR) + r"$", re.I)
_RE_PREFIJO = re.compile(r"^(\d+-)\\\\\?\\HID#", re.I)

# winreg.REG_* → nombre de RegistryValueKind de .NET (lo que guarda el script)
_TIPOS = {1: "String", 2: "ExpandString", 3: "Binary", 4: "DWord", 7: "MultiString", 11: "QWord"}


def normalizar_ruta(ruta) -> str:
    """Quita espacios y nulos de los extremos y cambia el prefijo NT "\\??\\"
    (que algunas versiones devuelven en RIDI_DEVICENAME) por "\\\\?\\". No
    cambia mayúsculas/minúsculas."""
    if not isinstance(ruta, str):
        return ""
    r = ruta.strip().strip("\x00").strip()
    if r.startswith("\\??\\"):
        r = "\\\\?\\" + r[4:]
    return r


def es_ruta_hid(ruta: str) -> bool:
    return bool(_RE_HID.match(ruta or ""))


def es_ruta_monitor(ruta: str) -> bool:
    return bool(_RE_MONITOR.match(ruta or ""))


def elegir_prefijo(existentes: dict, hids_tocados=()):
    """V17-s2-05 (revisión R2): prefijo del nombre de los valores nuevos.
    Devuelve (prefijo, aviso_o_None).

    Siempre PREFIJO_POR_DEFECTO ("20-"), salvo un caso: TODOS los valores que
    ya hay en Digimon tienen la forma completa "<n>-" + ruta HID (es_ruta_hid)
    = ruta de monitor (es_ruta_monitor), con el mismo prefijo P, y al menos uno
    de esos HID es un digitalizador tocado en esta pasada (o sea, una pantalla
    táctil confirmada por Raw Input, uso 0x04). Entonces se usa P: es la forma
    que Windows dejó para estas mismas pantallas, y con "20-" quedaría una
    segunda entrada del mismo táctil. Cualquier otro prefijo observado solo se
    avisa en el log (lo más seguro: no copiar formatos de origen dudoso, p. ej.
    de un lápiz u otro digitalizador)."""
    tocados = {normalizar_ruta(h).lower() for h in hids_tocados or ()}
    prefijos, todos_bien, alguno_tocado = set(), True, False
    for nombre, valor in (existentes or {}).items():
        dato = valor[0] if isinstance(valor, (tuple, list)) else valor
        m = _RE_PREFIJO.match(nombre or "")
        hid = nombre[len(m.group(1)):] if m else ""
        if not m or not es_ruta_hid(hid) or not isinstance(dato, str) or not es_ruta_monitor(dato):
            todos_bien = False
            if m:
                prefijos.add(m.group(1))
            continue
        prefijos.add(m.group(1))
        if hid.lower() in tocados:
            alguno_tocado = True
    otros = sorted(prefijos - {PREFIJO_POR_DEFECTO})
    if todos_bien and len(prefijos) == 1 and otros and alguno_tocado:
        return otros[0], (f"se usa el prefijo {otros[0]} que Windows ya dejó en Digimon para estas "
                          "mismas pantallas táctiles")
    if otros:
        return PREFIJO_POR_DEFECTO, (f"Digimon ya tiene valores con prefijo {', '.join(otros)}: "
                                     f"se escribe igual con {PREFIJO_POR_DEFECTO}")
    return PREFIJO_POR_DEFECTO, None


@dataclass
class Armado:
    valores: dict = field(default_factory=dict)      # nombre del valor → dato (REG_SZ)
    rechazos: list = field(default_factory=list)     # mensajes de pares descartados


def armar_valores(pares, prefijo: str = PREFIJO_POR_DEFECTO) -> Armado:
    """Arma los valores Digimon a partir de los toques: `pares` es una lista
    de (ruta_hid_del_digitalizador, ruta_interfaz_del_monitor), en el orden en
    que se tocaron las pantallas. Función pura.

    Reglas: normaliza (normalizar_ruta); rechaza rutas mal formadas; un
    digitalizador por monitor y un monitor por digitalizador (el primer toque
    manda, los repetidos se rechazan); sin duplicados (comparación sin
    distinguir mayúsculas)."""
    if not re.fullmatch(r"\d+-", prefijo or ""):
        raise ValueError(f"prefijo inválido: {prefijo!r}")
    armado = Armado()
    hids_usados, monitores_usados = set(), set()
    for i, par in enumerate(pares or (), start=1):
        try:
            hid, monitor = par
        except (TypeError, ValueError):
            armado.rechazos.append(f"toque {i}: par mal formado")
            continue
        hid, monitor = normalizar_ruta(hid), normalizar_ruta(monitor)
        if not es_ruta_hid(hid):
            armado.rechazos.append(f"toque {i}: ruta de digitalizador mal formada: {hid!r}")
            continue
        if not es_ruta_monitor(monitor):
            armado.rechazos.append(f"toque {i}: ruta de monitor mal formada: {monitor!r}")
            continue
        if hid.lower() in hids_usados:
            armado.rechazos.append(f"toque {i}: el digitalizador ya quedó asociado a otro monitor: {hid}")
            continue
        if monitor.lower() in monitores_usados:
            armado.rechazos.append(f"toque {i}: el monitor ya tiene un digitalizador asociado: {monitor}")
            continue
        hids_usados.add(hid.lower())
        monitores_usados.add(monitor.lower())
        armado.valores[prefijo + hid] = monitor
    return armado


def conflictos(valores: dict, existentes: dict) -> list:
    """Avisos (solo para el log) de valores que ya estaban y apuntan al mismo
    monitor desde OTRO digitalizador. No se borran: el inverso del paso 6 solo
    restaura valores existentes, así que borrar uno no se podría deshacer."""
    avisos = []
    nuevos = {n.lower() for n in valores}
    for nombre, (dato, _tipo) in (existentes or {}).items():
        if nombre.lower() in nuevos or not isinstance(dato, str):
            continue
        for nuevo_nombre, monitor in valores.items():
            if dato.lower() == monitor.lower():
                avisos.append(f"{nombre} también apunta a {monitor} (queda como estaba)")
    return avisos


# ── respaldo ────────────────────────────────────────────────────────────────

def _a_json(valor, tipo: str):
    if tipo == "Binary" and isinstance(valor, (bytes, bytearray)):
        return list(valor)
    if tipo == "MultiString" and isinstance(valor, (list, tuple)):
        return [str(v) for v in valor]
    return valor


def contenido_respaldo(existentes: dict, existia: bool) -> dict:
    """{"DigimonAntes": {...}, "DigimonExistia": bool} con el formato del script."""
    antes = {nombre: {"Valor": _a_json(valor, tipo), "Tipo": tipo}
             for nombre, (valor, tipo) in (existentes or {}).items()}
    return {"DigimonAntes": antes, "DigimonExistia": bool(existia)}


def asegurar_respaldo(ruta: str, escritor) -> bool:
    """Crea el respaldo si aún no tiene DigimonAntes. True si lo escribió,
    False si ya existía (no se pisa). Lanza OSError/ValueError si no puede
    leerlo o escribirlo: en ese caso NO se debe tocar el registro."""
    datos = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8-sig") as f:
            texto = f.read()
        if texto.strip():
            datos = json.loads(texto)
            if not isinstance(datos, dict):
                raise ValueError(f"respaldo con formato inesperado: {ruta}")
    if "DigimonAntes" in datos:
        return False
    datos.update(contenido_respaldo(escritor.leer(), escritor.existe()))
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)
    return True


# ── escritura en el registro (vista de 64 bits) ─────────────────────────────

class EscritorRegistro:
    """Lee y escribe HKLM\\SOFTWARE\\Microsoft\\Wisp\\Pen\\Digimon en la vista de
    64 bits (KEY_WOW64_64KEY). Solo crea o reemplaza valores REG_SZ; nunca
    borra. Nunca se usa en las pruebas (se inyecta un doble)."""

    def __init__(self):
        import winreg
        self._w = winreg

    def existe(self) -> bool:
        w = self._w
        try:
            with w.OpenKey(w.HKEY_LOCAL_MACHINE, RUTA_DIGIMON, 0, w.KEY_READ | w.KEY_WOW64_64KEY):
                return True
        except FileNotFoundError:
            return False

    def leer(self) -> dict:
        w = self._w
        salida = {}
        try:
            with w.OpenKey(w.HKEY_LOCAL_MACHINE, RUTA_DIGIMON, 0, w.KEY_READ | w.KEY_WOW64_64KEY) as k:
                i = 0
                while True:
                    try:
                        nombre, valor, tipo = w.EnumValue(k, i)
                    except OSError:
                        break
                    salida[nombre] = (valor, _TIPOS.get(tipo, "String"))
                    i += 1
        except FileNotFoundError:
            pass
        return salida

    def escribir(self, nombre: str, dato: str) -> None:
        w = self._w
        with w.CreateKeyEx(w.HKEY_LOCAL_MACHINE, RUTA_DIGIMON, 0,
                           w.KEY_SET_VALUE | w.KEY_QUERY_VALUE | w.KEY_WOW64_64KEY) as k:
            w.SetValueEx(k, nombre, 0, w.REG_SZ, dato)
