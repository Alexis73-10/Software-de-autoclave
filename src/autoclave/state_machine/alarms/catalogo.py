# Catálogo central de alarmas (spec 2026-10-06-sistema-alarmas-parte-a §4).
# Nivel y bloqueo son decisiones de seguridad: viven aquí, bajo control de
# versiones, no en configuración editable.

import re
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


SIS_01, SIS_02, SIS_03, SIS_04, SIS_05 = "SIS-01", "SIS-02", "SIS-03", "SIS-04", "SIS-05"
SUM_01, SUM_02, SUM_03, SUM_04, SUM_05, SUM_06 = (
    "SUM-01", "SUM-02", "SUM-03", "SUM-04", "SUM-05", "SUM-06")
PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06 = (
    "PRE-01", "PRE-02", "PRE-03", "PRE-04", "PRE-05", "PRE-06")
PUE_01, PUE_02, PUE_03, PUE_04, PUE_05 = "PUE-01", "PUE-02", "PUE-03", "PUE-04", "PUE-05"
SEN_01, SEN_02, SEN_03 = "SEN-01", "SEN-02", "SEN-03"
# S1 (tanda 8, D8-1): transductor de presión sin lectura. En ciclo, FALLO
# con código propio; fuera de ciclo, bloquea el inicio ("llame a servicio").
SEN_04, SEN_05, SEN_06, SEN_07 = "SEN-04", "SEN-05", "SEN-06", "SEN-07"
# Revisión ★ de S1 (SAF-01): empaque sin lectura en ciclo (puertas con empaque)
SEN_08 = "SEN-08"
# R8 (tanda 8, D8-5.12): reasignación de E/S sin verificar por el ingeniero
SEN_09 = "SEN-09"
# S9 (tanda 9, D9-1.6): fuera de ciclo, puerta abierta con la presión de cámara
# fuera de la banda atmosférica (calibración, referencia atmosférica o sensor
# de puerta)
SEN_10 = "SEN-10"
# E12 (tanda 12, C-13.7b): Referencia sin lectura en ciclo; no bloqueante, el
# ciclo sigue con las sondas que leen y queda NO CONFORME
SEN_11 = "SEN-11"
CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08 = (
    "CIC-01", "CIC-02", "CIC-03", "CIC-04", "CIC-05", "CIC-06", "CIC-07", "CIC-08")
