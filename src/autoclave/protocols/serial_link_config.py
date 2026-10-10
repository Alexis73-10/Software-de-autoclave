# autoclave.protocols.serial_link_config
# ---------------------------------------
# Parámetros ajustables del enlace serial PC <-> ESP32 (protocolo v2).
# Ver docs/mis_plans/planeacion_protocolo_serial_esp32.md, secciones 4, 10 y 11.
#
# Se leen solo desde src/autoclave/config/serial_link.json. Si el archivo
# falta o no es JSON válido, se registra una advertencia y se usan los valores
# internos (iguales a los de la especificación). Un valor fuera de rango o de
# tipo incorrecto se rechaza de la misma forma: advertencia y valor interno
# para esa clave.

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Any, Optional

from autoclave.utils.logging import logger
from autoclave.utils.resources import resource_path

CONFIG_RELATIVE_PATH = "autoclave/config/serial_link.json"


@dataclass(frozen=True)
class SerialLinkConfig:
    # Líneas inválidas consecutivas que se declaran pérdida de comunicación (4.4).
    lineas_invalidas_max: int = 10
    # Presupuesto total del handshake de conexión (4.6).
    handshake_presupuesto_s: float = 15.0
    # Intentos de ALL_OFF del handshake y espera de "OK ALL_OFF" por intento (4.6).
    all_off_intentos: int = 3
    all_off_timeout_s: float = 1.0
    # Tramas ST/DO consecutivas para declarar discrepancia sostenida (2.3, 6.5, 7).
    tramas_discrepancia: int = 2
    # Reintento automático de conexión/handshake (D-02).
    reintento_handshake_s: float = 3.0
    # Longitud máxima de una línea recibida, en bytes, antes de descartarla.
    longitud_max_linea: int = 256
    # D-05: disc_do (lectura de vuelta de salidas) dispara fallo. Apagado hasta
    # validarlo en hardware real; mientras tanto solo diagnóstico.
    disc_do_dispara_fallo: bool = False


# (tipo, mínimo, máximo) por clave. bool no lleva rango.
_RANGOS: dict[str, tuple[type, Optional[float], Optional[float]]] = {
    "lineas_invalidas_max":    (int,   1,    1000),
    "handshake_presupuesto_s": (float, 1.0,  120.0),
    "all_off_intentos":        (int,   1,    10),
    "all_off_timeout_s":       (float, 0.1,  10.0),
    "tramas_discrepancia":     (int,   1,    20),
    "reintento_handshake_s":   (float, 0.5,  60.0),
    "longitud_max_linea":      (int,   32,   4096),
    "disc_do_dispara_fallo":   (bool,  None, None),
}


def _validar(clave: str, valor: Any) -> Any:
    tipo, minimo, maximo = _RANGOS[clave]
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


def config_desde_dict(datos: Any, origen: str = "<dict>") -> SerialLinkConfig:
    defecto = SerialLinkConfig()
    if not isinstance(datos, dict):
        logger.warning("serial_link: configuración %s inválida (no es un objeto JSON); "
                       "se usan los valores internos", origen)
        return defecto

    valores = {}
    for f in fields(SerialLinkConfig):
        if f.name not in datos:
            continue
        try:
            valores[f.name] = _validar(f.name, datos[f.name])
        except ValueError as e:
            logger.warning("serial_link: %s=%r rechazado en %s (%s); se usa el valor "
                           "interno %r", f.name, datos[f.name], origen, e,
                           getattr(defecto, f.name))

    desconocidas = set(datos) - {f.name for f in fields(SerialLinkConfig)}
    if desconocidas:
        logger.warning("serial_link: claves desconocidas ignoradas en %s: %s",
                       origen, sorted(desconocidas))

    return SerialLinkConfig(**valores)


def cargar_config(path: Optional[str] = None) -> SerialLinkConfig:
    path = path or resource_path(CONFIG_RELATIVE_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        logger.warning("serial_link: no existe %s; se usan los valores internos", path)
        return SerialLinkConfig()
    except (OSError, ValueError) as e:
        logger.warning("serial_link: no se pudo leer %s (%s); se usan los valores internos",
                       path, e)
        return SerialLinkConfig()
    return config_desde_dict(datos, path)
