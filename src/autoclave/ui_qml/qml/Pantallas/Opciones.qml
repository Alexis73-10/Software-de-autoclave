pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

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
// La pantalla nunca compara roles. Atrás e Inicio salen conservando la sesión
// (con confirmación si hay cambios sin guardar, U-5/U-13; U2 de la tanda 2).
//
// Usuarios (T-8, R2-5): un botón abre Nuevo usuario a pantalla completa sobre
// OPCIONES (nuevoUsuarioPulsado; lo apila Main.qml). Es pantalla con token en
// uso (`usaToken`): la vigilancia de conexión de Main.qml aplica aquí.
Item {
    id: raiz
    objectName: "pantallaOpciones"

    property QtObject puente: null      // UiBridge: estado de la máquina y campana
    property QtObject comandosSistema: null   // confirmar estado seguro desde la campana (U1)
    property QtObject teclado: null     // PanelTeclado de la ventana (T12: ajuste de parámetros)
    // Cambios sin guardar de la sección activa (U-13, U-19): roles de sensor
    // sin guardar en Parámetros del ciclo (T12)
    property bool cambiosPendientes: (parametrosCiclo.item?.cambiosPendientes ?? false)
                                     || (parametrosEquipo.item?.cambiosPendientes ?? false)
                                     || (avanzadas.item?.cambiosPendientes ?? false)

    signal inicioPulsado()     // salir de OPCIONES conservando la sesión (U-5)
    // U2 (tanda 2): Atrás vuelve a la pantalla anterior conservando la sesión;
    // ya no hay Salir que la cierre (solo la inactividad, SAF-01, decisión 7)
    signal atrasPulsado()
    signal nuevoUsuarioPulsado()   // sección Usuarios: abrir Nuevo usuario
    signal cerrarSesionPulsado()   // barra inferior: cerrar la sesión y salir
    signal menuPulsado()           // engranaje del encabezado: Menú Principal

    readonly property bool usaToken: true
    // O2f (tanda 6): durante la calibración atmosférica solo Cancelar está activo
    readonly property bool navegacionBloqueada: mantenimiento.item?.navegacionBloqueada ?? false

    // Nombre de la sección en una línea (cajón y título, §5.0)
    function nombreSeccion(clave) {
        const k = "opciones.secciones." + clave
        return (I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : clave).replace(/\n/g, " ")
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
            seccionActiva = control.seccionInicial   // C1b: el admin aterriza en Usuarios
    }
    onSeccionesChanged: _ajustarSeccion()
    Component.onCompleted: { control.refrescar(); _ajustarSeccion() }

    // ---- cajón ----
    property bool cajonAbierto: false
    function abrirCajon() { if (!navegacionBloqueada) cajonAbierto = true }
    function cerrarCajon() { cajonAbierto = false }
    function alternarCajon() { if (!navegacionBloqueada) cajonAbierto = !cajonAbierto }

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
            _irASeccion(clave)
        }
    }

    // ---- historial propio de OPCIONES (D8-4.1, tanda 8) ----
    // Pila de niveles anteriores: {seccion, estado}. Cambiar de sección desde el
    // cajón apila la sección que se deja con su subnivel (programa, fase,
    // submenú, pestaña, segmento) y el desplazamiento de sus listas; Atrás, ya
    // arriba dentro de la sección, la restaura. Pila vacía: Atrás sale de OPCIONES.
    property var historial: []
    readonly property int profundidadHistorial: historial.length
    readonly property int _maxHistorial: 50
    function _cargadorDe(clave) {
        const mapa = { usuarios: usuarios, parametros_ciclo: parametrosCiclo,
                       parametros_sistema: parametrosEquipo, fecha_hora: fechaHora,
                       info_sistema: infoSistema, bitacora: bitacora,
                       mantenimiento: mantenimiento, conectividad: conectividad,
                       respaldo: respaldo, entradas_salidas: entradasSalidas,
                       opciones_avanzadas: avanzadas }
        return mapa[clave] ?? null
    }
    // Flickables (y ListView) de la sección, en orden de recorrido
    function _flickables(it, acc) {
        if (!it)
            return acc
        if (it.contentY !== undefined && it.flickableDirection !== undefined)
            acc.push(it)
        const hijos = it.children || []
        for (let i = 0; i < hijos.length; ++i)
            _flickables(hijos[i], acc)
        return acc
    }
    // Subniveles simples de las secciones (propiedades QML de la vista)
    readonly property var _propiedadesSubnivel: ["pestana", "segmento", "segmentoOrigen",
                                                 "sensorEnCalibracion"]
    function _capturarEstado(clave) {
        const item = _cargadorDe(clave)?.item ?? null
        const e = { props: {}, desplazamientos: [] }
        if (!item)
            return e
        for (const p of _propiedadesSubnivel)
            if (item[p] !== undefined)
                e.props[p] = item[p]
        if (item.vista !== undefined)
            e.vista = item.vista
        if (clave === "parametros_ciclo" && item.controlador) {
            e.programa = item.controlador.numero
            e.fase = item.controlador.seccion
        }
        if (clave === "parametros_sistema" && item.controlador)
            e.grupo = item.controlador.grupo
        e.desplazamientos = _flickables(item, []).map(f => ({ nombre: f.objectName, y: f.contentY }))
        return e
    }
    function _restaurarEstado(clave, e) {
        const item = _cargadorDe(clave)?.item ?? null
        if (!item || !e)
            return
        if (clave === "parametros_ciclo" && item.controlador) {
            const c = item.controlador
            if (e.programa > 0)
                c.elegirPrograma(e.programa)
            if (e.vista === "seccion" && e.fase) {
                c.abrirSeccion(e.fase)
            } else if (e.vista === "sensores") {
                c.cargarSensores(); item._prepararSensores()
            } else if (e.vista === "entradas") {
                c.cargarEntradas(); item._entradasSel = c.entradas.slice()
            }
        }
        if (clave === "parametros_sistema" && item.controlador && e.grupo !== undefined)
            item.controlador.abrirGrupo(e.grupo)
        for (const p of _propiedadesSubnivel)
            if (e.props[p] !== undefined && item[p] !== undefined)
                item[p] = e.props[p]
        if (e.vista !== undefined && item.vista !== undefined)
            item.vista = e.vista
        // el desplazamiento, cuando las listas ya tienen su contenido
        _desplazamientoPendiente = { clave: clave, lista: e.desplazamientos }
        temporizadorDesplazamiento.restart()
    }
    property var _desplazamientoPendiente: null
    Timer {
        id: temporizadorDesplazamiento
        interval: 0
        onTriggered: {
            const d = raiz._desplazamientoPendiente
            raiz._desplazamientoPendiente = null
            const item = d ? (raiz._cargadorDe(d.clave)?.item ?? null) : null
            if (!item || raiz.seccionActiva !== d.clave)
                return
            const actuales = raiz._flickables(item, [])
            for (let i = 0; i < Math.min(actuales.length, d.lista.length); ++i)
                if (actuales[i].objectName === d.lista[i].nombre)
                    actuales[i].contentY = d.lista[i].y
        }
    }
    function _irASeccion(clave) {
        if (seccionActiva !== "") {
            const pila = historial.slice()
            pila.push({ seccion: seccionActiva, estado: _capturarEstado(seccionActiva) })
            historial = pila.slice(-_maxHistorial)
        }
        seccionActiva = clave
    }
    // Atrás con pila: vuelve a la sección anterior; false si la pila está vacía
    function _volverEnHistorial() {
        while (historial.length > 0) {
            const pila = historial.slice()
            const nivel = pila.pop()
            historial = pila
            // una sección que ya no es visible para el rol se salta
            if (!secciones.some(s => s.clave === nivel.seccion))
                continue
            seccionActiva = nivel.seccion
            _restaurarEstado(nivel.seccion, nivel.estado)
            return true
        }
        return false
    }

    // ---- salida ----
    // Atrás e Inicio con cambios sin guardar piden confirmar el descarte (U-13)
    property var _salidaPendiente: null
    function _salirCon(senal) {
        cerrarCajon()
        if (navegacionBloqueada)
            return
        // salir de OPCIONES cierra el modo prueba de Entradas / Salidas (D-ES-08)
        entradasSalidas.item?.cerrarModoPrueba("abandono de la sección")
        if (cambiosPendientes) {
            _salidaPendiente = senal
            dialogoSalir.abrir()
        } else {
            senal()
        }
    }
    // Atrás (D8-4.1): primero la sección activa cierra su ventana de ajuste
    // (preguntando si hay un valor editado) o sube un subnivel (fase -> lista de
    // programas, submenú -> entrada, calibración -> sección); arriba en la
    // sección, vuelve al nivel anterior del historial; con la pila vacía sale
    // a la pantalla desde la que se entró (Main.qml).
    function atras() {
        cerrarCajon()
        if (parametrosCiclo.item?.retroceder())
            return
        if (parametrosEquipo.item?.retroceder())      // O2a: submenú -> entrada
            return
        if (mantenimiento.item?.retroceder())         // O2f: calibración -> Mantenimiento
            return
        if (entradasSalidas.item?.subirNivel())
            return
        if (navegacionBloqueada)
            return
        if (_volverEnHistorial())
            return
        _salirCon(atrasPulsado)
    }
    function inicio() { _salirCon(inicioPulsado) }
    function cerrarSesion() { _salirCon(cerrarSesionPulsado) }

    // ======================= fondo y encabezado =======================
    FondoApp { anchors.fill: parent }

    EncabezadoMenu {
        objectName: "encabezadoOpciones"
        escala: raiz.escala
        // alarmas más avisos de seguridad del panel (U1 de la tanda 2)
        conteoAlarmas: raiz.puente ? panelNotificaciones.conteoTotal : -1
        urgente: panelNotificaciones.urgente
        enCurso: panelNotificaciones.avisoEnCurso
        parpadeo: panelNotificaciones.parpadeo
        conEngranaje: true
        onCampanaPulsada: panelNotificaciones.abrir()
        onEngranajePulsado: raiz.menuPulsado()
    }

    // ======================= tarjeta blanca =======================
    // D8-5.10 (tanda 8, decisión 1.7 de la tanda 6): la tarjeta termina sobre
    // la barra inferior flotante (10 px, como Preciclo) en todas las secciones;
    // antes la barra quedaba dentro de la tarjeta
    Rectangle {
        id: tarjetaOpciones
        objectName: "tarjetaOpciones"
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: barra.y - raiz.m(10) - y
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
        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
        text: raiz.seccionActiva !== "" ? raiz.nombreSeccion(raiz.seccionActiva).toUpperCase()
                                        : I18n.t("opciones.titulo", I18n.lang)
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
                text: control.motivoSoloLectura === "rol"
                      ? I18n.t("opciones.solo_lectura_rol", I18n.lang)
                      : I18n.t("opciones.edicion_bloqueada", I18n.lang)
                wrapMode: Text.WordWrap
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(23)
            }
        }

        // Usuarios (O2b, tanda 6): pestañas Usuarios / Operadores; "+ Nuevo
        // usuario" sigue abriendo la pantalla existente (R2-5)
        Loader {
            id: usuarios
            objectName: "cargadorUsuarios"
            active: raiz.seccionActiva === "usuarios"
            anchors.fill: parent
            sourceComponent: OpcionesUsuarios {
                teclado: raiz.teclado
                rol: control.rol
                usuarioActual: control.usuario
                onNuevoUsuarioPulsado: raiz.nuevoUsuarioPulsado()
            }
        }

        // Parámetros del ciclo, Fases 2 a 4 (T12): debajo del aviso de bloqueo
        Loader {
            id: parametrosCiclo
            objectName: "cargadorParametrosCiclo"
            active: raiz.seccionActiva === "parametros_ciclo"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesParametrosCiclo {
                teclado: raiz.teclado
                edicionPermitida: raiz.edicionPermitida
            }
        }

        // Parámetros del equipo (O2a, tanda 6): 7 submenús
        Loader {
            id: parametrosEquipo
            objectName: "cargadorParametrosEquipo"
            active: raiz.seccionActiva === "parametros_sistema"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesParametrosEquipo {
                teclado: raiz.teclado
                edicionPermitida: raiz.edicionPermitida
                rol: control.rol                                  // O2a: decisión 1.9
                estadoMaquina: raiz.puente?.machineState ?? ""
            }
        }

        // Fecha y hora (O2c, tanda 6): solo lectura
        Loader {
            id: fechaHora
            objectName: "cargadorFechaHora"
            active: raiz.seccionActiva === "fecha_hora"
            anchors.fill: parent
            sourceComponent: OpcionesFechaHora {}
        }

        // Información del sistema (O2d, tanda 6): solo lectura
        Loader {
            id: infoSistema
            objectName: "cargadorInfoSistema"
            active: raiz.seccionActiva === "info_sistema"
            anchors.fill: parent
            sourceComponent: OpcionesInfoSistema {}
        }

        // Bitácora de auditoría (O2e, tanda 6): solo lectura
        Loader {
            id: bitacora
            objectName: "cargadorBitacora"
            active: raiz.seccionActiva === "bitacora"
            anchors.fill: parent
            sourceComponent: OpcionesBitacora { teclado: raiz.teclado }
        }

        // Mantenimiento (M1, tanda 3): próximo vencimiento y registro
        Loader {
            id: mantenimiento
            objectName: "cargadorMantenimiento"
            active: raiz.seccionActiva === "mantenimiento"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesMantenimiento {
                teclado: raiz.teclado
                edicionPermitida: raiz.edicionPermitida
            }
        }

        // Conectividad (O2g, tanda 6): red en lectura y correo de ciclos
        Loader {
            id: conectividad
            objectName: "cargadorConectividad"
            active: raiz.seccionActiva === "conectividad"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesConectividad {
                teclado: raiz.teclado
                rol: control.rol
                estadoMaquina: raiz.puente?.machineState ?? ""
            }
        }

        // Respaldo (O2h, tanda 6): exportar y restaurar por USB
        Loader {
            id: respaldo
            objectName: "cargadorRespaldo"
            active: raiz.seccionActiva === "respaldo"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesRespaldo {
                // solo fuera de ciclo, también el ingeniero (el backend responde 409)
                edicionPermitida: raiz.edicionPermitida && (raiz.puente?.machineState ?? "") !== "CICLO"
            }
        }

        // Entradas / Salidas (planeacion_opciones_entradas_salidas.md)
        Loader {
            id: entradasSalidas
            objectName: "cargadorEntradasSalidas"
            active: raiz.seccionActiva === "entradas_salidas"
            anchors.fill: parent
            sourceComponent: OpcionesEntradasSalidas {
                teclado: raiz.teclado
            }
        }

        // Opciones avanzadas (C9, tanda 9, D9-10): Manejo de ciclos para técnico
        // e ingeniero y, solo para el ingeniero, la reasignación de E/S (R8,
        // tanda 8, D8-5.12). El backend es la autoridad (rol, ciclo, confirmaciones)
        Loader {
            id: avanzadas
            objectName: "cargadorOpcionesAvanzadas"
            active: raiz.seccionActiva === "opciones_avanzadas"
            anchors.fill: parent
            anchors.topMargin: raiz.edicionPermitida ? 0 : raiz.m(84)
            sourceComponent: OpcionesAvanzadas {
                teclado: raiz.teclado
                puedeReasignar: control.puedeReasignarIo
                motivoManejo: control.motivoManejoCiclos
            }
        }

        // Secciones aún no migradas (U-4); centrado como en la imagen 1c
        Text {
            objectName: "textoProximamente"
            visible: raiz.seccionActiva !== "" && raiz.seccionActiva !== "usuarios"
                     && raiz.seccionActiva !== "parametros_ciclo"
                     && raiz.seccionActiva !== "mantenimiento"
                     && raiz.seccionActiva !== "parametros_sistema"
                     && raiz.seccionActiva !== "entradas_salidas"
                     && raiz.seccionActiva !== "fecha_hora"
                     && raiz.seccionActiva !== "info_sistema"
                     && raiz.seccionActiva !== "bitacora"
                     && raiz.seccionActiva !== "conectividad"
                     && raiz.seccionActiva !== "respaldo"
                     && raiz.seccionActiva !== "opciones_avanzadas"
            anchors.centerIn: parent
            text: I18n.t("opciones.proximamente", I18n.lang)
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
            text: I18n.t("opciones.sin_secciones", I18n.lang)
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
        // D8-5.2: mismo x y ancho que la tarjeta de contenido de encima
        x: tarjetaOpciones.x
        width: tarjetaOpciones.width
        y: parent.height - raiz.m(raiz.altoMockup - 1746)
        escala: raiz.escala
        inicioActivo: !raiz.navegacionBloqueada
        atrasHabilitado: !raiz.navegacionBloqueada
        cerrarSesionVisible: !raiz.navegacionBloqueada
        onAtrasPulsado: raiz.atras()
        onInicioPulsado: raiz.inicio()
        onCerrarSesionPulsado: raiz.cerrarSesion()
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
                text: I18n.t("opciones.titulo", I18n.lang)
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
        titulo: I18n.t("notificaciones.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        rotuloAlertas: I18n.t("notificaciones.alertas_avisos", I18n.lang)
        textoSinAlarmas: I18n.t("ciclo.sin_alarmas", I18n.lang)
        alarmas: raiz.puente?.alarms ?? null
        puente: raiz.puente
        comandosSistema: raiz.comandosSistema
    }

    // Atrás/Inicio con cambios sin guardar: confirmar descarta y sale, sin
    // cerrar la sesión (U-13; U2 de la tanda 2)
    DialogoConfirmacion {
        id: dialogoSalir
        objectName: "dialogoSalirOpciones"
        mensaje: I18n.t("opciones.salir_pregunta", I18n.lang)
        textoConfirmar: I18n.t("opciones.salir_confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { cerrar(); const s = raiz._salidaPendiente; raiz._salidaPendiente = null; if (s) s() }
    }
    // Cambiar de sección con cambios sin guardar (U-19): confirmar descarta y cambia
    DialogoConfirmacion {
        id: dialogoCambiarSeccion
        objectName: "dialogoCambiarSeccion"
        mensaje: I18n.t("opciones.cambiar_seccion_pregunta", I18n.lang)
        textoConfirmar: I18n.t("opciones.cambiar_seccion_confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { const c = raiz._seccionPendiente; raiz._seccionPendiente = ""; raiz._irASeccion(c) }
        onDescartado: raiz._seccionPendiente = ""
    }
}
