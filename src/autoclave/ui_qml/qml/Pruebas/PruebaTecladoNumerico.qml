pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// PRUEBA DESECHABLE (planeacion_teclados_qml.md, Paso 3): muestra el teclado
// numérico anclado al pie con mínimo -100, máximo 400 y 1 decimal. NO es parte
// de la navegación de producción: solo la abre ui_qml/prueba_teclado_numerico.py.
// Sin PanelTeclado ni animación (eso es el Paso 5). Borrar al terminar.
Window {
    id: ventana
    width: 600; height: 960   // 5:8; con --completa ocupa la pantalla
    visible: true
    color: Colores.fondoTarjeta


    property string resultado: I18n.t("prueba_teclado.sin_valor", I18n.lang)

    function abrirTeclado() {
        teclado.abrir(I18n.t("prueba_teclado.campo", I18n.lang), I18n.t("unidades.temperatura", I18n.lang),
                      null, -100, 400, 1)
    }

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

        // Aviso de prueba, siempre visible
        Rectangle {
            width: parent.width
            height: Escala.px(88)
            color: Colores.fondoSutil
            border.color: Colores.bordeCampo
            border.width: Escala.px(2)
            Text {
                anchors.centerIn: parent
                width: parent.width - Escala.px(48)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: I18n.t("prueba_teclado.aviso", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(24)
            }
        }

        Column {
            x: Escala.px(48); y: Escala.px(136)
            width: parent.width - Escala.px(96)
            spacing: Escala.px(16)

            Text {
                text: I18n.t("prueba_teclado.titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
            }

            // Campo de prueba: tocarlo reabre el teclado
            Rectangle {
                width: parent.width; height: Escala.px(120)
                radius: Escala.px(12)
                border.color: Colores.bordeCampo; border.width: Escala.px(2)
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Escala.px(24)
                    spacing: Escala.px(4)
                    Text {
                        text: I18n.t("prueba_teclado.valor_entregado", I18n.lang)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                    }
                    Text {
                        objectName: "resultado"
                        text: ventana.resultado
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(32)
                    }
                }
                MouseArea { anchors.fill: parent; onClicked: ventana.abrirTeclado() }
            }
            Text {
                text: I18n.t("prueba_teclado.reabrir", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
            }
        }

        // Teclado anclado al pie (sin PanelTeclado ni animación: Paso 5)
        TecladoNumerico {
            id: teclado
            objectName: "tecladoNumerico"
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(24)
            anchors.horizontalCenter: parent.horizontalCenter
            width: implicitWidth; height: implicitHeight
            onConfirmado: valor => {
                ventana.resultado = valor.toFixed(teclado.controlador.decimales)
                ventana.abrirTeclado()
            }
            onCancelado: {
                ventana.resultado = I18n.t("prueba_teclado.cancelado", I18n.lang)
                ventana.abrirTeclado()
            }
        }
    }

    Component.onCompleted: abrirTeclado()
}
