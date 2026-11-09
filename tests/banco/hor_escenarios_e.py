# tests/banco/hor_escenarios_e.py
#
# Tanda horizontal (9-nov), grupo E: modales, diálogos, paneles superpuestos,
# teclados en pantalla y la composición de Main.qml. Lo ejecuta
# tests/banco/hor_capturas.py (exec) con qml(), arnes(), PUENTE_SIMPLE, ALARMA
# y ACCIONES a la vista. No es una prueba automática.

from PySide6.QtCore import Property as _PropE, QObject as _QObjE, Signal as _SigE, Slot as _SlotE

_ALARMAS_E = ALARMA + (
    ';append({ id: "PARO", level: "EMERGENCIA", description: "Paro de emergencia activado",'
    ' source_state: "PREPARACION", priority: "alta" })'
    ';append({ id: "SEN-04", level: "FALLA", description: "Sensor de presión de cámara sin lectura;'
    ' revise el transmisor y el cableado", source_state: "PREPARACION", priority: "media" })'
    ';append({ id: "SUM-03", level: "ALERTA", description: "Suministro de agua de la bomba de vacío bajo",'
    ' source_state: "PREPARACION", priority: "baja" })')

qml("e_notificaciones", """
PanelNotificaciones {
    id: pn; objectName: "pn"
    titulo: "Notificaciones"; textoCerrar: "Cerrar"; textoSinAlarmas: "Sin notificaciones"
    puente: puenteFalso
    alarmas: ListModel { Component.onCompleted: { %s } }
    visible: true
}
""" % _ALARMAS_E, accion="py:e_expandir_grupos")


def _e_expandir_grupos(win, h):
    for n in ("grupoAlarmas", "grupoAvisos"):
        for o in h.por_nombre(n):
            o.setProperty("expandido", True)


ACCIONES["e_expandir_grupos"] = _e_expandir_grupos

_DETALLE_E = {
    "id": "SEN-04", "codigo": "SEN-04", "codigoVisible": "SEN-04", "level": "FALLA", "priority": "media",
    "titulo": "Sensor de presión de cámara sin lectura",
    "description": "El transmisor de presión de la cámara no entrega lectura válida desde hace más de "
                   "3 segundos. El ciclo en curso se detiene y la cámara queda en espera hasta que vuelva "
                   "la lectura.",
    "accion": "Revise el transmisor de presión, su alimentación de 24 V y el cableado hasta el módulo "
              "E/S. Si la lectura no vuelve, llame al servicio técnico.",
    "aparecida": "2026-11-09T10:21:07", "estado": "activa",
}
qml("e_detalle_alarma", """
VentanaDetalleAlarma { id: va; objectName: "va" }
""", accion="py:e_abrir_detalle")


def _e_abrir_detalle(win, h):
    for o in h.por_nombre("va"):
        h.QMetaObject.invokeMethod(o, "abrir", h.Q_ARG("QVariant", _DETALLE_E))


ACCIONES["e_abrir_detalle"] = _e_abrir_detalle

_FILAS_E = [
    ("modelo", "ACV-PISO-2P-150-VC"), ("serie", "SN260001"), ("serial_especifika", "SN260001"),
    ("id_maquina", "ACV-2026-SN260001"), ("puertas", "2"), ("puerta_pantalla", "Puerta 1 (carga)"),
    ("enfriamiento", "Chaqueta"), ("fecha_instalacion", "2026-10-22"), ("ciclos_realizados", "1284"),
    ("ultimo_ciclo", "2026-11-09 08:14"), ("ultimo_mantenimiento", "2026-09-30"),
    ("ciclos_restantes", "216"), ("version_software", "1.0.0-beta.1"), ("enlace_io", "modbus"),
    ("emparejamiento_modulo_es", None), ("version_modulo_es", "9232-0-13 / v1.0"),
    ("id_modulo_es", "005404849DB1"),
]
_FILAS_QML_E = ",\n".join(
    '{clave: "%s", valor: %s, disponible: true}' % (c, '"%s"' % v if v is not None else "null")
    for c, v in _FILAS_E)
