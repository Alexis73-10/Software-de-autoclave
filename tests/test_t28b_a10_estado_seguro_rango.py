"""A10 (tanda 28, flujo B; Cristian, 5-nov): el estado seguro no terminaba tras
ampliar `rango_presion_atm` en Parámetros del equipo.

Diagnóstico con un protocolo real (ControlLoop + ProtocoloEstadoSeguro +
ProtocoloFallo + ConfigManager con base) y el cambio por la API
(PATCH /global_params/rango_presion_atm, la ruta real; el prompt dice PUT):

- (d) valor cacheado, (e) ConfirmadorApagado / venteo y (f) campo de /status
  que no se recalcula: DESCARTADOS, el protocolo termina a los 3 ticks.
- (a) modo prueba, (b) temperatura alta y (c) AI vencida / sonda sin lectura:
  el protocolo, correctamente, no termina; la fila de estado seguro solo
  decía «Llevando la cámara a estado seguro» (NO ABRIR se oculta mientras el
  estado seguro está en curso), así que parecía colgado. Se corrige la
  presentación: «En pausa: modo prueba activo» o el motivo pendiente con su
  valor y su límite.

Criterio de cámara segura y 3 ticks sin cambio.
"""

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_s9_estado_seguro_arranque import _loop as _loop_s9, _programa, _tick_es
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"
ATM = 75.0          # presion_atmosferica de fábrica (solo lectura)


# ── montaje: ConfigManager real con base, loop real, API real ──────────────

@pytest.fixture
def equipo(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(db_path=tmp_path / "t.db")
    cm = ConfigManager()
    cm.load_config()
    cm.vincular_bd(db)
    cm.fijar("rango_presion_atm", 1, "prueba")              # el rango estrecho del equipo
    assert cm.get("presion_admosferica") == ATM
    loop = _loop_s9()
    loop.config_manager = cm
    loop.estado_seguro.config = cm                           # el mismo objeto vivo que la API
    ctx = MagicMock()
    ctx.db = db
    ctx.config_manager = cm
    ctx.control_loop = loop
    ctx.estado = loop.estado
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), srv, loop, cm
    db.close()


def _arrancar(loop, pres, temp=60.0, programa=None):
    loop.estado.sensores_pres["pres_camara"] = pres
    loop.estado.sensores_temp["temp_camara"] = temp
    loop.recuperar_ciclo_interrumpido(programa or _programa(temp_max=80.0))
    loop._procesar_recuperacion()


def _status():
    return modulo_backend("rutas.sistema")._estado_seguro_status()


def _patch_rango(client, srv, valor):
    r = client.patch("/global_params/rango_presion_atm", json={"valor": valor},
                     headers=cabecera(srv, "tecnico"))
    assert r.status_code == 200, r.text
    return r


# ── 1. diagnóstico: el cambio de rango en vuelo termina en 3 ticks ─────────

@pytest.mark.parametrize("pres, codigo", [(78.0, "sobrepresion"), (72.0, "vacio")])
def test_cambio_de_rango_durante_el_protocolo_termina_en_tres_ticks(equipo, pres, codigo):
    client, srv, loop, cm = equipo
    _arrancar(loop, pres)
    es = loop.estado_seguro
    assert es.activo, "con rango 1 kPa la cámara a 78/72 kPa no es segura"
    _tick_es(loop, 5)
    assert es.activo
    assert es.motivo_pendiente["codigo"] == codigo
    assert _status()["motivo_pendiente"]["limites"]["rango_presion_atm"] == 1.0
    _patch_rango(client, srv, 5)                             # 70–80 kPa: la cámara queda dentro
    assert cm.get("rango_presion_atm") == 5.0                # (d) ConfigManager.get da el nuevo
    _tick_es(loop, 2)
    assert es.activo                                         # 3 ticks seguidos, no menos
    assert es.motivo_pendiente is None                       # ya no queda motivo
    _tick_es(loop)
    assert not es.activo                                     # (d)(e) termina al tercero
    st = _status()                                           # (f) /status se recalcula
    assert st["activo"] is False and st["motivo_pendiente"] is None


