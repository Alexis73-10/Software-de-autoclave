# tests/banco/rv_interaccion.py
#
# Revisión visual (RV, etapa E, 19-nov): arnés de interacción. Levanta la UI
# completa de una puerta (autoclave.ui_qml.app.main, como ui_qml/lanzar.py) en
# una ventana VISIBLE de 1200x1920 (lienzo lógico; con --escala la ventana se
# dibuja más pequeña para que quepa en el monitor del PC y Cristian la vea en
# primer plano) contra el backend de AUTOCLAVE_BACKEND_URL, y la opera con
# eventos reales de ratón y teclado de QTest (presionar, mover y soltar en el
# centro visible del control, buscado por objectName o texto). No llama slots
# ni cambia propiedades para simular un toque.
#
# Después de cada paso: espera a que la pantalla se estabilice, guarda
# interaccion/<flujo>/NN_<paso>.png (grabWindow), registra las advertencias del
# motor QML y verifica el resultado esperado. Si el ítem que recibe el toque en
# el centro del control no es el control (otro ítem que acepta toques lo
# tapa), lo anota como «toque_desviado».
#
#   python tests/banco/rv_interaccion.py --puerta 1 --flujos arranque login ...
#       [--idioma es] [--escala 0.42] [--x 0] [--salida DIR]
#   python tests/banco/rv_interaccion.py --puerta 2 --espejo --salida DIR
#       (pantalla 2: captura cuando aparece <salida>/_disparo/<nombre>.txt)
#
# No es una prueba automática. Nunca acciona Apagar equipo, Reiniciar PC,
# instalación, respaldos, configurar módulo, red, fecha/hora ni correo real.

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# controles que nunca se accionan (se reportan «no accionado por seguridad»)
PROHIBIDOS = ("apagar", "reiniciar", "restaurar", "configurarModulo", "redModulo", "respaldo",
              "instalacion", "fechaHora", "enviarCorreo", "botonEnviar")


def _args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerta", type=int, default=1)
    ap.add_argument("--flujos", nargs="*", default=[])
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--escala", type=float, default=0.42)
    ap.add_argument("--x", type=int, default=0)
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "informes" / "revision_visual" / "interaccion"))
    ap.add_argument("--espejo", action="store_true")
    ap.add_argument("--ancho", type=int, default=1200)
    ap.add_argument("--alto", type=int, default=1920)
    return ap.parse_args()


A = _args()
os.environ["QT_SCALE_FACTOR"] = f"{A.escala:g}"
os.environ.setdefault("AUTOCLAVE_REINICIO_PC", "0")
SALIDA = Path(A.salida)
SALIDA.mkdir(parents=True, exist_ok=True)

from PySide6.QtCore import QPointF, Qt, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication, QWindow  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402,F401
from PySide6.QtTest import QTest  # noqa: E402

AVISOS = []


def _manejador(tipo, contexto, texto):
    if "Binding loop" in texto or "QFontDatabase" in texto or "no longer ships fonts" in texto:
        return
    AVISOS.append(texto)


qInstallMessageHandler(_manejador)


def _mostrar(self):
    self.setFlags(self.flags() | Qt.WindowStaysOnTopHint)
    self.setGeometry(A.x, 0, A.ancho, A.alto)
    self.show()
    self.raise_()
    self.requestActivate()


QWindow.showFullScreen = _mostrar


# ── utilidades sobre el árbol de ítems ──────────────────────────────────────