_COMANDOS_E = """
QtObject {
    id: comandosFalsos
    property bool ventanaPrincipal: true
    property bool fueraDeCiclo: true
    property bool camaraNoSegura: true
    property bool apagadoRechazado: false
    property bool ocupado: false
    property string mensaje: ""
}
"""
qml("e_equipo", """
PanelEquipo {
    objectName: "pe"
    titulo: "Información del equipo"; textoCerrar: "Cerrar"
    comandosSistema: comandosFalsos
    filas: [%s]
    visible: true
}
""" % _FILAS_QML_E, extra=PUENTE_SIMPLE + _COMANDOS_E)
qml("e_equipo_apagar", """
PanelEquipo {
    objectName: "pe"
    titulo: "Información del equipo"; textoCerrar: "Cerrar"
    comandosSistema: comandosFalsos
    filas: [%s]
    visible: true
}
""" % _FILAS_QML_E, extra=PUENTE_SIMPLE + _COMANDOS_E, accion="click:botonApagarEquipo")

qml("e_modal_confirmacion", """
ModalConfirmacion {
    visible: true
    titulo: "Confirmar el resultado del ciclo"
    cuerpo: "El ciclo 0042 terminó con fallo (CIC-12, aire o no condensables en la cámara). "
            + "Al confirmar, el equipo vuelve a la preparación y podrá abrir la puerta cuando la cámara "
            + "esté en condiciones seguras."
    nota: "La carga de este ciclo no debe usarse: repita el ciclo con una carga nueva."
    textoAccion: "Confirmar"
}
""")

qml("e_dialogo_confirmacion", """
DialogoConfirmacion {
    visible: true
    mensaje: "¿Apagar el equipo?\\n\\nLa cámara no está en condiciones seguras: no abra la puerta hasta que baje la presión."
    textoConfirmar: "Apagar equipo"
    textoCancelar: "Cancelar"
    colorConfirmar: Colores.peligroFuerte
}
""")

_OPERADORES_E = ",".join('{id: %d, nombre: "%s"}' % (i + 1, n) for i, n in enumerate([
    "Ana María Rodríguez", "Carlos Pérez", "Luisa Fernanda Gómez Castañeda", "Jorge Iván Restrepo",
    "Marta Lucía Ospina", "Pedro Nel Martínez", "Sandra Milena Torres", "Óscar Eduardo Vargas Londoño",
    "Diana Patricia Cárdenas", "Felipe Andrés Hoyos"]))
qml("e_modal_operador", """
ModalOperador {
    objectName: "mo"
    operadores: [%s]
    elegido: 3
    mensajeClave: "operador_ciclo.err_requerido"
}
""" % _OPERADORES_E)


# Main.qml con OPCIONES a la vista y la sesión sin conexión: aviso superpuesto
class _SesionSinConexionE(_QObjE):
    cambio = _SigE()
    cierrePorDesconexion = _SigE(str)
    cierrePorInactividad = _SigE()
    sesionInvalida = _SigE()

    def __init__(self):
        super().__init__()
        self._modo = False

    @_PropE(bool, notify=cambio)
    def sinConexion(self):
        return True

    @_PropE(str, notify=cambio)
    def tiempoParaCierre(self):
        return "0:12"

    @_PropE(bool, notify=cambio)
    def sesionActiva(self):
        return True

    def _get_modo(self):
        return self._modo

    def _set_modo(self, v):
        self._modo = bool(v)

    modoPrueba = _PropE(bool, _get_modo, _set_modo, notify=cambio)

    @_SlotE(bool, bool)
    def vigilar(self, conectado, con_token):
        pass


_SESION_E = _SesionSinConexionE()
arnes("e_main_sin_conexion", "../Main.qml", {"sesion": _SESION_E}, accion="py:e_main_opciones")


def _e_main_opciones(win, h):
    h.QMetaObject.invokeMethod(win, "abrirConfiguracion")
    h.QTest.qWait(900)


ACCIONES["e_main_opciones"] = _e_main_opciones

# teclados sobre las demás pantallas que los usan (para ver si tapan el campo)
qml("e_cambio_clave_teclado",
    "CambioClave { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }",
    accion="teclado_alfa")
qml("e_nuevo_usuario_teclado",
    "NuevoUsuario { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }",
    accion="teclado_alfa")
