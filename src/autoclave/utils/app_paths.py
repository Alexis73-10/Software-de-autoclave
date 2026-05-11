from pathlib import Path
import os

def get_data_dir():
    """
    Devuelve la carpeta de datos persistentes del sistema.
    En Windows: C:\\ProgramData\\Autoclave
    """
    base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    data_dir = base / "Autoclave"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
