import QtQuick
import Tema
import Autoclave.I18n

// Datos y gráfica de un ciclo del historial, para las ventanas flotantes del
// Menú Principal (Último ciclo y el ciclo elegido en Ciclos hoy). Solo
// presentación: recibe los textos ya formateados (bridge/resumen_sistema.py o
// bridge/ciclos_historial.py) y la curva en el formato de GraficaCiclo.qml.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: el mockup v3 no tiene estas ventanas.
Item {
    id: raiz

    property real escala: 1
    property string fecha: "—"
    property string hora: "—"
    property string programa: "—"           // número (02)
    property string programaNombre: "—"
    property string resultadoTexto: "—"
    property string resultadoDetalle: ""    // cierre tal como se guardó (p. ej. FALLO_CALENTAMIENTO)
    property color colorResultado: Colores.textoPrimario
    property string operador: "—"           // O1 (tanda 3): usuario que inició el ciclo; "—" si no hubo sesión
    // P4 (tanda 16, D-14.4): ciclo NO CONFORME (punto de referencia sin verificar):
    // franja roja de encabezado; el resultado técnico sigue en su campo
    property bool noConforme: false
    property var datosGrafica: ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
    property var fasesGrafica: []
    property bool graficaDisponible: false
    // RCB-07.2 (registro de la carga): sección de la carga del ciclo
    // (domain/registro_carga.seccion_carga; {} sin carga). «Ver carga» cambia
    // la gráfica por la lista completa; el aviso de carga no estéril se ve
    // siempre que el ciclo no terminó Completado (HAZ-RCB-02).
    property var carga: ({})
    readonly property bool tieneCarga: !!(carga && carga.titulo)
    property bool verCarga: false
    onCargaChanged: if (!tieneCarga) verCarga = false

    // El botón CERRAR de la gráfica (modo pantalla completa)
    signal cerrarPulsado()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    readonly property string _sinDato: "—"

    // Tanda horizontal: en el lienzo horizontal los datos van en una columna a
    // la izquierda y la gráfica a la derecha, a todo el alto, con la misma
    // escala que en vertical (1032 px del mockup de ancho, el de la ventana
    // flotante vertical); si el alto no alcanza para sus 794, se achica solo lo
    // necesario. `reservaSuperiorHz` (px reales) deja libre la parte de arriba
    // de la columna de datos para los botones de quien la usa (Volver, Enviar,
    // Imprimir).
    readonly property bool hz: Escala.horizontal
    property real reservaSuperiorHz: 0
    readonly property real _escalaGraficaHz: Math.min(m(1032) / 1129, height / 794)
    readonly property real _anchoDatosHz: width - grafica.width - m(32)

    component Campo: Column {
        property string rotulo: ""
        property string valor: ""
        property string detalle: ""     // texto pequeño bajo el valor (opcional)
        property color colorValor: Colores.textoPrimario
        spacing: raiz.m(6)
        Text {
            text: parent.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoMedium
            font.pixelSize: raiz.fuente(22)
        }
        Text {
            width: parent.width
            wrapMode: Text.Wrap
            text: parent.valor
            color: parent.colorValor
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(28)
        }
        Text {
            visible: text !== ""
            width: parent.width
            wrapMode: Text.Wrap
            text: parent.detalle
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(18)
        }
    }

    Rectangle {
        id: franjaNoConforme
        objectName: "franjaNoConformeDetalle"
        visible: raiz.noConforme
        y: raiz.hz ? raiz.reservaSuperiorHz : 0
        width: raiz.hz ? raiz._anchoDatosHz : parent.width
        height: visible ? textoNoConformeDetalle.implicitHeight + raiz.m(24) : 0
        radius: raiz.m(8)
        color: Colores.alarmaAlta
        Text {
            id: textoNoConformeDetalle
            x: raiz.m(16); width: parent.width - raiz.m(32)
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: I18n.t("ciclo.no_conforme_franja", I18n.lang)
            color: Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(24)
        }
    }

    // Vertical: una fila de 4 columnas. Horizontal: una columna (un dato debajo de otro).
    Grid {
        id: filaDatos
        y: (raiz.hz ? raiz.reservaSuperiorHz : 0)
           + (franjaNoConforme.visible ? franjaNoConforme.height + raiz.m(16) : 0)
        width: raiz.hz ? raiz._anchoDatosHz : parent.width
        columns: raiz.hz ? 1 : 4
        columnSpacing: raiz.m(24)
        rowSpacing: raiz.hz ? raiz.m(28) : 0
        // columnas: fecha 0.25, programa 0.37 (número y nombre), resultado 0.2, operador 0.18
        readonly property real _util: width - 3 * columnSpacing
        function ancho(f) { return raiz.hz ? width : _util * f }
        Campo {
            width: filaDatos.ancho(0.25)
            rotulo: I18n.t("menu.fecha_inicio", I18n.lang)
            valor: raiz.fecha !== raiz._sinDato ? raiz.fecha + "  " + raiz.hora : raiz._sinDato
        }
        Campo {
            width: filaDatos.ancho(0.37)
            rotulo: I18n.t("menu.programa_dato", I18n.lang)
            valor: raiz.programa + (raiz.programaNombre !== raiz._sinDato ? " · " + raiz.programaNombre : "")
            colorValor: Colores.menuNaranjaTexto
        }
        Campo {
            width: filaDatos.ancho(0.2)
            rotulo: I18n.t("menu.resultado_dato", I18n.lang)
            valor: raiz.resultadoTexto
            detalle: raiz.resultadoDetalle
            colorValor: raiz.colorResultado
        }
        Campo {
            width: filaDatos.ancho(0.18)
            rotulo: I18n.t("menu.operador", I18n.lang)
            valor: raiz.operador
        }
    }

    // RCB-07.2: resumen de la carga, aviso de no estéril y botón Ver carga / Ver gráfica
    Item {
        id: filaCarga
        objectName: "filaCargaDetalle"
        visible: raiz.tieneCarga
        x: 0
        y: filaDatos.y + filaDatos.height + raiz.m(20)
        width: raiz.hz ? raiz._anchoDatosHz : parent.width
        height: visible ? Math.max(columnaResumenCarga.implicitHeight, botonVerCarga.height) : 0
        Column {
            id: columnaResumenCarga
            width: parent.width - botonVerCarga.width - raiz.m(16)
            spacing: raiz.m(4)
            Text {
                objectName: "resumenCargaDetalle"
                width: parent.width
                wrapMode: Text.Wrap
                text: (raiz.carga.titulo || "") + " · " + (raiz.carga.resumen || "")
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(22)
            }
            Text {
                objectName: "noEsterilCargaDetalle"
                visible: !!raiz.carga.no_esteril
                width: parent.width
                wrapMode: Text.Wrap
                text: raiz.carga.no_esteril || ""
                color: Colores.alarmaAlta
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(22)
            }
        }
        BotonPildora {
            id: botonVerCarga
            objectName: "botonVerCargaDetalle"
            anchors.right: parent.right
            escala: raiz.escala
            texto: raiz.verCarga ? I18n.t("registro_carga.ver_grafica", I18n.lang)
                                 : I18n.t("registro_carga.ver_carga", I18n.lang)
            onPulsado: raiz.verCarga = !raiz.verCarga
        }
    }

    // RCB-07.2: lista completa de la carga en el lugar de la gráfica
    Item {
        id: listaCargaDetalle
        objectName: "listaCargaDetalle"
        visible: raiz.tieneCarga && raiz.verCarga
        x: grafica.x
        y: grafica.y
        width: grafica.width
        height: grafica.height
        Row {
            id: encabezadoCarga
            width: parent.width
            spacing: raiz.m(12)
            Repeater {
                model: raiz.carga.columnas || []
                Text {
                    width: (encabezadoCarga.width - 3 * encabezadoCarga.spacing)
                           * [0.1, 0.42, 0.24, 0.24][index]
                    wrapMode: Text.Wrap
                    text: modelData
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(20)
                }
            }
        }
        ListView {
            anchors.top: encabezadoCarga.bottom
            anchors.topMargin: raiz.m(8)
            anchors.bottom: notaCarga.top
            anchors.bottomMargin: raiz.m(8)
            width: parent.width
            clip: true
            model: raiz.carga.filas || []
            delegate: Item {
                required property var modelData
                width: ListView.view.width
                height: filaElemento.implicitHeight + raiz.m(12)
                Row {
                    id: filaElemento
                    width: parent.width
                    spacing: raiz.m(12)
                    Repeater {
                        model: modelData
                        Text {
                            width: (filaElemento.width - 3 * filaElemento.spacing)
                                   * [0.1, 0.42, 0.24, 0.24][index]
                            wrapMode: Text.WrapAnywhere
                            text: modelData
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(20)
                        }
                    }
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Colores.bordeDivisor
                }
            }
        }
        Text {
            id: notaCarga
            anchors.bottom: parent.bottom
            width: parent.width
            wrapMode: Text.Wrap
            text: raiz.carga.nota || ""
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(18)
        }
    }

    // Gráfica del ciclo: la misma tarjeta de la pantalla de ciclo en curso, en
    // modo pantalla completa (sin Tiempos; su CERRAR emite cerrarPulsado).
    // Diseñada a 1129 de ancho: se escala para ocupar el ancho disponible.
    GraficaCiclo {
        id: grafica
        objectName: "graficaDetalleCiclo"
        x: raiz.hz ? parent.width - width : 0
        visible: !(raiz.tieneCarga && raiz.verCarga)
        y: raiz.hz ? 0 : (filaCarga.visible ? filaCarga.y + filaCarga.height
                                             : filaDatos.y + filaDatos.height) + raiz.m(28)
        width: raiz.hz ? 1129 * raiz._escalaGraficaHz : parent.width
        height: parent.height - y
        escala: width / 1129
        modoPantallaCompleta: true
        datos: raiz.datosGrafica
        fases: raiz.fasesGrafica
        tiempoActualMin: {
            const t = raiz.datosGrafica?.t_min
            return t && t.length > 0 ? t[t.length - 1] : 0
        }
        onCerrarPulsado: raiz.cerrarPulsado()

        Text {
            objectName: "graficaNoDisponible"
            visible: !raiz.graficaDisponible
            anchors.centerIn: parent
            text: I18n.t("menu.grafica_no_disponible", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(28)
        }
    }
}
