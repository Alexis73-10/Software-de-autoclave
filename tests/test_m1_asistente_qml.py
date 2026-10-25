"""M1 (tanda 7): asistente de instalación QML con el paso Cámara, offscreen
(planeacion_asistente_modelo.md §4 y §6). Recorre la ventana real con el
puente real (tests/banco/m1_asistente_banco.py)."""

import pytest

pytest.importorskip("PySide6")
from tests.banco.m1_asistente_banco import recorrer  # noqa: E402

GUION = "—"


@pytest.fixture(scope="module")
def obs():
    return recorrer("es")


def _paso(obs, etiqueta):
    return next(p for p in obs["pasos"] if p["etiqueta"] == etiqueta)


def test_sin_avisos_qml(obs):
    assert obs["avisos"] == []


def test_tipo_de_equipo_solo_piso_y_sin_seleccion(obs):
    assert obs["clases"] == ["piso", "piso_lab"]
    assert obs["claseInicial"] == ""


def test_indicador_renumerado_con_el_paso_camara(obs):
    p = _paso(obs, "camara_vacia")
    # LIC-02 (licencia L0): +1 por el paso Contraseñas
    assert p["paso"] == "camara" and p["indice"] == 3 and p["total"] == 9
    assert p["subtitulo"].startswith("Paso 4 de 9") and "Cámara" in p["subtitulo"]


def test_camara_bloquea_siguiente_sin_datos(obs):
    p = _paso(obs, "camara_siguiente_sin_datos")
    assert p["paso"] == "camara"
    assert p["errorCapacidad"] == "Ingrese una capacidad entera de 20 a 2000 L"
    assert p["errorTipoCarga"] == "Seleccione el tipo de carga"
    p = _paso(obs, "camara_19")
    assert p["paso"] == "camara" and p["errorCapacidad"] != ""


def test_vista_previa_en_vivo(obs):
    assert _paso(obs, "camara_vacia")["vistaPrevia"] == GUION
    assert _paso(obs, "camara_solo_carga")["vistaPrevia"] == GUION          # falta la capacidad
    assert _paso(obs, "camara_escribiendo_4")["vistaPrevia"] == GUION       # 4 L, fuera de rango
    assert _paso(obs, "camara_escribiendo_45")["vistaPrevia"] == "SPK-SAT 45V2-LAB"   # sin confirmar
    assert _paso(obs, "camara_45V")["vistaPrevia"] == "SPK-SAT 45V2-LAB"
    assert _paso(obs, "camara_19")["vistaPrevia"] == GUION
    assert _paso(obs, "camara_2000H")["vistaPrevia"] == "SPK-SAT 2000H2-LAB"
    assert _paso(obs, "tras_camara")["paso"] == "enfriamiento"


def test_datos_sin_campo_libre_modelo(obs):
    p = _paso(obs, "datos")
    assert p["paso"] == "datos" and p["campoModelo"] is False


def test_resumen_muestra_el_nombre_arriba_con_capacidad_y_carga(obs):
    p = _paso(obs, "resumen")
    assert p["paso"] == "resumen" and p["resumenModelo"] == "SPK-SAT 2000H2-LAB"
    assert obs["filasResumen"][:2] == ["resumen_capacidad", "resumen_carga"]
    assert "resumen_modelo" not in obs["filasResumen"]


def test_instalar_manda_capacidad_y_carga_y_el_puente_calcula(obs):
    assert obs["instalado"] == [{"model_id": "SPK-SAT 2000H2-LAB", "capacidad_litros": 2000,
                                 "tipo_carga": "H", "equipment_class": "piso_lab"}]
    assert obs["terminado"] is True


def test_l0_contrasenas_obligatorias_antes_del_resumen(obs):
    """LIC-02 (licencia L0): sin contraseñas no se pasa al resumen; con ellas,
    instalar las fija (admin e ingeniero) y termina."""
    p = _paso(obs, "contrasenas_vacias")
    assert p["paso"] == "contrasenas"
    assert obs["erroresContrasenas"] == ["clave_admin", "clave_ingeniero", "confirmacion_admin",
                                         "confirmacion_ingeniero"]
    assert obs["clavesFijadas"] == [["admin", "ingeniero"]] and obs["terminado"] is True
