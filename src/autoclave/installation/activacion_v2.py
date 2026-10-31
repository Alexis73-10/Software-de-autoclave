# src/autoclave/installation/activacion_v2.py
#
# Instalación por automatización: verificador de los códigos de instalación v2
# (INS/REI de fabricación e INSA/REIA de automatización, formato ESPK2 2.1.0) y
# sello del perfil. Convive con el v1 (activation.py), que no se toca.
#
# Solo se verifica el código: no se guardan K_e ni lic/P/G/ventana/orig (decisión
# de Cristian). La lógica de lectura y la normalización de originales están
# copiadas tal cual de generador_especifika/src/generador/formato/codigos.py
# (normalizar_*_original, huella_originales, _etiqueta_instalacion, leer_instalacion)
# y base.py (Luhn y Base32); si el generador cambia, mandan el generador y sus
# vectores (tests/vectores/vectores_formato_v2.json).
#
# K_t (transporte, común a todos los equipos) se carga perezosamente y por
# separado de los secretos v1. Sin K_t todo código de 48 caracteres falla cerrado
# (`sin_transporte`); el v1 y la fabricación con v1 siguen igual.
import hashlib
import hmac
import logging
import re
import sys
import threading
from dataclasses import dataclass
from datetime import date
from enum import Enum

from autoclave.installation import activation
from autoclave.installation import secretos as _secretos

logger = logging.getLogger(__name__)

LONGITUD_V1 = 12
LONGITUD_V2 = 48

# --- Base32 y Luhn (copia de generador/formato/base.py) ---------------------------------------------

_ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_VALOR = {caracter: indice for indice, caracter in enumerate(_ALFABETO)}
_PATRON_SERIAL = re.compile(r"SN[0-9]{6}")


def _en_alfabeto(texto: str) -> bool:
    return bool(texto) and all(c in _VALOR for c in texto)


def _suma_luhn(texto: str, factor: int) -> int:
    suma = 0
    for caracter in reversed(texto):
        producto = factor * _VALOR[caracter]
        suma += producto // 32 + producto % 32
        factor = 3 - factor
    return suma


def _control_valido(codigo: str) -> bool:
    return len(codigo) >= 2 and _en_alfabeto(codigo) and _suma_luhn(codigo, 1) % 32 == 0


def _de_base32(texto: str) -> int:
    valor = 0
    for caracter in texto:
        valor = (valor << 5) | _VALOR[caracter]
    return valor


def _validar_serial(serial: str) -> str:
    if not isinstance(serial, str):
        raise ValueError("el serial debe ser texto")
    canonico = serial.strip().upper()
    if not _PATRON_SERIAL.fullmatch(canonico):
        raise ValueError("el serial debe tener la forma SNAANNNN (SN y seis dígitos)")
    return canonico


# --- Formato de INS/REI/INSA/REIA (copia de generador/formato/codigos.py) ---------------------------

_EPOCA = date(2026, 1, 1)
_TIPOS = {"SOL": 0, "INS": 1, "REI": 2, "FIN": 3, "EMG": 4, "EXT": 5}
_NOMBRE_TIPO = {valor: nombre for nombre, valor in _TIPOS.items()}
_VERSION = 0
_BYTES_K_T = 32
_BYTES_K_E = 16
_BITS_FECHA = 14
_DIAS_VENTANA = 7
_PLAZO_MAXIMO = 365
_GRACIA_MAXIMA = 60
_ANCHOS_INSTALACION = (1, _BITS_FECHA, _BITS_FECHA, 9, 6, 2, 8 * _BYTES_K_E, 56)
_BYTES_ETIQUETA_INSTALACION = 7

SERIE_ORIGINAL_MAX = 40
MODELO_ORIGINAL_MAX = 80
_BLANCOS_ASCII = " \t\n\r\x0b\x0c"
_A_ESPACIO = str.maketrans({c: " " for c in _BLANCOS_ASCII})


class CodigoInvalido(Exception):
    """Código rechazado al leerlo (motivos: formato, digitacion, tipo, etiqueta, ventana, rango)."""

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(motivo)


class OriginalInvalido(ValueError):
    """Serie o modelo original que no cumple §4.2.1 tras normalizarlo (campo: serie o modelo)."""

    def __init__(self, campo: str) -> None:
        self.campo = campo
        super().__init__(f"{campo}_original")


def _ascii_sin_barra(texto: str) -> bool:
    return all(" " <= c <= "~" and c != "|" for c in texto)


