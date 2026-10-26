# tests/test_c9_manejo_ciclos_banco_qml.py
#
# C9 (tanda 9, D9-10): OPCIONES › Opciones avanzadas › Manejo de ciclos con el
# backend doble (tests/banco/opciones_qml_banco.py), en español y en inglés:
#   - técnico fuera de ciclo: ve Opciones avanzadas solo con Manejo de ciclos
#     (sin la reasignación de E/S); crear, borrar (solo personalizados) y el
#     resultado;
#   - técnico e ingeniero en CICLO: todo deshabilitado (fuera de ciclo);
#   - ingeniero: elige entre Manejo de ciclos y la reasignación.
# Con C9_CAPTURAS=1 guarda docs/informes/tanda9/capturas/c9/C9_<idioma>_*.png.

import os

import pytest

pytest.importorskip("PySide6")

from tests.banco import opciones_qml_banco as banco  # noqa: E402

CAPTURAS = banco.RAIZ / "docs" / "informes" / "tanda9" / "capturas" / "c9"

PROGRAMAS = {"programas": [
    {"numero": 1, "cycle_id": "121_instrumental", "nombre": "instrumental 121", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 2, "cycle_id": "134_instrumental", "nombre": "instrumental 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 3, "cycle_id": "134_textil", "nombre": "textil 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 4, "cycle_id": "121_liquidos", "nombre": "liquidos 121", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 5, "cycle_id": "programa_5", "nombre": "Contenedores 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": False, "personalizado": True, "secciones": []},
    {"numero": 21, "cycle_id": "x", "nombre": "referencia", "origen": "factory",
     "danado": False, "editable": False, "habilitado": True, "personalizado": False, "secciones": []},
]}
RUTAS = {"GET /programas": [200, PROGRAMAS],
         "POST /programas/2/duplicar": [200, {"ok": True, "numero": 6, "nombre": "Bandejas 134"}],
         "DELETE /programas/5": [200, {"ok": True, "numero": 5}]}

PASOS_TECNICO = r'''
from autoclave import i18n as _i18n
from PySide6.QtCore import QObject
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
av = buscar("opcionesAvanzadas")
m = buscar("opcionesManejoCiclos")
ctrl = m.findChild(QObject, "manejoCiclosController")
salida["entradas"] = [s["clave"] for s in raiz.property("secciones")]
salida["selector"] = buscar("selectorOpcionesAvanzadas").isVisible()
salida["reasignacion"] = buscar("opcionesReasignacion") is not None
salida["filas"] = len(ctrl.property("programas"))
# Tanda 17 (PRC-01, decisión de Cristian): el programa se elige con el
# selector desplegable y la tarjeta muestra solo el elegido
m.elegirPrograma(5); esperar()
salida["borrar_5"] = buscar("botonBorrar_5", m).isVisible()
m.elegirPrograma(1); esperar()
salida["borrar_1"] = buscar("botonBorrar_1", m).isVisible()
salida["crear_hab"] = buscar("botonCrearPrograma", m).property("habilitado")
capturar(f"C9_{IDIOMA}_1_tecnico_lista.png")
m.abrirCrear(); esperar()
salida["panel_crear"] = buscar("panelCrearPrograma", m).isVisible()
salida["bases"] = len(ctrl.property("bases"))
capturar(f"C9_{IDIOMA}_2_crear_base.png")
m.elegirBase(2); esperar()
salida["panel_tras_elegir"] = buscar("panelCrearPrograma", m).isVisible()
ctrl.crear(2, "Bandejas 134"); esperar()
salida["banda"] = buscar("bandaManejoCiclos", m).isVisible()
salida["texto_banda"] = buscar("textoBandaManejoCiclos", m).property("text")
capturar(f"C9_{IDIOMA}_3_creado.png")
m.pedirBorrar(5, "Contenedores 134"); esperar()
salida["dialogo_borrar"] = buscar("dialogoBorrarManejo", m).isVisible()
capturar(f"C9_{IDIOMA}_4_borrar.png")
buscar("dialogoBorrarManejo", m).confirmado.emit(); esperar()
'''

