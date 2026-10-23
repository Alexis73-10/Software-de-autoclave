# tests/cap9_capturas_banco.py
#
# CAP9 (tanda 9, D9-13.5): banco de capturas de la interfaz QML con el código
# final de la tanda 9, en español y en inglés. Reúne los mecanismos que ya
# existían (offscreen, sin backend ni hardware) y deja todo en
# docs/informes/tanda9/capturas/banco/:
#
#   pantallas    banco de I4/V8b (22 pantallas sueltas, 1024x1638)
#                -> CAP9_<idioma>_<pantalla>.png + resumen.json
#   reasignacion recorrido de R8 (Opciones avanzadas › reasignación de E/S)
#                -> R8_<idioma>_<n>_*.png
#   manejo       recorrido de C9 (Opciones avanzadas › Manejo de ciclos)
#                -> C9_<idioma>_<n>_*.png
#   p9           Parámetros del ciclo › Finalización, Parámetros del equipo
#                (entrada y "Cámara segura") y Entradas / Salidas, puertas
#                simples y automáticas -> P9_<perfil>_<idioma>_<n>_*.png
#   preciclo     Main.qml en Preciclo con la tarjeta de alarmas: estado seguro
#                de arranque sin confirmación, el mismo detenido por presión de
#                cámara sin lectura con CIC-10 y SEN-06, y la confirmación tras
#                un paro real -> CAP9_<idioma>_preciclo_<n>_*.png
#
# Uso (sin argumentos corre todas las partes):
#
#     PYTHONPATH=<worktree>/src python tests/cap9_capturas_banco.py [parte ...]
#
# No es una prueba de pytest (no empieza por test_).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

# T10 (tanda 10): CAP_DESTINO cambia la carpeta (p. ej. capturas de otra tanda)
DESTINO = Path(os.environ.get("CAP_DESTINO") or RAIZ / "docs" / "informes" / "tanda9" / "capturas" / "banco")
IDIOMAS = ("es", "en")


