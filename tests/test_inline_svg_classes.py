# tests/test_inline_svg_classes.py
#
# El renderizador SVG de Qt implementa SVG Tiny 1.2 y no resuelve
# <style>/clases CSS (hallazgo UI-06 del plan de interfaz dual-pantalla,
# ya conocido para currentColor). Los logos exportados de CorelDRAW traen
# fill:black declarado como clase CSS (class="fil0") en vez de atributo
# fill directo — sin inlinar, el SVG se carga sin error pero no dibuja
# nada. Esta función resuelve las clases a atributos directos.

from autoclave.ui_qml.design.inline_svg_classes import resolver_clases_estilo


def test_inlinea_fill_de_una_clase_simple():
    svg = (
        '<svg><defs><style>.fil0 {fill:black}</style></defs>'
        '<path class="fil0" d="M0 0"/></svg>'
    )
    assert 'class="fil0"' not in resolver_clases_estilo(svg)
    assert 'fill="black"' in resolver_clases_estilo(svg)


def test_elimina_el_bloque_style():
    svg = '<svg><style>.fil0 {fill:black}</style><path class="fil0" d="M0 0"/></svg>'
    assert "<style>" not in resolver_clases_estilo(svg)


def test_conserva_elementos_sin_class():
    svg = '<svg><style>.fil0 {fill:black}</style><path d="M0 0"/></svg>'
    assert '<path d="M0 0"/>' in resolver_clases_estilo(svg)


def test_inlinea_fill_rule_ademas_de_fill():
    svg = (
        '<svg><style>.fil0 {fill:black;fill-rule:nonzero}</style>'
        '<path class="fil0" d="M0 0"/></svg>'
    )
    resultado = resolver_clases_estilo(svg)
    assert 'fill="black"' in resultado
    assert 'fill-rule="nonzero"' in resultado


def test_maneja_varias_clases_distintas():
    svg = (
        '<svg><style>.fil0 {fill:black} .fil1 {fill:none}</style>'
        '<path class="fil0" d="M0 0"/>'
        '<path class="fil1" d="M1 1"/></svg>'
    )
    resultado = resolver_clases_estilo(svg)
    assert 'fill="black"' in resultado
    assert 'fill="none"' in resultado
