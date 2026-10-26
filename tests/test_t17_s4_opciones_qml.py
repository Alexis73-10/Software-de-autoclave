"""Tanda 17 (s4): pantallas de OPCIONES.

- PRC-01: selector de programa desplegable (lista vertical con desplazamiento)
  en Parámetros del ciclo y en Manejo de ciclos; probado con 20 programas.
- MPR-01: con el modo prueba activo, la cabecera de Entradas/Salidas muestra la
  presión de cámara en la unidad vigente («—» sin lectura) y los avisos de
  salidas cortadas (ESG-02).
- BIT-05: filtros de la bitácora: Desde–Hasta con calendario táctil, Usuario y
  Tipo (categoría) desplegables.
- SON-01: «(monitoreo)» en el selector de Entradas mostradas.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
FRAGMENTO_I18N = RAIZ / "docs" / "informes" / "tanda17" / "i18n" / "s4.json"

_GUION = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401  (contentItem)
import autoclave.ui_qml.bridge.i18n_qml
import autoclave.ui_qml.bridge.unidades_qml as unidades_qml
import autoclave.ui_qml.controllers  # registra Autoclave.Controllers
from autoclave import i18n
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado

cfg = json.loads(sys.argv[2])
i18n.cargar()
for _idioma, _claves in cfg["fragmento"].items():
    for _clave, _texto in _claves.items():
        _nodo = i18n._catalogos[_idioma]
        _partes = _clave.split(".")
        for _p in _partes[:-1]:
            _nodo = _nodo.setdefault(_p, {})
        _nodo.setdefault(_partes[-1], _texto)
enviados = []

class Sesion:
    def enviar(self, metodo, ruta, cuerpo=None):
        enviados.append([metodo, ruta, cuerpo])
        base = ruta.split("?")[0]
        estado, datos = cfg["rutas"].get(metodo + " " + base, [200, {}])
        return Resultado("ok", datos, estado)

sesion_backend.instalar(Sesion())
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(cfg["qml"].encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t17_s4.qml"))
ventana = comp.create()
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(300)
vista = ventana.findChild(QObject, "vista")

def hijo(n, nodo=None):
    nodo = nodo or ventana.contentItem()
    for item in nodo.childItems():
        if item.objectName() == n:
            return item
        e = hijo(n, item)
        if e is not None:
            return e
    return None

def textos(nodo=None):
    out = []
    def rec(it):
        for h in it.childItems():
            if not h.isVisible():
                continue
            if h.inherits("QQuickText"):
                out.append(h.property("text"))
            rec(h)
    rec(nodo or ventana.contentItem())
    return out

def tocar(item):
    c = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(c.x(), c.y()))
    QTest.qWait(80)

r = {}
exec(cfg["pasos"])
r["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
r["enviados"] = enviados
print("RES=" + json.dumps(r, ensure_ascii=False, default=str))
"""


def _correr(qml, pasos, rutas):
    cfg = {"qml": qml, "pasos": pasos, "rutas": rutas,
           "fragmento": json.loads(FRAGMENTO_I18N.read_text(encoding="utf-8"))}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION, str(RAIZ_QML), json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=120, env=env)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[4:])


def _ventana(contenido):
    return """import QtQuick
import Tema
import "Pantallas"
Window { width: 1088; height: 1500; visible: true
  Binding { target: Escala; property: "factor"; value: 1 }
  %s }""" % contenido


# ── PRC-01 ───────────────────────────────────────────────────────────────────

_PROGRAMAS = {"programas": [
    {"numero": n, "cycle_id": f"p{n}", "nombre": f"Programa {n}", "origen": "user",
     "editable": True, "danado": n == 7, "habilitado": True, "personalizado": n > 4,
     "secciones": [{"clave": "esterilizacion", "no_se_ejecuta": False}]}
    for n in range(1, 21)]}


