import QtQuick
import Tema
import Autoclave.I18n

// T30-01 (tanda 30): elección obligatoria del operador al iniciar el ciclo sin
// sesión. Mismo estilo que ModalConfirmacion (velo, tarjeta de radio 28,
// título, divisor, dos botones de 88 de alto), con una lista táctil con
// desplazamiento de los operadores activos. Solo dibuja: la lista, el aviso
// (`mensajeClave`, clave i18n) y la visibilidad los da ComandoIniciarCiclo.
// «Iniciar ciclo» queda inactivo hasta tocar un operador; Cancelar o tocar el
// velo no inician. Los nombres largos pasan a varias líneas (sin elide, D8-5.4).
Item {
    id: raiz
    anchors.fill: parent
    z: 100

    property var operadores: []
    property string mensajeClave: ""
    property bool ocupado: false
    // id elegido (-1 = ninguno); se borra si deja de estar en la lista
    property int elegido: -1

    readonly property bool hayElegido: {
        for (let i = 0; i < (operadores ? operadores.length : 0); ++i)
            if (operadores[i].id === elegido) return true
        return false
    }

    signal aceptado(int operadorId)
    signal cancelado()

    onVisibleChanged: if (!visible) elegido = -1
    onOperadoresChanged: if (!hayElegido) elegido = -1

    function _cancelar() { raiz.cancelado() }
    function _aceptar() { if (raiz.hayElegido && !raiz.ocupado) raiz.aceptado(raiz.elegido) }

    Rectangle {
        objectName: "fondoModalOperador"
        anchors.fill: parent
        color: Colores.velo
        MouseArea { anchors.fill: parent; onClicked: raiz._cancelar() }
    }

    Rectangle {
        id: tarjeta
        objectName: "tarjetaModalOperador"
        readonly property real margen: Escala.px(48)
        width: parent.width - Escala.px(160)
        height: Math.min(Escala.px(1300), parent.height - Escala.px(192))
        anchors.centerIn: parent
        radius: Escala.px(28)
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

        Text {
            id: textoTitulo
            objectName: "tituloModalOperador"
            x: tarjeta.margen; y: Escala.px(40)
            width: tarjeta.width - 2 * tarjeta.margen
            text: I18n.t("operador_ciclo.titulo", I18n.lang)
            wrapMode: Text.WordWrap
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
        }
        Rectangle {
            id: linea
            x: tarjeta.margen; y: textoTitulo.y + textoTitulo.height + Escala.px(20)
            width: tarjeta.width - 2 * tarjeta.margen; height: Escala.px(2)
            color: Colores.bordeDivisor
        }
        Text {
            id: textoCuerpo
            objectName: "cuerpoModalOperador"
            x: tarjeta.margen
            anchors.top: linea.bottom; anchors.topMargin: Escala.px(24)
            width: tarjeta.width - 2 * tarjeta.margen
            text: I18n.t("operador_ciclo.cuerpo", I18n.lang)
            wrapMode: Text.WordWrap
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
            lineHeight: 1.15
        }
        Rectangle {
            id: nota
            objectName: "notaModalOperador"
            visible: raiz.mensajeClave !== ""
            x: tarjeta.margen
            anchors.top: textoCuerpo.bottom; anchors.topMargin: Escala.px(20)
            width: tarjeta.width - 2 * tarjeta.margen
            height: visible ? textoNota.height + Escala.px(40) : 0
            radius: Escala.px(12)
            color: Colores.advertenciaFondo
            border.width: Escala.px(2); border.color: Colores.advertencia
            Text {
                id: textoNota
                objectName: "textoNotaModalOperador"
                x: Escala.px(20); y: Escala.px(20)
                width: parent.width - Escala.px(40)
                text: raiz.mensajeClave !== "" ? I18n.t(raiz.mensajeClave, I18n.lang) : ""
                wrapMode: Text.WordWrap
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(24)
            }
        }

        ListView {
            id: lista
            objectName: "listaModalOperador"
            x: tarjeta.margen
            anchors.top: nota.visible ? nota.bottom : textoCuerpo.bottom
            anchors.topMargin: Escala.px(24)
            anchors.bottom: filaBotones.top
            anchors.bottomMargin: Escala.px(32)
            width: tarjeta.width - 2 * tarjeta.margen
            clip: true
            spacing: Escala.px(12)
            boundsBehavior: Flickable.StopAtBounds
            model: raiz.operadores
            delegate: Rectangle {
                id: fila
                required property var modelData
                required property int index
                readonly property bool marcada: modelData.id === raiz.elegido
                objectName: "filaOperador_" + index
                width: ListView.view.width
                height: Math.max(Escala.px(96), textoNombre.height + Escala.px(40))
                radius: Escala.px(16)
                color: marcada ? Colores.seleccionSutil : Colores.fondoSutil
                border.width: marcada ? Escala.px(3) : 0
                border.color: Colores.accionPrimario
                Text {
                    id: textoNombre
                    x: Escala.px(28)
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - Escala.px(56)
                    text: fila.modelData.nombre
                    wrapMode: Text.Wrap
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(30)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: !raiz.ocupado
                    onClicked: raiz.elegido = fila.modelData.id
                }
            }
        }

        TextMetrics {
            id: medidaVolver
            text: I18n.t("operador_ciclo.cancelar", I18n.lang)
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
        }
        TextMetrics {
            id: medidaAccion
            text: I18n.t("operador_ciclo.iniciar", I18n.lang)
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
        }
        Row {
            id: filaBotones
            readonly property real util: tarjeta.width - 2 * tarjeta.margen - spacing
            readonly property real base: Escala.px(340)
            readonly property real relleno: Escala.px(32)
            readonly property real anchoVolver: Math.min(Math.max(base, medidaVolver.width + relleno), util / 2)
            readonly property real anchoAccion: Math.min(Math.max(base, medidaAccion.width + relleno),
                                                         util - anchoVolver)
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(48)
            spacing: Escala.px(40)

            Rectangle {
                objectName: "botonCancelarOperador"
                width: filaBotones.anchoVolver; height: Escala.px(88)
                radius: Escala.px(6)
                color: Colores.fondoTarjeta
                border.width: Escala.px(2); border.color: Colores.bordeCampo
                Text {
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    text: medidaVolver.text
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz._cancelar() }
            }
            Rectangle {
                objectName: "botonIniciarOperador"
                readonly property bool activo: raiz.hayElegido && !raiz.ocupado
                width: filaBotones.anchoAccion; height: Escala.px(88)
                radius: Escala.px(6)
                color: Colores.accionPrimario
                opacity: activo ? 1.0 : 0.45
                Text {
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    text: medidaAccion.text
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoSobreAccion
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; enabled: parent.activo; onClicked: raiz._aceptar() }
            }
        }
    }
}
