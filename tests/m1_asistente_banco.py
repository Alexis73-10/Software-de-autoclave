# tests/m1_asistente_banco.py
#
# M1 (tanda 7): recorre el asistente de instalación QML (InstalacionVentana.qml
# con el puente real y un validador de código que acepta todo) offscreen, a
# 1200x1920, en un subproceso. Devuelve lo observado en cada paso (paso
# actual, textos de error, vista previa del nombre, resumen) y, si se pide,
# guarda una captura por paso en docs/informes/tanda7/capturas/M1_<n>_<paso>.png.
#
# Uso: python tests/m1_asistente_banco.py [es|en]   (genera las capturas)
# Lo usa tests/test_m1_asistente_qml.py (sin capturas).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAPTURAS = RAIZ / "docs" / "informes" / "tanda7" / "capturas"

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl, QMetaObject, Qt, Q_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QTest
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  (grabWindow)
    from autoclave import i18n
    import autoclave.ui_qml.bridge.i18n_qml as i18n_qml
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None

    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlEngine()
    engine.addImportPath(QML_DIR)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    instalados = []

    class Puente(PuenteInstalacion):
        pass

    # LIC-02 (licencia L0): las contraseñas van a una base falsa (no a la del banco)
    claves_fijadas = []

    class BdFalsa:
        def fijar_claves_instalacion(self, hashes):
            claves_fijadas.append(sorted(hashes))
            return ["Admin", "Ingeniero"]

        def close(self):
            pass

    puente = Puente(validar_codigo=lambda s, c: True, abrir_bd=BdFalsa, es_semilla=lambda c: False)
    # instalar() no escribe el perfil del equipo: se captura lo que mandaría la QML
    import autoclave.ui_qml.bridge.puente_instalacion as pi
    pi.escribir_perfil = lambda perfil, ahora=None: instalados.append(perfil)
    pi._hay_perfil_valido = lambda: False

    comp = QQmlComponent(engine, QUrl.fromLocalFile(QML_DIR + "/InstalacionVentana.qml"))
    ventana = comp.createWithInitialProperties({"puenteInstalacion": puente})
    assert ventana is not None, comp.errorString()
    ventana.setProperty("width", 1200)
    ventana.setProperty("height", 1920)
    ventana.show()
    a = ventana.findChild(QObject, "asistenteInstalacion")

    def esperar(ms=250):
        QTest.qWait(ms)

    def texto(nombre):
        o = a.findChild(QObject, nombre)
        return None if o is None else o.property("text")

    def visible(nombre):
        o = a.findChild(QObject, nombre)
        return bool(o is not None and o.property("visible"))

    def siguiente():
        QMetaObject.invokeMethod(a, "siguiente")
        esperar()

    capturas = []
    def capturar(n, paso):
        if cfg.get("capturas"):
            ruta = os.path.join(cfg["capturas"], f"M1_{cfg['idioma']}_{n:02d}_{paso}.png")
            esperar(400)
            ventana.grabWindow().save(ruta)
            capturas.append(ruta)

    obs = {"clases": [c["valor"] for c in a.property("clases")], "pasos": []}
    esperar(600)

    def anotar(etiqueta):
        obs["pasos"].append({
            "etiqueta": etiqueta, "paso": a.property("pasoActual"), "indice": a.property("indice"),
            "total": len(a.property("pasos").toVariant()), "subtitulo": texto("subtituloPaso"),
            "errorCapacidad": texto("errorCapacidad"), "errorTipoCarga": texto("errorTipoCarga"),
            "vistaPrevia": texto("vistaPreviaModelo"), "resumenModelo": texto("resumenModelo"),
            "campoModelo": a.findChild(QObject, "campoModelo") is not None,
        })

    n = 1
    # 1. Activación
    capturar(n, "activacion"); n += 1
    a.setProperty("serie", "SN-0001"); a.setProperty("codigo", "ABCDEF123456")
    siguiente()
    # 2. Tipo de equipo: sin selección inicial
    anotar("equipo_inicial")
    obs["claseInicial"] = a.property("clase")
    def item(nombre, raiz=None):               # delegados de Repeater: por el árbol visual
        for h in (raiz or ventana.contentItem()).childItems():
            if h.objectName() == nombre:
                return h
            r = item(nombre, h)
            if r is not None:
                return r
        return None
    obs["titulosClase"] = [item("clase_" + v).property("titulo") for v in obs["clases"]]
    capturar(n, "equipo"); n += 1
    QMetaObject.invokeMethod(a, "elegirClase", Q_ARG("QVariant", cfg.get("clase", "piso_lab")))
    siguiente()
    # 3. Puertas
    capturar(n, "puertas"); n += 1
    QMetaObject.invokeMethod(a, "elegirPuertas", Q_ARG("QVariant", cfg.get("puertas", 2)))
    a.setProperty("tipoPuerta", "advanced")
    siguiente()
    # 4. Cámara: sin datos, Siguiente no avanza
    anotar("camara_vacia")
    capturar(n, "camara_vacia"); n += 1
    siguiente()
    anotar("camara_siguiente_sin_datos")
    capturar(n, "camara_errores"); n += 1
    # Capacidad con el teclado numérico real: la vista previa sigue a lo que se escribe
    teclado_num = next(o for o in ventana.findChildren(QObject)
                       if type(o).__name__ == "TecladoNumericoController")
    QMetaObject.invokeMethod(a, "editarCapacidad")
    esperar()
    def digito(d):
        QMetaObject.invokeMethod(teclado_num, "presionarDigito", Q_ARG(str, d))
        esperar(120)
    def elegir_carga(n):
        sel = a.findChild(QObject, "selectorCarga")
        QMetaObject.invokeMethod(sel, "elegido", Q_ARG(int, n))
        esperar()
    elegir_carga(1)                                      # Vertical
    anotar("camara_solo_carga")
    digito("4")
    anotar("camara_escribiendo_4")                       # 4 L: fuera de rango, "—"
    digito("5")
    anotar("camara_escribiendo_45")                      # en vivo, sin confirmar
    capturar(n, "camara_teclado"); n += 1
    QMetaObject.invokeMethod(teclado_num, "confirmar")
    esperar(600)
    anotar("camara_45V")
    a.setProperty("capacidadLitros", 19)                 # fuera de rango (escrito a mano)
    esperar()
    siguiente()
    anotar("camara_19")
    a.setProperty("capacidadLitros", 2000)
    elegir_carga(2)                                      # Horizontal
    anotar("camara_2000H")
    capturar(n, "camara"); n += 1
    siguiente()
    anotar("tras_camara")
    # 5. Enfriamiento
    capturar(n, "enfriamiento"); n += 1
    a.setProperty("nivelEnfriamiento", 2)
    siguiente()
    # 6. Fuente de vapor
    capturar(n, "vapor"); n += 1
    a.setProperty("fuenteVapor", "generator")
    siguiente()
    # 7. Datos
    anotar("datos")
    capturar(n, "datos"); n += 1
    siguiente()
    # 8. Contraseñas (LIC-02): sin ellas Siguiente no avanza
    siguiente()
    anotar("contrasenas_vacias")
    obs["erroresContrasenas"] = sorted(a.property("errores").toVariant())
    for campo, valor in (("clave_admin", "admin-nueva-1"), ("confirmacion_admin", "admin-nueva-1"),
                         ("clave_ingeniero", "inge-nueva-1"), ("confirmacion_ingeniero", "inge-nueva-1")):
        a.setProperty(campo, valor)
    capturar(n, "contrasenas"); n += 1
    siguiente()
    # 9. Resumen
    anotar("resumen")
    filas = [f["clave"] for f in a.property("filasResumen").toVariant()]
    obs["filasResumen"] = filas
    obs["resumenEquipo"] = next((f["valor"] for f in a.property("filasResumen").toVariant()
                                 if f["clave"] == "resumen_equipo"), None)
    capturar(n, "resumen"); n += 1
    QMetaObject.invokeMethod(a, "instalar")
    esperar()
    obs["instalado"] = [{"model_id": p.model_id, "capacidad_litros": p.capacidad_litros,
                         "tipo_carga": p.tipo_carga, "equipment_class": p.equipment_class.value}
                        for p in instalados]
    obs["terminado"] = a.property("terminado")
    obs["clavesFijadas"] = claves_fijadas
    capturar(n, "listo")
    obs["avisos"] = avisos[:20]
    obs["capturas"] = capturas
    print("RESULTADO=" + json.dumps(obs, ensure_ascii=False))
''')


def recorrer(idioma: str = "es", capturas: bool = False, carpeta=None, **extra) -> dict:
    """carpeta: dónde guardar las capturas (por defecto, las de la tanda 7)."""
    carpeta = Path(carpeta) if carpeta else CAPTURAS
    if capturas:
        carpeta.mkdir(parents=True, exist_ok=True)
    cfg = {"idioma": idioma, "capturas": str(carpeta) if capturas else "", **extra}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


if __name__ == "__main__":
    r = recorrer(sys.argv[1] if len(sys.argv) > 1 else "es", capturas=True)
    print(json.dumps(r, ensure_ascii=False, indent=2))
