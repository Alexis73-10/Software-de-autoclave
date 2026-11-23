"""Modo fábrica, Etapa 1 (D-13): franja fija «MODO FÁBRICA» en Main.qml (las dos
ventanas), en todas las pantallas, incluida Ciclo en curso, solo con
/status.modo_fabrica true (UiBridge.modoFabrica). No captura toques y no tapa
contenido (en el borde inferior) de las pantallas de arranque, Preciclo y Ciclo en curso (detector de
solapes de la revisión visual, en vertical y horizontal)."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.req("D-13", "DF-03")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtTest import QTest
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  (contentItem)
    sys.path.insert(0, sys.argv[5])
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from tests.helpers.solapes_qml import FUNCION_SOLAPES, ANIMADOS, INSIGNIAS

    qml_dir, puerta, modo, tam = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    app = QGuiApplication([])
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    estado = {"maquina": "PREPARADO", "modo_fabrica": json.loads(modo)}
    ui.get_estado_global.side_effect = lambda: estado["maquina"]
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: f not in ("PARO_EMERGENCIA", "PARO_REAL")
    ui.get_cycle.return_value = {"name": "Bowie & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    ui.get_campo.side_effect = lambda clave, defecto=None: (
        estado["modo_fabrica"] if clave == "modo_fabrica" else defecto)
    puente = UiBridge(ui, door=puerta, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({"puente": puente})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ancho, alto = (int(x) for x in tam.split("x"))
    ventana.setProperty("width", ancho); ventana.setProperty("height", alto)
    ventana.show()

    comp = QQmlComponent(engine)
    comp.setData(("import QtQuick\nQtObject {\n" + FUNCION_SOLAPES + "\n}\n").encode("utf-8"),
                 QUrl.fromLocalFile(qml_dir + "/_fab_rev.qml"))
    rev = comp.create()

    def franja():
        return [o for o in ventana.findChildren(QObject) if o.objectName() == "franjaModoFabrica"][0]

    def texto():
        return [o for o in ventana.findChildren(QObject) if o.objectName() == "textoModoFabrica"][0]

    def visibles(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML") and o.property("visible")]

    def pantalla():
        QTest.qWait(800)
        if visibles("PantallaCicloEnCurso"): return "en_curso"
        if visibles("PantallaPreciclo"): return "preciclo"
        if visibles("Reposo"): return "arranque"
        return "?"

    def foto(nombre):
        f = franja()
        solapes = json.loads(QMetaObject.invokeMethod(
            rev, "solapesDesde", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", ventana.contentItem()),
            Q_ARG("QVariant", ventana.width()), Q_ARG("QVariant", ventana.height()),
            Q_ARG("QVariant", list(ANIMADOS)), Q_ARG("QVariant", list(INSIGNIAS))))
        con_franja = [s for s in solapes
                      if "FÁBRICA" in json.dumps(s, ensure_ascii=False)
                      or "FACTORY" in json.dumps(s, ensure_ascii=False)]
        punto = f.mapToItem(ventana.contentItem(), 0, 0)
        return {"pantalla": nombre, "visible": bool(f.property("visible")),
                "habilitada": bool(f.property("enabled")), "y": round(punto.y()),
                "ancho": round(f.property("width")), "alto": round(f.property("height")),
                "z": f.property("z"), "texto": texto().property("text"),
                "solapes_franja": con_franja}

    fotos = [foto(pantalla())]
    QMetaObject.invokeMethod([o for o in ventana.findChildren(QObject)
                              if o.metaObject().className().startswith("Reposo_QML")][0], "tocado")
    fotos.append(foto(pantalla()))
    estado["maquina"] = "CICLO"; puente.refrescar()
    fotos.append(foto(pantalla()))
    # el estado cambia en caliente: la franja sigue a /status
    estado["modo_fabrica"] = not estado["modo_fabrica"]; puente.refrescar(); QTest.qWait(50)
    cambio = bool(franja().property("visible"))
    print("RESULTADO=" + json.dumps({"fotos": fotos, "cambio": cambio, "avisos": avisos,
                                     "ancho_ventana": ventana.width(),
                                     "alto_ventana": ventana.height()}, ensure_ascii=False))
""")


def _correr(puerta=1, modo=True, tam="600x960"):
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", _SCRIPT, str(RAIZ_QML), str(puerta), json.dumps(modo),
         tam, str(RAIZ)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=120)
    for linea in r.stdout.splitlines():
        if linea.startswith("RESULTADO="):
            return json.loads(linea[len("RESULTADO="):])
    raise AssertionError(r.stderr[-3000:])


@pytest.mark.parametrize("puerta, tam", [(1, "600x960"), (2, "600x960"), (1, "1920x1200")])
def test_franja_visible_en_todas_las_pantallas_sin_tapar(puerta, tam):
    r = _correr(puerta, True, tam)
    assert r["avisos"] == []
    assert [f["pantalla"] for f in r["fotos"]] == ["arranque", "preciclo", "en_curso"]
    for f in r["fotos"]:
        assert f["visible"] is True, f
        assert f["habilitada"] is False, f           # no captura toques
        assert f["texto"] == "MODO FÁBRICA"
        # borde inferior del lienzo, a todo el ancho (el superior tiene el reloj)
        assert f["alto"] > 0 and f["y"] + f["alto"] == r["alto_ventana"]
        assert f["ancho"] == r["ancho_ventana"]
        assert f["z"] >= 2000
        assert f["solapes_franja"] == [], f
    assert r["cambio"] is False                      # al pasar a false desaparece


def test_sin_modo_fabrica_no_hay_franja():
    r = _correr(1, False)
    assert r["avisos"] == []
    assert all(f["visible"] is False for f in r["fotos"])
    assert r["cambio"] is True                       # al pasar a true aparece


def test_uibridge_modo_fabrica_solo_true_estricto():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge, modo_fabrica
    assert modo_fabrica(True) is True
    for v in (False, None, "true", 1, {}):
        assert modo_fabrica(v) is False
    ui = MagicMock()
    ui.connected = True
    ui.get_alarmas.return_value = []
    ui.get_cycle.return_value = None
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    valores = {"modo_fabrica": 1}
    ui.get_campo.side_effect = lambda c, d=None: valores.get(c, d)
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()
    assert puente.modoFabrica is False
    valores["modo_fabrica"] = True
    avisos = []
    puente.modoFabricaChanged.connect(lambda: avisos.append(1))
    puente.refrescar()
    assert puente.modoFabrica is True and avisos == [1]


def test_textos_de_la_franja():
    for idioma, esperado in (("es", "MODO FÁBRICA"), ("en", "FACTORY MODE")):
        datos = json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{idioma}.json")
                           .read_text(encoding="utf-8"))
        assert datos["fabrica"]["franja"] == esperado


def _luminancia(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_colores_de_la_franja_legibles_en_los_dos_temas():
    import re
    texto = (RAIZ_QML / "Tema" / "Colores.qml").read_text(encoding="utf-8")
    pares = {}
    for nombre in ("franjaFabricaFondo", "franjaFabricaTexto"):
        m = re.search(rf'{nombre}:\s*oscuro \? "(#\w{{6}})" : "(#\w{{6}})"', texto)
        assert m, nombre
        pares[nombre] = (m.group(2), m.group(1))     # (claro, oscuro)
    for i in (0, 1):
        a, b = (_luminancia(pares[n][i]) for n in ("franjaFabricaTexto", "franjaFabricaFondo"))
        contraste = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        assert contraste >= 4.5, (i, contraste)
