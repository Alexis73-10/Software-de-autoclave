"""T29-06 (tanda 29): Opciones › Parámetros del ciclo abre en el programa
seleccionado en Preciclo (`seleccionado` de GET /programas); sin él, en el
primero. El nombre del programa se ve en todas las vistas del flujo."""

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.controllers.parametros_ciclo_controller import (  # noqa: E402
    etiqueta_programa, numero_inicial)
from autoclave.ui_qml.sesion_backend import Resultado  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas" / "OpcionesParametrosCiclo.qml"


def _programas(seleccionado=None):
    return {"programas": [
        {"numero": n, "cycle_id": cid, "nombre": nombre, "origen": "user", "danado": False,
         "editable": True, "habilitado": True, "personalizado": False, "secciones": [],
         **({"seleccionado": cid == seleccionado} if seleccionado is not None else {})}
        for n, cid, nombre in ((1, "bowe_dick", "Bowie & Dick"),
                               (2, "134_instrumental", "Instrumental 134"),
                               (4, "liquidos", "Líquidos"))]}


class _Sesion:
    def __init__(self, datos):
        self.datos = datos

    def enviar(self, metodo, ruta, cuerpo=None):
        if ruta == "/programas":
            return Resultado("ok", self.datos, 200)
        return Resultado("ok", {}, 200)


def _ctrl(datos):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _Sesion(datos)
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    return c, s


def test_abre_en_el_programa_seleccionado():
    c, _ = _ctrl(_programas("liquidos"))
    assert c.numero == 4
    assert c.nombrePrograma == "Líquidos"
    assert c.etiquetaPrograma == "04 · Líquidos"


def test_sin_seleccionado_abre_en_el_primero():
    c, _ = _ctrl(_programas())
    assert c.numero == 1
    c, _ = _ctrl(_programas("no_existe"))
    assert c.numero == 1


def test_recargas_posteriores_no_cambian_el_programa_elegido():
    """Tras guardar se recarga la lista: no vuelve al seleccionado."""
    c, s = _ctrl(_programas("liquidos"))
    c.elegirPrograma(2)
    c.cargar()
    assert c.numero == 2


def test_funciones_puras():
    assert numero_inicial(_programas("134_instrumental")["programas"]) == 2
    assert numero_inicial(_programas()["programas"]) == 1
    assert etiqueta_programa(3, "Textiles") == "03 · Textiles"
    assert etiqueta_programa(0, "x") == "" and etiqueta_programa(None, "x") == ""


def test_nombre_del_programa_en_todas_las_vistas():
    texto = QML.read_text(encoding="utf-8")
    # programa: el selector «NN · nombre»; sección y ajuste: ya lo mostraban
    assert "SelectorPrograma {" in texto
    assert 'String(control.numero).padStart(2, "0") + " " + control.nombrePrograma' in texto
    assert 'raiz.nombreSeccion(control.seccion) + " · " + control.nombrePrograma' in texto
    # sensores y entradas (T29-06)
    for nombre in ("programaSensores", "programaEntradas"):
        i = texto.index(f'objectName: "{nombre}"')
        assert "control.etiquetaPrograma" in texto[i:i + 300]