def _pantallas() -> int:
    from tests.i4_truncado_banco import PANTALLAS, revisar
    resumen = {}
    for idioma in IDIOMAS:
        for nombre in PANTALLAS:
            r = revisar(nombre, idioma, captura=True, carpeta=DESTINO, prefijo="CAP9")
            resumen[f"{idioma}/{nombre}"] = {"malos": r["malos"], "textos_vistos": len(r["vistos"])}
            print("pantallas", idioma, nombre, json.dumps(r["malos"], ensure_ascii=False))
    (DESTINO / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    return 0


def _reasignacion() -> int:
    from tests import opciones_qml_banco as banco
    from tests.test_r8_reasignacion_banco_qml import PASOS
    for idioma in IDIOMAS:
        r = banco.correr("ingeniero", f"IDIOMA = {idioma!r}\n" + PASOS, capturas=True,
                         dir_capturas=DESTINO)
        print("reasignacion", idioma, "avisos:", r["avisos"])
    return 0


def _manejo() -> int:
    from tests import opciones_qml_banco as banco
    from tests import test_c9_manejo_ciclos_banco_qml as c9
    for idioma in IDIOMAS:
        pasos = [("tecnico", c9.PASOS_TECNICO, "PREPARADO", ""),
                 ("tecnico", c9.PASOS_EN_CICLO, "CICLO", "NUM = 5\nROL = 'tecnico'\n"),
                 ("ingeniero", c9.PASOS_EN_CICLO, "CICLO", "NUM = 6\nROL = 'ingeniero'\n"),
                 ("ingeniero", c9.PASOS_INGENIERO, "PREPARADO", "")]
        for rol, p, estado, extra in pasos:
            r = banco.correr(rol, f"IDIOMA = {idioma!r}\n{extra}" + p, rutas=c9.RUTAS,
                             estado=estado, capturas=True, dir_capturas=DESTINO)
            print("manejo", idioma, rol, estado, "avisos:", r["avisos"])
    return 0


def _p9() -> int:
    from tests import p9_capturas_banco as p9
    p9.DESTINO = DESTINO
    return p9.main()


_SCRIPT_PRECICLO = textwrap.dedent(r"""
    import json, os, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.core.runtime import alarmas_i18n
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None        # sin backend: no cambia el idioma

    def transporte(metodo, ruta, cuerpo, token, plazo):
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    _cargar_fuentes()
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=0.8, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)

    # Motivo literal que arma ProtocoloFallo (S9, D9-1.4) con la presión de
    # cámara sin lectura y el estado seguro activo (texto de T10, D10-3)
    MOTIVO = ("Sensor de presión de cámara sin lectura: sin el sensor de presión de "
              "cámara no se puede llevar la cámara a estado seguro. Revise la conexión "
              "del sensor de presión de cámara o llame a servicio técnico")

    def alarma(codigo, valores):
        # mismo DTO que server._alarma_dto: "description" es la descripción
        # registrada (español), que es la que muestra la lista de Preciclo
        d = CATALOGO[codigo]
        return {"id": codigo, "level": d.nivel.nombre_compat,
                "description": d.renderizar(valores), "source_state": "PREPARACION",
                "textos": alarmas_i18n.por_idioma(d, valores)}

    flags = {"LISTO_PARA_CICLO": False, "PARO_EMERGENCIA": False, "PARO_REAL": False}
    campos = {"estado_tarjeta": "ok", "no_abrir": True, "estado_seguro": {}}
    alarmas = []
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARACION"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.side_effect = lambda: list(alarmas)
    ui.get_estado_flag.side_effect = lambda f: flags.get(f, False)
    ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
    ui.get_cycle.return_value = {"name": "Instrumental 134", "number": 2}
    ui.get_sensores_temp.return_value = {"temp_camara": 62.4}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
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
    def esperar(ms=700):
        QTest.qWait(ms)
    def refrescar():
        puente.refrescar()
        esperar(500)
    def capturar(nombre):
        esperar(250)
        ventana.grabWindow().save(os.path.join(cfg["destino"], f"CAP9_{cfg['idioma']}_preciclo_{nombre}.png"))
    def visibles(nombre):
        return [str(o.property("texto")) for o in ventana.findChildren(QObject, nombre)
                if o.property("visible")]

    r = {}
    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
    esperar()
    r["pantalla_preciclo"] = any(o.property("visible") for o in buscar("PantallaPreciclo"))

    # 1. estado seguro del arranque, sin confirmación (D9-1.1/D9-1.2)
    campos["estado_seguro"] = {"activo": True, "requiere_confirmacion": False, "causa": "arranque"}
    refrescar()
    r["1_causa"] = visibles("avisoCausaEstadoSeguro")
    r["1_confirmar"] = puente.estadoSeguroRequiereConfirmacion
    capturar("1_estado_seguro_arranque")

    # 2. el mismo, detenido por la presión de cámara sin lectura: CIC-10 + SEN-06 (D9-1.4)
    ui.get_sensores_pres.return_value = {"pres_camara": None}
    campos["estado_seguro"] = {"activo": True, "requiere_confirmacion": False, "causa": "arranque",
                               "bloqueado_motivo": MOTIVO}
    alarmas[:] = [alarma("CIC-10", {"motivo": MOTIVO}), alarma("SEN-06", {})]
    refrescar()
    r["2_alarmas"] = puente.alarms.rowCount()
    r["2_descripciones"] = [f["description"] for f in puente.alarms.filas()]
    r["2_aviso_estado_seguro"] = visibles("avisoEstadoSeguroDetenido")
    capturar("2_cic10_sen06_sin_presion")

    # 3. confirmación pendiente tras un paro real ya liberado (D9-1.2)
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    alarmas[:] = []
    campos["estado_seguro"] = {"activo": True, "requiere_confirmacion": True,
                               "causa": "paro_liberado"}
    refrescar()
    r["3_paro_liberado"] = len(visibles("avisoParoLiberado"))
    capturar("3_confirmacion_tras_paro")
    r["avisos"] = [a for a in avisos if "Binding loop" not in a]
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


def _preciclo() -> int:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    fallos = 0
    for idioma in IDIOMAS:
        cfg = {"idioma": idioma, "destino": str(DESTINO)}
        p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_PRECICLO, json.dumps(cfg)],
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                           timeout=180)
        linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
        fallos += linea is None
        print("preciclo", idioma, linea or (p.stdout[-2000:] + p.stderr[-3000:]))
    return 1 if fallos else 0


PARTES = {"pantallas": _pantallas, "reasignacion": _reasignacion, "manejo": _manejo,
          "p9": _p9, "preciclo": _preciclo}


if __name__ == "__main__":
    import autoclave
    print("autoclave:", autoclave.__file__)
    DESTINO.mkdir(parents=True, exist_ok=True)
    elegidas = sys.argv[1:] or list(PARTES)
    sys.exit(max(PARTES[n]() or 0 for n in elegidas))
