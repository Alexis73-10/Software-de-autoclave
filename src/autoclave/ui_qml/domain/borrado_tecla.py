# ui_qml/domain/borrado_tecla.py
#
# Temporización pura de la tecla Borrar, compartida por los dos teclados en
# pantalla (TEC-D12 y §7 de planeacion_teclados_qml.md): un toque corto borra
# un carácter al soltar; mantenida 600 ms borra todo el campo, una sola vez,
# y al soltar ya no borra además un carácter. Sin autorrepetición.
#
# Las marcas de tiempo las pone el llamador con time.monotonic() (CLAUDE.md:
# nunca time.time() en temporizadores), así estas funciones se prueban sin
# esperar tiempo real.

from enum import Enum

UMBRAL_BORRADO_TOTAL_S = 0.6


def _instante_umbral(t_presion: float) -> float:
    # Se compara contra t_presion + umbral y no la resta t - t_presion: la
    # resta en coma flotante da 0.5999... para 600 ms exactos.
    return t_presion + UMBRAL_BORRADO_TOTAL_S


class AccionBorrado(Enum):
    NINGUNA = "NINGUNA"
    UN_CARACTER = "UN_CARACTER"
    TODO = "TODO"


def al_cumplir_umbral(t_presion: float, t_ahora: float, total_disparado: bool) -> AccionBorrado:
    """Aviso del temporizador mientras la tecla sigue presionada. Solo borra
    todo si de verdad pasaron 600 ms y todavía no se había disparado."""
    if total_disparado or t_ahora < _instante_umbral(t_presion):
        return AccionBorrado.NINGUNA
    return AccionBorrado.TODO


def al_soltar(t_presion: float, t_soltar: float, total_disparado: bool) -> AccionBorrado:
    """Al soltar la tecla. Si el borrado total ya ocurrió, no hace nada; si la
    pulsación duró 600 ms o más sin que llegara el aviso, borra todo igual."""
    if total_disparado:
        return AccionBorrado.NINGUNA
    if t_soltar >= _instante_umbral(t_presion):
        return AccionBorrado.TODO
    return AccionBorrado.UN_CARACTER
