# tests/test_estado_autoclave_f0.py
from autoclave.core.runtime.status import EstadoAutoclave


def test_f0_acumulado_inicia_en_cero():
    estado = EstadoAutoclave()
    assert estado.f0_acumulado == 0.0
