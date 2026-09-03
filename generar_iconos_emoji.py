# Script de un solo uso: exporta los emojis "🔧" (herramientas) y "👤"
# (login) como PNG con fondo transparente, para tenerlos como archivo en
# vez de depender del emoji como texto. Corre en una ventana real (no
# headless) porque necesita la fuente de emojis a color de Windows.
#
# Uso: python generar_iconos_emoji.py
# Aparece una ventana chiquita un instante y se cierra sola.

import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage

EMOJIS = {
    "icono-herramientas": "\U0001F527",
    "icono-login": "\U0001F464",
}

# Fondo magenta como "color clave": se recorta a transparente después.
# Ningún emoji del sistema usa magenta puro, así que es seguro.
QML_TEMPLATE = """
import QtQuick
Item {{
    width: 256; height: 256
    Rectangle {{ anchors.fill: parent; color: "#FF00FF" }}
    Text {{
        anchors.fill: parent
        text: "{emoji}"
        font.family: "Segoe UI Emoji"
        font.pixelSize: 210
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }}
}}
"""


def _quitar_magenta(img: QImage) -> QImage:
    img = img.convertToFormat(QImage.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.red() > 240 and c.green() < 15 and c.blue() > 240:
                c.setAlpha(0)
                img.setPixelColor(x, y, c)
    return img


def main() -> None:
    app = QGuiApplication(sys.argv)
    destino = "src/autoclave/ui_qml/assets"

    for nombre, emoji in EMOJIS.items():
        qml_path = f"_{nombre}_tmp.qml"
        with open(qml_path, "w", encoding="utf-8") as f:
            f.write(QML_TEMPLATE.format(emoji=emoji))

        view = QQuickView()
        view.setSource(QUrl.fromLocalFile(qml_path))
        for e in view.errors():
            print("QML ERROR:", e.toString())
        view.resize(256, 256)
        view.show()
        for _ in range(30):
            app.processEvents()

        img = _quitar_magenta(view.grabWindow())
        out = f"{destino}/{nombre}.png"
        img.save(out)
        print("Generado", out)
        view.close()

    print("Listo. Cierra esta ventana si sigue abierta.")


if __name__ == "__main__":
    sys.exit(main())