def normalizar_serie_original(texto: str) -> str:
    """Quita todo blanco ASCII, exige ASCII imprimible sin ``|`` de 1 a 40 y pasa a mayúsculas."""
    if not isinstance(texto, str):
        raise OriginalInvalido("serie")
    serie = "".join(c for c in texto if c not in _BLANCOS_ASCII)
    if not 1 <= len(serie) <= SERIE_ORIGINAL_MAX or not _ascii_sin_barra(serie):
        raise OriginalInvalido("serie")
    return serie.upper()


def normalizar_modelo_original(texto: str) -> str:
    """Recorta extremos, reduce rachas de blancos a un espacio, ASCII imprimible sin ``|`` de 1 a 80, mayúsculas."""
    if not isinstance(texto, str):
        raise OriginalInvalido("modelo")
    modelo = " ".join(parte for parte in texto.translate(_A_ESPACIO).split(" ") if parte)
    if not 1 <= len(modelo) <= MODELO_ORIGINAL_MAX or not _ascii_sin_barra(modelo):
        raise OriginalInvalido("modelo")
    return modelo.upper()


def normalizar_originales(serie: str, modelo: str) -> tuple[str, str]:
    """(serie_n, modelo_n); primero valida la serie."""
    return normalizar_serie_original(serie), normalizar_modelo_original(modelo)


def huella_originales(serie: str, modelo: str) -> str:
    """h_orig: hex de SHA-256("ESPK2|ORIG|" + serie_n + "|" + modelo_n)."""
    serie_n, modelo_n = normalizar_originales(serie, modelo)
    return hashlib.sha256(f"ESPK2|ORIG|{serie_n}|{modelo_n}".encode("ascii")).hexdigest()


@dataclass(frozen=True)
class _DatosInstalacion:
    tipo: str
    originales: tuple[str, str] | None


def _hmac(clave: bytes, mensaje: bytes) -> bytes:
    return hmac.new(clave, mensaje, hashlib.sha256).digest()


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=True))


def _partir(valor: int, anchos: tuple[int, ...]) -> list[int]:
    campos = []
    for ancho in reversed(anchos):
        campos.append(valor & ((1 << ancho) - 1))
        valor >>= ancho
    return campos[::-1]


def _desarmar(canonico: str, admitidos: tuple[str, ...], longitud: int) -> tuple[str, int]:
    """Orden de §4.2 y §5: formato (alfabeto y longitud), control, cabecera (versión y tipo)."""
    if not _en_alfabeto(canonico):
        raise CodigoInvalido("formato")
    cabecera = _de_base32(canonico[0])
    version, tipo = cabecera >> 3, _NOMBRE_TIPO.get(cabecera & 7)
    if len(canonico) != longitud:
        raise CodigoInvalido("formato")
    if not _control_valido(canonico):
        raise CodigoInvalido("digitacion")
    if version != _VERSION:
        raise CodigoInvalido("formato")
    if tipo not in admitidos:
        raise CodigoInvalido("tipo")
    return tipo, _de_base32(canonico[1:-1])


def _etiqueta_instalacion(k_t: bytes, tipo: str, serial: str, campos: tuple, k_e: bytes,
                          h_orig: str | None = None) -> bytes:
    texto = "|".join(str(campo) for campo in campos)
    prefijo = f"{tipo}|{serial}" if h_orig is None else f"{tipo}A|{serial}|{h_orig}"
    mensaje = f"ESPK2|{prefijo}|{texto}|".encode("ascii") + k_e
    return _hmac(k_t, mensaje)[:_BYTES_ETIQUETA_INSTALACION]


def _flujo_instalacion(k_t: bytes, etiqueta: bytes) -> bytes:
    return _hmac(k_t, b"ESPK2|KS|" + etiqueta)[:_BYTES_K_E]


def _regla_instalacion(tipo: str, permanente: bool, ventana: int, orig: int, P: int, G: int,
                       emerg: int) -> str | None:
    if permanente:
        if P != 0 or G != 0:
            return "en licencia permanente P y G deben ser 0"
    else:
        if not 1 <= P <= _PLAZO_MAXIMO:
            return f"P debe estar entre 1 y {_PLAZO_MAXIMO}"
        if not 0 <= G <= _GRACIA_MAXIMA:
            return f"G debe estar entre 0 y {_GRACIA_MAXIMA}"
    if tipo == "INS":
        if orig != 0 or emerg != 0:
            return "en una instalación orig y emerg deben ser 0"
    elif orig > ventana:
        return "la fecha original no puede ser posterior a la ventana"
    return None


