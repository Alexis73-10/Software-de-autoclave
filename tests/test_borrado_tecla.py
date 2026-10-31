# tests/test_borrado_tecla.py
#
# Temporización pura de la tecla Borrar, compartida por los dos teclados
# (TEC-D12 y §7 de planeacion_teclados_qml.md): toque corto -> un carácter al
# soltar; mantenida 600 ms -> todo el campo, una sola vez, sin además borrar
# un carácter al soltar. Marcas de tiempo monotónicas inyectadas.

from autoclave.ui_qml.domain.borrado_tecla import (
    UMBRAL_BORRADO_TOTAL_S,
    AccionBorrado,
    al_cumplir_umbral,
    al_soltar,
)


def test_umbral_es_600_ms():
    assert UMBRAL_BORRADO_TOTAL_S == 0.6


# ── al_soltar ────────────────────────────────────────────────────────────

def test_toque_corto_borra_un_caracter():
    assert al_soltar(t_presion=10.0, t_soltar=10.2, total_disparado=False) == AccionBorrado.UN_CARACTER


def test_soltar_justo_antes_del_umbral_borra_un_caracter():
    assert al_soltar(10.0, 10.599, total_disparado=False) == AccionBorrado.UN_CARACTER


def test_soltar_tras_borrado_total_no_borra_ademas_un_caracter():
    assert al_soltar(10.0, 11.5, total_disparado=True) == AccionBorrado.NINGUNA


def test_soltar_pasado_el_umbral_sin_disparo_previo_borra_todo():
    # Si el aviso del umbral llegó tarde (o no llegó), la duración manda:
    # una pulsación de 600 ms o más nunca se interpreta como toque corto.
    assert al_soltar(10.0, 10.6, total_disparado=False) == AccionBorrado.TODO


# ── al_cumplir_umbral ────────────────────────────────────────────────────

def test_al_cumplir_600_ms_borra_todo():
    assert al_cumplir_umbral(10.0, 10.6, total_disparado=False) == AccionBorrado.TODO


def test_aviso_anticipado_no_borra_nada():
    # Un temporizador que dispare antes de tiempo no debe vaciar el campo.
    assert al_cumplir_umbral(10.0, 10.5, total_disparado=False) == AccionBorrado.NINGUNA


def test_borrado_total_una_sola_vez():
    assert al_cumplir_umbral(10.0, 12.0, total_disparado=True) == AccionBorrado.NINGUNA
