# core/runtime/aire_atmosferico_prueba.py
#
# D8-3.19 (tanda 8) ★: en modo prueba, `aire_atmosferico_camara` es la ÚNICA
# excepción a D-ES-15 ("el modo prueba permite todas las salidas"). Abrirla con
# la cámara presurizada sacaría vapor por la entrada de aire. Solo se permite
# si hay lectura de presión de cámara y no supera la atmosférica de referencia
# más la brecha (los mismos parámetros del equipo que "cámara segura":
# `presion_atmosferica` + `rango_presion_atm`). En vacío sí se permite: es
# justamente para lo que sirve (romper el vacío).
#
# Falla cerrada: se rechaza sin lectura (None: el transductor sin señal la
# entrega así cuando se integre D8-1, rama S1), con una lectura por debajo del
# piso físico creíble o sin la referencia configurada. Pura: no toca salidas.
#
# Piso (revisión SEN-01 / SAF-01 / TMG-02 de E1): hoy `convert_pressures`
# recorta con max(0.0, ...) y un lazo de 4-20 mA abierto se lee 0,0 kPa, que
# sin el piso pasaría por "cámara en vacío" y permitiría abrir. Ninguna bomba
# de vacío del equipo llega a 1 kPa absoluto: por debajo, "sin lectura".
#
# Señal cruda (tercera revisión, SEN-01 / SEN-03): con la calibración de
# fábrica (adc_min 5 → 2 kPa) un lazo abierto (ADC 0) se lee ~1,5 kPa, sobre
# el piso; y la mediana y el filtro tardan 2-3 tramas en bajar. Por eso además
# se exige `senal_presente is True`: la cuenta ADC cruda del canal de
# pres_camara por encima de su adc_min (Units.senal_presion_presente).

import math

CLAVE_ATM = "presion_atmosferica"      # clave canónica (alias viejo: presion_admosferica)
CLAVE_RANGO = "rango_presion_atm"
PISO_LECTURA_KPA = 1.0

# Nombres de la salida: el del YAML / de la pantalla y el de EstadoAutoclave
# (errata histórica `admosferico`)
NOMBRES = frozenset({"aire_atmosferico_camara", "aire_admosferico_camara"})
CLAVE_ESTADO = "aire_admosferico_camara"

# Códigos de rechazo (catálogo: io.err_aire_*, vía sesion_backend)
CON_PRESION = "aire_atmosferico_con_presion"
SIN_PRESION = "aire_atmosferico_sin_presion"
SIN_REFERENCIA = "aire_atmosferico_sin_referencia"

MOTIVOS = {
    CON_PRESION: "La cámara tiene presión: no se puede abrir el aire atmosférico",
    SIN_PRESION: "Sin lectura de presión de cámara: no se puede abrir el aire atmosférico",
    SIN_REFERENCIA: "Falta la presión atmosférica de referencia: no se puede abrir el aire atmosférico",
}


def es_salida(nombre: str) -> bool:
    return nombre in NOMBRES


def _numero(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def senal_camara(units, leido_mono=None) -> bool:
    """True solo si `units` confirma señal cruda en el canal de pres_camara.
    `leido_mono`: instante en que el lazo leyó de Units la presión publicada
    (SAF-01/TMG-02: debe ser posterior a la confirmación de la señal).
    Cualquier error o respuesta distinta de True, o sin `leido_mono`: False
    (falla cerrada)."""
    from autoclave.core.runtime.status import EstadoAutoclave
    if leido_mono is None:
        return False
    try:
        return units.senal_presion_presente(EstadoAutoclave.map_pres["pres_camara"],
                                            leido_mono=leido_mono) is True
    except Exception:
        return False


def evaluar(estado, config, senal_presente=None) -> tuple[bool, str]:
    """(permitido, código). Código "" si se permite. `senal_presente`: la
    cuenta ADC cruda del canal está sobre su adc_min; distinto de True
    (incluido el valor por defecto) cuenta como "sin lectura"."""
    if senal_presente is not True:
        return False, SIN_PRESION
    pres = _numero((getattr(estado, "sensores_pres", None) or {}).get("pres_camara"))
    if pres is None or pres < PISO_LECTURA_KPA:
        return False, SIN_PRESION
    atm = _numero(config.get(CLAVE_ATM))
    rango = _numero(config.get(CLAVE_RANGO))
    if atm is None or rango is None:
        return False, SIN_REFERENCIA
    if pres > atm + rango:
        return False, CON_PRESION
    return True, ""