CIC_09, CIC_10 = "CIC-09", "CIC-10"
# D8-2.8 (tanda 8): pausas por falta de datos sobre el tope en esterilización
CIC_11 = "CIC-11"
# E12 (tanda 12): fallos propios de ESTERILIZACION, mismo mecanismo que CIC-11
# C-03: saturación (solo sólidos); C-13.4: Referencia sin retorno a la banda
CIC_12, CIC_13, CIC_14 = "CIC-12", "CIC-13", "CIC-14"
# F2 (tanda 16): VCH §4.5, fallos del aislamiento de cámara por sobrepresión
# (modo chaqueta, CALENTAMIENTO y ESTERILIZACION): sostenido y recurrente
CIC_15, CIC_16 = "CIC-15", "CIC-16"
# P5 (D-14.5): excursión confirmada después del tope de reinicios de la exposición
CIC_17 = "CIC-17"
# D-CHQ / VCH-CHQ (§4.6): chaqueta en el corte de control en modo chaqueta;
# aviso no bloqueante, se despeja solo
CIC_18 = "CIC-18"
# FC-08 (tanda 21): Referencia sin lectura con carga líquida; FALLO bloqueante
# como CIC-12/13 (en carga sólida sigue SEN-11, aviso no bloqueante)
CIC_19 = "CIC-19"
# M1 (tanda 3): aviso no bloqueante de mantenimiento vencido (id descriptivo
# como OPERANDO_SIN_BD; nunca impide un ciclo)
MANTENIMIENTO_VENCIDO = SIS_04
# B5 (tanda 4): aviso no bloqueante de impresora desconectada al arrancar
IMPRESORA_DESCONECTADA = SIS_05
# J12 (tanda 12, C-04.4): aviso no bloqueante de migración correctiva de un
# programa al cargarlo (p. ej. presion_add_* > 30 kPa bajado a 9)
SIS_06 = "SIS-06"
MIGRACION_CORRECTIVA = SIS_06
# LIC-02 (licencia L0): aviso no bloqueante en un equipo ya instalado cuya
# cuenta Admin o Ingeniero conserva la contraseña de fábrica (solo lo ven
# técnico e ingeniero, ROLES_VISIBLES)
SIS_07 = "SIS-07"
CONTRASENA_SEMILLA = SIS_07
COM_01, COM_02, COM_03 = "COM-01", "COM-02", "COM-03"
# D8-2.11 (tanda 8): ALL_OFF sin confirmar al salir del modo prueba
COM_04 = "COM-04"
# Módulo E/S (E6): los ids se conservan como códigos (no se renombran).
TARJETA_SIN_TRAMA_VALIDA = "TARJETA_SIN_TRAMA_VALIDA"
TARJETA_VERSION_INCOMPATIBLE = "TARJETA_VERSION_INCOMPATIBLE"
TARJETA_SIN_ACK = "TARJETA_SIN_ACK"
TARJETA_ALL_OFF_SIN_CONFIRMAR = "TARJETA_ALL_OFF_SIN_CONFIRMAR"
TARJETA_SALIDAS_NO_APAGADAS = "TARJETA_SALIDAS_NO_APAGADAS"
TARJETA_EXPANSOR_FUERA_DE_LINEA = "TARJETA_EXPANSOR_FUERA_DE_LINEA"
TARJETA_WATCHDOG = "TARJETA_WATCHDOG"
TARJETA_REINICIO = "TARJETA_REINICIO"
DISCREPANCIA_SALIDAS = "DISCREPANCIA_SALIDAS"
# Tanda 19 (MOD-12): módulos M31-U por Modbus TCP; misma clase que
# TARJETA_ALL_OFF_SIN_CONFIRMAR (bloqueante fuera de ciclo; en ciclo, COM-03).
TARJETA_CONFIG_SEGURIDAD = "TARJETA_CONFIG_SEGURIDAD"
TARJETA_MODULOS_ORDEN = "TARJETA_MODULOS_ORDEN"
# Arranque (secuencia por etapas): ids conservados.
OPERANDO_SIN_BD = "OPERANDO_SIN_BD"
CONFIGURACION_INVALIDA = "CONFIGURACION_INVALIDA"
CODIGOS_TARJETA = (
    TARJETA_SIN_TRAMA_VALIDA, TARJETA_VERSION_INCOMPATIBLE, TARJETA_SIN_ACK,
    TARJETA_ALL_OFF_SIN_CONFIRMAR, TARJETA_SALIDAS_NO_APAGADAS,
    TARJETA_EXPANSOR_FUERA_DE_LINEA, TARJETA_WATCHDOG, TARJETA_REINICIO,
    DISCREPANCIA_SALIDAS, TARJETA_CONFIG_SEGURIDAD, TARJETA_MODULOS_ORDEN,
)
# Ids anteriores al formato ÁREA-NN que se conservan sin renombrar
# (instrucción de la tanda 2026-10-14, regla 8).
CODIGOS_CONSERVADOS = CODIGOS_TARJETA + (OPERANDO_SIN_BD, CONFIGURACION_INVALIDA)

# MES-04 (tanda 23): el código guardado no cambia (historial, catálogo,
# trazabilidad); donde se muestra, un TARJETA_<x> se ve como MODULO_ES_<x>.
_PREFIJO_GUARDADO = "TARJETA_"
_PREFIJO_VISIBLE = "MODULO_ES_"


def codigo_visible(codigo):
    """Código de alarma tal como se muestra (pantalla, ticket, PDF, correo,
    exportaciones). Solo cambia el prefijo TARJETA_; cualquier otro valor
    (incluido None o un no-texto) se devuelve sin tocar."""
    if isinstance(codigo, str) and codigo.startswith(_PREFIJO_GUARDADO):
        return _PREFIJO_VISIBLE + codigo[len(_PREFIJO_GUARDADO):]
    return codigo


_RE_CODIGO_GUARDADO = re.compile(r"(?<![A-Za-z0-9_])" + _PREFIJO_GUARDADO + r"(?=[A-Z0-9])")