@pytest.mark.req("PRC-01")
def test_parametros_selector_desplegable_con_20_programas():
    pasos = r"""
sel = hijo("selectorPrograma")
r["texto_inicial"] = hijo("textoDesplegable", sel).property("text")
r["cerrado"] = not sel.property("abierto")
tocar(hijo("botonDesplegable", sel))
r["abierto"] = sel.property("abierto")
capa = hijo("capaDesplegable")
r["sobre_ventana"] = capa.parentItem() == ventana.contentItem()
lista = hijo("listaDesplegable")
r["desplaza"] = lista.property("contentHeight") > lista.property("height")
r["indicador"] = hijo("indicadorDesplazamiento").isVisible()
r["fila_1"] = hijo("programa_1") is not None
r["danado"] = any("Programa 7 ⚠" in t for t in textos(lista))
# desplazar hasta el 17 y tocarlo
lista.setProperty("contentY", lista.property("contentHeight") - lista.property("height"))
QTest.qWait(80)
tocar(hijo("programa_17"))
r["cerrado_al_elegir"] = not sel.property("abierto")
r["numero"] = vista.findChild(QObject, "parametrosCicloController").property("numero")
r["texto_elegido"] = hijo("textoDesplegable", sel).property("text")
# tocar fuera lo cierra sin elegir
tocar(hijo("botonDesplegable", sel))
QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
QTest.qWait(80)
r["cerrado_fuera"] = not sel.property("abierto")
r["numero_tras_fuera"] = vista.findChild(QObject, "parametrosCicloController").property("numero")
"""
    qml = _ventana('OpcionesParametrosCiclo { objectName: "vista"; anchors.fill: parent; edicionPermitida: true }')
    r = _correr(qml, pasos, {"GET /programas": [200, _PROGRAMAS]})
    assert r["avisos"] == [], r["avisos"]
    assert r["texto_inicial"] == "01 · Programa 1" and r["cerrado"]
    assert r["abierto"] and r["sobre_ventana"]
    assert r["desplaza"] and r["indicador"] and r["fila_1"] and r["danado"]
    assert r["cerrado_al_elegir"] and r["numero"] == 17 and r["texto_elegido"] == "17 · Programa 17"
    assert r["cerrado_fuera"] and r["numero_tras_fuera"] == 17


@pytest.mark.req("PRC-01")
def test_manejo_de_ciclos_usa_el_selector():
    pasos = r"""
m = vista
r["sel"] = hijo("selectorProgramaManejo") is not None
r["tarjeta_1"] = hijo("programaManejo_1") is not None and hijo("programaManejo_1").isVisible()
tocar(hijo("botonDesplegable", hijo("selectorProgramaManejo")))
tocar(hijo("programa_5"))
r["tarjeta_5"] = hijo("programaManejo_5") is not None and hijo("programaManejo_5").isVisible()
r["borrar_5"] = hijo("botonBorrar_5").isVisible()
m.elegirPrograma(2)
QTest.qWait(50)
r["borrar_2"] = hijo("botonBorrar_2").isVisible()
r["dup_2"] = hijo("botonDuplicar_2").property("habilitado")
m.abrirCrear()
QTest.qWait(50)
r["bases_lista"] = hijo("basesCrear").property("contentHeight") > hijo("basesCrear").property("height")
"""
    qml = _ventana('OpcionesManejoCiclos { objectName: "vista"; anchors.fill: parent }')
    r = _correr(qml, pasos, {"GET /programas": [200, _PROGRAMAS]})
    assert r["avisos"] == [], r["avisos"]
    assert r["sel"] and r["tarjeta_1"] and r["tarjeta_5"]
    assert r["borrar_5"] is True and r["borrar_2"] is False and r["dup_2"] is True
    assert r["bases_lista"] is True        # 20 bases: la lista se desplaza


@pytest.mark.req("SON-01")
def test_selector_de_entradas_rotula_monitoreo():
    pasos = r"""
c = vista.findChild(QObject, "parametrosCicloController")
c.cargarEntradas()
vista.setProperty("vista", "entradas")
QTest.qWait(80)
r["textos"] = textos()
"""
    entradas = {"entradas": ["temp_camara", "temp_2_camara"], "habilitadas": ["temp_camara", "temp_2_camara"],
                "disponibles": ["temp_camara", "temp_2_camara"], "no_en_uso": ["temp_2_camara"],
                "editable": True}
    qml = _ventana('OpcionesParametrosCiclo { objectName: "vista"; anchors.fill: parent; edicionPermitida: true }')
    r = _correr(qml, pasos, {"GET /programas": [200, _PROGRAMAS],
                             "GET /cycle/display-inputs": [200, entradas]})
    assert r["avisos"] == [], r["avisos"]
    assert [t for t in r["textos"] if "(monitoreo)" in t] == ["<b>Temperatura cámara 2 (monitoreo)</b>"],         r["textos"]


# ── MPR-01 ───────────────────────────────────────────────────────────────────

def _status(pres, avisos=None):
    s = {"machine_state": "PREPARADO", "test_mode_active": True, "estado_tarjeta": "ok",
         "card_connected": True, "sensors": {"pressure": {"camara": pres}, "temperature": {},
                                             "digital_inputs": {}, "digital_outputs": {}}}
    if avisos is not None:
        s["avisos_corte_prueba"] = avisos   # contrato de s3 (integración)
    return s


