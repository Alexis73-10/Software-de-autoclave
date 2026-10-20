"""U1 (tanda 5): singleton QML Unidades (presentación y entrada)."""

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ATM = 74.6


@pytest.fixture
def un():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.bridge.unidades_qml import UnidadesQml
    return UnidadesQml(sondear=False)


def test_por_defecto_c_y_kpa(un):
    assert (un.temperatura, un.presion) == ("C", "kPa")
    assert un.temp(134.0) == "134.0 °C" and un.pres(210.0) == "210.0 kPa"


def test_cambio_en_caliente_emite_y_sube_version(un):
    vistos = []
    un.cambiado.connect(lambda: vistos.append(1))
    un.aplicar({"temperatura": "F", "presion": "psi", "p_atm": ATM})
    assert vistos == [1] and un.version == 1
    assert un.temp(134.0) == "273.2 °F"
    assert un.pres(ATM + 6.894757) == "1.0 psig" and un.pres(ATM - 3.386389) == "1.0 inHg"
    un.aplicar({"temperatura": "F", "presion": "psi", "p_atm": ATM})   # igual: sin señal
    assert vistos == [1]


@pytest.mark.parametrize("datos", [None, {}, {"temperatura": "K", "presion": "kPa"}])
def test_respuesta_invalida_conserva_las_vigentes(un, datos):
    un.aplicar({"temperatura": "F", "presion": "bar", "p_atm": ATM})
    un.aplicar(datos)
    assert (un.temperatura, un.presion) == ("F", "bar")


def test_parametro_absoluto_y_diferencia(un):
    un.aplicar({"temperatura": "F", "presion": "psi", "p_atm": ATM})
    assert un.parametro(134.0, "°C", "temperatura_esterilizacion") == "273.2 °F"
    assert un.parametro(3.0, "°C", "rango_temperatura_ester") == "5.40 °F"
    assert un.parametro(6.894757, "kPa", "brecha_segura_presion") == "1.00 psi"
    assert un.parametro(30, "seg", "tiempo") == ""


def test_ingreso_convierte_valida_y_rechaza(un):
    un.aplicar({"temperatura": "F", "presion": "psi", "p_atm": ATM})
    assert un.aInterna(273.2, "°C", "temperatura_esterilizacion", "") == pytest.approx(134.0)
    assert un.aInterna(1.0, "kPa", "presion_alta_pulso_a", "psig") == pytest.approx(ATM + 6.894757)
    assert un.aInterna(1.0, "kPa", "presion_baja_pulso_a", "inHg") == pytest.approx(ATM - 3.386389)
    assert un.aInterna(-1.0, "kPa", "presion_alta_pulso_a", "psig") is None
    assert un.ingresosPsi("kPa", "presion_baja_pulso_a", 0, 1000) == ["psig", "inHg"]
    assert un.ingresosPsi("kPa", "brecha_segura_presion", 0, 10) == []


def test_psi_sin_p_atm_no_muestra_ni_convierte(un):
    un.aplicar({"temperatura": "C", "presion": "psi", "p_atm": None})
    assert un.pres(200.0) == "—"
    assert un.aInterna(10.0, "kPa", "presion_alta_pulso_a", "psig") is None


def test_ingresos_psi_con_la_firma_que_usa_el_qml(un):
    """Revisión U1 (SAF-01): misma lista de argumentos que OpcionesParametrosCiclo.qml."""
    import re
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesParametrosCiclo.qml").read_text(encoding="utf-8")
    assert re.search(r"Unidades\.ingresosPsi\(param\.unidad \|\| \"\", param\.clave, param\.min, param\.max\)", qml)
    un.aplicar({"temperatura": "C", "presion": "psi", "p_atm": ATM})
    assert un.ingresosPsi("kPa", "presion_baja_pulso_a", 0, 1000) == ["psig", "inHg"]
    assert un.ingresosPsi("kPa", "presion_baja_secado", 0, 50) == ["inHg"]


def test_a_interna_usa_la_unidad_fijada_al_abrir(un):
    """Revisión U1 (SAF-02): si cambió la vigente, manda la de ingreso."""
    un.aplicar({"temperatura": "C", "presion": "kPa", "p_atm": ATM})
    assert un.aInterna(140.0, "°C", "temp_max_apertura", "F") == pytest.approx(60.0)
    assert un.aInterna(140.0, "°C", "temp_max_apertura", "kPa") is None


def test_p_atm_fuera_de_rango_no_se_usa(un):
    un.aplicar({"temperatura": "C", "presion": "psi", "p_atm": 5.0})
    assert un.pres(200.0) == "—"


def test_rango_calentamiento_no_se_convierte(un):
    un.aplicar({"temperatura": "F", "presion": "psi", "p_atm": ATM})
    assert un.parametro(2.0, "kPa", "rango_calentamiento") == ""
