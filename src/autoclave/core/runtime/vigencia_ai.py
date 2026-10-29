# core/runtime/vigencia_ai.py
#
# S9 (tanda 9), revisión ★ pasada 2 (R2-A1 / R2-M1): vigencia de la trama AI
# (presiones y temperaturas) para el protocolo de fallo y las fases.
#
# Si el módulo E/S sigue mandando DI pero deja de mandar AI, Units conserva la
# última presión y temperatura: congeladas, parecen vigentes. El ControlLoop
# publica en el estado un proveedor `estado.lectura_ai` -> (trama AI vigente,
# número de trama); quien decide válvulas con la presión lo consulta aquí.
#
# Sin proveedor (dobles de prueba, estado sin ControlLoop): (True, None), el
# comportamiento anterior. Proveedor que falla o responde algo que no es un
# par: (False, None), falla cerrada. Se lee del __dict__ del estado para que
# un MagicMock no invente un proveedor.


def proveedor_de(estado):
    try:
        return vars(estado).get("lectura_ai")
    except TypeError:
        return None


def leer(estado, proveedor=None) -> tuple[bool, int | None]:
    """(trama AI vigente, su número o None)."""
    f = proveedor if proveedor is not None else proveedor_de(estado)
    if f is None:
        return True, None
    try:
        vigente, seq = f()
    except Exception:
        return False, None
    if isinstance(seq, bool) or not isinstance(seq, int):
        seq = None
    return vigente is True, seq
