"""Lectura de llamadas activar/resolver sobre un AlarmManager MagicMock.
Cada activación se renderiza contra el catálogo real: si un módulo no pasa
los valores que pide la plantilla, la prueba falla aquí (spec §4, prueba de
plantillas), no en el equipo."""

from autoclave.state_machine.alarms.catalogo import CATALOGO


def activaciones(mock_manager) -> list[tuple[str, str | None, dict]]:
    resultado = []
    for llamada in mock_manager.activar.call_args_list:
        codigo = llamada.args[0]
        origen = llamada.args[1] if len(llamada.args) > 1 else llamada.kwargs.get("origen")
        valores = {k: v for k, v in llamada.kwargs.items() if k != "origen"}
        CATALOGO[codigo].renderizar(valores)
        resultado.append((codigo, origen, valores))
    return resultado


def codigos_activados(mock_manager) -> list[str]:
    return [codigo for codigo, _, _ in activaciones(mock_manager)]


def codigos_resueltos(mock_manager) -> list[str]:
    return [llamada.args[0] for llamada in mock_manager.resolver.call_args_list]


def ultima_activacion(mock_manager) -> tuple[str, str | None, dict]:
    return activaciones(mock_manager)[-1]


# --- Compatibilidad para pruebas escritas con la API vieja (tanda 2026-10-14,
# integración de alarmas-parte-a). Traduce (código, origen) al id anterior
# según docs/catalogo_alarmas.md §9; los ids conservados pasan tal cual.
_ID_VIEJO = {
    "SIS-01": "PARO_EMERGENCIA", "SUM-01": "FALLO_SUMINISTRO_ELECTRICO",
    "SUM-02": "SUMINISTRO_ELECTRICO", "SUM-03": "SUMINISTRO_AGUA_BOMBA",
    "SUM-04": "SUMINISTRO_AGUA_GENERADOR", "SUM-05": "SUMINISTRO_AIRE_COMPRIMIDO",
    "SUM-06": "SUMINISTRO_VAPOR", "PRE-01": "CHAQUETA_FRIA",
    "PRE-02": "CHAQUETA_SOBRECALENTADA", "PRE-03": "PRESION_CAMARA_BAJA",
    "PRE-04": "PRESION_CAMARA_ALTA", "PRE-05": "AGUA_RESIDUAL_CAMARA",
    "PRE-06": "TEMP_DRENAJE_ALTA", "SEN-02": "SENSOR_AUSENTE",
    "COM-01": "NO_HAY_CONEXION", "COM-02": "FALLO_CONEXION",
    "CIC-07": "TIMEOUT_APERTURA_AUTOMATICA", "CIC-08": "APERTURA_AUTOMATICA_DENEGADA",
}


def id_viejo(codigo: str, origen: str | None) -> str:
    from autoclave.state_machine.alarms.catalogo import NOMBRES_LEGIBLES
    if codigo == "PUE-01" and origen:
        return f"PUERTA_{origen.split()[-1]}_ABIERTA"
    if codigo in ("PUE-02", "PUE-03") and origen:
        sufijo = "ABIERTA" if codigo == "PUE-02" else "EMPAQUE"
        return f"FALLO_PUERTA_{origen.split()[-1]}_{sufijo}"
    if codigo == "SEN-01" and origen:
        sensor = next((k for k, v in NOMBRES_LEGIBLES.items() if v == origen), origen)
        return f"ERROR_AI_{sensor.upper()}"
    return _ID_VIEJO.get(codigo, codigo)


def ids_viejos_activados(mock_manager) -> list[str]:
    return [id_viejo(c, o) for c, o, _ in activaciones(mock_manager)]


def ids_viejos_resueltos(mock_manager) -> list[str]:
    res = []
    for llamada in mock_manager.resolver.call_args_list:
        origen = llamada.args[1] if len(llamada.args) > 1 else llamada.kwargs.get("origen")
        res.append(id_viejo(llamada.args[0], origen))
    return res


def ids_viejos_activos(manager) -> list[str]:
    """Para un AlarmManager real: ids viejos de las instancias ACTIVAS."""
    from autoclave.state_machine.alarms.instancia import EstadoInstancia
    return [id_viejo(i.codigo, i.origen) for i in manager.activas()
            if i.estado is EstadoInstancia.ACTIVA]
