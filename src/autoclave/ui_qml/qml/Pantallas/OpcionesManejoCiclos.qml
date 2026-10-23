pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Opciones avanzadas › Manejo de ciclos (C9, tanda 9, D9-10).
// DISEÑO PROVISIONAL sin mockup: sigue el estilo de las otras secciones de
// OPCIONES (tarjetas, banda de mensaje, BotonFormulario).
//
// Crear (= duplicar un programa existente con nombre nuevo, Q2), duplicar,
// habilitar/deshabilitar y borrar los personalizados (nunca los de fábrica).
// Técnico e ingeniero, solo fuera de ciclo (`motivo` lo calcula
// permisos_opciones.motivo_manejo_ciclos). El backend es la autoridad y
// registra cada cambio en la bitácora.
Item {
    id: raiz
    objectName: "opcionesManejoCiclos"

    property QtObject teclado: null       // PanelTeclado de la ventana
    property string motivo: ""            // "" | "rol" | "ciclo" | "estado"
    readonly property bool puedeOperar: motivo === ""
    readonly property alias controlador: control
    readonly property bool cambiosPendientes: false

    // Programa base elegido en "Crear" (para el teclado)
    property int baseElegida: 0
    property int _numeroABorrar: 0
    property string _nombreABorrar: ""

    ManejoCiclosController {
        id: control
        objectName: "manejoCiclosController"
    }
    Component.onCompleted: control.cargar()
    onVisibleChanged: if (visible) control.cargar()

    function texto(clave, datos) { return clave ? I18n.t(clave, I18n.lang, datos || {}) : "" }
    function numero2(n) { return String(n).padStart(2, "0") }

    // ---- acciones (también las usan las pruebas) ----
    function abrirCrear() {
        if (!puedeOperar)
            return
        control.limpiarMensaje()
        panelCrear.visible = true
    }
    function elegirBase(numero) {
        baseElegida = numero
        panelCrear.visible = false
        if (teclado)
            teclado.abrirAlfanumerico(texto("manejo_ciclos.nombre_nuevo"), "", 40, false,
                                      (v) => control.crear(raiz.baseElegida, String(v)))
    }
    function pedirDuplicar(numero) {
        if (!puedeOperar)
            return
        control.limpiarMensaje()
        if (teclado)
            teclado.abrirAlfanumerico(texto("manejo_ciclos.nombre_nuevo"), "", 40, false,
                                      (v) => control.duplicar(numero, String(v)))
    }
    function pedirBorrar(numero, nombre) {
        if (!puedeOperar)
            return
        _numeroABorrar = numero
        _nombreABorrar = nombre
        dialogoBorrar.abrir()
    }

    // ------------------------------------------------------------ cabecera
    Column {
        id: cabecera
        width: parent.width
        spacing: Escala.px(14)

        Text {
            objectName: "explicacionManejoCiclos"
            width: parent.width
            wrapMode: Text.WordWrap
            text: raiz.texto("manejo_ciclos.explicacion")
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(21)
        }

        // Fuera de ciclo (D9-10): el ingeniero tampoco opera con un ciclo en curso
        Rectangle {
            objectName: "avisoEnCicloManejo"
            visible: raiz.motivo === "ciclo" || raiz.motivo === "estado"
            width: parent.width
            height: visible ? textoEnCiclo.implicitHeight + Escala.px(28) : 0
            radius: Escala.px(12)
            color: Colores.advertenciaFondo
            Text {
                id: textoEnCiclo
                anchors.left: parent.left; anchors.right: parent.right
                anchors.margins: Escala.px(14)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.WordWrap
                text: raiz.texto("manejo_ciclos.en_ciclo")
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(20)
            }
        }

        // Resultado de la última operación (tocar para cerrar)
        Rectangle {
            id: banda
            objectName: "bandaManejoCiclos"
            visible: control.mensaje !== ""
            width: parent.width
            height: visible ? textoBanda.implicitHeight + Escala.px(28) : 0
            radius: Escala.px(12)
            color: control.exito ? Colores.fondoSutil : Colores.peligroFondo
            Text {
                id: textoBanda
                objectName: "textoBandaManejoCiclos"
                anchors.left: parent.left; anchors.right: parent.right
                anchors.margins: Escala.px(14)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.WordWrap
                text: raiz.texto(control.mensaje, control.detalleMensaje)
                color: control.exito ? Colores.menuVerdeTexto : Colores.peligroTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
            MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
        }

        BotonFormulario {
            objectName: "botonCrearPrograma"
            width: Escala.px(420)
            primario: true
            texto: raiz.texto("manejo_ciclos.crear")
            habilitado: raiz.puedeOperar && control.bases.length > 0
            onPulsado: if (habilitado) raiz.abrirCrear()
        }
    }

    // ------------------------------------------------------------ lista
    ListView {
        id: lista
        objectName: "listaManejoCiclos"
        anchors.top: cabecera.bottom; anchors.topMargin: Escala.px(20)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        clip: true
        spacing: Escala.px(14)
        model: control.programas
        boundsBehavior: Flickable.StopAtBounds

        Text {
            visible: lista.count === 0
            anchors.centerIn: parent
            text: raiz.texto("manejo_ciclos.sin_programas")
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }

        delegate: Rectangle {
            id: tarjeta
            required property var modelData
            objectName: "programaManejo_" + modelData.numero
            width: ListView.view.width
            height: columna.implicitHeight + Escala.px(36)
            radius: Escala.px(14)
            color: Colores.fondoTarjeta
            border.width: Escala.px(2)
            border.color: Colores.bordeCampo

            Column {
                id: columna
                x: Escala.px(22); y: Escala.px(18)
                width: parent.width - Escala.px(44)
                spacing: Escala.px(10)

                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: raiz.numero2(tarjeta.modelData.numero) + " · " + tarjeta.modelData.nombre
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(26)
                }
                Text {
                    objectName: "estadoPrograma_" + tarjeta.modelData.numero
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: raiz.texto(tarjeta.modelData.personalizado ? "manejo_ciclos.personalizado"
                                                                     : "manejo_ciclos.de_fabrica")
                          + " · " + raiz.texto(tarjeta.modelData.habilitado ? "manejo_ciclos.habilitado"
                                                                           : "manejo_ciclos.deshabilitado")
                          + (tarjeta.modelData.danado ? " · " + raiz.texto("manejo_ciclos.danado") : "")
                    color: tarjeta.modelData.habilitado ? Colores.textoSecundario : Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
                Flow {
                    width: parent.width
                    spacing: Escala.px(12)
                    BotonFormulario {
                        objectName: "botonDuplicar_" + tarjeta.modelData.numero
                        width: Escala.px(250)
                        texto: raiz.texto("manejo_ciclos.duplicar")
                        habilitado: raiz.puedeOperar && tarjeta.modelData.duplicable
                        onPulsado: if (habilitado) raiz.pedirDuplicar(tarjeta.modelData.numero)
                    }
                    BotonFormulario {
                        objectName: "botonHabilitar_" + tarjeta.modelData.numero
                        width: Escala.px(250)
                        texto: raiz.texto(tarjeta.modelData.habilitado ? "manejo_ciclos.deshabilitar"
                                                                       : "manejo_ciclos.habilitar")
                        habilitado: raiz.puedeOperar
                        onPulsado: if (habilitado) control.fijarHabilitado(tarjeta.modelData.numero,
                                                                            !tarjeta.modelData.habilitado)
                    }
                    BotonFormulario {
                        objectName: "botonBorrar_" + tarjeta.modelData.numero
                        visible: tarjeta.modelData.borrable      // nunca los de fábrica
                        width: Escala.px(250)
                        texto: raiz.texto("manejo_ciclos.borrar")
                        habilitado: raiz.puedeOperar
                        onPulsado: if (habilitado) raiz.pedirBorrar(tarjeta.modelData.numero,
                                                                     tarjeta.modelData.nombre)
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ crear: programa base
    Rectangle {
        id: panelCrear
        objectName: "panelCrearPrograma"
        visible: false
        anchors.fill: parent
        color: "#99000000"   // PROVISIONAL: misma atenuación que DialogoConfirmacion
        MouseArea { anchors.fill: parent; onClicked: panelCrear.visible = false }

        Rectangle {
            anchors.centerIn: parent
            width: parent.width - Escala.px(60)
            height: Math.min(parent.height - Escala.px(60), contenidoCrear.implicitHeight + Escala.px(60))
            radius: Escala.px(20)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // el toque dentro no cierra

            Column {
                id: contenidoCrear
                x: Escala.px(30); y: Escala.px(30)
                width: parent.width - Escala.px(60)
                spacing: Escala.px(18)
                Text {
                    text: raiz.texto("manejo_ciclos.crear_titulo")
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(28)
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: raiz.texto("manejo_ciclos.crear_explicacion")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(21)
                }
                Flow {
                    objectName: "basesCrear"
                    width: parent.width
                    spacing: Escala.px(12)
                    Repeater {
                        model: control.bases
                        delegate: Rectangle {
                            id: chip
                            required property var modelData
                            objectName: "base_" + modelData.numero
                            width: textoChip.implicitWidth + Escala.px(44)
                            height: Escala.px(80)
                            radius: Escala.px(40)
                            color: Colores.fondoSutil
                            border.width: Escala.px(1)
                            border.color: Colores.bordeCampo
                            Text {
                                id: textoChip
                                anchors.centerIn: parent
                                text: raiz.numero2(chip.modelData.numero) + " · " + chip.modelData.nombre
                                color: Colores.textoPrimario
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoSemiBold
                                font.pixelSize: Escala.fuente(23)
                            }
                            MouseArea { anchors.fill: parent; onClicked: raiz.elegirBase(chip.modelData.numero) }
                        }
                    }
                }
                BotonFormulario {
                    objectName: "botonCancelarCrear"
                    width: Escala.px(300)
                    texto: I18n.t("acciones.cancelar", I18n.lang)
                    onPulsado: panelCrear.visible = false
                }
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoBorrar
        objectName: "dialogoBorrarManejo"
        mensaje: I18n.t("manejo_ciclos.borrar_pregunta", I18n.lang, { nombre: raiz._nombreABorrar })
        textoConfirmar: I18n.t("manejo_ciclos.borrar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: { cerrar(); control.borrar(raiz._numeroABorrar) }
    }
}
