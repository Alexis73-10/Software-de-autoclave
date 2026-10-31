# core/runtime/sensores_ciclo.py
#
# Catálogo de sensores de temperatura del ciclo y roles por programa
# (tanda 2026-10-14 §1.1; planeacion_sensores_ciclo.md rev. 2, RS-01 a RS-10,
# con los cambios de la tanda).
#
# - Roles por programa: exactamente 1 `principal`, 0 a 2 `referencia`, el
#   resto `no_en_uso`. Cualquiera de los tres sensores puede tener cualquier
#   rol. Los nombres visibles son solo ubicación física.
# - El Principal decide todo (control, fallas, F0, ticket, enfriamiento,
#   apertura, cámara segura). Las Referencias solo condicionan la entrada a
#   esterilización y generan una alerta de uniformidad térmica.
# - Un sensor `no_en_uso` no participa en control, fallas, F0, uniformidad,
#   entrada a esterilización, cámara segura, SENSOR_AUSENTE, SEN-03 ni SEN-11.
#   Tanda 17 (SON-01, decisión de Cristian): si está instalado se sigue
#   leyendo, publicando en /status y registrando en la gráfica del ciclo
#   (monitoreo); sin lectura se muestra "—", sin alarma ni aviso.
# - Se usa el Principal del programa seleccionado; sin programa, el del último
#   ciclo ejecutado; sin ninguno, temp_camara (el llamador elige el programa).

import json
import logging

from autoclave.core.runtime.lectura import lectura_valida
from autoclave.installation.equipment import get_capabilities
from autoclave.installation.profile import sonda_instalada

logger = logging.getLogger(__name__)

SENSORES = ("temp_camara", "temp_2_camara", "temp_ref")
NOMBRES = {"temp_camara": "Cámara 1", "temp_2_camara": "Cámara 2", "temp_ref": "Referencia"}
TIPOS = {"temp_camara": "camara", "temp_2_camara": "camara", "temp_ref": "referencia"}

PRINCIPAL, REFERENCIA, NO_EN_USO = "principal", "referencia", "no_en_uso"
ROLES = (PRINCIPAL, REFERENCIA, NO_EN_USO)
MAX_REFERENCIAS = 2
SENSOR_POR_OMISION = "temp_camara"

# Estados de disponibilidad (RS-01)
DISPONIBLE, SIN_SENAL, NO_INSTALADO = "disponible", "sin_senal", "no_instalado"

# Códigos de rechazo (RS-02, RS-06)
ASIGNACION_INVALIDA = "ASIGNACION_INVALIDA"
SENSOR_NO_DISPONIBLE = "SENSOR_NO_DISPONIBLE"
ASIGNACION_SENSORES_INVALIDA = "ASIGNACION_SENSORES_INVALIDA"
# PRG-01 (tanda 16, D-PRG-1): rol sobre una sonda no activa en el perfil
ROL_SONDA_NO_ACTIVA = "ROL_SONDA_NO_ACTIVA"


def asignacion_por_omision() -> dict[str, str]:
    """Asignación de fábrica: Principal = temp_camara, el resto no en uso."""
    return {s: (PRINCIPAL if s == SENSOR_POR_OMISION else NO_EN_USO) for s in SENSORES}


def interpretar_asignacion(crudo) -> tuple[dict, bool]:
    """(asignación, formato_antiguo). Migración perezosa (§4.2): sin el campo
    o con el formato antiguo ({"1": ..., "2": ...}) vale la de fábrica; el
    archivo no se reescribe hasta el primer guardado explícito. En el formato
    nuevo, un sensor ausente vale no_en_uso. No valida: ver errores_asignacion."""
    antiguo = (not isinstance(crudo, dict) or not crudo
               or all(str(k).isdigit() for k in crudo))
    if antiguo:
        return asignacion_por_omision(), True
    asignacion = {s: NO_EN_USO for s in SENSORES}
    asignacion.update(crudo)
    return asignacion, False


