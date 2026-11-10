# tests/test_hor_e_contraste.py
#
# Tanda horizontal, ronda 2, grupo E: contraste WCAG en modo oscuro de los
# pares de texto e ícono de los modales, paneles y teclados (los mismos en
# horizontal que en vertical; la ronda 2 no cambió ninguno). 4,5:1 para texto
# normal y 3:1 para texto grande y elementos gráficos (§8 de la paleta).

import pytest

from tests.test_tema_oscuro import _colores, _contraste

_PARES = [
    # (texto/ícono, fondo, mínimo, dónde)
    ("textoPrimario", "fondoTarjeta", 4.5, "títulos, cuerpos y valores de modales y teclados"),
    ("textoSecundario", "fondoTarjeta", 4.5, "título del teclado, rótulos de PanelEquipo"),
    ("textoGuia", "fondoTarjeta", 3.0, "ícono de ocultar teclado, rótulos del detalle de alarma (20 px)"),
    ("advertenciaTexto", "advertenciaFondo", 4.5, "nota de ModalConfirmacion / ModalOperador"),
    ("advertencia", "fondoTarjeta", 3.0, "borde de la nota"),
    ("textoSobreAccion", "accionPrimario", 3.0, "botón Cerrar / acción (texto grande: 26 px SemiBold)"),
    ("textoSobreAccion", "peligroFuerte", 4.5, "botón Apagar equipo"),
    ("textoPrimario", "seleccionSutil", 4.5, "operador elegido"),
    ("textoPrimario", "fondoSutil", 4.5, "fila de operador"),
    ("peligroTexto", "peligroFondo", 4.5, "tecla CANCELAR"),
    ("advertenciaTexto", "advertenciaFondo", 4.5, "tecla BORRAR"),
]


@pytest.mark.parametrize("texto,fondo,minimo,donde", _PARES)
def test_pares_del_grupo_e_en_oscuro(texto, fondo, minimo, donde):
    c = _colores()
    r = _contraste(c[texto][1], c[fondo][1])
    assert r >= minimo, f"{donde}: {texto} sobre {fondo} = {r:.2f}"
