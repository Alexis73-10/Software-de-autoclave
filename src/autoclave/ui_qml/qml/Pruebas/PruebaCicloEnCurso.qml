pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"

// PRUEBA (Fase 2 de planeacion_pantalla_ciclo_en_curso.md): muestra
// PantallaCicloEnCurso con DATOS DE EJEMPLO que imitan el mockup
// (images/pantalla_ciclo_con_grafica_editada.png) para la revisión visual.
// NO es parte de la navegación de producción ni se conecta al backend: solo la
// abre ui_qml/prueba_ciclo_en_curso.py. Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property var textosJson: ({})

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
    // Curvas lineales por tramos trazadas a ojo sobre el mockup; una muestra por
    // segundo durante 40 min (2400 puntos, ejercita la decimación).
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
                        [25,118],[28,107],[31,106],[33,98],[34.5,94],[35.5,95],[37,73],[39,53],[40,46]]
        const ref = [[0,34],[3,52],[6,72],[9,98],[10,104],[12,113],[15,120],[19,122],[21,120],[23,113],
                     [26,98],[30,93],[33,83],[34.5,82],[35.5,95],[36.5,84],[38,80],[40,64]]
        // presión trazada en unidades del eje izquierdo (0..150) y llevada a 0..200 kPa
        const pres = [[0,18],[2,24],[4,45],[6,56],[8,58],[9,78],[11,82],[12,92],[15,90],[20,93],
                      [25,90],[28,78],[32,68],[35,57],[37,45],[38.5,34],[40,30]]
        const d = { t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] }
        for (let s = 0; s <= 2400; s++) {
            const t = s / 60
            d.t_min.push(t)
            d.temp_camara.push(_interpolar(camara, t))
            d.temp_ref.push(_interpolar(ref, t))
            d.pres_camara.push(_interpolar(pres, t) * 200 / 150)
        }
        return d
    }
    // ---------------------------------------------------------------------------

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        PantallaCicloEnCurso {
            anchors.fill: parent
            textosJson: ventana.textosJson
            // DATOS DE EJEMPLO
            cicloActivo: "03"
            programa: "BOWE & DICK"
            tempEsterilizacion: "134.0"
            tiempoEsterilizacion: "10"
            tiempoSecado: "15"
            tempCamara: "085.0"
            tempReferencia: "084.6"
            presionCamara: "100.8"
            datosVigentes: true
            conteoNotificaciones: 2
            modelo: "SPK-SAT 45H"
            serie: "Sn123456"
            fases: [
                { fase: "precalentamiento", estado: "activa" },
                { fase: "vacio", estado: "pendiente" },
                { fase: "calentamiento", estado: "pendiente" },
                { fase: "esterilizacion", estado: "pendiente" },
                { fase: "descompresion", estado: "pendiente" },
                { fase: "secado", estado: "pendiente" },
            ]
            transcurridoS: 923
            restanteS: 1477
            datosGrafica: ventana._ejemplo
            fasesGrafica: [
                { clave: "precalentamiento", inicioMin: 0 },
                { clave: "vacio", inicioMin: 8.85 },
                { clave: "esterilizacion", inicioMin: 20.0 },
                { clave: "secado", inicioMin: 33.9 },
            ]
            tiempoActualMin: 40
            cursorMin: 15.383
        }
    }
}
