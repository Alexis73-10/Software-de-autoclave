# autoclave/estacion/configurar_modulo.py
#
# T20-04 (tanda 20, decisiones_tanda_20.md): `Autoclave.exe --rol
# configurar-modulo`. Lo invoca el Setup después del paso 08 (red de los
# módulos) para probar la conexión con el módulo principal M31-U y, si se le
# pasa, cambiar la contraseña de su página web (decisión 6).
#
# Recorrido:
#   1. Si llega --clave-archivo, lee la contraseña y BORRA el archivo de
#      inmediato (en un finally: también si algo falla después). La
#      contraseña nunca va al log, al resultado, a excepciones ni a la línea
#      de comandos.
#   2. Si hay un backend escuchando en 127.0.0.1:8000, no actúa
#      (backend_activo): no comparte el módulo con un software en marcha.
#   3. Lee la identidad de los módulos con ModbusLink.leer_identidad() (el
#      mismo código y la misma verificación que la conexión del software:
#      código de error y negociación, modelos, firmware y MAC), con reintentos
#      mientras no haya conexión y un presupuesto total de PRESUPUESTO_S (el
#      adaptador puede tardar en subir tras el paso 08).
#   4. Con contraseña válida (1 a 6 caracteres ASCII imprimibles), escribe el
#      usuario «admin» (0x758B, 5 registros) y la contraseña (0x7590, 3
#      registros) con la función 10 por el cliente del enlace y los relee.
#
# No escribe bobinas, ni la configuración de seguridad, ni reinicia el
# módulo, ni escribe 0x0C37: eso lo hace el software al conectar (MOD-07,
# ADB-04).
#
# --ip/--puerto solo se aceptan con --ip 127.0.0.1 exactamente (probar el .exe
# contra el simulador); con cualquier otra IP se ignoran ambos, con una
# advertencia, y se usan 192.168.3.7:502 (decisión 3).
#
# Resultado (--resultado <ruta>): JSON con una clave por línea y valores
# escalares planos (Inno Setup lo lee con búsqueda de texto): ok, codigo,
# texto_es, texto_en, accion_es, accion_en, modelo, composicion, n_modulos,
# firmware, mac, clave_cambiada.
#
# Códigos de salida: 0 ok; 2 backend_activo; 3 sin_conexion; 4 composicion,
# orden, firmware o expansor; 5 clave_invalida; 6 clave_no_quedo; 7 error o
# argumentos.
#
# Nota de riesgo (MED-04): la contraseña web se puede leer por Modbus (03 en
# 0x7590) y Modbus TCP no tiene autenticación; la protección real es la red
# dedicada.

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import socket
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

PRESUPUESTO_S = 30.0
PAUSA_REINTENTO_S = 1.0
IP_MODULO = "192.168.3.7"
PUERTO_MODULO = 502
IP_LOCAL = "127.0.0.1"
PUERTO_BACKEND = 8000
USUARIO_WEB = "admin"
MAX_CLAVE = 6

CODIGOS_SALIDA = {
    "ok": 0,
    "backend_activo": 2,
    "sin_conexion": 3,
    "composicion": 4, "orden": 4, "firmware": 4, "expansor": 4,
    "clave_invalida": 5,
    "clave_no_quedo": 6,
    "error": 7, "argumentos": 7,
}
# Códigos con texto de acción sugerida en el catálogo i18n.
_CON_ACCION = {"sin_conexion", "composicion", "orden", "firmware", "clave_no_quedo"}


class _ErrorArgumentos(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):           # nunca SystemExit
        raise _ErrorArgumentos(message)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = _Parser(prog="Autoclave.exe --rol configurar-modulo", add_help=False,
                allow_abbrev=False)
    p.add_argument("--resultado", required=True)
    p.add_argument("--clave-archivo", default=None)
    p.add_argument("--ip", default=None)
    p.add_argument("--puerto", type=int, default=None)
    p.add_argument("--idioma", choices=("es", "en"), default="es")
    return p.parse_args(argv)


def _ruta_resultado(argv: list[str]) -> Optional[str]:
    """--resultado aunque el resto de los argumentos no sea válido."""
    for i, a in enumerate(argv):
        if a == "--resultado" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--resultado="):
            return a.split("=", 1)[1]
    return None


