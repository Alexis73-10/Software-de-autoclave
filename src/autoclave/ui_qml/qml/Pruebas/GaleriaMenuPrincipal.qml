pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"

// PRUEBA (Fase 1 de planeacion_menu_principal_ui_qml.md): galería de los
// componentes del Menú Principal con DATOS DE EJEMPLO en sus estados normal,
// presionado, deshabilitado y valor largo. NO es parte de la navegación ni se
// conecta al backend: la abre ui_qml/prueba_menu_principal.py.
// Marco del diseñador de 1196 de ancho escalado con m() (D-18).
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

    Item {
        id: lienzo
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        readonly property real escala: width / 1196
        function m(v) { return v * escala }

        readonly property string iconos: "../../assets/iconos/mono/"

        FondoApp { anchors.fill: parent }

        EncabezadoMenu {
            objectName: "galeriaEncabezado"
            escala: lienzo.escala
            textosJson: ventana.textosJson
            conteoAlarmas: 2
        }

        // ---- tarjetas de menú, fila 1 (aro 122): normal con borde / deshabilitada ----
        TarjetaMenu {
            objectName: "tarjetaNormal"
            x: lienzo.m(63); y: lienzo.m(200); width: lienzo.m(716); height: lienzo.m(320)
            escala: lienzo.escala
            titulo: "INICIAR SESIÓN"
            descripcion: "Acceda con su usuario y contraseña"
            icono: lienzo.iconos + "usuario.svg"
            colorAcento: Colores.menuVerde
            colorTitulo: Colores.menuVerdeTexto
            aroAcento: true
            conBorde: true
        }
        TarjetaMenu {
            objectName: "tarjetaDeshabilitada"
            x: lienzo.m(798); y: lienzo.m(200); width: lienzo.m(350); height: lienzo.m(320)
            escala: lienzo.escala
            enabled: false
            titulo: "HISTORIAL"
            descripcion: "Consulte los ciclos realizados"
            icono: lienzo.iconos + "historial.svg"
            colorAcento: Colores.menuMorado
        }

        // ---- fila 2 (aro 106): presionada / texto largo / secado sin valor ----
        TarjetaMenu {
            objectName: "tarjetaPresionada"
            x: lienzo.m(63); y: lienzo.m(544); width: lienzo.m(349); height: lienzo.m(320)
            escala: lienzo.escala
            presionada: true
            diametroAro: 106; tamTitulo: 25; tamDescripcion: 21
            titulo: "REPORTES"
            descripcion: "Visualice y administre reportes de ciclos"
            icono: lienzo.iconos + "reportes.svg"
            colorAcento: Colores.menuNaranja
        }
        TarjetaMenu {
            objectName: "tarjetaTextoLargo"
            x: lienzo.m(431); y: lienzo.m(544); width: lienzo.m(349); height: lienzo.m(320)
            escala: lienzo.escala
            diametroAro: 106; tamTitulo: 25; tamDescripcion: 21
            titulo: "INFORMACIÓN DEL EQUIPO Y DEL SISTEMA COMPLETO"
            descripcion: "Texto de descripción deliberadamente largo para comprobar que se corta sin desbordar la tarjeta"
            icono: lienzo.iconos + "informacion.svg"
            colorAcento: Colores.menuAzul
        }
        TarjetaMenu {
            objectName: "tarjetaSecadoSinValor"
            x: lienzo.m(799); y: lienzo.m(544); width: lienzo.m(349); height: lienzo.m(320)
            escala: lienzo.escala
            diametroAro: 106; tamTitulo: 25; tamDescripcion: 21
            titulo: "TIEMPO ADICIONAL\nDE SECADO"
            descripcion: "Programa seleccionado"
            valor: "—"
            flechaVisible: false
            icono: lienzo.iconos + "sensor_tiempo_secado.svg"
            colorAcento: Colores.menuAzul
        }

        // ---- fila 3: secado con valor largo ----
        TarjetaMenu {
            objectName: "tarjetaSecadoValorLargo"
            x: lienzo.m(63); y: lienzo.m(888); width: lienzo.m(349); height: lienzo.m(320)
            escala: lienzo.escala
            diametroAro: 106; tamTitulo: 25; tamDescripcion: 21
            titulo: "TIEMPO ADICIONAL\nDE SECADO"
            descripcion: "Programa seleccionado"
            valor: "120.5 min"
            flechaVisible: false
            icono: lienzo.iconos + "sensor_tiempo_secado.svg"
            colorAcento: Colores.menuAzul
        }

        // ---- tarjetas de resumen como botón (D-20): presionada / deshabilitada ----
        TarjetaResumen {
            objectName: "resumenPresionado"
            x: lienzo.m(431); y: lienzo.m(888); width: lienzo.m(206); height: lienzo.m(330)
            escala: lienzo.escala
            presionada: true
            icono: lienzo.iconos + "reloj.svg"
            colorAcento: Colores.menuMorado
            rotulo: "CICLOS HOY"
            valor: "5"
            subrotulo: "Realizados"
        }
        TarjetaResumen {
            objectName: "resumenDeshabilitado"
            x: lienzo.m(653); y: lienzo.m(888); width: lienzo.m(230); height: lienzo.m(330)
            escala: lienzo.escala
            enabled: false
            icono: lienzo.iconos + "ciclos_totales.svg"
            colorAcento: Colores.menuAzul
            rotulo: "CICLOS TOTALES"
            valor: "128"
            subrotulo: "Realizados"
        }

        // ---- tarjetas de resumen: valor largo / sin dato / normal / contenido propio ----
        TarjetaResumen {
            objectName: "resumenValorLargo"
            x: lienzo.m(63); y: lienzo.m(1232); width: lienzo.m(230); height: lienzo.m(330)
            escala: lienzo.escala
            icono: lienzo.iconos + "ciclos_totales.svg"
            colorAcento: Colores.menuAzul
            rotulo: "CICLOS TOTALES"
            valor: "12345678"
            subrotulo: "Realizados"
        }
        TarjetaResumen {
            objectName: "resumenSinDato"
            x: lienzo.m(309); y: lienzo.m(1232); width: lienzo.m(293); height: lienzo.m(330)
            escala: lienzo.escala
            icono: lienzo.iconos + "mantenimiento.svg"
            colorAcento: Colores.menuNaranja
            rotulo: "PRÓXIMO\nMANTENIMIENTO"
            valor: "—"
        }
        TarjetaResumen {
            objectName: "resumenNormal"
            x: lienzo.m(618); y: lienzo.m(1232); width: lienzo.m(206); height: lienzo.m(330)
            escala: lienzo.escala
            icono: lienzo.iconos + "reloj.svg"
            colorAcento: Colores.menuMorado
            rotulo: "CICLOS HOY"
            valor: "5"
            subrotulo: "Realizados"
        }
        TarjetaResumen {
            objectName: "resumenUltimoCiclo"
            x: lienzo.m(840); y: lienzo.m(1232); width: lienzo.m(308); height: lienzo.m(330)
            escala: lienzo.escala
            // triángulo de play, como mockup-01 (reproducir.svg trae su propio aro)
            icono: lienzo.iconos + "reproducir.svg"
            iconoIncluyeAro: true
            colorAcento: Colores.menuAzul
            rotulo: "ÚLTIMO CICLO"
            DetalleUltimoCiclo {
                escala: lienzo.escala
                fecha: "12/10/2026"; hora: "14:25"
                rotuloPrograma: "Programa:"; programa: "02 · 134 INSTRUMENTAL"
                rotuloResultado: "Resultado:"; resultado: "COMPLETADO"
            }
        }

        BarraInferiorMenu {
            objectName: "galeriaBarraInferior"
            x: lienzo.m(43); y: lienzo.m(1600)
            escala: lienzo.escala
            version: "V: 1.0"
        }
    }
}
