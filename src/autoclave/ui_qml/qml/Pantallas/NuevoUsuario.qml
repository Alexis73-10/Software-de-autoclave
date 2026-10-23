pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import Tema
import "../Componentes"
import Autoclave.I18n

// Pantalla Nuevo Usuario (planeacion_nuevo_usuario.md, sección 5).
// Contenido: src/autoclave/images/nuevo_usuario.png sin "Nivel de acceso" ni
// botón "+" (D-01, D-02), con Código obligatorio (D-12) y Rol a todo el ancho
// (P-02). Medidas: pantalla_04_nuevo_usuario, llevadas al lienzo de 1200x1920.
//
// Solo presenta: las reglas de validación, el control de acceso y la escritura
// en la BD viven en el puente Python (NuevoUsuarioBridge, `puente`). Los campos
// se escriben con el teclado en pantalla (`teclado`, PanelTeclado del host).
// Las contraseñas se limpian al salir de la pantalla (limpiar()).
Item {
    id: raiz
    objectName: "nuevoUsuario"

    property QtObject teclado: null
    property QtObject puente: null
    // Errores del puente por clave de es.json (T-8): {clave: "seccion.clave", valores}
    // Pantalla con token en uso (OPCIONES › Usuarios): la vigila Main.qml
    readonly property bool usaToken: true

    // Valores confirmados de los campos
    property string nombre: ""
    property string usuario: ""
    property string clave: ""
    property string confirmacion: ""
    property string rol: ""
    property bool activo: true
    // Ojo de cada campo de contraseña: false = oculta (por defecto)
    property bool verClave: false
    property bool verConfirmacion: false
    // {campo: mensaje} devuelto por el puente; los campos lo muestran en rojo
    property var errores: ({})
    // campo que se está escribiendo ("" si ninguno)
    property string campoActivo: ""

    Connections {
        target: raiz.teclado
        function onAbiertoChanged() { if (!raiz.teclado.abierto) raiz.campoActivo = "" }
        // Confirmar en el último campo guarda el usuario
        function onTerminado() { if (raiz.campoActivo !== "") raiz.pulsarGuardar() }
    }

    // ── Campos de texto y teclado ────────────────────────────────────────
    // Orden de Confirmar → siguiente (Rol es desplegable: no entra en la cadena)
    readonly property var campos: [
        { nombre: "nombre",       titulo: I18n.t("formulario.nombre_completo", I18n.lang),     clave: "nombre" },
        { nombre: "usuario",      titulo: I18n.t("formulario.nombre_usuario", I18n.lang),      clave: "usuario" },
        { nombre: "clave",        titulo: I18n.t("formulario.contrasena", I18n.lang),          clave: "password" },
        { nombre: "confirmacion", titulo: I18n.t("formulario.confirmar_contrasena", I18n.lang), clave: "confirmacion" }
    ]
    function _oculto(nombre) {
        return (nombre === "clave" && !verClave) || (nombre === "confirmacion" && !verConfirmacion)
    }
    function editar(nombre) {
        if (!teclado)
            return
        listaRoles.visible = false
        const i = campos.findIndex(c => c.nombre === nombre)
        const campo = campos[i]
        const siguiente = i + 1 < campos.length ? campos[i + 1].nombre : ""
        const maximos = puente ? puente.longitudesMaximas : ({})
        teclado.abrirAlfanumerico(campo.titulo, raiz[nombre], maximos[campo.clave] || 0,
                                  _oculto(nombre), texto => raiz[nombre] = texto,
                                  siguiente ? () => raiz.editar(siguiente) : null)
        campoActivo = nombre
    }
    function textoCampo(nombre) {
        return campoActivo === nombre && teclado ? teclado.textoEnEdicion : raiz[nombre]
    }

    // Ojo (NU-02): el teclado lee `ocultar` al abrirse. Si el ojo se apaga
    // con el teclado abierto en ese campo, se reabre oculto con lo escrito
    // (abrirAlfanumerico guarda lo pendiente antes de reabrir). Al encenderlo
    // con el teclado abierto, el encabezado sigue con puntos hasta reabrir (NU-10).
    function alternarOjoClave() {
        verClave = !verClave
        if (!verClave && campoActivo === "clave")
            editar("clave")
    }
    function alternarOjoConfirmacion() {
        verConfirmacion = !verConfirmacion
        if (!verConfirmacion && campoActivo === "confirmacion")
            editar("confirmacion")
    }

    // ── Datos capturados y salida ────────────────────────────────────────
    function hayDatos() {
        return nombre !== "" || usuario !== "" || clave !== "" || confirmacion !== ""
            || rol !== "" || !activo
    }
    function limpiar() {
        if (teclado)
            teclado.cerrar()
        listaRoles.visible = false
        nombre = ""; usuario = ""; clave = ""; confirmacion = ""
        rol = ""; activo = true
        verClave = false; verConfirmacion = false
        errores = ({})
        campoActivo = ""
    }
    // Abandona la pantalla: pide confirmación solo si hay datos capturados
    function _abandonar(accion) {
        if (teclado)
            teclado.cerrar()
        listaRoles.visible = false
        if (hayDatos())
            dialogoDescartar.pedir(accion)
        else
            accion()
    }
    function _irA(destino) {
        limpiar()
        if (puente)
            puente.navegar(destino)
    }
    function pulsarAtras()    { _abandonar(() => _irA("admin_menu")) }
    function pulsarCancelar() { _abandonar(() => _irA("admin_menu")) }
    function pulsarInicio()   { _abandonar(() => _irA("home")) }

    function pulsarGuardar() {
        if (!puente)
            return
        if (teclado)
            teclado.cerrar()   // lo escrito sin Confirmar ya quedó en el campo
        listaRoles.visible = false
        const r = puente.guardar(nombre, usuario, clave, confirmacion, rol, activo)
        if (r.ok) {
            _irA("admin_menu")   // el host muestra "Usuario creado"
            return
        }
        errores = r.errores
        _enfocarPrimerError()
    }
    function _enfocarPrimerError() {
        const orden = ["nombre", "usuario", "clave", "confirmacion", "rol"]
        const claveError = { clave: "password" }
        for (const n of orden) {
            if (errores[claveError[n] || n] === undefined)
                continue
            if (n === "rol")
                listaRoles.visible = true
            else
                editar(n)
            return
        }
    }
    function error(campo) {
        const e = errores[campo]
        return e ? I18n.t(e.clave, I18n.lang, e.valores) : ""
    }

    // ── Presentación ─────────────────────────────────────────────────────
    readonly property string iconos: "../../assets/iconos/color/"

    FondoApp { anchors.fill: parent }

    BarraSuperior {
        objectName: "barraSuperior"
        mostrarIconos: true   // inertes en esta pantalla (P-07)
    }

    // Campo de formulario: etiqueta arriba, recuadro y error en rojo debajo
    component Campo: Item {
        id: c
        property string nombre: ""
        property string etiqueta: ""
        property string marcador: ""
        property string mensajeError: ""
        property bool conOjo: false
        property bool visibleTexto: true
        property alias nombreObjeto: entrada.objectName
        property alias nombreError: textoError.objectName
        signal tocado()
        signal ojoTocado()
        height: Escala.px(125)

        Text {
            id: etiquetaTexto
            text: c.etiqueta
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
            font.weight: Tipografia.pesoMedium
        }
        Rectangle {
            id: recuadro
            y: Escala.px(43)
            width: parent.width; height: Escala.px(82)
            radius: Escala.px(6)
            border.color: c.mensajeError !== "" ? Colores.peligroTexto
                        : raiz.campoActivo === c.nombre ? Colores.accionPrimario : Colores.bordeDivisor
            border.width: raiz.campoActivo === c.nombre || c.mensajeError !== "" ? 2 : 1

            TextField {
                id: entrada
                readOnly: true   // se escribe con el teclado en pantalla
                text: raiz.textoCampo(c.nombre)
                echoMode: c.visibleTexto ? TextInput.Normal : TextInput.Password
                color: Colores.textoPrimario
                placeholderText: c.marcador
                placeholderTextColor: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                anchors.left: parent.left
                anchors.right: c.conOjo ? ojo.left : parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.leftMargin: Escala.px(12)
                anchors.rightMargin: Escala.px(12)
                background: null
            }
            MouseArea {
                anchors.fill: entrada
                onClicked: c.tocado()
            }
            // Muestra "ojo_mostrar" mientras está oculta (la acción disponible es mostrarla)
            Image {
                id: ojo
                visible: c.conOjo
                anchors.right: parent.right
                anchors.rightMargin: Escala.px(24)
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(44); height: Escala.px(44)
                source: raiz.iconos + (c.visibleTexto ? "ojo_ocultar.svg" : "ojo_mostrar.svg")
                sourceSize.width: width
                sourceSize.height: height
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -Escala.px(16)   // área táctil más grande que el icono
                    onClicked: c.ojoTocado()
                }
            }
        }
        Text {
            id: textoError
            anchors.top: recuadro.bottom
            anchors.topMargin: Escala.px(4)
            x: Escala.px(4)
            text: c.mensajeError
            visible: text !== ""
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(18)
        }
    }

    TarjetaContenido {
        id: tarjeta
        objectName: "tarjetaNuevoUsuario"
        x: Escala.px(24); y: Escala.px(176)
        width: parent.width - Escala.px(48)
        height: raiz.height - Escala.px(176) - raiz.width / 1196 * 201

        contenido: [
            Item {
                id: formulario
                anchors.fill: parent
                clip: true

                // Deja el campo activo a la vista sobre el teclado
                readonly property real _desplazamiento: {
                    if (!raiz.teclado || !raiz.teclado.abierto || raiz.campoActivo === "")
                        return 0
                    const campo = { nombre: campoNombre, usuario: campoUsuario, clave: campoClave,
                                    confirmacion: campoConfirmacion }[raiz.campoActivo]
                    if (!campo)
                        return 0
                    const fondoCampo = tarjeta.y + campo.y + campo.height + Escala.px(24)
                    return Math.max(0, fondoCampo - (raiz.height - raiz.teclado.alturaOcupada))
                }

                Item {
                    id: lienzo
                    width: parent.width
                    height: parent.height
                    y: -formulario._desplazamiento
                    Behavior on y { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

                    // ---- título ----
                    Image {
                        id: atras
                        x: Escala.px(64); y: Escala.px(72)
                        width: Escala.px(36); height: Escala.px(36)
                        source: raiz.iconos + "chevron_izquierda.svg"
                        sourceSize.width: width
                        sourceSize.height: height
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -Escala.px(24)
                            onClicked: raiz.pulsarAtras()
                        }
                    }
                    Text {
                        anchors.left: atras.right
                        anchors.leftMargin: Escala.px(28)
                        anchors.verticalCenter: atras.verticalCenter
                        text: I18n.t("usuarios.titulo_nuevo", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
                        font.weight: Tipografia.pesoBold
                    }

                    // ---- avatar estático (D-02) ----
                    Rectangle {
                        x: Escala.px(46); y: Escala.px(224)
                        width: Escala.px(287); height: width; radius: width / 2
                        color: "#E6E6E6"
                        Image {
                            anchors.centerIn: parent
                            width: parent.width * 0.5; height: width
                            source: raiz.iconos + "usuario.svg"
                            sourceSize.width: width
                            sourceSize.height: height
                        }
                    }

                    // ---- columna derecha ----
                    Campo {
                        id: campoNombre
                        nombre: "nombre"
                        x: Escala.px(381); y: Escala.px(184)
                        width: Escala.px(707)
                        etiqueta: I18n.t("formulario.nombre_completo", I18n.lang)
                        marcador: I18n.t("usuarios.marcador_nombre", I18n.lang)
                        mensajeError: raiz.error("nombre")
                        nombreObjeto: "campoNombre"
                        nombreError: "errorNombre"
                        onTocado: raiz.editar("nombre")
                    }
                    Campo {
                        id: campoUsuario
                        nombre: "usuario"
                        x: campoNombre.x; y: campoNombre.y + Escala.px(167)
                        width: campoNombre.width
                        etiqueta: I18n.t("formulario.nombre_usuario", I18n.lang)
                        mensajeError: raiz.error("usuario")
                        nombreObjeto: "campoUsuario"
                        nombreError: "errorUsuario"
                        onTocado: raiz.editar("usuario")
                    }
                    Campo {
                        id: campoClave
                        nombre: "clave"
                        x: campoNombre.x; y: campoUsuario.y + Escala.px(167)
                        width: campoNombre.width
                        etiqueta: I18n.t("formulario.contrasena", I18n.lang)
                        marcador: I18n.t("usuarios.marcador_clave", I18n.lang)
                        conOjo: true
                        visibleTexto: raiz.verClave
                        mensajeError: raiz.error("password")
                        nombreObjeto: "campoClave"
                        nombreError: "errorClave"
                        onTocado: raiz.editar("clave")
                        onOjoTocado: raiz.alternarOjoClave()
                    }
                    Campo {
                        id: campoConfirmacion
                        nombre: "confirmacion"
                        x: campoNombre.x; y: campoClave.y + Escala.px(167)
                        width: campoNombre.width
                        etiqueta: I18n.t("formulario.confirmar_contrasena", I18n.lang)
                        conOjo: true
                        visibleTexto: raiz.verConfirmacion
                        mensajeError: raiz.error("confirmacion")
                        nombreObjeto: "campoConfirmacion"
                        nombreError: "errorConfirmacion"
                        onTocado: raiz.editar("confirmacion")
                        onOjoTocado: raiz.alternarOjoConfirmacion()
                    }

                    // ---- Rol: a todo el ancho (P-02), lista táctil sin teclado ----
                    Item {
                        id: filaRol
                        x: Escala.px(61); y: Escala.px(868)
                        width: Escala.px(1027); height: Escala.px(125)

                        Text {
                            text: I18n.t("formulario.rol", I18n.lang)
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
                        }
                        Rectangle {
                            id: recuadroRol
                            objectName: "campoRol"
                            y: Escala.px(43)
                            width: parent.width; height: Escala.px(82)
                            radius: Escala.px(6)
                            border.color: raiz.error("rol") !== "" ? Colores.peligroTexto
                                        : listaRoles.visible ? Colores.accionPrimario : Colores.bordeDivisor
                            border.width: listaRoles.visible || raiz.error("rol") !== "" ? 2 : 1

                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: Escala.px(28)
                                anchors.verticalCenter: parent.verticalCenter
                                readonly property var _elegido: raiz.puente
                                    ? raiz.puente.roles.find(r => r.valor === raiz.rol) : undefined
                                text: _elegido ? _elegido.etiqueta : I18n.t("usuarios.seleccione_rol", I18n.lang)
                                color: _elegido ? Colores.textoPrimario : Colores.textoGuia
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                            }
                            Image {
                                anchors.right: parent.right
                                anchors.rightMargin: Escala.px(40)
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(32); height: Escala.px(32)
                                source: raiz.iconos + (listaRoles.visible ? "chevron_arriba.svg"
                                                                          : "chevron_abajo.svg")
                                sourceSize.width: width
                                sourceSize.height: height
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    if (raiz.teclado)
                                        raiz.teclado.cerrar()
                                    listaRoles.visible = !listaRoles.visible
                                }
                            }
                        }
                        Text {
                            anchors.top: recuadroRol.bottom
                            anchors.topMargin: Escala.px(4)
                            x: Escala.px(4)
                            objectName: "errorRol"
                            text: raiz.error("rol")
                            visible: text !== ""
                            color: Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(18)
                        }
                    }

                    // ---- Estado (ocupa el lugar del Código, eliminado: mockup
                    // nuevo_usuario_sin_codigo.png) ----
                    Text {
                        id: etiquetaEstado
                        x: filaRol.x; y: Escala.px(1047)
                        text: I18n.t("formulario.estado", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                        font.weight: Tipografia.pesoMedium
                    }
                    Rectangle {
                        id: interruptor
                        objectName: "interruptorActivo"
                        x: Escala.px(206); y: Escala.px(1091)
                        width: Escala.px(73); height: Escala.px(39); radius: height / 2
                        color: raiz.activo ? Colores.accionPrimario : Colores.bordeCampo
                        Rectangle {
                            width: parent.height - Escala.px(6); height: width; radius: width / 2
                            anchors.verticalCenter: parent.verticalCenter
                            x: raiz.activo ? parent.width - width - Escala.px(3) : Escala.px(3)
                            color: "white"
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -Escala.px(16)
                            onClicked: raiz.activo = !raiz.activo
                        }
                    }
                    Text {
                        anchors.left: interruptor.right
                        anchors.leftMargin: Escala.px(32)
                        anchors.verticalCenter: interruptor.verticalCenter
                        text: I18n.t("formulario.activo", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                    }

                    // ---- botones ----
                    Rectangle {
                        x: filaRol.x; y: Escala.px(1177)
                        width: Escala.px(433); height: Escala.px(97)
                        radius: Escala.px(8)
                        border.color: Colores.bordeDivisor; border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: I18n.t("acciones.cancelar", I18n.lang)
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
                        }
                        MouseArea { anchors.fill: parent; onClicked: raiz.pulsarCancelar() }
                    }
                    Rectangle {
                        x: Escala.px(567); y: Escala.px(1177)
                        width: Escala.px(508); height: Escala.px(97)
                        radius: Escala.px(8)
                        color: Colores.accionPrimario
                        Row {
                            anchors.centerIn: parent
                            spacing: Escala.px(40)
                            Image {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Escala.px(48); height: Escala.px(48)
                                source: raiz.iconos + "guardar.svg"
                                sourceSize.width: width
                                sourceSize.height: height
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: I18n.t("acciones.guardar_usuario", I18n.lang)
                                color: "white"
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                                font.weight: Tipografia.pesoSemiBold
                            }
                        }
                        MouseArea { anchors.fill: parent; onClicked: raiz.pulsarGuardar() }
                    }
                    // Error que no es de un campo (permiso, sesión, sin conexión, ...)
                    Text {
                        objectName: "errorGeneral"
                        x: filaRol.x; y: Escala.px(1290)
                        width: Escala.px(1075) - filaRol.x
                        visible: text !== ""
                        text: raiz.error("general")
                        wrapMode: Text.WordWrap
                        color: Colores.peligroTexto
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                        font.weight: Tipografia.pesoMedium
                    }

                    // ---- lista de roles (sobre lo demás) ----
                    MouseArea {   // tocar fuera la cierra
                        anchors.fill: parent
                        visible: listaRoles.visible
                        onClicked: listaRoles.visible = false
                    }
                    Rectangle {
                        id: listaRoles
                        objectName: "listaRoles"
                        visible: false
                        // 2 px más ancha a cada lado: tapa el borde de lo que quede debajo
                        x: filaRol.x - Escala.px(2); y: filaRol.y + Escala.px(125) + Escala.px(4)
                        width: filaRol.width + Escala.px(4)
                        height: columnaRoles.height
                        radius: Escala.px(6)
                        border.color: Colores.bordeCampo; border.width: 1
                        clip: true
                        Column {
                            id: columnaRoles
                            width: parent.width
                            Repeater {
                                model: raiz.puente ? raiz.puente.roles : []
                                delegate: Rectangle {
                                    id: opcion
                                    required property var modelData
                                    width: columnaRoles.width; height: Escala.px(82)
                                    color: raiz.rol === modelData.valor ? Colores.accionFondoTenue : "transparent"
                                    Text {
                                        anchors.left: parent.left
                                        anchors.leftMargin: Escala.px(28)
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: opcion.modelData.etiqueta
                                        color: Colores.textoPrimario
                                        font.family: Tipografia.familia
                                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            raiz.rol = opcion.modelData.valor
                                            listaRoles.visible = false
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ]
    }

    // Barra inferior flotante, fuera de la tarjeta (misma colocación que Opciones.qml)
    BarraInferiorMenu {
        id: barraInferior
        objectName: "barraInferiorNuevoUsuario"
        escala: raiz.width / 1196
        // D8-5.2: mismo x y ancho que la tarjeta de contenido de encima
        x: tarjeta.x
        width: tarjeta.width
        y: raiz.height - 171 * escala
        version: I18n.t("app.version", I18n.lang)
        inicioActivo: true
        onAtrasPulsado: raiz.pulsarAtras()
        onInicioPulsado: raiz.pulsarInicio()
    }

    // Confirmación de descarte (D-09, P-06): PanelModal provisional. Su botón
    // inferior es "Seguir editando"; tocar fuera también cierra sin descartar.
    PanelModal {
        id: dialogoDescartar
        objectName: "dialogoDescartar"
        titulo: I18n.t("usuarios.descartar_titulo", I18n.lang)
        textoCerrar: I18n.t("usuarios.seguir_editando", I18n.lang)
        altoTarjeta: Escala.px(560)

        property var _accion: null
        function pedir(accion) { _accion = accion; abrir() }
        function confirmar() {
            const accion = _accion
            _accion = null
            cerrar()
            if (accion)
                accion()
        }
        onVisibleChanged: if (!visible) _accion = null   // cerrado sin descartar

        Column {
            width: parent.width
            spacing: Escala.px(32)
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("usuarios.descartar_mensaje", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
            }
            Rectangle {
                width: Escala.px(360); height: Escala.px(88)
                radius: Escala.px(6)
                anchors.horizontalCenter: parent.horizontalCenter
                border.color: Colores.peligroTexto; border.width: 2
                Text {
                    anchors.centerIn: parent
                    text: I18n.t("acciones.descartar", I18n.lang)
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: dialogoDescartar.confirmar() }
            }
        }
    }
}
