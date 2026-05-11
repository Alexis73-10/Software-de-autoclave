import sys
import os

def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        # .exe
        base_path = sys._MEIPASS
    else:
        # desarrollo → raíz del proyecto
        base_path = os.path.abspath("src")

    return os.path.join(base_path, relative_path)