def texto_con_codigos_visibles(texto):
    """MES-04: `texto` libre (motivo de fallo guardado, línea del ticket) con
    cada código TARJETA_<x> escrito como MODULO_ES_<x>. Solo para mostrar: el
    texto guardado no se toca. Un no-texto se devuelve sin tocar."""
    if isinstance(texto, str) and _PREFIJO_GUARDADO in texto:
        return _RE_CODIGO_GUARDADO.sub(_PREFIJO_VISIBLE, texto)
    return texto

_A, _M = Despeje.AUTOMATICO, Despeje.MANUAL

# LIC-02: alarmas que solo ven ciertos roles en la bandeja y la campana (la
# pantalla filtra por el rol de la sesión; sin sesión no se muestran). Las
# demás las ve todo el mundo.
ROLES_VISIBLES: dict[str, frozenset[str]] = {
    SIS_07: frozenset({"tecnico", "ingeniero"}),
}
_AV, _AL, _FC = Nivel.AVISO, Nivel.ALARMA, Nivel.FALLO_CRITICO


def _d(codigo, nivel, bloquea, despeje, titulo, descripcion, accion):
    return DefinicionAlarma(codigo, nivel, titulo, descripcion, accion, bloquea, despeje)


DEFINICIONES: tuple[DefinicionAlarma, ...] = (
    _d(SIS_01, _FC, True, _A, "Paro de emergencia activado",
       # E1 (PF-21): paro NC. U4 (tanda 2): solo con la entrada en 0 leída de
       # el módulo E/S; sin datos, COM-01 o TARJETA_SIN_TRAMA_VALIDA.
       "Paro de emergencia activo en estado {estado}. La entrada del paro está "
       "en 0. Si el botón no está pulsado, revisar que el cableado sea contacto "
       "normalmente cerrado (NC).",
       "Verifique que no haya riesgo y libere el botón de paro."),
    _d(SIS_02, _AV, False, _M, "Historial de alarmas no disponible",
       "No se pudo guardar el historial de alarmas: {error}. Las alarmas siguen "
       "funcionando, pero no quedan registradas.",
       "Avise a soporte técnico."),
    # T8 (SAF-01): el respaldo JSONL del ciclo no se pudo escribir. Sin base
    # de datos es el único registro electrónico del ciclo.
    _d(SIS_03, _AV, False, _M, "Respaldo del ciclo no disponible",
       "No se pudo escribir el respaldo del ciclo: {error}. Sin base de datos, el "
       "ciclo queda registrado solo en el ticket.",
       "Avise a servicio técnico: revise el espacio y los permisos del disco."),
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
    # D9-2 (tanda 9): ALARMA (antes AVISO), mismo bloqueo y despeje
    _d(SEN_01, _AL, True, _A, "Lectura inválida de sensor",
       "{sensor} entrega una lectura inválida ({valor}).",
       "Verifique la conexión del sensor."),
    _d(SEN_02, _FC, True, _M, "Sensor crítico sin lectura — No abrir la puerta",
       "Sin lectura de: {sensores}, en la fase {fase}. El ciclo se abortó.",
       "Verifique la conexión de los sensores antes de reiniciar."),
    # Tanda §1.1: sensor de temperatura del ciclo declarado y sin lectura,
    # fuera de ciclo. No bloquea el equipo; bloquea al INICIAR un programa
    # que lo use (RS-06, SENSOR_NO_DISPONIBLE).
    # D9-2 (tanda 9): ALARMA (antes AVISO), mismo bloqueo y despeje
    _d(SEN_03, _AL, False, _A, "Sensor de temperatura sin señal — No abrir la puerta",
       "{sensor} no entrega lectura ({valor}). Un programa que lo use no podrá iniciar.",
       "Verifique la conexión de la sonda o asígnele el rol No en uso."),
    # S1 (tanda 8, D8-1.2): en ciclo, FALLO con el vapor cortado y venteo solo
    # por la lenta; nunca se toma como vacío.
    _d(SEN_04, _FC, True, _M, "Sensor de presión de cámara sin lectura — No abrir la puerta",
       "El sensor de presión de cámara no entrega lectura en la fase {fase}. El ciclo se "
       "abortó: vapor cortado y descompresión solo por la válvula lenta.",
       "No abra la puerta. Llame a servicio técnico para revisar el sensor de presión de cámara."),
    _d(SEN_05, _FC, True, _M, "Sensor de presión de chaqueta sin lectura — No abrir la puerta",
       "El sensor de presión de chaqueta no entrega lectura en la fase {fase}. El ciclo se "
       "abortó: vapor cortado y descompresión solo por la válvula lenta.",
       "No abra la puerta hasta confirmar la cámara segura. Llame a servicio técnico para "
       "revisar el sensor de presión de chaqueta."),
    _d(SEN_08, _FC, True, _M, "Sensor de presión de empaque sin lectura — No abrir la puerta",
       "El sensor de presión de empaque de {puerta} no entrega lectura en la fase {fase}. "
       "El ciclo se abortó: vapor cortado y descompresión solo por la válvula lenta.",
       "No abra la puerta. Llame a servicio técnico para revisar el sensor de presión de "
       "empaque."),
    # S1 (tanda 8, D8-1.3): fuera de ciclo bloquea el inicio; "NO ABRIR" sigue
    # porque sin presión no se confirma la cámara segura.
    # D9-2 (tanda 9): ALARMA (antes AVISO), mismo bloqueo y despeje
    _d(SEN_06, _AL, True, _A, "Sensor de presión de cámara sin lectura — No abrir la puerta",
       "Sensor de presión de cámara sin lectura: llame a servicio.",
       "No abra la puerta: sin presión de cámara no se puede confirmar que sea seguro. "
       "Llame a servicio técnico."),
    # D9-2 (tanda 9): ALARMA (antes AVISO), mismo bloqueo y despeje
    _d(SEN_07, _AL, True, _A, "Sensor de presión de chaqueta sin lectura",
       "Sensor de presión de chaqueta sin lectura: llame a servicio.",
       "Llame a servicio técnico para revisar el sensor de presión de chaqueta."),
    # R8 (tanda 8; SAF-01/SAF-02 de su revisión): tras reasignar E/S, no se
    # inicia ningún ciclo hasta que el ingeniero verifique cada función en su
    # puerto nuevo (las analógicas, además, calibradas después de reasignar).
    _d(SEN_09, _AV, True, _A, "Reasignación de entradas y salidas sin verificar",
       "Funciones en un puerto nuevo sin verificar: {funciones}. No se pueden iniciar ciclos.",
       "El ingeniero debe verificar cada función en OPCIONES › Opciones avanzadas."),
    # S9 (tanda 9, D9-1.6): coherencia puerta-presión. Solo fuera de ciclo,
    # 3 lecturas para aparecer y 3 coherentes para despejarse sola. Sin
    # valores en el texto (las unidades de presión las elige el equipo).
    _d(SEN_10, _AL, True, _A, "Presión de cámara incoherente con la puerta abierta",
       "La puerta está abierta, pero la presión de cámara no corresponde a la presión "
       "atmosférica. No se pueden iniciar ciclos.",
       "Causas posibles: calibración del sensor de presión de cámara, presión atmosférica de "
       "referencia mal configurada o sensor de puerta. Llame a servicio técnico."),
    # E12 (tanda 12, C-13.7b): Referencia sin lectura durante el ciclo. No
    # aborta: el ciclo sigue con las sondas que leen y queda NO CONFORME.
    _d(SEN_11, _AV, False, _M, "Sensor de referencia sin lectura",
       # FC-08 (tanda 21): sin NO CONFORME; observación del ciclo
       "Sin lectura de {sensor} en la fase {fase}. El ciclo sigue controlado por el sensor "
       "Principal y la presión.",
       "Revise la conexión de la sonda de referencia. Valide la carga según su procedimiento "
       "antes de liberarla."),
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
    # Tanda §1.1 (b): una Referencia fuera de rango en esterilización no falla
    # el ciclo; alerta no bloqueante que queda en el historial.
    _d(CIC_09, _AV, False, _A, "Uniformidad térmica fuera de rango",
       "{sensor} está en {temp:.1f} °C, fuera del rango de esterilización "
       "({minimo:.1f}–{maximo:.1f} °C). El ciclo sigue controlado por el sensor Principal.",
       "Revise la carga y la ubicación de la sonda de referencia."),
    # SAF-04 de T5: el protocolo de estado seguro no puede terminar solo
    # D9-2 (tanda 9): ALARMA (antes AVISO), mismo bloqueo y despeje
    _d(CIC_10, _AL, False, _A, "Estado seguro detenido",
       "{motivo}. La cámara sigue sin considerarse segura.",
       "No abra la puerta. Revise la sonda Principal o asigne otra sonda como Principal en "
       "OPCIONES › Parámetros del ciclo › Sensores (técnico o ingeniero). Si no se resuelve, "
       "llame a servicio técnico."),
    # D8-2.8 (tanda 8): las pausas por falta de datos del módulo E/S (T2-a,
    # D8-2.7) en una misma exposición superaron pausa_max_esterilizacion_s
    _d(CIC_11, _AL, True, _M, "Comunicación inestable en esterilización",
       "Las pausas por falta de datos del módulo E/S sumaron {segundos:.0f} s en la "
       "esterilización (máximo {maximo:.0f} s). El ciclo se abortó.",
       "La carga NO está estéril. Revise el cable de red y la alimentación del módulo E/S y "
       "repita el ciclo. Si se repite, llame a servicio técnico."),
    # E12 (tanda 12, C-03): Tsat(P) - T_principal fuera de ±2 K durante 5 s
    # continuos en la exposición (solo carga sólida)
    _d(CIC_12, _AL, True, _M, "Aire o gases no condensables en la cámara",
       "La presión de cámara corresponde a {tsat:.1f} °C de saturación, {dt:.1f} K por encima "
       "del sensor Principal ({temp:.1f} °C). El ciclo se abortó.",
       "La carga NO está estéril. Revise la eliminación de aire (prevacío, prueba de Bowie & "
       "Dick y fugas de la cámara) y repita el ciclo."),
    _d(CIC_13, _AL, True, _M, "Vapor sobrecalentado o falla de la sonda",
       "El sensor Principal marca {temp:.1f} °C, {dt:.1f} K por encima de la saturación de la "
       "presión de cámara ({tsat:.1f} °C). El ciclo se abortó.",
       "La carga NO está estéril. Revise la sonda Principal y el sensor de presión de cámara "
       "(calibración) y el vapor de alimentación, y repita el ciclo."),
    # E12 (tanda 12, C-13.4): Referencia fuera de banda sin volver en
    # timeout_excursion_referencia
    _d(CIC_14, _AL, True, _M, "Referencia fuera de banda en esterilización",
       "{sensor} siguió fuera de la banda de esterilización por más de {minutos} min. El ciclo "
       "se abortó.",
       "La carga NO está estéril. Revise la carga, su ubicación y la sonda de referencia, y "
       "repita el ciclo."),
    # F2 (tanda 16, VCH §4.5): aislamiento de cámara por sobrepresión que no
    # se resuelve en timeout_aislamiento_camara, o que se repite
    # max_aislamientos_camara veces en ventana_aislamientos_camara
    _d(CIC_15, _AL, True, _M, "Sobrepresión de cámara sostenida",
       "La cámara siguió aislada por sobrepresión más de {minutos} min en la fase {fase} sin "
       "que la presión bajara del techo de control ({maximo:.1f} kPa). El ciclo se abortó.",
       "La carga NO está estéril. Revise la válvula de vapor de cámara (puede estar pegada "
       "abierta), los escapes y el sensor de presión de cámara. Llame a servicio técnico."),
    _d(CIC_16, _AL, True, _M, "Sobrepresión de cámara recurrente",
       "La cámara se aisló por sobrepresión {cantidad} veces en {minutos} min en la fase "
       "{fase}. El ciclo se abortó.",
       "La carga NO está estéril. Revise el techo de presión del programa y la regulación del "
       "vapor de chaqueta. Si se repite, llame a servicio técnico."),
    # F2 (tanda 16, P5 / D-14.5)
    _d(CIC_17, _AL, True, _M, "Exposición reiniciada demasiadas veces",
       "{sensor} volvió a salir de la banda de esterilización después de {reinicios} "
       "reinicios de la exposición (máximo {maximo}). El ciclo se abortó.",
       "La carga NO está estéril. Revise la carga, su ubicación y la sonda de referencia, y "
       "repita el ciclo."),
    # FC-08 (tanda 21): carga líquida, Referencia sin lectura
    _d(CIC_19, _AL, True, _M, "Sonda de referencia sin lectura — No abrir la puerta",
       "Sin lectura de {sensor} en la fase {fase}. En carga líquida la temperatura de la "
       "carga no se puede verificar. El ciclo se abortó.",
       "La carga NO está estéril. Revise la conexión de la sonda y repita el ciclo."),
    # F2 (tanda 16, D-CHQ / VCH-CHQ): no hay FALLO por esta vía (§4.6)
    _d(CIC_18, _AV, False, _A, "Presión de chaqueta en el límite de control",
       "La chaqueta llegó a {pres:.1f} kPa (límite {maximo:.1f} kPa) en la fase {fase}: la "
       "válvula de vapor de chaqueta queda cerrada mientras dure.",
       "Revise el regulador del vapor de suministro. El ciclo sigue."),
    # U4 (tanda 2): solo con el módulo E/S desconectado (sin puerto o puerto
    # perdido). Con el puerto presente y sin datos, TARJETA_SIN_TRAMA_VALIDA.
    _d(COM_01, _AL, True, _A, "Módulo E/S desconectado",
       "No se detecta el módulo E/S.",
       "Conecte el módulo E/S (cable de red) y verifique su alimentación."),
    _d(COM_02, _FC, True, _M, "Comunicación perdida durante el ciclo",
       "Se perdió la comunicación con el módulo E/S por más de {segundos:.1f} s en la fase "
       "{fase}. El ciclo se abortó.",
       "Verifique el cable de red y la alimentación del módulo E/S antes de reiniciar."),
    # D8-2.11 (tanda 8, Q1-P1): el módulo E/S no confirmó el ALL_OFF al salir del
    # modo prueba ni tras 3 reintentos. Bloquea el inicio hasta que llegue una
    # confirmación (ALL_OFF confirmado o handshake completo, que lo incluye).
    _d(COM_04, _AL, True, _A, "Salidas sin confirmar",
       "El módulo E/S no confirmó el apagado de todas las salidas al salir del "
       "modo prueba, ni tras 3 reintentos. Se repite la conexión con el módulo E/S.",
       "No inicie ciclos. Si la alarma no desaparece sola, llame a servicio técnico."),
    # T8 (D-03): alerta persistente, no bloqueante. Los ciclos se pueden
    # iniciar con confirmación explícita y quedan en el respaldo y el ticket.
    _d(OPERANDO_SIN_BD, _AL, False, _M, "Operando sin base de datos",
       "Base de datos no disponible: los ciclos se registran solo en el respaldo y en "
       "el ticket, sin operador. Opciones, calibración y usuarios no están disponibles.",
       "Llame a servicio técnico para revisar la base de datos."),
    _d(MANTENIMIENTO_VENCIDO, _AV, False, _A, "Mantenimiento vencido",
       "{motivo}",
       "Programe el mantenimiento con servicio técnico. El equipo puede seguir operando."),
    _d(IMPRESORA_DESCONECTADA, _AV, False, _A, "Impresora no conectada",
       "Impresora no conectada. Los reportes no se imprimirán; verifique el cable y la impresora.",
       "Revise el cable USB y que la impresora esté encendida. El equipo puede seguir operando."),
    # J12 (tanda 12, C-04.4): un origen por programa y parámetro migrado
    _d(MIGRACION_CORRECTIVA, _AV, False, _M, "Programa corregido al cargarlo",
       "El programa {programa} tenía {parametro} = {anterior} kPa, sobre el máximo permitido; "
       "se cambió a {nuevo} kPa.",
       "Un técnico o ingeniero debe revisar el programa en Opciones › Parámetros del ciclo. "
       "El equipo puede seguir operando."),
    # LIC-02 (licencia L0): despeje automático al cambiar la contraseña
    _d(CONTRASENA_SEMILLA, _AV, False, _A, "Contraseña de fábrica vigente",
       "La cuenta {cuentas} conserva la contraseña de fábrica, que es pública.",
       "Inicie sesión con esa cuenta y cambie la contraseña, o restablézcala en Opciones › "
       "Usuarios. El equipo puede seguir operando."),
    _d(CONFIGURACION_INVALIDA, _AL, True, _M, "Configuración inválida",
       "Configuración inválida: {motivo}",
       "Llame a servicio técnico para corregir la configuración."),
    # E6 decisión 9 (tanda 2026-10-14): fuera de ciclo, FALLA bloqueante que
    # se resuelve sola al completarse el siguiente handshake; en ciclo, COM-03
    # (FALLO_CRITICO, no se despeja sola) con el id del módulo E/S como causa.
    _d(COM_03, _FC, True, _M, "Falla del módulo E/S durante el ciclo",
       "{causa}: {motivo} Fase {fase}. El ciclo se abortó.",
       "Verifique el módulo E/S antes de reiniciar. Llame a servicio técnico."),
    _d(TARJETA_SIN_TRAMA_VALIDA, _AL, True, _A, "El módulo E/S no envía datos válidos",
       "{motivo}",
       "Revise el cable de red y la alimentación del módulo E/S. Llame a servicio técnico."),
    _d(TARJETA_VERSION_INCOMPATIBLE, _AL, True, _A, "Firmware del módulo E/S incompatible",
       "{motivo}",
       "Sin energía, revise el modelo y el orden de los módulos (principal, DI, DO, DO, PT100) y negocie (doble pulsación de Reload). Si el firmware es incompatible, llame a servicio técnico."),
    _d(TARJETA_SIN_ACK, _AL, True, _A, "El módulo E/S no confirma los comandos",
       "{motivo}",
       "Llame a servicio técnico."),
    _d(TARJETA_ALL_OFF_SIN_CONFIRMAR, _AL, True, _A,
       "El módulo E/S no confirmó el apagado de salidas",
       "{motivo}",
       "Llame a servicio técnico."),
    _d(TARJETA_CONFIG_SEGURIDAD, _AL, True, _A,
       "No se pudo verificar la configuración de seguridad de los módulos de E/S",
       "{motivo}",
       "Revise la red de los módulos de E/S. Si se repite, llame a servicio técnico."),
    _d(TARJETA_MODULOS_ORDEN, _AL, True, _A,
       "Orden de los módulos de E/S incorrecto o negociación pendiente",
       "{motivo}",
       "Sin energía, revise el orden de los módulos y negocie (doble pulsación de Reload)."),
    _d(TARJETA_SALIDAS_NO_APAGADAS, _AL, True, _A, "Salidas del módulo E/S no apagadas",
       "{motivo}",
       "No opere el equipo. Llame a servicio técnico (módulos de salida o su cableado)."),
    _d(TARJETA_EXPANSOR_FUERA_DE_LINEA, _AL, True, _A,
       "Expansor del módulo E/S fuera de línea",
       "{motivo}",
       "Sin energía, revise la unión de los módulos de expansión al principal. Si se repite, llame a servicio técnico."),
    _d(TARJETA_WATCHDOG, _AL, True, _A,
       "El módulo E/S apagó las salidas por falta de comunicación",
       "{motivo}",
       "Revise si el equipo de control se congeló. Si se repite, llame a servicio técnico."),
    _d(TARJETA_REINICIO, _AL, True, _A, "El módulo E/S se reinició",
       "{motivo}",
       "Revise la alimentación del módulo E/S. Si se repite, llame a servicio técnico."),
    _d(DISCREPANCIA_SALIDAS, _AL, True, _A,
       "Las salidas del módulo E/S no coinciden con lo comandado",
       "{motivo}",
       "Llame a servicio técnico."),
)

CATALOGO: dict[str, DefinicionAlarma] = {d.codigo: d for d in DEFINICIONES}

# T10 (tanda 10, D10-3): acción de CIC-10 cuando la causa es la presión de
# cámara sin lectura (D9-1.4). La de la definición (sonda Principal) sigue
# siendo la de las demás causas. La elige alarmas_i18n.accion() por el motivo.
CIC_10_ACCION_SIN_PRESION = (
    "No abra la puerta. Sin el sensor de presión de cámara no se puede llevar la cámara a "
    "estado seguro. Revise la conexión del sensor de presión de cámara o llame a servicio "
    "técnico.")

NOMBRES_LEGIBLES: dict[str, str] = {
    # Sensores
    # Sensores del ciclo: solo ubicación física (tanda §1.1)
    "temp_camara": "Cámara 1",
    "temp_2_camara": "Cámara 2",
    "temp_ref": "Referencia",
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
