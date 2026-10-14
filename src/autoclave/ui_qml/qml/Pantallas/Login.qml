import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// Pantalla 03 · Inicio de sesión.
// PENDIENTE (bloqueante real): el JSON de textos no trae "LOGIN" ni
// "Inicie sesión para continuar" — solo etiquetas de campo. Quedan como
// placeholder marcados abajo; hay que pedírselos al diseñador junto con
// el resto de textos que faltan.
// "INICIAR SESIÓN" se autentica contra el backend (POST /auth/login, T-8 de
// planeacion_backend_autenticacion.md) con LoginController, fuera del hilo de
// la GUI: mientras espera, el botón queda deshabilitado y se muestra
// "Validando…". Con sesión válida emite sesionIniciada (Main.qml abre
// OPCIONES) o, si la contraseña debe cambiarse, cambioClaveRequerido. Los
// mensajes salen de es.json por clave (sección "sesion"); con el usuario
// bloqueado, cuenta regresiva en m:ss y el botón (solo para ese usuario) se
// habilita al llegar a cero.
// La contraseña se vacía tras cada intento. Las etiquetas fijas de esta
// pantalla quedan para el plan de idiomas (planeacion_opciones.md §11).
// Los campos se escriben con el teclado en pantalla (PanelTeclado, inyectado
// por Main.qml como `teclado`): tocar un campo abre el alfanumérico, el campo
// muestra lo que se escribe, Confirmar guarda y pasa al siguiente campo (en
// el último, cierra). La contraseña va oculta también en el encabezado.
Item {
    id: raiz

    property QtObject teclado: null
    // TEC-D10: nombre de hasta 30 caracteres (USUARIO_MAX); la contraseña, hasta
    // 64 (PASSWORD_MAX de validacion_usuario.py, el mismo tope de CAMBIAR
    // CONTRASEÑA y Nuevo usuario), o no se podría entrar con una clave larga
    readonly property int longitudMaxima: 30
    readonly property int longitudMaximaClave: 64
    // Valores confirmados de los campos
    property string usuario: ""
    property string clave: ""
    // campo que se está escribiendo ("", "usuario" o "clave"): se resalta y
    // muestra lo que se lleva escrito; al cancelar vuelve a su valor
    property string campoActivo: ""
    Connections {
        target: raiz.teclado
        function onAbiertoChanged() { if (!raiz.teclado.abierto) raiz.campoActivo = "" }
    }
    // Orden de los campos: Confirmar en uno pasa al siguiente (PanelTeclado)
    readonly property var campos: [
        { nombre: "usuario", clave: "nombre_usuario", ocultar: false, maximo: longitudMaxima },
        { nombre: "clave",   clave: "contrasena",     ocultar: true,  maximo: longitudMaximaClave }
    ]
    function editar(nombre) {
        if (!teclado)
            return
        const i = campos.findIndex(c => c.nombre === nombre)
        const campo = campos[i]
        const siguiente = i + 1 < campos.length ? campos[i + 1].nombre : ""
        teclado.abrirAlfanumerico(I18n.t("formulario." + campo.clave, I18n.lang), raiz[nombre], campo.maximo,
                                  campo.ocultar, texto => raiz[nombre] = texto,
                                  siguiente ? () => raiz.editar(siguiente) : null)
        campoActivo = nombre
    }
    function textoCampo(nombre) {
        return campoActivo === nombre && teclado ? teclado.textoEnEdicion : raiz[nombre]
    }

    // Casa de la barra inferior: volver a la pantalla principal (la resuelve Main.qml)
    signal inicioPulsado()
    // Sesión validada (usuario, rol): Main.qml abre OPCIONES.
    signal sesionIniciada(string usuario, string rol)
    // Sesión válida con cambio de contraseña obligatorio: Main.qml abre CAMBIAR CONTRASEÑA
    signal cambioClaveRequerido()

    LoginController {
        id: sesion
        objectName: "loginController"
        onSesionIniciada: (usuario, rol) => raiz.sesionIniciada(usuario, rol)
        onCambioClaveRequerido: raiz.cambioClaveRequerido()
    }
    // el bloqueo es por usuario (como en el backend): otro usuario puede intentar
    readonly property bool puedeIntentar: !sesion.ocupado
        && !(sesion.bloqueado && usuario.trim().toLowerCase() === sesion.usuarioBloqueado)
    // TODO(corregir más adelante, reporte de Cristian 2026-10-07): lo escrito en el
    // teclado sin tocar Confirmar se pierde. Si se escribe la contraseña y se toca
    // directamente INICIAR SESIÓN, el login responde que falta la contraseña: el
    // texto en edición no llega a `usuario`/`clave`. Debe poder omitirse Confirmar
    // (tomar teclado.textoEnEdicion del campo activo antes de validar). Revisar
    // también tocar otro campo con el teclado abierto.
    function iniciarSesion() {
        if (!puedeIntentar)
            return
        if (teclado)
            teclado.cerrar()   // OJO: el comentario original decía que lo escrito sin Confirmar ya quedaba en el campo; no ocurre (TODO arriba)
        sesion.iniciarSesion(usuario, clave)
        clave = ""
    }

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
                            border.color: raiz.campoActivo === "usuario" ? Colores.accionPrimario
                                                                         : Colores.bordeCampo
                            border.width: raiz.campoActivo === "usuario" ? 2 : 1

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
                                id: campoUsuario
                                objectName: "campoUsuario"
                                readOnly: true   // se escribe con el teclado en pantalla
                                text: raiz.textoCampo("usuario")
                                // colores fijos: con Windows en modo oscuro, el estilo Basic
                                // toma la paleta del sistema y pinta el texto en blanco
                                color: Colores.textoPrimario
                                placeholderTextColor: Colores.textoGuia
                                font.family: Tipografia.familia
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
                            MouseArea {
                                anchors.fill: parent
                                onClicked: raiz.editar("usuario")
                            }
                        }

                        Rectangle {
                            width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                            border.color: raiz.campoActivo === "clave" ? Colores.accionPrimario
                                                                       : Colores.bordeCampo
                            border.width: raiz.campoActivo === "clave" ? 2 : 1

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
                                objectName: "campoClave"
                                readOnly: true   // se escribe con el teclado en pantalla
                                text: raiz.textoCampo("clave")
                                color: Colores.textoPrimario
                                placeholderTextColor: Colores.textoGuia
                                font.family: Tipografia.familia
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
                            // todo el campo menos el ojo, que tiene su propio toque
                            MouseArea {
                                anchors.left: parent.left
                                anchors.right: iconoOjo.left
                                anchors.rightMargin: Escala.px(16)   // no tapa el área ampliada del ojo
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                onClicked: raiz.editar("clave")
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
                            objectName: "botonIniciarSesion"
                            width: Escala.px(625); height: Escala.px(88); radius: Escala.px(6)
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: Colores.accionPrimario
                            opacity: raiz.puedeIntentar ? 1 : 0.5

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
                            MouseArea {
                                anchors.fill: parent
                                enabled: raiz.puedeIntentar
                                onClicked: raiz.iniciarSesion()
                            }
                        }

                        // "Validando…" mientras espera; si no, el mensaje de la última respuesta
                        Text {
                            objectName: "mensajeLogin"
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            visible: text !== ""
                            text: sesion.ocupado ? I18n.t("sesion.validando", I18n.lang)
                                : sesion.mensajeClave !== ""
                                    ? I18n.t(sesion.mensajeClave, I18n.lang, { tiempo: sesion.tiempoBloqueo })
                                    : ""
                            color: sesion.ocupado ? Colores.textoSecundario : Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
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
                        { icono: "casa",          activo: true, accion: function() { raiz.inicioPulsado() } }
                    ]
                }
            ]
        }
    }
}