def errores_asignacion(asignacion) -> list[str]:
    """Invariantes 1, 2, 3 y 5 de §4.3 (la 4, disponibilidad, depende de la
    lectura en vivo: ver errores_disponibilidad)."""
    if not isinstance(asignacion, dict):
        return ["la asignación debe ser un objeto sensor → rol"]
    errores = []
    desconocidos = sorted(k for k in asignacion if k not in SENSORES)
    if desconocidos:
        errores.append(f"sensores desconocidos: {desconocidos}")
    invalidos = sorted(k for k, v in asignacion.items() if v not in ROLES)
    if invalidos:
        errores.append(f"rol inválido en: {invalidos}")
    principales = [k for k, v in asignacion.items() if v == PRINCIPAL]
    if len(principales) != 1:
        errores.append(f"debe haber exactamente un sensor principal (hay {len(principales)})")
    referencias = [k for k, v in asignacion.items() if v == REFERENCIA]
    if len(referencias) > MAX_REFERENCIAS:
        errores.append(f"como máximo {MAX_REFERENCIAS} referencias (hay {len(referencias)})")
    return errores


def asignacion_de(programa) -> dict:
    """Asignación del programa (atributo `sensores` del Cycle), o la de
    fábrica si el programa no la tiene."""
    asignacion = getattr(programa, "sensores", None) if programa is not None else None
    if not isinstance(asignacion, dict):
        return asignacion_por_omision()
    return asignacion


def sensor_principal(programa) -> str:
    """El Principal siempre está definido: con una asignación inválida se
    devuelve temp_camara (el programa no es ejecutable: verificar_inicio lo
    bloquea; aquí solo se evita leer un sensor arbitrario)."""
    asignacion = asignacion_de(programa)
    if errores_asignacion(asignacion):
        return SENSOR_POR_OMISION
    return next(k for k, v in asignacion.items() if v == PRINCIPAL)


def sensores_referencia(programa) -> list[str]:
    asignacion = asignacion_de(programa)
    if errores_asignacion(asignacion):
        return []
    return [s for s in SENSORES if asignacion.get(s) == REFERENCIA]


def sensores_en_uso(programa) -> list[str]:
    """Principal primero y luego las Referencias, en orden del catálogo."""
    return [sensor_principal(programa)] + sensores_referencia(programa)


def temp_principal(estado, programa):
    return estado.sensores_temp.get(sensor_principal(programa))


def temp_seguridad(estado, programas, profile=None):
    """Temperatura para las decisiones de seguridad (apertura, cámara segura,
    NO ABRIR). Máximo de las lecturas de los Principales (distintos) de
    `programas`; None (NO seguro) si alguna falta, vale 0 o su sensor no está
    declarado por la instalación (SAF-01 y SAF-07 de la revisión de T3: tras
    un ciclo, cambiar de programa o de roles no puede pasar a medir con una
    sonda fría mientras la carga sigue caliente)."""
    if not isinstance(programas, (list, tuple)):
        programas = [programas]
    sensores = []
    for p in programas or [None]:
        s = sensor_principal(p)
        if s not in sensores:
            sensores.append(s)
    lecturas = []
    for s in sensores:
        if profile is not None and not sensor_declarado(profile, s):
            return None
        valor = estado.sensores_temp.get(s)
        if not lectura_valida(valor) or valor == 0:
            return None
        lecturas.append(float(valor))
    return max(lecturas)


def _tiene_sensor_liquidos(profile) -> bool:
    clase = getattr(profile, "equipment_class", None)
    try:
        return get_capabilities(clase).has_liquid_sensor
    except (KeyError, TypeError):
        return False


def sensor_declarado(profile, sensor: str) -> bool:
    """S-9 / RS-01.4: declarado por la instalación. Sin perfil, los tres.
    temp_2_camara solo existe en clases de laboratorio (has_liquid_sensor)."""
    if sensor not in SENSORES:
        return False
    if profile is None:
        return True
    if sensor == "temp_2_camara" and not _tiene_sensor_liquidos(profile):
        return False
    return sonda_instalada(profile, sensor)


def sensores_declarados(profile) -> list[str]:
    return [s for s in SENSORES if sensor_declarado(profile, s)]


