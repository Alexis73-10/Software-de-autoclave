# Contrato de autenticación contra el SIMULADO (T-14). Reutiliza la batería de
# test_contrato_autenticacion.py: las pruebas se importan y pytest las recoge
# en este módulo, donde la fixture `cliente` se sustituye por el simulador.
# Los usuarios de prueba por papel coinciden con USUARIOS_SEMBRADOS.

import pytest
from fastapi.testclient import TestClient

from autoclave.simulador.autenticacion_simulada import USUARIOS_SEMBRADOS
from autoclave.simulador.repeticion import Repeticion
from autoclave.simulador.servidor import crear_app
from tests import test_contrato_autenticacion as contrato
from tests.test_contrato_autenticacion import *  # noqa: F401,F403  la batería

_CICLO = {
    "id": 1, "numero_ciclo": 1, "tipo_ciclo": "x", "nombre_ciclo": "x",
    "lecturas": [{"t_s": 0, "codigo": "PV", "temp_camara": 30.0, "pres_camara": 80.0},
                 {"t_s": 60, "codigo": "E", "temp_camara": 30.0, "pres_camara": 80.0}],
}


class _GestorCiclos:
    cycles = {}


@pytest.fixture
def cliente():
    return TestClient(crear_app(Repeticion(_CICLO), _GestorCiclos(), {}))


def test_usuarios_de_prueba_sembrados_en_el_simulador():
    """La batería usa estos usuarios: el simulador debe tenerlos con esa clave."""
    for papel, (usuario, clave) in contrato._USUARIOS.items():
        assert usuario in USUARIOS_SEMBRADOS, papel
        assert USUARIOS_SEMBRADOS[usuario][2] == clave, papel
    assert USUARIOS_SEMBRADOS["Admin"][3] is True        # clave pendiente
    assert USUARIOS_SEMBRADOS["bloq1"][3] is False


def test_tokens_deterministas_por_sesion(cliente):
    t1 = contrato._token(cliente, "tecnico")
    t2 = contrato._token(cliente, "tecnico")
    assert t1.startswith("sim-tec1-") and t2.startswith("sim-tec1-") and t1 != t2


def test_el_backend_de_produccion_no_importa_el_simulador():
    import ast
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "autoclave" / "backend"
    for archivo in raiz.rglob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            modulos = ([a.name for a in nodo.names] if isinstance(nodo, ast.Import)
                       else [nodo.module or ""] if isinstance(nodo, ast.ImportFrom) else [])
            assert not any("simulador" in m for m in modulos), archivo
