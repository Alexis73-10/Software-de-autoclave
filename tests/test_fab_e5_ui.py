"""Modo fábrica, Etapa 5: cliente y pantalla del cierre de fabricación.

- sesion_backend reconoce `cierre_en_curso` (global) y los códigos de
  POST /fabrica/cierre con texto;
- CierreFabricaController presenta GET /fabrica/cierre y envía el POST con la
  contraseña;
- Opciones avanzadas ofrece «Cierre de fabricación» solo en FÁBRICA con
  sesión de ingeniero; iniciar pide confirmación y luego la contraseña.
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml import sesion_backend  # noqa: E402
from autoclave.ui_qml.sesion_backend import Resultado  # noqa: E402

pytestmark = [pytest.mark.req("DF-04"), pytest.mark.req("DF-05")]

RAIZ = Path(__file__).resolve().parents[1]

_GET = {
    "resumen": {"conteos": {"ciclos": 12, "lecturas": 900, "alarmas": 3, "bitacora": 250,
                            "mantenimientos": 1, "operadores": 2, "usuarios_prueba": 3,
                            "catalogo_carga": 4},
                "se_borra": [], "queda": []},
    "usb": {"unidades": [{"ruta": "E:\\", "libre_bytes": 8 * 10**9}], "unidad": "E:\\",
            "libre_bytes": 8 * 10**9, "estimado_bytes": 10**7, "requerido_bytes": 4 * 10**7},
    "precondiciones": {"ok": True, "motivos": []},
    "cierre": {"en_curso": False, "etapa": "", "error": None, "resultado": None,
               "etapas": ["validando", "paquete", "consolidando", "base_nueva", "marca",
                          "reiniciando"], "progreso": 0.0},
}


def _con(**cambios):
    d = json.loads(json.dumps(_GET))
    for clave, valor in cambios.items():
        d[clave] = valor
    return d


# ── sesion_backend e i18n ───────────────────────────────────────────────
def test_codigos_conocidos_y_textos():
    assert sesion_backend.clave_mensaje("cierre_en_curso") == "fabrica.err_cierre_en_curso"
    assert "cierre_en_curso" in sesion_backend.codigos_conocidos("/cycle/start")
    for codigo in ("cierre_estado_no_permitido", "usb_ausente", "usb_no_escribible",
                   "usb_sin_espacio"):
        assert codigo in sesion_backend.codigos_conocidos("/fabrica/cierre")
        assert sesion_backend.clave_mensaje(codigo, "/fabrica/cierre").startswith("cierre_fabrica.")
    assert "cierre_estado_no_permitido" not in sesion_backend.codigos_conocidos("/io/assignment")


def test_textos_en_ambos_catalogos():
    from autoclave.ui_qml.controllers import cierre_fabrica_controller as m
    es = json.loads((RAIZ / "src/autoclave/i18n/es.json").read_text(encoding="utf-8"))
    en = json.loads((RAIZ / "src/autoclave/i18n/en.json").read_text(encoding="utf-8"))
    assert set(es["cierre_fabrica"]) == set(en["cierre_fabrica"])
    from autoclave.core.runtime import cierre_fabrica as cf
    claves = {f"cierre_fabrica.etapa_{e}" for e in cf.ETAPAS}
    claves |= {f"cierre_fabrica.conteo_{c}" for c in m.ORDEN_CONTEOS}
    claves |= {f"cierre_fabrica.motivo_{c}" for c in (
        "sin_base", "ciclo", "falla", "estado", "paro", "confirmacion_pendiente", "modo_prueba",
        "apagando", "camara_no_segura", "reinicio_no_disponible", "usb_ausente",
        "usb_sin_espacio", "usb_no_escribible")}
    claves |= set(m._ERRORES_CIERRE.values()) | {"cierre_fabrica.err_paquete",
                                                  "cierre_fabrica.err_generico",
                                                  "fabrica.err_cierre_en_curso",
                                                  "manejo_ciclos.segmento_cierre_fabrica"}
    for cat in (es, en):
        for clave in claves:
            nodo = cat
            for parte in clave.split("."):
                nodo = nodo[parte]
            assert isinstance(nodo, str) and nodo, clave


# ── controlador ─────────────────────────────────────────────────────────
class _Sesion:
    def __init__(self, get=None, post=None):
        self.enviados = []
        self.get = get or _GET
        self.post = post or Resultado("ok", {"ok": True}, 202)

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            return Resultado("ok", self.get, 200)
        return self.post


def _ctrl(**kw):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.cierre_fabrica_controller import CierreFabricaController
    s = _Sesion(**kw)
    c = CierreFabricaController(sesion=s)
    c.cargar()
    return c, s


def test_presenta_el_resumen_y_la_usb():
    c, _ = _ctrl()
    assert c.cargado and c.precondicionesOk and c.puedeIniciar
    assert c.conteos[0] == {"clave": "cierre_fabrica.conteo_ciclos", "n": 12}
    assert len(c.conteos) == 8
    assert c.unidad == "E:\\" and c.libre == "8.0 GB" and c.requerido == "40 MB"
    assert c.enCurso is False and c.terminado is False


def test_iniciar_envia_la_clave_y_la_unidad():
    c, s = _ctrl()
    assert c.iniciar("secreta")
    assert ("POST", "/fabrica/cierre", {"clave": "secreta", "unidad": "E:\\"}) in s.enviados
    assert c.iniciar("") is False


def test_no_inicia_con_el_cierre_en_curso():
    c, s = _ctrl(get=_con(cierre={**_GET["cierre"], "en_curso": True, "etapa": "paquete",
                                  "progreso": 0.333}))
    assert c.enCurso and c.puedeIniciar is False and c.etapa == "paquete"
    assert c._timer.isActive()
    assert c.iniciar("x") is False


@pytest.mark.parametrize("causa, clave", [
    ("cierre_estado_no_permitido", "cierre_fabrica.err_estado"),
    ("usb_sin_espacio", "cierre_fabrica.err_usb_sin_espacio"),
    ("usb_no_escribible", "cierre_fabrica.err_usb_no_escribible"),
    ("cierre_en_curso", "fabrica.err_cierre_en_curso"),
    ("solo_modo_fabrica", "fabrica.err_solo_modo_fabrica")])
def test_rechazos_del_post(causa, clave):
    c, _ = _ctrl(post=Resultado(causa, {"codigo": causa}, 409))
    assert c.iniciar("x")
    assert c.mensaje == clave


def test_motivos_y_error_publicado():
    d = _con(precondiciones={"ok": False, "motivos": [
        {"codigo": "ciclo", "motivo": "Hay un ciclo"},
        {"codigo": "camara_no_segura", "motivo": "Temperatura 92 °C"}]},
        cierre={**_GET["cierre"], "error": {"codigo": "hash_invalido", "detalle": "x"}})
    c, _ = _ctrl(get=d)
    assert c.precondicionesOk is False and c.puedeIniciar is False
    assert [m["clave"] for m in c.motivos] == ["cierre_fabrica.motivo_ciclo",
                                               "cierre_fabrica.motivo_camara_no_segura"]
    assert c.mensaje == "cierre_fabrica.err_paquete"


def test_resultado_antes_del_reinicio():
    res = {"ruta_paquete": "E:\\Especifika_liberaciones\\liberacion_SN260001_20261122-1630.zip",
           "hash_paquete": "ab" * 32, "nombre_paquete": "x.zip", "fecha_liberacion": "f"}
    c, _ = _ctrl(get=_con(cierre={**_GET["cierre"], "en_curso": True, "etapa": "reiniciando",
                                  "progreso": 1.0, "resultado": res}))
    assert c.terminado and c.rutaPaquete == res["ruta_paquete"] and c.hashPaquete == "ab" * 32


# ── pantalla (offscreen) ────────────────────────────────────────────────
PASOS = r'''
from autoclave import i18n as _i18n
from PySide6.QtQml import QQmlComponent
from PySide6.QtCore import QUrl
_i18n.fijar_idioma(IDIOMA); esperar(100)
raiz.setProperty("seccionActiva", "opciones_avanzadas"); esperar(400)
av = buscar("opcionesAvanzadas")
salida["prop"] = av.property("cierreFabrica")
seg = buscar("segmentoAvanzadas_cierre", av)
salida["segmento"] = seg is not None and seg.isVisible()
if salida["segmento"]:
    av.elegirSegmento("cierre"); esperar(400)
    p = buscar("opcionesCierreFabrica")
    salida["pantalla"] = p is not None
    salida["textos"] = textos(p)
    capturar("cierre_" + IDIOMA + ".png")
    from PySide6.QtQml import qmlEngine
    eng = qmlEngine(p)
    c = QQmlComponent(eng)
    c.setData(b'import QtQuick\nQtObject { property var abiertos: []\n'
              b' function abrirAlfanumericoAccion(t, v, l, o, cb) { abiertos = [t, o]; cb("secreta") } }',
              QUrl.fromLocalFile("teclado_falso.qml"))
    tec = c.create()
    p.setProperty("teclado", tec)
    esperar(100)
    b = buscar("botonIniciarCierreFabrica", p)
    salida["boton_habilitado"] = b.property("habilitado")
    m = buscar("modalConfirmarCierreFabrica", p)
    m.abrir(); esperar()
    salida["modal"] = m.isVisible()
    m.aceptado.emit(); esperar(300)
    abiertos = tec.property("abiertos")
    salida["teclado"] = abiertos.toVariant() if hasattr(abiertos, "toVariant") else abiertos
'''


def _correr(rol, modo_fabrica, idioma="es", get=None):
    from tests.banco import opciones_qml_banco as banco
    rutas = {"GET /fabrica/cierre": [200, get or _GET], "GET /programas": [200, {"programas": []}],
             "POST /fabrica/cierre": [202, {"ok": True}]}
    pasos = "from PySide6.QtCore import QObject\n" + f"IDIOMA = {idioma!r}\n" + PASOS
    return banco.correr(rol, pasos, rutas=rutas, modo_fabrica=modo_fabrica)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_pantalla_fabrica_ingeniero_cierre_con_confirmacion_y_clave(idioma):
    r = _correr("ingeniero", True, idioma)
    assert r["prop"] is True and r["segmento"] is True and r["pantalla"] is True
    textos = " ".join(r["textos"])
    assert ("12" in textos) and ("E:" in textos)
    assert r["boton_habilitado"] is True and r["modal"] is True
    assert ["POST", "/fabrica/cierre", {"clave": "secreta", "unidad": "E:\\"}] in r["enviados"]
    assert r["teclado"][1] is True          # contraseña oculta
    assert r["avisos"] == []


@pytest.mark.parametrize("rol,modo_fabrica", [("ingeniero", False), ("tecnico", True)])
def test_pantalla_sin_cierre_en_entregado_o_para_tecnico(rol, modo_fabrica):
    r = _correr(rol, modo_fabrica)
    assert r["prop"] is False and r["segmento"] is False
    assert not [e for e in r["enviados"] if e[1] == "/fabrica/cierre"]
    assert r["avisos"] == []
