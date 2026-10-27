"""Tanda 18 (decisiones_tanda_18.md): arranque sin perfil e instalación.

- ARR-06: sin perfil (o inválido) la intro de arranque se ve en las dos
  pantallas antes del asistente / Reposo; la barra se detiene en
  verificando_instalacion con el motivo, lo sostiene ~2 s y termina; sin
  bitácora y sin colores de alarma (no es un fallo).
- REI-01: al terminar el asistente, cuenta regresiva de 10 s con «Reiniciar
  ahora» (sin cancelar) y el lanzador reinicia el PC con shutdown /r /t 0;
  solo en el compilado de Windows (AUTOCLAVE_REINICIO_PC=1/0); si Windows
  no reinicia, se sigue con el arranque normal.
- EST-08: se retiró la cubierta de arranque (EST-07).
"""

import builtins
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

from autoclave import exe_unico
from autoclave.ui_qml.bridge import puente_instalacion
from autoclave.ui_qml.bridge.progreso_arranque import (MENSAJE_SIN_PERFIL_MS,
                                                       ProgresoArranqueSinPerfil)

RAIZ = Path(__file__).resolve().parents[1]
QML_DIR = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── REI-01: activación y ejecución del reinicio del PC ─────────────────────

@pytest.mark.req("REI-01")
@pytest.mark.parametrize("entorno, congelado, plataforma, esperado", [
    ({}, True, "win32", True),                                  # compilado en Windows
    ({}, False, "win32", False),                                # desarrollo
    ({"AUTOCLAVE_REINICIO_PC": "1"}, False, "win32", True),     # a propósito
    ({"AUTOCLAVE_REINICIO_PC": "0"}, True, "win32", False),     # nunca
    ({"AUTOCLAVE_REINICIO_PC": "1"}, True, "linux", False),     # solo Windows
    ({}, True, "linux", False),
])
def test_reinicio_pc_activo(entorno, congelado, plataforma, esperado):
    assert exe_unico.reinicio_pc_activo(entorno, congelado=congelado, plataforma=plataforma) is esperado


class _Log:
    def __init__(self):
        self.lineas = []

    def _anotar(self, nivel, msg, *a, **k):
        self.lineas.append((nivel, msg % a if a else msg))

    def info(self, *a, **k):
        self._anotar("info", *a)

    def warning(self, *a, **k):
        self._anotar("warning", *a)

    def error(self, *a, **k):
        self._anotar("error", *a)

    def exception(self, *a, **k):
        self._anotar("exception", *a)


@pytest.mark.req("REI-01")
def test_reiniciar_pc_desactivado_no_ejecuta_nada():
    llamadas = []
    log = _Log()
    assert exe_unico.reiniciar_pc(log, activo=False, ejecutar=lambda *a, **k: llamadas.append(a)) is False
    assert llamadas == []
    assert any("desactivado" in m for _, m in log.lineas)


@pytest.mark.req("REI-01")
def test_reiniciar_pc_ejecuta_shutdown_de_system32_con_reinicio_inmediato():
    llamadas = []

    def ejecutar(cmd, **k):
        llamadas.append((cmd, k))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert exe_unico.reiniciar_pc(_Log(), activo=True, ejecutar=ejecutar) is True
    cmd, k = llamadas[0]
    assert Path(cmd[0]).name.lower() == "shutdown.exe"
    assert Path(cmd[0]).parent.name.lower() == "system32"
    assert cmd[1:] == ["/r", "/t", "0"]
    assert k["timeout"] == exe_unico.TOPE_REINICIO_PC_S


@pytest.mark.req("REI-01")
@pytest.mark.parametrize("falla", ["codigo", "excepcion", "tiempo"])
def test_reiniciar_pc_que_falla_devuelve_false_y_queda_en_el_log(falla):
    def ejecutar(cmd, **k):
        if falla == "codigo":
            return SimpleNamespace(returncode=1190, stdout="", stderr="Acceso denegado")
        if falla == "tiempo":
            raise subprocess.TimeoutExpired(cmd, k["timeout"])
        raise OSError("sin shutdown.exe")

    log = _Log()
    assert exe_unico.reiniciar_pc(log, activo=True, ejecutar=ejecutar) is False
    assert any(n in ("error", "exception") and "arranque normal" in m for n, m in log.lineas)


# ── el lanzador: asistente → reinicio, o arranque normal si no reinicia ─────

class _Proc:
    def __init__(self, pid=4321, codigo=0):
        self.pid = pid
        self._codigo = codigo

    def wait(self, timeout=None):
        return self._codigo

    def poll(self):
        return None

    def terminate(self):
        pass

    def kill(self):
        pass


