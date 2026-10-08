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
    property var textosJson: ({})

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
    // acceso a la configuración pasa por el login o va directo a OPCIONES
    // (planeacion_opciones_parametros_ciclo.md, U-5: Inicio conserva la sesión).
    OpcionesController { id: sesionVentana }
    function abrirConfiguracion() {
        sesionVentana.refrescar()
        pila.push(sesionVentana.sesionActiva ? opcionesComp : loginComp)
    }
    // El standby (equipo desatendido) cierra la sesión: quien vuelva debe
    // iniciarla de nuevo (confirmado por Cristian, 2026-10-07).
    function cerrarSesionPorStandby() {
        if (standby?.activo)
            sesionVentana.cerrarSesion()
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
    onEstadoMaquinaChanged: aplicarEstadoMaquina()
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
                infoEquipo: ventana.infoEquipo
                textosJson: ventana.textosJson
                onPuertaPulsada: ventana.comandosPuerta?.alternar()
                onIniciarCicloPulsado: ventana.comandoCiclo?.iniciar()
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
            Login {
                anchors.fill: parent
                teclado: panelTeclado
                textosJson: ventana.textosJson
                onInicioPulsado: pila.pop()
                // sesión validada: el login se reemplaza por OPCIONES
                onSesionIniciada: pila.replace(opcionesComp)
            }
        }
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
        }
    }
}
