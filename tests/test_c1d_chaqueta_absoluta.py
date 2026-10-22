# C1d (tanda 6): el sensor de chaqueta es ABSOLUTO (decisión 1.2 de Cristian,
# 20-oct). presion_chaqueta y toda lectura de chaqueta se tratan como presión
# absoluta en U1: psig = (P_abs − P_atm) / 6,894757.

from pathlib import Path

import pytest

from autoclave.core.runtime import unidades as u
from tests.test_c1c_clase_parametros import _archivos, _parametros

# ── C1d: chaqueta absoluta (decisión 1.2) ──────────────────────────────────

def test_chaqueta_es_absoluta_en_todos_los_programas():
    vistos = 0
    for ruta in _archivos()[:-1]:
        params = _parametros(ruta)
        assert params["globals"]["presion_chaqueta"]["clase"] == "absoluto", ruta.name
        assert params["secado"]["presion_chaqueta_secado"]["clase"] == "absoluto", ruta.name
        vistos += 1
    assert vistos >= 8


def test_chaqueta_en_psig_resta_la_atmosferica_una_sola_vez():
    """psig = (P_abs − P_atm) / 6,894757 (decisión 1.2: sensor ABSOLUTO)."""
    p_atm = 75.0
    clase = u.clase_de_unidad("kPa", "presion_chaqueta", "absoluto")
    assert clase == "pres"
    valor, unidad = u.pres_a_mostrar(300.0, "psi", p_atm)
    assert unidad == "psig"
    assert valor == pytest.approx((300.0 - p_atm) / 6.894757)
    assert u.pres_a_interna(valor, "psig", p_atm) == pytest.approx(300.0)


def test_lectura_viva_de_chaqueta_se_formatea_como_absoluta():
    from autoclave.ui_qml.bridge.unidades_qml import UnidadesQml
    un = UnidadesQml(sondear=False, consultar=lambda: None)
    un._aplicar({"temperatura": "C", "presion": "psi", "p_atm": 75.0})
    assert un.pres(300.0) == u.formatear_pres(300.0, "psi", 75.0)
    assert un.parametro(300.0, "kPa", "presion_chaqueta", "absoluto") == un.pres(300.0)