@pytest.fixture
def lanzador(monkeypatch):
    from autoclave.installation import backend_guard
    from autoclave.ui_qml import doble_pantalla

    eventos = []
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: None)
    monkeypatch.setattr(exe_unico, "_tomar_instancia", lambda args: None)
    monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    monkeypatch.setattr(backend_guard, "cleanup_stale_backend", lambda: None)
    monkeypatch.setattr(backend_guard, "write_backend_pid", lambda pid: None)
    estado = {"falta": True, "codigo_asistente": doble_pantalla.CODIGO_INSTALACION_TERMINADA,
              "reinicia": True, "motivo": "sin_perfil"}
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: estado["falta"])
    monkeypatch.setattr(puente_instalacion, "motivo_instalacion", lambda: estado["motivo"])
    monkeypatch.setattr(doble_pantalla, "vigilar_pantallas",
                        lambda cmds, lanzar, barra=None, detener=None: eventos.append("pantallas"))

    def popen(cmd, cwd=None, env=None):
        rol = cmd[cmd.index("--rol") + 1]
        puerta = cmd[cmd.index("--door") + 1] if "--door" in cmd else ""
        eventos.append(f"popen:{rol}{puerta}")
        if rol == "ui" and puerta == "1" and estado["falta"]:
            codigo = estado["codigo_asistente"]
            if codigo == doble_pantalla.CODIGO_INSTALACION_TERMINADA:
                estado["falta"] = False      # el asistente escribió el perfil
            return _Proc(codigo=codigo)
        return _Proc()

    monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)

    def reiniciar(log, **k):
        eventos.append("reinicio_pc")
        return estado["reinicia"]

    monkeypatch.setattr(exe_unico, "reiniciar_pc", reiniciar)
    return SimpleNamespace(eventos=eventos, estado=estado, monkeypatch=monkeypatch)


@pytest.mark.req("REI-01")
def test_tras_el_asistente_se_reinicia_el_pc_sin_backend_ni_pantallas(lanzador):
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    ev = lanzador.eventos
    assert ev[:2] == ["popen:ui1", "popen:ui2"]           # asistente y Reposo
    assert "reinicio_pc" in ev
    assert "popen:backend" not in ev and "pantallas" not in ev


@pytest.mark.req("REI-01")
def test_si_windows_no_reinicia_sigue_el_arranque_normal(lanzador):
    lanzador.estado["reinicia"] = False
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    ev = lanzador.eventos
    assert ev.index("reinicio_pc") < ev.index("popen:backend") < ev.index("pantallas")


@pytest.mark.req("REI-01")
def test_asistente_cerrado_sin_completar_no_reinicia(lanzador):
    lanzador.estado["codigo_asistente"] = 1
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 1
    assert "reinicio_pc" not in lanzador.eventos
    assert "popen:backend" not in lanzador.eventos


@pytest.mark.req("REI-01")
def test_codigo_de_exito_con_perfil_aun_invalido_no_reinicia(lanzador, monkeypatch):
    # el lanzador comprueba además que requiere_instalacion() ya sea falso
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: True)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 1
    assert "reinicio_pc" not in lanzador.eventos


@pytest.mark.req("REI-01")
def test_con_perfil_valido_no_hay_asistente_ni_reinicio(lanzador):
    lanzador.estado["falta"] = False
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert "reinicio_pc" not in lanzador.eventos
    assert "popen:backend" in lanzador.eventos and "pantallas" in lanzador.eventos


@pytest.mark.req("ARR-06")
@pytest.mark.parametrize("motivo, texto", [("sin_perfil", "Sin perfil de instalación"),
                                           ("invalido", "Perfil de instalación inválido")])
def test_el_lanzador_anota_el_motivo_en_su_log(lanzador, caplog, motivo, texto):
    lanzador.estado["motivo"] = motivo
    with caplog.at_level("WARNING", logger="autoclave.exe_unico"):
        exe_unico._lanzador(exe_unico._parse_args([]))
    assert any(texto in r.getMessage() for r in caplog.records)


# ── EST-08: sin cubierta de arranque ─────────────────────────────────────

@pytest.mark.req("EST-08")
def test_la_cubierta_de_arranque_ya_no_existe():
    src = RAIZ / "src" / "autoclave"
    assert not (src / "estacion" / "cubierta_arranque.py").exists()
    assert not (src / "estacion" / "primer_cuadro.py").exists()
    assert (src / "estacion" / "_ventanas.py").exists()       # la usa EST-06
    for ruta in (src / "exe_unico.py", src / "ui_qml" / "app.py", RAIZ / "packaging" / "Autoclave.spec"):
        texto = ruta.read_text(encoding="utf-8")
        for prohibido in ("cubierta_arranque", "primer_cuadro", "AUTOCLAVE_CUBIERTA",
                          "AvisoPrimerCuadro", "avisar_primer_cuadro", "_abrir_cubierta"):
            assert prohibido not in texto, (ruta.name, prohibido)


