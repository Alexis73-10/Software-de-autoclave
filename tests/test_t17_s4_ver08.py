"""Tanda 17 (VER-08): Información del equipo y Información del sistema muestran
`version_completa()`. En la compilación I la fila salía vacía porque era
anterior a la etapa VER; esta prueba falla si, con `_build_info` presente y
`sys.frozen` simulado (ejecutable compilado), la fila `version_software` sale
vacía o como «—»."""

import sys
import types

import pytest

pytestmark = pytest.mark.req("VER-08")

SIN_DATO = ("", "—", None)


@pytest.fixture(params=["entrega", "verificacion"])
def compilado(request, monkeypatch):
    """Ejecutable compilado simulado: sys.frozen y un autoclave._build_info falso."""
    from autoclave import _version
    import autoclave
    info = types.ModuleType("autoclave._build_info")
    if request.param == "entrega":
        info.COMMIT, info.ETIQUETA, info.SUCIO = "abc1234", f"v{_version.VERSION_SEMVER}", False
    else:
        info.COMMIT, info.ETIQUETA, info.SUCIO = "def5678", None, True
    info.FECHA_UTC = "2026-10-26T12:00:00Z"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setitem(sys.modules, "autoclave._build_info", info)
    monkeypatch.setattr(autoclave, "_build_info", info, raising=False)
    return request.param, info


def test_version_completa_compilada_no_vacia(compilado):
    from autoclave._version import VERSION_SEMVER, version_completa
    tipo, info = compilado
    v = version_completa()
    assert v not in SIN_DATO and "+fuente" not in v
    assert info.COMMIT in v
    if tipo == "entrega":
        assert v == f"{VERSION_SEMVER} ({info.COMMIT})"


def test_informacion_del_equipo_muestra_la_version(compilado):
    from autoclave._version import version_completa
    from autoclave.ui_qml.bridge import info_equipo
    v = info_equipo.version_software()
    assert v == version_completa()
    filas = {f["clave"]: f for f in info_equipo.filas_equipo(None, 1, v, None)}
    assert filas["version_software"]["valor"] not in SIN_DATO
    assert filas["version_software"]["valor"] == version_completa()
    assert filas["version_software"]["disponible"] is True


def test_informacion_del_sistema_muestra_la_version(compilado):
    """GET /system/info (backend) entrega `version_completa()` y el
    controlador de la pantalla la pone en la fila version_software."""
    from unittest.mock import MagicMock
    from autoclave._version import version_completa
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.profile = None
    ctx.serial.tarjeta.return_value = {"version": "2.1", "id": "X"}
    srv, _ = cargar_servidor(ctx)
    datos = TestClient(srv.app).get("/system/info").json()
    assert datos["software"]["version"] == version_completa()
    filas = {f["clave"]: f for g in grupos_de(datos) for f in g["filas"]}
    assert filas["version_software"]["valor"] not in SIN_DATO
    assert filas["version_software"]["valor"] == version_completa()


def test_desde_fuente_tambien_hay_version(monkeypatch):
    """Sin compilar (desde fuente) la fila tampoco queda vacía."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    from autoclave.ui_qml.bridge import info_equipo
    v = info_equipo.version_software()
    assert v not in SIN_DATO and v.endswith("+fuente")
