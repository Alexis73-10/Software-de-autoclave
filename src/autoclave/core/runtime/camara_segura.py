# core/runtime/camara_segura.py
#
# Condición "cámara segura" (planeacion_fin_de_ciclo_y_puertas.md §5, E2;
# tanda 2026-10-14 §1.1):
#
#   camara_segura = presión de cámara en [atm − rango_presion_atm, atm + rango_presion_atm]
#                   Y temperatura del sensor Principal ≤ temp_max_apertura
#
# Falla cerrada: sin lectura válida o sin configuración, NO es segura. La usan
# /status ("NO ABRIR"), la condición de inicio de ciclo (D-04), el interlock de
# apertura de puertas y "Apagar equipo" (§16).

import math

from autoclave.core.runtime.sensores_ciclo import temp_seguridad
from autoclave.core.runtime.motivos import Motivo

CLAVE_ATM = "presion_admosferica"      # nombre real de la clave en global_params.json
CLAVE_RANGO = "rango_presion_atm"
CLAVE_TEMP_MAX = "temp_max_apertura"


def _numero(valor) -> float | None:
    """Número finito o None (bool no cuenta como número)."""
    if isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# Hotfix ES (6-nov): los motivos de cámara no segura llevan el valor medido
# y su límite ("Temperatura 92 °C, máximo 80 °C"); la UI los muestra en NO
# ABRIR y en el bloqueo de inicio (motivos.py presenta temp_max/pres_max/
# pres_min en las unidades vigentes).
def _sobrepresion(pres: float, maximo: float) -> Motivo:
    return Motivo("sobrepresion", f"Sobrepresión en cámara: {pres:.0f} kPa, máximo {maximo:.0f} kPa",
                  pres=pres, pres_max=maximo)


def _vacio(pres: float, minimo: float) -> Motivo:
    return Motivo("vacio", f"Cámara en vacío: {pres:.0f} kPa, mínimo {minimo:.0f} kPa",
                  pres=pres, pres_min=minimo)


def _temp_alta(temp: float, maximo: float) -> Motivo:
    return Motivo("temp_alta", f"Temperatura {temp:.0f} °C, máximo {maximo:.0f} °C",
                  temp=temp, temp_max=maximo)


def lectura_presion(estado) -> float | None:
    """Presión de cámara (kPa abs) como número finito, o None."""
    try:
        return _numero(estado.sensores_pres.get("pres_camara"))
    except Exception:
        return None


def evaluar_presion(estado, config, datos_vigentes=True) -> tuple[bool, str]:
    """Tanda 17 (ESG-02): solo la parte de PRESIÓN del criterio de evaluar():
    (segura, motivo). Segura = lectura vigente y dentro de
    [atm − rango_presion_atm, atm + rango_presion_atm]; sobrepresión y vacío
    no son seguros. Falla cerrada: sin datos vigentes, sin lectura o sin
    configuración, NO es segura."""
    if not datos_vigentes:
        return False, Motivo("sin_datos_vigentes", "Sin conexión con el módulo E/S: datos no vigentes")
    faltan = [c for c in (CLAVE_ATM, CLAVE_RANGO) if _numero(config.get(c)) is None]
    if faltan:
        return False, Motivo("falta_config", f"Falta configuración: {', '.join(faltan)}",
                             claves=", ".join(faltan))
    atm = _numero(config.get(CLAVE_ATM))
    rango = _numero(config.get(CLAVE_RANGO))
    pres = lectura_presion(estado)
    if pres is None:
        return False, Motivo("sin_presion_camara", "Sin lectura válida de presión de cámara")
    if pres > atm + rango:
        return False, _sobrepresion(pres, atm + rango)
    if pres < atm - rango:
        return False, _vacio(pres, atm - rango)
    return True, ""


