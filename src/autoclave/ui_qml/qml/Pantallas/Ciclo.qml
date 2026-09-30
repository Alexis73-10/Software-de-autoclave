import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Tema
import "../Componentes"

// Pantalla de ciclo (mockup-01, docs/mis_plans/planeacion_pantalla_ciclo_ui.md).
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
// acción se deshabilitan. Textos: assets/textos/es.json (textosJson).
// Modelo y serie: perfil de instalación (InfoEquipo). La campana abre el panel
// de notificaciones y el recuadro de modelo/serie el de información del equipo
// (ambos PROVISIONALES, sin diseño).
// PENDIENTE (PC-04): insignia del estado sigue con el ejemplo del mockup.
// PENDIENTE (PC-03): tipografías y activos definitivos del diseñador.
Item {
    id: raiz

    // Los inyecta Main.qml: UiBridge (solo lectura), comandos de puerta y de
    // inicio de ciclo (aquí solo se lee su estado; las acciones las conecta
    // Main), InfoEquipo y es.json.
    property QtObject puente: null
    property QtObject comandosPuerta: null
    property QtObject comandoCiclo: null
    property QtObject infoEquipo: null
    property var textosJson: ({})

    // ---- datos del backend ----
    // "?." evita TypeError si no hay puente o al destruir la pantalla
    property string programa: puente?.programa ?? ""
    property string tempEsterilizacion: puente?.tempEsterilizacion ?? ""
    property string tiempoEsterilizacion: puente?.tiempoEsterilizacion ?? ""
    property string tiempoSecado: puente?.tiempoSecado ?? ""
    property string tempCamara: puente?.tempCamara ?? ""
    property string presionCamara: puente?.presionCamara ?? ""
    property bool datosVigentes: puente?.connected ?? false
    property string cicloActivo: puente?.cicloActivo ?? ""   // "cycle_number" del ciclo (01, 02...)
    property string estadoTexto: tx("estados", puente?.estadoEquipo ?? "no_preparado")
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

    // Insignia de la campana: única categoría de notificaciones por ahora (alertas y avisos)
    property int conteoNotificaciones: conteoAlarmas
    // Perfil de instalación; "—" si no se pudo leer
    property string modelo: (infoEquipo?.modelo ?? "") || tx("sistema", "sin_lectura")
    property string serie: (infoEquipo?.serie ?? "") || tx("sistema", "sin_lectura")
    property string version: tx("app", "version")

    // ---- acciones: las resuelve quien usa la pantalla (servicios, plan §7) ----
    signal puertaPulsada()        // abrir si puertaAbierta es false, cerrar si es true
    signal iniciarCicloPulsado()
    signal avatarPulsado()        // destino indefinido (PC-05)
    signal campanaPulsada()
    signal ajustesPulsado()
    signal inicioPulsado()

    // Texto de es.json por sección y clave; "" si falta (test_ui_qml_app lo vigila).
    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }

    // Textos de la pantalla (PC-07: siguen sin confirmar por el diseñador).
    readonly property QtObject textos: QtObject {
        readonly property string cicloActivo: raiz.tx("ciclo", "activo")
        readonly property string programa: raiz.tx("ciclo", "programa")
        readonly property string estado: raiz.tx("ciclo", "estado")
        readonly property string tempEster: raiz.tx("ciclo", "temp_ester")
        readonly property string tiempoEst: raiz.tx("ciclo", "tiempo_est")
        readonly property string tiempoSec: raiz.tx("ciclo", "tiempo_sec")
        readonly property string tempCamara: raiz.tx("ciclo", "temp_camara")
        readonly property string presion: raiz.tx("ciclo", "presion")
        readonly property string unidadTemp: raiz.tx("unidades", "temperatura")
        readonly property string unidadTiempo: raiz.tx("unidades", "tiempo")
        readonly property string unidadPresion: raiz.tx("unidades", "presion")
        readonly property string alarmasTitulo: raiz.tx("ciclo", "alarmas_titulo")
        readonly property string sinAlarmas: raiz.tx("ciclo", "sin_alarmas")
        readonly property string sinConexion: raiz.tx("sistema", "sin_conexion")
        readonly property string abrirPuerta: raiz.tx("ciclo", "abrir_puerta")
        readonly property string cerrarPuerta: raiz.tx("ciclo", "cerrar_puerta")   // PC-05: sin mockup
        readonly property string iniciarCiclo: raiz.tx("modulos", "iniciar_ciclo")
        readonly property string modelo: raiz.tx("ciclo", "modelo")
        readonly property string serie: raiz.tx("ciclo", "serie")
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
        readonly property var _meses: (raiz.textosJson.fecha && raiz.textosJson.fecha.meses) || []
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
        Rectangle {
            visible: raiz.conteoNotificaciones > 0
            x: raiz.m(922); y: raiz.m(50)
            width: raiz.m(26); height: raiz.m(25); radius: width / 2
            color: raiz.paleta.insignia
            Text {
                anchors.centerIn: parent
                text: raiz.conteoNotificaciones
                color: "white"
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(17)
            }
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
    Rectangle {
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: raiz.m(1723)
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

    Rotulo { cx: 1011; text: raiz.textos.estado }
    Rectangle {
        x: raiz.m(972); y: raiz.m(256); width: raiz.m(78); height: width; radius: width / 2
        color: raiz.paleta.naranjaEstado
        Text {
            anchors.centerIn: parent
            text: "!"
            color: "white"
            font.family: raiz.fuenteNumeros
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(56)
        }
    }
    TextoNaranja { cx: 1010; text: raiz.estadoTexto }

    // ---- tarjeta de parámetros ----
    Rectangle {
        x: raiz.m(34); y: raiz.m(425); width: raiz.m(1129); height: raiz.m(208)
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.bordeSuave
    }
    Divisor { cx: 255; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
    Divisor { cx: 482; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
    Divisor { cx: 708; y0: 452; y1: 608; color: raiz.paleta.divisorParam }
    Divisor { cx: 938; y0: 452; y1: 606; color: raiz.paleta.divisorParam }

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

    Icono { caja: [73, 448, 20, 33]; tinta: raiz.tintaTermometro; source: raiz.iconosColor + "sensor_temperatura.svg" }
    Etiqueta { lx: 129; bl: 469; text: raiz.textos.tempEster }
    Valor { cx: 152; text: raiz.tempEsterilizacion }
    Unidad { cx: 151.5; text: raiz.textos.unidadTemp }

    Icono { caja: [294, 447, 35, 35]; tinta: [5.9, 5.9, 42.1, 42.1]; source: raiz.iconosColor + "sensor_tiempo.svg" }
    Etiqueta { lx: 357; bl: 467; text: raiz.textos.tiempoEst }
    Valor { cx: 371.5; text: raiz.tiempoEsterilizacion }
    Unidad { cx: 378; text: raiz.textos.unidadTiempo }

    // color/sensor_tiempo_secado.svg viene en blanco: se tiñe de gris
    IconoTenido {
        caja: [532, 446, 27, 39]; tinta: [10.05, 4.2, 37.95, 43.8]
        source: raiz.iconosColor + "sensor_tiempo_secado.svg"
        color: raiz.paleta.iconoGris
    }
    Etiqueta { lx: 588; bl: 467; text: raiz.textos.tiempoSec }
    Valor { cx: 599; text: raiz.tiempoSecado }
    Unidad { cx: 599; text: raiz.textos.unidadTiempo }

    Icono { caja: [751, 448, 20, 33]; tinta: raiz.tintaTermometro; source: raiz.iconosColor + "sensor_temperatura_2.svg" }
    Etiqueta { lx: 798; bl: 469; text: raiz.textos.tempCamara }
    Valor { cx: 830.5; text: raiz.tempCamara }
    Unidad { cx: 821.5; text: raiz.textos.unidadTemp }

    Icono { caja: [983, 450, 37, 31]; tinta: [5.3, 8.0, 43.7, 40.85]; source: raiz.iconosColor + "sensor_presion.svg" }
    Etiqueta { lx: 1051; bl: 467; text: raiz.textos.presion }
    Valor { cx: 1045.5; text: raiz.presionCamara }
    Unidad { cx: 1061; text: raiz.textos.unidadPresion }

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
    // sistema.sin_conexion va arriba y la lista (congelada) se atenúa.
    // PROVISIONAL (sin diseño de toast): el mismo aviso muestra durante 5 s el
    // motivo con que el backend rechazó el último comando de puerta.
    Item {
        id: zonaAlarmas
        x: raiz.m(81); y: raiz.m(739)
        width: raiz.m(1116 - 81); height: raiz.m(1598 - 739)

        Text {
            id: avisoSinConexion
            visible: !raiz.datosVigentes || raiz.mensajePuerta !== ""
            width: parent.width
            height: visible ? implicitHeight : 0
            topPadding: raiz.m(12)
            bottomPadding: raiz.m(12)
            text: !raiz.datosVigentes ? raiz.textos.sinConexion : raiz.mensajePuerta
            wrapMode: Text.WordWrap
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(24)
        }

        ListView {
            anchors.top: avisoSinConexion.bottom
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            opacity: raiz.datosVigentes ? 1.0 : 0.4
            model: raiz.alarmas
            delegate: Item {
                id: fila
                // roles del modelo: id, level, description, source_state, priority
                required property var model
                width: ListView.view.width
                height: raiz.m(72)

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
                    elide: Text.ElideRight
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
        visible: raiz.listoParaCiclo && raiz.datosVigentes
        enabled: !raiz.cicloOcupado
        onPulsado: raiz.iniciarCicloPulsado()

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

    // ======================= barra inferior =======================
    Rectangle {
        x: raiz.m(33); y: raiz.m(1744); width: raiz.m(1130); height: raiz.m(141)
        radius: raiz.m(26)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.bordeSuave
    }
    Divisor { cx: 347; y0: 1763; y1: 1869; color: raiz.paleta.divisorPie }
    Divisor { cx: 834; y0: 1763; y1: 1869; color: raiz.paleta.divisorPie }

    // Icono de equipo: PROVISIONAL (PC-03), no hay activo; se dibuja con contornos.
    Item {
        x: raiz.m(71); y: raiz.m(1763); width: raiz.m(80); height: raiz.m(52)
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            border.color: raiz.paleta.iconoGris; border.width: raiz.m(1.5)
        }
        Rectangle {
            x: raiz.m(42); y: raiz.m(4); width: raiz.m(18); height: raiz.m(44)
            color: "transparent"
            border.color: raiz.paleta.iconoGris; border.width: raiz.m(1.5)
        }
    }
    component TextoPie: Texto {
        lx: 70; tam: 17
        color: raiz.paleta.textoPie
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }
    TextoPie { bl: 1838; text: raiz.textos.modelo + raiz.modelo }
    TextoPie { bl: 1862; text: raiz.textos.serie + raiz.serie }
    // Tocar el recuadro de equipo (hasta el primer divisor) abre la información del equipo
    MouseArea {
        x: raiz.m(33); y: raiz.m(1744); width: raiz.m(347 - 33); height: raiz.m(141)
        onClicked: {
            raiz.infoEquipo?.actualizar()
            panelEquipo.abrir()
        }
    }

    // Avatar: deshabilitado sin conexión (PROVISIONAL: opacidad 0.4)
    Item {
        anchors.fill: parent
        enabled: raiz.datosVigentes
        opacity: enabled ? 1.0 : 0.4
        Rectangle {
            x: raiz.m(550); y: raiz.m(1762); width: raiz.m(88); height: width; radius: width / 2
            color: raiz.paleta.avatarFondo
        }
        Icono {
            caja: [576, 1784, 36, 44]; tinta: [7.55, 4.2, 40.45, 43.95]
            source: raiz.iconosColor + "usuario.svg"
        }
        MouseArea {
            x: raiz.m(550); y: raiz.m(1762); width: raiz.m(88); height: width
            onClicked: raiz.avatarPulsado()
        }
    }

    // color/casa.svg trae #333333; el mockup mide #232323 (diferencia menor, se usa el activo)
    Icono {
        caja: [957, 1769, 88, 77]; tinta: [4.1, 6.8, 43.9, 41.4]
        source: raiz.iconosColor + "casa.svg"
    }
    MouseArea {
        x: raiz.m(940); y: raiz.m(1755); width: raiz.m(122); height: raiz.m(105)
        onClicked: raiz.inicioPulsado()
    }
    Text {
        x: raiz.m(1141) - width
        y: raiz.m(1867) - baselineOffset
        text: raiz.version
        color: raiz.paleta.versionTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(20)
    }

    // ======================= paneles (PROVISIONALES) =======================
    PanelNotificaciones {
        id: panelNotificaciones
        titulo: raiz.tx("notificaciones", "titulo")
        textoCerrar: raiz.tx("acciones", "cerrar")
        rotuloAlertas: raiz.tx("notificaciones", "alertas_avisos")
        textoSinAlarmas: raiz.textos.sinAlarmas
        alarmas: raiz.alarmas
    }
    PanelEquipo {
        id: panelEquipo
        titulo: raiz.tx("equipo", "titulo")
        textoCerrar: raiz.tx("acciones", "cerrar")
        filas: raiz.infoEquipo?.filas ?? []
        textosEquipo: raiz.textosJson.equipo ?? ({})
        sinLectura: raiz.tx("sistema", "sin_lectura")
    }
}
