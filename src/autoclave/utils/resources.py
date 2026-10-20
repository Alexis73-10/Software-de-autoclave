import sys
import os
import shutil

# Carpetas que el programa también ESCRIBE (parámetros globales, ciclos de
# usuario, correo, enlace serial). En un build congelado de un solo archivo
# (onefile), _MEIPASS es una carpeta temporal que se borra al cerrar: lo que se
# guardara ahí se perdería. En ese caso se usa una copia junto al .exe, en
# <carpeta del exe>/programa/autoclave/..., sembrada desde el paquete.
_ESCRIBIBLES = ("autoclave/config", "autoclave/cycles")
# Siempre se refrescan desde el paquete: son de fábrica, el programa no las
# edita, y así un build nuevo trae sus valores
_SOLO_FABRICA = ("autoclave/cycles/factory",)
_sembradas = set()


def raiz_datos_exe() -> str:
    """Carpeta de datos escribibles de un build congelado (la usa también
    utils/paths.app_root). Instalado en Archivos de programa (solo lectura sin
    administrador) es %ProgramData%\\Especifika\\Autoclave; en cualquier otro
    lugar (copia portátil), la carpeta del .exe."""
    carpeta_exe = os.path.dirname(os.path.abspath(sys.executable))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base and os.path.normcase(carpeta_exe).startswith(os.path.normcase(base) + os.sep):
            return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                                "Especifika", "Autoclave")
    return carpeta_exe


def _carpeta_persistente() -> str:
    return os.path.join(raiz_datos_exe(), "programa")


def _copiar(origen: str, destino: str) -> None:
    # copia a un temporal y renombra: varios procesos (backend y pantallas)
    # pueden sembrar a la vez
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    temporal = f"{destino}.{os.getpid()}.tmp"
    shutil.copy2(origen, temporal)
    os.replace(temporal, destino)


def _sembrar(prefijo: str) -> None:
    if prefijo in _sembradas:
        return
    _sembradas.add(prefijo)
    origen_raiz = os.path.join(sys._MEIPASS, prefijo)
    destino_raiz = os.path.join(_carpeta_persistente(), prefijo)
    for carpeta, _, archivos in os.walk(origen_raiz):
        relativa = os.path.relpath(carpeta, origen_raiz)
        if "__pycache__" in relativa:
            continue
        for nombre in archivos:
            origen = os.path.join(carpeta, nombre)
            destino = os.path.normpath(os.path.join(destino_raiz, relativa, nombre))
            de_fabrica = any(f"{prefijo}/{relativa}".replace("\\", "/").startswith(f)
                             for f in _SOLO_FABRICA)
            if de_fabrica or not os.path.exists(destino):
                try:
                    _copiar(origen, destino)
                except OSError:
                    pass   # otro proceso lo está copiando; se usa el que quede


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        # .exe
        normalizada = relative_path.replace("\\", "/")
        for prefijo in _ESCRIBIBLES:
            if normalizada == prefijo or normalizada.startswith(prefijo + "/"):
                _sembrar(prefijo)
                return os.path.join(_carpeta_persistente(), relative_path)
        base_path = sys._MEIPASS
    else:
        # desarrollo → raíz del proyecto
        base_path = os.path.abspath("src")

    return os.path.join(base_path, relative_path)
