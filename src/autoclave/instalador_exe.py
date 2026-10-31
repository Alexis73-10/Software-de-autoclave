# autoclave/instalador_exe.py
#
# Instalación de Autoclave desde una USB u otra carpeta:
#   - la carpeta del programa (Autoclave.exe y _internal\, build "onedir": sin
#     descompresión en cada apertura, que tardaba ~10 s) se copia a
#     %ProgramFiles%\Especifika\Autoclave
#   - los datos (perfil de instalación, base de datos, logs, parámetros y
#     ciclos editables) quedan en %ProgramData%\Especifika\Autoclave, con
#     permiso de modificación para Usuarios: Archivos de programa es de solo
#     lectura sin administrador y el programa escribe ahí a diario
#   - accesos directos en el Escritorio público y en el menú Inicio
#
# La copia se hace en un proceso elevado (UAC) con `--rol instalar`; el proceso
# original (sin elevar) espera y luego abre la copia instalada, así el
# programa no queda corriendo como administrador. Nada se escribe en la USB.
# Volver a instalar sobre una copia existente la actualiza (los datos se
# conservan); si la copia instalada está abierta, la copia falla y se avisa.
#
# Tanda 17 (INS-02): el Setup (tools/instalador/autoclave.iss) instala en
# X:\Especifika\Autoclave\{programa,datos} y anota RutaPrograma/RutaDatos en el
# registro; esta_instalado_aqui() reconoce también esa copia. El resto de este
# instalador (copia a Archivos de programa) no cambia: es la disposición
# anterior, que el Setup nuevo rechaza (pide desinstalarla).

import ctypes
import os
import shutil
import subprocess
import sys

from autoclave.utils import resources

TITULO = "Autoclave — Especifika"
# Usuarios (BUILTIN\Users) por SID: el nombre cambia con el idioma de Windows
_SID_USUARIOS = "*S-1-5-32-545"


def carpeta_instalacion() -> str:
    return os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Especifika", "Autoclave")


def exe_instalado() -> str:
    return os.path.join(carpeta_instalacion(), "Autoclave.exe")


def carpeta_datos() -> str:
    return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Especifika", "Autoclave")


def esta_instalado_aqui() -> bool:
    """True si este proceso corre desde la copia instalada: la de este
    instalador (%ProgramFiles%\\Especifika\\Autoclave) o, desde la tanda 17
    (INS-02), la del Setup, cuya carpeta anota `RutaPrograma` en
    HKLM\\SOFTWARE\\Especifika\\Autoclave (X:\\Especifika\\Autoclave\\programa).
    Sin esto, el programa instalado por el Setup volvería a ofrecer instalarse."""
    if os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(exe_instalado()):
        return True
    registro = resources._leer_registro_instalacion()
    return registro is not None and resources._misma_carpeta(
        registro[0], os.path.dirname(os.path.abspath(sys.executable)))


def _mensaje(texto: str, estilo: int) -> int:
    return ctypes.windll.user32.MessageBoxW(None, texto, TITULO, estilo | 0x40000)   # MB_TOPMOST


def preguntar(texto: str) -> bool:
    return _mensaje(texto, 0x04 | 0x20) == 6   # MB_YESNO | MB_ICONQUESTION → IDYES


def avisar(texto: str, error: bool = False) -> None:
    _mensaje(texto, 0x10 if error else 0x40)   # MB_ICONERROR / MB_ICONINFORMATION


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong), ("fMask", ctypes.c_ulong), ("hwnd", ctypes.c_void_p),
        ("lpVerb", ctypes.c_wchar_p), ("lpFile", ctypes.c_wchar_p),
        ("lpParameters", ctypes.c_wchar_p), ("lpDirectory", ctypes.c_wchar_p),
        ("nShow", ctypes.c_int), ("hInstApp", ctypes.c_void_p), ("lpIDList", ctypes.c_void_p),
        ("lpClass", ctypes.c_wchar_p), ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", ctypes.c_ulong), ("hIconOrMonitor", ctypes.c_void_p),
        ("hProcess", ctypes.c_void_p),
    ]


def _ejecutar_elevado(exe: str, parametros: str) -> int | None:
    """Lanza `exe` como administrador (UAC) y espera. None si se canceló."""
    # si el hijo heredara el entorno de PyInstaller de este proceso, intentaría
    # reutilizar su carpeta de extracción
    os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040   # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = exe
    info.lpParameters = parametros
    info.nShow = 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return None   # UAC rechazado
    kernel32 = ctypes.windll.kernel32
    kernel32.WaitForSingleObject(ctypes.c_void_p(info.hProcess), 0xFFFFFFFF)
    codigo = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(ctypes.c_void_p(info.hProcess), ctypes.byref(codigo))
    kernel32.CloseHandle(ctypes.c_void_p(info.hProcess))
    return codigo.value