@pytest.mark.req("EST-08")
def test_el_lanzador_no_importa_nada_de_la_cubierta(lanzador):
    pedidos = []
    original = builtins.__import__

    def espia(nombre, globals=None, locals=None, fromlist=(), level=0):
        pedidos.append((nombre, tuple(fromlist or ())))
        return original(nombre, globals, locals, fromlist, level)

    lanzador.estado["falta"] = False
    lanzador.monkeypatch.setattr(builtins, "__import__", espia)
    exe_unico._lanzador(exe_unico._parse_args([]))
    assert not any("cubierta" in n or "primer_cuadro" in n or "cubierta_arranque" in f
                   for n, f in pedidos)


@pytest.mark.req("EST-08")
def test_la_tarea_de_arranque_conserva_pt0s():
    for rel in ("tools/estacion/03_tarea_autoclave.ps1", "tools/instalador/tarea_arranque.ps1"):
        assert "PT0S" in (RAIZ / rel).read_text(encoding="utf-8"), rel


# ── ARR-06: motivo y fuente de progreso sin perfil ─────────────────────────

@pytest.mark.req("ARR-06")
@pytest.mark.parametrize("existe, motivo", [(False, "sin_perfil"), (True, "invalido")])
def test_motivo_instalacion(monkeypatch, existe, motivo):
    monkeypatch.setattr(puente_instalacion.storage, "exists", lambda: existe)
    assert puente_instalacion.motivo_instalacion() == motivo


@pytest.mark.req("ARR-06")
def test_motivo_instalacion_con_error_de_lectura_es_invalido(monkeypatch):
    def falla():
        raise PermissionError("sin permiso")

    monkeypatch.setattr(puente_instalacion.storage, "exists", falla)
    assert puente_instalacion.motivo_instalacion() == "invalido"


@pytest.mark.req("ARR-06")
@pytest.mark.parametrize("motivo, proceso", [("sin_perfil", "sin_perfil_instalacion"),
                                             ("invalido", "perfil_invalido_instalacion")])
def test_progreso_sin_perfil_se_detiene_con_el_motivo(motivo, proceso):
    p = ProgresoArranqueSinPerfil(motivo)
    assert p.proceso == proceso
    assert p.fraccion == 0.0
    assert p.terminado is False and p.falloBloqueante is False


@pytest.mark.req("ARR-06")
def test_progreso_sin_perfil_sostiene_el_mensaje_y_termina():
    assert MENSAJE_SIN_PERFIL_MS == 2000
    p = ProgresoArranqueSinPerfil("sin_perfil", sostener_ms=150, tope_ms=60000)
    p.iniciar()
    QTest.qWait(400)
    assert p.terminado is False            # hasta que la barra se ve, no corre el plazo
    p.reiniciarVista()
    QTest.qWait(60)
    assert p.terminado is False
    QTest.qWait(300)
    assert p.terminado is True and p.falloBloqueante is False
    p.reiniciarVista()                     # ya terminado: no cambia nada
    assert p.terminado is True


@pytest.mark.req("ARR-06")
def test_progreso_sin_perfil_termina_por_tope_aunque_nadie_lo_vea():
    p = ProgresoArranqueSinPerfil("invalido", sostener_ms=60000, tope_ms=150)
    p.iniciar()
    QTest.qWait(400)
    assert p.terminado is True


@pytest.mark.req("ARR-06")
def test_textos_nuevos_en_los_dos_idiomas():
    for idioma, esperados in (
        ("es", {"arranque.sin_perfil_instalacion": "Sin perfil de instalación: se abre el asistente",
                "arranque.perfil_invalido_instalacion": "Perfil de instalación inválido: se abre el asistente",
                "instalacion.reiniciar_ahora": "Reiniciar ahora"}),
        ("en", {"arranque.sin_perfil_instalacion": "No installation profile: opening the setup wizard",
                "arranque.perfil_invalido_instalacion": "Invalid installation profile: opening the setup wizard",
                "instalacion.reiniciar_ahora": "Restart now"}),
    ):
        cat = json.loads((RAIZ / f"src/autoclave/i18n/{idioma}.json").read_text(encoding="utf-8"))
        for clave, texto in esperados.items():
            sec, nombre = clave.split(".")
            assert cat[sec][nombre] == texto, (idioma, clave)
        assert "{segundos}" in cat["instalacion"]["reinicio_cuenta"]


