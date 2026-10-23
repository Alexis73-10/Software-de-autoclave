"""W10 (tanda 10, D10-4): pantalla 2 durante la instalación.

D10-4.1: sin perfil, mientras la pantalla 1 está en el asistente, la pantalla 2
muestra el Reposo (logo y reloj) con el aviso «Instalación en curso en la
pantalla 1», sin responder al toque y sin backend.
D10-4.2: al terminar la instalación, la pantalla 2 pasa sola al flujo normal
con el mismo mecanismo que la pantalla 1 (el lanzador la vuelve a abrir fuera
de la vigilancia de caídas). Con perfil válido o con una sola pantalla, nada
cambia."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from autoclave import exe_unico
from autoclave.installation import backend_guard
from autoclave.ui_qml import doble_pantalla
from autoclave.ui_qml.bridge import puente_instalacion

RAIZ = Path(__file__).resolve().parents[1]
QML_DIR = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


# ── app.py: qué abre cada pantalla según el perfil ──────────────────────

class _Corte(Exception):
    pass


def _cortar(*_a, **_k):
    raise _Corte


@pytest.fixture
def app_mod(monkeypatch):
    from autoclave.ui_qml import app as app_mod
    monkeypatch.setattr(app_mod, "QGuiApplication", MagicMock())
    monkeypatch.setattr(app_mod, "_cargar_fuentes", lambda: None)
    abiertos = []
    monkeypatch.setattr(app_mod, "_abrir_instalacion",
                        lambda a, args: abiertos.append(("asistente", args.door)) or 7)
    monkeypatch.setattr(app_mod, "_abrir_reposo_instalacion",
                        lambda a, args: abiertos.append(("reposo", args.door)) or 8)
    # flujo normal: el simulador de intro corta antes de tocar el backend
    monkeypatch.setenv("AUTOCLAVE_INTRO_SIMULACION", "normal")
    monkeypatch.setattr(app_mod, "SimuladorProgresoArranque", _cortar)
    app_mod._abiertos = abiertos
    return app_mod


def test_sin_perfil_la_pantalla_2_abre_el_reposo_de_instalacion(app_mod, monkeypatch):
    monkeypatch.setattr(app_mod, "requiere_instalacion", lambda: True)
    assert app_mod.main(["--door", "2", "--screen", "1"]) == 8
    assert app_mod._abiertos == [("reposo", 2)]


def test_sin_perfil_la_pantalla_1_sigue_abriendo_el_asistente(app_mod, monkeypatch):
    monkeypatch.setattr(app_mod, "requiere_instalacion", lambda: True)
    assert app_mod.main(["--door", "1"]) == 7
    assert app_mod._abiertos == [("asistente", 1)]


@pytest.mark.parametrize("door", [1, 2])
def test_con_perfil_valido_ninguna_pantalla_cambia(app_mod, monkeypatch, door):
    monkeypatch.setattr(app_mod, "requiere_instalacion", lambda: False)
    with pytest.raises(_Corte):           # llega al flujo normal (intro de arranque)
        app_mod.main(["--door", str(door)])
    assert app_mod._abiertos == []


def test_el_reposo_sale_solo_con_el_codigo_de_instalacion_terminada_fuera_del_exe():
    from autoclave.ui_qml import app as app_mod
    # lanzado por doble_pantalla (sin el ejecutable único): sale solo al aparecer el perfil
    assert app_mod.reposo_sale_solo({}) is True
    # bajo el ejecutable único lo cierra el lanzador al terminar el asistente
    assert app_mod.reposo_sale_solo({"AUTOCLAVE_EXE_UNICO": "1"}) is False


@pytest.mark.parametrize("falta, esperado", [(True, None),
                                             (False, doble_pantalla.CODIGO_INSTALACION_TERMINADA)])
def test_revisar_fin_de_instalacion(falta, esperado):
    from autoclave.ui_qml import app as app_mod
    salidas = []
    app_mod.revisar_fin_instalacion(lambda: falta, salidas.append)
    assert salidas == ([] if esperado is None else [esperado])


# ── QML: Reposo con el aviso, sin toque (es y en) ───────────────────────

_SCRIPT = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QPoint, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (para que la raíz llegue como QQuickWindow)
from autoclave import i18n
from autoclave.ui_qml.bridge import i18n_qml
from autoclave.ui_qml.app import _cargar_fuentes
qml_dir, idioma, captura = sys.argv[1], sys.argv[2], sys.argv[3]
i18n.cargar()
i18n.fijar_idioma(idioma)
i18n_qml.instancia._consultar = lambda: None        # sin backend: no cambia el idioma
app = QGuiApplication([])
_cargar_fuentes()
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine, QUrl.fromLocalFile(qml_dir + "/ReposoInstalacionVentana.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()
reposo = raiz.findChild(QObject, "reposoInstalacion")
aviso = raiz.findChild(QObject, "avisoInstalacion")
toques = []
reposo.tocado.connect(lambda: toques.append(1))
raiz.show()
QTest.qWait(300)
QTest.mouseClick(raiz, Qt.LeftButton, Qt.NoModifier, QPoint(raiz.width() // 2, raiz.height() // 2))
QTest.qWait(100)
if captura:
    raiz.grabWindow().save(captura)
print(json.dumps({"aviso": aviso.property("text") if aviso else None,
                  "visible": bool(aviso and aviso.property("visible")),
                  "tactil": reposo.property("tactil"), "toques": len(toques), "avisos": avisos}))
"""


