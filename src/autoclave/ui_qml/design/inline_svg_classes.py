# ui_qml/design/inline_svg_classes.py
#
# El renderizador SVG de Qt (SVG Tiny 1.2) no resuelve <style>/clases CSS
# (hallazgo UI-06 del plan de interfaz dual-pantalla). Los SVG exportados
# de CorelDRAW declaran fill como clase (class="fil0") en vez de atributo
# directo — sin inlinar, Qt carga el archivo sin error pero no dibuja
# nada. Uso: python -m autoclave.ui_qml.design.inline_svg_classes <archivo>

import re
import sys
from pathlib import Path

_STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL)
_REGLA_RE = re.compile(r"\.([\w-]+)\s*\{([^}]*)\}")
_CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')


def resolver_clases_estilo(svg: str) -> str:
    estilos = {}
    m = _STYLE_RE.search(svg)
    if m:
        for clase, cuerpo in _REGLA_RE.findall(m.group(1)):
            declaraciones = {}
            for decl in cuerpo.split(";"):
                if ":" not in decl:
                    continue
                prop, _, valor = decl.partition(":")
                declaraciones[prop.strip()] = valor.strip()
            estilos[clase] = declaraciones
        svg = svg[: m.start()] + svg[m.end() :]

    def _reemplazar(match: re.Match) -> str:
        clases = match.group(1).split()
        return " ".join(
            f'{prop}="{valor}"'
            for clase in clases
            for prop, valor in estilos.get(clase, {}).items()
        )

    return _CLASS_ATTR_RE.sub(_reemplazar, svg)


def main() -> None:
    origen = Path(sys.argv[1])
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else origen
    destino.write_text(resolver_clases_estilo(origen.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Generado {destino} desde {origen}")


if __name__ == "__main__":
    sys.exit(main())
