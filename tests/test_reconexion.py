# tests/test_reconexion.py
#
# Retroceso exponencial de reconexión del cliente WebSocket (§6.4 del plan
# de interfaz dual-pantalla): "Reintento con retroceso exponencial 1, 2,
# 4, 8, máximo 15 s."

import pytest

from autoclave.ui_qml.domain.reconexion import siguiente_intervalo_reintento


@pytest.mark.parametrize("intento,esperado", [
    (1, 1),
    (2, 2),
    (3, 4),
    (4, 8),
    (5, 15),   # 16 techado a 15 (§6.4)
    (6, 15),
    (100, 15),
])
def test_secuencia_de_retroceso(intento, esperado):
    assert siguiente_intervalo_reintento(intento) == esperado


def test_intento_menor_a_uno_es_invalido():
    with pytest.raises(ValueError):
        siguiente_intervalo_reintento(0)
