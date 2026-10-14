pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Elección del destino de un envío por correo (Historial y Reportes): los
// destinos por defecto de config/correo.json (AccionesCiclos.destinos), "Otro
// correo…" escrito con el teclado en pantalla, y Cancelar. Cubre su contenedor.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Rectangle {
    id: raiz

    property real escala: 1
    property var destinos: []           // [{nombre, correo}]
    property QtObject teclado: null     // PanelTeclado

    signal elegido(string correo)
    signal cancelado()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    color: Colores.fondoTarjeta
    MouseArea { anchors.fill: parent }   // no dejar pasar el toque a lo de abajo

    component Opcion: Rectangle {
        id: opcion
        signal tocada()
        width: parent.width; height: raiz.m(112)
        radius: raiz.m(20)
        color: zonaOpcion.pressed ? Colores.fondoSutil : Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: Colores.bordeDivisor
        MouseArea { id: zonaOpcion; anchors.fill: parent; onClicked: opcion.tocada() }
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width, raiz.m(760))
        spacing: raiz.m(20)
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: I18n.t("menu.enviar_a", I18n.lang)
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(30)
        }
        Repeater {
            model: raiz.destinos
            Opcion {
                id: destino
                required property var modelData
                objectName: "destino_" + modelData.nombre
                onTocada: raiz.elegido(destino.modelData.correo)
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    x: raiz.m(32)
                    width: parent.width - 2 * x
                    spacing: raiz.m(4)
                    Text {
                        text: destino.modelData.nombre
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(26)
                    }
                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: destino.modelData.correo
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(22)
                    }
                }
            }
        }
        Opcion {
            objectName: "destinoOtro"
            onTocada: raiz.teclado?.abrirAlfanumerico(
                I18n.t("menu.titulo_otro_correo", I18n.lang), "", 80, false,
                function (valor) { if (valor !== "") raiz.elegido(valor) })
            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: raiz.m(32)
                text: I18n.t("menu.otro_correo", I18n.lang)
                color: Colores.accionPrimarioTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(26)
            }
        }
        BotonPildora {
            objectName: "botonCancelarDestino"
            anchors.horizontalCenter: parent.horizontalCenter
            escala: raiz.escala
            texto: I18n.t("acciones.cancelar", I18n.lang)
            onPulsado: { raiz.teclado?.cerrar(); raiz.cancelado() }
        }
    }
}
