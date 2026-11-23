"""Modo fábrica, Etapa 2: cliente y pantalla de Manejo de ciclos.

- sesion_backend reconoce `solo_modo_fabrica` (global) y los códigos de
  `/programas` y `/fabrica/programas` con texto;
- ManejoCiclosController.borrarFabrica envía DELETE /fabrica/programas/{id};
- la pantalla ofrece «Borrar (modo fábrica)» solo en FÁBRICA con sesión de
  ingeniero, con confirmación.
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml import sesion_backend  # noqa: E402
from autoclave.ui_qml.sesion_backend import Resultado  # noqa: E402

pytestmark = [pytest.mark.req("DF-04"), pytest.mark.req("FAB-09")]

RAIZ = Path(__file__).resolve().parents[1]

_PROGRAMAS = {"programas": [
    {"numero": 1, "cycle_id": "bowe_dick", "nombre": "Bowie", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False,
     "fabrica_equipo": False, "secciones": []},
    {"numero": 7, "cycle_id": "programa_7", "nombre": "Del equipo", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False,
     "fabrica_equipo": True, "secciones": []},
    {"numero": 11, "cycle_id": "programa_11", "nombre": "Personal", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": True,
     "fabrica_equipo": False, "secciones": []},
]}


# ── sesion_backend ──────────────────────────────────────────────────────────

def test_codigos_conocidos_y_textos():
    assert "solo_modo_fabrica" in sesion_backend.codigos_conocidos("/fabrica/programas/x")
    assert "solo_modo_fabrica" in sesion_backend.codigos_conocidos("/programas")
    assert sesion_backend.clave_mensaje("solo_modo_fabrica") == "fabrica.err_solo_modo_fabrica"
    assert "maximo_programas_fabrica" in sesion_backend.codigos_conocidos("/programas/2/duplicar")
    for codigo in ("no_es_programa_de_fabrica", "error_archivo", "programa_activo"):
        assert codigo in sesion_backend.codigos_conocidos("/fabrica/programas/bowe_dick")
    # fuera de su ruta siguen siendo genéricos
    assert "no_es_programa_de_fabrica" not in sesion_backend.codigos_conocidos("/io/assignment")


def test_textos_en_ambos_catalogos():
    claves = ["manejo_ciclos.de_fabrica_equipo", "manejo_ciclos.borrar_fabrica",
              "manejo_ciclos.borrar_fabrica_pregunta", "manejo_ciclos.err_maximo_fabrica",
              "manejo_ciclos.err_solo_modo_fabrica", "manejo_ciclos.err_no_es_fabrica",
              "manejo_ciclos.err_archivo", "fabrica.err_solo_modo_fabrica",
              "bitacora.ev.programa_fabrica_borrado", "bitacora.tipo.programa_fabrica_borrado"]
    for idioma in ("es", "en"):
        cat = json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{idioma}.json")
                         .read_text(encoding="utf-8"))
        for clave in claves:
            nodo = cat
            for parte in clave.split("."):
                nodo = nodo[parte]
            assert isinstance(nodo, str) and nodo, (idioma, clave)


def test_evento_de_bitacora_en_configuracion():
    from autoclave.core.runtime import bitacora
    assert bitacora.CATEGORIA_DE_EVENTO["programa_fabrica_borrado"] == "configuracion"


# ── controlador ─────────────────────────────────────────────────────────────

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
        return Resultado("ok", {"ok": True}, 200)


def _ctrl(extra=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.manejo_ciclos_controller import ManejoCiclosController
    s = _Sesion(extra)
    c = ManejoCiclosController(sesion=s)
    c.cargar()
    return c, s


def test_filas_marcan_fabrica_equipo_y_borrable_fabrica():
    c, _ = _ctrl()
    por_numero = {p["numero"]: p for p in c.programas}
    assert por_numero[7]["fabrica_equipo"] is True and por_numero[1]["fabrica_equipo"] is False
    assert por_numero[1]["borrableFabrica"] is True and por_numero[7]["borrableFabrica"] is True
    assert por_numero[11]["borrableFabrica"] is False and por_numero[11]["borrable"] is True


def test_borrar_fabrica_envia_por_cycle_id():
    c, s = _ctrl()
    assert c.borrarFabrica(7)
    assert ("DELETE", "/fabrica/programas/programa_7", None) in s.enviados
    assert c.mensaje == "manejo_ciclos.ok_borrado" and c.detalleMensaje["nombre"] == "Del equipo"


def test_borrar_fabrica_no_envia_un_personalizado_ni_un_desconocido():
    c, s = _ctrl()
    assert c.borrarFabrica(11) is False and c.borrarFabrica(99) is False
    assert not [e for e in s.enviados if e[0] == "DELETE"]


@pytest.mark.parametrize("codigo,clave", [
    ("solo_modo_fabrica", "manejo_ciclos.err_solo_modo_fabrica"),
    ("no_es_programa_de_fabrica", "manejo_ciclos.err_no_es_fabrica"),
    ("programa_activo", "manejo_ciclos.err_programa_activo"),
    ("error_archivo", "manejo_ciclos.err_archivo"),
])
def test_rechazos_del_borrado_de_fabrica(codigo, clave):
    c, _ = _ctrl({("DELETE", "/fabrica/programas/bowe_dick"): Resultado(codigo, {}, 409)})
    assert c.borrarFabrica(1)
    assert c.mensaje == clave and c.exito is False


def test_crear_con_los_10_ocupados_muestra_su_texto():
    c, _ = _ctrl({("POST", "/programas/1/duplicar"):
                  Resultado("maximo_programas_fabrica", {}, 409)})
    assert c.crear(1, "Otro")
    assert c.mensaje == "manejo_ciclos.err_maximo_fabrica"


# ── pantalla (offscreen, con el backend doble de Opciones) ─────────────────

PASOS = r'''
from autoclave import i18n as _i18n
from PySide6.QtCore import QObject
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
m = buscar("opcionesManejoCiclos")
salida["borrar_fabrica_prop"] = m.property("borrarFabrica")
m.elegirPrograma(1); esperar()
salida["boton_1"] = buscar("botonBorrarFabrica_1", m).isVisible()
salida["estado_1"] = buscar("estadoPrograma_1", m).property("text")
m.elegirPrograma(7); esperar()
salida["boton_7"] = buscar("botonBorrarFabrica_7", m).isVisible()
salida["estado_7"] = buscar("estadoPrograma_7", m).property("text")
m.elegirPrograma(11); esperar()
salida["boton_11"] = buscar("botonBorrarFabrica_11", m).isVisible()
m.elegirPrograma(7); esperar()
m.pedirBorrarFabrica(7, "Del equipo"); esperar()
d = buscar("dialogoBorrarFabricaManejo", m)
salida["dialogo"] = d.isVisible() if d is not None else None
if d is not None and d.isVisible():
    d.confirmado.emit(); esperar()
'''

RUTAS = {"GET /programas": [200, _PROGRAMAS],
         "DELETE /fabrica/programas/programa_7": [200, {"ok": True, "cycle_id": "programa_7",
                                                        "numero": 7}]}


def _correr(rol, modo_fabrica, idioma="es"):
    from tests.banco import opciones_qml_banco as banco
    return banco.correr(rol, f"IDIOMA = {idioma!r}\n" + PASOS, rutas=RUTAS,
                        modo_fabrica=modo_fabrica)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_pantalla_fabrica_ingeniero_ofrece_borrar_con_confirmacion(idioma):
    r = _correr("ingeniero", True, idioma)
    assert r["borrar_fabrica_prop"] is True
    assert r["boton_1"] is True and r["boton_7"] is True and r["boton_11"] is False
    assert r["dialogo"] is True
    assert ("DELETE", "/fabrica/programas/programa_7", None) in [tuple(e) for e in r["enviados"]]
    esperado = "De fábrica del equipo" if idioma == "es" else "Factory program of this unit"
    assert esperado in r["estado_7"] and esperado not in r["estado_1"]
    assert r["avisos"] == []


@pytest.mark.parametrize("rol,modo_fabrica", [("ingeniero", False), ("tecnico", True)])
def test_pantalla_sin_borrar_de_fabrica_en_entregado_o_para_tecnico(rol, modo_fabrica):
    r = _correr(rol, modo_fabrica)
    assert r["borrar_fabrica_prop"] is False
    assert not any(r[k] for k in ("boton_1", "boton_7", "boton_11"))
    assert r["dialogo"] is False
    assert not [e for e in r["enviados"] if e[0] == "DELETE"]
    assert r["avisos"] == []
