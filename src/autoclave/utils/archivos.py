# utils/archivos.py
#
# Escritura atómica de archivos de estado (A2, tanda 3). El equipo no tiene
# UPS: un corte de energía puede llegar a mitad de una escritura, y un archivo
# a medio escribir (calibración, contador, latido, PID) no debe quedar como el
# único valor. Se escribe en un temporal del mismo directorio, se fuerza a
# disco (fsync) y se reemplaza con os.replace (atómico en NTFS y POSIX).

import os
from pathlib import Path


def escribir_texto_atomico(ruta: Path | str, texto: str, encoding: str = "utf-8",
                           respaldo: bool = False) -> None:
    """Escribe `texto` en `ruta` de forma atómica. Con `respaldo=True`, antes
    de reemplazar deja una copia del archivo previo en `<ruta>.bak`. Un fallo
    deja el archivo original intacto y no deja temporales."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    try:
        with open(tmp, "w", encoding=encoding, newline="") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        if respaldo and ruta.exists():
            # copia (no renombre): la ruta original nunca queda ausente
            bak = ruta.with_name(ruta.name + ".bak")
            bak_tmp = bak.with_name(bak.name + ".tmp")
            bak_tmp.write_bytes(ruta.read_bytes())
            os.replace(bak_tmp, bak)
        os.replace(tmp, ruta)
    finally:
        tmp.unlink(missing_ok=True)
