pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// CAMBIAR CONTRASEÑA (cambio obligatorio, T-8; plan_t8_login_qml.md §3.3).
// Misma composición que Login.qml (sin diseño propio, R1-2): título, avatar,
// aviso, tres campos de contraseña con el teclado alfanumérico en pantalla,
// botón y mensaje. Reglas de Nuevo usuario (longitudes y confirmación); la
// nueva no puede ser igual a la actual. Todos los textos salen de es.json.
//
// CambioClaveController hace POST /auth/change_password fuera del hilo de la
// GUI; mientras espera, el botón queda deshabilitado. Señales hacia Main.qml:
//   claveCambiada    -> OPCIONES (la sesión ya no tiene el cambio pendiente)
//   sesionTerminada  -> Login (bloqueo, sin respuesta del equipo o 401: el
//                       aviso queda en la sesión para el login)
//   atrasPulsado / inicioPulsado -> pantalla anterior / principal; la sesión
//                       ya se descartó con logout y el siguiente login vuelve
//                       a pedir el cambio (R1-3; U2 de la tanda 2)
Item {
    id: raiz
    objectName: "cambioClave"

    property QtObject teclado: null

    signal claveCambiada()
    signal sesionTerminada()
    // U2 (tanda 2): Atrás (pantalla anterior) e Inicio (principal) abandonan
    // el cambio obligatorio: la sesión, que no llegó a completarse, se
    // descarta con logout (revisión de U2: SAF-02/TMG-03). Deshabilitados con
    // el cambio en vuelo, para no dejar un cambio aplicado sin saberlo.
    signal atrasPulsado()
    signal inicioPulsado()

    CambioClaveController {
        id: control
        objectName: "cambioClaveController"
        onClaveCambiada: { raiz.limpiar(); raiz.claveCambiada() }
        onSesionTerminada: { raiz.limpiar(); raiz.sesionTerminada() }
    }
    readonly property bool puedeEnviar: !control.ocupado && !control.sinConexion

    // Valores confirmados de los campos (nombres del cuerpo de la petición)
    property string clave_actual: ""
    property string clave_nueva: ""
    property string confirmacion: ""
    property string campoActivo: ""
    Connections {
        target: raiz.teclado
        function onAbiertoChanged() { if (!raiz.teclado.abierto) raiz.campoActivo = "" }
        // Confirmar en el último campo envía el cambio
        function onTerminado() { if (raiz.campoActivo !== "") raiz.cambiar() }
    }
    readonly property var campos: [
        { nombre: "clave_actual", etiqueta: "clave_actual" },
        { nombre: "clave_nueva",  etiqueta: "clave_nueva" },
        { nombre: "confirmacion", etiqueta: "confirmar_clave_nueva" }
    ]
    function editar(nombre) {
        if (!teclado)
            return
        const i = campos.findIndex(c => c.nombre === nombre)
        const siguiente = i + 1 < campos.length ? campos[i + 1].nombre : ""
        teclado.abrirAlfanumerico(I18n.t("sesion." + (campos[i].etiqueta), I18n.lang), raiz[nombre],
                                  control.longitudMaxima, true, texto => raiz[nombre] = texto,
                                  siguiente ? () => raiz.editar(siguiente) : null)
        campoActivo = nombre
    }
    function textoCampo(nombre) {
        return campoActivo === nombre && teclado ? teclado.textoEnEdicion : raiz[nombre]
    }
    function error(campo) {
        const e = control.errores[campo]
        return e ? I18n.t(e.clave, I18n.lang, e.valores) : ""
    }
    function limpiar() {
        clave_actual = ""; clave_nueva = ""; confirmacion = ""
    }
    function cambiar() {
        if (!puedeEnviar)
            return
        if (teclado)
            teclado.cerrar()
        control.cambiar(clave_actual, clave_nueva, confirmacion)
    }
    function _salirCon(senal) {
        if (control.ocupado)
            return
        if (teclado)
            teclado.cerrar()
        limpiar()
        control.abandonar()
        senal()
    }
    function atras() { _salirCon(atrasPulsado) }
    function inicio() { _salirCon(inicioPulsado) }

    readonly property string iconos: "../../assets/iconos/color/"

    // Campo de contraseña: recuadro con candado y ojo, error en rojo debajo
    component CampoClave: Column {
        id: campo
        property string nombre: ""
        property string marcador: ""
        property bool visibleTexto: false
        width: parent ? parent.width : 0
        spacing: Escala.px(8)

        Rectangle {
            width: parent.width; height: Escala.px(88); radius: Escala.px(6)
            border.color: raiz.error(campo.nombre) !== "" ? Colores.peligroTexto
                        : raiz.campoActivo === campo.nombre ? Colores.accionPrimario
                                                            : Colores.bordeCampo
            border.width: raiz.campoActivo === campo.nombre || raiz.error(campo.nombre) !== "" ? 2 : 1

            Image {
                id: candado
                anchors.left: parent.left
                anchors.leftMargin: Escala.px(16)
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(24); height: Escala.px(24)
                source: raiz.iconos + "candado.svg"
                sourceSize.width: width
                sourceSize.height: height
            }
            Image {
                id: ojo
                anchors.right: parent.right
                anchors.rightMargin: Escala.px(16)
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(24); height: Escala.px(24)
                source: raiz.iconos + (campo.visibleTexto ? "ojo_ocultar.svg" : "ojo_mostrar.svg")
                sourceSize.width: width
                sourceSize.height: height
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -Escala.px(16)
                    onClicked: campo.visibleTexto = !campo.visibleTexto
                }
            }
            TextField {
                objectName: "campo_" + campo.nombre
                readOnly: true   // se escribe con el teclado en pantalla
                text: raiz.textoCampo(campo.nombre)
                echoMode: campo.visibleTexto ? TextInput.Normal : TextInput.Password
                color: Colores.textoPrimario
                placeholderTextColor: Colores.textoGuia
                placeholderText: campo.marcador
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                anchors.left: candado.right
                anchors.right: ojo.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.leftMargin: Escala.px(16)
                anchors.rightMargin: Escala.px(16)
                anchors.margins: Escala.px(4)
                background: null
            }
            MouseArea {
                anchors.left: parent.left
                anchors.right: ojo.left
                anchors.rightMargin: Escala.px(16)
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                onClicked: raiz.editar(campo.nombre)
            }
        }
        Text {
            objectName: "error_" + campo.nombre
            width: parent.width
            visible: text !== ""
            text: raiz.error(campo.nombre)
            wrapMode: Text.WordWrap
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
        }
    }

    FondoApp { anchors.fill: parent }

    Column {
        anchors.fill: parent
        BarraSuperior {}   // transparente

        TarjetaContenido {
            id: tarjetaContenido
            objectName: "tarjetaCambioClave"
            width: parent.width - Escala.px(48)
            height: raiz.height - Escala.px(176) - raiz.width / 1196 * 201
            anchors.horizontalCenter: parent.horizontalCenter

            contenido: [
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Escala.px(24)
                    spacing: 0

                    Item { Layout.preferredHeight: Escala.px(60) }

                    Column {
                        Layout.fillWidth: true
                        spacing: Escala.px(28)

                        Text {
                            objectName: "tituloCambioClave"
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: I18n.t("sesion.titulo_cambio_clave", I18n.lang)
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
                            font.weight: Tipografia.pesoBold
                        }

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
                            objectName: "avisoCambioObligatorio"
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: I18n.t("sesion.aviso_cambio_obligatorio", I18n.lang)
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        }
                    }

                    Item { Layout.preferredHeight: Escala.px(60) }

                    Column {
                        Layout.preferredWidth: Escala.px(756)
                        Layout.alignment: Qt.AlignHCenter
                        spacing: Escala.px(20)

                        CampoClave { nombre: "clave_actual"; marcador: I18n.t("sesion.clave_actual", I18n.lang) }
                        CampoClave { nombre: "clave_nueva"; marcador: I18n.t("sesion.clave_nueva", I18n.lang) }
                        CampoClave {
                            nombre: "confirmacion"
                            marcador: I18n.t("sesion.confirmar_clave_nueva", I18n.lang)
                        }

                        Rectangle {
                            objectName: "botonCambiarClave"
                            width: Escala.px(625); height: Escala.px(88); radius: Escala.px(6)
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: Colores.accionPrimario
                            opacity: raiz.puedeEnviar ? 1 : 0.5

                            Text {
                                anchors.centerIn: parent
                                text: I18n.t("sesion.boton_cambiar_clave", I18n.lang)
                                color: "white"
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                                font.weight: Tipografia.pesoSemiBold
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: raiz.puedeEnviar
                                onClicked: raiz.cambiar()
                            }
                        }

                        Text {
                            objectName: "mensajeCambioClave"
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            visible: text !== ""
                            text: control.ocupado ? I18n.t("sesion.validando", I18n.lang)
                                : control.mensajeClave !== "" ? I18n.t(control.mensajeClave, I18n.lang) : ""
                            color: control.ocupado ? Colores.textoSecundario : Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
                        }
                    }

                    Item { Layout.fillHeight: true }
                    Item { Layout.preferredHeight: Escala.px(24) }
                }
            ]
        }
    }

    // Barra inferior flotante, fuera de la tarjeta (misma colocación que Opciones.qml)
    BarraInferiorMenu {
        id: barraInferior
        objectName: "barraInferiorCambioClave"
        escala: raiz.width / 1196
        // D8-5.2: mismo x y ancho que la tarjeta de contenido de encima
        x: tarjetaContenido.x
        width: tarjetaContenido.width
        y: raiz.height - 171 * escala
        version: I18n.t("app.version", I18n.lang)
        // Atrás e Inicio abandonan el cambio; inactivos mientras se envía
        atrasHabilitado: !control.ocupado
        inicioActivo: !control.ocupado
        onAtrasPulsado: raiz.atras()
        onInicioPulsado: raiz.inicio()
    }
}
