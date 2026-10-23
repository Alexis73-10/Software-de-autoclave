# core/runtime/salidas_prueba_seguridad.py
#
# S9 (tanda 9), revisión ★ SAF-01 (DECISIÓN SIN CONFIRMAR de la sesión
# principal): D9-1.3 permite el modo prueba con el estado seguro activo, y
# D-ES-15 permite en él todas las salidas. Así, con la cámara presurizada, un
# técnico podía desbloquear y abrir la puerta desde Entradas / Salidas (las
# puertas no se actualizan en pausa y el interlock de ServicioPuertas no
# aplica a las órdenes directas).
#
# Excepciones a D-ES-15, además del aire atmosférico (D8-3.19):
# - apertura y desbloqueo de puertas: NO se encienden mientras el estado
#   seguro esté activo, haya una recuperación de arranque pendiente o la
#   cámara no sea segura (o no haya dato para saberlo);
# - descompresión rápida, descompresión de chaqueta y vapor de cámara: NO se
#   encienden mientras el estado seguro esté activo o haya una recuperación
#   de arranque pendiente.
# La descompresión lenta (el venteo seguro) y el bloqueo de puerta (cerrar el
# cerrojo) no se tocan. Pura: no toca salidas.

SALIDAS_PUERTA = ("abrir_puerta_1", "abrir_puerta_2", "desbloqueo_puerta_1", "desbloqueo_puerta_2")
SALIDAS_VAPOR = ("descompresion_rapida", "descompresion_chaqueta", "vapor_camara")

# Códigos de rechazo (catálogo: io.err_*, vía sesion_backend)
CAMARA_NO_SEGURA = "salida_prueba_camara_no_segura"
ESTADO_SEGURO = "salida_prueba_estado_seguro"

MOTIVOS = {
    CAMARA_NO_SEGURA: "La cámara no es segura: no se puede desbloquear ni abrir la puerta",
    ESTADO_SEGURO: ("La cámara se está llevando a estado seguro: no se puede encender "
                    "esta salida"),
}


def bloqueadas(estado_seguro_activo: bool, recuperacion_pendiente: bool,
               camara_segura: bool) -> dict[str, str]:
    """{clave de salida: código de rechazo} de las salidas que el modo prueba
    no puede encender ahora. Falla cerrada: cualquier valor distinto de True
    en `camara_segura` cuenta como no segura."""
    protocolo = estado_seguro_activo is not False or recuperacion_pendiente is not False
    resultado = {}
    if protocolo or camara_segura is not True:
        # el texto dice por qué: la cámara no segura manda sobre el protocolo
        codigo = CAMARA_NO_SEGURA if camara_segura is not True else ESTADO_SEGURO
        resultado.update({k: codigo for k in SALIDAS_PUERTA})
    if protocolo:
        resultado.update({k: ESTADO_SEGURO for k in SALIDAS_VAPOR})
    return resultado


def todas() -> dict[str, str]:
    """Falla cerrada (error al evaluar): todas bloqueadas."""
    return bloqueadas(True, True, False)
