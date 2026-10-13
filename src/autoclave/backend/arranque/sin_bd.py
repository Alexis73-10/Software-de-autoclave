# autoclave/backend/arranque/sin_bd.py
#
# PROVISIONAL hasta el modo sin base de datos (§7 de planeacion_arranque_y_modo_sin_bd.md).
# Si la etapa "abriendo_base_datos" se degrada, context.db y
# context.calibration_audit pasan a ser un BdNoDisponible: cualquier llamada
# lanza BdNoDisponibleError, que server.py traduce a 503 "sin_base_de_datos".
# El inicio de ciclo queda bloqueado aparte (alarma OPERANDO_SIN_BD y rechazo
# en /cycle/start): un ciclo sin registro rompe la trazabilidad.


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
