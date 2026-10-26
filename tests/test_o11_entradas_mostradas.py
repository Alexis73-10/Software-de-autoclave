"""O11 (tanda 11, D11-7): entradas mostradas solo con sensores en uso y
selector por fila (Opciones › Parámetros del ciclo)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoclave.core.managers import gestion_programas as gp
from autoclave.ui_qml.domain import entradas_mostradas as em
from tests.helpers.backend_doble import cabecera, parchear_en_backend
from tests.test_o1_gestion_programas import api, cm  # noqa: F401  (fixtures)
from tests.test_t3_endpoints_sensores import _CON_REF, _FABRICA, _put, entorno  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]
_HAB = ["temp_camara", "temp_2_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]


def _prog(sensores=None, entradas=None):
    return SimpleNamespace(sensores=sensores, entradas_mostradas=entradas)


# ── omisión (D11-7.4) ──────────────────────────────────────────────────────

@pytest.mark.parametrize("sensores, esperadas", [
    (None, ["temp_camara", "pres_camara"]),                 # de fábrica: solo Cámara 1
    (_FABRICA, ["temp_camara", "pres_camara"]),
    (_CON_REF, ["temp_camara", "temp_referencia", "pres_camara"]),
    ({"temp_camara": "referencia", "temp_2_camara": "principal", "temp_ref": "referencia"},
     ["temp_2_camara", "temp_camara", "pres_camara"]),      # primera Referencia (catálogo)
    ({"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"},
     ["temp_2_camara", "pres_camara"]),
])
def test_omision_segun_asignacion(sensores, esperadas):
    assert gp.entradas_de(_prog(sensores), _HAB) == esperadas


def test_omision_respeta_las_habilitadas():
    assert gp.entradas_de(_prog(_CON_REF), ["temp_camara", "pres_camara"]) == [
        "temp_camara", "pres_camara"]
    # ninguna de la omisión habilitada: la primera habilitada en uso
    assert gp.entradas_de(_prog(_FABRICA), ["temp_referencia", "pres_chaqueta"]) == ["pres_chaqueta"]


def test_no_en_uso_del_programa():
    assert gp.entradas_no_en_uso(_prog(_FABRICA)) == ["temp_2_camara", "temp_referencia"]
    assert gp.entradas_no_en_uso(_prog(_CON_REF)) == ["temp_2_camara"]


# ── JSON viejo con un No en uso (D11-7.4) ──────────────────────────────────

def test_json_viejo_con_no_en_uso_se_filtra_al_presentar():
    viejo = _prog(_FABRICA, ["temp_referencia", "pres_chaqueta", "temp_camara"])
    # Tanda 17 (SON-01, decisión de Cristian): las No en uso se conservan (monitoreo)
    assert gp.entradas_de(viejo, _HAB) == ["temp_referencia", "pres_chaqueta", "temp_camara"]
    solo_ref = _prog(_FABRICA, ["temp_referencia", "temp_2_camara"])
    assert gp.entradas_de(solo_ref, _HAB) == ["temp_referencia", "temp_2_camara"]


def test_get_cycle_filtra_un_json_viejo(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    c = gp.programa(ctx.cycle_manager, 2)
    c.entradas_mostradas = ["temp_referencia", "pres_chaqueta"]
    ctx.cycle_manager.selected_cycle = c
    d = client.get("/cycle").json()
    # Tanda 17 (SON-01, decisión de Cristian): la No en uso se conserva y se rotula
    assert d["entradas_mostradas"] == ["temp_referencia", "pres_chaqueta"]
    assert "temp_referencia" in d["entradas_no_en_uso"]


def test_programa_de_fabrica_tambien_se_filtra(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    fabrica = ctx.cycle_manager.fabrica[2]
    fabrica.entradas_mostradas = ["temp_referencia", "pres_camara"]
    ctx.cycle_manager.selected_cycle = fabrica
    # Tanda 17 (SON-01, decisión de Cristian): la No en uso se conserva
    assert client.get("/cycle").json()["entradas_mostradas"] == ["temp_referencia", "pres_camara"]


# ── selector y rechazo en el backend (D11-7.1) ─────────────────────────────

def test_disponibles_sin_no_en_uso(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    d = client.get("/cycle/display-inputs?programa=2").json()
    assert d["entradas"] == ["temp_camara", "pres_camara"]
    # Tanda 17 (SON-01, decisión de Cristian): el selector ofrece también las No en uso
    assert d["disponibles"] == _HAB
    assert d["habilitadas"] == _HAB


def test_put_rechaza_sensor_no_en_uso_422(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    c = gp.programa(ctx.cycle_manager, 2)
    antes = Path(c._path).read_text(encoding="utf-8")
    r = client.put("/cycle/display-inputs", headers=cabecera(srv, "tecnico"),
                   json={"programa": 2, "entradas": ["temp_camara", "temp_referencia"]})
    # Tanda 17 (SON-01, decisión de Cristian): se retira el rechazo SENSOR_NO_EN_USO
    assert r.status_code == 200, r.text
    assert Path(c._path).read_text(encoding="utf-8") != antes
    assert json.loads(Path(c._path).read_text(encoding="utf-8"))["entradas_mostradas"] == [
        "temp_camara", "temp_referencia"]
    assert gp.fijar_entradas(ctx.cycle_manager, 2, ["temp_2_camara"], _HAB)[1] == ["temp_2_camara"]


def test_put_acepta_sensor_en_uso(api, monkeypatch):
    client, srv, ctx, _ = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: list(_HAB))
    gp.programa(ctx.cycle_manager, 2).sensores = dict(_CON_REF)
    r = client.put("/cycle/display-inputs", headers=cabecera(srv, "tecnico"),
                   json={"programa": 2, "entradas": ["temp_referencia", "pres_camara"]})
    assert r.status_code == 200, r.text


# ── cambio de rol a No en uso (D11-7.3) ────────────────────────────────────

def test_cambio_de_rol_quita_la_entrada_con_auditoria(entorno):
    client, ctx, srv, prog, archivo = entorno
    assert _put(client, srv, _CON_REF).status_code == 200
    prog.entradas_mostradas = ["temp_referencia", "pres_camara"]
    r = _put(client, srv, _FABRICA, anterior=_CON_REF)
    assert r.status_code == 200, r.text
    # Tanda 17 (SON-01, decisión de Cristian): al pasar a No en uso ya no se quita de
    # las Entradas mostradas ni se audita `entradas_mostradas`
    assert prog.entradas_mostradas == ["temp_referencia", "pres_camara"]
    data = json.loads(archivo.read_text(encoding="utf-8"))
    assert "entradas_mostradas" not in data
    assert data["cycle_temperature_sensors"] == _FABRICA
    assert ctx.db.get_auditoria(evento="entradas_mostradas") == []


def test_cambio_de_rol_repone_el_principal_si_queda_vacia(entorno):
    client, ctx, srv, prog, archivo = entorno
    assert _put(client, srv, _CON_REF).status_code == 200
    prog.entradas_mostradas = ["temp_referencia"]
    assert _put(client, srv, _FABRICA, anterior=_CON_REF).status_code == 200
    # Tanda 17 (SON-01, decisión de Cristian): la selección no cambia
    assert prog.entradas_mostradas == ["temp_referencia"]
    assert "entradas_mostradas" not in json.loads(archivo.read_text(encoding="utf-8"))


def test_cambio_de_rol_sin_afectar_la_seleccion_no_la_toca(entorno):
    client, ctx, srv, prog, archivo = entorno
    prog.entradas_mostradas = ["pres_camara", "temp_camara"]
    assert _put(client, srv, _CON_REF).status_code == 200
    assert prog.entradas_mostradas == ["pres_camara", "temp_camara"]
    assert "entradas_mostradas" not in json.loads(archivo.read_text(encoding="utf-8"))
    assert ctx.db.get_auditoria(evento="entradas_mostradas") == []


def test_cambio_de_rol_rechazado_en_ciclo_no_toca_la_seleccion(entorno):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, ctx, srv, prog, archivo = entorno
    assert _put(client, srv, _CON_REF).status_code == 200
    prog.entradas_mostradas = ["temp_referencia"]
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert _put(client, srv, _FABRICA, anterior=_CON_REF).status_code == 409
    assert prog.entradas_mostradas == ["temp_referencia"]


def test_tras_cambio_de_rol_funcion_pura():
    # Tanda 17 (SON-01, decisión de Cristian): se retira entradas_tras_cambio_de_rol
    assert not hasattr(gp, "entradas_tras_cambio_de_rol")


# ── presentación: Preciclo, Ciclo y gráfica sin las filas No en uso ────────

SENSORS = {"temperature": {"camara": 121.04, "ref": 120.5}, "pressure": {"camara": 205.3}}


def test_construir_omite_las_no_en_uso():
    filas = em.construir(["temp_camara", "temp_referencia", "pres_camara"], SENSORS,
                         no_en_uso=["temp_referencia"])
    # Tanda 17 (SON-01, decisión de Cristian): la No en uso se muestra como monitoreo
    assert [f["clave"] for f in filas] == ["temp_camara", "temp_referencia", "pres_camara"]
    assert [f["monitoreo"] for f in filas] == [False, True, False]
    assert "—" not in [f["valor"] for f in filas]


def test_construir_todas_no_en_uso_cae_en_la_omision():
    filas = em.construir(["temp_referencia"], SENSORS, no_en_uso=["temp_referencia"])
    # Tanda 17 (SON-01, decisión de Cristian): ya no cae en la omisión
    assert [f["clave"] for f in filas] == ["temp_referencia"] and filas[0]["monitoreo"] is True


def test_series_omiten_las_no_en_uso():
    series = em.series_grafica(["temp_camara", "temp_referencia", "pres_camara"],
                               no_en_uso=["temp_referencia"])
    # Tanda 17 (SON-01, decisión de Cristian): la serie No en uso se grafica (monitoreo)
    assert [s["entrada"] for s in series] == ["temp_camara", "temp_referencia", "pres_camara"]
    assert [s["monitoreo"] for s in series] == [False, True, False]


def test_puente_sin_fila_no_en_uso():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from unittest.mock import MagicMock
    from PySide6.QtCore import QCoreApplication
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_flag.return_value = False
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_sensores_temp.return_value = {}
    ui.get_sensores_pres.return_value = {}
    ui.get_campo.side_effect = lambda k, d=None: SENSORS if k == "sensors" else d
    ui.get_cycle.return_value = {"name": "A",
                                 "entradas_mostradas": ["temp_camara", "temp_referencia", "pres_camara"],
                                 "entradas_no_en_uso": ["temp_referencia"]}
    b = UiBridge(ui, door=1, iniciar=False)
    b.refrescar()
    # Tanda 17 (SON-01, decisión de Cristian): la fila No en uso aparece (monitoreo)
    assert [f["clave"] for f in b.entradasMostradas] == ["temp_camara", "temp_referencia", "pres_camara"]
    assert [s["entrada"] for s in b.seriesGrafica] == ["temp_camara", "temp_referencia", "pres_camara"]


# ── selector por fila (D11-7.2) ────────────────────────────────────────────

from tests.test_o1_parametros_ciclo_ui import _PROGRAMAS  # noqa: E402
from autoclave.ui_qml.sesion_backend import Resultado  # noqa: E402

_DISP = ["temp_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]


class _Sesion:
    def __init__(self):
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if ruta == "/programas":
            return Resultado("ok", _PROGRAMAS, 200)
        if ruta.startswith("/cycle/display-inputs?"):
            return Resultado("ok", {"entradas": ["temp_camara", "pres_camara"], "editable": True,
                                    "habilitadas": _DISP + ["temp_2_camara"],
                                    "disponibles": list(_DISP)}, 200)
        return Resultado("ok", {"ok": True}, 200)


def _ctrl():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _Sesion()
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    c.cargarEntradas()
    return c, s


def test_selector_no_ofrece_un_no_en_uso():
    c, _ = _ctrl()
    assert c.entradasDisponibles == _DISP
    for fila in range(3):
        assert "temp_2_camara" not in c.opcionesFila(fila, ["temp_camara", "", ""])


def test_filas_iniciales_y_sin_repetidas():
    c, _ = _ctrl()
    assert c.filasEntradas == ["temp_camara", "pres_camara", ""]
    filas = ["temp_camara", "pres_camara", ""]
    assert c.opcionesFila(0, filas) == ["temp_camara", "temp_referencia", "pres_chaqueta"]
    assert c.opcionesFila(1, filas) == ["temp_referencia", "pres_camara", "pres_chaqueta"]
    assert c.opcionesFila(2, filas) == ["temp_referencia", "pres_chaqueta"]


def test_entrada_1_obligatoria_y_sin_repetir():
    c, s = _ctrl()
    assert not c.guardarFilas(["", "pres_camara", ""])
    assert c.mensaje == "opciones.err_entrada_1_obligatoria"
    assert not c.guardarFilas(["pres_camara", "pres_camara", ""])
    assert c.mensaje == "opciones.err_entradas_repetidas"
    assert not any(m == "PUT" for m, *_ in s.enviados)
    assert c.guardarFilas(["pres_chaqueta", "", "temp_camara"])
    assert ("PUT", "/cycle/display-inputs",
            {"programa": 2, "entradas": ["pres_chaqueta", "temp_camara"]}) in s.enviados


def test_mensaje_del_rechazo_no_en_uso():
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import mensaje_de
    assert mensaje_de("SENSOR_NO_EN_USO") == "opciones.err_sensor_no_en_uso"


def test_textos_es_en():
    base = RAIZ / "src" / "autoclave" / "i18n"
    for lang in ("es", "en"):
        d = json.loads((base / f"{lang}.json").read_text(encoding="utf-8"))["opciones"]
        for k in ("entrada_fila", "entrada_ninguna", "err_entrada_1_obligatoria",
                  "err_entradas_repetidas", "err_sensor_no_en_uso", "entradas_nota"):
            assert d.get(k), (lang, k)
    es = json.loads((base / "es.json").read_text(encoding="utf-8"))["opciones"]
    assert es["entrada_fila"].replace("{n}", "1") == "Entrada 1:"
    assert es["entrada_ninguna"] == "Ninguna"


def test_pantalla_tres_filas_con_desplegable():
    pytest.importorskip("PySide6")
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    guion = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem  # noqa: F401  (childItems)
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml.sesion_backend import Resultado
from autoclave.ui_qml.controllers import parametros_ciclo_controller as pcc
DISP = ["temp_camara", "temp_referencia", "pres_camara"]
class S:
    def enviar(self, m, ruta, cuerpo=None):
        if ruta == "/programas":
            return Resultado("ok", {"programas": [{"numero": 2, "cycle_id": "x", "nombre": "P",
                "editable": True, "habilitado": True, "secciones": []}]}, 200)
        if ruta.startswith("/cycle/display-inputs?"):
            return Resultado("ok", {"entradas": ["temp_camara"], "editable": True,
                                    "habilitadas": DISP, "disponibles": DISP}, 200)
        return Resultado("ok", {"ok": True}, 200)
from autoclave.ui_qml import sesion_backend
sesion_backend.ventana = lambda: S()
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { width: 800; height: 1200; OpcionesParametrosCiclo { objectName: "p"; anchors.fill: parent; edicionPermitida: true } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_o11.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
def items(it):
    for h in it.childItems():
        yield h
        yield from items(h)
def buscar(nombre):
    return next((h for h in items(raiz) if h.objectName() == nombre), None)
buscar("filaEntradas").pulsada.emit()
app.processEvents()
res = {}
for i in (1, 2, 3):
    fila = buscar("filaEntrada_%d" % i)
    assert fila is not None, i
    res["alto_%d" % i] = fila.property("height")
    res["valor_%d" % i] = fila.property("valor")
    res["titulo_%d" % i] = fila.property("titulo")
res["guardar_ancho"] = buscar("guardarEntradas").width()
buscar("filaEntrada_2").pulsada.emit()
app.processEvents()
lista = buscar("opcionesEntrada_2")
res["abierta"] = bool(lista and lista.isVisible())
res["opciones"] = [h.objectName() for h in items(raiz)
                   if h.objectName().startswith("opcionEntrada_") and h.isVisible()]
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()], **res}))
"""
    r = subprocess.run([sys.executable, "-c", guion, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["avisos"] == []
    assert [d["titulo_%d" % i] for i in (1, 2, 3)] == ["Entrada 1:", "Entrada 2:", "Entrada 3:"]
    assert d["valor_2"] == "Ninguna" and d["valor_3"] == "Ninguna"
    assert all(d["alto_%d" % i] >= 64 for i in (1, 2, 3))
    assert d["abierta"]
    assert d["guardar_ancho"] > 0          # el botón de guardar existente se ve
    # en la fila 2: Ninguna y las disponibles menos la elegida en la fila 1
    assert sorted(d["opciones"]) == sorted(["opcionEntrada_", "opcionEntrada_temp_referencia",
                                            "opcionEntrada_pres_camara"])
