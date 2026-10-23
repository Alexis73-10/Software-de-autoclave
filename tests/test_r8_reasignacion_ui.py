"""R8 (tanda 8, D8-5.12): OPCIONES > Opciones avanzadas = reasignación de E/S.
Controlador (tabla, conflictos vistos por la UI, envío) y pantalla QML
(carga sin avisos, elementos exigidos, cableada en Opciones.qml)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

RAIZ = Path(__file__).resolve().parents[1]

_FILAS = [
    {"funcion": "vapor_camara", "tipo": "DO", "i18n": "io.do.vapor_camara",
     "puerto_actual": 4, "id_actual": "DO 04", "puerto_guardado": 4, "puerto_fabrica": 4,
     "id_fabrica": "DO 04", "critica": True, "reforzada": False, "temperatura": False},
    {"funcion": "bomba_vacio", "tipo": "DO", "i18n": "io.do.bomba_vacio",
     "puerto_actual": 19, "id_actual": "DO 19", "puerto_guardado": 19, "puerto_fabrica": 19,
     "id_fabrica": "DO 19", "critica": False, "reforzada": False, "temperatura": False},
    {"funcion": "paro_emergencia", "tipo": "DI", "i18n": "io.di.paro_emergencia",
     "puerto_actual": 11, "id_actual": "DI 11", "puerto_guardado": 11, "puerto_fabrica": 11,
     "id_fabrica": "DI 11", "critica": True, "reforzada": True, "temperatura": False},
    {"funcion": "temp_camara", "tipo": "AI", "i18n": "io.ai.temp_camara",
     "puerto_actual": 1, "id_actual": "AI 01", "puerto_guardado": 1, "puerto_fabrica": 1,
     "id_fabrica": "AI 01", "critica": True, "reforzada": False, "temperatura": True},
]
_DATOS = {
    "filas": _FILAS,
    "puertos": {"DI": list(range(1, 17)), "DO": list(range(1, 25)),
                "AI_TEMP": list(range(1, 9)), "AI_PRES": list(range(9, 17))},
    "ocupados": {"DI": {"11": "paro_emergencia"}, "DO": {"4": "vapor_camara", "19": "bomba_vacio",
                                                        "5": "no_habilitada"},
                 "AI": {"1": "temp_camara"}},
    "cambios_guardados": {}, "reinicio_pendiente": False, "error_archivo": "", "bloqueo": "",
    "verificacion": {"estado": "sin_cambios", "funciones": {}},
    "editable": True, "motivo": "", "reinicio_disponible": True,
}


class _Sesion:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.respuestas.get((metodo, ruta))
        return r() if callable(r) else (r or Resultado("error_generico"))


def _ok(datos=None):
    return Resultado("ok", datos or {}, 200)


def _ctrl(datos=None, extra=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    resp = {("GET", "/io/assignment"): _ok(json.loads(json.dumps(datos or _DATOS)))}
    resp.update(extra or {})
    s = _Sesion(resp)
    c = ReasignacionController(sesion=s)
    c.cargar()
    return c, s


def test_tabla_cargada():
    c, _ = _ctrl()
    assert c.cargado and c.editable
    assert [f["funcion"] for f in c.filas] == ["vapor_camara", "bomba_vacio", "paro_emergencia",
                                                "temp_camara"]
    assert c.cantidadCambios == 0 and c.conflictos == []


def test_elegir_puerto_libre_y_volver_al_guardado():
    c, _ = _ctrl()
    c.elegirPuerto("vapor_camara", 7)
    assert c.pendientes == {"vapor_camara": "DO 07"}
    assert c.criticasPendientes == ["io.do.vapor_camara"]
    c.elegirPuerto("vapor_camara", 4)
    assert c.cantidadCambios == 0


def test_conflicto_visto_en_la_ui_incluye_funciones_no_habilitadas():
    c, _ = _ctrl()
    c.elegirPuerto("vapor_camara", 5)       # ocupado por una función no listada
    assert [(x["funcion"], x["otra"], x["etiqueta"]) for x in c.conflictos] == \
        [("vapor_camara", "no_habilitada", "DO 05")]
    assert c.aplicar("clave") is False
    assert c.mensaje == "reasignacion.err_conflicto"


def test_intercambio_sin_conflicto():
    c, _ = _ctrl()
    c.elegirPuerto("vapor_camara", 19)
    c.elegirPuerto("bomba_vacio", 4)
    assert c.conflictos == []


def test_puertos_para_respeta_el_tipo_y_marca_ocupados():
    c, _ = _ctrl()
    p = c.puertosPara("temp_camara")
    assert [x["puerto"] for x in p] == list(range(1, 9))     # solo AI de temperatura
    assert p[0]["actual"] is True and p[0]["fabrica"] is True
    d = {x["puerto"]: x for x in c.puertosPara("vapor_camara")}
    assert d[19]["ocupadoPor"] == "io.do.bomba_vacio"
    assert d[5]["ocupadoPor"] == "reasignacion.funcion_no_habilitada"


def test_reforzada_y_analogica_marcadas():
    c, _ = _ctrl()
    c.elegirPuerto("paro_emergencia", 12)
    c.elegirPuerto("temp_camara", 2)
    assert [r["funcion"] for r in c.reforzadasPendientes] == ["paro_emergencia"]
    assert c.hayAnalogicas is True


def test_aplicar_envia_cambios_clave_confirmacion_y_nombres():
    c, s = _ctrl(extra={("POST", "/io/assignment"): _ok({"ok": True, "reinicio": True})})
    c.elegirPuerto("paro_emergencia", 12)
    c.fijarNombre("paro_emergencia", "Paro de emergencia")
    assert c.aplicar("secreta") is True
    assert s.enviados[-1] == ("POST", "/io/assignment",
                              {"cambios": {"paro_emergencia": 12}, "clave": "secreta",
                               "confirmar": True, "nombres": {"paro_emergencia": "Paro de emergencia"}})
    assert c.reiniciando is True and c.editable is False
    assert c.mensaje == "reasignacion.reiniciando" and c.cantidadCambios == 0
    c.cargar()                               # el control volvió
    assert c.reiniciando is False and c.mensaje == ""


def test_rechazo_del_backend_muestra_el_motivo_y_conserva_los_cambios():
    c, _ = _ctrl(extra={("POST", "/io/assignment"): Resultado("reautenticacion_fallida", {}, 403)})
    c.elegirPuerto("vapor_camara", 7)
    assert c.aplicar("mala") is False
    assert c.mensaje == "reasignacion.err_clave"
    assert c.cantidadCambios == 1


def test_no_editable_en_ciclo():
    c, _ = _ctrl({**_DATOS, "editable": False, "motivo": "ciclo"})
    assert c.editable is False and c.motivo == "reasignacion.motivo_ciclo"
    c.elegirPuerto("vapor_camara", 7)
    assert c.cantidadCambios == 0


def test_sin_respuesta():
    c, _ = _ctrl()
    c._s().respuestas[("GET", "/io/assignment")] = Resultado(BACKEND_NO_RESPONDE)
    c.cargar()
    assert c.cargado is False and c.mensaje == "reasignacion.err_sin_respuesta"


def test_restaurar_fabrica():
    c, s = _ctrl(extra={("POST", "/io/assignment/factory"): _ok({"ok": True, "reinicio": True})})
    assert c.restaurarFabrica("secreta") is True
    assert s.enviados[-1] == ("POST", "/io/assignment/factory", {"clave": "secreta", "confirmar": True})


def test_claves_del_catalogo_existen_en_es_y_en():
    from autoclave import i18n
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesReasignacion.qml").read_text(encoding="utf-8")
    import re
    claves = set(re.findall(r'"(reasignacion\.[a-z_]+)"', qml)) | set(rc._MENSAJES.values())
    claves |= {f"reasignacion.motivo_{m}" for m in rc._MOTIVOS}
    claves |= {f"reasignacion.falta_{m}" for m in rc._FALTAS}
    claves |= {f"reasignacion.verif_{e}" for e in rc._ESTADOS_VERIF}
    faltan = [(k, l) for k in sorted(claves) for l in ("es", "en") if not i18n.existe(k, l)]
    assert faltan == []


_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { width: 1100; height: 1500; OpcionesReasignacion { anchors.fill: parent } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_r8.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
for nombre in ("opcionesReasignacion", "reasignacionController", "tablaReasignacion",
               "botonDescartarReasignacion", "botonRestaurarFabrica", "botonAplicarReasignacion",
               "selectorPuerto", "dialogoAlertaReasignacion", "dialogoReforzadaReasignacion",
               "dialogoReinicioReasignacion", "dialogoFabricaReasignacion"):
    assert raiz.findChild(QObject, nombre) is not None, nombre
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()]}))
"""


