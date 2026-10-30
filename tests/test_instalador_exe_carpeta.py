"""Instalador del build en carpeta (onedir): copia Autoclave.exe y _internal a
la carpeta de instalación sin mezclar versiones ni arrastrar otros archivos."""

import os

from autoclave.instalador_exe import _copiar_programa


def _programa(carpeta, version):
    os.makedirs(os.path.join(carpeta, "_internal"), exist_ok=True)
    with open(os.path.join(carpeta, "Autoclave.exe"), "w") as f:
        f.write(version)
    with open(os.path.join(carpeta, "_internal", version + ".dll"), "w") as f:
        f.write(version)


def test_instala_solo_el_programa(tmp_path):
    usb = tmp_path / "usb"
    _programa(str(usb), "v1")
    (usb / "fotos.jpg").write_text("x")
    destino = str(tmp_path / "ProgramFiles" / "Autoclave")
    os.makedirs(os.path.dirname(destino))
    _copiar_programa(str(usb), destino)
    assert sorted(os.listdir(destino)) == ["Autoclave.exe", "_internal"]


def test_actualiza_sin_dejar_archivos_viejos(tmp_path):
    destino = str(tmp_path / "Autoclave")
    _programa(destino, "v1")
    origen = tmp_path / "v2"
    _programa(str(origen), "v2")
    _copiar_programa(str(origen), destino)
    assert open(os.path.join(destino, "Autoclave.exe")).read() == "v2"
    assert os.listdir(os.path.join(destino, "_internal")) == ["v2.dll"]
    assert not os.path.exists(destino + ".viejo") and not os.path.exists(destino + ".nuevo")
