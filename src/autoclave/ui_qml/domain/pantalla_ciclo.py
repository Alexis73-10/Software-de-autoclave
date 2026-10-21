# ui_qml/domain/pantalla_ciclo.py
#
# Datos de la tarjeta de parámetros de la pantalla de ciclo (Pantallas/PantallaPreciclo.qml)
# a partir de las respuestas REST del backend:
#   GET /cycle  -> consignas del ciclo seleccionado (parameters.<seccion>.<nombre>.value)
#   GET /status -> lecturas de cámara (sensors.temperature.camara / sensors.pressure.camara)
#
# Frontera de confianza (§6.1 principio 3 de planeacion_ui_dual_pantalla.md):
# un dato ausente o mal formado se muestra como SIN_DATO, nunca se pinta a
# medias ni tumba el resto de la tarjeta. Punto decimal en presentación
# (TEC-D14, revoca D-19), vía formato_numerico.formatear_decimal.

import math

from autoclave.core.runtime import unidades as u
from autoclave.ui_qml.domain.formato_numerico import formatear_decimal

SIN_DATO = "---"


def _vigentes() -> tuple[str, str, float | None]:
    """(temperatura, presión, P_atm) de presentación (U1/I2, tanda 5): las del
    singleton QML Unidades; sin él, °C y kPa (el comportamiento de siempre)."""
    try:
        from autoclave.ui_qml.bridge.unidades_qml import instancia
        return instancia.temperatura, instancia.presion, instancia._p_atm
    except Exception:
        return u.POR_DEFECTO["temperatura"], u.POR_DEFECTO["presion"], None


def _temp(v: float) -> float:
    return u.temp_a_mostrar(v, _vigentes()[0])


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    if not math.isfinite(valor):
        return None
    return float(valor)


def formatear_temperatura(valor) -> str:
    """Consigna de temperatura: un decimal (134.0)."""
    v = _numero(valor)
    return SIN_DATO if v is None else formatear_decimal(_temp(v), 1)


def formatear_temp_camara(valor) -> str:
    """Lectura de cámara: un decimal y tres dígitos enteros (085.0), como el mockup."""
    v = _numero(valor)
    return SIN_DATO if v is None else f"{_temp(v):05.1f}"


def formatear_minutos(valor) -> str:
    """Tiempos en minutos: sin decimal si es entero (15), si no uno (3.5)."""
    v = _numero(valor)
    if v is None:
        return SIN_DATO
    v = round(v, 1)
    return formatear_decimal(v, 0 if v.is_integer() else 1)


def formatear_presion(valor) -> str:
    """Lectura de presión de cámara en la unidad de presentación (kPa: un
    decimal, 100.8). En psi sin P_atm válida: SIN_DATO, nunca un número
    inventado; el símbolo (psig o inHg) lo da simbolo_presion()."""
    v = _numero(valor)
    if v is None:
        return SIN_DATO
    _t, unidad, p_atm = _vigentes()
    mostrado, simbolo = u.pres_a_mostrar(v, unidad, p_atm)
    if mostrado is None:
        return SIN_DATO
    return formatear_decimal(mostrado, u.DECIMALES.get(simbolo, 1))


def simbolo_presion(valor) -> str:
    """Símbolo de la lectura de presión: kPa/bar/mbar, o psig/inHg según el
    lado de la atmosférica (cambia con el valor). Vacío si no hay dato."""
    _t, unidad, p_atm = _vigentes()
    v = _numero(valor)
    if unidad != "psi":
        return u.simbolo_pres(unidad)
    if v is None or p_atm is None:
        return u.simbolo_pres(unidad)
    return u.pres_a_mostrar(v, unidad, p_atm)[1]


def simbolo_temperatura() -> str:
    return u.simbolo_temp(_vigentes()[0])


def _obtener(datos, *ruta):
    for clave in ruta:
        if not isinstance(datos, dict):
            return None
        datos = datos.get(clave)
    return datos


def parametros_de_ciclo(ciclo) -> dict:
    """Consignas del ciclo seleccionado (respuesta de GET /cycle), ya formateadas."""
    nombre = _obtener(ciclo, "name")
    params = _obtener(ciclo, "parameters")
    return {
        "programa": nombre.upper() if isinstance(nombre, str) and nombre else SIN_DATO,
        "temp_esterilizacion": formatear_temperatura(
            _obtener(params, "esterilizacion", "temperatura_esterilizacion", "value")),
        "tiempo_esterilizacion": formatear_minutos(
            _obtener(params, "esterilizacion", "tiempo_esterilizacion", "value")),
        "tiempo_secado": formatear_minutos(
            _obtener(params, "secado", "tiempo_secado", "value")),
    }


def numero_de_ciclo(ciclo) -> str:
    """Indicativo del ciclo seleccionado ("number" de GET /cycle), dos dígitos (01)."""
    numero = _obtener(ciclo, "number")
    if isinstance(numero, bool) or not isinstance(numero, int) or numero < 1:
        return SIN_DATO
    return f"{numero:02d}"


def lecturas_de_status(status) -> dict:
    """Lecturas de cámara (respuesta de GET /status), ya formateadas."""
    return {
        "temp_camara": formatear_temp_camara(_obtener(status, "sensors", "temperature", "camara")),
        "presion_camara": formatear_presion(_obtener(status, "sensors", "pressure", "camara")),
        "presion_unidad": simbolo_presion(_obtener(status, "sensors", "pressure", "camara")),
        "temp_unidad": simbolo_temperatura(),
    }
