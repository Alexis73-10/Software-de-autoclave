pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n
import Autoclave.Unidades

// OPCIONES › Mantenimiento › Calibración de presión atmosférica (O2f, tanda 6;
// mockup 10 de docs/mockups/tanda6/APROBADO.md). Lista de condiciones con ✓,
// barra de progreso (mm:ss de 02:00 y número de muestras), promedio,
// dispersión y valor anterior con fecha, recuadro de criterios y aviso de
// cancelación. Durante la medición solo Cancelar está activo; Atrás, Inicio y
// el cajón los bloquea Opciones.qml con `bloqueada`.
// La medición y la validación las hace el backend; aquí solo se muestran.
// La presión de calibración va en kPa absolutos (dato de calibración, regla 5);
// la temperatura de la condición, por Unidades.
Item {
    id: raiz
    objectName: "opcionesCalibracionAtm"

    property bool edicionPermitida: false
    readonly property bool bloqueada: control.midiendo || control.porConfirmar

    CalibracionAtmController {
        id: control
        objectName: "calibracionAtmController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.activar()
    Component.onDestruction: control.desactivar()

    function textoCondicion(c) {
        if (c === "temp_baja")
            return I18n.t("calibracion_atm.cond_temp_baja", I18n.lang,
                          { temp: Unidades.temp(control.criterios.temp_max, Unidades.version) })
        return I18n.t("calibracion_atm.cond_" + c, I18n.lang)
    }

    component Dato: Item {
        id: dato
        property string rotulo: ""
        property string valor: ""
        width: parent ? parent.width : 0
        height: Escala.px(80)
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.5
            elide: Text.ElideRight
            text: dato.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.48
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideLeft
            text: dato.valor
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(28)
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
    }

    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool habilitado: true
        property color fondo: Colores.accionPrimario
        signal pulsado()
        height: Escala.px(96)
        radius: Escala.px(12)
        color: fondo
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            width: parent.width - Escala.px(24)
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(28)
        }
        MouseArea { anchors.fill: parent; enabled: boton.habilitado; onClicked: boton.pulsado() }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: columna.height + Escala.px(40)
        clip: true
        interactive: contentHeight > height

        Column {
            id: columna
            width: parent.width
            spacing: Escala.px(10)

            Rectangle {
                objectName: "mensajeCalibracionAtm"
                visible: control.mensaje !== ""
                width: parent.width
                height: visible ? textoMensaje.implicitHeight + Escala.px(32) : 0
                radius: Escala.px(12)
                color: control.mensaje === "calibracion_atm.impreso" ? Colores.accionFondoTenue
                                                                     : Colores.peligroFondo
                Text {
                    id: textoMensaje
                    anchors.fill: parent; anchors.margins: Escala.px(16)
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                    color: control.mensaje === "calibracion_atm.impreso" ? Colores.accionPrimarioTexto
                                                                         : Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
            }

            Text {
                width: parent.width
                text: I18n.t("calibracion_atm.titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(32)
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("calibracion_atm.guia", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }

            // ── condiciones ───────────────────────────────────────────
            Repeater {
                model: control.listaCondiciones
                delegate: Item {
                    id: fila
                    required property string modelData
                    readonly property bool cumple: control.condiciones[modelData] === true
                    objectName: "condicion_" + modelData
                    width: columna.width
                    height: Escala.px(64)
                    Rectangle {
                        id: marca
                        anchors.verticalCenter: parent.verticalCenter
                        width: Escala.px(44); height: width; radius: width / 2
                        color: fila.cumple ? Colores.menuVerde : Colores.peligroFondo
                        // ✓ dibujado (la fuente no tiene el glifo y IconoColor no
                        // se dibuja offscreen)
                        Item {
                            visible: fila.cumple
                            anchors.centerIn: parent
                            width: Escala.px(24); height: width
                            Rectangle {
                                x: Escala.px(1); y: Escala.px(12)
                                width: Escala.px(11); height: Escala.px(4); radius: height / 2
                                rotation: 45; color: "white"
                            }
                            Rectangle {
                                x: Escala.px(6); y: Escala.px(9)
                                width: Escala.px(19); height: Escala.px(4); radius: height / 2
                                rotation: -50; color: "white"
                            }
                        }
                        Text {
                            visible: !fila.cumple
                            anchors.centerIn: parent
                            text: "!"
                            color: Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: Escala.fuente(28)
                        }
                    }
                    Text {
                        anchors.left: marca.right; anchors.leftMargin: Escala.px(16)
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: raiz.textoCondicion(fila.modelData)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(26)
                    }
                }
            }

            // ── progreso ──────────────────────────────────────────────
            Item {
                width: parent.width
                height: Escala.px(56)
                Text {
                    objectName: "tiempoCalibracionAtm"
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    text: control.tiempoTexto
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(30)
                }
                Text {
                    objectName: "muestrasCalibracionAtm"
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    text: I18n.t("calibracion_atm.muestras", I18n.lang,
                                 { n: control.muestras, total: control.muestrasTotal })
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(24)
                }
            }
            Rectangle {
                objectName: "barraProgresoCalibracionAtm"
                width: parent.width
                height: Escala.px(24)
                radius: height / 2
                color: Colores.fondoSutil
                Rectangle {
                    width: parent.width * Math.min(1, control.muestras / Math.max(1, control.muestrasTotal))
                    height: parent.height
                    radius: parent.radius
                    color: Colores.accionPrimario
                }
            }

            Dato { rotulo: I18n.t("calibracion_atm.promedio", I18n.lang); valor: control.promedio }
            Dato { rotulo: I18n.t("calibracion_atm.dispersion", I18n.lang); valor: control.dispersion }
            Dato {
                objectName: "valorAnteriorCalibracionAtm"
                rotulo: I18n.t("calibracion_atm.anterior", I18n.lang)
                valor: control.referenciaFecha !== ""
                       ? control.referencia + " · " + control.referenciaFecha
                       : control.referencia
            }

            // ── resultado ─────────────────────────────────────────────
            Text {
                objectName: "resultadoCalibracionAtm"
                visible: control.estado !== "" && control.estado !== "inactiva"
                         && control.estado !== "midiendo"
                width: parent.width
                wrapMode: Text.WordWrap
                text: control.estado === "ok" ? I18n.t("calibracion_atm.res_ok", I18n.lang)
                      : control.estado === "por_confirmar" ? I18n.t("calibracion_atm.res_por_confirmar", I18n.lang,
                                                                    { dif: control.criterios.diferencia_confirmar })
                      : control.motivo !== "" && I18n.existe("calibracion_atm.motivo_" + control.motivo, I18n.lang)
                        ? I18n.t("calibracion_atm.res_" + control.estado, I18n.lang,
                                 { motivo: I18n.t("calibracion_atm.motivo_" + control.motivo, I18n.lang) })
                      : ""
                color: control.estado === "ok" ? Colores.menuVerdeTexto
                       : control.estado === "por_confirmar" ? Colores.advertenciaTexto : Colores.peligroTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(24)
            }

            // ── criterios ─────────────────────────────────────────────
            Rectangle {
                objectName: "criteriosCalibracionAtm"
                width: parent.width
                height: textoCriterios.implicitHeight + Escala.px(32)
                radius: Escala.px(12)
                color: Colores.advertenciaFondo
                Text {
                    id: textoCriterios
                    anchors.fill: parent; anchors.margins: Escala.px(16)
                    wrapMode: Text.WordWrap
                    text: I18n.t("calibracion_atm.criterios", I18n.lang, {
                                     min: control.criterios.promedio_min, max: control.criterios.promedio_max,
                                     disp: control.criterios.dispersion_max,
                                     dif: control.criterios.diferencia_confirmar })
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(21)
                }
            }

            // ── acciones ──────────────────────────────────────────────
            Row {
                width: parent.width
                spacing: Escala.px(16)
                visible: !control.porConfirmar
                Boton {
                    objectName: "botonIniciarCalibracionAtm"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("calibracion_atm.iniciar", I18n.lang)
                    habilitado: raiz.edicionPermitida && !control.midiendo && control.condicionesCumplidas
                    onPulsado: control.iniciar()
                }
                Boton {
                    objectName: "botonCancelarCalibracionAtm"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("acciones.cancelar", I18n.lang)
                    fondo: Colores.peligroTexto
                    habilitado: control.midiendo
                    onPulsado: control.cancelar()
                }
            }
            Row {
                width: parent.width
                spacing: Escala.px(16)
                visible: control.porConfirmar
                Boton {
                    objectName: "botonConfirmarCalibracionAtm"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("calibracion_atm.confirmar", I18n.lang)
                    onPulsado: dialogoConfirmar.abrir()
                }
                Boton {
                    objectName: "botonDescartarCalibracionAtm"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("calibracion_atm.descartar", I18n.lang)
                    fondo: Colores.textoSecundario
                    onPulsado: control.descartar()
                }
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoConfirmar
        objectName: "dialogoConfirmarCalibracionAtm"
        mensaje: I18n.t("calibracion_atm.confirmar_pregunta", I18n.lang,
                        { nuevo: control.promedio, anterior: control.referencia })
        textoConfirmar: I18n.t("calibracion_atm.confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { cerrar(); control.confirmar() }
    }
}
