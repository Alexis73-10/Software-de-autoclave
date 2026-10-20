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
    // ComandosSistema (E5): "Apagar equipo" solo en la ventana principal (§16)
    property QtObject comandosSistema: null
    readonly property bool puedeApagar: comandosSistema?.ventanaPrincipal ?? false
    property string sinLectura: "—"
    // Texto de la sección "equipo"; la clave misma si no existe (como antes de F1)
    function textoEquipo(clave) {
        return I18n.existe("equipo." + clave, I18n.lang) ? I18n.t("equipo." + clave, I18n.lang) : clave
    }

    ListView {
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: raiz.puedeApagar ? zonaApagar.top : parent.bottom
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

    // PROVISIONAL (sin diseño): Apagar equipo (fin de ciclo §16, D-20). Desde
    // A1 (tanda 3) el backend lo permite en cualquier estado salvo ciclo /
    // estado seguro actuando, también con la cámara NO segura (solo se avisa).
    Column {
        id: zonaApagar
        visible: raiz.puedeApagar
        anchors.left: parent.left; anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: Escala.px(8)
        Text {
            objectName: "mensajeApagar"
            width: parent.width
            visible: text.length > 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: (raiz.comandosSistema?.mensaje ?? "").length > 0
                  ? I18n.t("equipo.apagar_rechazado", I18n.lang,
                           {motivo: raiz.comandosSistema.mensaje}) : ""
            color: Colores.advertenciaTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(18)
        }
        Rectangle {
            objectName: "botonApagarEquipo"
            anchors.horizontalCenter: parent.horizontalCenter
            width: textoApagar.implicitWidth + Escala.px(64)
            height: Escala.px(72)
            radius: Escala.px(36)
            color: "#B71C1C"
            opacity: (raiz.comandosSistema?.ocupado ?? false) ? 0.5 : 1.0
            Text {
                id: textoApagar
                anchors.centerIn: parent
                text: I18n.t("equipo.apagar", I18n.lang)
                color: "white"
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(22)
            }
            MouseArea { anchors.fill: parent; onClicked: confirmarApagar.abrir() }
        }
    }

    DialogoConfirmacion {
        id: confirmarApagar
        objectName: "confirmarApagar"
        mensaje: I18n.t("equipo.apagar_pregunta", I18n.lang)
                 + ((raiz.comandosSistema?.camaraNoSegura ?? true)
                    ? "

" + I18n.t("equipo.apagar_camara_no_segura", I18n.lang) : "")
        textoConfirmar: I18n.t("equipo.apagar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: "#B71C1C"
        onConfirmado: { cerrar(); raiz.comandosSistema?.apagarEquipo() }
    }
}
