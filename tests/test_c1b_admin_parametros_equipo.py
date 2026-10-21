# C1b (tanda 6, decisión 1.5): el admin VE Parámetros del equipo en solo
# lectura (revierte P2-1 de la tanda 5). Campos deshabilitados con el motivo;
# el backend rechaza con 403.

from unittest.mock import MagicMock

import pytest

from autoclave.ui_qml.domain import permisos_opciones as po


def test_admin_ve_parametros_del_equipo():
    assert po.puede_ver("parametros_sistema", "admin")
    assert [s.clave for s in po.secciones_visibles("admin")] == [
        "parametros_sistema", "usuarios", "conectividad"]


@pytest.mark.parametrize("estado", ["PREPARACION", "PREPARADO", "FALLA", "CICLO"])
def test_admin_nunca_edita_parametros_del_equipo(estado):
    assert po.edicion_permitida(estado, "admin", "parametros_sistema") is False
    assert po.motivo_solo_lectura(estado, "admin", "parametros_sistema") == "rol"


def test_tecnico_e_ingeniero_no_cambian():
    assert po.edicion_permitida("PREPARADO", "tecnico", "parametros_sistema") is True
    assert po.edicion_permitida("CICLO", "tecnico", "parametros_sistema") is False
    assert po.motivo_solo_lectura("CICLO", "tecnico", "parametros_sistema") == "estado"
    assert po.motivo_solo_lectura("PREPARADO", "tecnico", "parametros_sistema") == ""
    assert po.edicion_permitida("CICLO", "ingeniero", "parametros_sistema") is True


def test_admin_aterriza_en_usuarios():
    assert po.seccion_inicial("admin") == "usuarios"
    assert po.seccion_inicial("tecnico") == "parametros_ciclo"
    assert po.seccion_inicial("operador") == ""


def test_admin_sigue_sin_ver_las_otras_tecnicas():
    for s in ("parametros_ciclo", "entradas_salidas", "mantenimiento", "opciones_avanzadas"):
        assert not po.puede_ver(s, "admin")


def test_motivo_en_es_y_en():
    from autoclave import i18n
    for idioma in ("es", "en"):
        assert i18n.existe("opciones.solo_lectura_rol", idioma)


def test_qml_muestra_motivo_del_controlador():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas/Opciones.qml"
           ).read_text(encoding="utf-8")
    assert "control.motivoSoloLectura" in qml
    assert "opciones.solo_lectura_rol" in qml
    assert "control.seccionInicial" in qml


@pytest.mark.parametrize("ruta,cuerpo", [("/printer/config", {"habilitada": True}),
                                         ("/units", {"temperatura": "C", "presion": "kPa"})])
def test_backend_rechaza_al_admin(ruta, cuerpo):
    from fastapi.testclient import TestClient
    from tests.backend_doble import cabecera, cargar_servidor
    srv, _ = cargar_servidor(MagicMock())
    r = TestClient(srv.app).put(ruta, json=cuerpo, headers=cabecera(srv, "admin"))
    assert r.status_code == 403
