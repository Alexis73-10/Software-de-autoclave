# tests/banco/hor_escenarios_a.py
#
# Tanda horizontal, grupo A (intro, arranque, asistente de instalación y
# sesión). Lo ejecuta tests/banco/hor_capturas.py dentro de su guion, con
# qml(), arnes(), PUENTE_SIMPLE y ACCIONES a la vista. No es una prueba
# automática.

_TEC = "\nPanelTeclado { id: tec; objectName: 'tec' }"

# ── intro y arranque ─────────────────────────────────────────────────────
_PROGRESO = ("QtObject { property real fraccion: 0.55; property string proceso: 'verificando_sensores';"
             " property bool terminado: false; property bool falloBloqueante: false;"
             " property bool completo: false }")


def _esperar_intro(win, h):
    h.QTest.qWait(3600)   # la intro dura 3,5 s: se captura su último cuadro (barra y textos)


ACCIONES["esperar_intro"] = _esperar_intro
qml("intro_final", "IntroArranque { anchors.fill: parent; modelo: 'SPK-SAT 250V2-LAB';"
    " versionSoftware: '1.0.0-beta.1'; progreso: " + _PROGRESO + " }", accion="py:esperar_intro")
qml("barra_reinicio", "BarraReinicioBackend { anchors.fill: parent; progreso: QtObject {"
    " property real fraccion: 0.45; property string proceso: 'verificando_sensores' } }")
qml("reposo_aviso", "Reposo { anchors.fill: parent; tactil: false;"
    " aviso: 'La pantalla 1 está en el asistente de instalación. Termine allí la instalación del equipo.' }")


# ── asistente de instalación (arnés PruebaInstalacion.qml) ──────────────
def _inst(props):
    def accion(win, h):
        inst = h.por_nombre("instalacion")[0]
        for k, v in props:
            inst.setProperty(k, v)
        h.QTest.qWait(300)
    return accion


_LLENO = [("serie", "SN260001"), ("codigo", "ABCDEFGHIJKL"), ("clase", "piso_lab"),
          ("numPuertas", 2), ("tipoPuerta", "advanced"), ("puertaPc", 2), ("nivelEnfriamiento", 2),
          ("capacidadLitros", 250), ("tipoCarga", "V"), ("fuenteVapor", "boiler")]
_PASOS = {
    "inst_activacion_auto": [("automatizado", True)],
    "inst_equipo": [("indice", 1), ("clase", "piso")],
    "inst_puertas": [("clase", "piso"), ("numPuertas", 2), ("tipoPuerta", "advanced"), ("indice", 2)],
    "inst_puertas_una": [("clase", "mesa_b"), ("numPuertas", 1), ("indice", 2)],
    "inst_camara": [("clase", "piso"), ("numPuertas", 2), ("capacidadLitros", 250),
                    ("tipoCarga", "V"), ("indice", 3)],
    "inst_enfriamiento": [("clase", "piso"), ("indice", 4)],
    "inst_vapor": [("clase", "piso"), ("indice", 5)],
    "inst_datos": [("clase", "piso"), ("indice", 6)],
    "inst_contrasenas": [("clase", "piso"), ("indice", 7)],
    "inst_resumen": _LLENO + [("indice", 8)],
    "inst_resumen_auto": _LLENO + [("automatizado", True), ("serie_original", "AB-1234"),
                                   ("modelo_original", "Autoclave XL 500"), ("indice", 8)],
    "inst_listo": [("terminado", True)],
}
for _n, _p in _PASOS.items():
    ACCIONES[_n] = _inst(_p)
    arnes(_n, "PruebaInstalacion.qml", accion="py:" + _n)


def _tocar(nombre, antes=None):
    def accion(win, h):
        if antes:
            antes(win, h)
        objs = h.por_nombre(nombre)
        if objs:
            h.tocar(objs[0])
        h.QTest.qWait(900)
    return accion


ACCIONES["inst_teclado_codigo"] = _tocar("campoCodigo")
arnes("inst_teclado_codigo", "PruebaInstalacion.qml", accion="py:inst_teclado_codigo")
def _inst_editar_clave(win, h):
    # los campos de contraseña son delegados de un Repeater (findChildren no los
    # ve): se abre el teclado como lo haría su toque
    _inst(_PASOS["inst_contrasenas"])(win, h)
    inst = h.por_nombre("instalacion")[0]
    h.QMetaObject.invokeMethod(inst, "editar", h.Q_ARG("QVariant", "confirmacion_ingeniero"),
                               h.Q_ARG("QVariant", ""))
    h.QTest.qWait(900)


ACCIONES["inst_teclado_clave"] = _inst_editar_clave
arnes("inst_teclado_clave", "PruebaInstalacion.qml", accion="py:inst_teclado_clave")

# ── sesión ──────────────────────────────────────────────────────────────
ACCIONES["login_clave"] = _tocar("campoClave")
qml("login_teclado_clave", "Login { anchors.fill: parent; teclado: tec }" + _TEC, accion="py:login_clave")
ACCIONES["login_ayuda"] = _tocar("enlaceOlvidoClave")
qml("login_sin_bd", "Login { anchors.fill: parent; teclado: tec;"
    " puente: QtObject { property bool sinBaseDatos: true } }" + _TEC, accion="py:login_ayuda")
ACCIONES["cambio_confirmacion"] = _tocar("campo_confirmacion")
qml("cambio_clave_teclado", "CambioClave { anchors.fill: parent; teclado: tec }" + _TEC,
    accion="py:cambio_confirmacion")

_PUENTE_NU = ("QtObject { id: pnu; property var roles: [{valor: 'operador', etiqueta: 'Operador'},"
              " {valor: 'supervisor', etiqueta: 'Supervisor'}, {valor: 'administrador', etiqueta: 'Administrador'},"
              " {valor: 'ingeniero', etiqueta: 'Ingeniero'}];"
              " property var longitudesMaximas: ({}); property bool operacionEnCurso: false;"
              " property int altaActual: 0; signal guardadoResuelto(string estado, var errores, string mensaje, int alta);"
              " function estadoDe(x) { return '' } function abandonarPreparacion() {}"
              " function navegar(d) {} function guardar() { return { enviado: false, errores: {} } } }")
ACCIONES["nu_roles"] = _tocar("campoRol")
qml("nuevo_usuario_roles", "NuevoUsuario { anchors.fill: parent; teclado: tec; puente: " + _PUENTE_NU + " }" + _TEC,
    accion="py:nu_roles")
ACCIONES["nu_confirmacion"] = _tocar("campoConfirmacion")
qml("nuevo_usuario_teclado", "NuevoUsuario { anchors.fill: parent; teclado: tec; puente: " + _PUENTE_NU + " }" + _TEC,
    accion="py:nu_confirmacion")