def _cargar_reposo(idioma, captura=""):
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(QML_DIR), idioma, captura],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=60, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("idioma, texto", [("es", "Instalación en curso en la pantalla 1"),
                                           ("en", "Installation in progress on screen 1")])
def test_reposo_de_instalacion_muestra_el_aviso_y_no_responde_al_toque(idioma, texto):
    captura = os.environ.get("W10_CAPTURAS")
    destino = str(Path(captura) / f"pantalla2_instalacion_{idioma}.png") if captura else ""
    s = _cargar_reposo(idioma, destino)
    assert s == {"aviso": texto, "visible": True, "tactil": False, "toques": 0, "avisos": []}


_SCRIPT_REPOSO_NORMAL = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from autoclave import i18n
import autoclave.ui_qml.bridge.i18n_qml
i18n.cargar()
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(sys.argv[1])
comp = QQmlComponent(engine)
comp.setData(b'import QtQuick\nimport "Pantallas"\nItem { width: 600; height: 960; Reposo { objectName: "r"; anchors.fill: parent } }',
             QUrl.fromLocalFile(sys.argv[1] + "/x.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()
r = raiz.findChild(QObject, "r")
aviso = raiz.findChild(QObject, "avisoInstalacion")
print(json.dumps({"tactil": r.property("tactil"), "aviso_visible": bool(aviso.property("visible"))}))
"""


def test_reposo_normal_sin_cambios_tactil_y_sin_aviso():
    r = subprocess.run([sys.executable, "-c", _SCRIPT_REPOSO_NORMAL, str(QML_DIR)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=60, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"tactil": True, "aviso_visible": False}


# ── exe_unico: el lanzador abre la pantalla 2 en Reposo y luego el flujo normal ──

class _Proc:
    def __init__(self, codigo=0, pid=4321):
        self._codigo = codigo
        self.pid = pid
        self.terminado = False

    def wait(self, timeout=None):
        return self._codigo

    def poll(self):
        return None if not self.terminado else -15

    def terminate(self):
        self.terminado = True

    def kill(self):
        self.terminado = True


@pytest.fixture
def lanzador(monkeypatch):
    lanzados, procs, pantallas, perfil = [], [], [], {"falta": True}
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: None)
    monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    monkeypatch.setattr(backend_guard, "cleanup_stale_backend", lambda: None)
    monkeypatch.setattr(backend_guard, "write_backend_pid", lambda pid: None)
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: perfil["falta"])

    def vigilar(cmds, lanzar, barra=None):
        # en la vigilancia ya no debe quedar viva la pantalla 2 de Reposo
        lz.reposo_vivo_al_vigilar = [p for c, p in zip(lanzados, procs)
                                     if "--door" in c and c[c.index("--door") + 1] == "2"
                                     and p.poll() is None]
        pantallas.extend(cmds)

    monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", vigilar)
    lz = SimpleNamespace(lanzados=lanzados, procs=procs, pantallas=pantallas, perfil=perfil,
                         monkeypatch=monkeypatch, reposo_vivo_al_vigilar=None)
    return lz


def _popen_con(lz, codigo_asistente, instala):
    def popen(cmd, cwd=None, env=None):
        lz.lanzados.append(cmd)
        es_ui = cmd[cmd.index("--rol") + 1] == "ui"
        puerta = cmd[cmd.index("--door") + 1] if "--door" in cmd else None
        if es_ui and puerta == "1" and lz.perfil["falta"]:
            if instala:
                lz.perfil["falta"] = False
            p = _Proc(codigo_asistente)
        else:
            p = _Proc()
        lz.procs.append(p)
        return p
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)


def _resumen(lz):
    out = []
    for c in lz.lanzados:
        rol = c[c.index("--rol") + 1]
        out.append(rol if rol != "ui" else f"ui{c[c.index('--door') + 1]}")
    return out


def test_exe_sin_perfil_abre_la_pantalla_2_en_reposo_y_al_terminar_el_flujo_normal(lanzador):
    _popen_con(lanzador, doble_pantalla.CODIGO_INSTALACION_TERMINADA, instala=True)
    args = exe_unico._parse_args(["--monitor-puerta2", "1"])
    assert exe_unico._lanzador(args) == 0
    assert _resumen(lanzador) == ["ui1", "ui2", "backend"]     # asistente + Reposo, sin backend
    reposo_cmd, reposo = lanzador.lanzados[1], lanzador.procs[1]
    assert reposo_cmd[reposo_cmd.index("--screen") + 1] == "1"
    assert reposo.terminado                                     # cerrada al terminar el asistente
    assert lanzador.reposo_vivo_al_vigilar == []
    # flujo normal: las dos pantallas, vigiladas como siempre
    puertas = [c[c.index("--door") + 1] for c in lanzador.pantallas]
    assert puertas == ["1", "2"]


def test_exe_asistente_cerrado_sin_instalar_cierra_el_reposo_y_no_arranca_nada(lanzador):
    _popen_con(lanzador, 0, instala=False)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 1
    assert _resumen(lanzador) == ["ui1", "ui2"]
    assert lanzador.procs[1].terminado
    assert lanzador.pantallas == []


def test_exe_una_pantalla_sin_perfil_no_abre_reposo(lanzador):
    _popen_con(lanzador, doble_pantalla.CODIGO_INSTALACION_TERMINADA, instala=True)
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla"])) == 0
    assert _resumen(lanzador) == ["ui1", "backend"]
    assert len(lanzador.pantallas) == 1


def test_exe_con_perfil_valido_sin_cambios(lanzador):
    lanzador.perfil["falta"] = False
    _popen_con(lanzador, 0, instala=False)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert _resumen(lanzador) == ["backend"]
    assert len(lanzador.pantallas) == 2


def test_exe_si_el_reposo_no_se_puede_abrir_el_asistente_sigue(lanzador, monkeypatch):
    _popen_con(lanzador, doble_pantalla.CODIGO_INSTALACION_TERMINADA, instala=True)
    popen = exe_unico.subprocess.Popen

    def popen_falla_puerta2(cmd, cwd=None, env=None):
        if "--door" in cmd and cmd[cmd.index("--door") + 1] == "2" and lanzador.pantallas == [] \
                and "backend" not in _resumen(lanzador):
            raise OSError("sin recursos")
        return popen(cmd, cwd=cwd, env=env)
    monkeypatch.setattr(exe_unico.subprocess, "Popen", popen_falla_puerta2)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert _resumen(lanzador) == ["ui1", "backend"]
    assert len(lanzador.pantallas) == 2


# ── doble_pantalla: el Reposo que sale con código 3 no cuenta como caída ──

def test_doble_pantalla_reposo_terminado_no_se_relanza_ni_cuenta():
    lanzados = []
    procs = [MagicMock(), MagicMock()]
    for p in procs:
        p.poll.return_value = doble_pantalla.CODIGO_INSTALACION_TERMINADA
    t = [0.0]

    def dormir(s):
        t[0] += s

    doble_pantalla.vigilar_pantallas([["ui", "1"], ["ui", "2"]],
                                     lambda c: lanzados.append(c) or procs[len(lanzados) - 1],
                                     reloj=lambda: t[0], dormir=dormir)
    assert lanzados == [["ui", "1"], ["ui", "2"]]
