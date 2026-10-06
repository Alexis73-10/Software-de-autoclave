# ui_qml/domain/navegador_periodo.py
#
# Periodo de calendario elegido en el Historial y en Reportes del Menú Principal:
# Diario / Semanal / Mensual (utils/periodos.py), recorrido con flechas sin pasar
# del periodo actual, con su rótulo ("Octubre 2026").

from datetime import date

from autoclave.ui_qml.domain import resumen_sistema as dominio
from autoclave.utils import periodos as calendario


class NavegadorPeriodo:
    def __init__(self, hoy=date.today):
        self._hoy = hoy                 # reloj de pared: solo para elegir el periodo
        self.periodo = ""               # "" = aún no se eligió ninguno
        self.fecha: date | None = None

    def ir_al_actual(self, periodo: str) -> None:
        self.periodo = periodo
        self.fecha = self._hoy()

    def mover(self, pasos: int) -> bool:
        """`pasos` periodos antes (negativo) o después, sin pasar del actual;
        False si no se movió."""
        if not self.periodo:
            return False
        destino = calendario.desplazar(self.periodo, self.fecha, pasos, self._hoy())
        if calendario.rango(self.periodo, destino) == calendario.rango(self.periodo, self.fecha):
            return False
        self.fecha = destino
        return True

    @property
    def rotulo(self) -> str:
        return dominio.rotulo_periodo(self.periodo, self.fecha) if self.periodo else ""

    @property
    def es_actual(self) -> bool:
        return not self.periodo or calendario.es_actual(self.periodo, self.fecha, self._hoy())
