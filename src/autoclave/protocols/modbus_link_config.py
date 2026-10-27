# autoclave.protocols.modbus_link_config
# ---------------------------------------
# Parámetros ajustables del enlace Modbus TCP con los módulos Ebyte M31-U
# (tanda 19, MOD-06; docs/mis_plans/planeacion_enlace_modbus.md).
#
# Se leen solo desde src/autoclave/config/modbus_link.json. Mismo criterio
# que la configuración del antiguo enlace serial: si el archivo falta o no es JSON válido, advertencia
# y valores internos; un valor de tipo o rango incorrecto se rechaza con
# advertencia y se usa el valor interno de esa clave.

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field, fields
from typing import Any, Optional

from autoclave.utils.logging import logger
from autoclave.utils.resources import resource_path

CONFIG_RELATIVE_PATH = "autoclave/config/modbus_link.json"

# Composición del riel (decisiones de la tanda 19, punto 7): principal y las
# expansiones en orden. Se compara sin «M31-», sin «-U», sin espacios y sin
# distinguir mayúsculas.
# ADB-01 (adenda_tanda_19_banco.md, tanda 20 T20-02): la lista de esclavos
# 0x0C80 incluye las E/S del propio principal como esclavo ID 0 (GXAXX0A00,
# 16 AI); los esclavos esperados son los IDs 0 a 4 y el ID 5 debe ser NONE.
COMPOSICION_INTERNA: dict = {
    "principal": "XAXX0A00G",
    "expansiones": ("GXAXX0A00", "GAXXXA000", "GXXAX00A0", "GXXAX00A0", "GXDXX0600"),
}
# Esclavos de la tabla 0x0C80 (8 registros cada uno, 32 esclavos).
MAX_EXPANSIONES = 32


@dataclass(frozen=True)
class ModbusLinkConfig:
    ip: str = "192.168.3.7"
    puerto: int = 502
    unit_id: int = 1
    # Periodo del sondeo de todas las entradas (decisión 3 de la tanda 19).
    periodo_sondeo_s: float = 0.1
    # Tiempo máximo de respuesta de una transacción.
    timeout_s: float = 0.3
    # Transacciones fallidas seguidas que se declaran pérdida (MOD-09).
    fallos_para_desconexion: int = 3
    # Reintento de la conexión verificada tras un fallo (MOD-06).
    reintento_conexion_s: float = 3.0
    # Presupuesto total de la conexión verificada (MOD-06).
    presupuesto_conexion_s: float = 15.0
    # 0x0C35 en décimas de segundo (10 = 1,0 s). DECISIÓN SIN CONFIRMAR (M-1).
    tiempo_desconexion_modulo_ds: int = 10
    # Intentos de escribir y verificar cada bloque de configuración (MOD-07).
    intentos_escritura_config: int = 3
    # Filtro de las PT100 (0x3AA4..) y de la AI (0x0DA2).
    filtro_pt100: int = 1
    filtro_ai: int = 0
    composicion_esperada: dict = field(
        default_factory=lambda: {"principal": COMPOSICION_INTERNA["principal"],
                                 "expansiones": list(COMPOSICION_INTERNA["expansiones"])})
    # Sondeos consecutivos con discrepancia comandado/leído (MOD-11).
    tramas_discrepancia: int = 2
    # Con Modbus la lectura sale del propio módulo de relés. DECISIÓN SIN CONFIRMAR.
    discrepancia_dispara_fallo: bool = True
    # ADB-04 (decisión 8 de la tanda 20): espera tras ordenar el reinicio del
    # módulo (0x0C1D = 0x5BB5) antes de reabrir el socket. DECISIÓN SIN
    # CONFIRMAR (banco M-5).
    espera_reinicio_s: float = 5.0
    # ADB-04: plazo propio para reabrir el socket y obtener respuesta tras el
    # reinicio; extiende el fin del intento de conexión solo cuando hay reinicio.
    presupuesto_reinicio_s: float = 30.0


# (tipo, mínimo, máximo) por clave. bool, str y estructura no llevan rango.
_RANGOS: dict[str, tuple[Any, Optional[float], Optional[float]]] = {
    "ip":                           ("ipv4", None, None),
    "puerto":                       (int,   1,    65535),
    "unit_id":                      (int,   1,    247),
    "periodo_sondeo_s":             (float, 0.05, 1.0),
    "timeout_s":                    (float, 0.05, 2.0),
    "fallos_para_desconexion":      (int,   1,    20),
    "reintento_conexion_s":         (float, 0.1,  60.0),
    "presupuesto_conexion_s":       (float, 1.0,  120.0),
    "tiempo_desconexion_modulo_ds": (int,   5,    100),
    "intentos_escritura_config":    (int,   1,    10),
    "filtro_pt100":                 (int,   1,    16),
    "filtro_ai":                    (int,   0,    4),
    "composicion_esperada":         ("composicion", None, None),
    "tramas_discrepancia":          (int,   1,    20),
    "discrepancia_dispara_fallo":   (bool,  None, None),
    "espera_reinicio_s":            (float, 0.0,  60.0),
    "presupuesto_reinicio_s":       (float, 0.5,  120.0),
}


def normalizar_modelo(texto: str) -> str:
    """Modelo comparable: sin espacios, mayúsculas, sin «M31-» ni «-U»."""
    t = "".join(str(texto).split()).upper()
    if t.startswith("M31-"):
        t = t[4:]
    if t.endswith("-U"):
        t = t[:-2]
    return t


