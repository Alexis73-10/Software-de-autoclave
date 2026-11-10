# tests/banco/hor_escenarios_b.py
#
# Tanda horizontal (9-nov), grupo B: escenarios de captura de Preciclo (dos
# puertas) y Ciclo en curso. No se ejecuta solo: lo carga tests/banco/hor_capturas.py
# dentro de su guion, con qml(), arnes(), PUENTE_PRECICLO, PUENTE_SIMPLE, ALARMA,
# fases(), ACCIONES y (del propio guion) fin_de_ciclo, FALLO y ALARMAS a la vista.
#
#   python tests/banco/hor_capturas.py --escenarios b_ciclo_pantalla_completa ...
#
# Nombres con el prefijo b_.
# flake8: noqa  (los nombres los define el guion que hace exec de este archivo)

# ---------------- Preciclo ----------------
_PUENTE_B = """
QtObject {
    id: puenteP
    objectName: "puente"
    property bool connected: %(conectado)s
    property string estadoModuloEs: "ok"
    property string cicloActivo: "04"
    property string programa: %(programa)s
    property string tempEsterilizacion: "134.0"
    property string tiempoEsterilizacion: "3.5"
    property string tiempoSecado: "15"
    property string tempCamara: "098.2"
    property string tempReferencia: "096.4"
    property string presionCamara: "084.1"
    property string estadoEquipo: %(estado)s
    property string machineState: %(maquina)s
    property bool modoPrueba: %(prueba)s
    property int door: %(puerta)s
    property string doorState: %(estado_puerta)s
    property bool doorOpen: doorState === "ABIERTO"
    property bool puertaConActuador: %(actuador)s
    property bool listoParaCiclo: %(listo)s
    property bool inicioCicloVisible: %(inicio)s
    property ListModel alarms: ListModel {
        Component.onCompleted: { %(alarmas)s }
    }
}
"""


def _puente_b(**k):
    base = {"conectado": "true", "programa": '"BOWIE & DICK"', "estado": '"listo"',
            "maquina": '"PREPARADO"', "prueba": "false", "puerta": "1", "estado_puerta": '"CERRADO"',
            "actuador": "true", "listo": "true", "inicio": "true", "alarmas": ""}
    base.update(k)
    return _PUENTE_B % base


_MUCHAS = ";".join(
    'append({ id: "AL%02d", level: "ALERTA", description: "Aviso de prueba número %d con un texto '
    'largo para ver el salto de línea dentro de la columna derecha de la tarjeta", '
    'source_state: "PREPARACION", priority: "%s" })' % (i, i, ("alta", "media", "baja")[i % 3])
    for i in range(1, 13))

_PRECICLO = "PantallaPreciclo { anchors.fill: parent; puente: puenteP }"

qml("b_preciclo_puerta2", _PRECICLO,
    _puente_b(puerta="2", estado_puerta='"ABIERTO"', listo="false", inicio="false",
              estado='"no_preparado"', maquina='"PREPARACION"', alarmas=ALARMA))
qml("b_preciclo_puerta2_manual", _PRECICLO,
    _puente_b(puerta="2", actuador="false"))
qml("b_preciclo_modo_prueba", _PRECICLO,
    _puente_b(prueba="true", inicio="false", estado='"no_preparado"', maquina='"PREPARACION"'))
qml("b_preciclo_falla", _PRECICLO,
    _puente_b(maquina='"FALLA"', estado='"no_preparado"', listo="false", inicio="false", alarmas=ALARMA))
qml("b_preciclo_sin_conexion", _PRECICLO, _puente_b(conectado="false", alarmas=ALARMA))
qml("b_preciclo_muchas_alarmas", _PRECICLO,
    _puente_b(listo="false", inicio="false", estado='"no_preparado"', maquina='"PREPARACION"',
              alarmas=_MUCHAS))
qml("b_preciclo_programa_largo", _PRECICLO,
    _puente_b(programa='"INSTRUMENTAL ENVUELTO 134 °C LARGO"'))

# selector de programa abierto (tocar el recuadro «Programa»)
_SELECTOR = """
QtObject {
    id: selectorB
    property bool sinConexion: false
    property string mensaje: ""
    property bool seleccionable: true
    property bool ocupado: false
    property var programas: [
        { numero: "01", nombre: "Instrumental 134 °C", parametros: "134 °C · 4 min · secado 15 min", masUsado: true, seleccionado: true, cycleId: "a" },
        { numero: "02", nombre: "Textiles 121 °C", parametros: "121 °C · 20 min · secado 20 min", masUsado: true, seleccionado: false, cycleId: "b" },
        { numero: "03", nombre: "Bowie & Dick", parametros: "134 °C · 3.5 min", masUsado: false, seleccionado: false, cycleId: "c" },
        { numero: "04", nombre: "Líquidos", parametros: "121 °C · 30 min", masUsado: false, seleccionado: false, cycleId: "d" }
    ]
    signal elegido()
    function limpiarMensaje() {}
    function cargar() {}
    function elegir(id) {}
}
"""
qml("b_preciclo_selector",
    "PantallaPreciclo { anchors.fill: parent; puente: puenteP; selectorCiclo: selectorB }",
    _puente_b() + _SELECTOR, accion="click:zonaProgramaTocable")

# ---------------- Ciclo en curso (arnés T21) ----------------
_EXITOSO_OBS = {"tipo": "exitoso", "hora_fin": "2026-10-28T13:51:07",
                "observaciones": [{"sensor": "Referencia 1", "hora": "13:12", "fase": "esterilizacion"}]}
