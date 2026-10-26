pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Tanda 17 (PRC-01, BIT-05), DISEÑO PROVISIONAL sin mockup: desplegable táctil
// reutilizable. Un botón con la opción vigente; al tocarlo abre, sobre toda la
// ventana, una lista VERTICAL con desplazamiento (filas grandes, indicador de
// posición a la derecha), pensada para 15 o más opciones. Se cierra al elegir
// o al tocar fuera de la lista.
//
// La capa de la lista se muestra encima de la ventana (Window.contentItem)
// mientras está abierta; cerrada vuelve a colgar del propio desplegable, de
// modo que las filas existen siempre en el árbol visual (las pruebas buscan
// `prefijoFila + valor`). Sin ventana (pruebas sin Window) se abre en el sitio.
//
// opciones: [{valor, texto, aviso?}] (aviso: texto en color de advertencia,
// p. ej. "⚠" de un programa dañado)
Item {
    id: raiz

    property var opciones: []
    property var valor: undefined
    property string tituloLista: ""
    property string textoVacio: ""          // sin opciones
    property string textoSinValor: ""       // ninguna opción vigente
    property string rotulo: ""              // rótulo pequeño encima del valor (opcional)
    property string prefijoFila: "opcion_"
    property bool habilitado: true
    property bool abierto: false
    property real altoFila: Escala.px(96)
    property real altoMaximoLista: Escala.px(1100)
    signal elegido(var valor)

    implicitHeight: Escala.px(rotulo !== "" ? 96 : 88)

    function _opcionVigente() {
        for (let i = 0; i < opciones.length; i++)
            if (opciones[i].valor === valor)
                return opciones[i]
        return null
    }
    readonly property var opcionVigente: _opcionVigente()
    readonly property string textoBoton: opcionVigente
                                         ? opcionVigente.texto + (opcionVigente.aviso ? " " + opcionVigente.aviso : "")
                                         : (opciones.length === 0 ? textoVacio : textoSinValor)

    function abrir() {
        if (habilitado && opciones.length > 0)
            abierto = true
    }
    function cerrar() { abierto = false }
    function elegir(v) {
        abierto = false
        elegido(v)
    }
    onVisibleChanged: if (!visible) abierto = false

    // ---------------------------------------------------------------- botón
    Rectangle {
        id: boton
        objectName: "botonDesplegable"
        anchors.fill: parent
        radius: Escala.px(14)
        color: Colores.fondoSutil
        border.width: Escala.px(2)
        border.color: raiz.abierto ? Colores.accionPrimario : Colores.bordeCampo
        opacity: raiz.habilitado ? 1 : 0.45

        Column {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
            anchors.right: chevron.left; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            Text {
                visible: raiz.rotulo !== ""
                text: raiz.rotulo
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(19)
            }
            Text {
                objectName: "textoDesplegable"
                width: parent.width
                text: raiz.textoBoton
                elide: Text.ElideRight
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(raiz.rotulo !== "" ? 24 : 26)
            }
        }
        Image {
            id: chevron
            anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
            anchors.verticalCenter: parent.verticalCenter
            width: Escala.px(36); height: width
            source: "../../assets/iconos/color/" + (raiz.abierto ? "chevron_arriba" : "chevron_abajo") + ".svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.abrir() }
    }

    // ---------------------------------------------------------------- lista
    Item {
        id: capa
        objectName: "capaDesplegable"
        readonly property Item destino: raiz.Window.window ? raiz.Window.window.contentItem : null
        parent: raiz.abierto && destino !== null ? destino : raiz
        x: 0; y: 0
        width: parent ? parent.width : 0
        height: parent ? parent.height : 0
        visible: raiz.abierto
        z: 1000

        // tocar fuera de la lista la cierra
        Rectangle {
            anchors.fill: parent
            color: "#99000000"
            MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
        }

        Rectangle {
            id: tarjeta
            objectName: "tarjetaDesplegable"
            anchors.centerIn: parent
            width: Math.max(Escala.px(400), Math.min(capa.width - Escala.px(80), Escala.px(980)))
            height: tituloTexto.height + lista.height + Escala.px(56)
            radius: Escala.px(20)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // el toque dentro no cierra

            Text {
                id: tituloTexto
                x: Escala.px(28); y: Escala.px(20)
                width: tarjeta.width - Escala.px(56)
                height: raiz.tituloLista !== "" ? implicitHeight : 0
                visible: raiz.tituloLista !== ""
                text: raiz.tituloLista
                elide: Text.ElideRight
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(28)
            }

            ListView {
                id: lista
                objectName: "listaDesplegable"
                x: Escala.px(16)
                anchors.top: tituloTexto.bottom; anchors.topMargin: Escala.px(16)
                width: tarjeta.width - Escala.px(32)
                // alto fijo por el número de opciones (no por las filas creadas)
                height: Math.min(raiz.opciones.length * raiz.altoFila, raiz.altoMaximoLista)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: raiz.opciones
                delegate: Rectangle {
                    id: fila
                    required property var modelData
                    required property int index
                    readonly property bool vigente: modelData.valor === raiz.valor
                    objectName: raiz.prefijoFila + modelData.valor
                    width: ListView.view.width - Escala.px(18)
                    height: raiz.altoFila
                    radius: Escala.px(10)
                    color: vigente ? Colores.accionFondoTenue : "transparent"
                    Text {
                        anchors.left: parent.left; anchors.leftMargin: Escala.px(18)
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(18)
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                        text: fila.modelData.texto + (fila.modelData.aviso ? " " + fila.modelData.aviso : "")
                        color: fila.vigente ? Colores.accionPrimarioTexto : Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: fila.vigente ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(26)
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width; height: Escala.px(1)
                        color: Colores.bordeDivisor
                    }
                    MouseArea { anchors.fill: parent; onClicked: raiz.elegir(fila.modelData.valor) }
                }
                // al abrir, la opción vigente queda a la vista
                onVisibleChanged: if (visible) {
                    for (let i = 0; i < raiz.opciones.length; i++)
                        if (raiz.opciones[i].valor === raiz.valor) { positionViewAtIndex(i, ListView.Contain); break }
                }
            }
            // indicador de posición (sin QtQuick.Controls): solo si hay más de lo visible
            Rectangle {
                objectName: "indicadorDesplazamiento"
                visible: lista.contentHeight > lista.height + 1
                x: lista.x + lista.width - width
                y: lista.y + lista.visibleArea.yPosition * lista.height
                width: Escala.px(8)
                height: Math.max(Escala.px(40), lista.visibleArea.heightRatio * lista.height)
                radius: width / 2
                color: Colores.bordeCampo
            }
        }
    }
}
