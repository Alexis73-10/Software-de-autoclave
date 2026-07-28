"""
autoclave.hal.measures.calibration_tools
-----------------------------------------
Funciones puras (sin I/O) para el modo de calibracion de 2 puntos: invierte
la calibracion 'user' vigente de un sensor (lineal o polinomio) en los
valores "mostrados" dados por el tecnico, y ajusta una recta nueva contra
los valores "reales" (equipo patron). Usa el mismo orden de coeficientes
que _user_calibrate en converters.py (Horner, orden descendente).
"""


def invert_user_calibration(
    shown_value: float,
    gain: float = 1.0,
    offset: float = 0.0,
    poly: list[float] | None = None,
) -> float:
    """Invierte la calibracion 'user' vigente (lineal u poly) para obtener
    el valor de fabrica (salida de _factory_calibrate) que produce
    `shown_value` como lectura final."""
    if poly and len(poly) >= 2:
        return _invert_poly(poly, shown_value)
    if gain == 0:
        raise ValueError("La calibracion actual tiene gain=0; no se puede invertir")
    return (shown_value - offset) / gain


def _poly_eval(coeffs: list[float], x: float) -> float:
    result = 0.0
    for c in coeffs:
        result = result * x + c
    return result


def _poly_derivative_coeffs(poly: list[float]) -> list[float]:
    """poly = [c0..cn] en orden descendente (c0*x^n + ... + cn), igual que
    _user_calibrate. Retorna los coeficientes de la derivada, mismo orden."""
    n = len(poly) - 1
    return [c * (n - i) for i, c in enumerate(poly[:-1])]


def _invert_poly(poly: list[float], target: float, max_iter: int = 100) -> float:
    """Newton-Raphson: encuentra x tal que _poly_eval(poly, x) == target.
    x0 = target (el polinomio de calibracion es una correccion pequena
    cerca de la identidad, por lo que target es una semilla razonable)."""
    deriv = _poly_derivative_coeffs(poly)
    x = target
    for _ in range(max_iter):
        fx = _poly_eval(poly, x) - target
        fpx = _poly_eval(deriv, x)
        if fpx == 0:
            raise ValueError("Derivada cero durante la inversion del polinomio")
        x_new = x - fx / fpx
        if abs(x_new - x) < 1e-9:
            return x_new
        x = x_new
    raise ValueError("La inversion del polinomio no convergio")


def fit_two_point(fv_low: float, real_low: float, fv_high: float, real_high: float) -> tuple[float, float]:
    """Ajusta gain/offset tales que gain*fv+offset reproduce real_low en
    fv_low y real_high en fv_high."""
    if fv_high == fv_low:
        raise ValueError("Los dos puntos de fabrica coinciden; no se puede calcular una recta")
    gain = (real_high - real_low) / (fv_high - fv_low)
    offset = real_low - gain * fv_low
    return gain, offset
