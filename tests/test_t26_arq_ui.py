# Tanda 26 (ARQ): lado UI del arranque retenido.
#
# - ARQ-D1: POST /arranque/iniciar sale solo con la intro empezada (primer
#   cuadro) y mientras el backend espera; solo la pantalla que avisa.
# - ARQ-D3: interfaz-lista sale solo con TODAS las etapas reales cumplidas y
#   mostradas (el «sin módulo E/S» deja terminar la intro pero no avisa) y la
#   barra nunca se adelanta al backend (avanzarVista / _cumplidas_reales).
# - ARQ-D5: backend reiniciado con la UI abierta → reenvío de iniciar e
#   interfaz-lista, con la barra de reinicio en Main.qml.

import json
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.backend.arranque.registro import RegistroArranque  # noqa: E402
from autoclave.ui_qml.bridge.progreso_arranque import ProgresoArranqueBackend  # noqa: E402

_BACKEND = ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
            "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
            "conectando_modulos_es", "verificando_sensores")


class _Backend:
    """Backend falso en memoria: un RegistroArranque real por instancia."""

    def __init__(self):
        self.registro = RegistroArranque()
        self.iniciados = 0
        self.avisos = 0

    def leer(self):
        return self.registro.instantanea()

    def iniciar(self):
        self.iniciados += 1
        self.registro.marcar_iniciado()

    def avisar(self):
        self.avisos += 1
        self.registro.marcar_interfaz_lista()

    def completar(self, hasta=None):
        for clave in _BACKEND:
            if self.registro.estado_de(clave).value == "pendiente":
                self.registro.iniciar(clave)
                self.registro.completar(clave)
            if clave == hasta:
                return

    def sin_es(self):
        """Etapas 1-6 hechas y la 7 reintentando con ARR_SIN_ES."""
        self.completar("abriendo_base_datos")
        self.registro.iniciar("conectando_modulos_es")
        self.registro.anotar("conectando_modulos_es", "ARR_SIN_ES")

    def reiniciar(self):
        self.registro = RegistroArranque()


def _progreso(b, **kw):
    return ProgresoArranqueBackend(b.leer, en_hilo=False, avisar=b.avisar,
                                   iniciar_backend=b.iniciar, **kw)


def _esperar(cond, max_s=2.0):
    import time
    fin = time.monotonic() + max_s
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


@pytest.mark.req("ARQ-D1")
def test_iniciar_solo_con_la_intro_empezada():
    b = _Backend()
    p = _progreso(b)
    p.sondear()
    p.sondear()
    assert b.iniciados == 0                      # ventana aún sin primer cuadro
    p.introIniciada()
    assert _esperar(lambda: b.iniciados == 1)
    p.sondear()                                   # ya no espera: no se repite
    assert b.iniciados == 1
    # la pantalla 2 nunca lo pide
    b2 = _Backend()
    p2 = ProgresoArranqueBackend(b2.leer, en_hilo=False)
    p2.introIniciada()
    p2.sondear()
    assert b2.iniciados == 0 and b2.registro.iniciado is False


@pytest.mark.req("ARQ-D3")
def test_sin_modulo_es_la_intro_termina_pero_no_avisa_hasta_terminar_de_verdad():
    b = _Backend()
    p = _progreso(b)
    p.introIniciada()
    b.sin_es()
    p.sondear()
    assert p.property("terminado") is True       # la intro puede salir (D-E)
    assert p.property("completo") is False       # pero sin llenar la barra
    p.avisarInterfazLista()
    p.sondear()
    assert b.avisos == 0
    b.registro.completar("conectando_modulos_es")
    p.sondear()
    assert b.avisos == 0                          # falta la etapa 8
    b.completar()
    p.sondear()
    assert _esperar(lambda: b.avisos == 1)
    assert b.registro.interfaz_lista.is_set()


@pytest.mark.req("ARQ-D3")
def test_aviso_solo_tras_el_fin_de_la_intro():
    b = _Backend()
    p = _progreso(b)
    p.introIniciada()
    b.completar()
    p.sondear()
    p.sondear()
    assert b.avisos == 0
    p.avisarInterfazLista()
    assert _esperar(lambda: b.avisos == 1)
    p.sondear()
    p.sondear()
    assert b.avisos == 1