@pytest.mark.req("MPR-01")
def test_controlador_presion_y_avisos_de_corte():
    from autoclave.ui_qml.controllers import entradas_salidas_controller as es
    assert es.presion_camara(_status(250.5)) == 250.5
    assert es.presion_camara(_status(None)) is None
    assert es.presion_camara({**_status(250.0), "card_connected": False}) is None
    assert es.presion_camara(None) is None
    avisos = es.avisos_corte(_status(1, [{"causa": "puerta_abierta", "salida": "vapor_camara"},
                                         "camara_presurizada", "io.ui.aviso_salida_cortada_presion",
                                         {"motivo": "otra cosa"}, 3]))
    assert avisos == [
        {"clave": "io.ui.aviso_vapor_cortado_puerta", "salida": "vapor_camara", "texto": ""},
        {"clave": "io.ui.aviso_salida_cortada_presion", "salida": "", "texto": ""},
        {"clave": "io.ui.aviso_salida_cortada_presion", "salida": "", "texto": ""},
        {"clave": "", "salida": "", "texto": "otra cosa"},
    ]
    assert es.avisos_corte(_status(1)) == []
    # forma real que publica el backend (s3): {n, salida, codigo, aviso}
    reales = es.avisos_corte(_status(1, [
        {"n": 1, "salida": "vapor_camara", "codigo": "salida_prueba_puerta_abierta",
         "aviso": "io.ui.aviso_vapor_cortado_puerta"},
        {"n": 2, "salida": "abrir_puerta_1", "codigo": "salida_prueba_camara_presurizada",
         "aviso": "io.ui.aviso_salida_cortada_presion"}]))
    assert [(a["clave"], a["salida"]) for a in reales] == [
        ("io.ui.aviso_vapor_cortado_puerta", "vapor_camara"),
        ("io.ui.aviso_salida_cortada_presion", "abrir_puerta_1")]


@pytest.mark.req("MPR-01")
@pytest.mark.parametrize("pres", [250.0, None])
def test_cabecera_del_modo_prueba_muestra_la_presion(pres):
    pasos = r"""
c = vista.findChild(QObject, "entradasSalidasController")
vista.setProperty("segmento", "salidas")
c.actualizar()
QTest.qWait(80)
r["banner"] = hijo("bannerModoPrueba").isVisible()
r["presion"] = hijo("valorPresionModoPrueba").property("text")
r["aviso"] = hijo("avisoCorte_0") is not None and hijo("avisoCorte_0").isVisible()
r["textos"] = textos(hijo("bannerModoPrueba").parentItem())
"""
    qml = _ventana('OpcionesEntradasSalidas { objectName: "vista"; anchors.fill: parent }')
    rutas = {"GET /status": [200, _status(pres, [{"causa": "puerta", "salida": "vapor_camara"}])],
             "GET /io/channels": [200, {"DI": [], "DO": [], "temperature": [], "pressure": []}]}
    r = _correr(qml, pasos, rutas)
    assert r["avisos"] == [], r["avisos"]
    from autoclave import i18n
    from autoclave.core.runtime import unidades as u
    i18n.cargar()
    assert r["banner"] is True
    assert r["presion"] == (u.formatear_pres(250.0, "kPa") if pres is not None else "—")
    assert i18n.t("io.ui.presion_camara", "es") in r["textos"]
    assert r["aviso"] is True
    assert any(i18n.t("io.ui.aviso_vapor_cortado_puerta", "es") in t for t in r["textos"])


# ── BIT-05 ───────────────────────────────────────────────────────────────────

class _S:
    def __init__(self):
        self.rutas = []

    def enviar(self, m, r, c=None):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.rutas.append(r)
        return Resultado("ok", {"filas": [], "pagina": 1, "paginas": 1, "total": 0,
                                "usuarios": ["ana", "tomas"], "tipos": [],
                                "categorias": ["seguridad", "sistema"]}, 200)