def _leer_instalacion(k_t: bytes, serial: str, canonico: str, hoy: date,
                      originales: tuple[str, str] | None) -> _DatosInstalacion:
    """Verifica un INS/REI (originales None) o INSA/REIA (con originales) ya normalizado (§4.2, §4.2.1).

    El resultado no conserva K_e ni los datos de la licencia: solo el tipo y los originales."""
    originales_n = None if originales is None else normalizar_originales(*originales)
    h_orig = None if originales_n is None else huella_originales(*originales_n)
    tipo, cuerpo = _desarmar(canonico, ("INS", "REI"), LONGITUD_V2)
    *campos, k_e_cifrado, etiqueta = _partir(cuerpo, _ANCHOS_INSTALACION)
    lic, dia_ventana, dia_orig, P, G, emerg = campos
    etiqueta_leida = etiqueta.to_bytes(_BYTES_ETIQUETA_INSTALACION, "big")
    k_e = _xor(k_e_cifrado.to_bytes(_BYTES_K_E, "big"), _flujo_instalacion(k_t, etiqueta_leida))
    esperada = _etiqueta_instalacion(k_t, tipo, serial, tuple(campos), k_e, h_orig)
    if not hmac.compare_digest(esperada, etiqueta_leida):
        raise CodigoInvalido("etiqueta")
    if not dia_ventana <= (hoy - _EPOCA).days < dia_ventana + _DIAS_VENTANA:
        raise CodigoInvalido("ventana")
    if _regla_instalacion(tipo, lic == 1, dia_ventana, dia_orig, P, G, emerg):
        raise CodigoInvalido("rango")
    return _DatosInstalacion(tipo=tipo, originales=originales_n)


# --- Transporte K_t (caché perezosa propia; no comparte estado con activation._cargar) ---------------

_lock = threading.Lock()
_k_t: bytes | None = None
_intentado = False
_ausencia_fijada = False    # solo pruebas: configurar_transporte(b"") fija «sin K_t»
_advertido = False


class TransporteNoDisponible(RuntimeError):
    """No hay K_t: no se puede sellar ni verificar nada del formato v2."""


def configurar_transporte(k_t: bytes | None) -> None:
    """SOLO PRUEBAS. Con 32 bytes fija K_t; con ``b""`` fija la ausencia de K_t (sin consultar
    disco); con None olvida lo cargado (la próxima consulta vuelve a buscar en recurso y archivo)."""
    global _k_t, _intentado, _advertido, _ausencia_fijada
    with _lock:
        if k_t is None:
            _k_t, _intentado, _advertido, _ausencia_fijada = None, False, False, False
            return
        if k_t == b"":
            _k_t, _intentado, _ausencia_fijada = None, True, True
            return
        if not isinstance(k_t, bytes) or len(k_t) != _BYTES_K_T:
            raise ValueError(f"configurar_transporte: k_t debe tener {_BYTES_K_T} bytes")
        _k_t, _intentado, _ausencia_fijada = k_t, True, False


def _cargar_transporte() -> bytes | None:
    if hasattr(sys, "_MEIPASS"):
        # En el compilado solo vale el recurso empaquetado (nada de rutas del usuario) y
        # nunca el K_t de prueba del formato (§7.1).
        from autoclave.utils.resources import resource_path
        try:
            k_t = _secretos.leer_transporte(resource_path(_secretos.RECURSO_TRANSPORTE))
        except _secretos.SecretosInvalidos:
            return None
        return None if _secretos.es_transporte_de_prueba(k_t) else k_t
    try:
        return _secretos.leer_transporte(_secretos.ruta_archivo_transporte())
    except _secretos.SecretosInvalidos:
        return None


def _obtener_transporte() -> bytes | None:
    global _k_t, _intentado, _advertido
    with _lock:
        # Solo se guarda el éxito: una lectura fallida (antivirus, disco) se reintenta
        # en la siguiente consulta en lugar de dejar el proceso sin K_t (revisión, M2).
        if _k_t is None and not _ausencia_fijada:
            _k_t, _intentado = _cargar_transporte(), True
        if _k_t is None and not _advertido:
            _advertido = True
            logger.warning("compilación sin transporte de activación v2: se rechaza "
                           "todo código de instalación de 48 caracteres")
        return _k_t


def transporte_disponible() -> bool:
    return _obtener_transporte() is not None


# --- Contratos --------------------------------------------------------------------------------------


class Modo(str, Enum):
    FABRICACION = "fabricacion"
    AUTOMATIZACION = "automatizacion"


@dataclass(frozen=True)
class ResultadoCodigo:
    """Resultado de verificar un código de instalación.

    ``motivo`` es None si ok; si no, uno de: formato, digitacion, tipo, etiqueta, ventana, rango,
    serial_formato, sin_transporte, serie_original, modelo_original, v1_en_automatizacion, v1_invalido.
    ``originales`` son los normalizados (solo en automatización con v2)."""

    ok: bool
    motivo: str | None = None
    formato: str | None = None
    tipo: str | None = None
    originales: tuple[str, str] | None = None