@pytest.mark.req("ARQ-D3")
def test_la_barra_nunca_se_adelanta_al_backend():
    b = _Backend()
    p = _progreso(b)
    total = sum(e["peso"] for e in b.leer()["etapas"] if e["clave"] != "preparando_interfaz")
    vistos = []
    for hasta in _BACKEND:
        b.completar(hasta)
        p.sondear()
        p.reiniciarVista()
        for _ in range(12):
            p.avanzarVista()
            real = sum(e["peso"] for e in b.leer()["etapas"]
                       if e["clave"] != "preparando_interfaz" and e["estado"] == "ok") / total
            vistos.append((p.property("fraccion"), real))
            assert p.property("fraccion") <= real + 1e-9
            if p.property("terminado"):
                assert real == pytest.approx(1.0)
    assert vistos[-1][0] == pytest.approx(1.0)


@pytest.mark.req("ARQ-D5")
def test_reinicio_del_backend_con_la_ui_abierta_reenvia_iniciar_y_avisar():
    b = _Backend()
    p = _progreso(b, vigilar_reinicio=True)
    p.introIniciada()
    p.sondear()
    assert _esperar(lambda: b.iniciados == 1)
    b.completar()
    p.sondear()
    p.avisarInterfazLista()
    assert _esperar(lambda: b.avisos == 1)
    p.sondear()                                   # interfaz hecha: pasa a vigilancia
    assert p.property("reiniciandoBackend") is False
    instancia_vieja = b.registro.instancia

    b.reiniciar()                                 # p. ej. reasignación de E/S
    assert b.registro.instancia != instancia_vieja
    p.sondear()
    assert p.property("reiniciandoBackend") is True
    assert _esperar(lambda: b.iniciados == 2)     # reenvía iniciar (sin animación)
    p.sondear()
    b.completar("abriendo_base_datos")
    p.sondear()
    assert b.avisos == 1 and p.property("reiniciandoBackend") is True
    b.completar()
    p.sondear()
    assert _esperar(lambda: b.avisos == 2)        # y la interfaz lista
    p.sondear()
    assert p.property("reiniciandoBackend") is False
    assert b.registro.interfaz_lista.is_set()


@pytest.mark.req("ARQ-D5")
def test_backend_caido_en_vigilancia_no_cambia_nada():
    b = _Backend()
    p = _progreso(b, vigilar_reinicio=True)
    p.introIniciada()
    p.sondear()
    b.completar()
    p.sondear()
    p.avisarInterfazLista()
    assert _esperar(lambda: b.avisos == 1)
    p.sondear()
    caido = {"si": True}

    def leer():
        if caido["si"]:
            raise OSError("reiniciándose")
        return b.leer()
    p._leer = leer
    for _ in range(3):
        p.sondear()
    assert p.property("reiniciandoBackend") is False and p.property("terminado") is True
    b.reiniciar()
    caido["si"] = False
    p.sondear()
    assert p.property("reiniciandoBackend") is True


@pytest.mark.req("ARQ-D5")
def test_pantalla_2_muestra_el_reinicio_sin_mandar_nada():
    b = _Backend()
    b.completar()
    b.registro.marcar_iniciado()
    b.registro.marcar_interfaz_lista()
    p = ProgresoArranqueBackend(b.leer, en_hilo=False, vigilar_reinicio=True)
    p.introIniciada()
    p.sondear()
    b.reiniciar()
    p.sondear()
    assert p.property("reiniciandoBackend") is True
    assert b.iniciados == 0
    b.registro.marcar_iniciado()      # la puerta 1 lo pidió
    b.completar()
    b.registro.marcar_interfaz_lista()
    p.sondear()
    assert p.property("reiniciandoBackend") is False


# ── Main.qml de verdad (subproceso offscreen) ─────────────────────────────

