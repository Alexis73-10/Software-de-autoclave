pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// Reportes (planeacion_dashboard_reportes.md §5/§7, REP-01..REP-14): pantalla
// completa de SOLO LECTURA que reemplaza a la ventana flotante del Menú
// Principal. Barra superior (EncabezadoMenu: logo, reloj y campana) con el
// título, barra inferior fija (Inicio a la izquierda, Salir a la derecha) y,
// entre ambas, un Flickable vertical con las secciones en este orden: Periodo,
// Indicadores, Resultado, Ciclos por día, Por programa, Calendario de
// ejecución, Causas de fallo, Mantenimiento / Alarmas / Por operador (tres
// columnas) y Acciones. Todas son visibles sin sesión (DR-D09); la sesión solo
// decide si se puede escribir un correo a mano (REP-13, SelectorDestino).
//
// Solo dibujo: los datos y textos vienen de `reporteDashboard`
// (bridge/reporte_dashboard.py + domain/reporte_dashboard.py). Las acciones
// (imprimir, enviar) son las de `acciones` (AccionesCiclos). Nada escribe en la
// base ni actúa sobre el equipo.
//
// Geometría: px del marco del diseñador (1196 de ancho) escalados con m() (D-18).
Item {
    id: raiz
    objectName: "pantallaReportes"

    property QtObject puente: null              // UiBridge: alarmas de la campana
    property QtObject reporteDashboard: null    // ReporteDashboard
    property QtObject acciones: null            // AccionesCiclos: imprimir / enviar
    property QtObject historial: null           // CiclosHistorial: curva del ciclo abierto
    property QtObject teclado: null             // PanelTeclado: correo escrito a mano
    property QtObject comandosSistema: null
    property bool sesionActiva: false           // REP-13

    signal inicioPulsado()      // vuelve al Menú Principal
    signal salirPulsado()       // sale a la pantalla principal del equipo
    signal campanaPulsada()

    readonly property real anchoMockup: 1196
    readonly property real escala: width / anchoMockup
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    readonly property string sinDato: "—"
    function dato(v) { return (v === undefined || v === null || v === "") ? sinDato : v }

    // Umbral de confirmación del consolidado (REP-12) y tamaño estimado por ciclo
    // (DECISIÓN SIN CONFIRMAR: a medir en el banco con el PDF real)
    property int umbralConsolidado: 300
    readonly property real mbPorCiclo: 0.1

    readonly property var rd: raiz.reporteDashboard
    readonly property var datos: raiz.rd ? raiz.rd.datos : ({})
    readonly property var encabezado: (raiz.datos && raiz.datos.encabezado) ? raiz.datos.encabezado : ({})
    readonly property bool hayError: raiz.rd ? raiz.rd.hayError : false
    readonly property bool cargando: raiz.rd ? raiz.rd.cargando : false
    readonly property bool valido: raiz.datos ? raiz.datos.valido === true : false
    readonly property int totalCiclos: {
        const ind = raiz.datos && raiz.datos.indicadores ? raiz.datos.indicadores : []
        return ind.length > 0 ? parseInt(ind[0].valor) || 0 : 0
    }
    readonly property bool ocupado: raiz.acciones ? raiz.acciones.ocupado : false
    readonly property bool correoListo: raiz.acciones ? raiz.acciones.correoConfigurado : false
    readonly property bool hayDestinoCorreo: sesionActiva || (raiz.acciones ? raiz.acciones.destinos.length : 0) > 0

    // estado de las acciones
    property string accionEnCurso: ""       // "imprimir" / "enviar"
    property string mensaje: ""
    property bool mensajeExito: true
    property bool eligiendoDestino: false
    property string envioPendiente: ""      // "resumen" / "consolidado" / "ciclo"
    property var idsCorreo: []
    // ciclo abierto desde el panel del día o desde la lista de un fallo
    property var cicloAbierto: null

    function textoDeResultado(clave) {
        return clave ? I18n.t("menu.resultado_" + clave.toLowerCase(), I18n.lang) : sinDato
    }
    function colorDeResultado(clave) {
        return clave === "COMPLETADO" ? Colores.menuVerdeTexto
             : clave === "FALLO" ? Colores.peligroTexto
             : clave === "CANCELADO" ? Colores.advertenciaTexto
             : Colores.textoPrimario
    }
    function textoEnviarCorreo(listo) {
        return !listo ? I18n.t("menu.correo_no_configurado", I18n.lang)
             : !hayDestinoCorreo ? I18n.t("reportes.destino_sin_guardados", I18n.lang)
             : I18n.t("menu.enviar_correo", I18n.lang)
    }

    function pedirEnvio(que) {
        mensaje = ""
        envioPendiente = que
        if (que === "consolidado" && totalCiclos > umbralConsolidado)
            confirmarConsolidado.abrir()
        else
            eligiendoDestino = true
    }
    function enviar(correo) {
        eligiendoDestino = false
        accionEnCurso = "enviar"
        const p = raiz.rd.periodo, f = raiz.rd.fecha
        if (envioPendiente === "ciclo") {
            const ids = idsCorreo
            idsCorreo = []
            raiz.acciones.enviarCorreo(ids, correo)
        } else if (envioPendiente === "consolidado")
            raiz.acciones.enviarConsolidado(p, f, correo)
        else
            raiz.acciones.enviarResumen(p, f, correo)
    }
    function imprimirResumen() {
        mensaje = ""
        accionEnCurso = "imprimir"
        raiz.acciones.imprimirResumen(raiz.rd.periodo, raiz.rd.fecha)
    }
    function abrirCiclo(fila) {
        mensaje = ""
        cicloAbierto = fila
        raiz.historial?.cargarGrafica(fila.id)
    }
    function cerrarCiclo() {
        mensaje = ""
        cicloAbierto = null
        raiz.historial?.limpiarGrafica()
    }

    Component.onCompleted: {
        raiz.acciones?.actualizarCorreo()
        raiz.rd?.consultar()
    }
    Component.onDestruction: {
        raiz.rd?.cerrarFallo()
        raiz.historial?.limpiarGrafica()
        raiz.teclado?.cerrar()
    }

    Connections {
        target: raiz.acciones
        ignoreUnknownSignals: true
        function onAccionTerminada(exito, texto) {
            raiz.accionEnCurso = ""
            raiz.mensajeExito = exito
            raiz.mensaje = texto
        }
    }

    // ======================= fondo, encabezado y título =======================
    FondoApp { anchors.fill: parent }

    EncabezadoMenu {
        objectName: "encabezadoReportes"
        escala: raiz.escala
        conteoAlarmas: raiz.puente ? panelNotificaciones.conteoTotal : -1
        urgente: panelNotificaciones.urgente
        enCurso: panelNotificaciones.avisoEnCurso
        parpadeo: panelNotificaciones.parpadeo
        onCampanaPulsada: { raiz.campanaPulsada(); panelNotificaciones.abrir() }
    }
    Text {
        objectName: "tituloReportes"
        y: raiz.m(188)
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
        text: I18n.t("reportes.titulo_pantalla", I18n.lang)
        color: "white"
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(39)
    }

    // ======================= barra inferior (anclada abajo) =======================
    BarraInferiorMenu {
        id: barra
        objectName: "barraInferiorReportes"
        x: raiz.m(54)
        width: raiz.m(1139 - 54)
        y: parent.height - raiz.m(171)
        escala: raiz.escala
        personalizada: true
        // Inicio a la izquierda, Salir a la derecha (REP-01)
        Item {
            objectName: "botonInicioReportes"
            x: 0; y: 0; width: barra.mx(313); height: parent.height
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                y: raiz.m(18)
                width: raiz.m(60); height: width
                source: "../../assets/iconos/color/home_icon.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                y: raiz.m(88)
                width: parent.width - raiz.m(24)
                horizontalAlignment: Text.AlignHCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("reportes.boton_inicio", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(26)
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.inicioPulsado() }
        }
        Item {
            objectName: "botonSalirReportes"
            x: barra.mx(800); y: 0; width: barra.mx(1128 - 800); height: parent.height
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                y: raiz.m(18)
                width: raiz.m(60); height: width
                source: "../../assets/iconos/color/logout_icon.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                y: raiz.m(88)
                width: parent.width - raiz.m(24)
                horizontalAlignment: Text.AlignHCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("reportes.boton_salir", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(26)
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.salirPulsado() }
        }
    }

    // ======================= contenido =======================
    // Tarjeta blanca de una sección
    component Seccion: Rectangle {
        id: sec
        property string titulo: ""
        default property alias cuerpo: contenidoSeccion.data
        width: parent ? parent.width : 0
        height: encabezadoSeccion.height + contenidoSeccion.childrenRect.height + raiz.m(32)
        radius: raiz.m(24)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: Colores.bordeDivisor
        Text {
            id: encabezadoSeccion
            visible: sec.titulo !== ""
            x: raiz.m(24); y: raiz.m(18)
            width: parent.width - raiz.m(48)
            height: visible ? raiz.m(52) : raiz.m(0)
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: sec.titulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(30)
        }
        Item {
            id: contenidoSeccion
            x: raiz.m(24)
            y: (sec.titulo !== "" ? raiz.m(18) + encabezadoSeccion.height : raiz.m(24))
            width: parent.width - raiz.m(48)
        }
    }

    Flickable {
        id: desplazable
        objectName: "contenidoReportes"
        x: raiz.m(54); y: raiz.m(262)
        width: raiz.m(1139 - 54)
        height: barra.y - y - raiz.m(16)
        contentWidth: width
        contentHeight: columna.height + raiz.m(24)
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: columna
            width: parent.width
            spacing: raiz.m(24)

            // ---------------- Periodo (REP-02)
            Seccion {
                objectName: "seccionPeriodo"
                height: selector.height + subtitulo.height + raiz.m(60)
                SelectorPeriodo {
                    id: selector
                    width: parent.width
                    escala: raiz.escala
                    conAnio: true
                    periodo: raiz.rd ? raiz.rd.periodo : "mes"
                    rotulo: String(raiz.encabezado.titulo ?? "")
                    esActual: raiz.rd ? raiz.rd.esPeriodoActual : true
                    onElegido: (p) => { raiz.mensaje = ""; raiz.rd?.cambiarPeriodo(p) }
                    onMovido: (pasos) => {
                        raiz.mensaje = ""
                        if (pasos < 0) raiz.rd?.anterior(); else raiz.rd?.siguiente()
                    }
                }
                Text {
                    id: subtitulo
                    objectName: "subtituloPeriodo"
                    y: selector.height + raiz.m(12)
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: [raiz.encabezado.rango, raiz.encabezado.comparado].filter(function (x) { return x }).join("  ·  ")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(22)
                }
            }

            // ---------------- cargando / error
            Seccion {
                objectName: "seccionCargando"
                visible: raiz.cargando && !raiz.valido && !raiz.hayError
                height: visible ? raiz.m(140) : 0
                Text {
                    width: parent.width; height: raiz.m(92)
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    text: I18n.t("reportes.pantalla_cargando", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(26)
                }
            }
            Seccion {
                objectName: "tarjetaErrorReportes"
                visible: raiz.hayError
                height: visible ? raiz.m(220) : 0
                Column {
                    width: parent.width
                    spacing: raiz.m(24)
                    Text {
                        objectName: "textoErrorReportes"
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: raiz.rd ? raiz.rd.textoError : ""
                        color: Colores.peligroTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(26)
                    }
                    BotonPildora {
                        objectName: "botonReintentarReportes"
                        anchors.horizontalCenter: parent.horizontalCenter
                        escala: raiz.escala
                        primario: true
                        texto: raiz.rd ? raiz.rd.textoReintentar : ""
                        onPulsado: raiz.rd?.reintentar()
                    }
                }
            }

            // ---------------- el resto: solo con datos y sin error
            Column {
                id: cuerpoDatos
                objectName: "cuerpoReportes"
                visible: raiz.valido && !raiz.hayError
                width: parent.width
                spacing: raiz.m(24)

                // Indicadores (REP-03)
                Seccion {
                    objectName: "seccionIndicadores"
                    titulo: I18n.t("reportes.seccion_indicadores", I18n.lang)
                    height: indicadores.height + raiz.m(100)
                    Grid {
                        id: indicadores
                        width: parent.width
                        columns: 2
                        spacing: raiz.m(16)
                        Repeater {
                            model: raiz.datos.indicadores ?? []
                            TarjetaIndicador {
                                required property var modelData
                                objectName: "indicador_" + (modelData.clave ?? "")
                                width: (indicadores.width - indicadores.spacing) / 2
                                height: raiz.m(200)
                                escala: raiz.escala
                                dato: modelData
                            }
                        }
                    }
                }

                // Resultado (REP-04)
                Seccion {
                    objectName: "seccionResultado"
                    titulo: I18n.t("reportes.seccion_resultado", I18n.lang)
                    height: dona.height + raiz.m(100)
                    GraficaDona {
                        id: dona
                        width: parent.width
                        escala: raiz.escala
                        dona: raiz.datos.dona ?? ({})
                    }
                }

                // Ciclos por día (REP-05)
                Seccion {
                    objectName: "seccionCiclosDia"
                    titulo: I18n.t("reportes.seccion_ciclos_dia", I18n.lang)
                    height: grafica.height + raiz.m(100)
                    GraficaArea {
                        id: grafica
                        objectName: "graficaCiclosDia"
                        width: parent.width
                        height: raiz.m(380)
                        escala: raiz.escala
                        serie: raiz.datos.serie ?? ({})
                        rotuloTotal: I18n.t("reportes.graf_total", I18n.lang)
                        rotuloFallos: I18n.t("reportes.graf_fallos", I18n.lang)
                        textoVacio: I18n.t("reportes.graf_vacia", I18n.lang)
                    }
                }

                // Por programa (REP-06)
                Seccion {
                    objectName: "seccionProgramas"
                    titulo: I18n.t("reportes.seccion_programas", I18n.lang)
                    height: listaProgramas.height + raiz.m(100)
                    ListaProgramasReporte {
                        id: listaProgramas
                        width: parent.width
                        height: implicitHeight
                        escala: raiz.escala
                        programas: raiz.datos.programas ?? []
                        textoVacio: I18n.t("reportes.prog_vacia", I18n.lang)
                    }
                }

                // Calendario de ejecución (REP-07)
                Seccion {
                    objectName: "seccionCalendario"
                    height: calendario.height + (panelDia.visible ? panelDia.height + raiz.m(16) : 0) + raiz.m(56)
                    CalendarioEjecucion {
                        id: calendario
                        objectName: "calendarioEjecucion"
                        width: parent.width
                        height: implicitHeight
                        escala: raiz.escala
                        calendario: raiz.datos.calendario ?? ({})
                        diaElegido: raiz.rd ? raiz.rd.diaElegido : ""
                        puedeVerAnio: raiz.rd ? raiz.rd.puedeVerAnio : false
                        onDiaTocado: (fecha) => raiz.rd?.elegirDia(fecha)
                        onMesElegido: (mes) => raiz.rd?.elegirMes(mes)
                        onProgramaElegido: (n) => raiz.rd?.elegirPrograma(n)
                        onVerAnioPedido: raiz.rd?.verAnio()
                    }
                    PanelDiaCalendario {
                        id: panelDia
                        objectName: "panelDiaCalendario"
                        visible: (raiz.datos.calendario?.vista ?? "mes") === "mes"
                                 && (raiz.datos.calendario?.sin_programas ?? false) !== true
                        y: calendario.height + raiz.m(16)
                        width: parent.width
                        height: raiz.m(560)
                        escala: raiz.escala
                        panel: raiz.rd ? raiz.rd.panelDia : ({})
                        ciclos: raiz.rd ? raiz.rd.ciclosDia : []
                        cargando: raiz.rd ? raiz.rd.cargandoDia : false
                        error: (raiz.rd && raiz.rd.errorDia) ? raiz.rd.textoError : ""
                        textoToque: raiz.datos.calendario?.texto_toque_dia ?? ""
                        textoResultado: raiz.textoDeResultado
                        colorResultado: raiz.colorDeResultado
                        onCicloElegido: (ciclo) => raiz.abrirCiclo(ciclo)
                    }
                }

                // Causas de fallo (REP-08)
                Seccion {
                    id: seccionCausas
                    objectName: "seccionCausas"
                    titulo: I18n.t("reportes.seccion_causas", I18n.lang)
                    readonly property var causas: raiz.datos.causas ?? []
                    height: (causas.length === 0 ? raiz.m(80) : Math.ceil(causas.length / 2) * raiz.m(76))
                            + raiz.m(100)
                    Text {
                        objectName: "textoSinCausas"
                        visible: seccionCausas.causas.length === 0
                        width: parent.width; height: raiz.m(80)
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        text: I18n.t("reportes.sin_fallos", I18n.lang)
                        color: Colores.textoGuia
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(24)
                    }
                    Grid {
                        width: parent.width
                        columns: 2
                        columnSpacing: raiz.m(16)
                        Repeater {
                            model: seccionCausas.causas
                            Item {
                                id: filaCausa
                                required property var modelData
                                objectName: "causa_" + modelData.causa
                                width: (parent.width - raiz.m(16)) / 2
                                height: raiz.m(76)
                                Text {
                                    x: 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - raiz.m(150)
                                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                                    text: filaCausa.modelData.causa
                                    color: Colores.textoPrimario
                                    font.family: Tipografia.familia
                                    font.weight: Tipografia.pesoSemiBold
                                    font.pixelSize: raiz.fuente(24)
                                }
                                Text {
                                    anchors.right: flecha.left; anchors.rightMargin: raiz.m(10)
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: String(filaCausa.modelData.cantidad)
                                    color: Colores.peligroTexto
                                    font.family: Tipografia.familia
                                    font.weight: Tipografia.pesoBold
                                    font.pixelSize: raiz.fuente(28)
                                }
                                Text {
                                    id: flecha
                                    anchors.right: parent.right; anchors.rightMargin: raiz.m(8)
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "›"
                                    color: Colores.textoGuia
                                    font.family: Tipografia.familia
                                    font.weight: Tipografia.pesoBold
                                    font.pixelSize: raiz.fuente(36)
                                }
                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    width: parent.width; height: raiz.m(2)
                                    color: Colores.bordeDivisor
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: { raiz.mensaje = ""; raiz.rd?.abrirFallo(filaCausa.modelData.causa) }
                                }
                            }
                        }
                    }
                }

                // Mantenimiento / Alarmas / Por operador (REP-09/10/11)
                Row {
                    id: tresColumnas
                    width: parent.width
                    spacing: raiz.m(16)
                    readonly property real ancho: (width - 2 * spacing) / 3
                    readonly property var mant: raiz.rd ? raiz.rd.mantenimiento : ({})

                    Seccion {
                        objectName: "seccionMantenimiento"
                        titulo: I18n.t("reportes.seccion_mantenimiento", I18n.lang)
                        width: tresColumnas.ancho
                        height: Math.max(mantenimiento.height + raiz.m(100), alarmasPeriodo.height + raiz.m(100),
                                         operadoresPeriodo.height + raiz.m(100))
                        Column {
                            id: mantenimiento
                            width: parent.width
                            spacing: raiz.m(10)
                            AnilloProgreso {
                                objectName: "anilloMantenimiento"
                                anchors.horizontalCenter: parent.horizontalCenter
                                escala: raiz.escala
                                diametro: 200
                                grosor: 18
                                fraccion: tresColumnas.mant.fraccion ?? 0
                                colorClave: tresColumnas.mant.color ?? "menuVerde"
                                texto: String(tresColumnas.mant.anillo_texto ?? "")
                            }
                            // el título del anillo baja a varias líneas (no cabe en una)
                            Text {
                                objectName: "tituloAnilloMantenimiento"
                                width: mantenimiento.width
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                text: String(tresColumnas.mant.anillo_titulo ?? "")
                                color: Colores.textoSecundario
                                font.family: Tipografia.familia
                                font.pixelSize: raiz.fuente(20)
                            }
                            Repeater {
                                model: [String(tresColumnas.mant.proximo ?? ""),
                                        String(tresColumnas.mant.ultimo_texto ?? ""),
                                        I18n.t("reportes.mant_correctivos", I18n.lang) + ": "
                                            + String(tresColumnas.mant.correctivos_texto ?? raiz.sinDato),
                                        I18n.t("reportes.mant_repuestos", I18n.lang) + ": "
                                            + String(tresColumnas.mant.repuestos_texto ?? raiz.sinDato)]
                                Text {
                                    required property string modelData
                                    required property int index
                                    objectName: "textoMantenimiento_" + index
                                    width: mantenimiento.width
                                    wrapMode: Text.WordWrap
                                    text: modelData
                                    color: index === 0 ? Colores.textoPrimario : Colores.textoSecundario
                                    font.family: Tipografia.familia
                                    font.weight: index === 0 ? Tipografia.pesoSemiBold : Tipografia.pesoRegular
                                    font.pixelSize: raiz.fuente(20)
                                }
                            }
                        }
                    }
                    Seccion {
                        objectName: "seccionAlarmas"
                        titulo: I18n.t("reportes.seccion_alarmas", I18n.lang)
                        width: tresColumnas.ancho
                        height: Math.max(mantenimiento.height + raiz.m(100), alarmasPeriodo.height + raiz.m(100),
                                         operadoresPeriodo.height + raiz.m(100))
                        ListaAlarmasPeriodo {
                            id: alarmasPeriodo
                            width: parent.width
                            height: implicitHeight
                            escala: raiz.escala
                            capa: raiz
                            alarmas: raiz.datos.alarmas ?? ({})
                            onAlarmaElegida: (fila) => detalleAlarma.abrir(fila.detalle)
                        }
                    }
                    Seccion {
                        objectName: "seccionOperadores"
                        titulo: I18n.t("reportes.seccion_operadores", I18n.lang)
                        width: tresColumnas.ancho
                        height: Math.max(mantenimiento.height + raiz.m(100), alarmasPeriodo.height + raiz.m(100),
                                         operadoresPeriodo.height + raiz.m(100))
                        ListaOperadores {
                            id: operadoresPeriodo
                            width: parent.width
                            height: implicitHeight
                            escala: raiz.escala
                            operadores: raiz.datos.operadores ?? ({})
                        }
                    }
                }

                // Acciones (REP-12)
                Seccion {
                    objectName: "seccionAcciones"
                    titulo: I18n.t("reportes.seccion_acciones", I18n.lang)
                    height: raiz.m(100) + botonesAcciones.height
                            + (notaDestino.visible ? notaDestino.height + raiz.m(12) : 0) + raiz.m(8)
                    Flow {
                        id: botonesAcciones
                        width: parent.width
                        spacing: raiz.m(16)
                        BotonPildora {
                            objectName: "botonImprimirResumen"
                            escala: raiz.escala
                            primario: true
                            texto: I18n.t("reportes.accion_imprimir_resumen", I18n.lang)
                            habilitado: !raiz.ocupado && raiz.valido
                            onPulsado: raiz.imprimirResumen()
                        }
                        BotonPildora {
                            objectName: "botonEnviarResumen"
                            escala: raiz.escala
                            texto: I18n.t("reportes.accion_enviar_resumen", I18n.lang)
                            habilitado: !raiz.ocupado && raiz.correoListo && raiz.hayDestinoCorreo && raiz.valido
                            onPulsado: raiz.pedirEnvio("resumen")
                        }
                        BotonPildora {
                            objectName: "botonEnviarConsolidado"
                            escala: raiz.escala
                            texto: I18n.t("reportes.accion_enviar_consolidado", I18n.lang)
                            habilitado: !raiz.ocupado && raiz.correoListo && raiz.hayDestinoCorreo
                                        && raiz.valido && raiz.totalCiclos > 0
                            onPulsado: raiz.pedirEnvio("consolidado")
                        }
                    }
                    // por qué no se puede enviar (correo sin configurar o sin destinatarios guardados)
                    Text {
                        id: notaDestino
                        objectName: "notaDestinoReportes"
                        visible: !(raiz.correoListo && raiz.hayDestinoCorreo)
                        y: botonesAcciones.height + raiz.m(12)
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: raiz.textoEnviarCorreo(raiz.correoListo)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(22)
                    }
                }
            }
        }
    }

    AvisoAccion {
        id: aviso
        objectName: "avisoAccionReportes"
        z: 20
        escala: raiz.escala
        anchors.horizontalCenter: parent.horizontalCenter
        y: barra.y - height - raiz.m(24)
        trabajando: raiz.accionEnCurso !== ""
        error: !trabajando && !raiz.mensajeExito
        texto: raiz.eligiendoDestino ? ""
             : raiz.accionEnCurso !== "" && (raiz.acciones ? raiz.acciones.progreso : "") !== ""
               ? raiz.acciones.progreso
             : raiz.accionEnCurso === "imprimir" ? I18n.t("menu.imprimiendo", I18n.lang)
             : raiz.accionEnCurso === "enviar" ? I18n.t("menu.enviando", I18n.lang)
             : raiz.mensaje
        onCerrado: raiz.mensaje = ""
    }

    // ======================= causa de fallo: lista paginada (REP-08) =======================
    Rectangle {
        id: capaFallo
        objectName: "listadoFallo"
        visible: (raiz.rd ? raiz.rd.causaFallo !== "" : false) && raiz.cicloAbierto === null
        x: desplazable.x; y: desplazable.y
        width: desplazable.width; height: desplazable.height
        z: 10
        radius: raiz.m(24)
        color: Colores.fondoTarjeta
        BotonPildora {
            id: volverResumen
            objectName: "botonVolverResumen"
            x: raiz.m(16); y: raiz.m(16)
            escala: raiz.escala
            texto: "‹  " + I18n.t("reportes.volver_resumen", I18n.lang)
            onPulsado: raiz.rd?.cerrarFallo()
        }
        Text {
            id: tituloFallo
            objectName: "tituloFallo"
            x: raiz.m(16)
            anchors.top: volverResumen.bottom; anchors.topMargin: raiz.m(24)
            width: parent.width - raiz.m(32)
            wrapMode: Text.WordWrap
            text: I18n.t("reportes.ciclos_con_fallo", I18n.lang)
                  .replace("{causa}", raiz.rd ? raiz.rd.causaFallo : "")
                  .replace("{n}", String(raiz.rd ? raiz.rd.totalFallo : 0))
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(28)
        }
        ListaCiclos {
            objectName: "listaFallo"
            x: raiz.m(16)
            anchors.top: tituloFallo.bottom; anchors.topMargin: raiz.m(16)
            anchors.bottom: paginacionFallo.top; anchors.bottomMargin: raiz.m(16)
            width: parent.width - raiz.m(32)
            escala: raiz.escala
            ciclos: raiz.rd ? raiz.rd.ciclosFallo : []
            seleccionable: true
            conOperador: true
            textoResultado: raiz.textoDeResultado
            colorResultado: raiz.colorDeResultado
            onCicloElegido: (fila) => raiz.abrirCiclo(fila)
            Text {
                objectName: "avisoListaFallo"
                anchors.centerIn: parent
                anchors.verticalCenterOffset: raiz.m(28)
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: text !== ""
                text: (raiz.rd && raiz.rd.cargandoFallo) ? I18n.t("menu.cargando", I18n.lang)
                    : (raiz.rd && raiz.rd.sinConexionFallo) ? I18n.t("menu.sin_conexion", I18n.lang)
                    : (raiz.rd && raiz.rd.ciclosFallo.length === 0) ? I18n.t("reportes.sin_ciclos_fallo", I18n.lang)
                    : ""
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(26)
            }
        }
        Item {
            id: paginacionFallo
            objectName: "paginacionFallo"
            x: raiz.m(16)
            anchors.bottom: parent.bottom; anchors.bottomMargin: raiz.m(16)
            width: parent.width - raiz.m(32)
            visible: raiz.rd ? raiz.rd.paginasFallo > 1 : false
            height: visible ? raiz.m(64) : 0
            BotonPildora {
                objectName: "botonPaginaAnterior"
                anchors.left: parent.left
                escala: raiz.escala
                texto: "‹  " + I18n.t("reportes.pagina_anterior", I18n.lang)
                habilitado: !!(raiz.rd && raiz.rd.paginaFallo > 1 && !raiz.rd.cargandoFallo)
                onPulsado: raiz.rd?.moverPaginaFallo(-1)
            }
            Text {
                objectName: "textoPaginaFallo"
                anchors.centerIn: parent
                text: I18n.t("reportes.pagina", I18n.lang)
                      .replace("{n}", String(raiz.rd ? raiz.rd.paginaFallo : 1))
                      .replace("{total}", String(raiz.rd ? raiz.rd.paginasFallo : 1))
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(24)
            }
            BotonPildora {
                objectName: "botonPaginaSiguiente"
                anchors.right: parent.right
                escala: raiz.escala
                texto: I18n.t("reportes.pagina_siguiente", I18n.lang) + "  ›"
                habilitado: !!(raiz.rd && raiz.rd.paginaFallo < raiz.rd.paginasFallo && !raiz.rd.cargandoFallo)
                onPulsado: raiz.rd?.moverPaginaFallo(1)
            }
        }
    }

    // ======================= ciclo abierto: acciones, datos y curva =======================
    Rectangle {
        id: capaCiclo
        objectName: "capaCiclo"
        visible: raiz.cicloAbierto !== null
        x: desplazable.x; y: desplazable.y
        width: desplazable.width; height: desplazable.height
        z: 15
        radius: raiz.m(24)
        color: Colores.fondoTarjeta
        BotonPildora {
            id: volverCiclo
            objectName: "botonVolverCiclo"
            x: raiz.m(16); y: raiz.m(16)
            escala: raiz.escala
            texto: "‹  " + I18n.t("menu.volver", I18n.lang)
            onPulsado: raiz.cerrarCiclo()
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: raiz.m(16)
            y: raiz.m(16)
            spacing: raiz.m(16)
            BotonPildora {
                objectName: "botonEnviarCiclo"
                escala: raiz.escala
                texto: raiz.textoEnviarCorreo(raiz.correoListo)
                habilitado: !raiz.ocupado && raiz.correoListo && raiz.hayDestinoCorreo
                onPulsado: {
                    raiz.idsCorreo = [raiz.cicloAbierto.id]
                    raiz.pedirEnvio("ciclo")
                }
            }
            BotonPildora {
                objectName: "botonImprimirCiclo"
                escala: raiz.escala
                primario: true
                texto: I18n.t("menu.imprimir", I18n.lang)
                habilitado: !raiz.ocupado
                onPulsado: {
                    raiz.mensaje = ""
                    raiz.accionEnCurso = "imprimir"
                    raiz.acciones.imprimir([raiz.cicloAbierto.id])
                }
            }
        }
        DetalleCiclo {
            objectName: "detalleCicloReportes"
            x: raiz.m(16)
            anchors.top: volverCiclo.bottom; anchors.topMargin: raiz.m(24)
            anchors.bottom: parent.bottom
            width: parent.width - raiz.m(32)
            escala: raiz.escala
            readonly property var c: raiz.cicloAbierto ?? ({})
            fecha: raiz.dato(c.fecha)
            hora: raiz.dato(c.hora)
            programa: raiz.dato(c.programa)
            programaNombre: raiz.dato(c.programa_nombre)
            resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
            resultadoDetalle: c.resultado_detalle ?? ""
            colorResultado: raiz.colorDeResultado(c.resultado ?? "")
            noConforme: c.no_conforme === true
            operador: raiz.dato(c.operador)
            datosGrafica: raiz.historial ? raiz.historial.datosGrafica : ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
            fasesGrafica: raiz.historial ? raiz.historial.fasesGrafica : []
            graficaDisponible: raiz.historial ? raiz.historial.graficaDisponible : false
            onCerrarPulsado: raiz.cerrarCiclo()
        }
    }

    // ======================= destino del correo y confirmaciones =======================
    SelectorDestino {
        objectName: "selectorDestinoReportes"
        anchors.fill: parent
        z: 30
        visible: raiz.eligiendoDestino
        escala: raiz.escala
        destinos: raiz.acciones ? raiz.acciones.destinos : []
        teclado: raiz.teclado
        sesionActiva: raiz.sesionActiva
        onElegido: (correo) => raiz.enviar(correo)
        onCancelado: raiz.eligiendoDestino = false
    }
    ModalConfirmacion {
        id: confirmarConsolidado
        objectName: "confirmarConsolidado"
        z: 40
        titulo: I18n.t("reportes.consolidado_grande_titulo", I18n.lang)
        cuerpo: I18n.t("reportes.consolidado_grande_texto", I18n.lang)
                .replace("{n}", String(raiz.totalCiclos))
                .replace("{mb}", String(Math.max(1, Math.round(raiz.totalCiclos * raiz.mbPorCiclo))))
        textoAccion: I18n.t("reportes.accion_enviar_consolidado", I18n.lang)
        onAceptado: raiz.eligiendoDestino = true
    }

    // ======================= paneles =======================
    VentanaDetalleAlarma {
        id: detalleAlarma
        objectName: "detalleAlarmaReportes"
    }
    PanelNotificaciones {
        id: panelNotificaciones
        objectName: "panelNotificacionesReportes"
        titulo: I18n.t("notificaciones.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        rotuloAlertas: I18n.t("notificaciones.alertas_avisos", I18n.lang)
        textoSinAlarmas: I18n.t("ciclo.sin_alarmas", I18n.lang)
        alarmas: raiz.puente ? raiz.puente.alarms : null
        puente: raiz.puente
        comandosSistema: raiz.comandosSistema
    }
}
