pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Listado de ciclos para las ventanas de Ciclos hoy e Historial del Menú
// Principal: encabezado de columnas (Ciclo, Fecha, Hora, Programa, Resultado)
// y una fila por ciclo, la más reciente arriba. Solo presentación: las filas
// vienen ya formateadas de bridge/ciclos_historial.py (id, numero, fecha, hora,
// programa, programa_nombre, resultado, resultado_detalle, operador).
// Con `seleccionable` cada fila lleva flecha y emite cicloElegido al tocarla.
// Con `marcable` (Historial) cada fila lleva a la izquierda una casilla para
// marcarla (imprimir / enviar) y el encabezado una para marcar todas; la casilla
// emite marcaAlternada / todasAlternadas, el resto de la fila sigue abriéndola.
// Con `conOperador` (Reportes, ciclos de un tipo de fallo, D8-5.6) la última
// columna muestra el operador en vez del resultado (todos tienen el mismo).
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: el mockup v3 no tiene estas ventanas.
Item {
    id: raiz

    property real escala: 1
    property var ciclos: []
    property bool seleccionable: false
    property bool marcable: false
    property bool conOperador: false
    property var marcados: []           // ids marcados (los guarda bridge/ciclos_historial.py)
    property bool todasMarcadas: false
    // Texto y color del resultado a partir de su clave (los resuelve la pantalla)
    property var textoResultado: function (clave) { return clave }
    property var colorResultado: function (clave) { return Colores.textoPrimario }
    readonly property real altoFila: m(76)
    readonly property real altoEncabezado: m(56)

    signal cicloElegido(var fila)
    signal marcaAlternada(int id)
    signal todasAlternadas(bool marcar)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    // Proporción del ancho de cada columna (la flecha ocupa el resto si es seleccionable),
    // a la derecha de la casilla si es marcable
    readonly property real _anchoCasilla: marcable ? m(84) : 0
    readonly property real _anchoColumnas: width - _anchoCasilla
    // U10b (D10-1.4): Fecha y Hora ceden ancho que les sobraba al Programa
    // (antes 0.22 / 0.14 / 0.27), para que el nombre «NN · Programa» quepa
    // completo sin achicarse con el marcado del Historial.
    readonly property var _columnas: [0.13, 0.19, 0.12, 0.32, 0.24 - (seleccionable ? 0.05 : 0)]
    function _x(i) {
        let x = 0
        for (let k = 0; k < i; k++) x += _columnas[k]
        return _anchoCasilla + x * _anchoColumnas
    }

    // Casilla de marcar: zona táctil de todo el ancho de la columna y del alto de la fila
    component Casilla: Item {
        id: casilla
        property bool marcada: false
        signal alternada()
        width: raiz._anchoCasilla
        height: parent.height
        visible: raiz.marcable
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            x: raiz.m(8)
            width: raiz.m(44); height: width
            radius: raiz.m(8)
            color: casilla.marcada ? Colores.accionPrimario : Colores.fondoTarjeta
            border.width: casilla.marcada ? 0 : raiz.m(3)
            border.color: Colores.bordeDivisor
            Text {
                anchors.centerIn: parent
                visible: casilla.marcada
                text: "✓"
                color: "white"
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(30)
            }
        }
        MouseArea { anchors.fill: parent; onClicked: casilla.alternada() }
    }

    component Celda: Text {
        property int columna: 0
        x: raiz._x(columna)
        width: raiz._columnas[columna] * raiz._anchoColumnas - raiz.m(12)
        anchors.verticalCenter: parent.verticalCenter
        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(24)
        color: Colores.textoPrimario
    }

    Item {
        id: encabezado
        width: parent.width
        height: raiz.altoEncabezado
        Casilla {
            objectName: "casillaTodas"
            marcada: raiz.todasMarcadas
            onAlternada: raiz.todasAlternadas(!raiz.todasMarcadas)
        }
        Repeater {
            model: ["col_ciclo", "col_fecha", "col_hora", "col_programa",
                    raiz.conOperador ? "col_operador" : "col_resultado"]
            Celda {
                required property string modelData
                required property int index
                columna: index
                text: I18n.t("menu." + modelData, I18n.lang)
                color: Colores.textoSecundario
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(20)
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: raiz.m(2)
            color: Colores.bordeDivisor
        }
    }

    ListView {
        id: vista
        objectName: "vistaListaCiclos"
        anchors.top: encabezado.bottom
        anchors.bottom: parent.bottom
        width: parent.width
        clip: true
        model: raiz.ciclos
        boundsBehavior: Flickable.StopAtBounds

        delegate: Item {
            id: fila
            required property var modelData
            width: ListView.view.width
            height: raiz.altoFila

            Rectangle {
                anchors.fill: parent
                color: "#000000"
                opacity: raiz.seleccionable && zona.pressed ? 0.06 : 0.0
            }
            Celda { columna: 0; text: fila.modelData.numero; font.weight: Tipografia.pesoBold }
            Celda { columna: 1; text: fila.modelData.fecha }
            Celda { columna: 2; text: fila.modelData.hora }
            Celda {
                columna: 3
                text: fila.modelData.programa
                      + (fila.modelData.programa_nombre !== "—" ? " · " + fila.modelData.programa_nombre : "")
                color: Colores.menuNaranjaTexto
            }
            Celda {
                columna: 4
                text: raiz.conOperador ? fila.modelData.operador
                                       : raiz.textoResultado(fila.modelData.resultado)
                color: raiz.conOperador ? Colores.textoPrimario
                                        : raiz.colorResultado(fila.modelData.resultado)
                font.weight: raiz.conOperador ? Tipografia.pesoRegular : Tipografia.pesoBold
            }
            // tinta de chevron_derecha.svg = [12.8, 4.3, 35.2, 43.8]: 22 de alto
            Image {
                visible: raiz.seleccionable
                readonly property real _k: raiz.m(22) / (43.8 - 4.3)
                width: 48 * _k; height: width
                x: parent.width - raiz.m(8) - 35.2 * _k
                anchors.verticalCenter: parent.verticalCenter
                source: "../../assets/iconos/mono/chevron_derecha.svg"
                sourceSize.width: width
                sourceSize.height: height
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: raiz.m(1)
                color: Colores.bordeDivisor
            }
            MouseArea {
                id: zona
                anchors.fill: parent
                enabled: raiz.seleccionable
                onClicked: raiz.cicloElegido(fila.modelData)
            }
            Casilla {
                objectName: "casilla_" + fila.modelData.id
                marcada: raiz.marcados.indexOf(fila.modelData.id) >= 0
                onAlternada: raiz.marcaAlternada(fila.modelData.id)
            }
        }
    }
}
