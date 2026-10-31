"""Tanda 12, C-09: el tope de calidad de vapor es T >= T_obj - 3 K
(_MARGEN_CALIDAD_VAPOR_K), no el 97 % de T_obj."""
from autoclave.state_machine.cycle_phases import calentamiento as cal


def test_constante_y_sin_factor_porcentual():
    assert cal._MARGEN_CALIDAD_VAPOR_K == 3.0
    assert not hasattr(cal, "_FACTOR_TOPE_TEMPERATURA")


def test_corte_con_121_empieza_en_118_y_no_en_117_37():
    # presión muy baja: corta solo si el tope ya está activo
    assert cal._duty_por_calidad_vapor(temp=117.5, pres=1.0, t_obj=121.0) == 1.0
    assert cal._duty_por_calidad_vapor(temp=117.99, pres=1.0, t_obj=121.0) == 1.0
    assert cal._duty_por_calidad_vapor(temp=118.0, pres=1.0, t_obj=121.0) == 0.0


def test_corte_con_134_empieza_en_131():
    assert cal._duty_por_calidad_vapor(temp=130.99, pres=1.0, t_obj=134.0) == 1.0
    assert cal._duty_por_calidad_vapor(temp=131.0, pres=1.0, t_obj=134.0) == 0.0