def test_pantalla_carga_sin_avisos():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["avisos"] == []


def test_cableada_en_opciones():
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/Opciones.qml").read_text(encoding="utf-8")
    # C9 (tanda 9, D9-10): la reasignación vive dentro del contenedor de
    # Opciones avanzadas, solo para el ingeniero
    avanzadas = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesAvanzadas.qml").read_text(encoding="utf-8")
    assert 'objectName: "cargadorReasignacion"' in avanzadas
    assert "active: raiz.puedeReasignar &&" in avanzadas
    assert "puedeReasignar: control.puedeReasignarIo" in qml
    assert 'raiz.seccionActiva === "opciones_avanzadas"' in qml
    assert 'raiz.seccionActiva !== "opciones_avanzadas"' in qml     # no muestra "próximamente"


_VERIF = {**_DATOS, "pendientes": ["vapor_camara", "paro_emergencia"],
          "verificacion": {"estado": "trama_presente", "funciones": {
              "vapor_camara": {"estado": "trama_presente", "falta": "sin_prueba_de_salida"},
              "paro_emergencia": {"estado": "trama_presente", "falta": ""},
              "temp_camara": {"estado": "verificada", "falta": ""}}}}


def test_verificacion_por_funcion():
    c, _ = _ctrl(_VERIF)
    v = {x["funcion"]: x for x in c.verificacion}
    assert c.cantidadSinVerificar == 2
    assert v["vapor_camara"]["pendiente"] is True
    assert v["vapor_camara"]["falta"] == "reasignacion.falta_sin_prueba_de_salida"
    assert v["paro_emergencia"]["falta"] == "" and v["paro_emergencia"]["reforzada"] is True
    assert v["temp_camara"]["estado"] == "verificada" and v["temp_camara"]["pendiente"] is False


def test_verificar_envia_funcion_clave_y_nombre():
    c, s = _ctrl(_VERIF, extra={("POST", "/io/assignment/verify"): _ok({"ok": True, "pendientes": []})})
    assert c.verificar("paro_emergencia", "secreta", "Paro de emergencia") is True
    assert ("POST", "/io/assignment/verify",
            {"funcion": "paro_emergencia", "clave": "secreta", "nombre": "Paro de emergencia"}) in s.enviados
    assert c.mensaje == "reasignacion.verificada_ok"


def test_verificar_rechazado_muestra_lo_que_falta():
    c, _ = _ctrl(_VERIF, extra={("POST", "/io/assignment/verify"):
                                Resultado("sin_prueba_de_salida", {}, 409)})
    assert c.verificar("vapor_camara", "secreta", "") is False
    assert c.mensaje == "reasignacion.falta_sin_prueba_de_salida"
