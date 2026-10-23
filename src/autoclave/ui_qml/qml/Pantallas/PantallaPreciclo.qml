import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Tema
import "../Componentes"
import Autoclave.I18n

// Pantalla previa al inicio del ciclo (mockup-01, docs/mis_plans/planeacion_pantalla_ciclo_ui.md).
// Antes Ciclo.qml; renombrada a PantallaPreciclo (planeacion_pantalla_ciclo_en_curso.md 14.7)
// para no confundirla con PantallaCicloEnCurso.
// Referencia: images/pantalla_ciclo_sin_grafica.png (1196 x 1917).
//
// Geometría: todas las medidas son px del lienzo del mockup (1196 x 1917) y pasan
// por m(), que escala uniformemente con el ancho real (plan §2: s = ancho / 1196).
// No se usa Escala.px() porque el lienzo de Escala es 1200 x 1920 y el mockup se
// midió a 1196 x 1917; con m() la pantalla coincide al píxel con la referencia.
//
// Datos: número y nombre del ciclo, estado, tarjeta de parámetros, puerta y
// alarmas vienen del puente de solo lectura UiBridge (bridge/ui_bridge.py), que
// lee el caché de UIServiceBackend. Sin conexión, los valores quedan congelados
// y en gris (no vigentes, planeacion_ui_dual_pantalla.md §6.4) y los botones de
// acción se deshabilitan. Textos: singleton I18n (autoclave/i18n).
// Modelo y serie: perfil de instalación (InfoEquipo). La campana abre el panel
// de notificaciones y el recuadro de modelo/serie el de información del equipo
// (ambos PROVISIONALES, sin diseño).
// Insignia del estado: check verde en "Listo"; "!" naranja en el resto (PC-04).
// PENDIENTE (PC-03): tipografías y activos definitivos del diseñador.
Item {
    id: raiz

    // Los inyecta Main.qml: UiBridge (solo lectura), comandos de puerta y de
    // inicio de ciclo (aquí solo se lee su estado; las acciones las conecta
    // Main), InfoEquipo y es.json.
    property QtObject puente: null
    property QtObject comandosPuerta: null
    property QtObject comandoCiclo: null
    // selectorCiclo: cambio de programa tocando el recuadro "Programa" (B6, tanda 4)
    property QtObject selectorCiclo: null
    // comandoFalla: botón RECONOCER FALLA (T-16), visible solo en FALLA
    property QtObject comandoFalla: null
    property QtObject infoEquipo: null
    // ComandosSistema (E5): Apagar equipo en el panel de equipo
    property QtObject comandosSistema: null

    // ---- datos del backend ----
    // "?." evita TypeError si no hay puente o al destruir la pantalla
    property string programa: puente?.programa ?? ""
    property string tempEsterilizacion: puente?.tempEsterilizacion ?? ""
    property string tiempoEsterilizacion: puente?.tiempoEsterilizacion ?? ""
    property string tiempoSecado: puente?.tiempoSecado ?? ""
    property string tempCamara: puente?.tempCamara ?? ""
    property string tempReferencia: puente?.tempReferencia ?? ""
    property string presionCamara: puente?.presionCamara ?? ""
    // O3 (tanda 6): entradas mostradas del programa; sin puente, las tres de siempre
    property var entradas: puente?.entradasMostradas ?? [
        { clave: "temp_camara", tipo: "temp", valor: tempCamara, unidad: textos.unidadTemp },
        { clave: "temp_referencia", tipo: "temp", valor: tempReferencia, unidad: textos.unidadTemp },
        { clave: "pres_camara", tipo: "pres", valor: presionCamara, unidad: textos.unidadPresion },
    ]
    property bool datosVigentes: puente?.connected ?? false
    // U4 (tanda 2): estado de la tarjeta de E/S ("desconectada",
    // "sin_tramas_validas" u "ok"); solo cambia textos, no bloquea la pantalla
    readonly property string estadoTarjeta: puente?.estadoTarjeta ?? "ok"
    property string cicloActivo: puente?.cicloActivo ?? ""   // "cycle_number" del ciclo (01, 02...)
    property string estadoTexto: I18n.t("estados." + (puente?.estadoEquipo ?? "no_preparado"), I18n.lang)
    // Insignia de ESTADO: check verde si el equipo está listo (decisión de
    // Cristian, 2026-10-01); "!" naranja en los demás estados.
    readonly property bool estadoListo: (puente?.estadoEquipo ?? "") === "listo"
    property int puerta: puente?.door ?? 1
    // ABIERTO/ABRIENDO -> "abierta" (acción: cerrar); regla en UiBridge.doorOpen,
    // la misma que usa ComandosPuerta para decidir qué comando enviar.
    property bool puertaAbierta: puente?.doorOpen ?? false
    property bool puertaOcupada: comandosPuerta?.ocupado ?? false
    property string mensajePuerta: comandosPuerta?.mensaje ?? ""   // motivo de rechazo del backend
    // Modelo de alarmas activas (roles: id, level, description, source_state, priority)
    property var alarmas: puente?.alarms ?? null
    readonly property int conteoAlarmas: alarmas?.count ?? 0
    // Misma bandera que _upd_listo de tkinter; sin ella el botón INICIAR CICLO desaparece
    property bool listoParaCiclo: puente?.listoParaCiclo ?? false
    property bool cicloOcupado: comandoCiclo?.ocupado ?? false
    // T-16 (§5.9, decisión 22): sin rol, solo con la máquina en FALLA
    readonly property bool enFalla: (puente?.machineState ?? "") === "FALLA"
    // B6 (tanda 4) y D8-5.1 (tanda 8): el programa se puede cambiar en
    // PREPARACION, PREPARADO y FALLA (decisión del 19-oct), sin paro ni modo
    // prueba, AUNQUE no haya datos vigentes de la tarjeta (Cristian, 22-oct
    // 12:08: elegir un programa no acciona nada). S9 (tanda 9, D9-1.3): también
    // con el estado seguro activo (la seguridad sigue usando el programa del
    // protocolo). En ciclo en curso NO. El backend vuelve a decidirlo (POST
    // /cycle/select) y su motivo se muestra en la ventana.
    readonly property string motivoNoTocable: {
        const m = puente?.machineState ?? ""
        if (m === "CICLO")
            return "selector_ciclo.motivo_ciclo_en_curso"
        if (puente?.paroActivo ?? false)
            return "selector_ciclo.motivo_paro"
        if (puente?.modoPrueba ?? false)
            return "selector_ciclo.motivo_modo_prueba"
        if (m !== "PREPARACION" && m !== "PREPARADO" && m !== "FALLA")
            return "selector_ciclo.motivo_estado"
        return ""
    }
    readonly property bool programaTocable: selectorCiclo !== null && motivoNoTocable === ""
    property bool fallaOcupada: comandoFalla?.ocupado ?? false

    // Insignia de la campana: alarmas activas más los avisos de seguridad del
    // panel (paro, estado seguro, NO ABRIR, modo prueba; U1 de la tanda 2)
    property int conteoNotificaciones: panelNotificaciones.conteoTotal
    // Perfil de instalación; "—" si no se pudo leer
    property string modelo: (infoEquipo?.modelo ?? "") || I18n.t("sistema.sin_lectura", I18n.lang)
    property string serie: (infoEquipo?.serie ?? "") || I18n.t("sistema.sin_lectura", I18n.lang)
    property string version: I18n.t("app.version", I18n.lang)

    // ---- acciones: las resuelve quien usa la pantalla (servicios, plan §7) ----
    signal puertaPulsada()        // abrir si puertaAbierta es false, cerrar si es true
    signal iniciarCicloPulsado()
    // T8 (§7.6): sin base de datos, tras confirmar "Continuar sin registro"
    signal iniciarSinRegistroPulsado()
    signal reconocerFallaPulsado()
    signal avatarPulsado()        // destino indefinido (PC-05)
    signal campanaPulsada()
    signal ajustesPulsado()
    signal equipoPulsado()        // B1: celda de equipo de la barra (abre el panel de equipo)

    // Textos de la pantalla (PC-07: siguen sin confirmar por el diseñador).
    readonly property QtObject textos: QtObject {
        readonly property string cicloActivo: I18n.t("ciclo.activo", I18n.lang)
        readonly property string programa: I18n.t("ciclo.programa", I18n.lang)
        readonly property string estado: I18n.t("ciclo.estado", I18n.lang)
        readonly property string tempEster: I18n.t("ciclo.temp_ester", I18n.lang)
        readonly property string tiempoEst: I18n.t("ciclo.tiempo_est", I18n.lang)
        readonly property string tiempoSec: I18n.t("ciclo.tiempo_sec", I18n.lang)
        readonly property string tempCamara: I18n.t("ciclo.temp_camara", I18n.lang)
        readonly property string tempReferencia: I18n.t("ciclo.temp_referencia", I18n.lang)
        readonly property string presion: I18n.t("ciclo.presion", I18n.lang)
        readonly property string unidadTemp: raiz.puente?.tempUnidad || I18n.t("unidades.temperatura", I18n.lang)   // I2: unidad elegida (U1)
        readonly property string unidadTiempo: I18n.t("unidades.tiempo", I18n.lang)
        readonly property string unidadPresion: raiz.puente?.presionUnidad || I18n.t("unidades.presion", I18n.lang)
        readonly property string alarmasTitulo: I18n.t("ciclo.alarmas_titulo", I18n.lang)
        readonly property string sinAlarmas: I18n.t("ciclo.sin_alarmas", I18n.lang)
        readonly property string sinConexion: I18n.t("sistema.sin_conexion", I18n.lang)
        readonly property string abrirPuerta: I18n.t("ciclo.abrir_puerta", I18n.lang)
        readonly property string cerrarPuerta: I18n.t("ciclo.cerrar_puerta", I18n.lang)   // PC-05: sin mockup
        readonly property string iniciarCiclo: I18n.t("modulos.iniciar_ciclo", I18n.lang)
        readonly property string reconocerFalla: I18n.t("modulos.reconocer_falla", I18n.lang)
        readonly property string modelo: I18n.t("ciclo.modelo", I18n.lang)
        readonly property string serie: I18n.t("ciclo.serie", I18n.lang)
    }

    // Colores medidos sobre el mockup. PENDIENTE: promover a Tema/Colores.qml
    // cuando el diseñador los confirme; se dejan aquí para no tocar el tema.
    readonly property QtObject paleta: QtObject {
        readonly property color negro: "#000000"
        readonly property color programa: "#000209"
        readonly property color naranjaTexto: "#EC9233"
        readonly property color naranjaEstado: "#FF962B"
        readonly property color verdeEjecutando: "#25BA9E"
        readonly property color insignia: "#08C9F9"
        readonly property color bordeTarjeta: "#E5E5E5"
        readonly property color bordeSuave: "#F5F5F5"
        readonly property color divisorCiclo: "#C0C0C0"
        readonly property color divisorParam: "#C3C3C3"
        readonly property color divisorPie: "#BEBEBE"
        readonly property color lineaAlarmas: "#D7D7D7"
        readonly property color tituloAlarmas: "#010006"
        readonly property color textoVacio: "#969BA0"
        readonly property color etiqueta: "#393939"
        readonly property color unidad: "#424242"
        readonly property color textoPie: "#3B3B3B"
        readonly property color versionTexto: "#8F8F8F"
        readonly property color avatarFondo: "#E6E6E6"
        readonly property color iconoGris: "#808080"
    }

    // Sustitutos (PC-03): Poppins no está disponible, se usa Montserrat
    // (Tipografia.familia); "sans tipo Arial" se resuelve con Arial del sistema.
    readonly property string fuenteNumeros: "Arial"

    readonly property real anchoMockup: 1196
    function m(v) { return v * raiz.width / anchoMockup }
    // pixelSize exige entero > 0 (width es 0 antes del primer layout)
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    readonly property string iconosColor: "../../assets/iconos/color/"
    readonly property string imagenes: "../../../images/"

    // Texto ubicado por línea base (bl) y por centro (cx) o borde izquierdo (lx),
    // todo en px del mockup: las cajas del plan son de tinta, no de caja de texto.
    component Texto: Text {
        property real cx: -1
        property real lx: -1
        property real bl: 0
        property real tam: 16
        font.pixelSize: raiz.fuente(tam)
        x: lx >= 0 ? raiz.m(lx) : raiz.m(cx) - width / 2
        y: raiz.m(bl) - baselineOffset
    }

    // Icono SVG de 48x48 ubicado para que su tinta llene la caja del mockup.
    // tinta = [x0, y0, x1, y1] de la tinta dentro del viewBox (medido con QSvgRenderer).
    component Icono: Image {
        property var caja: [0, 0, 0, 0]
        property var tinta: [0, 0, 48, 48]
        readonly property real _escala: raiz.m(caja[3]) / (tinta[3] - tinta[1])
        width: 48 * _escala
        height: width
        x: raiz.m(caja[0] + caja[2] / 2) - (tinta[0] + tinta[2]) / 2 * _escala
        y: raiz.m(caja[1]) - tinta[1] * _escala
        sourceSize.width: width
        sourceSize.height: height
    }

    // Icono recoloreado con MultiEffect (la fuente se oculta). Con fuente blanca,
    // colorization 1.0 la lleva al color pedido.
    component IconoTenido: Item {
        id: tenido
        property alias caja: fuente.caja
        property alias tinta: fuente.tinta
        property alias source: fuente.source
        property color color: "white"
        anchors.fill: parent
        Icono { id: fuente; visible: false }
        MultiEffect {
            x: fuente.x; y: fuente.y; width: fuente.width; height: fuente.height
            source: fuente
            colorization: 1.0
            colorizationColor: tenido.color
        }
    }

    component Divisor: Rectangle {
        property real cx: 0
        property real y0: 0
        property real y1: 0
        x: raiz.m(cx - 1); y: raiz.m(y0)
        width: raiz.m(2); height: raiz.m(y1 - y0)
    }

    // ======================= fondo =======================
    FondoApp { anchors.fill: parent }

    // ======================= cabecera =======================
    Image {
        x: raiz.m(73); y: raiz.m(57)
        width: raiz.m(267)
        height: width * 42427 / 158611   // proporción del viewBox del SVG
        source: "../../assets/logo/logo-especifika-blanco.svg"
        sourceSize.width: width
        sourceSize.height: height
    }

    Item {
        id: reloj
        anchors.fill: parent
        // mismo formato manual que BarraSuperior (sin depender de Qt.locale)
        readonly property var _meses: I18n.valor("fecha.meses", I18n.lang) || []
        property date _ahora: new Date()
        Timer { interval: 1000; running: true; repeat: true; onTriggered: reloj._ahora = new Date() }
        function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

        Texto {
            cx: 597.5; bl: 108; tam: 97
            text: reloj._dosDigitos(reloj._ahora.getHours()) + ":" +
                  reloj._dosDigitos(reloj._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familiaReloj
            font.weight: Tipografia.pesoBold
        }
        Texto {
            cx: 598; bl: 141; tam: 26
            text: reloj._ahora.getDate() + " " +
                  (reloj._meses[reloj._ahora.getMonth()] ?? "") + "  -  " +
                  reloj._ahora.getFullYear()
            color: "white"
            font.family: Tipografia.familiaReloj
        }
    }

    Item {
        anchors.fill: parent
        Icono {
            caja: [888, 64, 51, 57]; tinta: [5.85, 4.0, 42.15, 44.0]
            source: raiz.iconosColor + "campana.svg"   // variante blanca
        }
        InsigniaCampana {
            objectName: "insigniaCampana"
            x: raiz.m(922); y: raiz.m(50)
            width: raiz.m(26); height: raiz.m(25)
            conteo: raiz.conteoNotificaciones
            urgente: panelNotificaciones.urgente
            enCurso: panelNotificaciones.avisoEnCurso
            parpadeo: panelNotificaciones.parpadeo
            colorNormal: raiz.paleta.insignia
            tamFuente: raiz.fuente(17)
        }
        MouseArea {
            x: raiz.m(870); y: raiz.m(40); width: raiz.m(90); height: raiz.m(95)
            onClicked: { raiz.campanaPulsada(); panelNotificaciones.abrir() }
        }

        Icono {
            caja: [1043, 64, 57, 58]; tinta: [4.0, 4.0, 44.0, 44.0]
            source: raiz.iconosColor + "engranaje.svg"   // variante blanca
        }
        MouseArea {
            x: raiz.m(1025); y: raiz.m(45); width: raiz.m(95); height: raiz.m(95)
            onClicked: raiz.ajustesPulsado()
        }
    }

    // ======================= panel principal =======================
    // B1: termina sobre la barra flotante. Margen de 10 px (no 30 como en
    // Opciones) porque los botones ABRIR PUERTA / INICIAR CICLO llegan a y 1725
    // del lienzo y no se reubican (D-19: no refactorizar el resto).
    Rectangle {
        id: tarjetaPrincipal
        objectName: "tarjetaPreciclo"
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: barraInferior.y - raiz.m(10) - y
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
    }

    // ---- tarjeta de ciclo ----
    Rectangle {
        x: raiz.m(19); y: raiz.m(404); width: raiz.m(1159); height: raiz.m(2)
        color: raiz.paleta.bordeTarjeta
    }
    Divisor { cx: 351; y0: 219; y1: 384; color: raiz.paleta.divisorCiclo }
    Divisor { cx: 839; y0: 219; y1: 384; color: raiz.paleta.divisorCiclo }

    component Rotulo: Texto {
        bl: 229; tam: 17
        color: raiz.paleta.negro
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
    }
    component TextoNaranja: Texto {
        bl: 375; tam: 22
        color: raiz.paleta.naranjaTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }

    Rotulo { cx: 199; text: raiz.textos.cicloActivo }
    Texto {
        cx: 200; bl: 333; tam: 103
        text: raiz.cicloActivo
        color: raiz.datosVigentes ? raiz.paleta.negro : Colores.textoGuia
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }

    Rotulo { cx: 599.5; text: raiz.textos.programa }
    Texto {
        cx: 599; bl: 308; tam: 36
        text: raiz.programa
        color: raiz.datosVigentes ? raiz.paleta.programa : Colores.textoGuia
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
    }

    // B6 (tanda 4): el recuadro del programa abre el selector de ciclo
    Texto {
        objectName: "ayudaCambiarCiclo"
        visible: raiz.programaTocable
        cx: 599; bl: 352; tam: 16
        text: I18n.t("selector_ciclo.ayuda", I18n.lang)
        color: Colores.textoGuia
        font.family: Tipografia.familia
    }
    // D8-5.1: el recuadro "Programa" y el número del ciclo responden SIEMPRE:
    // si hoy no se puede cambiar, la ventana se abre con el motivo (catálogo)
    // y la lista inactiva; nunca deja de responder en silencio.
    MouseArea {
        objectName: "zonaProgramaTocable"
        enabled: raiz.selectorCiclo !== null
        x: raiz.m(351); y: raiz.m(219); width: raiz.m(488); height: raiz.m(165)
        onClicked: ventanaSelectorCiclo.abrir()
    }
    MouseArea {
        objectName: "zonaNumeroTocable"
        enabled: raiz.selectorCiclo !== null
        x: raiz.m(34); y: raiz.m(219); width: raiz.m(317); height: raiz.m(165)
        onClicked: ventanaSelectorCiclo.abrir()
    }

    Rotulo { cx: 1011; text: raiz.textos.estado }
    Rectangle {
        x: raiz.m(972); y: raiz.m(256); width: raiz.m(78); height: width; radius: width / 2
        color: raiz.estadoListo ? raiz.paleta.verdeEjecutando : raiz.paleta.naranjaEstado
        // confirmar.svg es oscuro: brightness 1.0 lo lleva a blanco
        Image {
            id: checkListo
            visible: false
            anchors.centerIn: parent
            width: raiz.m(62); height: width
            source: raiz.iconosColor + "confirmar.svg"
            sourceSize.width: width; sourceSize.height: height
        }
        MultiEffect {
            visible: raiz.estadoListo
            anchors.fill: checkListo
            source: checkListo
            brightness: 1.0
        }
        Text {
            visible: !raiz.estadoListo
            anchors.centerIn: parent
            text: "!"
            color: "white"
            font.family: raiz.fuenteNumeros
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(56)
        }
    }
    TextoNaranja {
        cx: 1010; text: raiz.estadoTexto
        color: raiz.estadoListo ? raiz.paleta.verdeEjecutando : raiz.paleta.naranjaTexto
    }

    // ---- tarjeta de parámetros ----
    Rectangle {
        x: raiz.m(34); y: raiz.m(425); width: raiz.m(1129); height: raiz.m(208)
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.bordeSuave
    }
    // 6 columnas iguales (1129/6 ≈ 188 px): 3 parámetros de ciclo y 3 sensores.
    // Valor y unidad centrados en la columna; icono y etiqueta desplazados como grupo.
    Divisor { cx: 222.2; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
    Divisor { cx: 410.3; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
    Divisor { cx: 598.5; y0: 452; y1: 608; color: raiz.paleta.divisorParam }
    Divisor { cx: 786.7; y0: 452; y1: 606; color: raiz.paleta.divisorParam }
    Divisor { cx: 974.8; y0: 452; y1: 606; color: raiz.paleta.divisorParam }

    component Etiqueta: Texto {
        tam: 12
        color: raiz.paleta.etiqueta
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }
    component Valor: Texto {
        bl: 554; tam: 55
        color: raiz.datosVigentes ? raiz.paleta.negro : Colores.textoGuia
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }
    component Unidad: Texto {
        bl: 606; tam: 27
        color: raiz.paleta.unidad
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }

    readonly property var tintaTermometro: [12.25, 4.0, 36.55, 44.0]

    Icono { caja: [59.1, 448, 20, 33]; tinta: raiz.tintaTermometro; source: raiz.iconosColor + "sensor_temperatura.svg" }
    Etiqueta { lx: 115.1; bl: 469; text: raiz.textos.tempEster }
    Valor { cx: 128.1; text: raiz.tempEsterilizacion }
    Unidad { cx: 127.6; text: raiz.textos.unidadTemp }

    Icono { caja: [246.7, 447, 35, 35]; tinta: [5.9, 5.9, 42.1, 42.1]; source: raiz.iconosColor + "sensor_tiempo.svg" }
    Etiqueta { lx: 309.7; bl: 467; text: raiz.textos.tiempoEst }
    Valor { cx: 316.2; text: raiz.tiempoEsterilizacion }
    Unidad { cx: 322.7; text: raiz.textos.unidadTiempo }

    // color/sensor_tiempo_secado.svg viene en blanco: se tiñe de gris
    IconoTenido {
        caja: [437.4, 446, 27, 39]; tinta: [10.05, 4.2, 37.95, 43.8]
        source: raiz.iconosColor + "sensor_tiempo_secado.svg"
        color: raiz.paleta.iconoGris
    }
    Etiqueta { lx: 493.4; bl: 467; text: raiz.textos.tiempoSec }
    Valor { cx: 504.4; text: raiz.tiempoSecado }
    Unidad { cx: 504.4; text: raiz.textos.unidadTiempo }

    // O3 (tanda 6): las entradas mostradas del programa (1 a 3, UiBridge.entradasMostradas)
    // en las 3 columnas de la derecha, en la unidad vigente; "—" si no hay lectura o
    // el sensor está "No en uso" en el programa.
    Repeater {
        model: raiz.entradas
        delegate: Item {
            id: entrada
            required property var modelData
            required property int index
            readonly property real c0: [598.5, 786.7, 974.8][entrada.index] || 0
            readonly property bool esPresion: entrada.modelData.tipo === "pres"
            anchors.fill: parent
            visible: entrada.index < 3
            Icono {
                visible: !entrada.esPresion
                caja: [entrada.c0 + 26.6, 448, 20, 33]; tinta: [12.25, 4.0, 36.55, 44.0]
                source: raiz.iconosColor + "sensor_temperatura_2.svg"
            }
            Icono {
                visible: entrada.esPresion
                caja: [entrada.c0 + 31.6, 450, 37, 31]; tinta: [5.3, 8.0, 43.7, 40.85]
                source: raiz.iconosColor + "sensor_presion.svg"
            }
            Etiqueta {
                lx: entrada.c0 + (entrada.esPresion ? 99.6 : 73.6); bl: entrada.esPresion ? 467 : 469
                text: I18n.t("ciclo.entrada_corta_" + entrada.modelData.clave, I18n.lang)
            }
            Valor { cx: entrada.c0 + 94.1; text: entrada.modelData.valor }
            Unidad { cx: entrada.c0 + (entrada.esPresion ? 109.6 : 85.1); text: entrada.modelData.unidad || "" }
        }
    }

    // ---- tarjeta de alarmas y avisos ----
    Rectangle {
        x: raiz.m(34); y: raiz.m(655); width: raiz.m(1130); height: raiz.m(944)
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.bordeTarjeta
    }
    Texto {
        lx: 81; bl: 717; tam: 27
        text: raiz.textos.alarmasTitulo
        color: raiz.paleta.tituloAlarmas
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
    }
    Rectangle {
        x: raiz.m(81); y: raiz.m(737); width: raiz.m(1116 - 81); height: raiz.m(2)
        color: raiz.paleta.lineaAlarmas
    }
    // Zona del listado (PC-06): geometría fija, se puebla sin moverla.
    // PROVISIONAL (PC-06, sin diseño de fila): barra de color por prioridad
    // IEC 60601-1-8 (Colores.alarma*) + descripción. Sin conexión, el aviso
    // sistema.sin_conexion va arriba y la lista (congelada) se atenúa; con la
    // tarjeta desconectada o sin datos, el aviso lo dice (U4).
    // U4 (tanda 2): arriba de la lista, las filas de seguridad compartidas con
    // el panel de la campana (SeccionEstadoSeguro): tarjeta desconectada o sin
    // datos, paro real, estado seguro pendiente con el botón "Confirmar y
    // llevar a estado seguro" (sin sesión), en curso, NO ABRIR y modo prueba.
    // PROVISIONAL (sin diseño de toast): el mismo aviso muestra durante 5 s el
    // motivo con que el backend rechazó el último comando de puerta.
    Item {
        id: zonaAlarmas
        x: raiz.m(81); y: raiz.m(739)
        width: raiz.m(1116 - 81); height: raiz.m(1598 - 739)

        Text {
            id: avisoSinConexion
            objectName: "avisoSinConexion"
            visible: !raiz.datosVigentes || raiz.estadoTarjeta !== "ok" || raiz.mensajePuerta !== ""
            width: parent.width
            height: visible ? implicitHeight : 0
            topPadding: raiz.m(12)
            bottomPadding: raiz.m(12)
            text: !raiz.datosVigentes ? raiz.textos.sinConexion
                : raiz.estadoTarjeta === "desconectada"
                  ? I18n.t("sistema.tarjeta_desconectada_valores", I18n.lang)
                : raiz.estadoTarjeta !== "ok"
                  ? I18n.t("sistema.tarjeta_sin_datos_valores", I18n.lang)
                : raiz.mensajePuerta
            wrapMode: Text.WordWrap
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(24)
        }

        // Fijas arriba, fuera de la lista: no se desplazan con ella
        // (revisión SAF-04 de U4)
        SeccionEstadoSeguro {
            id: seguridadPreciclo
            objectName: "seguridadPreciclo"
            anchors.top: avisoSinConexion.bottom
            width: parent.width
            puente: raiz.puente
            comandos: raiz.comandosSistema
            bottomPadding: conteo > 0 ? raiz.m(12) : 0
        }

        ListView {
            id: listaAlarmas
            objectName: "listaAlarmasPreciclo"
            anchors.top: seguridadPreciclo.bottom
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            model: raiz.alarmas
            delegate: Item {
                id: fila
                // roles del modelo: id, level, description, source_state, priority
                required property var model
                width: ListView.view.width
                height: raiz.m(72)
                // la lista congelada se atenúa sin conexión; las filas de
                // seguridad no
                opacity: raiz.datosVigentes ? 1.0 : 0.4

                Rectangle {
                    x: 0; y: raiz.m(12)
                    width: raiz.m(12); height: fila.height - raiz.m(24)
                    radius: raiz.m(3)
                    color: fila.model.priority === "media" ? Colores.alarmaMedia
                         : fila.model.priority === "baja"  ? Colores.alarmaBaja
                         : Colores.alarmaAlta
                }
                Text {
                    x: raiz.m(32)
                    width: fila.width - x
                    anchors.verticalCenter: parent.verticalCenter
                    text: fila.model.description !== "" ? fila.model.description : fila.model.id
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(24)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: fila.width; height: raiz.m(1)
                    color: raiz.paleta.lineaAlarmas
                }
            }
        }
    }
    Texto {
        visible: raiz.conteoAlarmas === 0 && raiz.datosVigentes
                 && seguridadPreciclo.conteo === 0
        cx: 598.5; bl: 1176; tam: 28
        text: raiz.textos.sinAlarmas
        color: raiz.paleta.textoVacio
        font.family: Tipografia.familia
    }

    // ======================= fila de botones =======================
    component BotonAccion: Item {
        id: boton
        property var caja: [0, 0, 0, 0]
        property color colorArriba
        property color colorAbajo
        property string texto: ""
        property real textoX: 0            // x absoluta del mockup donde empieza el texto
        property real circuloX: 0          // x absoluta del mockup del círculo de contorno
        property alias contenidoCirculo: circulo.data
        signal pulsado()

        // Sin conexión: deshabilitado (PROVISIONAL, sin diseño: opacidad 0.4)
        enabled: raiz.datosVigentes
        opacity: enabled ? 1.0 : 0.4

        x: raiz.m(caja[0]); y: raiz.m(caja[1])
        width: raiz.m(caja[2]); height: raiz.m(caja[3])

        Rectangle {
            id: cuerpo
            anchors.fill: parent
            radius: raiz.m(14)
            gradient: Gradient {
                GradientStop { position: 0.0; color: boton.colorArriba }
                GradientStop { position: 1.0; color: boton.colorAbajo }
            }
            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: "#40000000"
                shadowVerticalOffset: raiz.m(3)
                shadowBlur: 0.4
            }
        }
        Rectangle {
            id: circulo
            x: raiz.m(boton.circuloX - boton.caja[0])
            y: raiz.m(1629) - boton.y
            width: raiz.m(84); height: width; radius: width / 2
            color: "transparent"
            border.color: "white"; border.width: raiz.m(4)
        }
        Text {
            x: raiz.m(boton.textoX) - boton.x
            y: raiz.m(1676) - boton.y - baselineOffset
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoMedium
            font.pixelSize: raiz.fuente(17)
        }
        MouseArea { anchors.fill: parent; onClicked: boton.pulsado() }
    }

    // Degradados medidos a x=310 / x=1010 (plan §6.1–6.2), extrapolados linealmente
    // a los bordes del cuerpo.
    BotonAccion {
        caja: [41, 1615, 298, 110]
        colorArriba: Qt.rgba(47/255, 88/255, 251/255, 1)
        colorAbajo: Qt.rgba(0, 0, 73/255, 1)
        texto: raiz.puertaAbierta ? raiz.textos.cerrarPuerta : raiz.textos.abrirPuerta
        textoX: 172
        circuloX: 64
        // además de sin conexión, deshabilitado mientras hay un comando en curso
        enabled: raiz.datosVigentes && !raiz.puertaOcupada
        onPulsado: raiz.puertaPulsada()

        // PROVISIONAL (PC-03): PNG de puerta del UI anterior, aclarado a blanco.
        contenidoCirculo: [
        Image {
            id: imgPuerta
            anchors.centerIn: parent
            height: raiz.m(42); width: height * 607 / 992
            source: raiz.imagenes + (raiz.puertaAbierta ? "close_door_" : "open_door_") + raiz.puerta + ".png"
            // recortes = caja de tinta de cada PNG (1920x1080), medida con PIL getbbox()
            sourceClipRect: raiz.puerta === 2
                ? (raiz.puertaAbierta ? Qt.rect(653, 37, 603, 962) : Qt.rect(647, 22, 615, 992))
                : (raiz.puertaAbierta ? Qt.rect(670, 37, 598, 962) : Qt.rect(665, 22, 607, 992))
            visible: false
        },
        MultiEffect {
            anchors.fill: imgPuerta
            source: imgPuerta
            brightness: 1.0
        }
        ]
    }

    BotonAccion {
        caja: [845, 1616, 302, 110]
        colorArriba: Qt.rgba(8/255, 170/255, 65/255, 1)
        colorAbajo: Qt.rgba(1/255, 80/255, 30/255, 1)
        texto: raiz.textos.iniciarCiclo
        textoX: 980
        circuloX: 866
        // Como tkinter (_upd_listo) pero oculto en vez de inactivo cuando el equipo
        // no está listo; mientras se envía la orden no acepta otro toque.
        visible: raiz.listoParaCiclo && raiz.datosVigentes && !raiz.enFalla
        enabled: !raiz.cicloOcupado
        onPulsado: {
            if (raiz.puente?.sinBaseDatos ?? false)
                confirmarSinRegistro.abrir()
            else
                raiz.iniciarCicloPulsado()
        }

        // triángulo "play", desplazado a la derecha por compensación óptica
        contenidoCirculo: Shape {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: raiz.m(3)
            width: raiz.m(30); height: raiz.m(34)
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeWidth: 0
                fillColor: "white"
                startX: 0; startY: 0
                PathLine { x: raiz.m(30); y: raiz.m(17) }
                PathLine { x: 0; y: raiz.m(34) }
                PathLine { x: 0; y: 0 }
            }
        }
    }

    // RECONOCER FALLA (T-16): en el lugar de INICIAR CICLO, que en FALLA no
    // aparece (el equipo no está listo). Sin rol; el backend rechaza con el
    // paro de emergencia activo. Colores PROVISIONALES (sin mockup).
    BotonAccion {
        objectName: "botonReconocerFalla"
        caja: [845, 1616, 302, 110]
        colorArriba: Qt.rgba(230/255, 120/255, 20/255, 1)
        colorAbajo: Qt.rgba(120/255, 50/255, 0, 1)
        texto: raiz.textos.reconocerFalla
        textoX: 980
        circuloX: 866
        visible: raiz.enFalla && raiz.datosVigentes
        enabled: !raiz.fallaOcupada
        onPulsado: raiz.reconocerFallaPulsado()

        contenidoCirculo: Text {
            anchors.centerIn: parent
            text: "!"
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(40)
        }
    }

    // ======================= barra inferior =======================
    // B1 (tanda 6, decisión 1.7): la misma BarraInferiorMenu flotante de
    // Opciones, fuera del panel principal y por debajo de él. Conserva las
    // funciones de hoy: equipo a la izquierda (abre la información del equipo),
    // versión al centro (mockup aprobado, pantalla 1) e iniciar sesión a la
    // derecha, en el lugar de Inicio (U2 de la tanda 2). Coordenadas de los
    // hijos relativas a la barra (lienzo 1128 x 139; origen en x 34, y 1746).
    // Modelo y serie en la celda de equipo (línea base relativa al lienzo)
    component TextoPieBarra: Text {
        property real bl: 0
        x: raiz.m(70 - 34)
        y: raiz.m(bl - 1746) - baselineOffset
        color: raiz.paleta.textoPie
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(17)
    }
    BarraInferiorMenu {
        id: barraInferior
        objectName: "barraInferiorPreciclo"
        // D8-5.2: mismo x y ancho que la tarjeta de contenido de encima
        x: tarjetaPrincipal.x
        width: tarjetaPrincipal.width
        // anclada al borde inferior como en Opciones (171 px del lienzo)
        y: parent.height - raiz.m(1917 - 1746)
        escala: raiz.m(1)
        personalizada: true
        version: ""

        // Celda izquierda: icono de equipo, modelo y serie (antes x 33..347)
        Item {
            objectName: "botonEquipoPreciclo"
            x: 0; y: 0; width: barraInferior.mx(313); height: parent.height
            // icono_autoclave.svg (viewBox 94 x 62, tinta en 5.5..85.5 x 5.5..56.5)
            Image {
                x: raiz.m(71 - 5.5 - 34); y: raiz.m(1763 - 5.5 - 1746)
                width: raiz.m(94); height: raiz.m(62)
                source: raiz.iconosColor + "icono_autoclave.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            TextoPieBarra { bl: 1838; text: raiz.textos.modelo + raiz.modelo }
            TextoPieBarra { bl: 1862; text: raiz.textos.serie + raiz.serie }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    raiz.equipoPulsado()
                    raiz.infoEquipo?.actualizar()
                    panelEquipo.abrir()
                }
            }
        }

        // Celda central: versión
        Text {
            objectName: "versionPreciclo"
            x: barraInferior.mx((313 + 800) / 2) - width / 2
            y: (parent.height - height) / 2
            text: raiz.version
            color: raiz.paleta.versionTexto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(20)
        }

        // Celda derecha: avatar (iniciar sesión). Deshabilitado sin conexión
        // (PROVISIONAL: opacidad 0.4)
        Item {
            objectName: "avatarPreciclo"
            x: barraInferior.mx(800); y: 0; width: barraInferior.mx(1128 - 800); height: parent.height
            enabled: raiz.datosVigentes
            opacity: enabled ? 1.0 : 0.4
            Rectangle {
                id: fondoAvatar
                anchors.centerIn: parent
                width: raiz.m(88); height: width; radius: width / 2
                color: raiz.paleta.avatarFondo
            }
            // usuario.svg (tinta 7.55..40.45 x 4.2..43.95 de 48): 44 de alto
            Image {
                readonly property real _e: raiz.m(44) / (43.95 - 4.2)
                width: 48 * _e; height: width
                x: fondoAvatar.x + fondoAvatar.width / 2 - (7.55 + 40.45) / 2 * _e
                y: fondoAvatar.y + fondoAvatar.height / 2 - (4.2 + 43.95) / 2 * _e
                source: raiz.iconosColor + "usuario.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.avatarPulsado() }
        }
    }

    // ======================= paneles (PROVISIONALES) =======================
    PanelNotificaciones {
        id: panelNotificaciones
        titulo: I18n.t("notificaciones.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        rotuloAlertas: I18n.t("notificaciones.alertas_avisos", I18n.lang)
        textoSinAlarmas: raiz.textos.sinAlarmas
        alarmas: raiz.alarmas
        puente: raiz.puente
        comandosSistema: raiz.comandosSistema
    }
    // T8 (§7.6), PROVISIONAL (sin diseño): confirmación explícita por ciclo
    DialogoConfirmacion {
        id: confirmarSinRegistro
        objectName: "confirmarSinRegistro"
        mensaje: I18n.t("ciclo.sin_bd_pregunta", I18n.lang)
        textoConfirmar: I18n.t("ciclo.sin_bd_continuar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { cerrar(); raiz.iniciarSinRegistroPulsado() }
    }
    // B6 (tanda 4), PROVISIONAL (sin diseño): selector de ciclo. Lista de los
    // programas habilitados; los 3 más usados primero con la marca "Más usado".
    VentanaFlotante {
        id: ventanaSelectorCiclo
        objectName: "ventanaSelectorCiclo"
        escala: raiz.m(1)
        altoTarjeta: 1100
        titulo: I18n.t("selector_ciclo.titulo", I18n.lang)
        onMostrada: {
            raiz.selectorCiclo?.limpiarMensaje()
            raiz.selectorCiclo?.cargar()
        }
        Connections {
            target: raiz.selectorCiclo
            function onElegido() { ventanaSelectorCiclo.cerrar() }
        }
        Text {
            id: avisoSelector
            objectName: "avisoSelectorCiclo"
            width: parent.width
            wrapMode: Text.WordWrap
            visible: text !== ""
            text: !raiz.selectorCiclo ? ""
                  : raiz.motivoNoTocable !== "" ? I18n.t(raiz.motivoNoTocable, I18n.lang)
                  : raiz.selectorCiclo.sinConexion ? I18n.t("selector_ciclo.sin_conexion", I18n.lang)
                  : raiz.selectorCiclo.mensaje
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(22)
        }
        ListView {
            objectName: "listaSelectorCiclo"
            anchors.top: avisoSelector.visible ? avisoSelector.bottom : parent.top
            anchors.topMargin: avisoSelector.visible ? raiz.m(12) : 0
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            spacing: raiz.m(10)
            model: raiz.selectorCiclo?.programas ?? []
            delegate: Rectangle {
                id: fila
                required property var modelData
                readonly property bool activa: raiz.programaTocable
                                               && (raiz.selectorCiclo?.seleccionable ?? false)
                                               && !(raiz.selectorCiclo?.ocupado ?? false)
                objectName: "filaCiclo_" + modelData.numero
                width: ListView.view.width
                height: raiz.m(124)
                radius: raiz.m(16)
                color: modelData.seleccionado ? "#E8F0FE" : Colores.fondoSutil
                border.width: modelData.seleccionado ? raiz.m(3) : 0
                border.color: Colores.accionPrimario
                opacity: activa ? 1.0 : 0.45
                Text {
                    x: raiz.m(24); anchors.verticalCenter: parent.verticalCenter
                    width: raiz.m(80)
                    text: fila.modelData.numero
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(54)
                }
                Column {
                    x: raiz.m(118); anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - raiz.m(118) - raiz.m(24)
                    spacing: raiz.m(4)
                    Text {
                        width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: fila.modelData.nombre
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(30)
                    }
                    Text {
                        width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: fila.modelData.parametros
                                + (fila.modelData.masUsado ? "   \u2022 " + I18n.t("selector_ciclo.mas_usado", I18n.lang) : "")
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(22)
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: fila.activa
                    onClicked: raiz.selectorCiclo.elegir(fila.modelData.cycleId)
                }
            }
        }
    }
    PanelEquipo {
        comandosSistema: raiz.comandosSistema
        id: panelEquipo
        titulo: I18n.t("equipo.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        filas: raiz.infoEquipo?.filas ?? []
        sinLectura: I18n.t("sistema.sin_lectura", I18n.lang)
    }
}
