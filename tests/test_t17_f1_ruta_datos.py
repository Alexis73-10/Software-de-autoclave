"""Tanda 17, F1 (INS-02): orden de resolución de la carpeta de datos.

registro (si RutaPrograma es la carpeta del .exe) → Archivos de programa →
%ProgramData% → carpeta del .exe. El registro se simula: nunca se lee ni se
escribe el real.
"""
import os
import sys

import pytest

from autoclave.utils import resources

pytestmark = pytest.mark.req("INS-02")


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    pf = tmp_path / "PF"
    pd = tmp_path / "PD"
    monkeypatch.setenv("ProgramFiles", str(pf))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "PF86"))
    monkeypatch.setenv("ProgramData", str(pd))

    def fijar_exe(carpeta):
        monkeypatch.setattr(sys, "executable", str(carpeta / "Autoclave.exe"))

    def fijar_registro(valor):
        monkeypatch.setattr(resources, "_leer_registro_instalacion", lambda: valor)

    fijar_registro(None)
    return tmp_path, pf, pd, fijar_exe, fijar_registro


def test_registro_con_ruta_programa_igual_al_exe_da_ruta_datos(entorno):
    tmp, _, _, fijar_exe, fijar_registro = entorno
    programa = tmp / "D" / "Especifika" / "Autoclave" / "programa"
    datos = tmp / "D" / "Especifika" / "Autoclave" / "datos"
    fijar_exe(programa)
    fijar_registro((str(programa) + os.sep, str(datos)))
    assert resources.raiz_datos_exe() == os.path.normpath(str(datos))


def test_registro_compara_sin_distinguir_mayusculas(entorno):
    tmp, _, _, fijar_exe, fijar_registro = entorno
    programa = tmp / "Prog"
    fijar_exe(programa)
    fijar_registro((str(programa).upper(), str(tmp / "Datos")))
    assert resources.raiz_datos_exe() == os.path.normpath(str(tmp / "Datos"))


def test_registro_de_otra_carpeta_no_se_usa_y_rige_la_regla_anterior(entorno):
    tmp, pf, pd, fijar_exe, fijar_registro = entorno
    fijar_exe(pf / "Autoclave")
    fijar_registro((str(tmp / "otra" / "programa"), str(tmp / "otra" / "datos")))
    assert resources.raiz_datos_exe() == os.path.join(str(pd), "Especifika", "Autoclave")


def test_registro_de_otra_carpeta_y_copia_portatil_usa_la_carpeta_del_exe(entorno):
    tmp, _, _, fijar_exe, fijar_registro = entorno
    fijar_exe(tmp / "portatil")
    fijar_registro((str(tmp / "otra" / "programa"), str(tmp / "otra" / "datos")))
    assert resources.raiz_datos_exe() == str(tmp / "portatil")


def test_sin_registro_archivos_de_programa_va_a_programdata(entorno):
    _, pf, pd, fijar_exe, _ = entorno
    fijar_exe(pf / "Especifika" / "Autoclave")
    assert resources.raiz_datos_exe() == os.path.join(str(pd), "Especifika", "Autoclave")


def test_sin_registro_copia_portatil_usa_la_carpeta_del_exe(entorno):
    tmp, _, _, fijar_exe, _ = entorno
    fijar_exe(tmp / "usb")
    assert resources.raiz_datos_exe() == str(tmp / "usb")


def test_carpeta_persistente_cuelga_de_la_ruta_del_registro(entorno):
    tmp, _, _, fijar_exe, fijar_registro = entorno
    fijar_exe(tmp / "programa")
    fijar_registro((str(tmp / "programa"), str(tmp / "datos")))
    assert resources._carpeta_persistente() == os.path.join(os.path.normpath(str(tmp / "datos")),
                                                            "programa")


def test_constantes_compartidas_con_el_setup():
    assert resources.CLAVE_REGISTRO == r"SOFTWARE\Especifika\Autoclave"
    assert (resources.VALOR_RUTA_PROGRAMA, resources.VALOR_RUTA_DATOS) == ("RutaPrograma", "RutaDatos")
    assert (resources.SUBCARPETA_PROGRAMA, resources.SUBCARPETA_DATOS) == ("programa", "datos")


class _WinregFalso:
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 1
    KEY_WOW64_64KEY = 256

    def __init__(self, valores=None, error=False):
        self.valores, self.error, self.abiertas = valores or {}, error, []

    def OpenKey(self, raiz, ruta, reservado, acceso):
        self.abiertas.append((raiz, ruta, acceso))
        if self.error:
            raise FileNotFoundError(ruta)
        falso = self

        class _Clave:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        _Clave.valores = falso.valores
        return _Clave()

    def QueryValueEx(self, clave, nombre):
        if nombre not in self.valores:
            raise FileNotFoundError(nombre)
        return self.valores[nombre], 1


def test_lectura_usa_hklm_en_la_vista_de_64_bits(monkeypatch):
    falso = _WinregFalso({"RutaPrograma": r"D:\Especifika\Autoclave\programa",
                          "RutaDatos": r"D:\Especifika\Autoclave\datos"})
    monkeypatch.setitem(sys.modules, "winreg", falso)
    assert resources._leer_registro_instalacion() == (r"D:\Especifika\Autoclave\programa",
                                                      r"D:\Especifika\Autoclave\datos")
    raiz, ruta, acceso = falso.abiertas[0]
    assert raiz == "HKLM" and ruta == r"SOFTWARE\Especifika\Autoclave"
    assert acceso & falso.KEY_WOW64_64KEY and acceso & falso.KEY_READ


@pytest.mark.parametrize("valores,error", [
    ({}, True),
    ({"RutaPrograma": r"D:\p"}, False),
    ({"RutaPrograma": "", "RutaDatos": r"D:\d"}, False),
    ({"RutaPrograma": r"D:\p", "RutaDatos": 5}, False),
])
def test_lectura_incompleta_o_ausente_da_none(monkeypatch, valores, error):
    monkeypatch.setitem(sys.modules, "winreg", _WinregFalso(valores, error))
    assert resources._leer_registro_instalacion() is None
