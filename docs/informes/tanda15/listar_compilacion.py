"""Lista determinista de una compilación PyInstaller (tanda 15, A0/ORG-07/K).

Uso: python listar_compilacion.py <clon> <nombre_spec_sin_extension> <salida.txt>

Escribe dos secciones ordenadas:
- ``## dist``: archivos bajo ``dist/<nombre>/`` (o ``dist/<nombre>.exe`` si es onefile),
  ruta relativa a ``dist/`` con ``/``, sin tamaño;
- ``## pyz``: nombres de módulo de ``build/<nombre>/PYZ-00.toc``.
"""
import ast
import os
import sys


def main(clon: str, nombre: str, salida: str) -> None:
    dist = os.path.join(clon, "dist")
    archivos = []
    carpeta = os.path.join(dist, nombre)
    if os.path.isdir(carpeta):
        for raiz, _dirs, files in os.walk(carpeta):
            for f in files:
                rel = os.path.relpath(os.path.join(raiz, f), dist)
                archivos.append(rel.replace(os.sep, "/"))
    exe = os.path.join(dist, nombre + ".exe")
    if os.path.isfile(exe):
        archivos.append(nombre + ".exe")
    archivos.sort()

    toc = os.path.join(clon, "build", nombre, "PYZ-00.toc")
    with open(toc, encoding="utf-8") as fh:
        datos = ast.literal_eval(fh.read())
    modulos = sorted({e[0] for e in datos[1]})

    with open(salida, "w", encoding="utf-8", newline="\n") as out:
        out.write(f"# {nombre}: {len(archivos)} archivos en dist, {len(modulos)} módulos en PYZ\n")
        out.write("## dist\n")
        out.writelines(a + "\n" for a in archivos)
        out.write("## pyz\n")
        out.writelines(m + "\n" for m in modulos)


if __name__ == "__main__":
    main(*sys.argv[1:4])
