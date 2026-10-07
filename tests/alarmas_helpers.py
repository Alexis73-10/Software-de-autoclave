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
