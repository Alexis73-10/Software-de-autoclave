pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import Autoclave.Controllers
import "Pantallas"
import "Componentes"

Window {
    id: ventana
    width: 600; height: 960   // 5:8, igual que el lienzo de Escala
    visibility: Window.Windowed   // app.py la pasa a pantalla completa en el monitor elegido
    visible: true
    color: Colores.fondoMarinoOscuro

    // Los inyecta app.py (setInitialProperties). puente: UiBridge de solo lectura;
    // comandosPuerta: abrir/cerrar la puerta de esta ventana; ajustes: lanzador
    // del menú de configuración PySide; textosJson: assets/textos/es.json.
    // comandoCiclo: iniciar ciclo; infoEquipo: modelo/serie y panel de equipo.
    property QtObject puente: null
    property QtObject comandosPuerta: null
    property QtObject comandoCiclo: null
    // comandoFalla: RECONOCER FALLA de la pantalla de preciclo (T-16)
    property QtObject comandoFalla: null
    property QtObject infoEquipo: null
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
    property var textosJson: ({})
    function txRuta(ruta, valores) {
        const i = ruta.indexOf(".")
        const s = i > 0 && textosJson ? textosJson[ruta.slice(0, i)] : undefined
        let texto = s && s[ruta.slice(i + 1)] !== undefined ? s[ruta.slice(i + 1)] : ""
        for (const k in (valores || {}))
            texto = texto.replace("{" + k + "}", valores[k])
        return texto
    }

    // Pantalla principal según el estado de la máquina que reporta el backend
    // (planeacion_pantalla_ciclo_en_curso.md §9): en CICLO, la de ciclo en curso
    // (también tras el fin, mientras se espera la confirmación); si no, la previa
    // al inicio. No depende del toque local de INICIAR CICLO. Cada pantalla física
    // lo decide por su cuenta con el mismo backend (sin estado compartido).
    readonly property string estadoMaquina: puente?.machineState ?? "DESCONOCIDO"
    readonly property bool enCiclo: estadoMaquina === "CICLO"
    property bool mostrandoEnCurso: false
    function destinoPrincipal() { return enCiclo ? enCursoComp : cicloComp }
    function irAPrincipal() {
        pila.push(destinoPrincipal())
        mostrandoEnCurso = enCiclo
    }

    // Arranque <-> principal lo decide el standby (única transición simultánea):
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
    function abrirConfiguracion() {
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
        pila.push(loginComp)
    }
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
                pila.pop()                       // "<" y Cancelar: vuelven a Usuarios
            else
                ventana.volverAPrincipal()       // Inicio (sesión conservada) o Salir (cerrada)
        }
    }

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
    Component.onCompleted: if (enCiclo && pila.depth === 1) irAPrincipal()

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
            // un teclado abierto no sobrevive a un cambio de pantalla
            onCurrentItemChanged: panelTeclado.cerrar()
        }

        // Teclado en pantalla de esta ventana (Paso 5 de planeacion_teclados_qml.md):
        // sobre el StackView, inyectado a las pantallas como `teclado`.
        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
            textosJson: ventana.textosJson
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
                    text: ventana.txRuta("sesion.sin_conexion_escrituras")
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
                    text: ventana.txRuta("sesion.sin_conexion_cierre",
                                         { tiempo: ventana.sesion?.tiempoParaCierre ?? "" })
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(24)
                }
            }
        }
    }

    // Pantallas de alto fijo (1920 de diseño): centradas en el lienzo (AreaFija)
    Component {
        id: esperaComp
        AreaFija {
            Arranque {
                anchors.fill: parent
                textosJson: ventana.textosJson
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
                comandoFalla: ventana.comandoFalla
                infoEquipo: ventana.infoEquipo
                textosJson: ventana.textosJson
                onPuertaPulsada: ventana.comandosPuerta?.alternar()
                onIniciarCicloPulsado: ventana.comandoCiclo?.iniciar()
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
            textosJson: ventana.textosJson
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
            textosJson: ventana.textosJson
            inicioActivo: true
            onInicioPulsado: pila.pop()
            onIniciarSesionPulsado: ventana.abrirConfiguracion()
        }
    }
    Component {
        id: loginComp
        AreaFija {
            objectName: "areaLogin"
            Login {
                anchors.fill: parent
                teclado: panelTeclado
                textosJson: ventana.textosJson
                onInicioPulsado: pila.pop()
                // sesión validada: el login se reemplaza por OPCIONES, o por
                // CAMBIAR CONTRASEÑA si es obligatorio (T-8)
                onSesionIniciada: pila.replace(opcionesComp)
                onCambioClaveRequerido: pila.replace(cambioClaveComp)
            }
        }
    }
    // Cambio de contraseña obligatorio (T-8): clave cambiada -> OPCIONES;
    // sesión terminada (bloqueo, sin respuesta, 401) -> Login con su aviso;
    // abandonar (Salir / Inicio) -> logout y pantalla principal.
    Component {
        id: cambioClaveComp
        AreaFija {
            readonly property bool usaToken: true
            CambioClave {
                anchors.fill: parent
                teclado: panelTeclado
                textosJson: ventana.textosJson
                onClaveCambiada: { sesionVentana.refrescar(); pila.replace(opcionesComp) }
                onSesionTerminada: { sesionVentana.refrescar(); pila.replace(loginComp) }
                onAbandonado: { sesionVentana.refrescar(); ventana.volverAPrincipal() }
            }
        }
    }
    // Nuevo usuario (T-8, R2-5): pantalla completa sobre OPCIONES; "<" y
    // Cancelar vuelven a Usuarios (ver Connections de puenteNuevoUsuario).
    Component {
        id: nuevoUsuarioComp
        AreaFija {
            readonly property bool usaToken: true
            NuevoUsuario {
                anchors.fill: parent
                teclado: panelTeclado
                puente: ventana.puenteNuevoUsuario
                textosJson: ventana.textosJson
            }
        }
    }
    function abrirNuevoUsuario() {
        ventana.puenteNuevoUsuario?.actualizarSesion()
        pila.push(nuevoUsuarioComp)
    }
    // OPCIONES (planeacion_opciones_parametros_ciclo.md, Fase 1). Alto flexible.
    // Inicio sale conservando la sesión; Salir la cierra. Ambos regresan a la
    // pantalla principal según el estado (preciclo o ciclo en curso), aunque se
    // haya llegado por el Menú Principal (decisión de Cristian, 2026-10-07).
    function volverAPrincipal() {
        pila.pop(null)
        irAPrincipal()
    }
    Component {
        id: opcionesComp
        Opciones {
            puente: ventana.puente
            textosJson: ventana.textosJson
            onInicioPulsado: ventana.volverAPrincipal()
            onSesionCerrada: ventana.volverAPrincipal()
            onNuevoUsuarioPulsado: ventana.abrirNuevoUsuario()
        }
    }
}
