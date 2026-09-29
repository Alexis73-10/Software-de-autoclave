import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
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

    // Iconos del formulario: variante color/ (gris / azul del checkbox),
    // que es la que coincide con 05_PNG_REFERENCIA/pantalla_03_login.
    readonly property string iconos: "../../assets/iconos/color/"

    FondoApp { anchors.fill: parent }

    Column {
        anchors.fill: parent
        BarraSuperior {}   // transparente

        TarjetaContenido {
            width: parent.width - Escala.px(48)   // 24 a cada lado
            height: parent.height - Escala.px(176) - Escala.px(24)  // barra + margen inferior
            anchors.horizontalCenter: parent.horizontalCenter

            contenido: [
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Escala.px(24)   // relleno_tarjeta
                    spacing: 0

                    Item { Layout.preferredHeight: Escala.px(60) }  // margen fijo antes del título

                    Column {
                        Layout.fillWidth: true
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
                            width: Escala.px(336); height: Escala.px(336); radius: width / 2
                            color: "#E6E6E6"

                            Image {
                                anchors.centerIn: parent
                                width: parent.width * 0.5
                                height: width
                                source: "../../assets/iconos/color/usuario.svg"
                                sourceSize.width: width
                                sourceSize.height: height
                            }
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "Inicie sesión para continuar"  // PLACEHOLDER
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        }
                    }

                    Item { Layout.preferredHeight: Escala.px(60) }  // margen fijo antes del formulario

                    // Formulario angosto y centrado (756 de diseño, como la referencia).
                    // En un Layout el ancho se fija con preferredWidth: "width" lo pisa el layout.
                    Column {
                        Layout.preferredWidth: Escala.px(756)
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Escala.px(28)

                        Rectangle {
                            width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                            border.color: Colores.bordeCampo; border.width: 1

                            Image {
                                id: iconoUsuario
                                anchors.left: parent.left
                                anchors.leftMargin: Escala.px(16)
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(24); height: Escala.px(24)
                                source: raiz.iconos + "usuario.svg"
                                sourceSize.width: width
                                sourceSize.height: height
                            }

                            TextField {
                                anchors.left: iconoUsuario.right
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: Escala.px(16)
                                anchors.margins: Escala.px(4)
                                placeholderText: "Nombre Usuario"
                                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                                background: null
                            }
                        }

                        Rectangle {
                            width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                            border.color: Colores.bordeCampo; border.width: 1

                            Image {
                                id: iconoCandado
                                anchors.left: parent.left
                                anchors.leftMargin: Escala.px(16)
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(24); height: Escala.px(24)
                                source: raiz.iconos + "candado.svg"
                                sourceSize.width: width
                                sourceSize.height: height
                            }

                            // Alterna ver/ocultar la contraseña. Muestra "ojo_mostrar"
                            // mientras está oculta (la acción disponible es mostrarla).
                            Image {
                                id: iconoOjo
                                anchors.right: parent.right
                                anchors.rightMargin: Escala.px(16)
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(24); height: Escala.px(24)
                                source: raiz.iconos + (campoClave.echoMode === TextInput.Password
                                                       ? "ojo_mostrar.svg" : "ojo_ocultar.svg")
                                sourceSize.width: width
                                sourceSize.height: height

                                MouseArea {
                                    anchors.fill: parent
                                    anchors.margins: -Escala.px(16)   // área táctil más grande que el icono
                                    onClicked: campoClave.echoMode =
                                        campoClave.echoMode === TextInput.Password
                                            ? TextInput.Normal : TextInput.Password
                                }
                            }

                            TextField {
                                id: campoClave
                                anchors.left: iconoCandado.right
                                anchors.right: iconoOjo.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: Escala.px(16)
                                anchors.rightMargin: Escala.px(16)
                                anchors.margins: Escala.px(4)
                                placeholderText: "Contraseña"
                                echoMode: TextInput.Password
                                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                                background: null
                            }
                        }

                        // PENDIENTE: el diseñador no entregó ícono de casilla vacía;
                        // desmarcada se ve solo el Rectangle con borde.
                        Row {
                            id: recordarUsuario
                            // Más angosto que los campos (625 vs 756), centrado.
                            // Dentro de un Column (no Layout): width + anchors.
                            width: Escala.px(625)
                            anchors.horizontalCenter: parent.horizontalCenter
                            property bool marcado: false
                            spacing: Escala.px(16)

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(24); height: Escala.px(24)
                                radius: Escala.px(4)
                                border.color: Colores.bordeCampo; border.width: 1

                                Image {
                                    anchors.fill: parent
                                    visible: recordarUsuario.marcado
                                    source: raiz.iconos + "casilla_marcada.svg"
                                    sourceSize.width: width
                                    sourceSize.height: height
                                }
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Recordar Usuario"
                                color: Colores.textoPrimario
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                                font.weight: Tipografia.pesoMedium
                            }

                            TapHandler { onTapped: recordarUsuario.marcado = !recordarUsuario.marcado }
                        }

                        Rectangle {
                            width: Escala.px(625); height: Escala.px(88); radius: Escala.px(6)
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: Colores.accionPrimario

                            Row {
                                anchors.centerIn: parent
                                spacing: Escala.px(16)

                                // No hay variante blanca del ícono: se aclara el
                                // mono/ (casi negro) a blanco con brillo máximo.
                                Image {
                                    id: iconoBoton
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Escala.px(32); height: Escala.px(32)
                                    source: "../../assets/iconos/mono/usuario.svg"
                                    sourceSize.width: width
                                    sourceSize.height: height
                                    visible: false
                                }
                                MultiEffect {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: iconoBoton.width; height: iconoBoton.height
                                    source: iconoBoton
                                    brightness: 1.0
                                }

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "INICIAR SESIÓN"
                                    color: "white"
                                    font.family: Tipografia.familia
                                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                                    font.weight: Tipografia.pesoSemiBold
                                }
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

                    Item { Layout.fillHeight: true }   // espaciador elástico: el hueco queda abajo

                    Item { Layout.preferredHeight: Escala.px(24) }  // aire antes del divisor
                }
            ]

            pie: [
                BarraInferior {
                    anchors.fill: parent
                    version: "V: 1.0"
                    botones: [
                        { icono: "salir_sesion",  activo: false },
                        { icono: "historial",     activo: false },
                        { icono: "mantenimiento", activo: false },
                        { icono: "casa",          activo: true  }
                    ]
                }
            ]
        }
    }
}
