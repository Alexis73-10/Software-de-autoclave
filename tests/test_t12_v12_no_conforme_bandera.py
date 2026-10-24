# Tanda 12, V12 (SAF-06): la marca NO CONFORME es una bandera propia de
# CicloState, puesta antes de anotar el ticket; si anotar falla, el ciclo
# sigue NO CONFORME y no usa la apertura automática.

from tests.test_t12_c13_7b_referencia_sin_lectura import _ciclo_con_ref


class _ListaRota(list):
    def append(self, _):
        raise RuntimeError("falla simulada al anotar")


def test_no_conforme_aunque_falle_el_aviso_del_ticket():
    ciclo, estado, _, _ = _ciclo_con_ref(None)
    estado.avisos_ciclo = _ListaRota()
    ciclo.run()
    assert ciclo.no_conforme is True


def test_reset_limpia_la_bandera():
    ciclo, estado, _, _ = _ciclo_con_ref(None)
    estado.avisos_ciclo = _ListaRota()
    ciclo.run()
    ciclo.reset()
    assert ciclo.no_conforme is False
