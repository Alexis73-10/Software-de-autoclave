# core/runtime/mantenimiento.py
#
# Próximo mantenimiento (M1, tanda 3). Lógica pura, sin E/S:
#
# - Primer mantenimiento = fecha de instalación + `intervalo_dias`. Tras
#   registrar un mantenimiento realizado, la base pasa a ser esa fecha (y los
#   ciclos de ese momento).
# - Con `intervalo_ciclos` > 0 el próximo vence por lo que ocurra primero
#   (fecha o ciclos). 0 = no aplica ese criterio.
# - La fecha es de CALENDARIO (fecha de pared), no un temporizador de proceso.
#   Si el reloj del sistema es anterior a la fecha de instalación o al último
#   mantenimiento registrado (manipulado o sin batería), no se afirma nada:
#   estado SIN_DATO y la UI muestra "—" (nunca un valor falso).
# - Vencido es solo informativo: genera un aviso no bloqueante y NUNCA impide
#   un ciclo.
#
# VALORES POR DEFECTO (aprobados por Cristian el 2026-10-20): 365 días y 1000
# ciclos, contados desde la instalación (o desde el último mantenimiento
# registrado); vence por lo que ocurra primero.

from dataclasses import dataclass
from datetime import date, datetime, timedelta

# Tipos de mantenimiento registrables (única definición: la usan el servicio y
# el controlador QML, MNT-03). Solo `preventivo` reinicia el contador (MNT-01,
# D-2). `calibracion` salió de los tipos (MNT-02, D-5) y `otro` también (P-3,
# D8-3.25, tanda 8: todo lo que no es preventivo es correctivo). Las filas
# viejas de la tabla (solo anexar) se muestran como histórico y nunca se
# ofrecen (MNT-05).
TIPOS = ("preventivo", "correctivo")
# Tipos que solo pueden aparecer en filas viejas: se rotulan "(histórico)" con
# la clave i18n opciones.mant_tipo_<tipo> y nunca se ofrecen (MNT-05).
TIPOS_HISTORICOS = ("calibracion", "otro")

INTERVALO_DIAS_DEFECTO = 365
INTERVALO_CICLOS_DEFECTO = 1000
# valores provisionales de la tanda 3, migrados a los definitivos (B3, tanda 4)
INTERVALO_DIAS_PROVISIONAL = 180
INTERVALO_CICLOS_PROVISIONAL = 0
INTERVALO_DIAS_MAX = 3650
INTERVALO_CICLOS_MAX = 1_000_000

# estados del cálculo
OK = "ok"
PROXIMO = "proximo"        # faltan 14 días o menos (o 5% de los ciclos): aviso en la UI
VENCIDO = "vencido"
SIN_DATO = "sin_dato"      # sin instalación, o reloj anterior a la base
NO_APLICA = "no_aplica"    # ambos intervalos en 0

DIAS_AVISO = 14


def validar_intervalos(intervalo_dias, intervalo_ciclos) -> list[str]:
    """Errores de validación (lista vacía = válidos). Enteros, 0 = no aplica."""
    errores = []
    for nombre, valor, maximo in (("intervalo_dias", intervalo_dias, INTERVALO_DIAS_MAX),
                                  ("intervalo_ciclos", intervalo_ciclos, INTERVALO_CICLOS_MAX)):
        if isinstance(valor, bool) or not isinstance(valor, int):
            errores.append(f"{nombre}: debe ser un entero")
        elif not 0 <= valor <= maximo:
            errores.append(f"{nombre}: fuera de rango (0 a {maximo})")
    return errores


@dataclass(frozen=True)
class EstadoMantenimiento:
    estado: str
    proximo_fecha: date | None = None
    dias_restantes: int | None = None
    ciclos_restantes: int | None = None
    ultimo_fecha: date | None = None
    ultimo_tipo: str = ""
    vencido_por: str = ""        # "fecha" | "ciclos" | ""

    @property
    def vencido(self) -> bool:
        return self.estado == VENCIDO

    def a_dict(self) -> dict:
        return {
            "estado": self.estado,
            "vencido": self.vencido,
            "proximo_fecha": self.proximo_fecha.isoformat() if self.proximo_fecha else None,
            "dias_restantes": self.dias_restantes,
            "ciclos_restantes": self.ciclos_restantes,
            "ultimo_fecha": self.ultimo_fecha.isoformat() if self.ultimo_fecha else None,
            "ultimo_tipo": self.ultimo_tipo,
            "vencido_por": self.vencido_por,
        }


def _a_fecha(valor) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.fromisoformat(str(valor)).date()
    except ValueError:
        return None


def calcular(instalado_en, intervalo_dias: int, intervalo_ciclos: int, ultimo: dict | None,
             ciclos_actuales: int | None, hoy: date,
             ciclos_instalacion: int = 0) -> EstadoMantenimiento:
    """`ultimo`: {"fecha", "ciclos", "tipo"} del último mantenimiento registrado
    o None. `ciclos_actuales`: contador persistente de ciclos (None = se
    desconoce). `ciclos_instalacion`: valor del contador al instalar (0 en un
    equipo nuevo); los ciclos cuentan desde ahí hasta el primer mantenimiento."""
    if not intervalo_dias and not intervalo_ciclos:
        return EstadoMantenimiento(NO_APLICA)
    base_fecha = _a_fecha(ultimo.get("fecha")) if ultimo else None
    instalado = _a_fecha(instalado_en)
    ultimo_fecha = base_fecha
    if base_fecha is None:
        base_fecha = instalado
    if base_fecha is None:
        return EstadoMantenimiento(SIN_DATO)
    # reloj anterior a la base (instalación o último mantenimiento): no se afirma nada
    if hoy < base_fecha or (instalado is not None and hoy < instalado):
        return EstadoMantenimiento(SIN_DATO, ultimo_fecha=ultimo_fecha,
                                   ultimo_tipo=(ultimo or {}).get("tipo", ""))
    ciclos_base = int(ultimo.get("ciclos") or 0) if ultimo else max(0, int(ciclos_instalacion or 0))

    proximo, dias = None, None
    if intervalo_dias:
        proximo = base_fecha + timedelta(days=intervalo_dias)
        dias = (proximo - hoy).days
    restantes = None
    if intervalo_ciclos and ciclos_actuales is not None:
        restantes = intervalo_ciclos - max(0, int(ciclos_actuales) - ciclos_base)

    por_fecha = dias is not None and dias < 0
    por_ciclos = restantes is not None and restantes <= 0
    if por_fecha or por_ciclos:
        estado, por = VENCIDO, "fecha" if por_fecha else "ciclos"
    elif (dias is not None and dias <= DIAS_AVISO) or (
            restantes is not None and intervalo_ciclos and restantes <= intervalo_ciclos * 0.05):
        estado, por = PROXIMO, ""
    else:
        estado, por = OK, ""
    return EstadoMantenimiento(estado, proximo, dias, restantes, ultimo_fecha,
                               (ultimo or {}).get("tipo", ""), por)
