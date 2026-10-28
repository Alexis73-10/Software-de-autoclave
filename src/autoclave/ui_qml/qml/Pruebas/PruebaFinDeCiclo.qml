pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"

// PRUEBA (tanda 21, etapa G de planeacion_fin_de_ciclo.md): muestra
// PantallaCicloEnCurso terminada y PantallaPreciclo con DATOS DE EJEMPLO para
// las capturas que se comparan con docs/diseno/mockups/fin_de_ciclo/.
// NO es parte de la navegación de producción ni se conecta al backend: solo la
// abre tests/banco/t21_capturas_fin_ciclo.py, que fija `escenario` y `fin`
// (armado en Python con ui_qml/domain/fin_de_ciclo, los mismos textos que en
// el equipo). Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 800; height: 1280
    visible: true
    color: Colores.fondoMarinoOscuro

    // "ciclo" | "preciclo"
    property string pantalla: "ciclo"
    // ciclo: "" (en curso) | "exitoso" | "cancelado" | "fallo"
    property string resultado: ""
    property var fin: ({})
    property var fases: []
    property bool ackEstadoSeguro: false
    // preciclo
    property bool conActuador: false
    property string estadoPuerta: "CERRADO"
    property bool conectado: true

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
    function _interpolar(puntos, t) {
        if (t <= puntos[0][0]) return puntos[0][1]
        for (let i = 1; i < puntos.length; i++) {
            if (t <= puntos[i][0]) {
                const a = puntos[i - 1], b = puntos[i]
                return a[1] + (b[1] - a[1]) * (t - a[0]) / (b[0] - a[0])
            }
        }
        return puntos[puntos.length - 1][1]
    }
    readonly property var _ejemplo: {
        const camara = [[0,44],[2,58],[5,85],[7,100],[9,117],[12,127],[15,130],[20,130],[22,128],
                        [25,118],[28,107],[30.3,106]]
        const ref = [[0,34],[3,52],[6,72],[9,98],[10,104],[12,113],[15,120],[19,122],[21,120],[23,113],
                     [26,98],[30.3,92]]
        const pres = [[0,18],[2,24],[4,45],[6,56],[8,58],[9,78],[11,82],[12,92],[15,90],[20,93],
                      [25,90],[28,78],[30.3,72]]
        const d = { t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] }
        for (let s = 0; s <= 1818; s += 6) {
            const t = s / 60
            d.t_min.push(t)
            d.temp_camara.push(_interpolar(camara, t))
            d.temp_ref.push(_interpolar(ref, t))
            d.pres_camara.push(_interpolar(pres, t) * 200 / 150)
        }
        return d
    }

    // Puente de solo lectura de ejemplo (las propiedades que leen las pantallas)
    QtObject {
        id: puenteEjemplo
        property bool connected: ventana.conectado
        property string estadoTarjeta: "ok"
        property string cicloActivo: ventana.pantalla === "ciclo" ? "03" : "04"
        property string programa: "BOWE & DICK"
        property string tempEsterilizacion: "134.0"
        property string tiempoEsterilizacion: ventana.pantalla === "ciclo" ? "10" : "3.5"
        property string tiempoSecado: "15"
        property string tempCamara: ventana.pantalla === "ciclo" ? "121.3" : "098.2"
        property string tempReferencia: ventana.pantalla === "ciclo" ? "118.0" : "096.4"
        property string presionCamara: ventana.pantalla === "ciclo" ? "182.5" : "084.1"
        property bool ackConfirmaEstadoSeguro: ventana.ackEstadoSeguro
        property string estadoEquipo: "no_preparado"
        property string machineState: "PREPARACION"
        property int door: 1
        property string doorState: ventana.conectado ? ventana.estadoPuerta : ""
        property bool doorOpen: doorState === "ABIERTO" || doorState === "ABRIENDO"
        property bool puertaConActuador: ventana.conActuador
        property bool listoParaCiclo: false
    }
    QtObject {
        id: comandosEjemplo
        property bool ocupado: false
        property string error: ""
        property string aviso: ""
        function cancelar() {}
        function confirmar() {}
        function descartarError() {}
    }
    QtObject {
        id: infoEjemplo
        property string modelo: "SPK-SAT 45H"
        property string serie: "Sn123456"
        property var filas: []
        function actualizar() {}
    }
    // ---------------------------------------------------------------------------

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        PantallaCicloEnCurso {
            objectName: "pantallaCiclo"
            visible: ventana.pantalla === "ciclo"
            anchors.fill: parent
            puente: puenteEjemplo
            comandos: comandosEjemplo
            infoEquipo: infoEjemplo
            conteoNotificaciones: 2
            resultado: ventana.resultado
            fin: ventana.fin
            fases: ventana.fases
            transcurridoS: 1820
            restanteS: ventana.resultado === "" ? 600 : null
            datosGrafica: ventana._ejemplo
            fasesGrafica: [
                { clave: "precalentamiento", inicioMin: 0 },
                { clave: "vacio", inicioMin: 8.85 },
                { clave: "esterilizacion", inicioMin: 20.0 },
                { clave: "secado", inicioMin: 33.9 },
            ]
            tiempoActualMin: 40
        }
        PantallaPreciclo {
            objectName: "pantallaPreciclo"
            visible: ventana.pantalla === "preciclo"
            anchors.fill: parent
            puente: ventana.pantalla === "preciclo" ? puenteEjemplo : null
            infoEquipo: null
        }
    }
}
