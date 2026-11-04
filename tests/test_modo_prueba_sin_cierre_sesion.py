"""Ajuste 2026-11-04 (decidido por el usuario): en modo prueba la sesión de la
ventana no se cierra por inactividad y su token se renueva; y el corte de 5 min
de OPCIONES > Entradas/Salidas solo aplica si no hay salidas ON (estado
desconocido: corta, falla cerrada)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from autoclave.cliente.session_manager import SessionManager  # noqa: E402
from autoclave.ui_qml import sesion_backend as sb  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
TOKEN = "tok-modo-prueba"
USUARIO_OK = {"token": TOKEN, "usuario": "ing1", "nombre": "Ing", "rol": "ingeniero",
              "debe_cambiar_clave": False}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()
    import gc
    gc.collect()
    QCoreApplication.processEvents()


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Transporte:
    def __init__(self):
        self.llamadas = []

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        self.llamadas.append((metodo, ruta, token))
        return 200, {"ok": True}


def _sesion(reloj):
    t = Transporte()
    return sb.SesionVentana(transporte=t, ejecutar=lambda f: f(), reloj=reloj), t


def test_fuera_de_modo_prueba_cierra_por_inactividad():
    reloj = Reloj()
    s, _ = _sesion(reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    cierres = []
    s.cierrePorInactividad.connect(lambda: cierres.append(True))
    reloj.t += sb.SESION_INACTIVIDAD_S
    s._revisar_inactividad()
    assert not SessionManager.is_authenticated() and cierres == [True]


def test_en_modo_prueba_no_cierra_y_renueva_el_token():
    reloj = Reloj()
    s, t = _sesion(reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    cierres = []
    s.cierrePorInactividad.connect(lambda: cierres.append(True))
    s.modoPrueba = True
    for _ in range(40):                         # 40 * 60 s: muy por encima del plazo
        reloj.t += 60
        s._revisar_inactividad()
    assert SessionManager.is_authenticated() and cierres == []
    renovaciones = [c for c in t.llamadas if c[1] == "/auth/sesion"]
    assert len(renovaciones) >= 2 and all(c[2] == TOKEN for c in renovaciones)
    assert not any(c[1] == "/auth/logout" for c in t.llamadas)


def test_al_salir_del_modo_prueba_el_plazo_se_reinicia():
    reloj = Reloj()
    s, _ = _sesion(reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.modoPrueba = True
    reloj.t += 10_000
    s._revisar_inactividad()
    s.modoPrueba = False                        # no cierra al instante
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()
    reloj.t += sb.SESION_INACTIVIDAD_S - 1
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()
    reloj.t += 1
    s._revisar_inactividad()
    assert not SessionManager.is_authenticated()


def test_modo_prueba_emite_cambio_solo_si_cambia():
    s, _ = _sesion(Reloj())
    avisos = []
    s.modoPruebaChanged.connect(lambda: avisos.append(s.modoPrueba))
    s.modoPrueba = False
    s.modoPrueba = True
    s.modoPrueba = True
    s.modoPrueba = False
    assert avisos == [True, False]


def test_main_qml_enlaza_modo_prueba_a_la_sesion():
    fuente = (RAIZ / "src/autoclave/ui_qml/qml/Main.qml").read_text(encoding="utf-8")
    assert 'property: "modoPrueba"' in fuente and "puente?.modoPrueba" in fuente


_GUION = r"""
import json, sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { id: r
  OpcionesEntradasSalidas { id: es; objectName: "es"; segmento: "salidas" }
  property bool unaOn: es.hayAlgunaSalidaOn([{encendida: false}, {encendida: true}, {encendida: null}])
  property bool todasOff: es.hayAlgunaSalidaOn([{encendida: false}, {encendida: false}])
  property bool desconocido: es.hayAlgunaSalidaOn([{encendida: null}, {encendida: null}])
  property bool vacia: es.hayAlgunaSalidaOn([])
  property bool sinLista: es.hayAlgunaSalidaOn(null)
  property int plazo: es.plazoInactividadMs }''', QUrl.fromLocalFile(qml_dir + "/prueba_mp.qml"))
r = c.create()
assert r is not None, c.errorString()
print(json.dumps({k: r.property(k) for k in
      ("unaOn", "todasOff", "desconocido", "vacia", "sinLista", "plazo")}))
"""


def test_corte_de_5_min_solo_sin_salidas_on_y_falla_cerrada():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
                            "PYTHONPATH": str(RAIZ / "src")})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["plazo"] == 300000
    assert d["unaOn"] is True                        # alguna ON: no corta (se rearma)
    assert d["todasOff"] is False                    # todas OFF: corta
    assert d["desconocido"] is False and d["vacia"] is False and d["sinLista"] is False  # corta


def test_temporizador_rearma_con_salida_on_y_corta_si_no():
    f = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml").read_text(
        encoding="utf-8")
    assert "if (raiz.hayAlgunaSalidaOn(control.salidas)) raiz.marcarActividad()" in f
    assert 'else control.salirModoPrueba("inactividad de la interfaz")' in f
