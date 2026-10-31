# src/autoclave/installation/secretos.py
#
# LIC-01 (licencia L0): los secretos de activación ya no están en el código.
# Viven en un archivo fuera del repositorio:
#     %USERPROFILE%\Documents\especifika_secretos\activacion.json
# (o la ruta completa de la variable de entorno ESPECIFIKA_SECRETOS), con el
# formato {"version": 1, "instalacion": "<64 hex>", "fabrica": "<64 hex>"}.
# Lo crea tools/secretos/generar_secretos.py. La compilación del autoclave lo
# empaqueta como config/activacion_secretos.json (Autoclave.spec y
# AutoclaveBackend.spec); el generador lo lee del PC donde corre.
#
# Nunca se imprime ni se registra un valor de secreto: solo la ruta y la huella
# corta (8 hex de SHA-256), para comparar el generador con la compilación.

import hashlib
import json
import os
from pathlib import Path

VARIABLE_ENTORNO = "ESPECIFIKA_SECRETOS"
VERSION = 1
CLAVES = ("instalacion", "fabrica")
# nombre del recurso dentro del ejecutable (fuera de autoclave/config a
# propósito: esa carpeta se siembra en disco escribible, utils/resources.py)
RECURSO_EMPAQUETADO = "config/activacion_secretos.json"


class SecretosInvalidos(Exception):
    """El archivo de secretos no existe o no tiene el formato esperado."""


def ruta_archivo_secretos() -> Path:
    """Ruta del archivo de secretos de desarrollo/compilación (§1.1)."""
    propia = os.environ.get(VARIABLE_ENTORNO, "").strip()
    if propia:
        return Path(propia)
    base = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(base) / "Documents" / "especifika_secretos" / "activacion.json"


def decodificar(datos: dict) -> dict[str, bytes]:
    """{"instalacion": bytes, "fabrica": bytes} o SecretosInvalidos. El
    mensaje de error nunca incluye el valor."""
    if not isinstance(datos, dict) or datos.get("version") != VERSION:
        raise SecretosInvalidos(f"versión distinta de {VERSION}")
    secretos = {}
    for clave in CLAVES:
        valor = datos.get(clave)
        if not isinstance(valor, str) or len(valor) != 64:
            raise SecretosInvalidos(f"'{clave}' no tiene 64 caracteres hexadecimales")
        try:
            secretos[clave] = bytes.fromhex(valor)
        except ValueError:
            raise SecretosInvalidos(f"'{clave}' no es hexadecimal") from None
    if secretos["instalacion"] == secretos["fabrica"]:
        raise SecretosInvalidos("los dos secretos son iguales")
    return secretos


def leer_archivo(ruta: Path | str) -> dict[str, bytes]:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise SecretosInvalidos(f"no existe {ruta}")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SecretosInvalidos(f"no se pudo leer {ruta} como JSON") from None
    return decodificar(datos)


def huella(secreto: bytes) -> str:
    """Primeros 8 hex de SHA-256: identifica el secreto sin revelarlo."""
    return hashlib.sha256(secreto).hexdigest()[:8]


def entrada_compilacion() -> tuple[str, str, str]:
    """Entrada TOC de PyInstaller (destino, origen, 'DATA') para empaquetar el
    archivo de secretos. Sin archivo válido detiene la compilación: no debe
    salir un ejecutable que rechace todos los códigos sin que nadie lo note."""
    ruta = ruta_archivo_secretos()
    try:
        secretos = leer_archivo(ruta)
    except SecretosInvalidos as e:
        raise SystemExit(f"LIC-01: compilación sin secretos de activación ({e}). "
                         f"Ejecute tools\\secretos\\generar_secretos.py o defina "
                         f"{VARIABLE_ENTORNO}.") from None
    print(f"LIC-01: secretos de activación de {ruta} "
          f"(huella instalación {huella(secretos['instalacion'])}, "
          f"fábrica {huella(secretos['fabrica'])})")
    return (RECURSO_EMPAQUETADO, str(ruta), "DATA")


# --- Transporte K_t del formato de códigos v2 (instalación por automatización) ---
# Archivo aparte del v1 (que no cambia): {"version": 2, "transporte": "<64 hex>",
# "huella_maestro": "<8 hex>"}, lo exporta el generador. Desarrollo:
#     %USERPROFILE%\Documents\especifika_secretos\activacion_v2.json
# o la ruta completa de la variable ESPECIFIKA_TRANSPORTE. Se empaqueta como
# config/activacion_transporte.json (fuera de autoclave/config, como el v1).

VARIABLE_ENTORNO_TRANSPORTE = "ESPECIFIKA_TRANSPORTE"
VERSION_TRANSPORTE = 2
RECURSO_TRANSPORTE = "config/activacion_transporte.json"
# K_t ficticio de prueba (§7.1 del formato v2): público; jamás debe viajar en una entrega.
K_T_DE_PRUEBA_HEX = "6578a9994682225f37861fe063d7f5edd44e022a91f884acc21d014ef3889857"


def ruta_archivo_transporte() -> Path:
    """Ruta del archivo de K_t de desarrollo/compilación."""
    propia = os.environ.get(VARIABLE_ENTORNO_TRANSPORTE, "").strip()
    if propia:
        return Path(propia)
    base = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(base) / "Documents" / "especifika_secretos" / "activacion_v2.json"


def leer_transporte(ruta: Path | str) -> bytes:
    """K_t (32 bytes) del archivo del generador, o SecretosInvalidos. El mensaje
    de error nunca incluye el valor."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise SecretosInvalidos(f"no existe {ruta}")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SecretosInvalidos(f"no se pudo leer {ruta} como JSON") from None
    if not isinstance(datos, dict) or datos.get("version") != VERSION_TRANSPORTE:
        raise SecretosInvalidos(f"versión distinta de {VERSION_TRANSPORTE}")
    valor = datos.get("transporte")
    if not isinstance(valor, str) or len(valor) != 64:
        raise SecretosInvalidos("'transporte' no tiene 64 caracteres hexadecimales")
    try:
        return bytes.fromhex(valor)
    except ValueError:
        raise SecretosInvalidos("'transporte' no es hexadecimal") from None


def es_transporte_de_prueba(k_t: bytes) -> bool:
    return k_t == bytes.fromhex(K_T_DE_PRUEBA_HEX)


def entrada_compilacion_transporte() -> tuple[str, str, str]:
    """Entrada TOC de PyInstaller para empaquetar el K_t. Sin archivo válido, o
    con el K_t ficticio de prueba (públicos los vectores), detiene la compilación."""
    ruta = ruta_archivo_transporte()
    try:
        k_t = leer_transporte(ruta)
    except SecretosInvalidos as e:
        raise SystemExit(f"LIC-01: compilación sin transporte de activación v2 ({e}). "
                         f"Exporte el transporte desde el generador a {ruta} o defina "
                         f"{VARIABLE_ENTORNO_TRANSPORTE}.") from None
    if es_transporte_de_prueba(k_t):
        raise SystemExit("LIC-01: el transporte de activación v2 es el K_t de prueba "
                         "(§7.1 del formato); no puede ir en una entrega.")
    print(f"LIC-01: transporte de activación v2 de {ruta} (huella {huella(k_t)})")
    return (RECURSO_TRANSPORTE, str(ruta), "DATA")