@pytest.mark.req("BIT-05")
def test_controlador_rango_usuario_y_categoria():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.core.runtime.bitacora import CATEGORIAS
    from autoclave.ui_qml.controllers.bitacora_controller import BitacoraController
    s = _S()
    c = BitacoraController(sesion=s)
    c.cargar()
    hoy = date.today().isoformat()
    assert f"hasta={hoy}" in s.rutas[-1] and "desde=" not in s.rutas[-1]     # Hasta = hoy por omisión
    assert c.hasta == hoy and c.hastaEsHoy and c.desde == ""
    assert c.usuarios == ["ana", "tomas"]
    assert c.categorias == ["seguridad", "sistema"]           # las de la respuesta, en su orden
    c.fijarCategoria("configuracion")
    assert "categoria=configuracion" in s.rutas[-1] and "evento=" not in s.rutas[-1]
    c.fijarCategoria("no_existe")
    assert c.categoria == "" and "categoria=" not in s.rutas[-1]
    assert c.fijarDesde("2026-10-01") and "desde=2026-10-01" in s.rutas[-1]
    assert c.fijarHasta("2026-10-20") and "hasta=2026-10-20" in s.rutas[-1] and not c.hastaEsHoy
    assert not c.fijarHasta("2026-09-30") and c.mensaje == "bitacora.err_rango"
    assert not c.fijarDesde("2026-02-30") and c.mensaje == "bitacora.err_fecha"
    assert c.fijarHasta("") and c.hasta == hoy                # Sin fecha: vuelve a hoy
    c.fijarUsuario("ana")
    assert "usuario=ana" in s.rutas[-1]
    assert set(CATEGORIAS) == {"seguridad", "configuracion", "usuarios_sesion",
                               "mantenimiento_calibracion", "sistema"}


@pytest.mark.req("BIT-05")
def test_pantalla_calendario_y_desplegables():
    pasos = r"""
c = vista.findChild(QObject, "bitacoraController")
cal = vista.findChild(QObject, "calendarioBitacora")
r["filtro_hasta"] = hijo("filtroHasta") is not None
# Hasta: abre el calendario en el mes de hoy; elegir el 10 del mes anterior
tocar(hijo("filtroHasta"))
r["cal_abierto"] = cal.property("abierta")
r["cal_sobre_ventana"] = hijo("capaCalendario").parentItem() == ventana.contentItem()
mes0 = hijo("nombreMesCalendario").property("text")
tocar(hijo("mesAnterior"))
r["mes_cambia"] = hijo("nombreMesCalendario").property("text") != mes0
tocar(hijo("dia_10"))
r["cal_cerrado"] = not cal.property("abierta")
r["hasta"] = c.property("hasta")
# Desde: «Sin fecha» la deja vacía; Cancelar no cambia nada
tocar(hijo("filtroDesde"))
tocar(hijo("botonCancelarCalendario"))
r["desde_tras_cancelar"] = c.property("desde")
tocar(hijo("filtroDesde"))
tocar(hijo("mesAnterior"))
tocar(hijo("dia_3"))
r["desde"] = c.property("desde")
tocar(hijo("filtroDesde"))
tocar(hijo("botonSinFechaCalendario"))
r["desde_sin"] = c.property("desde")
tocar(hijo("filtroHasta"))
tocar(hijo("botonHoyCalendario"))
r["hasta_hoy"] = c.property("hasta")
# Usuario y Tipo: desplegables
tocar(hijo("botonDesplegable", hijo("filtroUsuario")))
tocar(hijo("usuario_tomas"))
r["usuario"] = c.property("usuario")
tocar(hijo("botonDesplegable", hijo("filtroTipo")))
r["categorias_vistas"] = textos()
tocar(hijo("categoria_usuarios_sesion"))
r["categoria"] = c.property("categoria")
"""
    datos = {"filas": [], "total": 0, "pagina": 1, "paginas": 1, "usuarios": ["ana", "tomas"],
             "tipos": []}
    qml = _ventana('OpcionesBitacora { objectName: "vista"; anchors.fill: parent }')
    r = _correr(qml, pasos, {"GET /audit_log": [200, datos]})
    assert r["avisos"] == [], r["avisos"]
    hoy = date.today()
    anterior = date(hoy.year - (hoy.month == 1), (hoy.month - 2) % 12 + 1, 10).isoformat()
    assert r["filtro_hasta"] and r["cal_abierto"] and r["cal_sobre_ventana"] and r["mes_cambia"]
    assert r["cal_cerrado"] and r["hasta"] == anterior
    assert r["desde_tras_cancelar"] == ""
    assert r["desde"] == anterior[:8] + "03"
    assert r["desde_sin"] == ""
    assert r["hasta_hoy"] == hoy.isoformat()
    assert r["usuario"] == "tomas" and r["categoria"] == "usuarios_sesion"
    rutas = [e[1] for e in r["enviados"]]
    assert any("categoria=usuarios_sesion" in x and "usuario=tomas" in x for x in rutas)
    from autoclave import i18n
    i18n.cargar()
    assert i18n.t("bitacora.categoria.usuarios_sesion", "es") in " ".join(r["categorias_vistas"])
