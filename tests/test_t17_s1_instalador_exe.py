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


# ── R1 (V17-s1-03): con la instalación del Setup no se instala en Archivos de programa ──

@pytest.fixture
def sin_efectos(monkeypatch):
    """Nada de UAC, copias, accesos directos ni ventanas: se registran las llamadas."""
    llamadas = []
    monkeypatch.setattr(instalador_exe, "avisar", lambda texto, error=False: llamadas.append(("avisar", texto)))
    monkeypatch.setattr(instalador_exe, "preguntar", lambda texto: llamadas.append(("preguntar", texto)) or True)
    monkeypatch.setattr(instalador_exe, "_ejecutar_elevado", lambda *a: llamadas.append(("elevar", a)) or 0)
    monkeypatch.setattr(instalador_exe, "_copiar_programa", lambda *a: llamadas.append(("copiar", a)))
    monkeypatch.setattr(instalador_exe, "_acceso_directo", lambda *a: llamadas.append(("lnk", a)))
    monkeypatch.setattr(instalador_exe.subprocess, "Popen", lambda *a, **k: llamadas.append(("abrir", a)))
    monkeypatch.setattr(instalador_exe.subprocess, "run", lambda *a, **k: llamadas.append(("run", a)))
    return llamadas


def test_instalacion_con_setup_desde_otra_carpeta(entorno):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(tmp / "USB" / "Autoclave", (str(programa), str(programa.parent / "datos")))
    assert instalador_exe.instalacion_con_setup() == str(programa)
    # desde la propia RutaPrograma: es la instalada, no "otra"
    fijar(programa, (str(programa), str(programa.parent / "datos")))
    assert instalador_exe.instalacion_con_setup() is None
    fijar(tmp / "USB" / "Autoclave", None)
    assert instalador_exe.instalacion_con_setup() is None


def test_ofrecer_instalacion_con_setup_solo_avisa_y_sale(entorno, sin_efectos):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(tmp / "USB" / "Autoclave", (str(programa), str(programa.parent / "datos")))
    assert instalador_exe.ofrecer_instalacion() is True
    assert [c[0] for c in sin_efectos] == ["avisar"]
    texto = sin_efectos[0][1]
    assert str(programa) in texto and "Setup" in texto
    assert "No se instaló ni se cambió nada" in texto and "Nothing was installed or changed" in texto
    assert not (tmp / "PF").exists()


def test_rol_instalar_con_setup_no_copia_nada(entorno, sin_efectos):
    tmp, fijar = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    fijar(tmp / "USB" / "Autoclave", (str(programa), str(programa.parent / "datos")))
    assert instalador_exe.instalar() == 1
    assert [c[0] for c in sin_efectos] == ["avisar"]
    assert not (tmp / "PF").exists() and not (tmp / "PD").exists()


def test_sin_setup_sigue_ofreciendo_como_antes(entorno, sin_efectos):
    tmp, fijar = entorno
    fijar(tmp / "USB" / "Autoclave", None)
    assert instalador_exe.ofrecer_instalacion() is True
    assert [c[0] for c in sin_efectos] == ["preguntar", "elevar", "abrir"]
