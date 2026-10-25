# tests/o11_capturas_banco.py
#
# O11 (tanda 11, D11-7): capturas antes/después de Opciones › Parámetros del
# ciclo › Entradas mostradas, Preciclo y Ciclo en curso, en es y en. No lo
# recoge pytest. Reutiliza el banco CAP9: tests/opciones_qml_banco.py para
# Opciones; para Preciclo y Ciclo carga la pantalla sola con un UiBridge real
# sobre un UIServiceBackend simulado (como la parte "preciclo" de
# tests/cap9_capturas_banco.py).
#
# Caso: programa con la asignación de fábrica (Principal = Cámara 1, resto No
# en uso) y un JSON viejo con entradas_mostradas = [temp_camara,
# temp_referencia, pres_camara]. Antes: la fila de Referencia sale con "—".
# Después: el backend ya filtra la lista y la pantalla tampoco muestra la fila.
#
#   PYTHONPATH=<worktree>/src python -X utf8 tests/o11_capturas_banco.py antes
#   PYTHONPATH=<worktree>/src python -X utf8 tests/o11_capturas_banco.py despues

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
DESTINO = RAIZ / "docs" / "informes" / "tanda11" / "capturas" / "o11"
IDIOMAS = ("es", "en")

_SCRIPT_PANTALLA = textwrap.dedent(r'''
    import json, os, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  (grabWindow)
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.cliente.ui_service_backend import UIServiceBackend

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None

    sensors = {"temperature": {"camara": 134.2, "ref": 120.5},
               "pressure": {"camara": 310.4, "chaqueta": 250.0}}
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = cfg["estado"]
    ui.get_estado_flag.return_value = False
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_sensores_temp.return_value = {"temp_camara": 134.2, "temp_ref": 120.5}
    ui.get_sensores_pres.return_value = {"pres_camara": 310.4}
    campos = {"sensors": sensors, "estado_tarjeta": "ok", "no_abrir": False}
    ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
    ui.get_cycle.return_value = cfg["ciclo"]
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        width: 1200; height: 1920; visible: true
        %s { anchors.fill: parent; puente: puenteReal }
    }
    """ % cfg["pantalla"]
    ruta = f"{QML_DIR}/_prueba_o11_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.rootContext().setContextProperty("puenteReal", puente)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(900)
    w.grabWindow().save(cfg["archivo"])
    print("RESULTADO=" + json.dumps({"filas": [f["clave"] + "=" + f["valor"] for f in puente.entradasMostradas],
                                     "avisos": [a for a in avisos if "Binding loop" not in a][:10]},
                                    ensure_ascii=False))
''')


def _ciclo_de(momento: str) -> dict:
    """GET /cycle tal como lo arma el backend en cada momento."""
    viejo = ["temp_camara", "temp_referencia", "pres_camara"]
    no_en_uso = ["temp_2_camara", "temp_referencia"]
    if momento == "antes":
        return {"name": "Instrumental 134", "number": 2, "entradas_mostradas": viejo,
                "entradas_no_en_uso": no_en_uso}
    from types import SimpleNamespace
    from autoclave.core.managers import gestion_programas as gp
    prog = SimpleNamespace(sensores=None, entradas_mostradas=viejo)
    habilitadas = ["temp_camara", "temp_2_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]
    return {"name": "Instrumental 134", "number": 2,
            "entradas_mostradas": gp.entradas_de(prog, habilitadas),
            "entradas_no_en_uso": gp.entradas_no_en_uso(prog)}


def _pantallas(momento: str) -> int:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    fallos = 0
    for idioma in IDIOMAS:
        for pantalla, estado, corto in (("PantallaPreciclo", "PREPARADO", "preciclo"),
                                        ("PantallaCicloEnCurso", "CICLO", "ciclo")):
            cfg = {"idioma": idioma, "pantalla": pantalla, "estado": estado,
                   "ciclo": _ciclo_de(momento),
                   "archivo": str(DESTINO / f"O11_{momento}_{idioma}_{corto}.png")}
            p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_PANTALLA, json.dumps(cfg)],
                               capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                               timeout=180)
            linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
            fallos += linea is None
            print(momento, idioma, corto, linea or (p.stdout[-2000:] + p.stderr[-3000:]))
    return fallos


_PROGRAMAS = {"programas": [
    {"numero": 2, "cycle_id": "134_instrumental", "nombre": "Instrumental 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False,
     "secciones": [{"clave": "globals"}, {"clave": "esterilizacion"}]}]}


def _opciones(momento: str) -> int:
    from tests import opciones_qml_banco as banco
    habilitadas = ["temp_camara", "temp_2_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]
    entradas = {"programa": 2, "entradas": _ciclo_de(momento)["entradas_mostradas"],
                "habilitadas": habilitadas, "editable": True}
    if momento == "despues":
        entradas["disponibles"] = ["temp_camara", "pres_camara", "pres_chaqueta"]
    rutas = {"GET /programas": (200, _PROGRAMAS), "GET /cycle/display-inputs": (200, entradas)}
    fallos = 0
    for idioma in IDIOMAS:
        pasos = f'''
        from autoclave import i18n as _i18n
        _i18n.fijar_idioma({idioma!r}); esperar(100)
        raiz.setProperty("seccionActiva", "parametros_ciclo"); esperar(500)
        p = buscar("parametrosCiclo")
        buscar("filaEntradas", p).pulsada.emit(); esperar(400)
        capturar("O11_{momento}_{idioma}_opciones_1_entradas.png")
        if {momento!r} == "despues":
            buscar("filaEntrada_2", p).pulsada.emit(); esperar(400)
            capturar("O11_{momento}_{idioma}_opciones_2_desplegable.png")
        salida["ok"] = True
        '''
        r = banco.correr("tecnico", pasos, rutas=rutas, capturas=True, dir_capturas=DESTINO)
        fallos += not r.get("ok")
        print(momento, idioma, "opciones", "avisos:", r["avisos"])
    return fallos


if __name__ == "__main__":
    import autoclave
    print("autoclave:", autoclave.__file__)
    DESTINO.mkdir(parents=True, exist_ok=True)
    momento = sys.argv[1] if len(sys.argv) > 1 else "despues"
    sys.exit(1 if (_opciones(momento) + _pantallas(momento)) else 0)