# Tanda 17 (SON-01): series de temperatura de la gráfica del ciclo antes de SON-01
_SERIES_GRAFICA_ANTERIORES = ("temp_camara", "temp_ref")


def sondas_grafica(profile) -> frozenset:
    """Tanda 17 (SON-01, decisión de Cristian): sondas del ciclo cuyas
    lecturas guardadas (lecturas_grafica) se entregan a la gráfica, al PDF y
    al correo: las declaradas por la instalación, sin mirar el rol (una sonda
    No en uso es de monitoreo y se registra; una no instalada sigue oculta).
    Solo presentación: ante un error, las de antes de SON-01."""
    try:
        return frozenset(sensores_declarados(profile))
    except Exception:
        logger.exception("SON-01: no se pudieron leer las sondas declaradas para la gráfica")
        return frozenset(_SERIES_GRAFICA_ANTERIORES)


def temperaturas_grafica(fila, sondas) -> dict:
    """{temp_camara, temp_ref, temp_2_camara} de una fila de lecturas_grafica
    para /cycle/current/graph y /cycle/history/{id}/graph: None en las sondas
    que no están en `sondas` (sondas_grafica) o si la fila no trae la columna."""
    resultado = {}
    for s in SENSORES:
        try:
            valor = fila[s]
        except (KeyError, IndexError):
            valor = None
        resultado[s] = valor if s in sondas else None
    return resultado


def estado_sensor(profile, estado, sensor: str) -> str:
    if not sensor_declarado(profile, sensor):
        return NO_INSTALADO
    lectura = estado.sensores_temp.get(sensor)
    # 0 = sin lectura, mismo criterio que SEN-03 (SAF-09 de la revisión de T3)
    return DISPONIBLE if lectura_valida(lectura) and lectura != 0 else SIN_SENAL


def f0_disponible(profile) -> bool:
    """F0 solo en equipos de laboratorio (clases *_lab, has_liquid_sensor).
    Sin perfil no se restringe (comportamiento previo)."""
    if profile is None:
        return True
    return _tiene_sensor_liquidos(profile)


def errores_disponibilidad(asignacion: dict, profile, estado) -> list[str]:
    """Sensores en uso no declarados o sin lectura (invariante 4, RS-06)."""
    return [s for s, rol in asignacion.items()
            if rol in (PRINCIPAL, REFERENCIA)
            and estado_sensor(profile, estado, s) != DISPONIBLE]


def roles_sonda_no_activa(asignacion, profile) -> list[str]:
    """PRG-01 (tanda 16, D-PRG-1): sensores con rol Principal o Referencia
    cuya sonda no está activa en el perfil de instalación (temperature_probes,
    o temp_2_camara en una clase sin sensor de líquidos). Sin perfil, []
    (comportamiento anterior)."""
    if profile is None or not isinstance(asignacion, dict):
        return []
    return [s for s in SENSORES if asignacion.get(s) in (PRINCIPAL, REFERENCIA)
            and not sensor_declarado(profile, s)]


MOTIVO_SONDA_NO_ACTIVA = "rol asignado a una sonda no activa en el perfil de instalación"


def motivo_sonda_no_activa(sensores) -> str:
    return f"{MOTIVO_SONDA_NO_ACTIVA}: " + ", ".join(NOMBRES.get(s, s) for s in sensores)


def verificar_inicio(programa, profile, estado):
    """RS-06: None si el programa puede iniciar; si no, (código, detalle).
    PRG-01 (tanda 16, D-PRG-1): un rol sobre una sonda no activa en el perfil
    reutiliza el bloqueo de sensor ausente (SENSOR_NO_DISPONIBLE, que ya
    trataban así tests/test_t3_sensores_ciclo.py y la interfaz) con un motivo
    propio que empieza por MOTIVO_SONDA_NO_ACTIVA, evaluado antes que la
    falta de lectura (DECISIÓN SIN CONFIRMAR: D-PRG-1 admite reutilizar el
    bloqueo existente; ROL_SONDA_NO_ACTIVA queda para la asignación)."""
    asignacion = asignacion_de(programa)
    errores = errores_asignacion(asignacion)
    if errores:
        return ASIGNACION_SENSORES_INVALIDA, "; ".join(errores)
    no_activas = roles_sonda_no_activa(asignacion, profile)
    if no_activas:
        return SENSOR_NO_DISPONIBLE, motivo_sonda_no_activa(no_activas)
    faltan = errores_disponibilidad(asignacion, profile, estado)
    if faltan:
        return SENSOR_NO_DISPONIBLE, f"sensores en uso sin lectura o no instalados: {faltan}"
    return None


