pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import Autoclave.Controllers
import "Pantallas"
import "Componentes"
import Autoclave.I18n

Window {
    id: ventana
    width: 600; height: 960   // 5:8, igual que el lienzo de Escala
    visibility: Window.Windowed   // app.py la pasa a pantalla completa en el monitor elegido
    visible: true
    color: Colores.fondoMarinoOscuro

    // Los inyecta app.py (setInitialProperties). puente: UiBridge de solo lectura;
    // comandosPuerta: abrir/cerrar la puerta de esta ventana; ajustes: lanzador
    // del menú de configuración PySide. Textos: singleton I18n (autoclave/i18n).
    // comandoCiclo: iniciar ciclo; infoEquipo: modelo/serie y panel de equipo.
    property QtObject puente: null
    property QtObject comandosPuerta: null
    property QtObject comandoCiclo: null
    // selectorCiclo: cambio de programa desde Preciclo (B6, tanda 4)
    property QtObject selectorCiclo: null
    // comandoFalla: RECONOCER FALLA de la pantalla de preciclo (T-16)
    property QtObject comandoFalla: null
    property QtObject infoEquipo: null
    // comandosSistema: Confirmar y llevar a estado seguro / Apagar equipo (E5)
    property QtObject comandosSistema: null
    property QtObject ajustes: null
    // standby: activo = mostrar la pantalla de arranque (simultáneo en ambas pantallas)
    property QtObject standby: null
    // progreso / comandosCicloEnCurso: datos y comandos de la pantalla de ciclo en curso
    property QtObject progreso: null
    property QtObject comandosCicloEnCurso: null
    // resumen: Resumen del Sistema del Menú Principal (ResumenSistema, solo lectura)
    property QtObject resumen: null
    // historial: listados de Ciclos hoy e Historial del Menú Principal (CiclosHistorial)
    property QtObject historial: null
    // acciones: imprimir / enviar por correo ciclos del Historial (AccionesCiclos)
    property QtObject acciones: null
    // reporte: resumen de ciclos por periodo de Reportes (ReporteResumen)
    property QtObject reporte: null
    // sesion: sesión de esta ventana contra el backend (SesionVentana, T-8):
    // vigilancia de conexión, cierre por desconexión y 401
    property QtObject sesion: null
    // puenteNuevoUsuario: NuevoUsuarioBridge de OPCIONES › Usuarios
    property QtObject puenteNuevoUsuario: null
    // progresoArranque: progreso del arranque para la intro (etapas reales de
    // GET /arranque, bridge/progreso_arranque.py); versionSoftware: para el pie de la intro.
    // Sin progresoArranque (pruebas) no se muestra la intro.
    property QtObject progresoArranque: null
    property string versionSoftware: ""
    property bool introTerminada: false

    // Pantalla principal según el estado de la máquina que reporta el backend
    // (planeacion_pantalla_ciclo_en_curso.md §9): en CICLO, la de ciclo en curso
    // (también tras el fin, mientras se espera la confirmación); si no, la previa
    // al inicio. No depende del toque local de INICIAR CICLO. Cada pantalla física
    // lo decide por su cuenta con el mismo backend (sin estado compartido).
    readonly property string estadoMaquina: puente?.machineState ?? "DESCONOCIDO"
    readonly property bool enCiclo: estadoMaquina === "CICLO"
    property bool mostrandoEnCurso: false
    // Sin datos del backend (DESCONOCIDO) se conserva la última principal: no
    // se pasa a preciclo con un ciclo que puede seguir en marcha (revisión U2,
    // TMG-04/SAF-03)
    function _principalEnCurso() { return estadoMaquina === "DESCONOCIDO" ? mostrandoEnCurso : enCiclo }
    function destinoPrincipal() { return _principalEnCurso() ? enCursoComp : cicloComp }
    function irAPrincipal() {
        const enCurso = _principalEnCurso()
        pila.push(enCurso ? enCursoComp : cicloComp)
        mostrandoEnCurso = enCurso
    }

    // Reposo <-> principal lo decide el standby (única transición simultánea):
    // activo -> se vuelve al arranque desde cualquier pantalla; inactivo -> principal.
    // El resto de la navegación (login, paneles) es local de cada pantalla.
    function aplicarStandby() {
        if (!standby)
            return
        panelTeclado.cerrar()
        cerrarSesionPorStandby()
        if (standby.activo) {
            if (pila.depth > 1)
                pila.pop(null)
        } else if (pila.depth === 1) {
            irAPrincipal()
        }
    }
    Connections {
        target: ventana.standby
        function onActivoChanged() { ventana.aplicarStandby() }
    }

    // Sesión de esta ventana (SessionManager, una por proceso): decide si el
    // acceso a la configuración pasa por el login, por el cambio de contraseña
    // obligatorio o va directo a OPCIONES (planeacion_opciones_parametros_ciclo.md,
    // U-5: Inicio conserva la sesión).
    OpcionesController { id: sesionVentana }
    // S4 (CIC-10): el aviso de estado seguro detenido abre OPCIONES
    Connections {
        target: ventana.comandosSistema
        ignoreUnknownSignals: true
        function onAsignarSondaSolicitada() { ventana.abrirConfiguracion() }
    }
    function abrirConfiguracion() {
        // U1 (TMG-02): con el paro real o la confirmación pendiente no se va a
        // una pantalla sin campana (U4: el panel ya no se bloquea; el paro se
        // ve en la tarjeta de alarmas de la principal). DECISIÓN SIN
        // CONFIRMAR U4-3: se conserva este freno en el avatar.
        if (seguridadUrgente)
            return
        sesionVentana.refrescar()
        pila.push(!sesionVentana.sesionActiva ? loginComp
                  : sesionVentana.cambioClavePendiente ? cambioClaveComp : opcionesComp)
    }
    // El standby (equipo desatendido) cierra la sesión, con /auth/logout
    // (decisión 31): quien vuelva debe iniciarla de nuevo (Cristian, 2026-10-07).
    function cerrarSesionPorStandby() {
        if (standby?.activo)
            sesionVentana.cerrarSesion()
    }
    // HIBERNACION es la suspensión (decisiones 15 y 31): cierra la sesión con
    // logout y sale de las pantallas con token. Hoy no se alcanza (OPC-25).
    function aplicarSuspension() {
        if (estadoMaquina !== "HIBERNACION")
            return
        // también cancela un login en vuelo (cerrarSesion -> cerrar_local)
        sesionVentana.cerrarSesion()
        if (enPantallaConToken || pila.currentItem?.objectName === "areaLogin")
            volverAPrincipal()
    }

    // Pantalla con token a la vista (OPCIONES, Nuevo usuario, Cambio de
    // clave): la vigilancia de conexión solo aplica en ellas (§3.7 del plan T-8)
    readonly property bool enPantallaConToken: pila.currentItem?.usaToken ?? false
    readonly property bool conectado: puente ? puente.connected : true
    function vigilarConexion() { sesion?.vigilar(conectado, enPantallaConToken) }
    onConectadoChanged: vigilarConexion()
    onEnPantallaConTokenChanged: vigilarConexion()
    function irALogin() {
        panelTeclado.cerrar()
        pila.pop(null)
        irAPrincipal()
        if (!seguridadUrgente)   // U1: con paro, el login no tapa el panel (TMG-02 de U2)
            pila.push(loginComp)
    }
    // Revisión de U2 (TMG-01): una respuesta de login o de cambio de clave que
    // llega cuando su pantalla ya salió (Atrás, Home, cambio de estado) no
    // navega: si no, reemplazaría la pantalla principal
    function esActual(item) { return item !== null && pila.currentItem === item }
    Connections {
        target: ventana.sesion
        // 15 s sin conexión: el cambio obligatorio vuelve al login (token
        // descartado); OPCIONES y Nuevo usuario, a la pantalla principal
        function onCierrePorDesconexion(destino) {
            sesionVentana.refrescar()
            if (destino === "login")
                ventana.irALogin()
            else
                ventana.volverAPrincipal()
        }
        // 5 min sin actividad en esta ventana (SAF-01): la sesión ya se cerró
        // con logout; si había una pantalla con token o el login, a la principal
        function onCierrePorInactividad() {
            sesionVentana.refrescar()
            if (ventana.enPantallaConToken || pila.currentItem?.objectName === "areaLogin")
                ventana.volverAPrincipal()
        }
        // 401 en una escritura o al validar tras reconectar: volver al login
        function onSesionInvalida() {
            sesionVentana.refrescar()
            if (ventana.enPantallaConToken)
                ventana.irALogin()
        }
    }
    Connections {
        target: ventana.puenteNuevoUsuario
        function onSolicitudNavegar(destino) {
            if (destino === "admin_menu")
                ventana.atras()                  // "<", Atrás y Cancelar: vuelven a Usuarios
            else
                ventana.volverAPrincipal()       // Inicio (sesión conservada)
        }
    }

    // U1 (tanda 2): con el paro o la confirmación de estado seguro pendiente,
    // una pantalla sin campana (login, cambio de clave, nuevo usuario) vuelve a
    // la principal, cuya tarjeta de alarmas los muestra con el botón de
    // confirmar (U4: el panel ya no se abre solo; paroActivo = paro real, la
    // tarjeta desconectada no fuerza esta vuelta). La sesión no se
    // toca: solo la cierra la inactividad (SAF-01). No aplica a la pantalla de
    // reposo (el standby ya despierta con el paro) ni a la intro de arranque.
    readonly property bool seguridadUrgente: (puente?.paroActivo ?? false)
                                             || (puente?.estadoSeguroRequiereConfirmacion ?? false)
    function irAPanelSeguridad() {
        if (!seguridadUrgente)
            return
        panelTeclado.cerrar()   // no tapa el panel (SAF-02)
        introTerminada = true   // la intro no lo oculta (SAF-03)
        if (pila.depth > 1 && (pila.currentItem?.sinCampana ?? false))
            volverAPrincipal()
    }
    onSeguridadUrgenteChanged: irAPanelSeguridad()

    // Entrada/salida de la pantalla de ciclo en curso. Con estado desconocido
    // (sin datos del backend) no se navega; en el arranque lo resuelve el standby.
    function aplicarEstadoMaquina() {
        if (estadoMaquina === "DESCONOCIDO" || pila.depth <= 1 || enCiclo === mostrandoEnCurso)
            return
        panelTeclado.cerrar()
        pila.pop(null)
        irAPrincipal()
    }
    onEnCicloChanged: aplicarEstadoMaquina()
    onEstadoMaquinaChanged: { aplicarEstadoMaquina(); aplicarSuspension() }
    // UI que arranca (o se reinicia) con la máquina ya en CICLO: directo a la
    // pantalla de ciclo en curso, sin esperar el toque del arranque (plan §9)
    Component.onCompleted: { if (enCiclo && pila.depth === 1) irAPrincipal(); irAPanelSeguridad(); vigilarConexion() }

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno,
                        ventana.height / Escala.altoDiseno)
    }
    Binding {
        target: Escala
        property: "altoLienzo"
        value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor)
    }

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        // Navegación arranque <-> ciclo por standby; desde ciclo, el avatar abre
        // el login QML, que al validar lleva a OPCIONES; su casa regresa a ciclo.
        StackView {
            id: pila
            anchors.fill: parent
            initialItem: esperaComp
            // un teclado abierto no sobrevive a un cambio de pantalla; con el
            // paro o la confirmación pendiente no se queda en una sin campana (U1)
            onCurrentItemChanged: panelTeclado.cerrar()
        }

        // U1 (tanda 2): el paro, el estado seguro, NO ABRIR y el modo prueba ya
        // no van en una franja superior: están en el panel de la campana
        // (PanelNotificaciones › SeccionEstadoSeguro) y, desde U4, también en
        // la tarjeta de alarmas de Preciclo y de Ciclo en curso. Ver
        // irAPanelSeguridad().

        // Teclado en pantalla de esta ventana (Paso 5 de planeacion_teclados_qml.md):
        // sobre el StackView, inyectado a las pantallas como `teclado`.
        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
        }

        // Sin conexión con token en uso: escrituras bloqueadas y cuenta
        // regresiva local hasta el cierre de la sesión (§3.7 del plan T-8)
        Rectangle {
            objectName: "avisoSinConexionSesion"
            visible: (ventana.sesion?.sinConexion ?? false) && ventana.enPantallaConToken
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Escala.px(24)
            height: columnaAviso.implicitHeight + Escala.px(32)
            radius: Escala.px(12)
            color: Colores.advertenciaFondo
            Column {
                id: columnaAviso
                anchors.centerIn: parent
                width: parent.width - Escala.px(48)
                spacing: Escala.px(6)
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: I18n.t("sesion.sin_conexion_escrituras", I18n.lang)
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(26)
                }
                Text {
                    objectName: "cuentaRegresivaSesion"
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: I18n.t("sesion.sin_conexion_cierre", I18n.lang, { tiempo: ventana.sesion?.tiempoParaCierre ?? "" })
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(24)
                }
            }
        }

        // Intro de arranque (planeacion_animacion_arranque.md): lo primero que se
        // ve, encima de la pantalla de reposo que ya está debajo en la pila. Su
        // último cuadro es el fondo de reposo; al terminar se descarga.
        Loader {
            id: intro
            objectName: "introArranque"
            anchors.fill: parent
            active: ventana.progresoArranque !== null && !ventana.introTerminada
            sourceComponent: IntroArranque {
                progreso: ventana.progresoArranque
                modelo: ventana.infoEquipo?.modelo ?? ""
                versionSoftware: ventana.versionSoftware
                onFinalizada: ventana.introTerminada = true
            }
        }

        // PROVISIONAL (sin capa de alarmas en QML; ver sistema de alarmas): fallo
        // bloqueante de arranque superpuesto a la intro congelada (regla 3).
        Rectangle {
            objectName: "alarmaArranque"
            visible: intro.item?.falloBloqueante ?? false
            anchors.left: parent.left; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: Escala.px(48)
            height: filaAlarmaArranque.height + Escala.px(48)
            radius: Escala.px(16)
            color: Colores.fondoTarjeta
            FilaAlarma {
                id: filaAlarmaArranque
                anchors.left: parent.left; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.margins: Escala.px(24)
                height: Escala.px(96)
                prioridad: "alta"
                idAlarma: "ARRANQUE"
                descripcion: I18n.t("arranque.fallo_titulo", I18n.lang) + ": " +
                             I18n.t((intro.item?.sinProgreso ?? false)
                                            ? "arranque.sin_progreso" : "arranque.fallo_bloqueante", I18n.lang)
            }
        }
    }

    // Pantallas de alto fijo (1920 de diseño): centradas en el lienzo (AreaFija)
    Component {
        id: esperaComp
        AreaFija {
            Reposo {
                anchors.fill: parent
                // con standby, el toque ya lo registró el filtro de eventos y el
                // cambio llega por aplicarStandby(); sin él (pruebas), navegación local
                onTocado: if (!ventana.standby) ventana.irAPrincipal()
            }
        }
    }
    Component {
        id: cicloComp
        AreaFija {
            PantallaPreciclo {
                anchors.fill: parent
                puente: ventana.puente
                comandosPuerta: ventana.comandosPuerta
                comandoCiclo: ventana.comandoCiclo
                selectorCiclo: ventana.selectorCiclo
                comandoFalla: ventana.comandoFalla
                infoEquipo: ventana.infoEquipo
                comandosSistema: ventana.comandosSistema
                onPuertaPulsada: ventana.comandosPuerta?.alternar()
                onIniciarCicloPulsado: ventana.comandoCiclo?.iniciar()
                onIniciarSinRegistroPulsado: ventana.comandoCiclo?.iniciarSinRegistro()
                onReconocerFallaPulsado: ventana.comandoFalla?.reconocer()
                onAjustesPulsado: pila.push(menuComp)
                onAvatarPulsado: ventana.abrirConfiguracion()
            }
        }
    }
    // Pantalla de ciclo en curso: alto flexible (sin AreaFija). Campana y panel de
    // equipo los abre la propia pantalla; el engranaje y el avatar abren el login
    // (u OPCIONES si ya hay sesión) — decisión de Cristian, 2026-10-07 (U-18).
    // Si la máquina sale de CICLO con el menú abierto, aplicarEstadoMaquina()
    // vacía la pila y vuelve a la pantalla principal que corresponda.
    Component {
        id: enCursoComp
        PantallaCicloEnCurso {
            puente: ventana.puente
            progreso: ventana.progreso
            comandos: ventana.comandosCicloEnCurso
            infoEquipo: ventana.infoEquipo
            comandosSistema: ventana.comandosSistema
            onAjustesPulsado: ventana.abrirConfiguracion()
            onAvatarPulsado: ventana.abrirConfiguracion()
        }
    }
    // Menú Principal (planeacion_menu_principal_ui_qml.md): lo abre el engranaje de
    // la pantalla de preciclo y el de la de ciclo en curso (decisión de Cristian,
    // 2026-10-02); su casa regresa a esa pantalla. Iniciar sesión abre el login QML
    // (su casa regresa al menú); Información y la campana abren sus paneles dentro
    // del propio menú. Alto flexible (sin AreaFija).
    Component {
        id: menuComp
        MenuPrincipal {
            puente: ventana.puente
            resumen: ventana.resumen
            historial: ventana.historial
            acciones: ventana.acciones
            reporte: ventana.reporte
            teclado: panelTeclado
            infoEquipo: ventana.infoEquipo
            comandosSistema: ventana.comandosSistema
            inicioActivo: true
            onAtrasPulsado: ventana.atras()
            onInicioPulsado: ventana.volverAPrincipal()
            onIniciarSesionPulsado: ventana.abrirConfiguracion()
        }
    }
    Component {
        id: loginComp
        AreaFija {
            id: areaLogin
            objectName: "areaLogin"
            readonly property bool sinCampana: true
            Login {
                anchors.fill: parent
                teclado: panelTeclado
                puente: ventana.puente
                onAtrasPulsado: ventana.atras()
                onInicioPulsado: ventana.volverAPrincipal()
                // sesión validada: el login se reemplaza por OPCIONES, o por
                // CAMBIAR CONTRASEÑA si es obligatorio (T-8)
                onSesionIniciada: if (ventana.esActual(areaLogin)) pila.replace(opcionesComp)
                onCambioClaveRequerido: if (ventana.esActual(areaLogin)) pila.replace(cambioClaveComp)
            }
        }
    }
    // Cambio de contraseña obligatorio (T-8): clave cambiada -> OPCIONES;
    // sesión terminada (bloqueo, sin respuesta, 401) -> Login con su aviso;
    // Atrás / Inicio (U2) -> pantalla anterior / principal, sin logout.
    Component {
        id: cambioClaveComp
        AreaFija {
            id: areaCambioClave
            objectName: "areaCambioClave"
            readonly property bool usaToken: true
            readonly property bool sinCampana: true
            CambioClave {
                anchors.fill: parent
                teclado: panelTeclado
                onClaveCambiada: { sesionVentana.refrescar(); if (ventana.esActual(areaCambioClave)) pila.replace(opcionesComp) }
                onSesionTerminada: {
                    sesionVentana.refrescar()
                    if (!ventana.esActual(areaCambioClave))
                        return
                    if (ventana.seguridadUrgente)
                        ventana.volverAPrincipal()
                    else
                        pila.replace(loginComp)
                }
                onAtrasPulsado: { sesionVentana.refrescar(); ventana.atras() }
                onInicioPulsado: { sesionVentana.refrescar(); ventana.volverAPrincipal() }
            }
        }
    }
    // Nuevo usuario (T-8, R2-5): pantalla completa sobre OPCIONES; "<" y
    // Cancelar vuelven a Usuarios (ver Connections de puenteNuevoUsuario).
    Component {
        id: nuevoUsuarioComp
        AreaFija {
            objectName: "areaNuevoUsuario"
            readonly property bool usaToken: true
            readonly property bool sinCampana: true
            NuevoUsuario {
                anchors.fill: parent
                teclado: panelTeclado
                puente: ventana.puenteNuevoUsuario
            }
        }
    }
    function abrirNuevoUsuario() {
        if (seguridadUrgente)
            return
        ventana.puenteNuevoUsuario?.actualizarSesion()
        pila.push(nuevoUsuarioComp)
    }
    // OPCIONES (planeacion_opciones_parametros_ciclo.md, Fase 1). Alto flexible.
    // Inicio sale conservando la sesión; Atrás (U2) vuelve a la pantalla
    // anterior, también sin cerrarla. Inicio regresa a la
    // pantalla principal según el estado (preciclo o ciclo en curso), aunque se
    // haya llegado por el Menú Principal (decisión de Cristian, 2026-10-07).
    // U2 (tanda 2): Atrás regresa a la pantalla anterior de la pila sin cerrar
    // la sesión. Nunca deja la pila sin pantalla principal: con solo reposo y
    // principal debajo, vuelve a la principal que corresponda al estado.
    function atras() {
        panelTeclado.cerrar()
        if (pila.depth > 2)
            pila.pop()
        else
            volverAPrincipal()
    }
    function volverAPrincipal() {
        pila.pop(null)
        irAPrincipal()
    }
    Component {
        id: opcionesComp
        Opciones {
            puente: ventana.puente
            teclado: panelTeclado
            comandosSistema: ventana.comandosSistema
            onAtrasPulsado: ventana.atras()
            onInicioPulsado: ventana.volverAPrincipal()
            onNuevoUsuarioPulsado: ventana.abrirNuevoUsuario()
            onMenuPulsado: pila.push(menuComp)
            onCerrarSesionPulsado: { sesionVentana.cerrarSesion(); ventana.volverAPrincipal() }
        }
    }
}
