pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"

// OPCIONES, Fase 1: marco (planeacion_opciones_parametros_ciclo.md, rev. 3, §5.0,
// U-2, U-5, U-6, U-19 y §7). Referencia: src/autoclave/images/opciones_cajon_comparativo.png
// (1a cajón cerrado, 1b abierto técnico, 1c abierto admin). Contenido de PySide
// (U-1): cada sección muestra solo "Próximamente" (U-4: QML no abre vistas PySide).
//
// Geometría: px del marco del diseñador (1196 x 1917, el de PantallaPreciclo.qml)
// escalados con m(), medidos sobre la referencia (factor 1196/620). Alto flexible
// (9:16): encabezado y título anclados arriba, barra inferior abajo.
//
// Navegación: cajón lateral modal (U-19) que se abre con la hamburguesa del
// título y se cierra tocando fuera, al elegir una entrada o con alternarCajon().
// Sin gesto de deslizamiento (Q-7). El título muestra la sección activa (Q-8).
//
// Sesión y permisos: OpcionesController (SessionManager + domain/permisos_opciones.py).
// La pantalla nunca compara roles. Salir cierra la sesión (con confirmación si
// hay cambios sin guardar, U-5/U-13); Inicio sale conservándola.
Item {
    id: raiz

    property QtObject puente: null      // UiBridge: estado de la máquina y campana
    property var textosJson: ({})
    // Cambios sin guardar de la sección activa. Fase 1: ninguna sección edita,
    // siempre false; las fases 3 y 4 lo alimentan (U-13, U-19).
    property bool cambiosPendientes: false

    signal inicioPulsado()     // salir de OPCIONES conservando la sesión (U-5)
    signal sesionCerrada()     // Salir: sesión ya cerrada

    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }
    // Nombre de la sección en una línea (cajón y título, §5.0)
    function nombreSeccion(clave) {
        const s = textosJson?.opciones?.secciones
        return ((s && s[clave] !== undefined) ? s[clave] : clave).replace(/\n/g, " ")
    }

    readonly property real anchoMockup: 1196
    readonly property real altoMockup: 1917
    readonly property real escala: width / anchoMockup
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    readonly property string iconosMono: "../../assets/iconos/mono/"

    OpcionesController {
        id: control
        objectName: "opcionesController"
        estadoMaquina: raiz.puente?.machineState ?? ""
        seccion: raiz.seccionActiva
    }
    readonly property alias controlador: control
    readonly property var secciones: control.secciones
    readonly property bool edicionPermitida: control.edicionPermitida

    // Sección activa: al abrir, la primera visible (el admin aterriza en Usuarios)
    property string seccionActiva: ""
    function _ajustarSeccion() {
        if (!secciones.some(s => s.clave === seccionActiva))
            seccionActiva = secciones.length > 0 ? secciones[0].clave : ""
    }
    onSeccionesChanged: _ajustarSeccion()
    Component.onCompleted: { control.refrescar(); _ajustarSeccion() }

    // ---- cajón ----
    property bool cajonAbierto: false
    function abrirCajon() { cajonAbierto = true }
    function cerrarCajon() { cajonAbierto = false }
    function alternarCajon() { cajonAbierto = !cajonAbierto }

    // Elegir una entrada: cierra el cajón y muestra su panel; con cambios sin
    // guardar pide confirmación antes de cambiar (U-19)
    property string _seccionPendiente: ""
    function elegirSeccion(clave) {
        cerrarCajon()
        if (clave === seccionActiva)
            return
        if (cambiosPendientes) {
            _seccionPendiente = clave
            dialogoCambiarSeccion.abrir()
        } else {
            seccionActiva = clave
        }
    }

    // ---- salida ----
    function salir() {
        cerrarCajon()
        if (cambiosPendientes)
            dialogoSalir.abrir()
        else
            _cerrarSesion()
    }
    function _cerrarSesion() {
        control.cerrarSesion()
        sesionCerrada()
    }

    // ======================= fondo y encabezado =======================
    FondoApp { anchors.fill: parent }

    EncabezadoMenu {
        objectName: "encabezadoOpciones"
        escala: raiz.escala
        textosJson: raiz.textosJson
        conteoAlarmas: raiz.puente?.alarms?.count ?? -1
        conEngranaje: true
        onCampanaPulsada: panelNotificaciones.abrir()
    }

    // ======================= tarjeta blanca =======================
    Rectangle {
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: parent.height - y - raiz.m(17)
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
    }

    // ---- título: hamburguesa + sección activa (imagen 1a) ----
    // Tres trazos dibujados (no hay icono de hamburguesa en assets): 48 x 31 en (79, 253)
    Column {
        x: raiz.m(79); y: raiz.m(253)
        spacing: raiz.m(10.5)
        Repeater {
            model: 3
            delegate: Rectangle {
                width: raiz.m(48); height: raiz.m(3.3)
                radius: height / 2
                color: Colores.textoPrimario
            }
        }
    }
    MouseArea {
        objectName: "botonHamburguesa"
        x: raiz.m(49); y: raiz.m(219); width: raiz.m(108); height: raiz.m(100)   // > 64 px (U-14)
        onClicked: raiz.alternarCajon()
    }
    Text {
        objectName: "tituloOpciones"
        x: raiz.m(160)
        y: raiz.m(282) - baselineOffset
        width: raiz.m(1140) - x
        elide: Text.ElideRight
        text: raiz.seccionActiva !== "" ? raiz.nombreSeccion(raiz.seccionActiva).toUpperCase()
                                        : raiz.tx("opciones", "titulo")
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(36)
        font.letterSpacing: raiz.m(36 * 0.05)   // track 5 de titulo_pantalla
    }

    // ======================= contenido (todo el ancho, U-19) =======================
    Item {
        id: contenido
        objectName: "contenidoOpciones"
        x: raiz.m(54); y: raiz.m(330)
        width: raiz.m(1088)
        height: barra.y - y - raiz.m(30)

        // Solo lectura fuera de PREPARACION / PREPARADO (U-8): aviso fijo
        Rectangle {
            objectName: "avisoEdicionBloqueada"
            visible: raiz.seccionActiva !== "" && !raiz.edicionPermitida
            width: parent.width
            height: raiz.m(72)
            radius: raiz.m(14)
            color: Colores.advertenciaFondo
            Text {
                anchors.fill: parent
                anchors.leftMargin: raiz.m(24); anchors.rightMargin: raiz.m(24)
                verticalAlignment: Text.AlignVCenter
                text: raiz.tx("opciones", "edicion_bloqueada")
                wrapMode: Text.WordWrap
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(23)
            }
        }

        // Fase 1: ninguna sección migrada (U-4); centrado como en la imagen 1c
        Text {
            objectName: "textoProximamente"
            visible: raiz.seccionActiva !== ""
            anchors.centerIn: parent
            text: raiz.tx("opciones", "proximamente")
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(42)
        }

        // Rol sin ninguna sección visible (§5.0)
        Text {
            objectName: "textoSinSecciones"
            visible: raiz.seccionActiva === ""
            anchors.centerIn: parent
            width: parent.width - raiz.m(80)
            horizontalAlignment: Text.AlignHCenter
            text: raiz.tx("opciones", "sin_secciones")
            wrapMode: Text.WordWrap
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(30)
        }
    }

    // ======================= barra inferior =======================
    BarraInferiorMenu {
        id: barra
        objectName: "barraInferiorOpciones"
        x: raiz.m(34)
        y: parent.height - raiz.m(raiz.altoMockup - 1746)
        escala: raiz.escala
        version: raiz.tx("app", "version")
        salirHabilitado: true
        inicioActivo: true
        onSalirPulsado: raiz.salir()
        onInicioPulsado: raiz.inicioPulsado()
    }

    // ======================= cajón lateral (U-19, imágenes 1b y 1c) =======================
    // Fondo atenuado: tocar fuera cierra; no deja pasar el toque al contenido
    Rectangle {
        objectName: "fondoCajon"
        anchors.fill: parent
        color: "#99000000"   // PROVISIONAL: misma atenuación que DialogoConfirmacion
        opacity: raiz.cajonAbierto ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea { anchors.fill: parent; onClicked: raiz.cerrarCajon() }
    }

    Rectangle {
        id: cajon
        objectName: "cajonOpciones"
        width: raiz.m(627)   // ~ la mitad del ancho (U-19)
        height: parent.height
        x: raiz.cajonAbierto ? -radius : -width - radius
        visible: x > -width - radius
        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        radius: raiz.m(39)   // esquinas derechas redondeadas; las izquierdas quedan fuera de pantalla
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // el toque dentro del cajón no lo cierra

        // contenido del cajón, en coordenadas de pantalla (el cajón empieza en -radius)
        Item {
            x: cajon.radius
            width: cajon.width - cajon.radius
            height: parent.height

            Text {
                objectName: "tituloCajon"
                x: raiz.m(60)
                y: raiz.m(160) - baselineOffset
                text: raiz.tx("opciones", "titulo")
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(36)
                font.letterSpacing: raiz.m(36 * 0.05)
            }
            Rectangle {
                x: raiz.m(60); y: raiz.m(199)
                width: raiz.m(571 - 60); height: raiz.m(2)
                color: Colores.bordeDivisor
            }

            Column {
                objectName: "navegacionOpciones"
                x: raiz.m(25); y: raiz.m(247)
                spacing: raiz.m(118 - 97)

                Repeater {
                    model: raiz.secciones
                    delegate: Item {
                        id: entrada
                        required property var modelData
                        readonly property bool activa: modelData.clave === raiz.seccionActiva
                        objectName: "entrada_" + modelData.clave
                        // mismo margen a ambos lados, dentro del borde del cajón
                        width: cajon.width - cajon.radius - 2 * raiz.m(25)
                        // > 64 px de área táctil (U-14); si el nombre no cabe en una
                        // línea, la fila crece y pasa a dos (U-2, rev. 3.1)
                        height: Math.max(raiz.m(97), textoEntrada.contentHeight + raiz.m(36))

                        Rectangle {
                            anchors.fill: parent
                            radius: raiz.m(18)
                            color: entrada.activa ? Colores.accionFondoTenue : "transparent"
                        }
                        Rectangle {
                            visible: entrada.activa
                            width: raiz.m(6); height: parent.height
                            radius: width / 2
                            color: Colores.accionPrimario
                        }
                        IconoColor {
                            x: raiz.m(89 - 25) - width / 2
                            anchors.verticalCenter: parent.verticalCenter
                            width: raiz.m(54); height: width
                            source: raiz.iconosMono + entrada.modelData.icono
                            color: entrada.activa ? Colores.accionPrimario : Colores.textoPrimario
                        }
                        Text {
                            id: textoEntrada
                            objectName: "textoEntrada"
                            x: raiz.m(160 - 25)
                            width: parent.width - x - raiz.m(12)
                            anchors.verticalCenter: parent.verticalCenter
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            text: raiz.nombreSeccion(entrada.modelData.clave)
                            color: entrada.activa ? Colores.accionPrimarioTexto : Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: entrada.activa ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                            font.pixelSize: raiz.fuente(27)
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: raiz.elegirSeccion(entrada.modelData.clave)
                        }
                    }
                }
            }
        }
    }

    // ======================= ventanas =======================
    PanelNotificaciones {
        id: panelNotificaciones
        objectName: "panelNotificacionesOpciones"
        titulo: raiz.tx("notificaciones", "titulo")
        textoCerrar: raiz.tx("acciones", "cerrar")
        rotuloAlertas: raiz.tx("notificaciones", "alertas_avisos")
        textoSinAlarmas: raiz.tx("ciclo", "sin_alarmas")
        alarmas: raiz.puente?.alarms ?? null
    }

    // Salir con cambios sin guardar: Salir descarta y cierra la sesión (U-13)
    DialogoConfirmacion {
        id: dialogoSalir
        objectName: "dialogoSalirOpciones"
        mensaje: raiz.tx("opciones", "salir_pregunta")
        textoConfirmar: raiz.tx("opciones", "salir_confirmar")
        textoCancelar: raiz.tx("acciones", "cancelar")
        onConfirmado: raiz._cerrarSesion()
    }
    // Cambiar de sección con cambios sin guardar (U-19): confirmar descarta y cambia
    DialogoConfirmacion {
        id: dialogoCambiarSeccion
        objectName: "dialogoCambiarSeccion"
        mensaje: raiz.tx("opciones", "cambiar_seccion_pregunta")
        textoConfirmar: raiz.tx("opciones", "cambiar_seccion_confirmar")
        textoCancelar: raiz.tx("acciones", "cancelar")
        onConfirmado: { raiz.seccionActiva = raiz._seccionPendiente; raiz._seccionPendiente = "" }
        onDescartado: raiz._seccionPendiente = ""
    }
}
