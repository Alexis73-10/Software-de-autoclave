import pytest
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point


def test_invert_lineal():
    # pres_camara antes de esta sesion: gain=1.3466, offset=-67.11
    fv = invert_user_calibration(12.0, gain=1.3466, offset=-67.11)
    assert fv == pytest.approx(58.747958, abs=1e-5)


def test_invert_lineal_gain_cero_lanza_valueerror():
    with pytest.raises(ValueError):
        invert_user_calibration(20.0, gain=0.0, offset=0.0)


def test_invert_poly_temp_camara():
    # poly real de temp_camara antes de esta sesion (5 puntos: 2,70,100,120,135 C)
    poly = [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
    fv_low = invert_user_calibration(20.0, poly=poly)
    fv_high = invert_user_calibration(131.3, poly=poly)
    assert fv_low == pytest.approx(18.715942, abs=1e-5)
    assert fv_high == pytest.approx(130.064013, abs=1e-5)


def test_fit_two_point_normal():
    gain, offset = fit_two_point(58.747958, 9.54, 288.957374, 300.0)
    assert gain == pytest.approx(1.261721, abs=1e-5)
    assert offset == pytest.approx(-64.583518, abs=1e-4)


def test_fit_two_point_puntos_iguales_lanza_valueerror():
    with pytest.raises(ValueError):
        fit_two_point(50.0, 10.0, 50.0, 20.0)


def test_extremo_a_extremo_temp_camara_reproduce_calibration_yaml():
    """Reproduce el calculo verificado manualmente en esta sesion para
    temp_camara: bajo 20.0->20.0, alto 131.3->132.5, reemplazando el poly
    de 5 puntos. Debe dar el gain/offset ya escrito en calibration.yaml."""
    poly = [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
    fv_low = invert_user_calibration(20.0, poly=poly)
    fv_high = invert_user_calibration(131.3, poly=poly)
    gain, offset = fit_two_point(fv_low, 20.0, fv_high, 132.5)
    assert round(gain, 6) == pytest.approx(1.010345, abs=1e-6)
    assert round(offset, 6) == pytest.approx(1.090435, abs=1e-6)


def test_extremo_a_extremo_pres_camara_reproduce_calibration_yaml():
    """Idem para pres_camara: bajo 12->9.54, alto 322->300, con la
    calibracion previa gain=1.3466/offset=-67.11."""
    fv_low = invert_user_calibration(12.0, gain=1.3466, offset=-67.11)
    fv_high = invert_user_calibration(322.0, gain=1.3466, offset=-67.11)
    gain, offset = fit_two_point(fv_low, 9.54, fv_high, 300.0)
    assert round(gain, 6) == pytest.approx(1.261721, abs=1e-6)
    assert round(offset, 6) == pytest.approx(-64.583518, abs=1e-5)