def vigilar_fuera_de_ciclo(alarm_manager, profile, sensor: str, valor) -> None:
    """PREPARACION/PREPARADO (tanda §1.1): un sensor del ciclo declarado por
    la instalación y sin lectura (None, no finito o 0) da la alerta SEN-03,
    no bloqueante; uno no declarado no se vigila."""
    from autoclave.state_machine.alarms.catalogo import SEN_03, nombre_legible
    if not sensor_declarado(profile, sensor):
        return
    legible = nombre_legible(sensor)
    if not lectura_valida(valor) or valor == 0:
        alarm_manager.activar(SEN_03, origen=legible, sensor=legible, valor=valor)
    else:
        alarm_manager.resolver(SEN_03, origen=legible)


# ── S11 (tanda 11, D11-3): SEN-03 solo para los sensores en uso ─────────────

def sensores_vigilados_fuera_de_ciclo(programas) -> set:
    """Sensores del ciclo que SEN-03 vigila en PREPARACION/PREPARADO: unión
    de Principal + Referencias de `programas` (programas_seguridad(): el
    seleccionado y las copias que aún cuentan para la seguridad). Sin
    programas, la regla del Principal sin programa (asignación de fábrica).
    Con una asignación inválida se vigila de más: los sensores marcados
    principal/referencia en ella más el de fábrica (falla segura; ese
    programa no puede iniciar, verificar_inicio lo bloquea)."""
    lista = [p for p in (programas or []) if p is not None] or [None]
    vigilados = set()
    for p in lista:
        vigilados.update(sensores_en_uso(p))
        asignacion = asignacion_de(p)
        if errores_asignacion(asignacion):
            vigilados.add(SENSOR_POR_OMISION)
            if isinstance(asignacion, dict):
                vigilados.update(s for s, rol in asignacion.items()
                                 if s in SENSORES and rol in (PRINCIPAL, REFERENCIA))
    return vigilados


def programas_para_sen03(programas_seguridad, cycle):
    """Programas cuyos sensores en uso vigila SEN-03. Sin proveedor, el
    programa del estado. None si el proveedor falla: el llamador vigila los
    tres sensores (comportamiento anterior a S11, falla segura)."""
    if programas_seguridad is None:
        return [cycle]
    try:
        return list(programas_seguridad() or [])
    except Exception:
        logger.exception("SEN-03: no se pudieron obtener los programas; se vigilan todos")
        return None


def vigilar_en_uso_fuera_de_ciclo(alarm_manager, profile, estado, programas) -> None:
    """D11-3: vigila (vigilar_fuera_de_ciclo) los sensores en uso de
    `programas`; los demás no se vigilan y su SEN-03, si estaba activa, se
    resuelve. `programas=None` vigila los tres (falla segura)."""
    from autoclave.state_machine.alarms.catalogo import SEN_03, nombre_legible
    vigilados = set(SENSORES) if programas is None else sensores_vigilados_fuera_de_ciclo(programas)
    for sensor in SENSORES:
        if sensor in vigilados:
            vigilar_fuera_de_ciclo(alarm_manager, profile, sensor,
                                   estado.sensores_temp.get(sensor))
        else:
            alarm_manager.resolver(SEN_03, origen=nombre_legible(sensor))


def canonica(asignacion: dict) -> str:
    """JSON canónico (claves ordenadas) para auditoría y registro del ciclo."""
    return json.dumps(asignacion, sort_keys=True, ensure_ascii=False)