def _modelo_valido(valor: Any) -> str:
    if not isinstance(valor, str):
        raise ValueError("modelo no es texto")
    m = normalizar_modelo(valor)
    if not m or not m.isalnum() or m == "NONE":
        raise ValueError(f"modelo inválido {valor!r}")
    return m


def _validar_composicion(valor: Any) -> dict:
    if not isinstance(valor, dict) or set(valor) != {"principal", "expansiones"}:
        raise ValueError("debe ser un objeto con 'principal' y 'expansiones'")
    principal = _modelo_valido(valor["principal"])
    exp = valor["expansiones"]
    if not isinstance(exp, list) or not (1 <= len(exp) <= MAX_EXPANSIONES):
        raise ValueError(f"'expansiones' debe ser una lista de 1 a {MAX_EXPANSIONES} modelos")
    return {"principal": principal, "expansiones": [_modelo_valido(m) for m in exp]}


def _validar(clave: str, valor: Any) -> Any:
    tipo, minimo, maximo = _RANGOS[clave]
    if tipo == "ipv4":
        if not isinstance(valor, str):
            raise ValueError("debe ser texto")
        try:
            ipaddress.IPv4Address(valor.strip())
        except ValueError:
            raise ValueError("no es una dirección IPv4") from None
        return valor.strip()
    if tipo == "composicion":
        return _validar_composicion(valor)
    if tipo is bool:
        if not isinstance(valor, bool):
            raise ValueError("debe ser true/false")
        return valor
    # bool es subclase de int en Python: se rechaza explícitamente.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("debe ser numérico")
    if tipo is int and not float(valor).is_integer():
        raise ValueError("debe ser entero")
    if not (minimo <= valor <= maximo):
        raise ValueError(f"fuera de rango [{minimo}, {maximo}]")
    return tipo(valor)


def config_desde_dict(datos: Any, origen: str = "<dict>") -> ModbusLinkConfig:
    defecto = ModbusLinkConfig()
    if not isinstance(datos, dict):
        logger.warning("modbus_link: configuración %s inválida (no es un objeto JSON); "
                       "se usan los valores internos", origen)
        return defecto

    valores = {}
    for f in fields(ModbusLinkConfig):
        if f.name not in datos:
            continue
        try:
            valores[f.name] = _validar(f.name, datos[f.name])
        except ValueError as e:
            logger.warning("modbus_link: %s=%r rechazado en %s (%s); se usa el valor "
                           "interno %r", f.name, datos[f.name], origen, e,
                           getattr(defecto, f.name))

    desconocidas = set(datos) - {f.name for f in fields(ModbusLinkConfig)}
    if desconocidas:
        logger.warning("modbus_link: claves desconocidas ignoradas en %s: %s",
                       origen, sorted(desconocidas))

    _validar_cruzado(valores, defecto, origen)
    return ModbusLinkConfig(**valores)


# V19-s1-04: all_off(1.0) debe alcanzar a leer la confirmación (timeout de
# una transacción menor que la mitad del segundo).
TIMEOUT_MAXIMO_CRUZADO_S = 0.5


def _validar_cruzado(valores: dict, defecto: ModbusLinkConfig, origen: str) -> None:
    """Validación cruzada (V19-s1-04): las claves implicadas vuelven al valor
    interno, con advertencia. Los valores internos cumplen las dos reglas."""
    periodo = valores.get("periodo_sondeo_s", defecto.periodo_sondeo_s)
    desconexion = valores.get("tiempo_desconexion_modulo_ds",
                              defecto.tiempo_desconexion_modulo_ds)
    # El sondeo debe renovar el temporizador del módulo al menos dos veces
    # dentro de su tiempo de desconexión.
    if not periodo < (desconexion / 10.0) / 2.0:
        logger.warning("modbus_link: periodo_sondeo_s=%r no es menor que la mitad de "
                       "tiempo_desconexion_modulo_ds=%r (%.2f s) en %s; se usan los "
                       "valores internos %r y %r", periodo, desconexion,
                       desconexion / 20.0, origen, defecto.periodo_sondeo_s,
                       defecto.tiempo_desconexion_modulo_ds)
        valores.pop("periodo_sondeo_s", None)
        valores.pop("tiempo_desconexion_modulo_ds", None)
    timeout = valores.get("timeout_s", defecto.timeout_s)
    if timeout >= TIMEOUT_MAXIMO_CRUZADO_S:
        logger.warning("modbus_link: timeout_s=%r no es menor que %.1f s (all_off(1.0) no "
                       "alcanzaría a confirmar) en %s; se usa el valor interno %r",
                       timeout, TIMEOUT_MAXIMO_CRUZADO_S, origen, defecto.timeout_s)
        valores.pop("timeout_s", None)


def cargar_config(path: Optional[str] = None) -> ModbusLinkConfig:
    path = path or resource_path(CONFIG_RELATIVE_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        logger.warning("modbus_link: no existe %s; se usan los valores internos", path)
        return ModbusLinkConfig()
    except (OSError, ValueError) as e:
        logger.warning("modbus_link: no se pudo leer %s (%s); se usan los valores internos",
                       path, e)
        return ModbusLinkConfig()
    return config_desde_dict(datos, path)