def test_status_y_puente_dejan_de_mostrar_el_estado_seguro(equipo):
    """(f): /status.estado_seguro y el puente QML dejan la fila en el mismo tick."""
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    _tick_es(loop)
    assert UiBridge._seguridad_de({"estado_seguro": _status()})["es_activo"] is True
    _patch_rango(client, srv, 5)
    _tick_es(loop, 3)
    assert UiBridge._seguridad_de({"estado_seguro": _status()})["es_activo"] is False


def test_venteo_del_protocolo_no_retiene_el_estado_seguro(equipo):
    """(e): con el protocolo real venteando (solo la lenta, sobrepresión) el
    fin depende solo de cámara segura 3 ticks; ni el venteo ni ningún
    ConfirmadorApagado lo retienen."""
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    _tick_es(loop, 3)
    assert loop.estado_seguro.activo
    prot = loop.estado_seguro._protocolo
    _patch_rango(client, srv, 5)
    _tick_es(loop, 3)
    assert not loop.estado_seguro.activo
    assert prot.ejecutado and getattr(prot, "_ejecutado", True)


def test_tambien_un_cambio_de_atmosferica_rige_en_vuelo(equipo):
    """(d): la atmosférica tampoco se copia (la fija la calibración O2f)."""
    _client, _srv, loop, cm = equipo
    _arrancar(loop, 78.0)
    _tick_es(loop, 3)
    assert loop.estado_seguro.activo
    cm.aplicar_valor("presion_atmosferica", 78.0, "calibracion")
    _tick_es(loop, 3)
    assert not loop.estado_seguro.activo


# ── 2. (a) modo prueba: pausa visible y termina al salir ───────────────────

def test_modo_prueba_muestra_la_pausa_y_termina_al_salir(equipo):
    from autoclave.ui_qml.domain import detalle_aviso
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    _tick_es(loop)
    ok, motivo = loop.enter_test_mode()
    assert ok is True, motivo
    _patch_rango(client, srv, 5)                 # la cámara ya es segura con el nuevo rango
    es = loop.estado_seguro
    # en modo prueba la máquina de estados no corre: no se cuentan ticks
    assert es.activo and es.en_pausa_modo_prueba is True
    st = _status()
    assert st["en_pausa_modo_prueba"] is True and st["motivo_pendiente"] is None
    seg = UiBridge._seguridad_de({"estado_seguro": st})
    ctx = {"pausaPrueba": seg["es_pausa_prueba"], "pendiente": seg["es_pendiente"],
           "causa": seg["es_causa"]}
    assert detalle_aviso.texto_espera(ctx, "es") == "En pausa: modo prueba activo"
    assert detalle_aviso.texto_espera(ctx, "en") == "Paused: test mode active"
    fila = detalle_aviso.armar("estado_seguro_en_curso", ctx)        # detalle ALD
    assert "En pausa: modo prueba activo" in fila["descripciones"]["es"]
    assert "Paused: test mode active" in fila["descripciones"]["en"]
    loop.exit_test_mode()
    _tick_es(loop)
    assert es.en_pausa_modo_prueba is False
    _tick_es(loop, 2)
    assert not es.activo                         # termina solo, 3 ticks tras salir


# ── 3. (b) temperatura alta: no termina y el detalle lo dice ───────────────

