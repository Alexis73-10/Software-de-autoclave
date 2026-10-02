pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Tema
import "grafica_ejes.mjs" as Ejes

// Tarjeta "GRÁFICA DEL CICLO" de la pantalla de ciclo en curso
// (planeacion_pantalla_ciclo_en_curso.md §8; referencia:
// images/pantalla_ciclo_con_grafica_editada.png, tarjeta en x 33..1162, y 804..1598).
//
// Geometría: px del mockup relativos a la esquina de la tarjeta, escalados por m()
// (escala = px reales por px del mockup, la misma de la pantalla). El alto es
// flexible: cabecera, leyenda e íconos de fase quedan arriba; el eje X y su título
// bajan con el alto sobrante (yb()), y el área de trazado absorbe la diferencia.
//
// Dibujo propio con QtQuick Shapes (PathPolyline), sin QtCharts. Ejes y
// decimación: grafica_ejes.mjs (probado en tests/test_grafica_ejes_js.py).
// Solo presentación: no calcula tiempos de proceso; recibe t (min) del backend.
Item {
    id: raiz

    property real escala: 1.0
    property var textosJson: ({})

    // Datos: arreglos paralelos ordenados por tiempo (t_min en minutos desde el
    // inicio del ciclo); los valores sin lectura van como null.
    property var datos: ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
    // Inicio de cada fase de la UI en el ciclo actual, en orden: [{clave, inicioMin}]
    property var fases: []
    property real tiempoActualMin: 0
    // Cursor: minuto señalado; NaN = oculto
    property real cursorMin: NaN

    signal tiemposPulsado()
    signal pantallaCompletaPulsado()

    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }

    // Series de la gráfica. Los sensores mostrados serán configurables desde
    // configuración en el futuro; por ahora esta es la única lista.
    readonly property var series: [
        { clave: "temp_camara", texto: tx("ciclo", "serie_temp_camara"), color: "#6599FC",
          eje: "izquierdo", unidad: tx("unidades", "temperatura") },
        { clave: "temp_ref", texto: tx("ciclo", "serie_temp_ref"), color: "#9732DA",
          eje: "izquierdo", unidad: tx("unidades", "temperatura") },
        { clave: "pres_camara", texto: tx("ciclo", "serie_presion"), color: "#00CCB0",
          eje: "derecho", unidad: tx("unidades", "presion") },
    ]

    readonly property QtObject paleta: QtObject {
        readonly property color borde: "#E5E5E5"
        readonly property color titulo: "#010006"
        readonly property color texto: "#1A1A1A"
        readonly property color separador: "#D8D8D8"
        readonly property color cuadricula: "#D4D4D4"
        readonly property color eje: "#DADADA"
        readonly property color divisorFase: "#BCBCBC"
        readonly property color iconoFase: "#505050"
        readonly property color etiquetaEje: "#000000"
        readonly property color tituloEje: "#333333"
        readonly property color bordeBoton: "#C8C8C8"
        readonly property color cursor: "#3A3A3A"
    }

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // alto sobrante respecto al mockup (794): lo absorbe el área de trazado
    readonly property real _extra: height - m(794)
    function yb(v) { return m(v) + _extra }

    readonly property string iconosColor: "../../assets/iconos/color/"

    // ---- ejes ----
    function _maximo(claves) {
        let mx = null
        for (const c of claves) {
            const arr = raiz.datos[c] || []
            for (const v of arr)
                if (v !== null && v !== undefined && isFinite(v) && (mx === null || v > mx)) mx = v
        }
        return mx
    }
    readonly property var ejeX: Ejes.ejeX(tiempoActualMin)
    readonly property var ejeIzquierdo: Ejes.ejeY(_maximo(series.filter(s => s.eje === "izquierdo").map(s => s.clave)))
    readonly property var ejeDerecho: Ejes.ejeY(_maximo(series.filter(s => s.eje === "derecho").map(s => s.clave)))

    // área de trazado: x de datos 0..ejeX.maximo en 93..1035; cuadrícula 68..1059
    readonly property real xDato0: m(93)
    readonly property real xDato1: m(1035)
    readonly property real yArriba: m(279)
    readonly property real yAbajo: yb(709)
    function xDe(tMin) { return xDato0 + (tMin / ejeX.maximo) * (xDato1 - xDato0) }
    function yDe(v, eje) {
        const e = eje === "derecho" ? ejeDerecho : ejeIzquierdo
        return yAbajo - (v / e.maximo) * (yAbajo - yArriba)
    }

    function _puntos(serie) {
        const r = Ejes.decimar(raiz.datos.t_min || [], raiz.datos[serie.clave] || [],
                               0, ejeX.maximo, Math.max(1, xDato1 - xDato0))
        const pts = []
        for (let i = 0; i < r.x.length; i++)
            pts.push(Qt.point(xDe(r.x[i]), yDe(r.y[i], serie.eje)))
        return pts
    }

    // índice de la lectura más cercana a t (búsqueda binaria sobre t_min)
    function _indiceCercano(t) {
        const ts = raiz.datos.t_min || []
        if (ts.length === 0) return -1
        let lo = 0, hi = ts.length - 1
        while (hi - lo > 1) {
            const mid = (lo + hi) >> 1
            if (ts[mid] < t) lo = mid; else hi = mid
        }
        return Math.abs(ts[lo] - t) <= Math.abs(ts[hi] - t) ? lo : hi
    }

    function _formatoMmSs(tMin) {
        const s = Math.max(0, Math.round(tMin * 60))
        const mm = Math.floor(s / 60), ss = s % 60
        return (mm < 10 ? "0" + mm : "" + mm) + ":" + (ss < 10 ? "0" + ss : "" + ss)
    }

    // ======================= tarjeta =======================
    Rectangle {
        anchors.fill: parent
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.borde
    }

    // Texto ubicado por línea base (bl) y por centro (cx), borde izquierdo (lx) o
    // borde derecho (rx), en px del mockup relativos a la tarjeta.
    component Texto: Text {
        property real cx: -1
        property real lx: -1
        property real rx: -1
        property real bl: 0
        property real tam: 16
        font.pixelSize: raiz.fuente(tam)
        font.family: Tipografia.familia
        x: lx >= 0 ? raiz.m(lx) : rx >= 0 ? raiz.m(rx) - width : raiz.m(cx) - width / 2
        y: raiz.m(bl) - baselineOffset
    }

    // ---- cabecera ----
    Texto {
        lx: 48; bl: 62; tam: 26
        text: raiz.tx("ciclo", "grafica")
        color: raiz.paleta.titulo
        font.weight: Tipografia.pesoBold
    }

    // leyenda
    Repeater {
        model: raiz.series
        delegate: Item {
            id: leyenda
            required property var modelData
            required property int index
            readonly property var _cx: [98, 327, 509]
            readonly property var _lx: [125, 354, 540]
            anchors.fill: parent
            Rectangle {
                x: raiz.m(leyenda._cx[leyenda.index] - 10); y: raiz.m(96)
                width: raiz.m(20); height: width; radius: width / 2
                color: leyenda.modelData.color
            }
            Texto {
                lx: leyenda._lx[leyenda.index]; bl: 114; tam: 21
                text: leyenda.modelData.texto
                color: raiz.paleta.texto
            }
        }
    }

    // botón "Tiempos" (desplegable: §8, Fase 3)
    Rectangle {
        x: raiz.m(856); y: raiz.m(43); width: raiz.m(154); height: raiz.m(58)
        radius: raiz.m(6)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        Text {
            x: raiz.m(25)
            anchors.verticalCenter: parent.verticalCenter
            text: raiz.tx("ciclo", "tiempos")
            color: raiz.paleta.texto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(20)
        }
        Image {
            x: raiz.m(116); y: raiz.m(24)
            width: raiz.m(14); height: width
            source: raiz.iconosColor + "chevron_abajo.svg"
            sourceSize.width: width; sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.tiemposPulsado() }
    }

    // botón de pantalla completa
    Rectangle {
        x: raiz.m(1037); y: raiz.m(43); width: raiz.m(58); height: raiz.m(58)
        radius: raiz.m(6)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        Image {
            anchors.centerIn: parent
            width: raiz.m(40); height: width   // tinta 33 px (viewBox 4..44 de 48)
            source: raiz.iconosColor + "pantalla_completa.svg"
            sourceSize.width: width; sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.pantallaCompletaPulsado() }
    }

    Rectangle {
        x: raiz.m(61); y: raiz.m(146); width: raiz.m(1069 - 61); height: raiz.m(2)
        color: raiz.paleta.separador
    }

    // ---- unidades de los ejes ----
    Texto {
        lx: 21; bl: 246; tam: 20
        text: raiz.tx("unidades", "temperatura")
        color: raiz.paleta.etiquetaEje
    }
    Texto {
        lx: 1075; bl: 245; tam: 20
        text: raiz.tx("unidades", "presion")
        color: raiz.paleta.etiquetaEje
    }

    // ---- cuadrícula y etiquetas Y (mismas divisiones en ambos ejes) ----
    Repeater {
        model: raiz.ejeIzquierdo.divisiones + 1
        delegate: Item {
            id: linea
            required property int index
            readonly property real yLinea: raiz.yAbajo - linea.index * (raiz.yAbajo - raiz.yArriba) / raiz.ejeIzquierdo.divisiones
            anchors.fill: parent
            Rectangle {
                x: raiz.m(68); y: linea.yLinea - height / 2
                width: raiz.m(1059 - 68); height: Math.max(1, raiz.m(1.2))
                color: linea.index === 0 ? raiz.paleta.eje : raiz.paleta.cuadricula
            }
            Text {
                x: raiz.m(55) - width
                y: linea.yLinea - height / 2 - raiz.m(3)
                text: Math.round(linea.index * raiz.ejeIzquierdo.paso * 100) / 100
                color: raiz.paleta.etiquetaEje
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
            Text {
                x: raiz.m(1075)
                y: linea.yLinea - height / 2 - raiz.m(3)
                text: Math.round(linea.index * raiz.ejeDerecho.paso * 100) / 100
                color: raiz.paleta.etiquetaEje
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
        }
    }

    // ---- eje X: marcas y etiquetas ----
    Repeater {
        model: Math.round(raiz.ejeX.maximo / raiz.ejeX.paso) + 1
        delegate: Item {
            id: marca
            required property int index
            readonly property real xMarca: raiz.xDe(marca.index * raiz.ejeX.paso)
            anchors.fill: parent
            Rectangle {
                x: marca.xMarca - width / 2; y: raiz.yAbajo
                width: Math.max(1, raiz.m(1.2)); height: raiz.m(6)
                color: raiz.paleta.eje
            }
            Text {
                x: marca.xMarca - width / 2
                y: raiz.yb(741) - baselineOffset
                text: marca.index * raiz.ejeX.paso
                color: raiz.paleta.etiquetaEje
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
        }
    }
    Text {
        x: raiz.m(564) - width / 2
        y: raiz.yb(779) - baselineOffset
        text: raiz.tx("ciclo", "grafica_eje_tiempo")
        color: raiz.paleta.tituloEje
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(20)
    }

    // ---- divisores de fase e íconos ----
    // Cada fase ocupa [inicio, inicio de la siguiente | tiempo actual]; la línea
    // punteada marca el comienzo de cada fase salvo la primera (en t = 0).
    Repeater {
        model: raiz.fases
        delegate: Item {
            id: tramo
            required property var modelData
            required property int index
            readonly property real inicio: tramo.modelData.inicioMin
            readonly property real fin: tramo.index + 1 < raiz.fases.length
                ? raiz.fases[tramo.index + 1].inicioMin : raiz.tiempoActualMin
            anchors.fill: parent

            Shape {
                visible: tramo.inicio > 0
                anchors.fill: parent
                ShapePath {
                    strokeColor: raiz.paleta.divisorFase
                    strokeWidth: Math.max(1, raiz.m(1.5))
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [4, 3]
                    fillColor: "transparent"
                    startX: raiz.xDe(tramo.inicio); startY: raiz.m(164)
                    PathLine { x: raiz.xDe(tramo.inicio); y: raiz.yAbajo }
                }
            }
            // ícono blanco teñido de gris (misma técnica que IconoTenido de Ciclo.qml)
            Image {
                id: iconoFase
                visible: false
                width: raiz.m(52); height: width   // tinta ≈ 43 px
                x: (raiz.xDe(tramo.inicio) + raiz.xDe(tramo.fin)) / 2 - width / 2
                y: raiz.m(205) - height / 2
                source: raiz.iconosColor + "fase_" + tramo.modelData.clave + ".svg"
                sourceSize.width: width; sourceSize.height: height
            }
            MultiEffect {
                visible: raiz.xDe(tramo.fin) - raiz.xDe(tramo.inicio) > raiz.m(40)
                x: iconoFase.x; y: iconoFase.y; width: iconoFase.width; height: iconoFase.height
                source: iconoFase
                colorization: 1.0
                colorizationColor: raiz.paleta.iconoFase
            }
        }
    }

    // ---- series ----
    Item {
        id: areaTrazado
        x: 0; y: raiz.yArriba - raiz.m(10)
        width: raiz.width; height: raiz.yAbajo - y + raiz.m(2)
        clip: true
        Repeater {
            model: raiz.series
            delegate: Shape {
                id: trazo
                required property var modelData
                x: 0; y: -areaTrazado.y
                width: raiz.width; height: raiz.height
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: trazo.modelData.color
                    strokeWidth: raiz.m(3)
                    fillColor: "transparent"
                    joinStyle: ShapePath.RoundJoin
                    capStyle: ShapePath.RoundCap
                    PathPolyline { path: raiz._puntos(trazo.modelData) }
                }
            }
        }
    }

    // ---- cursor y globo de valores ----
    Item {
        id: cursor
        readonly property int indice: isNaN(raiz.cursorMin) ? -1 : raiz._indiceCercano(raiz.cursorMin)
        readonly property real tCursor: indice >= 0 ? raiz.datos.t_min[indice] : 0
        readonly property real xCursor: raiz.xDe(tCursor)
        visible: indice >= 0
        anchors.fill: parent

        Rectangle {
            x: cursor.xCursor - width / 2; y: raiz.m(272)
            width: raiz.m(3); height: raiz.yAbajo - y - raiz.m(8)
            color: raiz.paleta.cursor
        }
        Repeater {
            model: raiz.series
            delegate: Rectangle {
                id: punto
                required property var modelData
                readonly property var valor: cursor.indice >= 0 ? raiz.datos[punto.modelData.clave][cursor.indice] : null
                visible: punto.valor !== null && punto.valor !== undefined
                x: cursor.xCursor - width / 2
                y: (punto.visible ? raiz.yDe(punto.valor, punto.modelData.eje) : 0) - height / 2
                width: raiz.m(18); height: width; radius: width / 2
                color: punto.modelData.color
                border.color: "white"; border.width: raiz.m(2)
            }
        }

        // Globo: 220 x 145 en el mockup, a la derecha del cursor salvo que no quepa;
        // nunca se sale del área de la tarjeta.
        Rectangle {
            id: globo
            width: raiz.m(220); height: raiz.m(145)
            x: Math.max(raiz.m(8), Math.min(cursor.xCursor - raiz.m(34), raiz.width - width - raiz.m(8)))
            y: Math.min(raiz.yAbajo - height - raiz.m(45), raiz.m(519) + raiz._extra / 2)
            radius: raiz.m(14)
            color: Colores.fondoTarjeta
            border.width: raiz.m(1.5); border.color: raiz.paleta.borde
            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: "#30000000"
                shadowVerticalOffset: raiz.m(2)
                shadowBlur: 0.5
            }
            Text {
                x: raiz.m(18); y: raiz.m(36) - baselineOffset
                text: raiz._formatoMmSs(cursor.tCursor) + " " + raiz.tx("unidades", "tiempo")
                color: raiz.paleta.texto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoMedium
                font.pixelSize: raiz.fuente(21)
            }
            Repeater {
                model: raiz.series
                delegate: Item {
                    id: filaGlobo
                    required property var modelData
                    required property int index
                    readonly property var valor: cursor.indice >= 0 ? raiz.datos[filaGlobo.modelData.clave][cursor.indice] : null
                    readonly property real bl: raiz.m(61 + filaGlobo.index * 29)
                    anchors.fill: parent
                    Rectangle {
                        x: raiz.m(17); y: filaGlobo.bl - raiz.m(10)
                        width: raiz.m(11); height: width; radius: width / 2
                        color: filaGlobo.modelData.color
                    }
                    Text {
                        x: raiz.m(35); y: filaGlobo.bl - baselineOffset
                        text: filaGlobo.modelData.texto
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(13)
                    }
                    Text {
                        // alineado a la derecha del globo (mockup: termina en x = 211 de 220)
                        x: raiz.m(211) - width; y: filaGlobo.bl - baselineOffset
                        text: (filaGlobo.valor === null || filaGlobo.valor === undefined
                               ? raiz.tx("sistema", "sin_lectura")
                               : Number(filaGlobo.valor).toFixed(1)) + " " + filaGlobo.modelData.unidad
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(16)
                    }
                }
            }
        }
    }
}