def _no(motivo: str, formato: str | None = None) -> ResultadoCodigo:
    return ResultadoCodigo(ok=False, motivo=motivo, formato=formato)


def verificar_codigo_instalacion(
    serial: str,
    codigo: str,
    modo: Modo,
    serie_original: str | None = None,
    modelo_original: str | None = None,
    *,
    hoy: date | None = None,
    k_t: bytes | None = None,
    validar_v1=activation.validate_installation_code,
) -> ResultadoCodigo:
    """Despacha por longitud exacta tras normalizar: 12 = v1, 48 = v2, otra = formato.

    v1 solo en fabricación (llama a ``validar_v1(serial, codigo, hoy)``); en automatización da
    ``v1_en_automatizacion`` sin llamarlo. v2 en fabricación valida INS/REI sin originales (los
    ignora); en automatización valida INSA/REIA atado a los originales normalizados. Falla cerrado
    sin K_t (``sin_transporte``), solo para v2.
    """
    modo = Modo(modo)
    canonico = activation.normalizar_codigo(codigo)
    if not _en_alfabeto(canonico):
        return _no("formato")
    if len(canonico) == LONGITUD_V1:
        if modo is Modo.AUTOMATIZACION:
            return _no("v1_en_automatizacion", "v1")
        if validar_v1(serial, codigo, hoy):
            return ResultadoCodigo(ok=True, formato="v1")
        return _no("v1_invalido", "v1")
    if len(canonico) != LONGITUD_V2:
        return _no("formato")
    try:
        serial_c = _validar_serial(serial)
    except ValueError:
        return _no("serial_formato", "v2")
    clave = k_t if k_t is not None else _obtener_transporte()
    if not clave:
        logger.error("código v2 rechazado: la compilación no tiene transporte de activación v2")
        return _no("sin_transporte", "v2")
    originales = None
    if modo is Modo.AUTOMATIZACION:
        try:
            originales = (normalizar_serie_original(serie_original),
                          normalizar_modelo_original(modelo_original))
        except OriginalInvalido as e:
            return _no(f"{e.campo}_original", "v2")
    try:
        datos = _leer_instalacion(clave, serial_c, canonico, hoy or date.today(), originales)
    except CodigoInvalido as e:
        return _no(e.motivo, "v2")
    return ResultadoCodigo(ok=True, formato="v2", tipo=datos.tipo, originales=datos.originales)


# --- Sello de identidad del perfil ------------------------------------------------------------------


def _k_perfil(k_t: bytes) -> bytes:
    return _hmac(k_t, b"ESPK2|AUTOCLAVE|PERFIL")


def _sello(k_t: bytes, tipo: str, serial: str, serie_n: str, modelo_n: str) -> str:
    mensaje = f"1|{tipo}|{serial}|{serie_n}|{modelo_n}".encode("utf-8")
    return _hmac(_k_perfil(k_t), mensaje).hex()


def sellar_identidad(tipo: str, serial: str, serie_n: str, modelo_n: str,
                     k_t: bytes | None = None) -> str:
    """sello_identidad = HMAC(K_p, "1|{tipo}|{serial}|{serie_n}|{modelo_n}") en hex (64).

    Raises:
        TransporteNoDisponible: sin K_t.
    """
    clave = k_t if k_t is not None else _obtener_transporte()
    if not clave:
        raise TransporteNoDisponible("sin transporte de activación v2")
    return _sello(clave, tipo, serial, serie_n, modelo_n)


def verificar_sello_identidad(data: dict, k_t: bytes | None = None) -> bool:
    """True si ``data`` (perfil como diccionario) trae un ``sello_identidad`` que coincide. False sin
    K_t, con campos faltantes o no textuales, o ante cualquier alteración."""
    if not isinstance(data, dict):
        return False
    clave = k_t if k_t is not None else _obtener_transporte()
    if not clave:
        return False
    campos = [data.get(n) for n in ("tipo_instalacion", "serial_number", "serial_original",
                                    "modelo_original", "sello_identidad")]
    if not all(isinstance(c, str) and c for c in campos):
        return False
    tipo, serial, serie_n, modelo_n, sello = campos
    try:
        esperado = _sello(clave, tipo, serial, serie_n, modelo_n)
    except UnicodeError:
        return False
    return hmac.compare_digest(esperado.encode("ascii"), sello.encode("utf-8", "replace"))
