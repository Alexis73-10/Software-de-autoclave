pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// PROVISIONAL (sin diseño): información del equipo, abre al tocar el recuadro
// de modelo/serie. Filas de InfoEquipo.filas: {clave, valor, disponible}.
// valor null -> dato aún desconocido (sistema.sin_lectura); disponible false
// -> sin fuente en el software (equipo.no_disponible). valorClave (opcional)
// -> el valor es un texto de la sección "equipo" (p.ej. emparejamiento de la
// tarjeta, E6).
PanelModal {
    id: raiz
    altoTarjeta: Escala.px(1500)

    property var filas: []
    property string sinLectura: "—"
    // Texto de la sección "equipo"; la clave misma si no existe (como antes de F1)
    function textoEquipo(clave) {
        return I18n.existe("equipo." + clave, I18n.lang) ? I18n.t("equipo." + clave, I18n.lang) : clave
    }

    ListView {
        anchors.fill: parent
        clip: true
        model: raiz.filas
        delegate: Item {
            id: fila
            required property var modelData
            width: ListView.view.width
            height: Escala.px(76)

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * 0.5
                text: raiz.textoEquipo(fila.modelData.clave)
                elide: Text.ElideRight
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoMedium
                font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * 0.5
                horizontalAlignment: Text.AlignRight
                text: !fila.modelData.disponible ? I18n.t("equipo.no_disponible", I18n.lang)
                    : fila.modelData.valorClave ? raiz.textoEquipo(fila.modelData.valorClave)
                    : (fila.modelData.valor ?? raiz.sinLectura)
                elide: Text.ElideLeft
                color: fila.modelData.disponible ? Colores.textoPrimario : Colores.textoGuia
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: Escala.px(1)
                color: "#E6E6E6"
            }
        }
    }
}