def evaluar(estado, config, programas, profile=None, datos_vigentes=True,
            temp_max_ciclo=None) -> tuple[bool, str]:
    """(segura, motivo). `programas` (uno o una lista) deciden los sensores
    Principales: se toma el máximo y basta que falte uno para que no sea
    segura (temp_seguridad). None = temp_camara. El motivo es "" si es segura.

    `datos_vigentes` False (enlace caído o DI vencida) = NO segura: las
    lecturas guardadas son viejas (SAF-01 de T4). `temp_max_ciclo`: tras un
    ciclo, su `finalizacion.temp_max_apertura`; rige el menor con el global
    (SAF-04 de T4), igual que la apertura automática."""
    if not datos_vigentes:
        return False, Motivo("sin_datos_vigentes", "Sin conexión con el módulo E/S: datos no vigentes")
    faltan = [c for c in (CLAVE_ATM, CLAVE_RANGO, CLAVE_TEMP_MAX)
              if _numero(config.get(c)) is None]
    if faltan:
        return False, Motivo("falta_config", f"Falta configuración: {', '.join(faltan)}",
                             claves=", ".join(faltan))
    atm = _numero(config.get(CLAVE_ATM))
    rango = _numero(config.get(CLAVE_RANGO))
    temp_max = _numero(config.get(CLAVE_TEMP_MAX))
    del_ciclo = _numero(temp_max_ciclo)
    if del_ciclo is not None:
        temp_max = min(temp_max, del_ciclo)

    pres = _numero(estado.sensores_pres.get("pres_camara"))
    if pres is None:
        return False, Motivo("sin_presion_camara", "Sin lectura válida de presión de cámara")
    temp = _numero(temp_seguridad(estado, programas, profile))
    if temp is None:
        return False, Motivo("sin_temp_camara", "Sin lectura válida de temperatura de cámara")
    if pres > atm + rango:
        return False, _sobrepresion(pres, atm + rango)
    if pres < atm - rango:
        return False, _vacio(pres, atm - rango)
    if temp > temp_max:
        return False, _temp_alta(temp, temp_max)
    return True, ""


# ESS-02 (28-oct): motivos de cámara NO segura que son solo un sensor sin
# lectura (inventario ESS-01). La comunicación (sin_datos_vigentes), la
# configuración y el error de evaluación no son sensores: se siguen mostrando.
CODIGOS_SENSOR = frozenset({"sin_presion_camara", "sin_temp_camara"})


def motivos(estado, config, programas, profile=None, datos_vigentes=True,
            temp_max_ciclo=None) -> list:
    """ESS-02: TODOS los motivos por los que la cámara no es segura (evaluar()
    da solo el primero), en el mismo orden que evaluar(); [] si es segura.
    Solo para presentación: no la usa ningún interlock. Sin datos vigentes o
    sin configuración, solo ese motivo (lo demás no se puede juzgar)."""
    if not datos_vigentes:
        return [Motivo("sin_datos_vigentes", "Sin conexión con el módulo E/S: datos no vigentes")]
    faltan = [c for c in (CLAVE_ATM, CLAVE_RANGO, CLAVE_TEMP_MAX)
              if _numero(config.get(c)) is None]
    if faltan:
        return [Motivo("falta_config", f"Falta configuración: {', '.join(faltan)}",
                       claves=", ".join(faltan))]
    atm = _numero(config.get(CLAVE_ATM))
    rango = _numero(config.get(CLAVE_RANGO))
    temp_max = _numero(config.get(CLAVE_TEMP_MAX))
    del_ciclo = _numero(temp_max_ciclo)
    if del_ciclo is not None:
        temp_max = min(temp_max, del_ciclo)

    salida = []
    pres = _numero(estado.sensores_pres.get("pres_camara"))
    temp = _numero(temp_seguridad(estado, programas, profile))
    if pres is None:
        salida.append(Motivo("sin_presion_camara", "Sin lectura válida de presión de cámara"))
    if temp is None:
        salida.append(Motivo("sin_temp_camara", "Sin lectura válida de temperatura de cámara"))
    if pres is not None and pres > atm + rango:
        salida.append(_sobrepresion(pres, atm + rango))
    if pres is not None and pres < atm - rango:
        salida.append(_vacio(pres, atm - rango))
    if temp is not None and temp > temp_max:
        salida.append(_temp_alta(temp, temp_max))
    return salida


def solo_por_sensor(lista) -> bool:
    """ESS-02: True si la cámara no es segura SOLO por sensores sin lectura
    (lista no vacía y todos sus códigos en CODIGOS_SENSOR). Falla cerrada:
    lista vacía, motivo sin código o cualquier otro motivo → False."""
    try:
        codigos = [getattr(m, "codigo", None) for m in lista]
    except Exception:
        return False
    return bool(codigos) and all(c in CODIGOS_SENSOR for c in codigos)
