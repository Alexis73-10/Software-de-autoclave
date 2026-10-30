pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"
import "../Componentes"

// PRUEBA (Fase 3 de planeacion_menu_principal_ui_qml.md): arnés del Menú
// Principal. NO es parte de la navegación de producción (Fase 4 diferida, D-11):
// lo abre ui_qml/prueba_menu_principal.py --pantalla. Con --backend recibe el
// puente real (ResumenSistema + UiBridge); sin él usa DATOS DE EJEMPLO parecidos
// a los del mockup v3 (no son lecturas reales). Mismo escalado que Main.qml.
// Las señales de la pantalla solo se registran en consola.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject puente: null
    property QtObject resumen: null
    // CiclosHistorial y AccionesCiclos: los da siempre prueba_menu_principal.py
    // (con --backend, reales; sin él, sobre el backend simulado historial_ejemplo.py)
    property QtObject historial: null
    property QtObject acciones: null
    property QtObject reporte: null
    property QtObject infoEquipo: null
    // Para capturas: ventana flotante abierta al iniciar y backend sin respuesta (ejemplo)
    property string ventanaInicial: ""
    property bool sinConexionEjemplo: false

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno)
    }
    Binding {
        target: Escala
        property: "altoLienzo"
        value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor)
    }

    // ---------------- DATOS DE EJEMPLO (no son lecturas reales) ----------------
    // Mismos roles que AlarmListModel de UiBridge: id, level, description, source_state, priority
    QtObject {
        id: puenteEjemplo
        // "id" no se admite en ListElement: se agregan con append()
        property ListModel alarms: ListModel {
            Component.onCompleted: {
                append({ id: "CHAQUETA_FRIA", level: "FALLA", description: "Chaqueta fría",
                         source_state: "PREPARADO", priority: "media" })
                append({ id: "SUMINISTRO", level: "ALERTA", description: "Revise el suministro de agua",
                         source_state: "PREPARADO", priority: "baja" })
            }
        }
    }
    QtObject {
        id: resumenEjemplo
        property bool sinConexion: ventana.sinConexionEjemplo
        readonly property string _sd: "—"
        property string ciclosTotales: sinConexion ? _sd : "1248"
        property string ciclosHoy: sinConexion ? _sd : "5"
        property string ultimoFecha: sinConexion ? _sd : "12/10/2026"
        property string ultimoHora: sinConexion ? _sd : "14:25"
        property string ultimoPrograma: sinConexion ? _sd : "02"
        property string ultimoProgramaNombre: sinConexion ? _sd : "Instrumental 134"
        property string ultimoResultado: sinConexion ? "" : "COMPLETADO"
        property string ultimoResultadoDetalle: ""
        property string ultimoOperador: _sd
        property string proximoMantenimiento: _sd
        property bool graficaUltimoDisponible: false
        property var datosGraficaUltimo: ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
        property var fasesGraficaUltimo: []

        function iniciar() {}
        function detener() {}
        // Curva de ejemplo: tramos lineales de un ciclo de 40 min, una muestra cada 6 s
        function cargarGraficaUltimo() {
            if (sinConexion) return
            const tramos = [[0, 44, 40, 30], [5, 85, 70, 45], [9, 117, 105, 120], [15, 134, 133, 304],
                            [19, 134, 134, 306], [20, 110, 112, 150], [22, 100, 104, 30],
                            [37, 95, 98, 20], [40, 60, 70, 101]]
            function interp(t, k) {
                for (let i = 1; i < tramos.length; i++) {
                    if (t <= tramos[i][0]) {
                        const a = tramos[i - 1], b = tramos[i]
                        return a[k] + (b[k] - a[k]) * (t - a[0]) / (b[0] - a[0])
                    }
                }
                return tramos[tramos.length - 1][k]
            }
            const d = { t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] }
            for (let s = 0; s <= 2400; s += 6) {
                const t = s / 60
                d.t_min.push(t)
                d.temp_camara.push(interp(t, 1))
                d.temp_ref.push(interp(t, 2))
                d.pres_camara.push(interp(t, 3))
            }
            datosGraficaUltimo = d
            fasesGraficaUltimo = [
                { clave: "precalentamiento", inicioMin: 0 }, { clave: "vacio", inicioMin: 2 },
                { clave: "calentamiento", inicioMin: 9 }, { clave: "esterilizacion", inicioMin: 15 },
                { clave: "descompresion", inicioMin: 19 }, { clave: "secado", inicioMin: 22 }]
            graficaUltimoDisponible = true
        }
    }
    // ---------------------------------------------------------------------------

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        MenuPrincipal {
            id: menu
            objectName: "menuPrincipal"
            anchors.fill: parent
            puente: ventana.puente ?? puenteEjemplo
            resumen: ventana.resumen ?? resumenEjemplo
            historial: ventana.historial
            acciones: ventana.acciones
            reporte: ventana.reporte
            teclado: panelTeclado
            infoEquipo: ventana.infoEquipo

            onIniciarSesionPulsado: console.log("MenuPrincipal: iniciar sesión")
            onAtrasPulsado: console.log("MenuPrincipal: atras")
            onInicioPulsado: console.log("MenuPrincipal: inicio")
            onMantenimientoPulsado: console.log("MenuPrincipal: próximo mantenimiento")
            onUltimoCicloPulsado: console.log("MenuPrincipal: último ciclo")
        }
        // Teclado en pantalla (correo de destino escrito a mano), como en Main.qml
        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
        }
    }

    Component.onCompleted: if (ventanaInicial !== "") menu.abrirVentana(ventanaInicial)
}