def test_temperatura_alta_no_termina_y_el_detalle_nombra_valor_y_limite(equipo):
    from autoclave.ui_qml.domain import detalle_aviso
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0, temp=92.0)
    _patch_rango(client, srv, 5)
    _tick_es(loop, 10)
    es = loop.estado_seguro
    assert es.activo                                         # correcto: la carga sigue caliente
    st = _status()
    assert st["motivo_pendiente"]["codigo"] == "temp_alta"
    assert st["motivo_pendiente"]["limites"]["temp_max_apertura"] == 80.0
    seg = UiBridge._seguridad_de({"estado_seguro": st})
    ctx = {"pausaPrueba": seg["es_pausa_prueba"], "pendiente": seg["es_pendiente"]}
    assert "Temperatura 92.0 °C, límite 80.0 °C" in detalle_aviso.texto_espera(ctx, "es")
    assert "Temperature 92.0 °C, limit 80.0 °C" in detalle_aviso.texto_espera(ctx, "en")
    fila = detalle_aviso.armar("estado_seguro_en_curso", ctx)
    assert "Temperatura 92.0 °C, límite 80.0 °C" in fila["descripciones"]["es"]
    loop.estado.sensores_temp["temp_camara"] = 70.0
    _tick_es(loop, 3)
    assert not es.activo


def test_limite_de_temperatura_es_el_menor_con_el_del_programa(equipo):
    from autoclave.ui_qml.domain import detalle_aviso
    _client, _srv, loop, _cm = equipo
    _arrancar(loop, 78.0, temp=70.0, programa=_programa(temp_max=60.0))
    _tick_es(loop)
    pend = _status()["motivo_pendiente"]
    assert pend["codigo"] in ("sobrepresion", "temp_alta")
    loop.estado.sensores_pres["pres_camara"] = ATM
    _tick_es(loop)
    pend = _status()["motivo_pendiente"]
    assert pend["codigo"] == "temp_alta" and pend["limites"]["temp_max_apertura"] == 60.0
    assert "límite 60.0 °C" in detalle_aviso.texto_espera({"pendiente": pend}, "es")


# ── (c) AI vencida o sonda sin lectura: correcto, y el detalle lo dice ─────

def test_ai_vencida_no_termina_y_lo_dice(equipo):
    from autoclave.ui_qml.domain import detalle_aviso
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    _patch_rango(client, srv, 5)
    loop.link.edad_ultima_ai.return_value = 30.0             # trama AI vencida
    _tick_es(loop, 6)
    assert loop.estado_seguro.activo
    pend = _status()["motivo_pendiente"]
    assert pend["codigo"] == "sin_presion_camara"
    assert detalle_aviso.texto_espera({"pendiente": pend}, "es") == \
        "Pendiente: Presión de cámara sin lectura"


def test_principal_sin_lectura_no_termina_y_lo_dice(equipo):
    from autoclave.ui_qml.domain import detalle_aviso
    client, srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    _patch_rango(client, srv, 5)
    loop.estado.sensores_temp["temp_camara"] = None
    _tick_es(loop, 6)
    assert loop.estado_seguro.activo
    pend = _status()["motivo_pendiente"]
    assert pend["codigo"] == "sin_temp_camara"
    assert "sin lectura" in detalle_aviso.texto_espera({"pendiente": pend}, "es")


def test_sin_datos_vigentes_el_motivo_es_la_comunicacion(equipo):
    _client, _srv, loop, _cm = equipo
    _arrancar(loop, 78.0)
    loop.estado_seguro.update(datos_vigentes=False)
    assert loop.estado_seguro.motivo_pendiente["codigo"] == "sin_datos_vigentes"


def test_sin_motivo_ni_pausa_no_hay_nota():
    from autoclave.ui_qml.domain import detalle_aviso
    assert detalle_aviso.texto_espera({}, "es") == ""
    assert detalle_aviso.texto_espera(None, "en") == ""
    fila = detalle_aviso.armar("estado_seguro_en_curso", {"causa": "fallo"})
    assert "Pendiente" not in fila["descripciones"]["es"]