_SEN11 = [{"codigo": "SEN-11", "nivel": "AVISO", "titulo": "Sensor de referencia sin lectura",
           "descripcion": "", "valores": {"sensor": "Referencia 1", "fase": "Esterilización"},
           "aparecida": "2026-10-28T13:12:03", "resuelta": None}]
_fin_obs = fin_de_ciclo.armar(fin_de_ciclo.normalizar_terminacion(_EXITOSO_OBS, "exitoso"),
                              fin_de_ciclo.normalizar_alarmas(_SEN11), "es")
_COMPLETAS = [{"fase": f, "estado": "completada"} for f in
              ("precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado")]


def _fijar(nombre, **props):
    def accion(win, h):
        for o in h.por_nombre(nombre):
            for k, v in props.items():
                o.setProperty(k, v)
    return accion


def _tiempos(win, h):
    # abre el desplegable «Tiempos» tocando el botón (sin objectName): su
    # posición en la tarjeta es (856 + dw, 43) px del mockup, 154 × 58
    for g in h.por_nombre("graficaCicloEnCurso"):
        e, dw = g.property("escala"), (g.property("dw") or 0)
        p = g.mapToScene(h.QPointF((856 + dw + 77) * e, (43 + 29) * e)).toPoint()
        h.QTest.mouseClick(win, h.Qt.LeftButton, h.Qt.NoModifier, p)
        break


def _zoom(win, h):
    for g in h.por_nombre("graficaCicloEnCurso"):
        h.QMetaObject.invokeMethod(g, "fijarVentana", h.Q_ARG("QVariant", 15), h.Q_ARG("QVariant", 25),
                                   h.Q_ARG("QVariant", 110), h.Q_ARG("QVariant", 135))
        g.setProperty("cursorMin", 20.0)
        break


ACCIONES["b_pantalla_completa"] = _fijar("pantallaCiclo", pantallaCompleta=True)
ACCIONES["b_vista_grafica"] = _fijar("pantallaCiclo", vistaGrafica=True)
ACCIONES["b_ver_observaciones"] = _fijar("pantallaCiclo", verObservaciones=True)
ACCIONES["b_tiempos"] = _tiempos
ACCIONES["b_zoom"] = _zoom

_EN_CURSO = {"resultado": "", "fin": {}, "fases": fases("esterilizacion", "activa")}
arnes("b_ciclo_pantalla_completa", "PruebaFinDeCiclo.qml", _EN_CURSO, accion="py:b_pantalla_completa")
arnes("b_ciclo_tiempos", "PruebaFinDeCiclo.qml", _EN_CURSO, accion="py:b_tiempos")
arnes("b_ciclo_zoom_lupa", "PruebaFinDeCiclo.qml", _EN_CURSO, accion="py:b_zoom")
arnes("b_ciclo_sin_conexion", "PruebaFinDeCiclo.qml", {**_EN_CURSO, "conectado": False})
arnes("b_fin_fallido_grafica", "PruebaFinDeCiclo.qml",
      {"resultado": "fallo", "fin": _fin, "fases": fases("esterilizacion", "fallida")},
      accion="py:b_vista_grafica")
arnes("b_fin_observaciones_pildora", "PruebaFinDeCiclo.qml",
      {"resultado": "exitoso", "fin": _fin_obs, "fases": _COMPLETAS})
arnes("b_fin_observaciones_panel", "PruebaFinDeCiclo.qml",
      {"resultado": "exitoso", "fin": _fin_obs, "fases": _COMPLETAS}, accion="py:b_ver_observaciones")
arnes("b_fin_estado_seguro_modal", "PruebaFinDeCiclo.qml",
      {"resultado": "fallo", "fin": _fin, "fases": fases("esterilizacion", "fallida"), "ackEstadoSeguro": True},
      accion="click:botonCancelarCiclo")

# espera de la entrega de la cámara (ENT-09), con el botón forzado del ingeniero
_PUENTE_CICLO = """
QtObject {
    id: puenteC
    objectName: "puente"
    property bool connected: true
    property string estadoModuloEs: "ok"
    property string cicloActivo: "07"
    property string programa: "LÍQUIDOS 121 °C"
    property string tempEsterilizacion: "121.0"
    property string tiempoEsterilizacion: "30"
    property string tiempoSecado: "0"
    property string tempCamara: "104.2"
    property string tempReferencia: "112.8"
    property string presionCamara: "131.5"
    property bool ackConfirmaEstadoSeguro: false
}
QtObject {
    id: comandosC
    property bool ocupado: false
    property string error: ""
    property string aviso: ""
    property bool rolIngeniero: %(ingeniero)s
    function refrescarRol() {}
    function cancelar() {}
    function confirmar() {}
    function descartarError() {}
}
QtObject {
    id: infoC
    property string modelo: "SPK-SAT 45H"
    property string serie: "Sn123456"
    property var filas: []
    function actualizar() {}
}
"""
_CICLO_ESPERA = """PantallaCicloEnCurso {
    objectName: "pantallaCiclo"
    anchors.fill: parent
    puente: puenteC; comandos: comandosC; infoEquipo: infoC
    resultado: "exitoso"; entregada: false; forzable: true
    fases: %s
    transcurridoS: 3312
}""" % str(_COMPLETAS).replace("'", '"')
qml("b_ciclo_espera_entrega_ingeniero", _CICLO_ESPERA, _PUENTE_CICLO % {"ingeniero": "true"})
qml("b_ciclo_espera_entrega", _CICLO_ESPERA, _PUENTE_CICLO % {"ingeniero": "false"})
