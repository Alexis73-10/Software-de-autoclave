# state_machine/cycle_phases/debounce_acumulado.py
#
# F3 (tanda 16, P6 / D-14.6): debounce ACUMULADO en ventana deslizante.
#
# El debounce de "5 s continuos" (C-07.2, tanda 12) se reinicia con cada
# lectura dentro de rango: una señal que oscila alrededor del umbral (ruido de
# la PT100 frente a brecha_error_temperatura = 0,1 K) nunca confirma. Aquí se
# confirma cuando el tiempo con la condición activa suma `acumulado_s` dentro
# de los últimos `ventana_s` (defecto 5 s de 10 s, DECISIÓN SIN CONFIRMAR de
# D-14.6, a reajustar con el banco).
#
# Medición (reloj monotónico que pasa el llamador): cada tramo entre dos
# llamadas cuenta como "activo" si la condición estaba activa al EMPEZAR el
# tramo. Con la condición activa sin interrupción desde t0, lo acumulado es
# now - t0: confirma a los mismos 5 s que el debounce continuo anterior.
#
# `en_conteo`: la condición está activa en la última llamada (equivale al
# antiguo `clave in _falla_desde`). Lo usa ESTERILIZACION para no completar
# con una falla sin confirmar (V12, SAF-01). Un tiempo acumulado sin la
# condición activa NO bloquea la finalización: con ruido sostenido por debajo
# del umbral de confirmación la fase quedaría sin terminar ni fallar.

from collections import deque

ACUMULADO_DEFECTO_S = 5.0
VENTANA_DEFECTO_S = 10.0


class DebounceAcumulado:

    def __init__(self, acumulado_s: float = ACUMULADO_DEFECTO_S,
                 ventana_s: float = VENTANA_DEFECTO_S):
        if not (0 < acumulado_s <= ventana_s):
            raise ValueError("DebounceAcumulado: se exige 0 < acumulado_s <= ventana_s")
        self.acumulado_s = float(acumulado_s)
        self.ventana_s = float(ventana_s)
        self.reset()

    def reset(self) -> None:
        self._tramos: deque = deque()     # (inicio, fin) con la condición activa
        self._ultimo_t = None
        self._ultima_condicion = False

    @property
    def en_conteo(self) -> bool:
        return self._ultima_condicion

    def acumulado(self, now: float) -> float:
        """Segundos con la condición activa dentro de (now - ventana_s, now]."""
        desde = now - self.ventana_s
        total = 0.0
        for inicio, fin in self._tramos:
            total += max(0.0, min(fin, now) - max(inicio, desde))
        return total

    def actualizar(self, condicion: bool, now: float) -> bool:
        """Registra la condición en `now` y devuelve True si está confirmada
        (acumulado >= acumulado_s). Solo confirma con la condición activa en
        este instante."""
        if self._ultimo_t is not None and now > self._ultimo_t and self._ultima_condicion:
            if self._tramos and self._tramos[-1][1] == self._ultimo_t:
                self._tramos[-1] = (self._tramos[-1][0], now)
            else:
                self._tramos.append((self._ultimo_t, now))
        if self._ultimo_t is None or now >= self._ultimo_t:
            self._ultimo_t = now
        self._ultima_condicion = bool(condicion)
        desde = now - self.ventana_s
        while self._tramos and self._tramos[0][1] <= desde:
            self._tramos.popleft()
        return self._ultima_condicion and self.acumulado(now) >= self.acumulado_s