def test_puente_sin_campos_nuevos_falla_a_nada():
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    seg = UiBridge._seguridad_de({"estado_seguro": {"activo": True}})
    assert seg["es_pausa_prueba"] is False and seg["es_pendiente"] == {}
    seg = UiBridge._seguridad_de({"estado_seguro": {"activo": True, "en_pausa_modo_prueba": 1,
                                                    "motivo_pendiente": "x"}})
    assert seg["es_pausa_prueba"] is False and seg["es_pendiente"] == {}


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_textos_nuevos_en_los_dos_idiomas(idioma):
    from autoclave import i18n
    for clave in ("sistema.estado_seguro_pausa_modo_prueba", "sistema.estado_seguro_espera"):
        assert i18n.existe(clave, idioma)
    from autoclave.ui_qml.domain.detalle_aviso import MOTIVOS_NO_ABRIR
    for m in MOTIVOS_NO_ABRIR:
        assert i18n.existe(f"aviso_detalle.estado_seguro_espera.{m}", idioma)


# ── 4. ningún valor del rango ni de la atmosférica se cachea ───────────────

_CLAVES_ATM = ("rango_presion_atm", "presion_admosferica", "presion_atmosferica")
_ARCHIVOS = ("state_machine/estado_seguro.py", "state_machine/cycle_phases/protocolo_fallo.py",
             "core/runtime/camara_segura.py")


@pytest.mark.parametrize("ruta", _ARCHIVOS)
def test_ningun_atributo_guarda_el_rango_ni_la_atmosferica(ruta):
    """Ningún `self.<x> = ...config.get(<clave atm>)` (ni a través de una
    variable local tomada de config.get) en el protocolo ni en cámara segura:
    se leen en cada uso."""
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            continue
        destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
        a_self = any(isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name)
                     and d.value.id == "self" for d in destinos)
        if not a_self:
            continue
        # lo que se usa solo dentro de una comparación (p. ej. un contador de
        # lecturas de vacío `+1 if pres < atm - rango else 0`) no es una copia
        fuente = " ".join(ast.unparse(n) for n in _fuera_de_comparaciones(nodo.value))
        assert not any(c in fuente for c in _CLAVES_ATM), \
            f"{ruta}:{nodo.lineno} guarda en un atributo: {ast.unparse(nodo)}"
        assert not re.search(r"\b(atm|rango)\b", fuente), \
            f"{ruta}:{nodo.lineno} copia atm/rango a un atributo: {ast.unparse(nodo)}"


def _fuera_de_comparaciones(nodo):
    """Hojas (nombres y constantes) del valor asignado que no están dentro de
    una comparación."""
    if isinstance(nodo, ast.Compare):
        return []
    if isinstance(nodo, (ast.Name, ast.Constant)):
        return [nodo]
    salida = []
    for hijo in ast.iter_child_nodes(nodo):
        salida += _fuera_de_comparaciones(hijo)
    return salida


def test_el_protocolo_lee_la_configuracion_en_cada_tick():
    """Con un config que cuenta lecturas: cada update() del estado seguro
    vuelve a pedir atm y rango (no los toma una vez al iniciar)."""
    from tests.test_s9_estado_seguro_arranque import _CFG

    class Contador(dict):
        lecturas = 0

        def get(self, k, d=None):
            if k in _CLAVES_ATM:
                Contador.lecturas += 1
            return super().get(k, d)

    loop = _loop_s9()
    cfg = Contador(dict(_CFG, rango_presion_atm=1.0))
    loop.config_manager = cfg
    loop.estado_seguro.config = cfg
    _arrancar(loop, 103.0)                       # atm 101,3: sobrepresión con rango 1
    assert loop.estado_seguro.activo
    antes = Contador.lecturas
    _tick_es(loop)
    despues_uno = Contador.lecturas
    _tick_es(loop)
    assert despues_uno > antes and Contador.lecturas > despues_uno
    cfg["rango_presion_atm"] = 5.0
    _tick_es(loop, 3)
    assert not loop.estado_seguro.activo


def test_estado_de_maquina_no_interviene(equipo):
    """El protocolo de arranque corre en PREPARACION; tras un fallo, en FALLA:
    en los dos el fin solo depende de cámara segura 3 ticks."""
    client, srv, loop, _cm = equipo
    loop.estado.set_machine_state(GlobalState.FALLA)
    _arrancar(loop, 78.0)
    _patch_rango(client, srv, 5)
    _tick_es(loop, 3)
    assert not loop.estado_seguro.activo


