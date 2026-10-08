# core/managers/validacion_config.py
#
# Validación de la configuración global al arrancar el backend. Si algo falla,
# el backend arranca bloqueado con la alarma CONFIGURACION_INVALIDA (decisión de
# Cristian del 2026-10-07, revisión de la etapa 1 de autenticación): sin
# máquina de estados, puertas, ciclo ni modo prueba hasta corregir la
# configuración y reiniciar.
#
# Por ahora solo cubre rango_presion_atm (1–10 kPa, decidido en
# planeacion_backend_parametros.md); la validación de todas las claves de esa
# spec (§4.2) se añadirá aquí.

RANGO_PRESION_ATM_KPA = (1.0, 10.0)


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def errores_config_arranque(config) -> list[str]:
    """Lista de errores legibles; vacía si la configuración es válida.
    `config` es un ConfigManager (o cualquier objeto con get(clave))."""
    errores = []
    minimo, maximo = RANGO_PRESION_ATM_KPA
    rango = config.get("rango_presion_atm")
    if rango is None:
        errores.append("Falta el parámetro rango_presion_atm")
    elif not _es_numero(rango) or rango != rango:   # rango != rango: NaN
        errores.append(f"rango_presion_atm no es numérico ({rango!r})")
    elif not minimo <= rango <= maximo:
        errores.append(
            f"rango_presion_atm fuera de rango: {rango} kPa (permitido {minimo:g}–{maximo:g} kPa)")
    return errores
