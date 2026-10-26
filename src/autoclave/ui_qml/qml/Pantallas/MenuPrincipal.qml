pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import Tema
import "../Componentes"
import Autoclave.I18n

// Menú Principal (planeacion_menu_principal_ui_qml.md, Fase 3). Referencia:
// docs/mockups/menu_principal_v3.png (1188 x 1906).
//
// Geometría: px del marco del diseñador (1196 x 1917, el de PantallaPreciclo.qml)
// escalados con m() (D-18). El v3 está desplazado respecto a ese marco: sus
// coordenadas pasan al marco restando 5 en x y 1 en y (medido sobre el
// encabezado y la barra inferior, que coinciden con los de PantallaPreciclo.qml;
// ver informe de Fase 3). Alto flexible (9:16): encabezado anclado arriba, barra
// inferior anclada abajo, y el alto sobrante se reparte en dos partes iguales:
// entre las tarjetas de menú y el resumen, y entre el resumen y la barra.
//
// Solo composición: los datos vienen de `resumen` (bridge/resumen_sistema.py,
// solo lectura) y del contador de alarmas de `puente` (UiBridge); las acciones
// solo emiten señales (la navegación real es la Fase 4, diferida).
Item {
    id: raiz

    // Los inyecta quien usa la pantalla (arnés de pruebas por ahora)
    property QtObject puente: null      // UiBridge: alarmas de la campana (contador y panel)
    property QtObject resumen: null     // ResumenSistema (o datos de ejemplo del arnés)
    property QtObject infoEquipo: null  // InfoEquipo: panel de información del equipo
    // ComandosSistema (E5): Apagar equipo en el panel de equipo
    property QtObject comandosSistema: null
    property QtObject historial: null   // CiclosHistorial: listados de Ciclos hoy e Historial
    property QtObject acciones: null    // AccionesCiclos: imprimir / enviar por correo (Historial, Reportes)
    property QtObject reporte: null     // ReporteResumen: resumen por periodo de Reportes
    property QtObject teclado: null     // PanelTeclado: correo de destino escrito a mano
    // Casa de la barra: activa cuando hay una pantalla a la que regresar (la de
    // preciclo o la de ciclo en curso, desde cuyo engranaje se abrió el menú)
    property bool inicioActivo: false

    // ---- acciones: las resuelve quien usa la pantalla (Main.qml) ----
    signal iniciarSesionPulsado()       // abre el login QML (Main.qml)
    signal campanaPulsada()
    signal atrasPulsado()       // U2: pantalla anterior (no cierra sesión)
    signal inicioPulsado()
    signal historialPulsado()
    signal reportesPulsado()
    signal informacionPulsado()
    signal ciclosTotalesPulsado()
    signal ciclosHoyPulsado()
    signal mantenimientoPulsado()
    signal ultimoCicloPulsado()


    readonly property string sinDato: "—"
    function dato(v) { return (v === undefined || v === null || v === "") ? sinDato : v }

    readonly property real anchoMockup: 1196
    readonly property real altoMockup: 1917
    readonly property real escala: width / anchoMockup
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // Alto sobrante en px del mockup (0 en el marco de diseño) y su mitad
    readonly property real _extra: Math.max(0, height / escala - altoMockup)
    readonly property real _desfaseResumen: _extra / 2

    readonly property string iconosMono: "../../assets/iconos/mono/"
    readonly property string iconosColor: "../../assets/iconos/color/"

    // ---- datos (todo "—" si falta) ----
    readonly property bool sinConexion: resumen?.sinConexion ?? false
    // Resultado de un ciclo por su clave (COMPLETADO / CANCELADO / FALLO, o "")
    function textoDeResultado(clave) {
        return clave ? I18n.t("menu.resultado_" + clave.toLowerCase(), I18n.lang) : sinDato
    }
    // COMPLETADO verde (mockup); FALLO y CANCELADO PROVISIONALES: tonos de peligro y
    // advertencia, NO los colores de alarma reservados por IEC 60601-1-8
    function colorDeResultado(clave) {
        return clave === "COMPLETADO" ? Colores.menuVerdeTexto
             : clave === "FALLO" ? Colores.peligroTexto
             : clave === "CANCELADO" ? Colores.advertenciaTexto
             : Colores.textoPrimario
    }
    readonly property string claveResultado: resumen?.ultimoResultado ?? ""
    // P4 (tanda 16, D-14.4): un último ciclo NO CONFORME se rotula así (en el
    // detalle queda además su resultado técnico, COMPLETADO)
    readonly property bool ultimoNoConforme: resumen?.ultimoNoConforme ?? false
    readonly property string textoResultado: ultimoNoConforme
        ? I18n.t("menu.resultado_no_conforme", I18n.lang) : textoDeResultado(claveResultado)
    readonly property color colorResultado: ultimoNoConforme
        ? Colores.peligroTexto : colorDeResultado(claveResultado)

    // Abre una ventana flotante por nombre ("ultimo_ciclo", "mantenimiento",
    // "ciclos_hoy", "historial", "reportes"), como si se tocara su tarjeta (arnés y capturas)
    function abrirVentana(nombre) {
        if (nombre === "ultimo_ciclo") ventanaUltimoCiclo.abrir()
        else if (nombre === "mantenimiento") ventanaMantenimiento.abrir()
        else if (nombre === "ciclos_hoy") ventanaCiclosHoy.abrir()
        else if (nombre === "historial") ventanaHistorial.abrir()
        else if (nombre === "reportes") ventanaReportes.abrir()
    }

    // La pantalla activa consulta el resumen y lo sondea cada 10 s (§6.5)
    function _activar() { if (visible) resumen?.iniciar(); else resumen?.detener() }
    onVisibleChanged: _activar()
    onResumenChanged: _activar()
    Component.onCompleted: _activar()
    Component.onDestruction: resumen?.detener()

    // ======================= fondo y encabezado =======================
    FondoApp { anchors.fill: parent }

    EncabezadoMenu {
        objectName: "encabezadoMenu"
        escala: raiz.escala
        // alarmas más avisos de seguridad del panel (U1 de la tanda 2)
        conteoAlarmas: raiz.puente ? panelNotificaciones.conteoTotal : -1
        urgente: panelNotificaciones.urgente
        enCurso: panelNotificaciones.avisoEnCurso
        parpadeo: panelNotificaciones.parpadeo
        onCampanaPulsada: { raiz.campanaPulsada(); panelNotificaciones.abrir() }
    }

    // Aviso de backend sin respuesta (D-16). PROVISIONAL: sin diseño del diseñador.
    Rectangle {
        objectName: "avisoSinConexion"
        visible: raiz.sinConexion
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz.m(192)
        width: textoAviso.implicitWidth + raiz.m(64)
        height: raiz.m(56)
        radius: height / 2
        color: Colores.fondoTarjeta
        opacity: 0.92
        Text {
            id: textoAviso
            anchors.centerIn: parent
            text: I18n.t("menu.sin_conexion", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(24)
        }
    }

    // ======================= título =======================
    // Casa de contorno dibujada (en assets solo hay casa rellena): caja 57 x 57 en (567, 262)
    Shape {
        x: raiz.m(567); y: raiz.m(262)
        width: raiz.m(57); height: raiz.m(57)
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "white"
            strokeWidth: raiz.m(3.3)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathPolyline {
                path: [Qt.point(raiz.m(1.5), raiz.m(28)), Qt.point(raiz.m(28.5), raiz.m(1.5)),
                       Qt.point(raiz.m(55.5), raiz.m(28))]
            }
            PathPolyline {
                path: [Qt.point(raiz.m(9), raiz.m(20)), Qt.point(raiz.m(9), raiz.m(55.5)),
                       Qt.point(raiz.m(22), raiz.m(55.5)), Qt.point(raiz.m(22), raiz.m(37)),
                       Qt.point(raiz.m(35), raiz.m(37)), Qt.point(raiz.m(35), raiz.m(55.5)),
                       Qt.point(raiz.m(48), raiz.m(55.5)), Qt.point(raiz.m(48), raiz.m(20))]
            }
        }
    }

    component Titulo: Text {
        property real cx: 0
        property real bl: 0
        x: raiz.m(cx) - width / 2
        y: raiz.m(bl) - baselineOffset
        color: "white"
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(39)
    }
    Titulo { objectName: "tituloMenu"; cx: 596.5; bl: 390; text: I18n.t("menu.titulo", I18n.lang) }

    // ======================= tarjetas de menú =======================
    component Fila1: TarjetaMenu {
        escala: raiz.escala
        y: raiz.m(499); height: raiz.m(320)
    }
    component Fila2: TarjetaMenu {
        escala: raiz.escala
        y: raiz.m(843); width: raiz.m(349); height: raiz.m(320)
        tamTitulo: 25; tamDescripcion: 21
    }

    Fila1 {
        objectName: "tarjetaIniciarSesion"
        x: raiz.m(54); width: raiz.m(716)
        titulo: I18n.t("acciones.iniciar_sesion", I18n.lang)
        descripcion: I18n.t("menu.iniciar_sesion_desc", I18n.lang)
        icono: raiz.iconosMono + "usuario.svg"
        tamIcono: 87
        colorAcento: Colores.menuVerde
        colorTitulo: Colores.menuVerdeTexto
        aroAcento: true
        conBorde: true
        onPulsada: raiz.iniciarSesionPulsado()
    }
    // Historial: listado de ciclos con filtro diario / semanal / mensual, solo
    // para ver (decisión de Cristian, 2026-10-02)
    Fila1 {
        objectName: "tarjetaHistorial"
        x: raiz.m(789); width: raiz.m(350)
        titulo: I18n.t("modulos.historial", I18n.lang)
        descripcion: I18n.t("menu.historial_desc", I18n.lang)
        // variante color: glifo morado con su propio aro gris, como el v3
        icono: raiz.iconosColor + "historial.svg"
        iconoTenido: false
        iconoIncluyeAro: true
        onPulsada: { raiz.historialPulsado(); ventanaHistorial.abrir() }
    }
    // Reportes: resumen por periodo (decisión de Cristian, 2026-10-06); el
    // consolidado y las alarmas se agregan después como pestañas
    // U5 (tanda 3): sin la tarjeta "Tiempo adicional de secado", Reportes e
    // Información ocupan la fila a mitad de ancho cada una (54..1139 con 19 de
    // separación, como entre Iniciar sesión e Historial)
    Fila2 {
        objectName: "tarjetaReportes"
        x: raiz.m(54); width: raiz.m(533)
        titulo: I18n.t("modulos.reportes", I18n.lang)
        descripcion: I18n.t("menu.reportes_desc", I18n.lang)
        icono: raiz.iconosMono + "reportes.svg"
        tamIcono: 85
        colorAcento: Colores.menuNaranja
        onPulsada: { raiz.reportesPulsado(); ventanaReportes.abrir() }
    }
    Fila2 {
        objectName: "tarjetaInformacion"
        x: raiz.m(606); width: raiz.m(533)
        // Abre la información del equipo, el mismo panel que el recuadro de modelo
        // y serie de PantallaPreciclo.qml (decisión de Cristian, 2026-10-02)
        titulo: I18n.t("modulos.informacion", I18n.lang)
        descripcion: I18n.t("menu.informacion_desc", I18n.lang)
        icono: raiz.iconosMono + "informacion.svg"
        iconoIncluyeAro: true
        colorAcento: Colores.menuAzul
        aroAcento: true
        onPulsada: {
            raiz.informacionPulsado()
            raiz.infoEquipo?.actualizar()
            panelEquipo.abrir()
        }
    }

    // ======================= resumen del sistema =======================
    Item {
        id: bloqueResumen
        width: parent.width
        height: parent.height
        y: raiz.m(raiz._desfaseResumen)

        Titulo { objectName: "tituloResumen"; cx: 598; bl: 1244; text: I18n.t("menu.resumen", I18n.lang) }

        component Resumen: TarjetaResumen {
            escala: raiz.escala
            y: raiz.m(1295); height: raiz.m(330)
        }

        // Solo informativa: se ve normal pero no es botón (decisión de Cristian, 2026-10-02)
        Resumen {
            objectName: "resumenCiclosTotales"
            x: raiz.m(54); width: raiz.m(230)
            interactiva: false
            icono: raiz.iconosMono + "ciclos_totales.svg"
            tamIcono: 79
            colorAcento: Colores.menuAzul
            rotulo: I18n.t("menu.ciclos_totales", I18n.lang)
            valor: raiz.dato(raiz.resumen?.ciclosTotales)   // TODO(MP-06a): último numero_ciclo
            subrotulo: I18n.t("menu.realizados", I18n.lang)
            onPulsada: raiz.ciclosTotalesPulsado()
        }
        Resumen {
            objectName: "resumenMantenimiento"
            x: raiz.m(300); width: raiz.m(293)
            icono: raiz.iconosMono + "mantenimiento.svg"
            tamIcono: 73
            colorAcento: Colores.menuNaranja
            rotulo: I18n.t("menu.proximo_mantenimiento", I18n.lang)
            // M1 (tanda 3): fecha del próximo mantenimiento; "VENCIDO" si ya pasó
            valor: (raiz.resumen?.mantenimientoVencido ?? false)
                   ? I18n.t("menu.vencido", I18n.lang)
                   : raiz.dato(raiz.resumen?.proximoMantenimiento)
            onPulsada: { raiz.mantenimientoPulsado(); ventanaMantenimiento.abrir() }
        }
        // Abre el listado de los ciclos terminados hoy; tocar uno muestra su gráfica y datos
        Resumen {
            objectName: "resumenCiclosHoy"
            x: raiz.m(609); width: raiz.m(206)
            icono: raiz.iconosMono + "reloj.svg"
            iconoIncluyeAro: true
            colorAcento: Colores.menuMorado
            rotulo: I18n.t("menu.ciclos_hoy", I18n.lang)
            valor: raiz.dato(raiz.resumen?.ciclosHoy)
            subrotulo: I18n.t("menu.realizados", I18n.lang)
            onPulsada: { raiz.ciclosHoyPulsado(); ventanaCiclosHoy.abrir() }
        }
        Resumen {
            objectName: "resumenUltimoCiclo"
            x: raiz.m(831); width: raiz.m(308)
            icono: raiz.iconosMono + "reproducir.svg"
            iconoIncluyeAro: true
            colorAcento: Colores.menuAzul
            rotulo: I18n.t("menu.ultimo_ciclo", I18n.lang)
            onPulsada: { raiz.ultimoCicloPulsado(); ventanaUltimoCiclo.abrir() }
            DetalleUltimoCiclo {
                escala: raiz.escala
                fecha: raiz.dato(raiz.resumen?.ultimoFecha)
                hora: raiz.dato(raiz.resumen?.ultimoHora)
                rotuloPrograma: I18n.t("menu.programa", I18n.lang)
                programa: raiz.dato(raiz.resumen?.ultimoPrograma)
                rotuloResultado: I18n.t("menu.resultado", I18n.lang)
                resultado: raiz.textoResultado
                colorResultado: raiz.colorResultado
            }
        }
    }

    // ======================= barra inferior (anclada abajo) =======================
    BarraInferiorMenu {
        objectName: "barraInferiorMenu"
        // D8-5.2: el Menú no tiene una tarjeta única; la barra mide lo mismo
        // que la grilla de tarjetas de encima (x 54 a 1139 del lienzo)
        x: raiz.m(54)
        width: raiz.m(1139 - 54)
        y: parent.height - raiz.m(raiz.altoMockup - 1746)
        escala: raiz.escala
        version: I18n.t("app.version", I18n.lang)
        inicioActivo: raiz.inicioActivo
        onAtrasPulsado: raiz.atrasPulsado()
        onInicioPulsado: raiz.inicioPulsado()
    }

    // ======================= ventanas flotantes (D-21, PROVISIONALES) =======================
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

    VentanaFlotante {
        id: ventanaUltimoCiclo
        objectName: "ventanaUltimoCiclo"
        escala: raiz.escala
        altoTarjeta: 1500
        titulo: I18n.t("menu.ventana_ultimo_ciclo", I18n.lang)
        // la curva se pide solo al abrir (GET /cycle/history/{id}/graph)
        onMostrada: raiz.resumen?.cargarGraficaUltimo()

        DetalleCiclo {
            objectName: "detalleUltimoCiclo"
            anchors.fill: parent
            escala: raiz.escala
            fecha: raiz.dato(raiz.resumen?.ultimoFecha)
            hora: raiz.dato(raiz.resumen?.ultimoHora)
            programa: raiz.dato(raiz.resumen?.ultimoPrograma)
            programaNombre: raiz.dato(raiz.resumen?.ultimoProgramaNombre)
            resultadoTexto: raiz.textoDeResultado(raiz.claveResultado)
            resultadoDetalle: raiz.resumen?.ultimoResultadoDetalle ?? ""
            colorResultado: raiz.colorDeResultado(raiz.claveResultado)
            noConforme: raiz.ultimoNoConforme
            operador: raiz.dato(raiz.resumen?.ultimoOperador)
            datosGrafica: raiz.resumen?.datosGraficaUltimo ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
            fasesGrafica: raiz.resumen?.fasesGraficaUltimo ?? []
            graficaDisponible: raiz.resumen?.graficaUltimoDisponible ?? false
            onCerrarPulsado: ventanaUltimoCiclo.cerrar()
        }
    }

    // M1 (tanda 3): vencimiento, último mantenimiento y ciclos restantes
    VentanaFlotante {
        id: ventanaMantenimiento
        objectName: "ventanaMantenimiento"
        escala: raiz.escala
        altoTarjeta: 520
        titulo: I18n.t("menu.ventana_mantenimiento", I18n.lang)
        Column {
            width: parent.width
            spacing: raiz.m(28)
            Campo {
                width: parent.width
                objectName: "campoProximoMantenimiento"
                rotulo: I18n.t("menu.proximo_vencimiento", I18n.lang)
                valor: (raiz.resumen?.mantenimientoVencido ?? false)
                       ? I18n.t("menu.vencido", I18n.lang)
                       : raiz.dato(raiz.resumen?.proximoMantenimiento)
            }
            Campo { width: parent.width; rotulo: I18n.t("menu.ultimo_mantenimiento", I18n.lang); valor: raiz.dato(raiz.resumen?.ultimoMantenimiento) }
            Campo { width: parent.width; rotulo: I18n.t("menu.ciclos_restantes", I18n.lang); valor: raiz.dato(raiz.resumen?.ciclosRestantesMantenimiento) }
        }
    }

    // Mensaje centrado de un listado: cargando, sin conexión o sin ciclos
    component AvisoLista: Text {
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(26)
        text: (raiz.historial?.cargando ?? false) && (raiz.historial?.ciclos?.length ?? 0) === 0
              ? I18n.t("menu.cargando", I18n.lang)
              : (raiz.historial?.sinConexion ?? false) ? I18n.t("menu.sin_conexion", I18n.lang)
              : (raiz.historial?.ciclos?.length ?? 0) === 0 ? I18n.t("menu.sin_ciclos", I18n.lang)
              : ""
        visible: text !== ""
    }
    component NotaTruncado: Text {
        visible: raiz.historial?.truncado ?? false
        text: I18n.t("menu.lista_truncada", I18n.lang)
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(20)
    }

    // Ciclos hoy: listado de los ciclos terminados desde las 00:00 (los mismos que
    // cuenta la tarjeta); tocar uno muestra su gráfica y sus datos en la misma
    // ventana, con un botón para volver al listado.
    VentanaFlotante {
        id: ventanaCiclosHoy
        objectName: "ventanaCiclosHoy"
        escala: raiz.escala
        altoTarjeta: 1500
        // fila elegida del listado (null = se muestra el listado)
        property var seleccion: null
        titulo: seleccion ? I18n.t("menu.ciclo_titulo", I18n.lang) + " " + seleccion.numero
                          : I18n.t("menu.ventana_ciclos_hoy", I18n.lang)
        onMostrada: { seleccion = null; raiz.historial?.consultar("dia", true) }
        onCerrada: { seleccion = null; raiz.historial?.limpiarGrafica() }

        Item {
            anchors.fill: parent
            visible: ventanaCiclosHoy.seleccion === null
            ListaCiclos {
                objectName: "listaCiclosHoy"
                anchors.fill: parent
                anchors.bottomMargin: notaHoy.visible ? notaHoy.height + raiz.m(12) : 0
                escala: raiz.escala
                ciclos: raiz.historial?.ciclos ?? []
                seleccionable: true
                textoResultado: raiz.textoDeResultado
                colorResultado: raiz.colorDeResultado
                onCicloElegido: (fila) => {
                    ventanaCiclosHoy.seleccion = fila
                    raiz.historial?.cargarGrafica(fila.id)
                }
                AvisoLista { anchors.verticalCenterOffset: raiz.m(28) }
            }
            NotaTruncado { id: notaHoy; anchors.bottom: parent.bottom }
        }

        Item {
            anchors.fill: parent
            visible: ventanaCiclosHoy.seleccion !== null
            // Volver al listado
            Item {
                id: volver
                objectName: "botonVolverListado"
                width: textoVolver.implicitWidth + raiz.m(56); height: raiz.m(56)
                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: Colores.fondoSutil
                    border.width: raiz.m(2); border.color: Colores.bordeDivisor
                }
                Text {
                    id: textoVolver
                    anchors.centerIn: parent
                    text: "\u2039  " + I18n.t("menu.volver", I18n.lang)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: { ventanaCiclosHoy.seleccion = null; raiz.historial?.limpiarGrafica() }
                }
            }
            DetalleCiclo {
                objectName: "detalleCicloHoy"
                anchors.top: volver.bottom
                anchors.topMargin: raiz.m(24)
                anchors.bottom: parent.bottom
                width: parent.width
                escala: raiz.escala
                readonly property var c: ventanaCiclosHoy.seleccion ?? ({})
                fecha: raiz.dato(c.fecha)
                hora: raiz.dato(c.hora)
                programa: raiz.dato(c.programa)
                programaNombre: raiz.dato(c.programa_nombre)
                resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
                resultadoDetalle: c.resultado_detalle ?? ""
                colorResultado: raiz.colorDeResultado(c.resultado ?? "")
                noConforme: c.no_conforme === true   // P4 (D-14.4)
                operador: raiz.dato(c.operador)
                datosGrafica: raiz.historial?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
                fasesGrafica: raiz.historial?.fasesGrafica ?? []
                graficaDisponible: raiz.historial?.graficaDisponible ?? false
                onCerrarPulsado: ventanaCiclosHoy.cerrar()
            }
        }
    }

    // Historial: listado por periodo de calendario (Diario / Semanal / Mensual,
    // recorrido con las flechas sin pasar del actual), por fecha de inicio (incluye
    // ciclos interrumpidos). Tocar un ciclo muestra sus datos y su gráfica; las
    // casillas marcan ciclos para imprimirlos en la impresora térmica o enviarlos
    // por correo como PDF con gráfica (bridge/acciones_ciclos.py).
    VentanaFlotante {
        id: ventanaHistorial
        objectName: "ventanaHistorial"
        escala: raiz.escala
        altoTarjeta: 1500
        property string periodo: "dia"
        // fila elegida del listado (null = se muestra el listado)
        property var seleccion: null
        // ciclos por enviar mientras se elige el destino (los marcados, o el abierto)
        property var idsCorreo: []
        property string accionEnCurso: ""      // "imprimir" / "enviar" mientras trabaja
        property string mensaje: ""
        property bool mensajeExito: true
        property bool eligiendoDestino: false
        readonly property bool ocupado: raiz.acciones?.ocupado ?? false
        readonly property var marcados: raiz.historial?.seleccionados ?? []
        readonly property bool correoListo: raiz.acciones?.correoConfigurado ?? false
        readonly property string textoEnviar: correoListo ? I18n.t("menu.enviar_correo", I18n.lang)
                                                          : I18n.t("menu.correo_no_configurado", I18n.lang)
        titulo: seleccion ? I18n.t("menu.ciclo_titulo", I18n.lang) + " " + seleccion.numero
                          : I18n.t("menu.ventana_historial", I18n.lang)

        // al abrir: hoy; los filtros conservan la fecha que se está viendo
        function elegir(p) { periodo = p; seleccion = null; mensaje = ""; raiz.historial?.cambiarPeriodo(p) }
        function mover(pasos) { mensaje = ""; raiz.historial?.moverPeriodo(pasos) }
        function volverAlListado() { seleccion = null; mensaje = ""; raiz.historial?.limpiarGrafica() }
        function imprimir(ids) {
            mensaje = ""
            accionEnCurso = "imprimir"
            raiz.acciones?.imprimir(ids)
        }
        function pedirDestino(ids) {
            mensaje = ""
            idsCorreo = ids
            eligiendoDestino = true
        }
        function enviar(correo) {
            eligiendoDestino = false
            accionEnCurso = "enviar"
            raiz.acciones?.enviarCorreo(idsCorreo, correo)
        }
        onMostrada: {
            seleccion = null
            eligiendoDestino = false
            raiz.acciones?.actualizarCorreo()   // config/correo.json se edita a mano por ahora
            periodo = "dia"
            mensaje = ""
            raiz.historial?.consultarHistorial("dia")
        }
        onCerrada: {
            seleccion = null
            eligiendoDestino = false
            mensaje = ""
            raiz.teclado?.cerrar()
            raiz.historial?.limpiarGrafica()
        }

        Connections {
            target: ventanaHistorial.visible ? raiz.acciones : null
            function onAccionTerminada(exito, texto) {
                ventanaHistorial.accionEnCurso = ""
                ventanaHistorial.mensajeExito = exito
                ventanaHistorial.mensaje = texto
            }
        }

        // ---------- listado ----------
        Item {
            anchors.fill: parent
            visible: ventanaHistorial.seleccion === null

            SelectorPeriodo {
                id: selectorHistorial
                width: parent.width
                escala: raiz.escala
                periodo: ventanaHistorial.periodo
                rotulo: raiz.historial?.rotuloPeriodo ?? ""
                esActual: raiz.historial?.esPeriodoActual ?? true
                onElegido: (p) => ventanaHistorial.elegir(p)
                onMovido: (pasos) => ventanaHistorial.mover(pasos)
            }

            ListaCiclos {
                objectName: "listaHistorial"
                anchors.top: selectorHistorial.bottom
                anchors.topMargin: raiz.m(16)
                anchors.bottom: barraAcciones.top
                anchors.bottomMargin: raiz.m(16) + (notaHistorial.visible ? notaHistorial.height + raiz.m(8) : 0)
                width: parent.width
                escala: raiz.escala
                ciclos: raiz.historial?.ciclos ?? []
                seleccionable: true
                marcable: true
                marcados: ventanaHistorial.marcados
                todasMarcadas: raiz.historial?.todosSeleccionados ?? false
                textoResultado: raiz.textoDeResultado
                colorResultado: raiz.colorDeResultado
                onCicloElegido: (fila) => {
                    ventanaHistorial.mensaje = ""
                    ventanaHistorial.seleccion = fila
                    raiz.historial?.cargarGrafica(fila.id)
                }
                onMarcaAlternada: (id) => raiz.historial?.alternarSeleccion(id)
                onTodasAlternadas: (marcar) => raiz.historial?.seleccionarTodos(marcar)
                AvisoLista { anchors.verticalCenterOffset: raiz.m(28) }
            }
            NotaTruncado {
                id: notaHistorial
                anchors.bottom: barraAcciones.top
                anchors.bottomMargin: raiz.m(12)
            }

            // Acciones sobre los ciclos marcados
            Item {
                id: barraAcciones
                objectName: "barraAccionesHistorial"
                anchors.bottom: parent.bottom
                width: parent.width
                height: raiz.m(64)
                readonly property int cuenta: ventanaHistorial.marcados.length
                Text {
                    objectName: "cuentaMarcados"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: barraAcciones.cuenta > 0
                    text: barraAcciones.cuenta + " " + I18n.t("menu.seleccionados", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                Row {
                    anchors.right: parent.right
                    spacing: raiz.m(16)
                    BotonPildora {
                        objectName: "botonEnviarMarcados"
                        escala: raiz.escala
                        texto: ventanaHistorial.textoEnviar
                        habilitado: barraAcciones.cuenta > 0 && !ventanaHistorial.ocupado
                                    && ventanaHistorial.correoListo
                        onPulsado: ventanaHistorial.pedirDestino(ventanaHistorial.marcados)
                    }
                    BotonPildora {
                        objectName: "botonImprimirMarcados"
                        escala: raiz.escala
                        primario: true
                        texto: I18n.t("menu.imprimir", I18n.lang)
                        habilitado: barraAcciones.cuenta > 0 && !ventanaHistorial.ocupado
                        onPulsado: ventanaHistorial.imprimir(ventanaHistorial.marcados)
                    }
                }
            }
        }

        // ---------- ciclo abierto: sus acciones, datos y gráfica ----------
        Item {
            anchors.fill: parent
            visible: ventanaHistorial.seleccion !== null
            BotonPildora {
                id: volverHistorial
                objectName: "botonVolverHistorial"
                escala: raiz.escala
                texto: "‹  " + I18n.t("menu.volver", I18n.lang)
                onPulsado: ventanaHistorial.volverAlListado()
            }
            Row {
                anchors.right: parent.right
                spacing: raiz.m(16)
                BotonPildora {
                    objectName: "botonEnviarCiclo"
                    escala: raiz.escala
                    texto: ventanaHistorial.textoEnviar
                    habilitado: !ventanaHistorial.ocupado && ventanaHistorial.correoListo
                    onPulsado: ventanaHistorial.pedirDestino([ventanaHistorial.seleccion.id])
                }
                BotonPildora {
                    objectName: "botonImprimirCiclo"
                    escala: raiz.escala
                    primario: true
                    texto: I18n.t("menu.imprimir", I18n.lang)
                    habilitado: !ventanaHistorial.ocupado
                    onPulsado: ventanaHistorial.imprimir([ventanaHistorial.seleccion.id])
                }
            }
            DetalleCiclo {
                objectName: "detalleCicloHistorial"
                anchors.top: volverHistorial.bottom
                anchors.topMargin: raiz.m(24)
                anchors.bottom: parent.bottom
                anchors.bottomMargin: avisoHistorial.visible ? avisoHistorial.height + raiz.m(16) : 0
                width: parent.width
                escala: raiz.escala
                readonly property var c: ventanaHistorial.seleccion ?? ({})
                fecha: raiz.dato(c.fecha)
                hora: raiz.dato(c.hora)
                programa: raiz.dato(c.programa)
                programaNombre: raiz.dato(c.programa_nombre)
                resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
                resultadoDetalle: c.resultado_detalle ?? ""
                colorResultado: raiz.colorDeResultado(c.resultado ?? "")
                noConforme: c.no_conforme === true   // P4 (D-14.4)
                operador: raiz.dato(c.operador)
                datosGrafica: raiz.historial?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
                fasesGrafica: raiz.historial?.fasesGrafica ?? []
                graficaDisponible: raiz.historial?.graficaDisponible ?? false
                onCerrarPulsado: ventanaHistorial.cerrar()
            }
        }

        AvisoAccion {
            id: avisoHistorial
            objectName: "avisoAccionHistorial"
            escala: raiz.escala
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: ventanaHistorial.seleccion === null ? raiz.m(84) : 0
            trabajando: ventanaHistorial.accionEnCurso !== ""
            error: !trabajando && !ventanaHistorial.mensajeExito
            texto: ventanaHistorial.eligiendoDestino ? ""
                 : ventanaHistorial.accionEnCurso === "imprimir" ? I18n.t("menu.imprimiendo", I18n.lang)
                 : ventanaHistorial.accionEnCurso === "enviar" ? I18n.t("menu.enviando", I18n.lang)
                 : ventanaHistorial.mensaje
            onCerrado: ventanaHistorial.mensaje = ""
        }

        SelectorDestino {
            objectName: "selectorDestino"
            anchors.fill: parent
            visible: ventanaHistorial.eligiendoDestino
            escala: raiz.escala
            destinos: raiz.acciones?.destinos ?? []
            teclado: raiz.teclado
            onElegido: (correo) => ventanaHistorial.enviar(correo)
            onCancelado: ventanaHistorial.eligiendoDestino = false
        }
    }

    // Reportes, con un periodo de calendario común a sus pestañas:
    // - Resumen: totales por resultado, por programa y causas de fallo; se imprime
    //   en la térmica o se envía por correo como PDF.
    // - Consolidado: un solo PDF por correo con el resumen, el índice y las
    //   páginas de cada ciclo del periodo (gráfica con consignas); sin térmica.
    // - D8-5.6: tocar una causa de fallo del Resumen despliega los ciclos del
    //   periodo con ese fallo (número, fecha y hora, programa, operador),
    //   paginados; tocar un ciclo abre su detalle con imprimir y enviar, como
    //   desde el Historial (la curva la pide el puente del Historial).
    // Alarmas se agrega después.
    VentanaFlotante {
        id: ventanaReportes
        objectName: "ventanaReportes"
        escala: raiz.escala
        altoTarjeta: 1500
        titulo: seleccionFallo ? I18n.t("menu.ciclo_titulo", I18n.lang) + " " + seleccionFallo.numero
                               : I18n.t("reportes.titulo", I18n.lang)
        property string periodo: "dia"
        // D8-5.6: ciclo abierto desde el listado de un fallo (null = listado o resumen)
        property var seleccionFallo: null
        // ciclos por enviar mientras se elige el destino (el abierto); vacío = el resumen
        property var idsCorreo: []
        readonly property bool enFallo: (raiz.reporte?.causaFallo ?? "") !== ""
        property string pestana: "resumen"     // "resumen" / "consolidado"
        property string accionEnCurso: ""      // "imprimir" / "enviar" mientras trabaja
        property string mensaje: ""
        property bool mensajeExito: true
        property bool eligiendoDestino: false
        readonly property bool ocupado: raiz.acciones?.ocupado ?? false
        readonly property bool correoListo: raiz.acciones?.correoConfigurado ?? false
        readonly property bool hayCiclos: raiz.reporte?.hayCiclos ?? false

        // al abrir: hoy; los filtros conservan la fecha que se está viendo
        function elegir(p) { periodo = p; mensaje = ""; raiz.reporte?.cambiarPeriodo(p) }
        function abrirFallo(causa) { mensaje = ""; seleccionFallo = null; raiz.reporte?.abrirFallo(causa) }
        function cerrarFallo() {
            mensaje = ""
            seleccionFallo = null
            raiz.historial?.limpiarGrafica()
            raiz.reporte?.cerrarFallo()
        }
        function abrirCicloFallo(fila) {
            mensaje = ""
            seleccionFallo = fila
            raiz.historial?.cargarGrafica(fila.id)
        }
        function volverAlFallo() { mensaje = ""; seleccionFallo = null; raiz.historial?.limpiarGrafica() }
        function imprimirCiclo(ids) {
            mensaje = ""
            accionEnCurso = "imprimir"
            raiz.acciones?.imprimir(ids)
        }
        function pedirDestinoCiclo(ids) {
            mensaje = ""
            idsCorreo = ids
            eligiendoDestino = true
        }
        function imprimir() {
            mensaje = ""
            accionEnCurso = "imprimir"
            raiz.acciones?.imprimirResumen(raiz.reporte.periodo, raiz.reporte.fecha)
        }
        function enviar(correo) {
            eligiendoDestino = false
            accionEnCurso = "enviar"
            if (idsCorreo.length > 0) {
                const ids = idsCorreo
                idsCorreo = []
                raiz.acciones?.enviarCorreo(ids, correo)
            } else if (pestana === "consolidado")
                raiz.acciones?.enviarConsolidado(raiz.reporte.periodo, raiz.reporte.fecha, correo)
            else
                raiz.acciones?.enviarResumen(raiz.reporte.periodo, raiz.reporte.fecha, correo)
        }
        onMostrada: {
            pestana = "resumen"
            seleccionFallo = null
            idsCorreo = []
            eligiendoDestino = false
            raiz.acciones?.actualizarCorreo()
            periodo = "dia"
            mensaje = ""
            raiz.reporte?.consultar("dia")
        }
        onCerrada: {
            eligiendoDestino = false
            mensaje = ""
            idsCorreo = []
            raiz.teclado?.cerrar()
            seleccionFallo = null
            raiz.historial?.limpiarGrafica()
            raiz.reporte?.cerrarFallo()
        }

        Connections {
            target: ventanaReportes.visible ? raiz.acciones : null
            function onAccionTerminada(exito, texto) {
                ventanaReportes.accionEnCurso = ""
                ventanaReportes.mensajeExito = exito
                ventanaReportes.mensaje = texto
            }
        }

        // Pestañas
        Row {
            id: pestanas
            visible: !ventanaReportes.enFallo
            spacing: raiz.m(40)
            Repeater {
                model: [["resumen", "pestana_resumen"], ["consolidado", "pestana_consolidado"]]
                Item {
                    id: pestana
                    required property var modelData
                    readonly property bool activa: ventanaReportes.pestana === modelData[0]
                    objectName: "pestana_" + modelData[0]
                    width: textoPestana.implicitWidth + raiz.m(16); height: raiz.m(56)
                    Text {
                        id: textoPestana
                        anchors.centerIn: parent
                        text: I18n.t("reportes." + (pestana.modelData[1]), I18n.lang)
                        color: pestana.activa ? Colores.accionPrimarioTexto : Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.weight: pestana.activa ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(26)
                    }
                    Rectangle {
                        visible: pestana.activa
                        anchors.bottom: parent.bottom
                        width: parent.width; height: raiz.m(4); radius: height / 2
                        color: Colores.accionPrimario
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !ventanaReportes.ocupado
                        onClicked: { ventanaReportes.mensaje = ""; ventanaReportes.pestana = pestana.modelData[0] }
                    }
                }
            }
        }

        SelectorPeriodo {
            id: selectorReportes
            visible: !ventanaReportes.enFallo
            anchors.top: pestanas.bottom
            anchors.topMargin: raiz.m(24)
            width: parent.width
            escala: raiz.escala
            periodo: ventanaReportes.periodo
            rotulo: raiz.reporte?.rotuloPeriodo ?? ""
            esActual: raiz.reporte?.esPeriodoActual ?? true
            onElegido: (p) => ventanaReportes.elegir(p)
            onMovido: (pasos) => { ventanaReportes.mensaje = ""; raiz.reporte?.moverPeriodo(pasos) }
        }

        Item {
            visible: !ventanaReportes.enFallo
            anchors.top: selectorReportes.bottom
            anchors.topMargin: raiz.m(28)
            anchors.bottom: accionesReportes.top
            anchors.bottomMargin: raiz.m(16) + (avisoReportes.visible ? avisoReportes.height + raiz.m(16) : 0)
            width: parent.width
            ResumenPeriodo {
                objectName: "resumenPeriodo"
                anchors.fill: parent
                visible: ventanaReportes.hayCiclos && ventanaReportes.pestana === "resumen"
                escala: raiz.escala
                datos: raiz.reporte?.datos ?? ({ total: "0", totales: [], por_programa: [], causas: [] })
                onCausaElegida: (causa) => ventanaReportes.abrirFallo(causa)
            }
            Text {
                objectName: "avisoReporte"
                anchors.centerIn: parent
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: text !== ""
                text: (raiz.reporte?.cargando ?? false) && !ventanaReportes.hayCiclos ? I18n.t("menu.cargando", I18n.lang)
                    : (raiz.reporte?.sinConexion ?? false) ? I18n.t("menu.sin_conexion", I18n.lang)
                    : !ventanaReportes.hayCiclos ? I18n.t("reportes.sin_ciclos", I18n.lang)
                    : ""
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(26)
            }
            // Consolidado: cuántos ciclos entran y qué se enviará
            Column {
                objectName: "consolidado"
                visible: ventanaReportes.hayCiclos && ventanaReportes.pestana === "consolidado"
                width: parent.width
                spacing: raiz.m(20)
                Row {
                    spacing: raiz.m(16)
                    Text {
                        id: cuentaConsolidado
                        objectName: "cuentaConsolidado"
                        text: raiz.reporte?.datos?.total ?? "0"
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(64)
                    }
                    Text {
                        anchors.baseline: cuentaConsolidado.baseline
                        text: I18n.t("reportes.consolidado_cuenta", I18n.lang)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(28)
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("reportes.consolidado_desc", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(24)
                    lineHeight: 1.2
                }
            }
        }

        AvisoAccion {
            id: avisoReportes
            objectName: "avisoAccionReportes"
            z: 2     // sobre el listado y el ciclo abierto de un fallo (D8-5.6)
            escala: raiz.escala
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: ventanaReportes.enFallo ? parent.bottom : accionesReportes.top
            anchors.bottomMargin: ventanaReportes.enFallo ? 0 : raiz.m(16)
            trabajando: ventanaReportes.accionEnCurso !== ""
            error: !trabajando && !ventanaReportes.mensajeExito
            // el consolidado tarda: muestra su avance (AccionesCiclos.progreso)
            texto: ventanaReportes.eligiendoDestino ? ""
                 : ventanaReportes.accionEnCurso !== "" && (raiz.acciones?.progreso ?? "") !== ""
                   ? raiz.acciones.progreso
                 : ventanaReportes.accionEnCurso === "imprimir" ? I18n.t("menu.imprimiendo", I18n.lang)
                 : ventanaReportes.accionEnCurso === "enviar" ? I18n.t("menu.enviando", I18n.lang)
                 : ventanaReportes.mensaje
            onCerrado: ventanaReportes.mensaje = ""
        }

        // ---------- D8-5.6: ciclos con el fallo elegido, paginados ----------
        Item {
            objectName: "listadoFallo"
            anchors.fill: parent
            visible: ventanaReportes.enFallo && ventanaReportes.seleccionFallo === null
            BotonPildora {
                id: volverResumen
                objectName: "botonVolverResumen"
                escala: raiz.escala
                texto: "‹  " + I18n.t("reportes.volver_resumen", I18n.lang)
                onPulsado: ventanaReportes.cerrarFallo()
            }
            Text {
                id: tituloFallo
                objectName: "tituloFallo"
                anchors.top: volverResumen.bottom
                anchors.topMargin: raiz.m(24)
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("reportes.ciclos_con_fallo", I18n.lang)
                      .replace("{causa}", raiz.reporte?.causaFallo ?? "")
                      .replace("{n}", String(raiz.reporte?.totalFallo ?? 0))
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(28)
            }
            ListaCiclos {
                objectName: "listaFallo"
                anchors.top: tituloFallo.bottom
                anchors.topMargin: raiz.m(16)
                anchors.bottom: paginacionFallo.top
                anchors.bottomMargin: raiz.m(16)
                width: parent.width
                escala: raiz.escala
                ciclos: raiz.reporte?.ciclosFallo ?? []
                seleccionable: true
                conOperador: true
                onCicloElegido: (fila) => ventanaReportes.abrirCicloFallo(fila)
                Text {
                    objectName: "avisoListaFallo"
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: raiz.m(28)
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    visible: text !== ""
                    text: (raiz.reporte?.cargandoFallo ?? false) ? I18n.t("menu.cargando", I18n.lang)
                        : (raiz.reporte?.sinConexionFallo ?? false) ? I18n.t("menu.sin_conexion", I18n.lang)
                        : (raiz.reporte?.ciclosFallo?.length ?? 0) === 0 ? I18n.t("reportes.sin_ciclos_fallo", I18n.lang)
                        : ""
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(26)
                }
            }
            // paginación: solo si hay más de una página
            Item {
                id: paginacionFallo
                objectName: "paginacionFallo"
                anchors.bottom: parent.bottom
                width: parent.width
                height: visible ? raiz.m(64) : 0
                visible: (raiz.reporte?.paginasFallo ?? 1) > 1
                BotonPildora {
                    objectName: "botonPaginaAnterior"
                    anchors.left: parent.left
                    escala: raiz.escala
                    texto: "‹  " + I18n.t("reportes.pagina_anterior", I18n.lang)
                    habilitado: (raiz.reporte?.paginaFallo ?? 1) > 1 && !(raiz.reporte?.cargandoFallo ?? false)
                    onPulsado: raiz.reporte?.moverPaginaFallo(-1)
                }
                Text {
                    objectName: "textoPaginaFallo"
                    anchors.centerIn: parent
                    text: I18n.t("reportes.pagina", I18n.lang)
                          .replace("{n}", String(raiz.reporte?.paginaFallo ?? 1))
                          .replace("{total}", String(raiz.reporte?.paginasFallo ?? 1))
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
                    habilitado: (raiz.reporte?.paginaFallo ?? 1) < (raiz.reporte?.paginasFallo ?? 1)
                                && !(raiz.reporte?.cargandoFallo ?? false)
                    onPulsado: raiz.reporte?.moverPaginaFallo(1)
                }
            }
        }

        // ---------- D8-5.6: ciclo abierto desde el listado del fallo ----------
        Item {
            anchors.fill: parent
            visible: ventanaReportes.seleccionFallo !== null
            BotonPildora {
                id: volverFallo
                objectName: "botonVolverFallo"
                escala: raiz.escala
                texto: "‹  " + I18n.t("menu.volver", I18n.lang)
                onPulsado: ventanaReportes.volverAlFallo()
            }
            Row {
                anchors.right: parent.right
                spacing: raiz.m(16)
                BotonPildora {
                    objectName: "botonEnviarCicloFallo"
                    escala: raiz.escala
                    texto: ventanaReportes.correoListo ? I18n.t("menu.enviar_correo", I18n.lang)
                                                       : I18n.t("menu.correo_no_configurado", I18n.lang)
                    habilitado: !ventanaReportes.ocupado && ventanaReportes.correoListo
                    onPulsado: ventanaReportes.pedirDestinoCiclo([ventanaReportes.seleccionFallo.id])
                }
                BotonPildora {
                    objectName: "botonImprimirCicloFallo"
                    escala: raiz.escala
                    primario: true
                    texto: I18n.t("menu.imprimir", I18n.lang)
                    habilitado: !ventanaReportes.ocupado
                    onPulsado: ventanaReportes.imprimirCiclo([ventanaReportes.seleccionFallo.id])
                }
            }
            DetalleCiclo {
                objectName: "detalleCicloFallo"
                anchors.top: volverFallo.bottom
                anchors.topMargin: raiz.m(24)
                anchors.bottom: parent.bottom
                anchors.bottomMargin: avisoReportes.visible ? avisoReportes.height + raiz.m(16) : 0
                width: parent.width
                escala: raiz.escala
                readonly property var c: ventanaReportes.seleccionFallo ?? ({})
                fecha: raiz.dato(c.fecha)
                hora: raiz.dato(c.hora)
                programa: raiz.dato(c.programa)
                programaNombre: raiz.dato(c.programa_nombre)
                resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
                resultadoDetalle: c.resultado_detalle ?? ""
                colorResultado: raiz.colorDeResultado(c.resultado ?? "")
                noConforme: c.no_conforme === true   // P4 (D-14.4)
                operador: raiz.dato(c.operador)
                datosGrafica: raiz.historial?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
                fasesGrafica: raiz.historial?.fasesGrafica ?? []
                graficaDisponible: raiz.historial?.graficaDisponible ?? false
                onCerrarPulsado: ventanaReportes.cerrar()
            }
        }

        Row {
            id: accionesReportes
            visible: !ventanaReportes.enFallo
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            spacing: raiz.m(16)
            BotonPildora {
                objectName: "botonEnviarResumen"
                escala: raiz.escala
                texto: ventanaReportes.correoListo ? I18n.t("menu.enviar_correo", I18n.lang)
                                                   : I18n.t("menu.correo_no_configurado", I18n.lang)
                habilitado: !ventanaReportes.ocupado && ventanaReportes.correoListo
                            && !(raiz.reporte?.sinConexion ?? true)
                            && (ventanaReportes.pestana === "resumen" || ventanaReportes.hayCiclos)
                onPulsado: { ventanaReportes.mensaje = ""; ventanaReportes.eligiendoDestino = true }
            }
            BotonPildora {
                objectName: "botonImprimirResumen"
                visible: ventanaReportes.pestana === "resumen"   // el consolidado es solo por correo
                escala: raiz.escala
                primario: true
                texto: I18n.t("menu.imprimir", I18n.lang)
                habilitado: !ventanaReportes.ocupado && !(raiz.reporte?.sinConexion ?? true)
                onPulsado: ventanaReportes.imprimir()
            }
        }

        SelectorDestino {
            objectName: "selectorDestinoReportes"
            anchors.fill: parent
            visible: ventanaReportes.eligiendoDestino
            escala: raiz.escala
            destinos: raiz.acciones?.destinos ?? []
            teclado: raiz.teclado
            onElegido: (correo) => ventanaReportes.enviar(correo)
            onCancelado: ventanaReportes.eligiendoDestino = false
        }
    }

    // ======================= paneles de la campana y de información =======================
    // Los mismos de PantallaPreciclo.qml (PROVISIONALES, sin diseño del diseñador)
    PanelNotificaciones {
        id: panelNotificaciones
        objectName: "panelNotificacionesMenu"
        titulo: I18n.t("notificaciones.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        rotuloAlertas: I18n.t("notificaciones.alertas_avisos", I18n.lang)
        textoSinAlarmas: I18n.t("ciclo.sin_alarmas", I18n.lang)
        alarmas: raiz.puente?.alarms ?? null
        puente: raiz.puente
        comandosSistema: raiz.comandosSistema
    }
    PanelEquipo {
        comandosSistema: raiz.comandosSistema
        id: panelEquipo
        objectName: "panelEquipoMenu"
        titulo: I18n.t("equipo.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        filas: raiz.infoEquipo?.filas ?? []
        sinLectura: I18n.t("sistema.sin_lectura", I18n.lang)
    }
}
