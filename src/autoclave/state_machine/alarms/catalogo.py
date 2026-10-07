# Catálogo central de alarmas (spec 2026-10-06-sistema-alarmas-parte-a §4).
# Nivel y bloqueo son decisiones de seguridad: viven aquí, bajo control de
# versiones, no en configuración editable.

import string
from dataclasses import dataclass
from enum import Enum


class Nivel(Enum):
    INFORMATIVO = 1
    AVISO = 2
    ALARMA = 3
    FALLO_CRITICO = 4

    @property
    def requiere_reconocimiento(self) -> bool:
        return self in (Nivel.ALARMA, Nivel.FALLO_CRITICO)

    @property
    def nombre_compat(self) -> str:
        """Nombre de nivel que esperan los consumidores viejos de /status."""
        return _NOMBRE_COMPAT[self]


_NOMBRE_COMPAT = {
    Nivel.INFORMATIVO: "INFORMATIVO",
    Nivel.AVISO: "ALERTA",
    Nivel.ALARMA: "FALLA",
    Nivel.FALLO_CRITICO: "EMERGENCIA",
}


class Despeje(Enum):
    AUTOMATICO = "AUTOMATICO"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class DefinicionAlarma:
    codigo: str
    nivel: Nivel
    titulo: str
    descripcion: str
    accion: str
    bloquea_inicio: bool
    despeje: Despeje

    def campos(self) -> set[str]:
        return {campo for _, campo, _, _ in string.Formatter().parse(self.descripcion) if campo}

    def renderizar(self, valores: dict) -> str:
        return self.descripcion.format(**valores)


SIS_01, SIS_02 = "SIS-01", "SIS-02"
SUM_01, SUM_02, SUM_03, SUM_04, SUM_05, SUM_06 = (
    "SUM-01", "SUM-02", "SUM-03", "SUM-04", "SUM-05", "SUM-06")
PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06 = (
    "PRE-01", "PRE-02", "PRE-03", "PRE-04", "PRE-05", "PRE-06")
PUE_01, PUE_02, PUE_03, PUE_04, PUE_05 = "PUE-01", "PUE-02", "PUE-03", "PUE-04", "PUE-05"
SEN_01, SEN_02 = "SEN-01", "SEN-02"
CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08 = (
    "CIC-01", "CIC-02", "CIC-03", "CIC-04", "CIC-05", "CIC-06", "CIC-07", "CIC-08")
COM_01, COM_02 = "COM-01", "COM-02"

_A, _M = Despeje.AUTOMATICO, Despeje.MANUAL
_AV, _AL, _FC = Nivel.AVISO, Nivel.ALARMA, Nivel.FALLO_CRITICO


def _d(codigo, nivel, bloquea, despeje, titulo, descripcion, accion):
    return DefinicionAlarma(codigo, nivel, titulo, descripcion, accion, bloquea, despeje)