def _acceso_directo(ruta_lnk: str, destino: str) -> None:
    os.makedirs(os.path.dirname(ruta_lnk), exist_ok=True)
    script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
              "$s.TargetPath=$env:DESTINO;$s.WorkingDirectory=$env:CARPETA;$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   env={**os.environ, "LNK": ruta_lnk, "DESTINO": destino,
                        "CARPETA": os.path.dirname(destino)},
                   capture_output=True, timeout=30, check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def _copiar_programa(origen: str, destino: str) -> None:
    """Copia la carpeta del programa: primero a `<destino>.nuevo`, luego cambia
    la vieja por la nueva (sin mezclar archivos de dos versiones). Falla si la
    copia instalada está abierta."""
    nuevo, viejo = destino + ".nuevo", destino + ".viejo"
    for resto in (nuevo, viejo):
        if os.path.isdir(resto):
            shutil.rmtree(resto)
    # solo el programa, no lo que haya junto a él (p. ej. la raíz de la USB)
    shutil.copytree(os.path.join(origen, "_internal"), os.path.join(nuevo, "_internal"))
    shutil.copy2(os.path.join(origen, "Autoclave.exe"), os.path.join(nuevo, "Autoclave.exe"))
    if os.path.isdir(destino):
        os.replace(destino, viejo)
    try:
        os.replace(nuevo, destino)
    except OSError:
        if os.path.isdir(viejo):
            os.replace(viejo, destino)   # deja la versión anterior
        raise
    shutil.rmtree(viejo, ignore_errors=True)


def instalacion_con_setup() -> str | None:
    """R1 (V17-s1-03): carpeta `RutaPrograma` si el equipo tiene una
    instalación del Setup (disposición X:\\Especifika\\Autoclave, tanda 17,
    INS-02) y este proceso NO corre desde ella; None si no. Con una instalación
    así, este instalador no debe crear la disposición anterior en Archivos de
    programa: el equipo se actualiza con el Setup."""
    registro = resources._leer_registro_instalacion()
    if registro is None:
        return None
    if resources._misma_carpeta(registro[0], os.path.dirname(os.path.abspath(sys.executable))):
        return None
    return registro[0]


def _aviso_usar_setup(ruta_programa: str) -> str:
    # mensaje fijo bilingüe: este módulo corre antes de cargar el idioma
    return ("Este equipo ya tiene Autoclave instalado con el instalador (Setup) en:\n"
            f"{ruta_programa}\n\n"
            "Para actualizarlo, ejecute Autoclave_Setup_<versión>.exe como administrador. "
            "No se instaló ni se cambió nada.\n\n"
            "Autoclave is already installed on this PC with the installer (Setup) in:\n"
            f"{ruta_programa}\n\n"
            "To update it, run Autoclave_Setup_<version>.exe as administrator. "
            "Nothing was installed or changed.")


def instalar() -> int:
    """Rol `--rol instalar` (ya elevado). 0 si quedó instalado."""
    instalada = instalacion_con_setup()
    if instalada is not None:
        # R1 (V17-s1-03): nunca la disposición anterior junto a la del Setup
        avisar(_aviso_usar_setup(instalada), error=True)
        return 1
    destino = exe_instalado()
    try:
        os.makedirs(os.path.dirname(carpeta_instalacion()), exist_ok=True)
        if os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(destino):
            _copiar_programa(os.path.dirname(os.path.abspath(sys.executable)),
                             carpeta_instalacion())
    except OSError as e:
        avisar("No se pudo copiar Autoclave a\n" f"{carpeta_instalacion()}\n\n"
               "Si Autoclave está abierto, ciérrelo y vuelva a intentar.\n\n" f"Detalle: {e}", error=True)
        return 1

    datos = carpeta_datos()
    os.makedirs(datos, exist_ok=True)
    subprocess.run(["icacls", datos, "/grant", f"{_SID_USUARIOS}:(OI)(CI)M", "/T", "/Q"],
                   capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)

    escritorio = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
    inicio = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                          r"Microsoft\Windows\Start Menu\Programs")
    for lnk in (os.path.join(escritorio, "Autoclave.lnk"), os.path.join(inicio, "Autoclave.lnk")):
        try:
            _acceso_directo(lnk, destino)
        except Exception:
            pass   # sin acceso directo el programa igual queda instalado
    return 0


def ofrecer_instalacion() -> bool:
    """Desde la USB (o cualquier copia fuera de Archivos de programa): pregunta,
    instala elevado y abre la copia instalada. True si este proceso debe
    terminar ahí (instalado o cancelado); nunca se sigue corriendo desde la USB.

    R1 (V17-s1-03): si el equipo tiene una instalación del Setup (registro
    RutaPrograma), no instala nada: avisa que se actualiza con el Setup y
    termina, sin abrir ni tocar la copia instalada (lo más seguro)."""
    instalada = instalacion_con_setup()
    if instalada is not None:
        avisar(_aviso_usar_setup(instalada))
        return True
    actualizar = os.path.exists(exe_instalado())
    texto = ("Ya hay un Autoclave instalado en este PC.\n\n¿Actualizarlo con esta versión?\n"
             "Los datos (perfil, ciclos, base de datos) se conservan."
             if actualizar else
             "¿Instalar Autoclave en este PC?\n\n"
             f"Programa: {carpeta_instalacion()}\nDatos: {carpeta_datos()}")
    if not preguntar(texto):
        return True
    codigo = _ejecutar_elevado(sys.executable, "--rol instalar")
    if codigo is None:
        avisar("Instalación cancelada: se necesitan permisos de administrador.", error=True)
        return True
    if codigo != 0:
        return True   # instalar() ya avisó el motivo
    entorno = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    subprocess.Popen([exe_instalado()], cwd=carpeta_instalacion(), env=entorno,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    return True
