pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// Calibracion de un sensor por dos puntos (planeacion_opciones_entradas_salidas.md
// §5.4 y §7). Se abre desde Temperatura o Presion. La lectura del equipo de cada
// punto se puede escribir a mano o capturar de la lectura en vivo (D-ES-13); la
// bitacora guarda el origen de cada una. La plausibilidad la decide el backend:
// 409 pide confirmacion, 422 no deja continuar. No incluye aun el metodo de
// ganancia y offset directos (el backend no tiene ese endpoint).
Item {
    id: raiz
    objectName: "opcionesCalibracionSensor"

    property QtObject controlador: null
    property QtObject teclado: null
    property string segmento: ""
    property string sensor: ""
    property string nombreSensor: ""
    signal volver()

    // puntos: NaN = sin capturar; origen "capturada" | "escrita"
    property real realBajo: Number.NaN
    property real lecturaBaja: Number.NaN
    property string origenBajo: "escrita"
    property real realAlto: Number.NaN
    property real lecturaAlta: Number.NaN
    property string origenAlto: "escrita"
    property string accionPendiente: ""         // "ultimo" | "defecto"

    readonly property var lista: segmento === "temperatura" ? controlador.temperatura : controlador.presion
    readonly property var lectura: {
        for (var i = 0; i < lista.length; i++)
            if (lista[i].name === sensor) return lista[i]
        return null
    }
    readonly property string unidad: segmento === "temperatura" ? "°C" : "kPa"
    readonly property bool puntosCompletos: !isNaN(realBajo) && !isNaN(lecturaBaja)
                                            && !isNaN(realAlto) && !isNaN(lecturaAlta)
    // D9-4 (tanda 9): calcular() usa la calibración vigente del controlador;
    // leer `calibracion` antes hace que el resultado se recalcule al guardarla
    readonly property var resultado: controlador.calibracion !== null && puntosCompletos
        ? controlador.calcular(lecturaBaja, realBajo, lecturaAlta, realAlto) : ({ valido: false })
    readonly property var cal: controlador.calibracion
    readonly property bool puedeAplicar: controlador.puedeCalibrar && resultado.valido === true

    function aplicar(confirmar) {
        if (controlador.aplicarPuntos(lecturaBaja, realBajo, lecturaAlta, realAlto,
                                      origenBajo, origenAlto, confirmar)) {
            realBajo = Number.NaN; lecturaBaja = Number.NaN
            realAlto = Number.NaN; lecturaAlta = Number.NaN
        } else if (controlador.requiereConfirmacion) {
            dialogoRango.abrir()
        }
    }

    function editar(titulo, valorActual, alConfirmar) {
        if (raiz.teclado)
            raiz.teclado.abrirNumerico(titulo, raiz.unidad, isNaN(valorActual) ? 0 : valorActual,
                                       -1000, 100000, 2, alConfirmar)
    }

    component Campo: Rectangle {
        id: campo
        property string rotulo: ""
        property real valor: Number.NaN
        signal tocado()
        height: Escala.px(84)
        radius: Escala.px(12)
        color: Colores.fondoSutil
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(16)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.55
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
            text: campo.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(21)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(16)
            anchors.verticalCenter: parent.verticalCenter
            text: isNaN(campo.valor) ? "—" : campo.valor.toFixed(2) + " " + raiz.unidad
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(26)
        }
        MouseArea { anchors.fill: parent; onClicked: campo.tocado() }
    }

    component BotonCal: Rectangle {
        id: boton
        property string texto: ""
        property color relleno: Colores.accionPrimario
        property bool habilitado: true
        signal pulsado()
        radius: Escala.px(12)
        color: relleno
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; enabled: boton.habilitado; onClicked: boton.pulsado() }
    }

    // Un bloque de punto (bajo o alto)
    component BloquePunto: Column {
        id: bloque
        property string titulo: ""
        property string clave: ""
        property real real: Number.NaN
        property real lectura: Number.NaN
        signal editarReal()
        signal editarLectura()
        signal capturar()
        width: parent ? parent.width : 0
        spacing: Escala.px(8)
        Text {
            text: bloque.titulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        Campo {
            objectName: "realPunto_" + bloque.clave
            width: parent.width
            rotulo: I18n.t("io.ui.cal_real", I18n.lang)
            valor: bloque.real
            onTocado: bloque.editarReal()
        }
        Row {
            width: parent.width
            spacing: Escala.px(10)
            Campo {
                objectName: "lecturaPunto_" + bloque.clave
                width: parent.width - botonCapturar.width - parent.spacing
                rotulo: I18n.t("io.ui.cal_equipo", I18n.lang)
                valor: bloque.lectura
                onTocado: bloque.editarLectura()
            }
            BotonCal {
                id: botonCapturar
                objectName: "capturar_" + bloque.clave
                width: Escala.px(190); height: Escala.px(84)
                habilitado: raiz.lectura !== null && raiz.lectura.valido
                texto: I18n.t("io.ui.cal_capturar", I18n.lang)
                onPulsado: bloque.capturar()
            }
        }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: contenido.implicitHeight + Escala.px(20)
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: contenido
            width: parent.width
            spacing: Escala.px(14)

            // encabezado con regreso al segmento de origen
            Row {
                spacing: Escala.px(14)
                Rectangle {
                    objectName: "botonVolverCalibracion"
                    width: Escala.px(72); height: Escala.px(72); radius: Escala.px(36)
                    color: Colores.fondoSutil
                    Text {
                        anchors.centerIn: parent
                        text: "‹"
                        color: Colores.textoPrimario
                        font.pixelSize: Escala.fuente(48)
                    }
                    MouseArea { anchors.fill: parent; onClicked: raiz.volver() }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("io.ui.cal_titulo", I18n.lang, { sensor: raiz.nombreSensor })
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(30)
                }
            }

            // lectura en vivo
            Rectangle {
                width: parent.width; height: Escala.px(120); radius: Escala.px(14)
                color: Colores.fondoTarjeta
                border.width: Escala.px(1); border.color: Colores.bordeDivisor
                Text {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("io.ui.cal_lectura", I18n.lang) + "\n"
                          + (raiz.lectura ? raiz.lectura.id + " · " + I18n.t("io.ui.adc", I18n.lang) + " "
                                            + (raiz.lectura.adc === null ? "—" : raiz.lectura.adc) : "")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
                Text {
                    objectName: "lecturaVivaCalibracion"
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.lectura && raiz.lectura.valido
                          ? raiz.lectura.valor.toFixed(2) + " " + raiz.unidad : "---"
                    color: raiz.lectura && raiz.lectura.valido ? Colores.textoPrimario : Colores.advertencia
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(46)
                }
            }

            // ganancia / offset: actual y por defecto, mas la ultima calibracion
            Rectangle {
                width: parent.width; height: Escala.px(150); radius: Escala.px(14)
                color: Colores.fondoSutil
                Grid {
                    anchors.fill: parent; anchors.margins: Escala.px(16)
                    columns: 3; rowSpacing: Escala.px(6)
                    Text { width: parent.width / 3; text: ""; font.pixelSize: Escala.fuente(20) }
                    Text {
                        width: parent.width / 3; text: I18n.t("io.ui.cal_actual", I18n.lang)
                        color: Colores.textoSecundario; font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(20); font.weight: Tipografia.pesoSemiBold
                    }
                    Text {
                        width: parent.width / 3; text: I18n.t("io.ui.cal_defecto", I18n.lang)
                        color: Colores.textoSecundario; font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(20); font.weight: Tipografia.pesoSemiBold
                    }
                    Text {
                        width: parent.width / 3; text: I18n.t("io.ui.ganancia", I18n.lang)
                        color: Colores.textoSecundario; font.family: Tipografia.familia; font.pixelSize: Escala.fuente(22)
                    }
                    Text {
                        objectName: "gananciaActual"
                        width: parent.width / 3
                        text: raiz.cal.gain === undefined ? "—" : Number(raiz.cal.gain).toFixed(4)
                        color: Colores.textoPrimario; font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold; font.pixelSize: Escala.fuente(24)
                    }
                    Text {
                        width: parent.width / 3; text: "1.0000"
                        color: Colores.textoPrimario; font.family: Tipografia.familia; font.pixelSize: Escala.fuente(24)
                    }
                    Text {
                        width: parent.width / 3; text: I18n.t("io.ui.offset", I18n.lang)
                        color: Colores.textoSecundario; font.family: Tipografia.familia; font.pixelSize: Escala.fuente(22)
                    }
                    Text {
                        objectName: "offsetActual"
                        width: parent.width / 3
                        text: raiz.cal.offset === undefined ? "—" : Number(raiz.cal.offset).toFixed(4)
                        color: Colores.textoPrimario; font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold; font.pixelSize: Escala.fuente(24)
                    }
                    Text {
                        width: parent.width / 3; text: "0.0000"
                        color: Colores.textoPrimario; font.family: Tipografia.familia; font.pixelSize: Escala.fuente(24)
                    }
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: raiz.cal.poly === true
                text: I18n.t("io.ui.cal_polinomio", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }

            BloquePunto {
                titulo: I18n.t("io.ui.cal_punto_bajo", I18n.lang)
                clave: "bajo"
                real: raiz.realBajo
                lectura: raiz.lecturaBaja
                onEditarReal: raiz.editar(titulo, raiz.realBajo, (v) => raiz.realBajo = Number(v))
                onEditarLectura: raiz.editar(titulo, raiz.lecturaBaja,
                                             (v) => { raiz.lecturaBaja = Number(v); raiz.origenBajo = "escrita" })
                onCapturar: { raiz.lecturaBaja = raiz.lectura.valor; raiz.origenBajo = "capturada" }
            }
            BloquePunto {
                titulo: I18n.t("io.ui.cal_punto_alto", I18n.lang)
                clave: "alto"
                real: raiz.realAlto
                lectura: raiz.lecturaAlta
                onEditarReal: raiz.editar(titulo, raiz.realAlto, (v) => raiz.realAlto = Number(v))
                onEditarLectura: raiz.editar(titulo, raiz.lecturaAlta,
                                             (v) => { raiz.lecturaAlta = Number(v); raiz.origenAlto = "escrita" })
                onCapturar: { raiz.lecturaAlta = raiz.lectura.valor; raiz.origenAlto = "capturada" }
            }

            // resultado calculado con la formula del backend
            Rectangle {
                objectName: "resultadoCalibracion"
                width: parent.width; height: Escala.px(100); radius: Escala.px(14)
                color: Colores.accionFondoTenue
                Text {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("io.ui.cal_resultado", I18n.lang)
                    color: Colores.accionPrimarioTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(22)
                }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
                    anchors.verticalCenter: parent.verticalCenter
                    text: raiz.resultado.valido === true
                          ? I18n.t("io.ui.ganancia", I18n.lang) + " " + Number(raiz.resultado.gain).toFixed(4)
                            + "   " + I18n.t("io.ui.offset", I18n.lang) + " " + Number(raiz.resultado.offset).toFixed(4)
                          : "—"
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(24)
                }
            }

            Text {
                width: parent.width
                text: I18n.t("io.ui.ultima_calibracion", I18n.lang) + ": "
                      + (raiz.cal.ultimo ? raiz.cal.ultimo.timestamp + " · " + raiz.cal.ultimo.usuario
                                         : I18n.t("io.ui.de_fabrica", I18n.lang))
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }

            Row {
                width: parent.width
                spacing: Escala.px(10)
                BotonCal {
                    objectName: "botonRestaurarUltimo"
                    width: (parent.width - parent.spacing) / 2; height: Escala.px(84)
                    relleno: Colores.menuNaranja
                    habilitado: raiz.controlador.puedeCalibrar
                    texto: I18n.t("io.ui.cal_restaurar_ultimo", I18n.lang)
                    onPulsado: { raiz.accionPendiente = "ultimo"; dialogoRestaurar.abrir() }
                }
                BotonCal {
                    objectName: "botonRestaurarDefecto"
                    width: (parent.width - parent.spacing) / 2; height: Escala.px(84)
                    relleno: Colores.menuNaranja
                    habilitado: raiz.controlador.puedeCalibrar
                    texto: I18n.t("io.ui.cal_restaurar_defecto", I18n.lang)
                    onPulsado: { raiz.accionPendiente = "defecto"; dialogoRestaurar.abrir() }
                }
            }
            BotonCal {
                objectName: "botonAplicarCalibracion"
                width: parent.width; height: Escala.px(96)
                habilitado: raiz.puedeAplicar
                texto: I18n.t("io.ui.cal_aplicar", I18n.lang)
                onPulsado: raiz.aplicar(false)
            }
            Item { width: 1; height: Escala.px(10) }
        }
    }

    DialogoConfirmacion {
        id: dialogoRango
        objectName: "dialogoCalibracionFueraDeRango"
        mensaje: I18n.t("io.ui.cal_confirmar_titulo", I18n.lang)
                 + (raiz.controlador.detalle !== "" ? "\n\n" + raiz.controlador.detalle : "")
        textoConfirmar: I18n.t("io.ui.cal_aplicar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.advertencia
        onConfirmado: { cerrar(); raiz.aplicar(true) }
    }

    DialogoConfirmacion {
        id: dialogoRestaurar
        objectName: "dialogoRestaurarCalibracion"
        mensaje: I18n.t("io.ui.cal_confirmar_restaurar", I18n.lang)
        textoConfirmar: raiz.accionPendiente === "ultimo"
                        ? I18n.t("io.ui.cal_restaurar_ultimo", I18n.lang)
                        : I18n.t("io.ui.cal_restaurar_defecto", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.advertencia
        onConfirmado: { cerrar(); raiz.controlador.restaurar(raiz.accionPendiente) }
    }
}
