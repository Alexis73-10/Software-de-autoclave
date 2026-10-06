pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import Tema
import "../Componentes"

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
    property QtObject historial: null   // CiclosHistorial: listados de Ciclos hoy e Historial
    property QtObject acciones: null    // AccionesCiclos: imprimir / enviar por correo (Historial)
    property QtObject teclado: null     // PanelTeclado: correo de destino escrito a mano
    property var textosJson: ({})
    // Casa de la barra: activa cuando hay una pantalla a la que regresar (la de
    // preciclo o la de ciclo en curso, desde cuyo engranaje se abrió el menú)
    property bool inicioActivo: false

    // ---- acciones: las resuelve quien usa la pantalla (Main.qml) ----
    signal iniciarSesionPulsado()       // abre el login QML (Main.qml)
    signal campanaPulsada()
    signal salirPulsado()
    signal inicioPulsado()
    signal historialPulsado()
    signal reportesPulsado()
    signal informacionPulsado()
    signal ciclosTotalesPulsado()
    signal ciclosHoyPulsado()
    signal mantenimientoPulsado()
    signal ultimoCicloPulsado()

    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }

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
        return clave ? tx("menu", "resultado_" + clave.toLowerCase()) : sinDato
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
    readonly property string textoResultado: textoDeResultado(claveResultado)
    readonly property color colorResultado: colorDeResultado(claveResultado)

    // Abre una ventana flotante por nombre ("ultimo_ciclo", "mantenimiento",
    // "ciclos_hoy", "historial"), como si se tocara su tarjeta (arnés y capturas)
    function abrirVentana(nombre) {
        if (nombre === "ultimo_ciclo") ventanaUltimoCiclo.abrir()
        else if (nombre === "mantenimiento") ventanaMantenimiento.abrir()
        else if (nombre === "ciclos_hoy") ventanaCiclosHoy.abrir()
        else if (nombre === "historial") ventanaHistorial.abrir()
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
        textosJson: raiz.textosJson
        conteoAlarmas: raiz.puente?.alarms?.count ?? -1
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
            text: raiz.tx("menu", "sin_conexion")
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
    Titulo { objectName: "tituloMenu"; cx: 596.5; bl: 390; text: raiz.tx("menu", "titulo") }

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
        titulo: raiz.tx("acciones", "iniciar_sesion")
        descripcion: raiz.tx("menu", "iniciar_sesion_desc")
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
        titulo: raiz.tx("modulos", "historial")
        descripcion: raiz.tx("menu", "historial_desc")
        // variante color: glifo morado con su propio aro gris, como el v3
        icono: raiz.iconosColor + "historial.svg"
        iconoTenido: false
        iconoIncluyeAro: true
        onPulsada: { raiz.historialPulsado(); ventanaHistorial.abrir() }
    }
    // D-13: Reportes visible y deshabilitada. TODO(MP-04): habilitar cuando exista su pantalla.
    Fila2 {
        objectName: "tarjetaReportes"
        x: raiz.m(54)
        enabled: false
        titulo: raiz.tx("modulos", "reportes")
        descripcion: raiz.tx("menu", "reportes_desc")
        icono: raiz.iconosMono + "reportes.svg"
        tamIcono: 85
        colorAcento: Colores.menuNaranja
        onPulsada: raiz.reportesPulsado()
    }
    Fila2 {
        objectName: "tarjetaInformacion"
        x: raiz.m(422)
        // Abre la información del equipo, el mismo panel que el recuadro de modelo
        // y serie de PantallaPreciclo.qml (decisión de Cristian, 2026-10-02)
        titulo: raiz.tx("modulos", "informacion")
        descripcion: raiz.tx("menu", "informacion_desc")
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
    // Informativa, sin flecha ni acción. TODO(MP-11): "tiempo adicional de secado"
    // es un parámetro nuevo por programa que aún no existe; hasta su plan propio
    // muestra "—" y no lee ningún parámetro.
    Fila2 {
        objectName: "tarjetaSecado"
        x: raiz.m(790)
        interactiva: false
        flechaVisible: false
        titulo: raiz.tx("menu", "secado_titulo")
        descripcion: raiz.tx("menu", "secado_desc")
        valor: raiz.dato(raiz.resumen?.tiempoSecado)
        icono: raiz.iconosMono + "sensor_tiempo_secado.svg"
        tamIcono: 76
        colorAcento: Colores.menuNaranja
        aroAcento: true
    }

    // ======================= resumen del sistema =======================
    Item {
        id: bloqueResumen
        width: parent.width
        height: parent.height
        y: raiz.m(raiz._desfaseResumen)

        Titulo { objectName: "tituloResumen"; cx: 598; bl: 1244; text: raiz.tx("menu", "resumen") }

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
            rotulo: raiz.tx("menu", "ciclos_totales")
            valor: raiz.dato(raiz.resumen?.ciclosTotales)   // TODO(MP-06a): último numero_ciclo
            subrotulo: raiz.tx("menu", "realizados")
            onPulsada: raiz.ciclosTotalesPulsado()
        }
        Resumen {
            objectName: "resumenMantenimiento"
            x: raiz.m(300); width: raiz.m(293)
            icono: raiz.iconosMono + "mantenimiento.svg"
            tamIcono: 73
            colorAcento: Colores.menuNaranja
            rotulo: raiz.tx("menu", "proximo_mantenimiento")
            valor: raiz.dato(raiz.resumen?.proximoMantenimiento)   // MP-06b: sin fuente
            onPulsada: { raiz.mantenimientoPulsado(); ventanaMantenimiento.abrir() }
        }
        // Abre el listado de los ciclos terminados hoy; tocar uno muestra su gráfica y datos
        Resumen {
            objectName: "resumenCiclosHoy"
            x: raiz.m(609); width: raiz.m(206)
            icono: raiz.iconosMono + "reloj.svg"
            iconoIncluyeAro: true
            colorAcento: Colores.menuMorado
            rotulo: raiz.tx("menu", "ciclos_hoy")
            valor: raiz.dato(raiz.resumen?.ciclosHoy)
            subrotulo: raiz.tx("menu", "realizados")
            onPulsada: { raiz.ciclosHoyPulsado(); ventanaCiclosHoy.abrir() }
        }
        Resumen {
            objectName: "resumenUltimoCiclo"
            x: raiz.m(831); width: raiz.m(308)
            icono: raiz.iconosMono + "reproducir.svg"
            iconoIncluyeAro: true
            colorAcento: Colores.menuAzul
            rotulo: raiz.tx("menu", "ultimo_ciclo")
            onPulsada: { raiz.ultimoCicloPulsado(); ventanaUltimoCiclo.abrir() }
            DetalleUltimoCiclo {
                escala: raiz.escala
                fecha: raiz.dato(raiz.resumen?.ultimoFecha)
                hora: raiz.dato(raiz.resumen?.ultimoHora)
                rotuloPrograma: raiz.tx("menu", "programa")
                programa: raiz.dato(raiz.resumen?.ultimoPrograma)
                rotuloResultado: raiz.tx("menu", "resultado")
                resultado: raiz.textoResultado
                colorResultado: raiz.colorResultado
            }
        }
    }

    // ======================= barra inferior (anclada abajo) =======================
    BarraInferiorMenu {
        objectName: "barraInferiorMenu"
        x: raiz.m(34)
        y: parent.height - raiz.m(raiz.altoMockup - 1746)
        escala: raiz.escala
        version: raiz.tx("app", "version")
        salirHabilitado: false   // D-12, TODO(MP-03): sin canal de sesión con el login PySide
        inicioActivo: raiz.inicioActivo
        onSalirPulsado: raiz.salirPulsado()
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
            elide: Text.ElideRight
            text: parent.valor
            color: parent.colorValor
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(28)
        }
        Text {
            visible: text !== ""
            width: parent.width
            elide: Text.ElideRight
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
        titulo: raiz.tx("menu", "ventana_ultimo_ciclo")
        // la curva se pide solo al abrir (GET /cycle/history/{id}/graph)
        onMostrada: raiz.resumen?.cargarGraficaUltimo()

        DetalleCiclo {
            objectName: "detalleUltimoCiclo"
            anchors.fill: parent
            escala: raiz.escala
            textosJson: raiz.textosJson
            fecha: raiz.dato(raiz.resumen?.ultimoFecha)
            hora: raiz.dato(raiz.resumen?.ultimoHora)
            programa: raiz.dato(raiz.resumen?.ultimoPrograma)
            programaNombre: raiz.dato(raiz.resumen?.ultimoProgramaNombre)
            resultadoTexto: raiz.textoResultado
            resultadoDetalle: raiz.resumen?.ultimoResultadoDetalle ?? ""
            colorResultado: raiz.colorResultado
            // TODO(MP-14b): el operador que inició el ciclo no se guarda (D-24)
            operador: raiz.dato(raiz.resumen?.ultimoOperador)
            datosGrafica: raiz.resumen?.datosGraficaUltimo ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
            fasesGrafica: raiz.resumen?.fasesGraficaUltimo ?? []
            graficaDisponible: raiz.resumen?.graficaUltimoDisponible ?? false
            onCerrarPulsado: ventanaUltimoCiclo.cerrar()
        }
    }

    // Sin fuente de mantenimiento en el sistema (MP-14c, B-03): todo "—"
    VentanaFlotante {
        id: ventanaMantenimiento
        objectName: "ventanaMantenimiento"
        escala: raiz.escala
        altoTarjeta: 380
        titulo: raiz.tx("menu", "ventana_mantenimiento")
        Column {
            width: parent.width
            spacing: raiz.m(28)
            Campo { width: parent.width; rotulo: raiz.tx("menu", "ultimo_mantenimiento"); valor: raiz.sinDato }
            Campo { width: parent.width; rotulo: raiz.tx("menu", "ciclos_restantes"); valor: raiz.sinDato }
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
              ? raiz.tx("menu", "cargando")
              : (raiz.historial?.sinConexion ?? false) ? raiz.tx("menu", "sin_conexion")
              : (raiz.historial?.ciclos?.length ?? 0) === 0 ? raiz.tx("menu", "sin_ciclos")
              : ""
        visible: text !== ""
    }
    component NotaTruncado: Text {
        visible: raiz.historial?.truncado ?? false
        text: raiz.tx("menu", "lista_truncada")
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
        titulo: seleccion ? raiz.tx("menu", "ciclo_titulo") + " " + seleccion.numero
                          : raiz.tx("menu", "ventana_ciclos_hoy")
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
                textosJson: raiz.textosJson
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
                    text: "\u2039  " + raiz.tx("menu", "volver")
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
                textosJson: raiz.textosJson
                readonly property var c: ventanaCiclosHoy.seleccion ?? ({})
                fecha: raiz.dato(c.fecha)
                hora: raiz.dato(c.hora)
                programa: raiz.dato(c.programa)
                programaNombre: raiz.dato(c.programa_nombre)
                resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
                resultadoDetalle: c.resultado_detalle ?? ""
                colorResultado: raiz.colorDeResultado(c.resultado ?? "")
                // TODO(MP-14b): el operador que inició el ciclo no se guarda (D-24)
                operador: raiz.dato(c.operador)
                datosGrafica: raiz.historial?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
                fasesGrafica: raiz.historial?.fasesGrafica ?? []
                graficaDisponible: raiz.historial?.graficaDisponible ?? false
                onCerrarPulsado: ventanaCiclosHoy.cerrar()
            }
        }
    }

    // Botón de texto en píldora de la ventana de Historial.
    // DISEÑO PROVISIONAL: sin diseño del diseñador.
    component BotonVentana: Item {
        id: boton
        property string texto: ""
        property bool primario: false
        property bool habilitado: true
        signal pulsado()
        width: Math.max(raiz.m(220), textoBoton.implicitWidth + raiz.m(56))
        height: raiz.m(64)
        opacity: habilitado ? 1 : 0.4
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: boton.primario ? Colores.accionPrimario : Colores.fondoSutil
            border.width: boton.primario ? 0 : raiz.m(2)
            border.color: Colores.bordeDivisor
            opacity: zonaBoton.pressed ? 0.8 : 1
        }
        Text {
            id: textoBoton
            anchors.centerIn: parent
            text: boton.texto
            color: boton.primario ? "white" : Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(22)
        }
        MouseArea {
            id: zonaBoton
            anchors.fill: parent
            enabled: boton.habilitado
            onClicked: boton.pulsado()
        }
    }

    // Flecha del periodo del Historial: anterior (atras) o siguiente
    component FlechaPeriodo: Item {
        id: flecha
        property bool atras: true
        property bool habilitada: true
        signal pulsada()
        width: raiz.m(96)
        opacity: habilitada ? 1 : 0.25
        Rectangle {
            anchors.centerIn: parent
            width: raiz.m(72); height: width; radius: width / 2
            color: Colores.fondoSutil
            border.width: raiz.m(2); border.color: Colores.bordeDivisor
        }
        // tinta de chevron_derecha.svg = [12.8, 4.3, 35.2, 43.8]
        Image {
            readonly property real _k: raiz.m(26) / (43.8 - 4.3)
            width: 48 * _k; height: width
            anchors.centerIn: parent
            rotation: flecha.atras ? 180 : 0
            source: raiz.iconosMono + "chevron_derecha.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; enabled: flecha.habilitada; onClicked: flecha.pulsada() }
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
        readonly property string textoEnviar: correoListo ? raiz.tx("menu", "enviar_correo")
                                                          : raiz.tx("menu", "correo_no_configurado")
        titulo: seleccion ? raiz.tx("menu", "ciclo_titulo") + " " + seleccion.numero
                          : raiz.tx("menu", "ventana_historial")

        function elegir(p) { periodo = p; seleccion = null; mensaje = ""; raiz.historial?.consultarHistorial(p) }
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
        function cancelarDestino() { raiz.teclado?.cerrar(); eligiendoDestino = false }
        function enviar(correo) {
            eligiendoDestino = false
            accionEnCurso = "enviar"
            raiz.acciones?.enviarCorreo(idsCorreo, correo)
        }
        onMostrada: {
            seleccion = null
            eligiendoDestino = false
            raiz.acciones?.actualizarCorreo()   // config/correo.json se edita a mano por ahora
            elegir("dia")
        }
        onCerrada: {
            seleccion = null
            eligiendoDestino = false
            mensaje = ""
            raiz.teclado?.cerrar()
            raiz.historial?.limpiarGrafica()
        }

        Connections {
            target: raiz.acciones
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

            Row {
                id: filtros
                spacing: raiz.m(16)
                Repeater {
                    model: [["dia", "filtro_diario"], ["semana", "filtro_semanal"], ["mes", "filtro_mensual"]]
                    Rectangle {
                        id: filtro
                        required property var modelData
                        readonly property bool elegido: ventanaHistorial.periodo === modelData[0]
                        objectName: "filtro_" + modelData[0]
                        width: raiz.m(200); height: raiz.m(60)
                        radius: height / 2
                        color: elegido ? Colores.accionPrimario : Colores.fondoSutil
                        border.width: elegido ? 0 : raiz.m(2)
                        border.color: Colores.bordeDivisor
                        Text {
                            anchors.centerIn: parent
                            text: raiz.tx("menu", filtro.modelData[1])
                            color: filtro.elegido ? "white" : Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: raiz.fuente(22)
                        }
                        MouseArea { anchors.fill: parent; onClicked: ventanaHistorial.elegir(filtro.modelData[0]) }
                    }
                }
            }

            // Periodo entre flechas; la siguiente se apaga en el periodo actual
            Item {
                id: navegacion
                anchors.top: filtros.bottom
                anchors.topMargin: raiz.m(20)
                width: parent.width
                height: raiz.m(72)
                FlechaPeriodo {
                    objectName: "flechaAnterior"
                    height: parent.height
                    onPulsada: ventanaHistorial.mover(-1)
                }
                Text {
                    objectName: "rotuloPeriodo"
                    anchors.centerIn: parent
                    width: parent.width - raiz.m(220)
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: raiz.historial?.rotuloPeriodo ?? ""
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(28)
                }
                FlechaPeriodo {
                    objectName: "flechaSiguiente"
                    anchors.right: parent.right
                    height: parent.height
                    atras: false
                    habilitada: !(raiz.historial?.esPeriodoActual ?? true)
                    onPulsada: ventanaHistorial.mover(1)
                }
            }

            ListaCiclos {
                objectName: "listaHistorial"
                anchors.top: navegacion.bottom
                anchors.topMargin: raiz.m(16)
                anchors.bottom: barraAcciones.top
                anchors.bottomMargin: raiz.m(16) + (notaHistorial.visible ? notaHistorial.height + raiz.m(8) : 0)
                width: parent.width
                escala: raiz.escala
                textosJson: raiz.textosJson
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
                    text: barraAcciones.cuenta + " " + raiz.tx("menu", "seleccionados")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                Row {
                    anchors.right: parent.right
                    spacing: raiz.m(16)
                    BotonVentana {
                        objectName: "botonEnviarMarcados"
                        texto: ventanaHistorial.textoEnviar
                        habilitado: barraAcciones.cuenta > 0 && !ventanaHistorial.ocupado
                                    && ventanaHistorial.correoListo
                        onPulsado: ventanaHistorial.pedirDestino(ventanaHistorial.marcados)
                    }
                    BotonVentana {
                        objectName: "botonImprimirMarcados"
                        primario: true
                        texto: raiz.tx("menu", "imprimir")
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
            BotonVentana {
                id: volverHistorial
                objectName: "botonVolverHistorial"
                texto: "‹  " + raiz.tx("menu", "volver")
                onPulsado: ventanaHistorial.volverAlListado()
            }
            Row {
                anchors.right: parent.right
                spacing: raiz.m(16)
                BotonVentana {
                    objectName: "botonEnviarCiclo"
                    texto: ventanaHistorial.textoEnviar
                    habilitado: !ventanaHistorial.ocupado && ventanaHistorial.correoListo
                    onPulsado: ventanaHistorial.pedirDestino([ventanaHistorial.seleccion.id])
                }
                BotonVentana {
                    objectName: "botonImprimirCiclo"
                    primario: true
                    texto: raiz.tx("menu", "imprimir")
                    habilitado: !ventanaHistorial.ocupado
                    onPulsado: ventanaHistorial.imprimir([ventanaHistorial.seleccion.id])
                }
            }
            DetalleCiclo {
                objectName: "detalleCicloHistorial"
                anchors.top: volverHistorial.bottom
                anchors.topMargin: raiz.m(24)
                anchors.bottom: parent.bottom
                anchors.bottomMargin: avisoAccion.visible ? avisoAccion.height + raiz.m(16) : 0
                width: parent.width
                escala: raiz.escala
                textosJson: raiz.textosJson
                readonly property var c: ventanaHistorial.seleccion ?? ({})
                fecha: raiz.dato(c.fecha)
                hora: raiz.dato(c.hora)
                programa: raiz.dato(c.programa)
                programaNombre: raiz.dato(c.programa_nombre)
                resultadoTexto: raiz.textoDeResultado(c.resultado ?? "")
                resultadoDetalle: c.resultado_detalle ?? ""
                colorResultado: raiz.colorDeResultado(c.resultado ?? "")
                // TODO(MP-14b): el operador que inició el ciclo no se guarda (D-24)
                operador: raiz.dato(c.operador)
                datosGrafica: raiz.historial?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
                fasesGrafica: raiz.historial?.fasesGrafica ?? []
                graficaDisponible: raiz.historial?.graficaDisponible ?? false
                onCerrarPulsado: ventanaHistorial.cerrar()
            }
        }

        // ---------- aviso de la acción: en curso o su resultado (tocarlo lo cierra) ----------
        Rectangle {
            id: avisoAccion
            objectName: "avisoAccionHistorial"
            readonly property bool trabajando: ventanaHistorial.accionEnCurso !== ""
            readonly property string texto: ventanaHistorial.accionEnCurso === "imprimir" ? raiz.tx("menu", "imprimiendo")
                                          : ventanaHistorial.accionEnCurso === "enviar" ? raiz.tx("menu", "enviando")
                                          : ventanaHistorial.mensaje
            readonly property bool error: !trabajando && !ventanaHistorial.mensajeExito
            visible: texto !== "" && !ventanaHistorial.eligiendoDestino
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: ventanaHistorial.seleccion === null ? raiz.m(84) : 0
            width: Math.min(parent.width, textoAvisoAccion.implicitWidth + raiz.m(64))
            height: textoAvisoAccion.height + raiz.m(32)
            radius: raiz.m(20)
            color: error ? Colores.peligroFondo : Colores.fondoTarjeta
            border.width: raiz.m(2)
            border.color: error ? Colores.peligroTexto : Colores.bordeDivisor
            Text {
                id: textoAvisoAccion
                objectName: "textoAvisoAccion"
                anchors.centerIn: parent
                width: Math.min(implicitWidth, avisoAccion.parent.width - raiz.m(64))
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                text: avisoAccion.texto
                color: avisoAccion.error ? Colores.peligroTexto
                     : avisoAccion.trabajando ? Colores.textoPrimario : Colores.menuVerdeTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(24)
            }
            MouseArea {
                anchors.fill: parent
                enabled: !avisoAccion.trabajando
                onClicked: ventanaHistorial.mensaje = ""
            }
        }

        // ---------- destino del correo: uno predeterminado u otro escrito a mano ----------
        Rectangle {
            id: selectorDestino
            objectName: "selectorDestino"
            anchors.fill: parent
            visible: ventanaHistorial.eligiendoDestino
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // no dejar pasar el toque a lo de abajo
            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width, raiz.m(760))
                spacing: raiz.m(20)
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: raiz.tx("menu", "enviar_a")
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(30)
                }
                Repeater {
                    model: raiz.acciones?.destinos ?? []
                    Rectangle {
                        id: destino
                        required property var modelData
                        objectName: "destino_" + modelData.nombre
                        width: parent.width; height: raiz.m(112)
                        radius: raiz.m(20)
                        color: zonaDestino.pressed ? Colores.fondoSutil : Colores.fondoTarjeta
                        border.width: raiz.m(2); border.color: Colores.bordeDivisor
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
                                elide: Text.ElideRight
                                text: destino.modelData.correo
                                color: Colores.textoSecundario
                                font.family: Tipografia.familia
                                font.pixelSize: raiz.fuente(22)
                            }
                        }
                        MouseArea {
                            id: zonaDestino
                            anchors.fill: parent
                            onClicked: ventanaHistorial.enviar(destino.modelData.correo)
                        }
                    }
                }
                Rectangle {
                    objectName: "destinoOtro"
                    width: parent.width; height: raiz.m(112)
                    radius: raiz.m(20)
                    color: zonaOtro.pressed ? Colores.fondoSutil : Colores.fondoTarjeta
                    border.width: raiz.m(2); border.color: Colores.bordeDivisor
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        x: raiz.m(32)
                        text: raiz.tx("menu", "otro_correo")
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(26)
                    }
                    MouseArea {
                        id: zonaOtro
                        anchors.fill: parent
                        onClicked: raiz.teclado?.abrirAlfanumerico(
                            raiz.tx("menu", "titulo_otro_correo"), "", 80, false,
                            function (valor) { if (valor !== "") ventanaHistorial.enviar(valor) })
                    }
                }
                BotonVentana {
                    objectName: "botonCancelarDestino"
                    anchors.horizontalCenter: parent.horizontalCenter
                    texto: raiz.tx("acciones", "cancelar")
                    onPulsado: ventanaHistorial.cancelarDestino()
                }
            }
        }
    }

    // ======================= paneles de la campana y de información =======================
    // Los mismos de PantallaPreciclo.qml (PROVISIONALES, sin diseño del diseñador)
    PanelNotificaciones {
        id: panelNotificaciones
        objectName: "panelNotificacionesMenu"
        titulo: raiz.tx("notificaciones", "titulo")
        textoCerrar: raiz.tx("acciones", "cerrar")
        rotuloAlertas: raiz.tx("notificaciones", "alertas_avisos")
        textoSinAlarmas: raiz.tx("ciclo", "sin_alarmas")
        alarmas: raiz.puente?.alarms ?? null
    }
    PanelEquipo {
        id: panelEquipo
        objectName: "panelEquipoMenu"
        titulo: raiz.tx("equipo", "titulo")
        textoCerrar: raiz.tx("acciones", "cerrar")
        filas: raiz.infoEquipo?.filas ?? []
        textosEquipo: raiz.textosJson.equipo ?? ({})
        sinLectura: raiz.tx("sistema", "sin_lectura")
    }
}
