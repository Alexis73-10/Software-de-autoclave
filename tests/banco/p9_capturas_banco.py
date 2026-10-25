# tests/banco/p9_capturas_banco.py
#
# P9 (tanda 9): capturas de Parámetros del ciclo › Finalización, Parámetros
# del equipo (entrada y "Cámara segura") y Entradas / Salidas, para un perfil
# de puertas simples y uno de puertas automáticas, en es y en.
#
#   PYTHONPATH=<worktree>/src python tests/banco/p9_capturas_banco.py
#
# Los datos de las pantallas salen de los mismos módulos que usa el backend
# (ConfigManager + grupos_visibles, catálogo del programa de fábrica filtrado
# como _hojas_seccion, io_names.canales_digitales con el perfil); la sesión del
# backend se reemplaza por un doble que responde según la ruta. Offscreen.

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "informes" / "tanda9" / "capturas" / "p9"

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave import i18n

    cfg = json.loads(sys.argv[1])
    rutas = cfg["rutas"]

    class Sesion:
        sinConexion = False
        def enviar(self, metodo, ruta, cuerpo=None):
            estado, datos = rutas.get(f"{metodo} {ruta.split('?')[0]}", (200, {}))
            if 200 <= estado < 300:
                return sesion_backend.Resultado("ok", datos, estado)
            return sesion_backend.Resultado((datos or {}).get("codigo") or "error_generico",
                                            datos, estado)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)

    sesion_backend.ventana = lambda: Sesion()
    i18n.fijar_idioma(cfg["lang"])
    qapp = QGuiApplication([])
    _cargar_fuentes()

    def ventana(contenido, nombre_qml):
        qml = ("import QtQuick\nimport Tema\nimport \"Pantallas\"\n"
               "Window { width: 1200; height: 1500; visible: true; color: \"white\"\n"
               "  Binding { target: Escala; property: \"factor\"; value: 1 }\n"
               "  " + contenido + " }\n")
        ruta = f"{QML_DIR}/_p9_{nombre_qml}_{os.getpid()}.qml"
        open(ruta, "w", encoding="utf-8").write(qml)
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        try:
            engine.load(QUrl.fromLocalFile(ruta))
        finally:
            os.remove(ruta)
        w = engine.rootObjects()[0]
        w.show()
        QTest.qWait(300)
        return engine, w, w.findChild(QQuickItem, "pantalla")

    def capturar(w, archivo):
        QTest.qWait(300)
        w.grabWindow().save(os.path.join(cfg["destino"], archivo))

    pre = f"P9_{cfg['perfil']}_{cfg['lang']}_"

    # Parámetros del ciclo › Finalización
    e, w, p = ventana('OpcionesParametrosCiclo { objectName: "pantalla"; anchors.fill: parent; '
                      'edicionPermitida: true }', "ciclo")
    from PySide6.QtCore import QObject
    ctrl = p.findChild(QObject, "parametrosCicloController")
    ctrl.elegirPrograma(2)
    ctrl.abrirSeccion("finalizacion")
    p.setProperty("vista", "seccion")
    capturar(w, pre + "1_ciclo_finalizacion.png")
    w.close(); del e

    # Parámetros del equipo: entrada y Cámara segura
    e, w, p = ventana('OpcionesParametrosEquipo { objectName: "pantalla"; anchors.fill: parent; '
                      'edicionPermitida: true; rol: "ingeniero"; estadoMaquina: "PREPARADO" }',
                      "equipo")
    capturar(w, pre + "2_equipo_entrada.png")
    p.findChild(QObject, "parametrosEquipoController").abrirGrupo("camara_segura")
    capturar(w, pre + "3_equipo_camara_segura.png")
    w.close(); del e

    # Entradas / Salidas › Entradas
    e, w, p = ventana('OpcionesEntradasSalidas { objectName: "pantalla"; anchors.fill: parent }',
                      "es")
    capturar(w, pre + "4_entradas_salidas.png")
    w.close(); del e
    print("RESULTADO=ok")