class Arnes:
    def __init__(self, ventana):
        self.v = ventana
        self.flujo = "sin_flujo"
        self.n = 0
        self.registro = []      # una entrada por paso
        self.resultados = {}    # flujo -> lista de pasos

    # búsqueda
    def items(self, raiz=None):
        pila = [raiz or self.v.contentItem()]
        while pila:
            it = pila.pop()
            yield it
            pila.extend(it.childItems())

    def visible(self, it):
        if not it.isVisible() or it.opacity() <= 0.01 or it.width() <= 0 or it.height() <= 0:
            return False
        c = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
        return 0 <= c.x() <= A.ancho and 0 <= c.y() <= A.alto

    def buscar(self, nombre=None, texto=None, prefijo=None, todos=False):
        hallados = []
        for it in self.items():
            if not self.visible(it):
                continue
            on = it.objectName()
            if nombre is not None and on != nombre:
                continue
            if prefijo is not None and not on.startswith(prefijo):
                continue
            if texto is not None:
                t = it.property("text")
                if not isinstance(t, str) or texto.lower() not in t.lower():
                    continue
            hallados.append(it)
        if todos:
            return hallados
        return hallados[0] if hallados else None

    def esperar(self, cond, s=6.0):
        lim = time.monotonic() + s
        while time.monotonic() < lim:
            QTest.qWait(150)
            try:
                if cond():
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def esperar_item(self, s=6.0, **kw):
        it = None

        def c():
            nonlocal it
            it = self.buscar(**kw)
            return it is not None
        self.esperar(c, s)
        return it

    # ítem que recibe el toque en (x, y): el más alto que acepta botones
    def receptor(self, x, y):
        def rec(it):
            hijos = sorted(it.childItems(), key=lambda h: h.z())
            for h in reversed(hijos):
                if not h.isVisible() or h.opacity() <= 0.01 or not h.isEnabled():
                    continue
                p = h.mapFromScene(QPointF(x, y))
                if h.clip() and not h.contains(p):
                    continue
                r = rec(h)
                if r is not None:
                    return r
                if h.contains(p) and h.acceptedMouseButtons() != Qt.NoButton:
                    return h
            return None
        return rec(self.v.contentItem())

    def _relacionados(self, a, b):
        # una MouseArea hermana que cubre el control (patrón de los campos) cuenta
        # como del control: se compara contra el subárbol del padre del control
        if a.parentItem() is not None:
            x = b
            while x is not None:
                if x == a.parentItem():
                    return True
                x = x.parentItem()
        x = b
        while x is not None:
            if x == a:
                return True
            x = x.parentItem()
        x = a
        while x is not None:
            if x == b:
                return True
            x = x.parentItem()
        return False

    def centro(self, it):
        p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
        return p.x(), p.y()

    # acciones
    def tocar(self, it, nombre_paso=None):
        if it is None:
            return False
        on = it.objectName()
        if any(p.lower() in on.lower() for p in PROHIBIDOS):
            self.nota(f"no accionado por seguridad: {on}")
            return False
        x, y = self.centro(it)
        r = self.receptor(x, y)
        if r is not None and not self._relacionados(it, r):
            self.nota(f"toque_desviado: centro de {on or it.property('text')} lo recibe "
                      f"{type(r).__name__}:{r.objectName()} (padre {r.parentItem().objectName() if r.parentItem() else ''})")
        pt = QPointF(x, y).toPoint()
        QTest.mousePress(self.v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.qWait(60)
        QTest.mouseRelease(self.v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.qWait(500)
        return True

    def tocar_en(self, x, y, descripcion=""):
        """Toque en coordenadas lógicas de la ventana (controles sin objectName)."""
        r = self.receptor(x, y)
        if r is None:
            self.nota(f"toque en ({x},{y}) {descripcion}: ningún ítem acepta el toque")
        pt = QPointF(x, y).toPoint()
        QTest.mousePress(self.v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.qWait(60)
        QTest.mouseRelease(self.v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.qWait(500)

    def arrastrar(self, it, dx, dy=0, pasos=20, soltar=True):
        x, y = self.centro(it)
        p0 = QPointF(x, y).toPoint()
        QTest.mousePress(self.v, Qt.LeftButton, Qt.NoModifier, p0)
        for i in range(1, pasos + 1):
            QTest.mouseMove(self.v, QPointF(x + dx * i / pasos, y + dy * i / pasos).toPoint())
            QTest.qWait(25)
        if soltar:
            QTest.mouseRelease(self.v, Qt.LeftButton, Qt.NoModifier,
                               QPointF(x + dx, y + dy).toPoint())
        QTest.qWait(700)

    def teclear(self, texto):
        # teclado en pantalla: cada carácter es una Tecla con ese texto
        for ch in texto:
            tecla = None
            if ch == " ":
                tecla = self.buscar(nombre="teclaEspacio")
            else:
                for it in self.items():
                    if self.visible(it) and it.property("texto") == ch:
                        tecla = it
                        break
            if tecla is None:
                cand = [(it.property("texto"), it.isVisible(), round(it.opacity(), 2),
                         tuple(round(v) for v in self.centro(it)))
                        for it in self.items() if isinstance(it.property("texto"), str)][:8]
                self.nota(f"sin tecla para {ch!r}; candidatas {cand}")
                continue
            self.tocar(tecla)

    def nota(self, texto):
        self.registro.append({"flujo": self.flujo, "paso": self.n, "nota": texto})
        print("NOTA", self.flujo, self.n, texto, flush=True)

    def captura(self, paso, esperado=None, ok=None, espejo=False):
        self.n += 1
        QTest.qWait(600)
        d = SALIDA / self.flujo
        d.mkdir(parents=True, exist_ok=True)
        archivo = d / f"{self.n:02d}_{paso}.png"
        self.v.grabWindow().save(str(archivo))
        if espejo:
            disparo = SALIDA / "_disparo"
            disparo.mkdir(exist_ok=True)
            (disparo / f"{self.flujo}__{self.n:02d}_{paso}_p2.txt").write_text("1")
        avisos = AVISOS[:]
        AVISOS.clear()
        entrada = {"flujo": self.flujo, "paso": self.n, "nombre": paso, "captura": str(archivo.relative_to(SALIDA)),
                   "esperado": esperado, "ok": ok, "avisos": avisos[:20]}
        self.registro.append(entrada)
        print("PASO", self.flujo, self.n, paso, "ok=" + str(ok), "avisos=" + str(len(avisos)), flush=True)
        return ok


def status():
    import requests
    try:
        return requests.get(os.environ.get("AUTOCLAVE_BACKEND_URL", "http://127.0.0.1:8000") + "/status",
                            timeout=2).json()
    except Exception as ex:  # noqa: BLE001
        return {"error": repr(ex)}


def ejecutar_flujos(app):
    ventana = [w for w in QGuiApplication.topLevelWindows() if isinstance(w, QQuickWindow)][0]
    h = Arnes(ventana)
    QTest.qWait(1500)
    if A.espejo:
        disparo = SALIDA / "_disparo"
        disparo.mkdir(exist_ok=True)
        fin = SALIDA / "_fin.txt"
        while not fin.exists():
            QTest.qWait(200)
            for f in sorted(disparo.glob("*_p2.txt")):
                flujo, paso = f.stem.split("__", 1)
                d = SALIDA / flujo
                d.mkdir(parents=True, exist_ok=True)
                QTest.qWait(400)
                ventana.grabWindow().save(str(d / f"{paso}.png"))
                f.unlink()
        return 0
    from tests.banco import rv_flujos
    for nombre in A.flujos:
        h.flujo = f"{nombre}_{A.idioma}"
        h.n = 0
        try:
            getattr(rv_flujos, "flujo_" + nombre)(h, status)
        except Exception:  # noqa: BLE001
            h.nota("excepción del arnés: " + traceback.format_exc()[-800:])
            h.captura("excepcion", ok=False)
        (SALIDA / f"registro_{h.flujo}.json").write_text(
            json.dumps([r for r in h.registro if r["flujo"] == h.flujo], ensure_ascii=False, indent=1),
            encoding="utf-8")
    return 0


QGuiApplication.exec = lambda self: ejecutar_flujos(self)

if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    from autoclave.ui_qml import app as app_ui
    sys.exit(app_ui.main(["--door", str(A.puerta)]))