_SCRIPT = textwrap.dedent(r"""
    import json, sys, time
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from autoclave.ui_qml.bridge.progreso_arranque import ProgresoArranqueBackend
    from autoclave.backend.arranque.registro import RegistroArranque

    qml_dir = sys.argv[1]
    qapp = QGuiApplication([])
    CLAVES = ["verificando_instalacion", "liberando_procesos", "iniciando_servicios",
              "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
              "conectando_modulos_es", "verificando_sensores"]
    estado = {"reg": RegistroArranque(), "iniciar": [], "avisos": [], "t_cumplidas": None}

    def leer():
        return estado["reg"].instantanea()

    def iniciar():
        estado["iniciar"].append(time.monotonic())
        estado["reg"].marcar_iniciado()

    def avisar():
        estado["avisos"].append((time.monotonic(), estado["reg"].terminado))
        estado["reg"].marcar_interfaz_lista()

    p = ProgresoArranqueBackend(leer, en_hilo=False, avisar=avisar, iniciar_backend=iniciar,
                                vigilar_reinicio=True, intervalo_ms=50,
                                intervalo_vigilancia_ms=100)
    avisos_qml = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos_qml.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({"versionSoftware": "1.0", "progresoArranque": p})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    t_creada = time.monotonic()
    QTest.qWait(200)
    r = {"avisos_qml": avisos_qml, "iniciar_antes_de_mostrar": len(estado["iniciar"])}
    ventana.show()
    p.iniciar()
    loader = ventana.findChild(QObject, "introArranque")
    reinicio = ventana.findChild(QObject, "reinicioBackend")
    intro = loader.property("item")

    def esperar(cond, max_s):
        fin = time.monotonic() + max_s
        while not cond() and time.monotonic() < fin:
            QTest.qWait(10)
        return cond()

    def correr_etapas(pausa_ms):
        r_ = estado["reg"]
        adelanto = []
        for c in CLAVES:
            r_.iniciar(c)
            for _ in range(max(1, pausa_ms // 20)):
                QTest.qWait(20)
                if intro is not None and loader.property("active"):
                    hechas = sum(e["peso"] for e in r_.instantanea()["etapas"]
                                 if e["clave"] != "preparando_interfaz" and e["estado"] == "ok")
                    total = sum(e["peso"] for e in r_.instantanea()["etapas"]
                                if e["clave"] != "preparando_interfaz")
                    if intro.property("fraccionMostrada") > hechas / total + 1e-6:
                        adelanto.append((c, intro.property("fraccionMostrada"), hechas / total))
            r_.completar(c)
        return adelanto

    r["iniciar"] = esperar(lambda: len(estado["iniciar"]) >= 1, 5)
    r["adelanto"] = correr_etapas(400)
    estado["t_cumplidas"] = time.monotonic()
    r["intro_termino"] = esperar(lambda: not loader.property("active"), 15)
    r["aviso"] = esperar(lambda: len(estado["avisos"]) == 1, 5)
    r["aviso_con_backend_terminado"] = estado["avisos"][0][1] if estado["avisos"] else None
    r["aviso_tras_cumplidas"] = (estado["avisos"][0][0] >= estado["t_cumplidas"]
                                 if estado["avisos"] else None)
    QTest.qWait(300)
    r["reinicio_inactivo"] = not reinicio.property("active")

    # ARQ-D5: el backend se reinicia con la pantalla abierta
    estado["reg"] = RegistroArranque()
    r["reinicio_visible"] = esperar(lambda: reinicio.property("active"), 3)
    r["reiniciar_pedido"] = esperar(lambda: len(estado["iniciar"]) >= 2, 3)
    correr_etapas(60)
    r["reaviso"] = esperar(lambda: len(estado["avisos"]) == 2, 5)
    r["reinicio_oculto"] = esperar(lambda: not reinicio.property("active"), 3)
    print("RESULTADO" + json.dumps(r))
""")


@pytest.mark.req("ARQ-D1")
@pytest.mark.req("ARQ-D3")
@pytest.mark.req("ARQ-D5")
def test_main_qml_inicia_avisa_y_muestra_el_reinicio(tmp_path):
    from autoclave.ui_qml import app
    qml_dir = str(Path(app.__file__).resolve().parent / "qml")
    script = tmp_path / "arq.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    import os
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run([sys.executable, str(script), qml_dir], capture_output=True,
                          text=True, timeout=120, env=entorno)
    linea = [x for x in proc.stdout.splitlines() if x.startswith("RESULTADO")]
    assert linea, proc.stdout[-2000:] + proc.stderr[-4000:]
    r = json.loads(linea[0][len("RESULTADO"):])
    assert r["iniciar_antes_de_mostrar"] == 0
    assert r["iniciar"] is True
    assert r["adelanto"] == []                          # la barra nunca se adelantó
    assert r["intro_termino"] is True
    assert r["aviso"] is True
    assert r["aviso_con_backend_terminado"] is True
    assert r["aviso_tras_cumplidas"] is True
    assert r["reinicio_inactivo"] is True
    assert r["reinicio_visible"] is True
    assert r["reiniciar_pedido"] is True
    assert r["reaviso"] is True
    assert r["reinicio_oculto"] is True
    errores = [a for a in r["avisos_qml"] if "BarraReinicioBackend" in a or "IntroArranque" in a]
    assert errores == []