def destino(ip: Optional[str], puerto: Optional[int]) -> tuple[str, int]:
    """(ip, puerto) a usar: los pedidos solo con 127.0.0.1 exactamente."""
    if ip == IP_LOCAL:
        return IP_LOCAL, puerto if puerto is not None else PUERTO_MODULO
    if ip is not None or puerto is not None:
        logger.warning("configurar-modulo: --ip/--puerto solo se aceptan con %s; se usan "
                       "%s:%d", IP_LOCAL, IP_MODULO, PUERTO_MODULO)
    return IP_MODULO, PUERTO_MODULO


def backend_escuchando() -> bool:
    """True si algo escucha en 127.0.0.1:8000 (sin Qt)."""
    try:
        with socket.create_connection((IP_LOCAL, PUERTO_BACKEND), timeout=0.5):
            return True
    except OSError:
        return False


def clave_valida(clave: str) -> bool:
    return (1 <= len(clave) <= MAX_CLAVE
            and all(0x20 <= ord(c) <= 0x7E for c in clave))


def _leer_y_borrar_clave(ruta: str) -> Optional[str]:
    """Lee la contraseña (ASCII) y borra el archivo siempre. None si no se
    pudo leer o no es ASCII. Quita solo los \\r\\n finales."""
    try:
        with open(ruta, "rb") as f:
            crudo = f.read()
        try:
            texto = crudo.decode("ascii")
        except UnicodeDecodeError:
            return None
        return texto.rstrip("\r\n")
    except OSError as e:
        logger.warning("configurar-modulo: no se pudo leer el archivo de la contraseña (%s)",
                       type(e).__name__)
        return None
    finally:
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.error("configurar-modulo: no se pudo borrar el archivo de la contraseña "
                         "(%s)", type(e).__name__)


def _crear_enlace(ip: str, puerto: int, presupuesto_s: float):
    from autoclave.protocols.modbus_link import ModbusLink
    from autoclave.protocols.modbus_link_config import cargar_config
    base = cargar_config()
    cfg = dataclasses.replace(base, ip=ip, puerto=puerto,
                              presupuesto_conexion_s=max(1.0, min(base.presupuesto_conexion_s,
                                                                  presupuesto_s)))
    return ModbusLink(config=cfg)


def _resultado_base() -> dict[str, Any]:
    return {"ok": False, "codigo": "error", "texto_es": "", "texto_en": "",
            "accion_es": "", "accion_en": "", "modelo": "", "composicion": "",
            "n_modulos": 0, "firmware": "", "mac": "", "clave_cambiada": False}


def _textos(res: dict, codigo: str, **params) -> None:
    from autoclave import i18n
    res["codigo"] = codigo
    res["ok"] = codigo == "ok"
    for idioma in ("es", "en"):
        if codigo == "ok":
            texto = i18n.t("configurar_modulo.ok", idioma, modelo=res["modelo"],
                           n=res["n_modulos"], firmware=res["firmware"], mac=res["mac"])
            if res["clave_cambiada"]:
                texto += " " + i18n.t("configurar_modulo.ok_clave", idioma)
        else:
            texto = i18n.t(f"configurar_modulo.{codigo}", idioma, **params)
        res[f"texto_{idioma}"] = texto
        res[f"accion_{idioma}"] = (i18n.t(f"configurar_modulo.{codigo}_accion", idioma)
                                   if codigo in _CON_ACCION else "")


def _escribir_resultado(ruta: Optional[str], res: dict) -> None:
    if not ruta:
        return
    plano = {k: (v if isinstance(v, (bool, int, float)) or v is None else str(v))
             for k, v in res.items()}
    try:
        with open(ruta, "w", encoding="ascii", errors="replace") as f:
            json.dump(plano, f, ensure_ascii=True, indent=2)
            f.write("\n")
    except OSError as e:
        logger.error("configurar-modulo: no se pudo escribir el resultado en %s (%s)", ruta, e)


def _codigo_de_fallo(causa: Optional[str]) -> str:
    if causa in ("composicion", "orden", "firmware", "expansor"):
        return causa
    if causa == "sin_conexion":
        return "sin_conexion"
    return "error"


