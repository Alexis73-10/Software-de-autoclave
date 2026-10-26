pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Tanda 17 (BIT-05), DISEÑO PROVISIONAL sin mockup: calendario táctil
// reutilizable para elegir una fecha sin teclado. Ventana emergente sobre toda
// la ventana de la aplicación con el mes y flechas ‹ › para cambiarlo, la
// cuadrícula de días (semana de lunes a domingo; `calendario.dias_cortos`) y
// los botones Hoy, Sin fecha (opcional) y Cancelar. Tocar un día lo elige y
// cierra. Fechas en texto AAAA-MM-DD (sin zona horaria: solo el día civil).
//
// Uso: calendario.abrir(fechaInicial, titulo); señal elegida(fecha) ("" =
// Sin fecha). Cancelar o tocar fuera cierra sin elegir.
Item {
    id: raiz

    property string titulo: ""
    property bool permiteSinFecha: true
    // Hoy (AAAA-MM-DD); quien lo usa puede pasar el del controlador
    property string hoy: _iso(new Date())
    property string seleccion: ""
    property bool abierta: false
    property int anio: 2026
    property int mes: 0                       // 0..11
    signal elegida(string fecha)
    signal cancelada()

    anchors.fill: parent
    z: 300

    function _dos(n) { return String(n).padStart(2, "0") }
    function _iso(d) { return d.getFullYear() + "-" + _dos(d.getMonth() + 1) + "-" + _dos(d.getDate()) }
    function _partes(fecha) {
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(fecha || ""))
        return m ? [Number(m[1]), Number(m[2]) - 1, Number(m[3])] : null
    }
    function abrir(fechaInicial, tituloVentana) {
        if (tituloVentana !== undefined)
            titulo = tituloVentana
        seleccion = _partes(fechaInicial) ? String(fechaInicial) : ""
        const p = _partes(seleccion) || _partes(hoy) || [2026, 0, 1]
        anio = p[0]
        mes = p[1]
        abierta = true
    }
    function cerrar() { abierta = false }
    // la pantalla que lo contiene se oculta: se cierra sin elegir
    onVisibleChanged: if (!visible) cancelar()
    // Tanda 17 (R4, V17-s4-02): se cierra cuando la seguridad pasa a urgente
    // (Main.qml irAPanelSeguridad() -> Capas.cerrarTodas())
    Connections {
        target: Capas
        function onCierreSolicitado() { raiz.cancelar() }
    }
    function cancelar() {
        if (!abierta) return
        abierta = false
        cancelada()
    }
    function elegir(fecha) {
        abierta = false
        elegida(fecha)
    }
    function elegirDia(dia) { elegir(anio + "-" + _dos(mes + 1) + "-" + _dos(dia)) }
    function mesAnterior() {
        if (mes === 0) { mes = 11; anio -= 1 } else mes -= 1
    }
    function mesSiguiente() {
        if (mes === 11) { mes = 0; anio += 1 } else mes += 1
    }

    // días del mes visible en 6 semanas (0 = celda vacía), semana de lunes
    readonly property var celdas: {
        const primero = new Date(anio, mes, 1)
        const desplazamiento = (primero.getDay() + 6) % 7      // lunes = 0
        const dias = new Date(anio, mes + 1, 0).getDate()
        const out = []
        for (let i = 0; i < 42; i++) {
            const d = i - desplazamiento + 1
            out.push(d >= 1 && d <= dias ? d : 0)
        }
        return out
    }
    readonly property string nombreMes: {
        const meses = I18n.valor("fecha.meses_largos", I18n.lang)
        return (meses && meses.length === 12 ? meses[mes] : String(mes + 1)) + " " + anio
    }
    readonly property var diasCortos: {
        const d = I18n.valor("calendario.dias_cortos", I18n.lang)
        return d && d.length === 7 ? d : ["1", "2", "3", "4", "5", "6", "7"]
    }

    Item {
        id: capa
        objectName: "capaCalendario"
        readonly property Item destino: raiz.Window.window ? raiz.Window.window.contentItem : null
        parent: raiz.abierta && destino !== null ? destino : raiz
        x: 0; y: 0
        width: parent ? parent.width : 0
        height: parent ? parent.height : 0
        visible: raiz.abierta
        z: 1000

        Rectangle {
            anchors.fill: parent
            color: "#99000000"
            MouseArea { anchors.fill: parent; onClicked: raiz.cancelar() }
        }

        Rectangle {
            id: tarjeta
            objectName: "tarjetaCalendario"
            anchors.centerIn: parent
            width: Math.max(Escala.px(560), Math.min(capa.width - Escala.px(80), Escala.px(860)))
            height: columna.implicitHeight + Escala.px(64)
            radius: Escala.px(24)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // el toque dentro no cierra

            Column {
                id: columna
                x: Escala.px(32); y: Escala.px(32)
                width: tarjeta.width - Escala.px(64)
                spacing: Escala.px(16)

                Text {
                    width: parent.width
                    visible: raiz.titulo !== ""
                    text: raiz.titulo
                    wrapMode: Text.WordWrap
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(24)
                }

                // mes con flechas
                Item {
                    width: parent.width
                    height: Escala.px(96)
                    Flecha {
                        objectName: "mesAnterior"
                        anchors.left: parent.left
                        icono: "chevron_izquierda"
                        Accessible.name: I18n.t("calendario.mes_anterior", I18n.lang)
                        onPulsada: raiz.mesAnterior()
                    }
                    Text {
                        objectName: "nombreMesCalendario"
                        anchors.centerIn: parent
                        text: raiz.nombreMes
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: Escala.fuente(30)
                    }
                    Flecha {
                        objectName: "mesSiguiente"
                        anchors.right: parent.right
                        icono: "chevron_derecha"
                        Accessible.name: I18n.t("calendario.mes_siguiente", I18n.lang)
                        onPulsada: raiz.mesSiguiente()
                    }
                }

                // cabecera de días
                Row {
                    Repeater {
                        model: raiz.diasCortos
                        delegate: Text {
                            required property var modelData
                            width: columna.width / 7
                            horizontalAlignment: Text.AlignHCenter
                            text: String(modelData)
                            color: Colores.textoGuia
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(22)
                        }
                    }
                }

                Grid {
                    columns: 7
                    Repeater {
                        model: raiz.celdas
                        delegate: Item {
                            id: celda
                            required property var modelData
                            readonly property int dia: Number(modelData)
                            readonly property string fecha: dia > 0
                                ? raiz.anio + "-" + raiz._dos(raiz.mes + 1) + "-" + raiz._dos(dia) : ""
                            objectName: dia > 0 ? "dia_" + dia : ""
                            width: columna.width / 7
                            height: Escala.px(84)
                            Rectangle {
                                visible: celda.dia > 0
                                anchors.centerIn: parent
                                width: Math.min(parent.width, parent.height) - Escala.px(8)
                                height: width
                                radius: width / 2
                                color: celda.fecha === raiz.seleccion ? Colores.accionPrimario : "transparent"
                                border.width: celda.fecha === raiz.hoy ? Escala.px(2) : 0
                                border.color: Colores.accionPrimario
                                Text {
                                    anchors.centerIn: parent
                                    text: celda.dia
                                    color: celda.fecha === raiz.seleccion ? "white" : Colores.textoPrimario
                                    font.family: Tipografia.familia
                                    font.weight: Tipografia.pesoSemiBold
                                    font.pixelSize: Escala.fuente(26)
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: celda.dia > 0
                                onClicked: raiz.elegirDia(celda.dia)
                            }
                        }
                    }
                }

                Flow {
                    width: parent.width
                    spacing: Escala.px(16)
                    BotonCal {
                        objectName: "botonHoyCalendario"
                        texto: I18n.t("calendario.hoy", I18n.lang)
                        primario: true
                        onPulsado: raiz.elegir(raiz.hoy)
                    }
                    BotonCal {
                        objectName: "botonSinFechaCalendario"
                        visible: raiz.permiteSinFecha
                        texto: I18n.t("calendario.sin_fecha", I18n.lang)
                        onPulsado: raiz.elegir("")
                    }
                    BotonCal {
                        objectName: "botonCancelarCalendario"
                        texto: I18n.t("calendario.cancelar", I18n.lang)
                        onPulsado: raiz.cancelar()
                    }
                }
            }
        }
    }

    component Flecha: Rectangle {
        id: f
        property string icono: ""
        signal pulsada()
        width: Escala.px(96); height: Escala.px(96)
        radius: width / 2
        color: Colores.fondoSutil
        Image {
            anchors.centerIn: parent
            width: Escala.px(44); height: width
            source: "../../assets/iconos/color/" + f.icono + ".svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: f.pulsada() }
    }

    component BotonCal: Rectangle {
        id: b
        property string texto: ""
        property bool primario: false
        signal pulsado()
        width: Math.max(Escala.px(200), textoB.implicitWidth + Escala.px(48))
        height: Escala.px(84)
        radius: Escala.px(8)
        color: primario ? Colores.accionPrimario : Colores.fondoSutil
        border.width: primario ? 0 : Escala.px(2)
        border.color: Colores.bordeCampo
        Text {
            id: textoB
            anchors.centerIn: parent
            text: b.texto
            color: b.primario ? "white" : Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(24)
        }
        MouseArea { anchors.fill: parent; onClicked: b.pulsado() }
    }
}