PASOS_EN_CICLO = r'''
from autoclave import i18n as _i18n
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
m = buscar("opcionesManejoCiclos")
salida["aviso"] = buscar("avisoEnCicloManejo", m).isVisible()
salida["crear_hab"] = buscar("botonCrearPrograma", m).property("habilitado")
# Tanda 17 (PRC-01, decisión de Cristian): la tarjeta muestra solo el elegido
m.elegirPrograma(1); esperar()
salida["dup_hab"] = buscar("botonDuplicar_1", m).property("habilitado")
m.elegirPrograma(5); esperar()
salida["hab_hab"] = buscar("botonHabilitar_5", m).property("habilitado")
salida["borrar_hab"] = buscar("botonBorrar_5", m).property("habilitado")
m.abrirCrear(); m.pedirBorrar(5, "x"); esperar()
salida["panel_crear"] = buscar("panelCrearPrograma", m).isVisible()
salida["dialogo_borrar"] = buscar("dialogoBorrarManejo", m).isVisible()
capturar(f"C9_{IDIOMA}_{NUM}_{ROL}_en_ciclo.png")
'''

PASOS_INGENIERO = r'''
from autoclave import i18n as _i18n
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
salida["selector"] = buscar("selectorOpcionesAvanzadas").isVisible()
salida["manejo"] = buscar("opcionesManejoCiclos") is not None
capturar(f"C9_{IDIOMA}_7_ingeniero_manejo.png")
from tests.test_r8_reasignacion_banco_qml import _datos
rutas["GET /io/assignment"] = (200, _datos())
av = buscar("opcionesAvanzadas")
av.elegirSegmento("reasignacion"); esperar(400)
salida["reasignacion"] = buscar("opcionesReasignacion") is not None
salida["manejo_tras"] = buscar("opcionesManejoCiclos") is not None
capturar(f"C9_{IDIOMA}_8_ingeniero_reasignacion.png")
'''


def _correr(rol, pasos, idioma, estado="PREPARADO", extra=""):
    capturas = os.environ.get("C9_CAPTURAS") == "1"
    return banco.correr(rol, f"IDIOMA = {idioma!r}\n{extra}" + pasos, rutas=RUTAS, estado=estado,
                        capturas=capturas, dir_capturas=CAPTURAS)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_tecnico_fuera_de_ciclo(idioma):
    r = _correr("tecnico", PASOS_TECNICO, idioma)
    assert "opciones_avanzadas" in r["entradas"]
    assert r["selector"] is False and r["reasignacion"] is False     # solo el ingeniero
    assert r["filas"] == 5                                            # sin los de cycles/factory
    assert r["borrar_5"] is True and r["borrar_1"] is False          # nunca los de fábrica
    assert r["crear_hab"] is True
    assert r["panel_crear"] is True and r["bases"] == 5
    assert r["panel_tras_elegir"] is False
    assert r["banda"] is True and "Bandejas 134" in r["texto_banda"] and "6" in r["texto_banda"]
    assert r["dialogo_borrar"] is True
    enviados = [tuple(e) for e in r["enviados"]]
    assert ("POST", "/programas/2/duplicar", {"nombre": "Bandejas 134", "crear": True}) in enviados
    assert ("DELETE", "/programas/5", None) in enviados
    assert r["avisos"] == []


@pytest.mark.parametrize("rol,num", [("tecnico", 5), ("ingeniero", 6)])
@pytest.mark.parametrize("idioma", ["es", "en"])
def test_en_ciclo_todo_deshabilitado(rol, num, idioma):
    r = _correr(rol, PASOS_EN_CICLO, idioma, estado="CICLO", extra=f"NUM = {num}\nROL = {rol!r}\n")
    assert r["aviso"] is True
    assert not any(r[k] for k in ("crear_hab", "dup_hab", "hab_hab", "borrar_hab"))
    assert r["panel_crear"] is False and r["dialogo_borrar"] is False
    assert not [e for e in r["enviados"] if e[0] != "GET"]
    assert r["avisos"] == []


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ingeniero_elige_entre_manejo_y_reasignacion(idioma):
    r = _correr("ingeniero", PASOS_INGENIERO, idioma)
    assert r["selector"] is True and r["manejo"] is True
    assert r["reasignacion"] is True and r["manejo_tras"] is False
    assert r["avisos"] == []
