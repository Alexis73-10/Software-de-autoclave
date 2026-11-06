"""Tanda 26 (ALD): toda fila de alarma, alerta, aviso o fallo abre su detalle.

(a) cada FilaAlarma y cada delegado de lista de alarmas en QML es tocable o
    figura en una excepción justificada;
(b) cada alarma del catálogo tiene título y acción en es y en;
(c) el detalle de NO ABRIR por temperatura alta muestra valor medido y límite
    (en Python y tocando la fila en QML).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

# Excepciones justificadas (ruta relativa a qml/ -> motivo)
EXCEPCIONES_DELEGADOS = {
    "Componentes/PanelFinCiclo.qml": "FilaAcordeon: la causa se despliega en línea en el mismo panel (FC-13)",
    "Pantallas/OpcionesEntradasSalidas.qml": "avisos de corte del modo prueba: pantalla de otro frente "
                                             "(T26-SMP); pendiente de abrir detalle",
}


# ── (a) QML ─────────────────────────────────────────────────────────────────

def _bloques_filaalarma(texto):
    """Cuerpos de cada `FilaAlarma { ... }` (llaves balanceadas)."""
    for m in re.finditer(r"\bFilaAlarma\s*\{", texto):
        i, nivel = m.end(), 1
        while i < len(texto) and nivel:
            nivel += {"{": 1, "}": -1}.get(texto[i], 0)
            i += 1
        yield texto[m.end():i - 1]


def test_toda_filaalarma_es_tocable():
    total = 0
    for f in QML.rglob("*.qml"):
        if f.name.startswith("_") or f.name == "FilaAlarma.qml":
            continue
        for cuerpo in _bloques_filaalarma(f.read_text(encoding="utf-8")):
            total += 1
            assert re.search(r"\btocable:\s*true\b", cuerpo), f"{f.name}: FilaAlarma sin tocable"
            assert "onPulsada" in cuerpo, f"{f.name}: FilaAlarma tocable sin onPulsada"
    assert total >= 9          # hotfix ES: sin la fila «estado seguro en curso»


def test_listas_de_alarmas_abren_el_detalle():
    esperados = {
        "Componentes/PanelNotificaciones.qml": "abrirDesde(model)",
        "Pantallas/PantallaPreciclo.qml": "abrirDesde(fila.model)",
        "Componentes/ListaAlarmasPeriodo.qml": "alarmaElegida",
        "Componentes/SeccionEstadoSeguro.qml": "abrirDetalle(",
        "Main.qml": "detalleArranque.abrirDesde",
    }
    for ruta, huella in esperados.items():
        assert huella in (QML / ruta).read_text(encoding="utf-8"), ruta
    for ruta in EXCEPCIONES_DELEGADOS:
        assert (QML / ruta).exists()


# ── (b) catálogo ────────────────────────────────────────────────────────────

def test_catalogo_con_titulo_y_accion_en_es_y_en():
    from autoclave import i18n
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    faltan = []
    for idioma in i18n.IDIOMAS:
        for codigo in CATALOGO:
            e = i18n.valor(f"alarmas.{codigo}", idioma)
            for campo in ("titulo", "accion"):
                if not isinstance(e, dict) or not str(e.get(campo, "")).strip():
                    faltan.append(f"{idioma}:{codigo}.{campo}")
    assert not faltan, faltan


def test_textos_de_filas_sinteticas_en_es_y_en():
    from autoclave import i18n
    from autoclave.ui_qml.domain import detalle_aviso as d
    ctx = {"noAbrir": {"codigo": "temp_alta", "valores": {"temp": 99.0},
                       "limites": {"temp_max_apertura": 60.0}}}
    for clave in d.CLAVES:
        fila = d.armar(clave, ctx)
        assert fila["id"] and fila["sintetica"] is True
        for idioma in i18n.IDIOMAS:
            for campo in ("titulos", "descripciones", "acciones"):
                texto = fila[campo][idioma]
                assert texto.strip(), (clave, idioma, campo)
                assert not texto.startswith(("aviso_detalle.", "sistema.")), (clave, idioma)
    for motivo in d.MOTIVOS_NO_ABRIR:
        for idioma in i18n.IDIOMAS:
            assert i18n.existe(f"aviso_detalle.no_abrir_motivos.{motivo}.descripcion", idioma)
            assert i18n.existe(f"aviso_detalle.no_abrir_motivos.{motivo}.accion", idioma)


# ── (c) NO ABRIR con temp_alta ─────────────────────────────────────────────

_CTX = {"noAbrir": {"codigo": "temp_alta", "valores": {"temp": 87.4},
                    "limites": {"temp_max_apertura": 60.0, "presion_atmosferica": 74.6,
                                "rango_presion_atm": 5.0},
                    "motivo": "Temperatura demasiado alta (87 °C)", "textos": {}},
        "apariciones": {"no_abrir": "2026-11-05T10:00:00"}}


@pytest.mark.parametrize("idioma,fragmento", [("es", "Límite para abrir"), ("en", "Limit to open")])
def test_no_abrir_temp_alta_muestra_valor_y_limite(idioma, fragmento):
    from autoclave.ui_qml.domain import detalle_aviso as d
    fila = d.armar("no_abrir", _CTX)
    texto = fila["descripciones"][idioma]
    assert fragmento in texto and "87.4" in texto and "60.0" in texto
    assert "60.0" in fila["acciones"][idioma]
    assert fila["aparecida"] == "2026-11-05T10:00:00"
    assert fila["codigo"] == "NO_ABRIR" and fila["level"] == "FALLA"


def test_no_abrir_sobrepresion_muestra_rango():
    from autoclave.ui_qml.domain import detalle_aviso as d
    ctx = {"noAbrir": dict(_CTX["noAbrir"], codigo="sobrepresion", valores={"pres": 250.0},
                           limites={"presion_atmosferica": 75.0, "rango_presion_atm": 5.0})}
    t = d.armar("no_abrir", ctx)["descripciones"]["es"]
    assert "250" in t and "70" in t and "80" in t


def test_limite_ausente_no_inventa_numero():
    from autoclave.ui_qml.domain import detalle_aviso as d
    ctx = {"noAbrir": {"codigo": "temp_alta", "valores": {"temp": 80.0}, "limites": {}}}
    assert "—" in d.armar("no_abrir", ctx)["descripciones"]["es"]


def test_clave_desconocida_y_contexto_malo_no_lanzan():
    from autoclave.ui_qml.domain import detalle_aviso as d
    assert d.armar("nada") == {}
    assert d.armar("no_abrir", None)["id"] == "NO_ABRIR"
    assert d.armar("no_abrir", {"noAbrir": "x"})["id"] == "NO_ABRIR"


def test_apariciones():
    from autoclave.ui_qml.domain import detalle_aviso as d
    a = d.actualizar_apariciones({}, {"paro"}, "t1")
    assert d.actualizar_apariciones(a, {"paro", "no_abrir"}, "t2") == {"no_abrir": "t2", "paro": "t1"}
    assert d.actualizar_apariciones(a, set(), "t3") == {}
    assert d.claves_activas({}, conectado=False) == {"sin_conexion"}


def test_limites_publicados_en_status(monkeypatch):
    from types import SimpleNamespace

    from autoclave.backend import server  # noqa: F401  (orden de carga)
    from autoclave.backend.rutas import sistema

    class Cfg:
        def get(self, k):
            return {"temp_max_apertura": 80.0, "presion_admosferica": 75.0,
                    "rango_presion_atm": 5.0}.get(k)

    monkeypatch.setattr(sistema, "context", SimpleNamespace(config_manager=Cfg()))
    assert sistema._limites_camara_segura(60.0)["temp_max_apertura"] == 60.0
    assert sistema._limites_camara_segura(None)["temp_max_apertura"] == 80.0
    assert sistema._limites_camara_segura(None)["rango_presion_atm"] == 5.0


# ── QML: tocar la fila NO ABRIR abre el detalle con valor y límite ──────────

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QUrl, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
import autoclave.ui_qml.bridge.i18n_qml
import autoclave.ui_qml.bridge.detalle_aviso_qml
from autoclave import i18n
i18n.cargar(); i18n.fijar_idioma("es")
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine(); engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(sys.argv[2].encode(), QUrl.fromLocalFile(qml_dir + "/prueba_t26_ald.qml"))
v = comp.create()
assert v is not None, comp.errorString()
v.show(); QTest.qWait(200)
def rec(it, nombre):
    for h in it.childItems():
        if h.objectName() == nombre and h.isVisible():
            return h
        e = rec(h, nombre)
        if e:
            return e
fila = rec(v.contentItem(), "areaFilaAlarma")
c = fila.mapToScene(fila.boundingRect().center()).toPoint()
QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(c.x(), c.y())); QTest.qWait(400)
out = []
def tx(it):
    for h in it.childItems():
        if h.isVisible() and h.inherits("QQuickText"):
            out.append(h.property("text"))
        tx(h)
tx(v.contentItem())
print("RES=" + json.dumps({"textos": out, "avisos": avisos}, ensure_ascii=False))
"""

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 1200; height: 1920; visible: true
    Binding { target: Escala; property: "factor"; value: 1 }
    QtObject {
        id: puente
        property bool noAbrir: true
        property string noAbrirMotivo: "Temperatura demasiado alta (87 °C)"
        property bool noAbrirPorSensor: false
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool modoPrueba: false
        property bool connected: true
        property string estadoModuloEs: "ok"
        property var contextoAviso: ({ "noAbrir": { "codigo": "temp_alta", "valores": { "temp": 87.4 },
            "limites": { "temp_max_apertura": 60.0 }, "motivo": "", "textos": {} },
            "apariciones": { "no_abrir": "2026-11-05T10:00:00" } })
    }
    SeccionEstadoSeguro { puente: puente; grupo: "alarma"; width: 1000 }
}
"""


def test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite():
    pytest.importorskip("PySide6")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(RAIZ / "src"))
    p = subprocess.run([sys.executable, "-c", _SCRIPT, str(QML), _QML], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, env=env)
    linea = [x for x in p.stdout.splitlines() if x.startswith("RES=")]
    assert linea, p.stdout + p.stderr
    r = json.loads(linea[0][4:])
    todo = " | ".join(r["textos"])
    assert "Detalle de la alarma" in todo, todo
    assert "Temperatura de la cámara: 87.4" in todo and "60.0" in todo, todo
    assert "2026-11-05 10:00:00" in todo, todo
    assert not [a for a in r["avisos"] if "SeccionEstadoSeguro" in a or "VentanaDetalle" in a], r["avisos"]
