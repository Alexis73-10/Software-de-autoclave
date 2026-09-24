import QtQuick
import QtQuick.Controls.Basic
import Tema
import "../Componentes"

// Pantalla 03 · Inicio de sesión.
// PENDIENTE (bloqueante real): el JSON de textos no trae "LOGIN" ni
// "Inicie sesión para continuar" — solo etiquetas de campo. Quedan como
// placeholder marcados abajo; hay que pedírselos al diseñador junto con
// el resto de textos que faltan.
// PENDIENTE: la autenticación contra el backend no está conectada — este es
// el cascarón visual. Falta resolver el canal de comunicación (HTTP vs.
// acceso directo) antes de cablear el botón "INICIAR SESIÓN".
Item {
    id: raiz

    Rectangle { anchors.fill: parent; color: Colores.fondoBarraSuperior }

    Column {
        anchors.fill: parent
        BarraSuperior {}

        Rectangle {
            width: parent.width
            height: parent.height - Escala.px(176) - Escala.px(168)
            color: "white"

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: Escala.px(60)
                width: Escala.px(700)
                spacing: Escala.px(28)

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "LOGIN"
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
                    font.weight: Tipografia.pesoBold
                }

                // Avatar placeholder — reemplazar por foto de usuario cuando exista
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Escala.px(160); height: Escala.px(160); radius: width / 2
                    color: "#E6E6E6"
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Inicie sesión para continuar"  // PLACEHOLDER
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    border.color: Colores.bordeCampo; border.width: 1
                    TextField {
                        anchors.fill: parent
                        anchors.margins: Escala.px(4)
                        placeholderText: "Nombre Usuario"
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        background: null
                    }
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    border.color: Colores.bordeCampo; border.width: 1
                    TextField {
                        id: campoClave
                        anchors.fill: parent
                        anchors.margins: Escala.px(4)
                        placeholderText: "Contraseña"
                        echoMode: TextInput.Password
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        background: null
                    }
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    color: Colores.accionPrimario
                    Text {
                        anchors.centerIn: parent
                        text: "INICIAR SESIÓN"
                        color: "white"
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                        font.weight: Tipografia.pesoSemiBold
                    }
                    // TODO: conectar con backend cuando se resuelva el canal
                    MouseArea { anchors.fill: parent }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "¿Olvidó su contraseña?"
                    color: Colores.accionPrimarioTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
            }
        }

        BarraInferior {
            botones: [
                { icono: "salir_sesion",  activo: false },
                { icono: "historial",     activo: false },
                { icono: "mantenimiento", activo: false },
                { icono: "casa",          activo: true  }
            ]
        }
    }
}
