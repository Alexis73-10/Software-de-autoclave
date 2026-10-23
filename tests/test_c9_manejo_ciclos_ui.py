"""C9 (tanda 9, D9-10): controlador de Opciones avanzadas › Manejo de ciclos,
textos del catálogo y retiro de los botones de Parámetros del ciclo."""

import json
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"

_PROGRAMAS = {"programas": [
    {"numero": 1, "cycle_id": "121_instrumental", "nombre": "instrumental 121", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 2, "cycle_id": "134_instrumental", "nombre": "instrumental 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 5, "cycle_id": "programa_5", "nombre": "Copia", "origen": "user",
     "danado": False, "editable": True, "habilitado": False, "personalizado": True, "secciones": []},
    {"numero": 9, "cycle_id": "x", "nombre": "Referencia", "origen": "factory",
     "danado": False, "editable": False, "habilitado": True, "personalizado": False, "secciones": []},
]}


class _Sesion:
    def __init__(self, extra=None):
        self.enviados = []
        self.extra = extra or {}

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if (metodo, ruta) in self.extra:
            return self.extra[(metodo, ruta)]
        if ruta == "/programas":
            return Resultado("ok", _PROGRAMAS, 200)
        if ruta.endswith("/duplicar"):
            return Resultado("ok", {"ok": True, "numero": 6, "nombre": cuerpo["nombre"]}, 200)
        return Resultado("ok", {"ok": True}, 200)


def _ctrl(extra=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.manejo_ciclos_controller import ManejoCiclosController
    s = _Sesion(extra)
    c = ManejoCiclosController(sesion=s)
    c.cargar()
    return c, s


def test_lista_solo_los_programas_operables_con_sus_marcas():
    c, _ = _ctrl()
    filas = c.programas
    # los de cycles/factory (origen "factory") son referencia: no se manejan aquí
    assert [p["numero"] for p in filas] == [1, 2, 5]
    p5 = filas[2]
    assert p5["personalizado"] is True and p5["habilitado"] is False
    assert p5["borrable"] is True and filas[0]["borrable"] is False
    assert all(p["duplicable"] for p in filas)
    assert [p["numero"] for p in c.bases] == [1, 2, 5]


def test_crear_es_duplicar_con_marca_de_crear():
    c, s = _ctrl()
    assert c.crear(2, "Nuevo")
    assert ("POST", "/programas/2/duplicar", {"nombre": "Nuevo", "crear": True}) in s.enviados
    assert c.mensaje == "manejo_ciclos.ok_creado"
    assert c.detalleMensaje == {"nombre": "Nuevo", "numero": 6}
    assert c.exito is True


def test_duplicar_habilitar_borrar_llaman_al_backend():
    c, s = _ctrl()
    assert c.duplicar(1, "Otra")
    assert ("POST", "/programas/1/duplicar", {"nombre": "Otra"}) in s.enviados
    assert c.fijarHabilitado(5, True)
    assert ("PUT", "/programas/5/habilitado", {"habilitado": True}) in s.enviados
    assert c.mensaje == "manejo_ciclos.ok_habilitado"
    assert c.fijarHabilitado(1, False)
    assert c.mensaje == "manejo_ciclos.ok_deshabilitado"
    assert c.borrar(5)
    assert ("DELETE", "/programas/5", None) in s.enviados
    assert c.mensaje == "manejo_ciclos.ok_borrado" and c.detalleMensaje["nombre"] == "Copia"
    # cada operación relee la lista
    assert sum(1 for m, r, _ in s.enviados if r == "/programas") >= 5


def test_nombre_vacio_no_llega_al_backend():
    c, s = _ctrl()
    assert not c.crear(1, "   ")
    assert not any(r.endswith("/duplicar") for _, r, _ in s.enviados)
    assert c.mensaje == "manejo_ciclos.err_nombre_invalido" and c.exito is False


@pytest.mark.parametrize("codigo,clave", [
    ("estado_no_permitido", "manejo_ciclos.err_estado"),
    ("rol_sin_permiso", "manejo_ciclos.err_rol"),
    ("nombre_repetido", "manejo_ciclos.err_nombre_repetido"),
    ("VALOR_INVALIDO", "manejo_ciclos.err_nombre_invalido"),
    ("programa_activo", "manejo_ciclos.err_programa_activo"),
    ("programa_de_fabrica", "manejo_ciclos.err_de_fabrica"),
    ("PROGRAMA_NO_EDITABLE", "manejo_ciclos.err_no_duplicable"),
    ("programa_no_encontrado", "manejo_ciclos.err_no_encontrado"),
    ("BASE_OCUPADA", "manejo_ciclos.err_base_ocupada"),
    (BACKEND_NO_RESPONDE, "manejo_ciclos.err_sin_respuesta"),
    ("otra_cosa", "manejo_ciclos.err_generico"),
])
def test_rechazos_muestran_el_motivo(codigo, clave):
    c, s = _ctrl({("DELETE", "/programas/5"): Resultado(codigo, {}, 409)})
    assert not c.borrar(5)
    assert c.mensaje == clave and c.exito is False
    # sin respuesta el resultado es incierto: se relee la lista igual
    assert s.enviados[-1] == ("GET", "/programas", None)


def test_sin_respuesta_al_cargar():
    c, _ = _ctrl({("GET", "/programas"): Resultado(BACKEND_NO_RESPONDE, None, 0)})
    assert c.programas == [] and c.mensaje == "manejo_ciclos.err_sin_respuesta"


def test_textos_en_ambos_catalogos():
    from autoclave.ui_qml.controllers import manejo_ciclos_controller as mc
    cats = {i: json.loads((RAIZ / "src/autoclave/i18n" / f"{i}.json").read_text(encoding="utf-8"))
            for i in ("es", "en")}
    claves = set(mc._MENSAJES.values()) | {"manejo_ciclos.ok_creado", "manejo_ciclos.ok_habilitado",
                                            "manejo_ciclos.ok_deshabilitado", "manejo_ciclos.ok_borrado",
                                            "manejo_ciclos.err_nombre_invalido"}
    for archivo in ("OpcionesManejoCiclos.qml", "OpcionesAvanzadas.qml"):
        claves |= set(re.findall(r'"(manejo_ciclos\.[a-z_]+)"', (QML / archivo).read_text(encoding="utf-8")))
    assert len(claves) > 20
    for idioma, cat in cats.items():
        for clave in sorted(claves):
            grupo, nombre = clave.split(".")
            assert isinstance(cat[grupo].get(nombre), str), (idioma, clave)
    assert isinstance(cats["en"]["opciones"].get("gestion_movida"), str)


def test_parametros_del_ciclo_ya_no_tiene_los_botones():
    qml = (QML / "OpcionesParametrosCiclo.qml").read_text(encoding="utf-8")
    for nombre in ("gestionPrograma", "botonHabilitar", "botonDuplicar", "botonBorrar",
                   "dialogoBorrarPrograma"):
        assert f'"{nombre}"' not in qml, nombre
    assert "opciones.gestion_movida" in qml
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    for slot in ("fijarHabilitado", "duplicar", "borrar"):
        assert not hasattr(ParametrosCicloController, slot), slot


def test_opciones_carga_el_contenedor_de_opciones_avanzadas():
    qml = (QML / "Opciones.qml").read_text(encoding="utf-8")
    assert "OpcionesAvanzadas {" in qml
    assert "control.puedeReasignarIo" in qml and "control.motivoManejoCiclos" in qml
    assert "opciones_avanzadas: avanzadas" in qml              # historial (N8)
