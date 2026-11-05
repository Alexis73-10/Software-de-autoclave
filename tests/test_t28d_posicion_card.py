"""Tanda 28 (A11): posición de la card del cursor de la gráfica (función pura)."""
import pytest

from autoclave.ui_qml.domain.posicion_card import _largo_cruce, _limpiar, posicionar_card

AREA = (68.0, 279.0, 1059.0, 709.0)
W, H = 220.0, 145.0
RES = 17.0


def _curva(y, x0=68.0, x1=1059.0, n=50):
    return [{"x": x0 + (x1 - x0) * i / (n - 1), "y": y} for i in range(n)]


def _pos(cx, curvas):
    return posicionar_card(AREA, cx, W, H, curvas, RES)


def _caja(r):
    return r["x"], r["y"], r["x"] + W, r["y"] + H


def _comun(r, cx, curvas):
    x0, y0, x1, y1 = _caja(r)
    assert x0 >= AREA[0] - 1e-6 and x1 <= AREA[2] + 1e-6
    assert y0 >= AREA[1] - 1e-6 and y1 <= AREA[3] + 1e-6
    # no tapa el cursor: entera a un costado
    assert x1 <= cx - RES + 1e-6 or x0 >= cx + RES - 1e-6
    if r["libre"]:
        assert _largo_cruce(_limpiar(curvas), x0, x1, y0, y1) == 0.0


def test_curvas_altas_va_abajo():
    cv = [_curva(300.0), _curva(330.0)]
    r = _pos(500.0, cv)
    _comun(r, 500.0, cv)
    assert r["libre"] and r["franja"] == "inferior"


def test_curvas_bajas_va_arriba():
    cv = [_curva(690.0), _curva(650.0)]
    r = _pos(500.0, cv)
    _comun(r, 500.0, cv)
    assert r["libre"] and r["franja"] == "superior"


def test_curvas_cruzadas_busca_hueco():
    sube = [{"x": 68.0 + i * 20.0, "y": 700.0 - i * 8.0} for i in range(50)]
    baja = [{"x": 68.0 + i * 20.0, "y": 290.0 + i * 8.0} for i in range(50)]
    for cx in (150.0, 560.0, 1000.0):
        r = _pos(cx, [sube, baja])
        _comun(r, cx, [sube, baja])


def test_curvas_en_todo_el_alto_elige_el_lado_menos_cruzado_y_no_es_libre():
    # una curva vertical a cada lado deja sin hueco a los dos costados
    cv = [[{"x": 400.0 + i * 5, "y": 279.0 + 430.0 * (i % 2)} for i in range(120)]]
    r = _pos(560.0, cv)
    assert r["libre"] is False
    _comun(r, 560.0, cv)


def test_cerca_del_borde_derecho_va_a_la_izquierda():
    cv = [_curva(500.0, 68.0, 1059.0)]
    r = _pos(1050.0, cv)
    _comun(r, 1050.0, cv)
    assert r["lado"] == "izquierda"


def test_cerca_del_borde_izquierdo_va_a_la_derecha():
    r = _pos(70.0, [_curva(500.0)])
    _comun(r, 70.0, [_curva(500.0)])
    assert r["lado"] == "derecha"


def test_sin_curvas_y_datos_invalidos():
    for cv in ([], [[]], [[{"x": float("nan"), "y": 1.0}, {"x": 5.0, "y": None}]]):
        r = _pos(500.0, cv)
        _comun(r, 500.0, cv)
        assert r["libre"]


def test_cursor_fuera_del_area_se_acota():
    for cx in (-50.0, 5000.0, float("nan")):
        r = posicionar_card(AREA, cx, W, H, [], RES)
        x0, _, x1, _ = _caja(r)
        assert x0 >= AREA[0] and x1 <= AREA[2]


def test_segmento_largo_entre_dos_lecturas_cuenta():
    # un único tramo largo que atraviesa la franja superior
    cv = [[{"x": 100.0, "y": 300.0}, {"x": 1000.0, "y": 300.0}]]
    r = _pos(500.0, cv)
    assert r["libre"] and r["franja"] == "inferior"


@pytest.mark.parametrize("cx", [68.0, 200.0, 500.0, 900.0, 1059.0])
def test_siempre_dentro_del_area(cx):
    cv = [_curva(300.0 + (cx % 300)), _curva(650.0)]
    _comun(_pos(cx, cv), cx, cv)


def test_area_invalida_no_da_nan():
    r = posicionar_card((float("nan"), 0, 100, 100), 50, W, H, [], RES)
    assert r["libre"] is False and r["x"] == r["x"] and r["y"] == r["y"]


def test_curva_pegada_a_la_card_cuenta_por_el_margen():
    # curva a 1 px del borde inferior de la card en la franja superior
    cv = [_curva(279.0 + H + 1.0)]
    r = _pos(500.0, cv)
    assert r["libre"] and not (r["franja"] == "superior")