''')


def _perfil(door_type):
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.installation.profile import InstallationProfile, Role
    return InstallationProfile(
        machine_id="P9", model_id="P9", serial_number="P9", equipment_class=EquipmentClass.PISO,
        door_count=2, door_type=door_type, cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT, created_at=datetime(2026, 10, 23))


def _rutas(door_type) -> dict:
    from autoclave.core.managers.config_manager import ConfigManager, grupos_visibles
    from autoclave.core.runtime import io_names
    from autoclave.installation.profile import puertas_simples
    perfil = _perfil(door_type)
    simples = puertas_simples(perfil)

    cm = ConfigManager(); cm.load_config()
    grupos = grupos_visibles(simples)
    equipo = {"parametros": [p for p in cm.describir() if p["grupo"] in grupos], "grupos": grupos}

    prog = json.loads((RAIZ / "src" / "autoclave" / "cycles" / "factory" / "instrumental_134.json")
                      .read_text(encoding="utf-8"))
    fin = prog["parameters"]["finalizacion"]
    ocultos = {"tiempo_espera_apertura", "apertura_automatica"} if simples else set()
    parametros = []
    for clave, hoja in fin.items():
        if clave in ocultos:
            continue
        parametros.append({
            "path": [clave], "clave": clave, "tipo": hoja.get("type") or "int",
            "unidad": (hoja.get("unit") or "").replace("�", "°"), "clase": hoja.get("clase"),
            "valor": hoja["value"], "defecto": hoja["value"], "min": hoja.get("min"),
            "max": hoja.get("max"), "opciones": [], "modos": [], "modificado": False,
            "ultima_modificacion": None})
    programas = {"programas": [{
        "numero": 2, "cycle_id": "instrumental_134", "nombre": "Instrumental 134",
        "editable": True, "danado": False, "habilitado": True, "personalizado": False,
        "secciones": [{"clave": "finalizacion", "no_se_ejecuta": False}]}]}

    di = io_names.canales_digitales("DI", profile=perfil)
    crudas = {c["estado_key"]: 1 for c in di}
    crudas.update({"paro_emergencia": 1, "atrapamiento_puerta_1": 1, "atrapamiento_puerta_2": 0,
                   "puerta_1_cerrada": 1, "puerta_1_abierta": 0,
                   "puerta_2_cerrada": 0, "puerta_2_abierta": 1})
    status = {"estado_tarjeta": "ok", "card_connected": True, "machine_state": "PREPARADO",
              "test_mode_active": False, "sensors": {"digital_inputs": crudas,
                                                      "digital_outputs": {}}}
    canales = {"DI": di, "DO": [], "temperature": [], "pressure": []}
    return {
        "GET /system_params": [200, equipo],
        "GET /printer/config": [200, {"habilitada": True}],
        "GET /units": [200, {"temperatura": "C", "presion": "kPa"}],
        "GET /language": [200, {"idioma": "es"}],
        "GET /programas": [200, programas],
        "GET /programas/2/seccion/finalizacion": [200, {"editable": True,
                                                       "parametros": parametros}],
        "GET /io/channels": [200, canales],
        "GET /status": [200, status],
    }


def main() -> int:
    from autoclave.devices.puertas.door_type import DoorType
    DESTINO.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    fallos = 0
    for perfil, tipo in (("simples", DoorType.SIMPLE), ("automaticas", DoorType.ADVANCED)):
        rutas = _rutas(tipo)
        for lang in ("es", "en"):
            cfg = {"perfil": perfil, "lang": lang, "rutas": rutas, "destino": str(DESTINO)}
            p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                               capture_output=True, text=True, encoding="utf-8", env=env,
                               cwd=RAIZ, timeout=180)
            ok = "RESULTADO=ok" in p.stdout
            fallos += not ok
            print(perfil, lang, "ok" if ok else p.stderr[-2000:])
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
