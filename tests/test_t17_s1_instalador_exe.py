"""Tanda 17, s1 (INS-02): el programa instalado por el Setup en
X:\\Especifika\\Autoclave\\programa se reconoce como instalado
(instalador_exe.esta_instalado_aqui) y no vuelve a ofrecer instalarse.

El registro se simula (monkeypatch de resources._leer_registro_instalacion):
nunca se lee ni se escribe el real."""
import os
import sys

import pytest

from autoclave import instalador_exe
from autoclave.utils import resources

pytestmark = pytest.mark.req("INS-02")


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "PF"))
    monkeypatch.setenv("ProgramData", str(tmp_path / "PD"))

    def fijar(exe_carpeta, registro):
        monkeypatch.setattr(sys, "executable", str(exe_carpeta / "Autoclave.exe"))
        monkeypatch.setattr(resources, "_leer_registro_instalacion", lambda: registro)

    return tmp_path, fijar


def test_carpeta_del_registro_es_instalada(entorno):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(programa, (str(programa), str(programa.parent / "datos")))
    assert instalador_exe.esta_instalado_aqui()


def test_registro_con_barra_final_y_mayusculas(entorno):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(programa, (str(programa).upper() + os.sep, str(programa.parent / "datos")))
    assert instalador_exe.esta_instalado_aqui()


def test_otra_carpeta_no_es_instalada(entorno):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(tmp / "USB" / "Autoclave", (str(programa), str(programa.parent / "datos")))
    assert not instalador_exe.esta_instalado_aqui()


def test_sin_registro_solo_archivos_de_programa(entorno):
    tmp, fijar = entorno
    fijar(tmp / "USB" / "Autoclave", None)
    assert not instalador_exe.esta_instalado_aqui()
    # la regla anterior (copia de este instalador) sigue igual
    fijar(tmp / "PF" / "Especifika" / "Autoclave", None)
    assert instalador_exe.esta_instalado_aqui()


def test_usa_las_funciones_de_resources():
    """Un solo lector del registro (utils/resources): mismos nombres que el Setup."""
    import inspect
    fuente = inspect.getsource(instalador_exe.esta_instalado_aqui)
    assert "resources._leer_registro_instalacion()" in fuente
    assert "resources._misma_carpeta(" in fuente
