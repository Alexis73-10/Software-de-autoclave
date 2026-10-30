# autoclave/backend/arranque/sin_bd.py
#
# Modo sin base de datos (§7 de planeacion_arranque_y_modo_sin_bd.md; T8).
# Si la etapa "abriendo_base_datos" se degrada, context.db y
# context.calibration_audit pasan a ser un BdNoDisponible: cualquier llamada
# lanza BdNoDisponibleError, que server.py traduce a 503 "sin_base_de_datos".
# Los ciclos siguen (D-03, alarma OPERANDO_SIN_BD no bloqueante): /cycle/start
# exige confirmar_sin_registro en cada ciclo y el registro va al respaldo JSONL
# y al ticket.


class BdNoDisponibleError(RuntimeError):
    pass


class BdNoDisponible:
    def __bool__(self) -> bool:
        return False

    def __getattr__(self, nombre: str):
        if nombre.startswith("__"):
            raise AttributeError(nombre)

        def _no_disponible(*_args, **_kwargs):
            raise BdNoDisponibleError(f"Base de datos no disponible ({nombre})")

        return _no_disponible

    def __repr__(self) -> str:
        return "BdNoDisponible()"
