
import QtQuick
import Tema
import "Pantallas"
Window {
    width: 1024; height: 1638; visible: true
    // elide/wrapMode son enums: se leen aquí, en JS, como enteros
        function revisar() {
            const raiz = contentItem
            const malos = []; const vistos = []
            function rec(it) {
                const hijos = it.children || []
                for (let i = 0; i < hijos.length; ++i) {
                    const h = hijos[i]
                    if (!h.visible || h.opacity === 0) continue
                    if (h.truncated !== undefined && h.elide !== undefined
                            && typeof h.text === "string" && h.text.trim() !== "") { vistos.push(h.text)
                        if (h.truncated)
                            malos.push({tipo: "truncado", texto: h.text, obj: h.objectName,
                                        ancho: Math.round(h.width)})
                        else if (h.elide === Text.ElideNone && h.wrapMode === Text.NoWrap
                                 && h.width > 0 && h.contentWidth > h.width + 2)
                            malos.push({tipo: "desborda", texto: h.text, obj: h.objectName,
                                        ancho: Math.round(h.width),
                                        contenido: Math.round(h.contentWidth)})
                    }
                    rec(h)
                }
            }
            rec(raiz)
            return JSON.stringify({malos: malos, vistos: vistos})
        }
    Binding { target: Escala; property: "factor"; value: 0.853333 }
    QtObject { id: puenteFalso; property string machineState: "PREPARADO"
               property bool connected: true }
    Opciones { objectName: "pantalla"; anchors.fill: parent }
}
