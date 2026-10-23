pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Usuarios (O2b, tanda 6; mockup 6 aprobado). Pestañas Usuarios /
// Operadores. Usuarios: nombre, rol, último ingreso y chip Activo/Desactivado;
// para el seleccionado, "Restablecer contraseña" y "Desactivar" (o Reactivar),
// y "+ Nuevo usuario" (abre la pantalla existente). Operadores: lista con
// agregar y desactivar. Nunca se borra un usuario; nadie se desactiva a sí
// mismo ni deja el equipo sin un ingeniero activo (lo impone el backend).
// Decisión 1.9: el técnico ve los controles deshabilitados, con el motivo.
Item {
    id: raiz
    objectName: "opcionesUsuarios"

    property QtObject teclado: null
    property string rol: ""
    property string usuarioActual: ""
    property string pestana: "usuarios"          // "usuarios" | "operadores"
    property string seleccionado: ""
    readonly property bool cambiosPendientes: false

    signal nuevoUsuarioPulsado()

    UsuariosController {
        id: control
        objectName: "usuariosController"
        rol: raiz.rol
        usuarioActual: raiz.usuarioActual
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    readonly property var filaSeleccionada: {
        const l = control.usuarios
        for (let i = 0; i < l.length; ++i)
            if (l[i].usuario === raiz.seleccionado) return l[i]
        return null
    }
    readonly property string motivoSeleccionado: raiz.seleccionado !== ""
                                                 && control.usuarios.length >= 0
                                                 ? control.motivoSobre(raiz.seleccionado) : control.motivo
    function etiquetaRol(r) {
        const k = "roles." + r
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : r
    }

    // contraseña temporal: dos pasos con el teclado (oculto)
    property string _claveTemporal: ""
    function pedirClave() {
        if (!raiz.teclado) return
        raiz.teclado.abrirAlfanumerico(I18n.t("gestion_usuarios.clave_temporal", I18n.lang), "", 64, true,
            (t) => raiz._claveTemporal = t,
            () => raiz.teclado.abrirAlfanumerico(I18n.t("gestion_usuarios.clave_confirmar", I18n.lang),
                                                 "", 64, true, (t) => raiz._confirmacion = t))
    }
    property string _confirmacion: ""
    Connections {
        target: raiz.teclado
        enabled: raiz.pestana === "usuarios"
        function onTerminado() {
            if (raiz._claveTemporal !== "" && raiz._confirmacion !== "") {
                confirmarClave.abrir()
            }
        }
    }

    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool habilitado: true
        property bool secundario: false
        signal pulsado()
        height: Escala.px(88)
        radius: Escala.px(12)
        color: secundario ? Colores.fondoSutil : Colores.accionPrimario
        border.width: secundario ? Escala.px(1) : 0
        border.color: Colores.bordeCampo
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            width: parent.width - Escala.px(16)
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: boton.texto
            color: boton.secundario ? Colores.textoPrimario : "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
        }
        MouseArea { anchors.fill: parent; enabled: boton.habilitado; onClicked: boton.pulsado() }
    }

    component Chip: Rectangle {
        id: chip
        property bool activo: true
        width: textoChip.implicitWidth + Escala.px(28)
        height: Escala.px(44)
        radius: height / 2
        color: activo ? Colores.accionFondoTenue : Colores.fondoSutil
        Text {
            id: textoChip
            anchors.centerIn: parent
            text: chip.activo ? I18n.t("gestion_usuarios.activo", I18n.lang)
                              : I18n.t("gestion_usuarios.desactivado", I18n.lang)
            color: chip.activo ? Colores.menuVerdeTexto : Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(20)
        }
    }

    Column {
        id: cabeza
        width: parent.width
        spacing: Escala.px(12)

        // pestañas
        Row {
            width: parent.width
            Repeater {
                model: ["usuarios", "operadores"]
                delegate: Rectangle {
                    id: pes
                    required property string modelData
                    objectName: "pestana_" + modelData
                    readonly property bool activa: raiz.pestana === modelData
                    width: cabeza.width / 2; height: Escala.px(84)
                    radius: Escala.px(10)
                    color: activa ? Colores.accionPrimario : Colores.fondoSutil
                    Text {
                        anchors.centerIn: parent
                        text: pes.modelData === "usuarios" ? I18n.t("gestion_usuarios.pestana_usuarios", I18n.lang)
                                                           : I18n.t("gestion_usuarios.pestana_operadores", I18n.lang)
                        color: pes.activa ? "white" : Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(26)
                    }
                    MouseArea { anchors.fill: parent; onClicked: raiz.pestana = pes.modelData }
                }
            }
        }

        Rectangle {
            objectName: "avisoMotivoUsuarios"
            visible: control.motivo !== ""
            width: parent.width; height: visible ? Escala.px(72) : 0
            radius: Escala.px(12)
            color: Colores.advertenciaFondo
            Text {
                anchors.fill: parent; anchors.margins: Escala.px(16)
                verticalAlignment: Text.AlignVCenter
                wrapMode: Text.WordWrap
                text: I18n.t("gestion_usuarios.motivo_rol", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(22)
            }
        }

        Rectangle {
            objectName: "errorUsuarios"
            visible: control.mensaje !== ""
            width: parent.width; height: visible ? Escala.px(72) : 0
            radius: Escala.px(12)
            color: Colores.peligroFondo
            Text {
                anchors.fill: parent; anchors.margins: Escala.px(16)
                verticalAlignment: Text.AlignVCenter
                wrapMode: Text.WordWrap
                text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
        }

        Text {
            objectName: "notaUsuarios"
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("gestion_usuarios.nota", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }
    }

    // ======================= pestaña Usuarios =======================
    Item {
        visible: raiz.pestana === "usuarios"
        anchors.top: cabeza.bottom; anchors.topMargin: Escala.px(12)
        anchors.bottom: parent.bottom
        width: parent.width

        ListView {
            id: listaUsuarios
            objectName: "listaUsuarios"
            anchors.top: parent.top
            anchors.bottom: accionesUsuario.top; anchors.bottomMargin: Escala.px(12)
            width: parent.width
            clip: true
            spacing: Escala.px(6)
            model: control.usuarios
            delegate: Rectangle {
                id: filaU
                required property var modelData
                objectName: "filaUsuario_" + modelData.usuario
                readonly property bool sel: raiz.seleccionado === modelData.usuario
                width: listaUsuarios.width; height: Escala.px(108)
                radius: Escala.px(12)
                color: sel ? Colores.accionFondoTenue : Colores.fondoSutil
                border.width: sel ? Escala.px(2) : 0
                border.color: Colores.accionPrimario
                Column {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.right: chipU.left; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: filaU.modelData.nombre + "  ·  " + filaU.modelData.usuario
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: Escala.fuente(26)
                    }
                    Text {
                        width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: raiz.etiquetaRol(filaU.modelData.rol) + "  ·  "
                              + I18n.t("gestion_usuarios.ultimo_ingreso", I18n.lang) + ": "
                              + (filaU.modelData.ultimoIngreso !== "" ? filaU.modelData.ultimoIngreso
                                                                      : I18n.t("gestion_usuarios.nunca", I18n.lang))
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(21)
                    }
                }
                Chip {
                    id: chipU
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
                    anchors.verticalCenter: parent.verticalCenter
                    activo: filaU.modelData.activo
                }
                MouseArea { anchors.fill: parent; onClicked: raiz.seleccionado = filaU.modelData.usuario }
            }
        }

        Column {
            id: accionesUsuario
            anchors.bottom: parent.bottom
            width: parent.width
            spacing: Escala.px(10)

            Text {
                objectName: "motivoSeleccionado"
                visible: raiz.seleccionado !== "" && raiz.motivoSeleccionado !== ""
                         && raiz.motivoSeleccionado !== "rol"
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.motivoSeleccionado === "propio" ? I18n.t("gestion_usuarios.motivo_propio", I18n.lang)
                                                           : I18n.t("gestion_usuarios.motivo_rol_objetivo", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(21)
            }
            Row {
                width: parent.width
                spacing: Escala.px(12)
                Boton {
                    objectName: "botonRestablecerClave"
                    width: (parent.width - Escala.px(12)) / 2
                    secundario: true
                    texto: I18n.t("gestion_usuarios.restablecer", I18n.lang)
                    habilitado: raiz.filaSeleccionada !== null && raiz.motivoSeleccionado === ""
                                && raiz.teclado !== null
                    onPulsado: { raiz._claveTemporal = ""; raiz._confirmacion = ""; raiz.pedirClave() }
                }
                Boton {
                    objectName: "botonActivoUsuario"
                    width: (parent.width - Escala.px(12)) / 2
                    secundario: true
                    texto: raiz.filaSeleccionada && !raiz.filaSeleccionada.activo
                           ? I18n.t("gestion_usuarios.reactivar", I18n.lang)
                           : I18n.t("gestion_usuarios.desactivar", I18n.lang)
                    habilitado: raiz.filaSeleccionada !== null && raiz.motivoSeleccionado === ""
                    onPulsado: confirmarActivo.abrir()
                }
            }
            Boton {
                objectName: "botonNuevoUsuario"
                width: parent.width
                texto: I18n.t("gestion_usuarios.nuevo", I18n.lang)
                habilitado: control.motivo === ""
                onPulsado: raiz.nuevoUsuarioPulsado()
            }
        }
    }

    // ======================= pestaña Operadores =======================
    Item {
        visible: raiz.pestana === "operadores"
        anchors.top: cabeza.bottom; anchors.topMargin: Escala.px(12)
        anchors.bottom: parent.bottom
        width: parent.width

        ListView {
            id: listaOperadores
            objectName: "listaOperadores"
            anchors.top: parent.top
            anchors.bottom: botonAgregarOperador.top; anchors.bottomMargin: Escala.px(12)
            width: parent.width
            clip: true
            spacing: Escala.px(6)
            model: control.operadores
            delegate: Rectangle {
                id: filaO
                required property var modelData
                objectName: "filaOperador_" + modelData.id
                width: listaOperadores.width; height: Escala.px(96)
                radius: Escala.px(12)
                color: Colores.fondoSutil
                Text {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.right: chipO.left; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
                    height: parent.height; verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.Wrap
                    fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
                    text: filaO.modelData.nombre
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(26)
                }
                Chip {
                    id: chipO
                    anchors.right: botonO.left; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    activo: filaO.modelData.activo
                }
                Boton {
                    id: botonO
                    objectName: "botonActivoOperador_" + filaO.modelData.id
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(240); height: Escala.px(72)
                    secundario: true
                    texto: filaO.modelData.activo ? I18n.t("gestion_usuarios.desactivar", I18n.lang)
                                                  : I18n.t("gestion_usuarios.reactivar", I18n.lang)
                    habilitado: control.motivo === ""
                    onPulsado: control.fijarActivoOperador(filaO.modelData.id, !filaO.modelData.activo)
                }
            }
        }
        Text {
            visible: control.operadores.length === 0
            anchors.centerIn: listaOperadores
            text: I18n.t("gestion_usuarios.sin_operadores", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
        Boton {
            id: botonAgregarOperador
            objectName: "botonAgregarOperador"
            anchors.bottom: parent.bottom
            width: parent.width
            texto: I18n.t("gestion_usuarios.agregar_operador", I18n.lang)
            habilitado: control.motivo === "" && raiz.teclado !== null
            onPulsado: raiz.teclado.abrirAlfanumerico(I18n.t("gestion_usuarios.nombre_operador", I18n.lang),
                                                      "", 40, false, (t) => raiz._nombreOperador = t)
        }
    }
    property string _nombreOperador: ""
    Connections {
        target: raiz.teclado
        enabled: raiz.pestana === "operadores"
        function onTerminado() {
            if (raiz._nombreOperador.trim() !== "") {
                control.agregarOperador(raiz._nombreOperador)
                raiz._nombreOperador = ""
            }
        }
    }

    DialogoConfirmacion {
        id: confirmarActivo
        objectName: "confirmarActivoUsuario"
        mensaje: raiz.filaSeleccionada === null ? ""
                 : I18n.t(raiz.filaSeleccionada.activo ? "gestion_usuarios.confirmar_desactivar"
                                                       : "gestion_usuarios.confirmar_reactivar",
                          I18n.lang, { usuario: raiz.seleccionado })
        textoConfirmar: raiz.filaSeleccionada && !raiz.filaSeleccionada.activo
                        ? I18n.t("gestion_usuarios.reactivar", I18n.lang)
                        : I18n.t("gestion_usuarios.desactivar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: {
            cerrar()
            if (raiz.filaSeleccionada)
                control.fijarActivo(raiz.seleccionado, !raiz.filaSeleccionada.activo)
        }
    }
    DialogoConfirmacion {
        id: confirmarClave
        objectName: "confirmarRestablecerClave"
        mensaje: I18n.t("gestion_usuarios.confirmar_restablecer", I18n.lang, { usuario: raiz.seleccionado })
        textoConfirmar: I18n.t("gestion_usuarios.restablecer", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: {
            cerrar()
            control.restablecer(raiz.seleccionado, raiz._claveTemporal, raiz._confirmacion)
            raiz._claveTemporal = ""; raiz._confirmacion = ""
        }
        onDescartado: { raiz._claveTemporal = ""; raiz._confirmacion = "" }
    }
}