# ── QML: la nota de la fila de estado seguro en curso (carga real) ─────────

_SCRIPT_QML = r'''
import json
from unittest.mock import MagicMock
from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401
from PySide6.QtTest import QTest
from autoclave.cliente.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.app import QML_DIR
from autoclave.ui_qml.bridge.ui_bridge import UiBridge
from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
from autoclave.ui_qml import sesion_backend
from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

qapp = QGuiApplication([])
sesion = sesion_backend.SesionVentana(transporte=lambda *a: (200, {"ok": True}),
                                      ejecutar=lambda t: t(), cierre_s=0.8, intervalo_ms=50)
sesion_backend.instalar(sesion)
puente_nu = NuevoUsuarioBridge(sesion=sesion)
flags = {"LISTO_PARA_CICLO": False, "PARO_EMERGENCIA": False, "PARO_REAL": False}
campos = {"estado_modulo_es": "ok", "no_abrir": True, "estado_seguro": {}}
ui = MagicMock(spec=UIServiceBackend)
ui.connected = True
ui.get_estado_global.return_value = "FALLA"
ui.get_estado_puerta.return_value = "CERRADO"
ui.get_alarmas.return_value = []
ui.get_estado_flag.side_effect = lambda f: flags.get(f, False)
ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
ui.get_sensores_temp.return_value = {"temp_camara": 92.0}
ui.get_sensores_pres.return_value = {"pres_camara": 75.0}
puente = UiBridge(ui, door=1, iniciar=False)
puente.refrescar()
avisos = []
engine = QQmlApplicationEngine()
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
engine.addImportPath(QML_DIR)
engine.setInitialProperties({"puente": puente, "sesion": sesion, "puenteNuevoUsuario": puente_nu})
engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
ventana = engine.rootObjects()[0]
ventana.show()
def buscar(tipo):
    return [o for o in ventana.findChildren(QObject)
            if o.metaObject().className().startswith(tipo + "_QML")]
def textos(nombre):
    return [str(o.property("texto")) for o in ventana.findChildren(QObject, nombre)
            if o.property("visible")]
def refrescar():
    puente.refrescar()
    QTest.qWait(300)
r = {}
QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
QTest.qWait(700)
campos["estado_seguro"] = {"activo": True, "causa": "fallo", "en_pausa_modo_prueba": True}
campos["test_mode_active"] = True
refrescar()
r["pausa"] = textos("avisoEsperaEstadoSeguro")
campos["test_mode_active"] = False
campos["estado_seguro"] = {"activo": True, "causa": "fallo", "motivo_pendiente": {
    "codigo": "temp_alta", "valores": {"temp": 92.0}, "texto": "x",
    "limites": {"temp_max_apertura": 80.0, "presion_atmosferica": 75.0,
                "rango_presion_atm": 5.0}}}
refrescar()
r["temp"] = textos("avisoEsperaEstadoSeguro")
campos["estado_seguro"] = {"activo": True, "causa": "fallo"}
refrescar()
r["nada"] = textos("avisoEsperaEstadoSeguro")
r["avisos"] = avisos
print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
'''


@pytest.fixture(scope="module")
def qml():
    import json
    import os
    import subprocess
    import sys
    pytest.importorskip("PySide6")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT_QML], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=180, cwd=RAIZ.parents[1])
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_qml_muestra_la_pausa_por_modo_prueba(qml):
    assert qml["pausa"] and qml["pausa"][0] == "En pausa: modo prueba activo"


def test_qml_muestra_el_motivo_pendiente_con_valor_y_limite(qml):
    assert qml["temp"] and "Temperatura 92.0 °C, límite 80.0 °C" in qml["temp"][0]


def test_qml_sin_motivo_no_muestra_nota(qml):
    assert qml["nada"] == []


def test_qml_sin_avisos_del_motor(qml):
    assert [a for a in qml["avisos"] if "Binding loop" not in a] == [], qml["avisos"]