# ── QML: intro encima del asistente / Reposo y cuenta regresiva ────────────

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickWindow  # noqa: F401
from autoclave import i18n
import autoclave.ui_qml.bridge.i18n_qml as i18n_qml
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion
from autoclave.ui_qml.bridge.progreso_arranque import ProgresoArranqueSinPerfil
from autoclave.ui_qml.app import QML_DIR

ventana_qml, idioma = sys.argv[1], sys.argv[2]
i18n.cargar()
i18n.fijar_idioma(idioma)
i18n_qml.instancia._consultar = lambda: None
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(QML_DIR)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
progreso = ProgresoArranqueSinPerfil("sin_perfil", sostener_ms=300)
progreso.iniciar()
props = {"progresoArranque": progreso, "versionSoftware": "1.0.0-alpha.3"}
if ventana_qml == "InstalacionVentana.qml":
    props["puenteInstalacion"] = PuenteInstalacion(validar_codigo=lambda s, c: False)
comp = QQmlComponent(engine, QUrl.fromLocalFile(QML_DIR + "/" + ventana_qml))
raiz = comp.createWithInitialProperties(props)
assert raiz is not None, comp.errorString()
raiz.show()
obs = {}
loader = raiz.findChild(QObject, "introArranqueInstalacion") or raiz.findChild(QObject, "introArranqueReposo")
QTest.qWait(4200)                 # 3,5 s de animación: la barra ya se ve
intro = loader.property("item")
texto = intro.findChild(QObject, "procesoArranque") if intro else None
obs["intro_activa_al_inicio"] = bool(loader.property("active"))
obs["proceso"] = texto.property("text") if texto else None
for _ in range(60):               # sostener 0,3 s + salida 1 s
    if not loader.property("active"):
        break
    QTest.qWait(100)
obs["intro_activa_al_final"] = bool(loader.property("active"))
if ventana_qml == "InstalacionVentana.qml":
    a = raiz.findChild(QObject, "asistenteInstalacion")
    a.setProperty("terminado", True)
    QTest.qWait(100)
    obs["boton"] = a.findChild(QObject, "botonContinuar").property("texto")
    obs["reinicio_10"] = a.findChild(QObject, "textoReinicio").property("text")
    QTest.qWait(2150)
    obs["restantes"] = a.property("segundosRestantes")
else:
    raiz.setProperty("instalacionTerminada", True)
    QTest.qWait(1150)
    obs["aviso"] = raiz.findChild(QObject, "avisoInstalacion").property("text")
obs["avisos"] = avisos[:10]
print("RESULTADO=" + json.dumps(obs, ensure_ascii=False))
"""


def _correr(ventana, idioma="es"):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, ventana, idioma],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


@pytest.mark.req("ARR-06")
@pytest.mark.req("REI-01")
def test_asistente_tras_la_intro_y_cuenta_regresiva():
    r = _correr("InstalacionVentana.qml")
    assert r["avisos"] == []
    assert r["intro_activa_al_inicio"] is True
    assert r["proceso"] == "Sin perfil de instalación: se abre el asistente"
    assert r["intro_activa_al_final"] is False
    assert r["boton"] == "Reiniciar ahora"
    assert r["reinicio_10"] == "Instalación completada. El equipo se reiniciará en 10 s"
    assert r["restantes"] in (7, 8)        # la cuenta corre (1 s por paso)


@pytest.mark.req("ARR-06")
@pytest.mark.req("REI-01")
def test_reposo_tras_la_intro_y_aviso_de_reinicio_en_ingles():
    r = _correr("ReposoInstalacionVentana.qml", "en")
    assert r["avisos"] == []
    assert r["intro_activa_al_inicio"] is True
    assert r["proceso"] == "No installation profile: opening the setup wizard"
    assert r["intro_activa_al_final"] is False
    assert r["aviso"] == "Installation complete. The equipment will restart in 9 s"


@pytest.mark.req("REI-01")
def test_avisar_fin_instalacion_marca_la_ventana_solo_con_perfil_valido():
    from autoclave.ui_qml import app as app_mod
    props = {}
    ventana = SimpleNamespace(setProperty=lambda k, v: props.__setitem__(k, v))
    assert app_mod.avisar_fin_instalacion(lambda: True, ventana) is False
    assert props == {}
    assert app_mod.avisar_fin_instalacion(lambda: False, ventana) is True
    assert props == {"instalacionTerminada": True}
