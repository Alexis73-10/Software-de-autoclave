pragma ComponentBehavior: Bound
import QtQuick
import Tema

// Resumen de ciclos de un periodo (pestaña Resumen de Reportes): totales por
// resultado con su porcentaje y una barra de proporciones, la tabla por
// programa y las causas de fallo. Solo presentación: recibe `datos` ya
// formateado (ui_qml/domain/reporte_resumen.py). Se desplaza si no cabe.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Flickable {
    id: raiz

    property real escala: 1
    property var textosJson: ({})
    property var datos: ({ total: "0", totales: [], por_programa: [], causas: [] })

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function tx(clave) {
        const s = textosJson ? textosJson["reportes"] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }
    function colorDe(clave) {
        return clave === "completados" ? Colores.menuVerdeTexto
             : clave === "fallos" ? Colores.peligroTexto
             : clave === "cancelados" ? Colores.advertenciaTexto
             : Colores.textoSecundario
    }

    contentHeight: contenido.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    component Titulo: Text {
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(28)
    }
    // Fila de tabla: celdas [texto] con proporción de ancho; la primera a la
    // izquierda y el resto a la derecha
    component FilaTabla: Item {
        id: fila
        property var celdas: []
        property var proporciones: []
        property var colores: []
        property bool encabezado: false
        width: parent.width
        height: raiz.m(encabezado ? 56 : 68)
        Repeater {
            model: fila.celdas.length
            Text {
                required property int index
                readonly property real _x: {
                    let x = 0
                    for (let k = 0; k < index; k++) x += fila.proporciones[k]
                    return x * fila.width
                }
                x: _x
                width: fila.proporciones[index] * fila.width - raiz.m(12)
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: index === 0 ? Text.AlignLeft : Text.AlignRight
                elide: Text.ElideRight
                text: fila.celdas[index]
                color: fila.encabezado ? Colores.textoSecundario
                     : (fila.colores[index] ?? Colores.textoPrimario)
                font.family: Tipografia.familia
                font.weight: fila.encabezado || index === 0 ? Tipografia.pesoSemiBold : Tipografia.pesoBold
                font.pixelSize: raiz.fuente(fila.encabezado ? 20 : 24)
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: raiz.m(fila.encabezado ? 2 : 1)
            color: Colores.bordeDivisor
        }
    }

    Column {
        id: contenido
        width: raiz.width
        spacing: raiz.m(24)

        // ---------- totales ----------
        Row {
            id: totales
            objectName: "totalesResumen"
            width: parent.width
            readonly property real _ancho: width / 5
            Column {
                width: totales._ancho
                spacing: raiz.m(4)
                Text {
                    width: parent.width - raiz.m(8)
                    wrapMode: Text.WordWrap
                    text: raiz.tx("total")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(20)
                }
                Text {
                    objectName: "totalResumen"
                    text: raiz.datos.total
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(52)
                }
            }
            Repeater {
                model: raiz.datos.totales
                Column {
                    id: total
                    required property var modelData
                    objectName: "total_" + modelData.clave
                    width: totales._ancho
                    spacing: raiz.m(4)
                    Text {
                        width: parent.width - raiz.m(8)
                        wrapMode: Text.WordWrap
                        text: raiz.tx(total.modelData.clave)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(20)
                    }
                    Row {
                        spacing: raiz.m(8)
                        Text {
                            id: cantidad
                            text: total.modelData.cantidad
                            color: raiz.colorDe(total.modelData.clave)
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: raiz.fuente(52)
                        }
                        Text {
                            anchors.baseline: cantidad.baseline
                            text: total.modelData.porcentaje
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(22)
                        }
                    }
                }
            }
        }

        // barra de proporciones por resultado
        Rectangle {
            width: parent.width
            height: raiz.m(16)
            radius: height / 2
            color: Colores.bordeDivisor
            clip: true
            Row {
                anchors.fill: parent
                Repeater {
                    model: raiz.datos.totales
                    Rectangle {
                        required property var modelData
                        width: parent.width * modelData.fraccion
                        height: parent.height
                        color: raiz.colorDe(modelData.clave)
                    }
                }
            }
        }

        // ---------- por programa ----------
        Titulo { text: raiz.tx("por_programa"); topPadding: raiz.m(16) }
        Column {
            objectName: "tablaProgramas"
            width: parent.width
            readonly property var _prop: [0.40, 0.12, 0.12, 0.12, 0.12, 0.12]
            FilaTabla {
                encabezado: true
                proporciones: parent._prop
                celdas: [raiz.tx("programa"), raiz.tx("col_total"), raiz.tx("col_completados"),
                         raiz.tx("col_fallos"), raiz.tx("col_cancelados"), raiz.tx("col_sin_cierre")]
            }
            Repeater {
                model: raiz.datos.por_programa
                FilaTabla {
                    required property var modelData
                    proporciones: [0.40, 0.12, 0.12, 0.12, 0.12, 0.12]
                    celdas: [modelData.programa, modelData.total, modelData.completados,
                             modelData.fallos, modelData.cancelados, modelData.sin_cierre]
                    colores: [Colores.textoPrimario, Colores.textoPrimario, raiz.colorDe("completados"),
                              raiz.colorDe("fallos"), raiz.colorDe("cancelados"), raiz.colorDe("sin_cierre")]
                }
            }
        }

        // ---------- causas de fallo ----------
        Titulo { text: raiz.tx("causas_fallo"); topPadding: raiz.m(16) }
        Text {
            objectName: "sinFallos"
            visible: raiz.datos.causas.length === 0
            text: raiz.tx("sin_fallos")
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(24)
        }
        Column {
            objectName: "tablaCausas"
            visible: raiz.datos.causas.length > 0
            width: parent.width
            FilaTabla {
                encabezado: true
                proporciones: [0.8, 0.2]
                celdas: [raiz.tx("causa"), raiz.tx("cantidad")]
            }
            Repeater {
                model: raiz.datos.causas
                FilaTabla {
                    required property var modelData
                    proporciones: [0.8, 0.2]
                    celdas: [modelData.causa, modelData.cantidad]
                    colores: [Colores.textoPrimario, Colores.peligroTexto]
                }
            }
        }
    }
}
