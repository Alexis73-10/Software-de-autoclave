# core/runtime/salidas_prueba_seguridad.py
#
# S9 (tanda 9), revisión ★ SAF-01 (DECISIÓN SIN CONFIRMAR de la sesión
# principal): D9-1.3 permite el modo prueba con el estado seguro activo, y
# D-ES-15 permite en él todas las salidas. Así, con la cámara presurizada, un
# técnico podía desbloquear y abrir la puerta desde Entradas / Salidas (las
# puertas no se actualizan en pausa y el interlock de ServicioPuertas no
# aplica a las órdenes directas).
#
# Tanda 17 (ESG-02, decisión de Cristian, 26-oct 16:46) reemplaza SAF-01:
#
# - Bloqueos PROPIOS del estado seguro (código ESTADO_SEGURO; también con la
#   recuperación de arranque pendiente, que usa el mismo código): con LECTURA
#   VIGENTE de presión de cámara se retiran (el modo prueba ya pausa el
#   protocolo): quedan libres la descompresión rápida, la de chaqueta, el aire
#   comprimido de cámara, el vapor de generador y de caldera, y el vapor de
#   cámara salvo la protección 3. Sin lectura vigente de presión se mantienen
#   TODOS los bloqueos de antes (también las puertas).
# - Protecciones del modo prueba que rigen SIEMPRE (con o sin estado seguro).
#   Fallan cerradas: sin dato no se permite.
#   1. abrir_puerta_N y 2. desbloqueo_puerta_N (vacío al empaque): se rechazan
#      si la cámara no es segura EN PRESIÓN según camara_segura (fuera de
#      presion_atmosferica ± rango_presion_atm, también en vacío, o sin
#      lectura vigente): CAMARA_PRESURIZADA.
#      Además se conserva la regla anterior de puertas con la cámara no segura
#      por otra causa (temperatura del Principal, configuración):
#      CAMARA_NO_SEGURA (DECISIÓN SIN CONFIRMAR: ESG-02 no la retira).
#      bomba_vacio no se bloquea: solo lleva vacío al empaque con
#      desbloqueo_puerta_N abierto (AdvancedDoor enciende las dos), que ya está
#      protegido; sola evacúa la cámara por vacio_camara (DECISIÓN SIN CONFIRMAR).
#   3. vapor_camara: se rechaza si alguna puerta instalada no está confirmada
#      cerrada (puerta_N_cerrada falso, sin lectura o DI no vigente):
#      PUERTA_ABIERTA.
#   El lazo (ControlLoop, paso 2e) apaga en el mismo tick una salida que pasa
#   a estar bloqueada con la orden ya dada, y avisa en Entradas / Salidas.
# - Se conserva el corte del aire atmosférico (D8-3.19, aire_atmosferico_prueba).
#   La descompresión lenta (el venteo seguro) y el bloqueo de puerta (cerrar el
#   cerrojo) no se tocan. Pura: no toca salidas.

SALIDAS_PUERTA = ("abrir_puerta_1", "abrir_puerta_2", "desbloqueo_puerta_1", "desbloqueo_puerta_2")
SALIDAS_VAPOR = ("descompresion_rapida", "descompresion_chaqueta", "vapor_camara",
                 # revisión ★ pasada 2, P-a (DECISIÓN SIN CONFIRMAR): pueden
                 # presurizar o calentar la cámara; vapor_chaqueta no entra a
                 # la cámara y sigue permitida (PREGUNTA PARA CRISTIAN)
                 "aire_comprimido_camara", "vapor_generador", "vapor_caldera")
# ESG-02, protección 3
SALIDA_VAPOR_CAMARA = "vapor_camara"

# Códigos de rechazo (catálogo: io.err_*, vía sesion_backend)
CAMARA_NO_SEGURA = "salida_prueba_camara_no_segura"
ESTADO_SEGURO = "salida_prueba_estado_seguro"
# ESG-02 (textos F3: io.err_puerta_camara_presurizada, io.err_vapor_puerta_abierta)
CAMARA_PRESURIZADA = "salida_prueba_camara_presurizada"
PUERTA_ABIERTA = "salida_prueba_puerta_abierta"

MOTIVOS = {
    CAMARA_NO_SEGURA: "La cámara no es segura: no se puede desbloquear ni abrir la puerta",
    ESTADO_SEGURO: ("La cámara se está llevando a estado seguro: no se puede encender "
                    "esta salida"),
    CAMARA_PRESURIZADA: ("No se puede abrir ni desbloquear la puerta: la cámara está "
                         "presurizada o en vacío, o no hay lectura de presión"),
    PUERTA_ABIERTA: ("No se puede abrir el vapor de cámara: hay una puerta abierta o sin "
                     "confirmación de cerrada"),
}

# ESG-02: aviso (clave i18n, F3) para la pantalla de Entradas / Salidas cuando
# el lazo apaga una salida ya encendida
AVISOS_CORTE = {
    CAMARA_PRESURIZADA: "io.ui.aviso_salida_cortada_presion",
    PUERTA_ABIERTA: "io.ui.aviso_vapor_cortado_puerta",
}


def bloqueadas(estado_seguro_activo: bool, recuperacion_pendiente: bool,
               camara_segura: bool, presion_vigente: bool = False,
               presion_segura: bool | None = None,
               puertas_cerradas: bool | None = None) -> dict[str, str]:
    """{clave de salida: código de rechazo} de las salidas que el modo prueba
    no puede encender ahora. Falla cerrada: cualquier valor distinto de True
    cuenta como no seguro / sin dato.

    - `camara_segura`: camara_segura.evaluar completo (presión y temperatura).
    - `presion_vigente`: hay lectura vigente de presión de cámara (ESG-02: solo
      así se retiran los bloqueos propios del estado seguro). Por omisión
      False: se mantienen todos los de antes.
    - `presion_segura`: la presión (vigente) está en atm ± rango (ESG-02,
      protecciones 1 y 2). None = no evaluada aparte: rige `camara_segura`,
      que ya incluye la presión.
    - `puertas_cerradas`: todas las puertas instaladas confirmadas cerradas
      (ESG-02, protección 3). None = sin dato: vapor de cámara bloqueado."""
    protocolo = estado_seguro_activo is not False or recuperacion_pendiente is not False
    # ESG-02: sin lectura vigente de presión, los bloqueos del estado seguro siguen
    bloqueo_protocolo = protocolo and presion_vigente is not True
    resultado = {}
    if presion_segura is not None and presion_segura is not True:
        codigo_puerta = CAMARA_PRESURIZADA
    elif camara_segura is not True:
        codigo_puerta = CAMARA_NO_SEGURA
    elif bloqueo_protocolo:
        codigo_puerta = ESTADO_SEGURO
    else:
        codigo_puerta = None
    if codigo_puerta is not None:
        resultado.update({k: codigo_puerta for k in SALIDAS_PUERTA})
    if bloqueo_protocolo:
        resultado.update({k: ESTADO_SEGURO for k in SALIDAS_VAPOR})
    if puertas_cerradas is not True and SALIDA_VAPOR_CAMARA not in resultado:
        resultado[SALIDA_VAPOR_CAMARA] = PUERTA_ABIERTA
    return resultado


def todas() -> dict[str, str]:
    """Falla cerrada (error al evaluar): todas bloqueadas."""
    return bloqueadas(True, True, False)
