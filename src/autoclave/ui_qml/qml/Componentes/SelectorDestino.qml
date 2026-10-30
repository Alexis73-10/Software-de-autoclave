pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Elección del destino de un envío por correo (Historial y Reportes): los
// destinos guardados (AccionesCiclos.destinos), "Todos los guardados" (si hay
// más de uno), "Otro correo…" escrito con el teclado en pantalla, y Cancelar.
// Cubre su contenedor. `elegido` lleva una dirección o varias separadas por
// coma (AccionesCiclos las separa, valida y envía).
//
// C2 (tanda 7) — causa raíz del correo a mano que "se enviaba" sin llegar: el
// panel de teclado entrega lo escrito EN VIVO (cada tecla llama al callback de
// abrirAlfanumerico) y aquí ese callback emitía `elegido`, así que se enviaba
// la primera dirección a medio escribir con forma válida ("Juan@gmail.c")
// mientras el resto de teclas se ignoraba con la acción ocupada. Ahora el
// callback solo guarda el texto; al Confirmar (u Ocultar con texto) se pasa a
// un paso de confirmación: la dirección se valida y el usuario elige enviar
// solo a ella o junto con las guardadas. Nada de esto la agrega a las
// guardadas (eso es de admin e ingeniero, OPCIONES › Conectividad).
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Rectangle {
    id: raiz

    property real escala: 1
    property var destinos: []           // [{nombre, correo}]
    property QtObject teclado: null     // PanelTeclado

    signal elegido(string correo)
    signal cancelado()

    // dirección escrita a mano y paso en curso
    property string manual: ""
    property bool escribiendo: false
    property bool confirmando: false
    readonly property string manualLimpio: manual.trim()
    // misma regla que config_correo.correo_valido (el puente vuelve a validar)
    readonly property bool manualValido: /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(manualLimpio)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    function correosGuardados() {
        const lista = []
        for (let i = 0; i < destinos.length; i++)
            lista.push(destinos[i].correo)
        return lista
    }
    function abrirManual() {
        confirmando = false
        escribiendo = true
        teclado?.abrirAlfanumerico(I18n.t("menu.titulo_otro_correo", I18n.lang), manual, 80, false,
                                   function (valor) { raiz.manual = valor })
    }
    function reiniciar() {
        escribiendo = false
        confirmando = false
        manual = ""
    }

    onVisibleChanged: if (!visible) reiniciar()

    Connections {
        target: raiz.escribiendo ? raiz.teclado : null
        function onConfirmado(valor) {
            raiz.manual = valor
            raiz.escribiendo = false
            raiz.confirmando = raiz.manualLimpio !== ""
        }
        function onCancelado() { raiz.reiniciar() }
        function onAbiertoChanged() {
            // Ocultar el teclado conserva lo escrito: también pasa a confirmar
            if (raiz.escribiendo && !raiz.teclado.abierto) {
                raiz.escribiendo = false
                raiz.confirmando = raiz.manualLimpio !== ""
            }
        }
    }

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

        // ---------- lista de destinos ----------
        Column {
            width: parent.width
            spacing: raiz.m(20)
            visible: !raiz.confirmando
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
                            wrapMode: Text.WrapAnywhere
                            text: destino.modelData.correo
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(22)
                        }
                    }
                }
            }
            Opcion {
                objectName: "destinoTodos"
                visible: raiz.destinos.length > 1
                onTocada: raiz.elegido(raiz.correosGuardados().join(","))
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: raiz.m(32)
                    text: I18n.t("correo_c2.todos_guardados", I18n.lang)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(26)
                }
            }
            Opcion {
                objectName: "destinoOtro"
                onTocada: raiz.abrirManual()
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
        }

        // ---------- confirmación de la dirección escrita a mano ----------
        Column {
            objectName: "confirmacionManual"
            width: parent.width
            spacing: raiz.m(16)
            visible: raiz.confirmando
            Text {
                width: parent.width
                text: I18n.t("correo_c2.enviar_a_manual", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(22)
            }
            Text {
                objectName: "textoCorreoManual"
                width: parent.width
                wrapMode: Text.WrapAnywhere
                text: raiz.manualLimpio
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(28)
            }
            Text {
                objectName: "avisoCorreoInvalido"
                width: parent.width
                visible: !raiz.manualValido
                wrapMode: Text.WordWrap
                text: I18n.t("correo_c2.aviso_invalida", I18n.lang)
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(22)
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("correo_c2.no_se_guarda", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
            BotonPildora {
                objectName: "botonSoloManual"
                anchors.horizontalCenter: parent.horizontalCenter
                escala: raiz.escala
                primario: true
                habilitado: raiz.manualValido
                texto: I18n.t("correo_c2.solo_manual", I18n.lang)
                onPulsado: raiz.elegido(raiz.manualLimpio)
            }
            BotonPildora {
                objectName: "botonManualYGuardados"
                anchors.horizontalCenter: parent.horizontalCenter
                visible: raiz.destinos.length > 0
                escala: raiz.escala
                habilitado: raiz.manualValido
                texto: I18n.t("correo_c2.manual_y_guardados", I18n.lang)
                onPulsado: raiz.elegido([raiz.manualLimpio].concat(raiz.correosGuardados()).join(","))
            }
            BotonPildora {
                objectName: "botonCorregirManual"
                anchors.horizontalCenter: parent.horizontalCenter
                escala: raiz.escala
                texto: I18n.t("correo_c2.corregir", I18n.lang)
                onPulsado: raiz.abrirManual()
            }
        }

        BotonPildora {
            objectName: "botonCancelarDestino"
            anchors.horizontalCenter: parent.horizontalCenter
            escala: raiz.escala
            texto: I18n.t("acciones.cancelar", I18n.lang)
            onPulsado: { raiz.teclado?.cerrar(); raiz.reiniciar(); raiz.cancelado() }
        }
    }
}