DEFINICIONES: tuple[DefinicionAlarma, ...] = (
    _d(SIS_01, _FC, True, _A, "Paro de emergencia activado",
       "Se presionó el paro de emergencia en estado {estado}. Todas las salidas están apagadas.",
       "Verifique que no haya riesgo y libere el botón de paro."),
    _d(SIS_02, _AV, False, _M, "Historial de alarmas no disponible",
       "No se pudo guardar el historial de alarmas: {error}. Las alarmas siguen "
       "funcionando, pero no quedan registradas.",
       "Avise a soporte técnico."),
    _d(SUM_01, _FC, True, _M, "Corte eléctrico durante el ciclo",
       "Se perdió el suministro eléctrico en la fase {fase}. El ciclo se abortó.",
       "Verifique la alimentación del equipo antes de reiniciar."),
    _d(SUM_02, _AV, True, _A, "Sin suministro eléctrico",
       "La señal de suministro eléctrico está inactiva.",
       "Verifique la alimentación del equipo."),
    _d(SUM_03, _AV, True, _A, "Sin agua para la bomba de vacío",
       "La señal de suministro de agua de la bomba está inactiva.",
       "Abra la válvula de agua de la bomba y verifique la presión de la red."),
    _d(SUM_04, _AV, True, _A, "Sin agua para el generador",
       "La señal de suministro de agua del generador está inactiva.",
       "Abra la válvula de agua del generador y verifique la presión de la red."),
    _d(SUM_05, _AV, True, _A, "Sin aire comprimido",
       "La señal de suministro de aire comprimido está inactiva.",
       "Verifique el compresor y la válvula de aire."),
    _d(SUM_06, _AV, False, _A, "Sin suministro de vapor",
       "No hay suministro de vapor en estado {estado}. La chaqueta queda en espera "
       "hasta que regrese.",
       "Verifique el generador y la válvula de vapor."),
    _d(PRE_01, _AV, True, _A, "Presión de chaqueta baja",
       "La chaqueta está en {pres:.0f} kPa, por debajo del mínimo de {minimo:.0f} kPa "
       "(objetivo {objetivo:.0f} ± {rango:.0f}).",
       "Espere a que la chaqueta alcance presión. Si no sube, verifique el suministro de vapor."),
    _d(PRE_02, _AV, True, _A, "Presión de chaqueta alta",
       "La chaqueta está en {pres:.0f} kPa, por encima del máximo de {maximo:.0f} kPa "
       "(objetivo {objetivo:.0f} ± {rango:.0f}).",
       "Verifique la válvula de vapor de chaqueta."),
    _d(PRE_03, _AV, True, _A, "Presión de cámara baja",
       "La cámara está en {pres:.0f} kPa, por debajo de {minimo:.0f} kPa.",
       "Espere a que la cámara se iguale con la atmósfera."),
    _d(PRE_04, _AV, True, _A, "Presión de cámara alta",
       "La cámara está en {pres:.0f} kPa, por encima de {maximo:.0f} kPa.",
       "No abra la puerta. Espere a que la cámara descomprima."),
    _d(PRE_05, _AV, True, _A, "Agua residual en la cámara",
       "El sensor de nivel detecta agua acumulada en la cámara. Se está drenando.",
       "Si no desaparece, verifique el drenaje de la cámara y la trampa de vapor."),
    _d(PRE_06, _AV, True, _A, "Temperatura de drenaje alta",
       "El drenaje está en {temp:.1f} °C, por encima del máximo de {maximo:.1f} °C. "
       "Se activó el enfriamiento.",
       "Verifique el agua del intercambiador."),
    _d(PUE_01, _AV, True, _A, "Puerta abierta",
       "{puerta} está abierta. El ciclo no puede iniciar.",
       "Cierre la puerta."),
    _d(PUE_02, _AL, True, _M, "Puerta abierta durante el ciclo",
       "{puerta} dejó de detectarse cerrada en la fase {fase}. El ciclo se abortó.",
       "Verifique el sensor de puerta cerrada y el cierre mecánico."),
    _d(PUE_03, _AL, True, _M, "Presión de empaque insuficiente",
       "El empaque de {puerta} bajó a {pres:.0f} kPa (mínimo {minimo:.0f} kPa) en la "
       "fase {fase}. El ciclo se abortó.",
       "Verifique el aire comprimido y el estado del empaque."),
    _d(PUE_04, _AV, False, _A, "Apertura en modo seguro",
       "{puerta} se está abriendo sin bomba de vacío por falla eléctrica.",
       "Ninguna, la apertura continúa."),
    _d(PUE_05, _AV, False, _A, "Cierre en modo seguro",
       "{puerta} se está cerrando sin bomba de vacío por falla eléctrica.",
       "Ninguna, el cierre continúa."),
    _d(SEN_01, _AV, True, _A, "Lectura inválida de sensor",
       "{sensor} entrega una lectura inválida ({valor}).",
       "Verifique la conexión del sensor."),
    _d(SEN_02, _FC, True, _M, "Sensor crítico sin lectura",
       "Sin lectura de: {sensores}, en la fase {fase}. El ciclo se abortó.",
       "Verifique la conexión de los sensores antes de reiniciar."),
    _d(CIC_01, _AL, True, _M, "Fallo en precalentamiento", "{motivo}",
       "Revise el suministro de vapor de la chaqueta."),
    _d(CIC_02, _AL, True, _M, "Fallo en prevacío", "{motivo}",
       "Revise la bomba de vacío y su agua de sello."),
    _d(CIC_03, _AL, True, _M, "Fallo en calentamiento", "{motivo}",
       "Revise el suministro de vapor y la presión del generador."),
    _d(CIC_04, _AL, True, _M, "Fallo en esterilización", "{motivo}",
       "La carga NO está estéril. Revise el suministro de vapor y repita el ciclo."),
    _d(CIC_05, _AL, True, _M, "Fallo en descompresión", "{motivo}",
       "No abra la puerta hasta confirmar presión atmosférica. Revise las válvulas de escape."),
    _d(CIC_06, _AL, True, _M, "Fallo en secado", "{motivo}",
       "Revise la bomba de vacío. La carga puede salir húmeda."),
    _d(CIC_07, _AV, False, _A, "Enfriamiento demorado",
       "La cámara sigue en {temp:.1f} °C (máximo para abrir {maximo:.1f} °C) tras "
       "{minutos:.0f} min.",
       "Espere. La puerta se abrirá sola al enfriar."),
    _d(CIC_08, _AV, False, _A, "Apertura automática denegada",
       "No se pudo abrir {puerta}: {motivo}.",
       "Verifique el bloqueo mecánico de la puerta."),
    _d(COM_01, _AL, True, _A, "Sin comunicación con la tarjeta",
       "No llegan datos válidos de la tarjeta de control.",
       "Verifique el cable USB y la alimentación de la tarjeta."),
    _d(COM_02, _FC, True, _M, "Comunicación perdida durante el ciclo",
       "Se perdió la comunicación con la tarjeta por más de {segundos:.0f} s en la fase "
       "{fase}. El ciclo se abortó.",
       "Verifique el cable USB y la alimentación de la tarjeta antes de reiniciar."),
)

CATALOGO: dict[str, DefinicionAlarma] = {d.codigo: d for d in DEFINICIONES}

NOMBRES_LEGIBLES: dict[str, str] = {
    # Sensores
    "temp_camara": "Temperatura de cámara",
    "temp_2_camara": "Temperatura de cámara 2",
    "temp_ref": "Temperatura de referencia",
    "temp_chaqueta": "Temperatura de chaqueta",
    "temp_drenaje_cam": "Temperatura de drenaje de cámara",
    "temp_drenaje": "Temperatura de drenaje",
    "pres_camara": "Presión de cámara",
    "pres_chaqueta": "Presión de chaqueta",
    "pres_empaque_1": "Presión de empaque puerta 1",
    "pres_empaque_2": "Presión de empaque puerta 2",
    # Fases (CicloState / BaseFase.name)
    "PRECALENTAMIENTO": "Precalentamiento",
    "PRE_VACIO": "Prevacío",
    "CALENTAMIENTO": "Calentamiento",
    "ESTERILIZACION": "Esterilización",
    "DESCOMPRESION": "Descompresión",
    "SECADO": "Secado",
}


def nombre_legible(clave: str) -> str:
    return NOMBRES_LEGIBLES.get(clave, clave)