def _identidad_parcial(res: dict, enlace) -> None:
    """Modelo, composición y MAC leídos antes de un fallo (diagnóstico)."""
    try:
        mod = enlace.get_diagnostico()["modulos"]
    except Exception:
        return
    modelos = mod.get("modelos") or {}
    res["modelo"] = modelos.get("principal") or ""
    exp = modelos.get("expansiones") or []
    res["composicion"] = ",".join(str(e) for e in exp)
    res["n_modulos"] = len(exp)
    fw = mod.get("firmware") or {}
    if fw:
        res["firmware"] = f"{fw.get('principal')} / " + ",".join(fw.get("expansiones") or [])
    res["mac"] = mod.get("mac") or ""


def ejecutar(args: argparse.Namespace, clave: Optional[str], hay_clave: bool) -> dict:
    """Pasos 2 a 4. `clave` ya leída (el archivo ya está borrado)."""
    from autoclave.protocols.modbus_link import FalloConexion

    res = _resultado_base()
    if backend_escuchando():
        logger.warning("configurar-modulo: hay un backend escuchando en %s:%d; no se actúa",
                       IP_LOCAL, PUERTO_BACKEND)
        _textos(res, "backend_activo")
        return res

    ip, puerto = destino(args.ip, args.puerto)
    logger.info("configurar-modulo: módulo en %s:%d (presupuesto %.0f s)", ip, puerto,
                PRESUPUESTO_S)
    fin = time.monotonic() + PRESUPUESTO_S
    enlace = None
    identidad = None
    ultimo: Optional[FalloConexion] = None
    intento = 0
    while True:
        intento += 1
        restante = fin - time.monotonic()
        enlace = _crear_enlace(ip, puerto, restante)
        try:
            identidad = enlace.leer_identidad(cerrar=not hay_clave)
            break
        except FalloConexion as f:
            ultimo = f
            logger.info("configurar-modulo: intento %d sin éxito (%s): %s", intento,
                        f.causa, f.motivo)
            if f.causa != "sin_conexion" or time.monotonic() + PAUSA_REINTENTO_S >= fin:
                break
            time.sleep(PAUSA_REINTENTO_S)

    if identidad is None:
        codigo = _codigo_de_fallo(ultimo.causa if ultimo else None)
        if enlace is not None:
            _identidad_parcial(res, enlace)
        _textos(res, codigo, detalle=ultimo.motivo if ultimo else "")
        return res

    res.update(modelo=identidad["modelo"] or "",
               composicion=",".join(identidad["composicion"]),
               n_modulos=int(identidad["n_modulos"]), firmware=identidad["firmware"],
               mac=identidad["mac"])
    try:
        if hay_clave:
            if clave is None or not clave_valida(clave):
                logger.warning("configurar-modulo: contraseña web no válida; no se escribe")
                _textos(res, "clave_invalida")
                return res
            if not enlace.escribir_credenciales_web(USUARIO_WEB, clave):
                _textos(res, "clave_no_quedo")
                return res
            res["clave_cambiada"] = True
            logger.info("configurar-modulo: contraseña web escrita y comprobada")
    finally:
        clave = None
        if hay_clave:
            enlace.stop()
    _textos(res, "ok")
    return res


def main(argv=None) -> int:
    """Punto de entrada del rol. Nunca lanza."""
    argv = list(argv or [])
    res = _resultado_base()
    ruta = _ruta_resultado(argv)
    idioma = "es"
    try:
        logging.getLogger("pymodbus").setLevel(logging.WARNING)
        try:
            args = _parse_args(argv)
        except (_ErrorArgumentos, ValueError) as e:
            logger.error("configurar-modulo: argumentos no válidos: %s", e)
            _textos(res, "argumentos", detalle=str(e))
            _escribir_resultado(ruta, res)
            return CODIGOS_SALIDA["argumentos"]
        ruta = args.resultado
        idioma = args.idioma
        clave = None
        hay_clave = args.clave_archivo is not None
        if hay_clave:
            clave = _leer_y_borrar_clave(args.clave_archivo)
        res = ejecutar(args, clave, hay_clave)
        clave = None
    except Exception as e:
        logger.exception("configurar-modulo falló")
        res = _resultado_base()
        _textos(res, "error", detalle=type(e).__name__)
    _escribir_resultado(ruta, res)
    nivel = logging.INFO if res["ok"] else logging.WARNING
    logger.log(nivel, "configurar-modulo: %s — %s", res["codigo"],
               res.get(f"texto_{idioma}", ""))
    return CODIGOS_SALIDA.get(res["codigo"], CODIGOS_SALIDA["error"])
