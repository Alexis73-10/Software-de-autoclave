# core/runtime/motivos_fase.py
#
# X9 (tanda 9, D9-13.4; planeacion_i18n.md §3.10, D-25): motivos de fallo de
# las fases del ciclo con CLAVE y PARÁMETROS.
#
# Igual que `motivos.Motivo` (puertas), `MotivoFase` es un `str` con el texto
# en español de siempre que además lleva `codigo` y `valores`. Las fases lo
# siguen guardando en estado.motivo_fallo y escribiendo en el log; CicloState
# pasa el código y los valores a la alarma CIC-0x (y de ahí a
# ciclos.valores_fallo), y la alarma, el Historial, el PDF y la reimpresión
# arman el texto en el idioma y las unidades vigentes al presentarlo.
#
# Textos: i18n/<idioma>.json → motivos_fase.<codigo>, placeholders "{nombre}".
# Convención de valores (por prefijo del nombre):
#   temp*   temperatura absoluta en °C   → módulo de unidades
#   pres*   presión absoluta en kPa      → módulo de unidades
#   clave_<nombre>  clave del catálogo; se inserta su texto como {<nombre>}
#   el resto se inserta como texto (los números ya vienen con su formato).
# Nunca lanza: ante cualquier error se usa el texto en español.

import logging
import math
from types import MappingProxyType

from autoclave import i18n
from autoclave.core.runtime import unidades as u

logger = logging.getLogger(__name__)

PREFIJO = "motivos_fase."
# Claves con que viajan en los valores de la alarma CIC-0x (y en
# ciclos.valores_fallo): el código y cada valor con prefijo propio, para no
# chocar con los parámetros de la alarma (`motivo`, `origen`).
CLAVE_CODIGO = "motivo_codigo"
PREFIJO_VALOR = "motivo_v_"

# Códigos usados por las fases. La prueba de X9 verifica que cada uno tenga
# texto en es y en, con los mismos placeholders.
CODIGOS = (
    "cal_tiempo_limite", "cal_tiempo_limite_sostenimiento", "cal_no_sostuvo",
    "est_comunicacion", "est_temp_alta", "est_temp_baja", "est_pres_alta", "est_pres_baja",
    "est_timeout_f0",
    # E12 (tanda 12): C-03 (saturación, solo sólidos) y C-13.4 (Referencia)
    "est_aire", "est_sobrecalentado", "est_excursion_referencia",
    "desc_tiempo_limite",
    "sec_vacio_perdido", "sec_sin_vacio", "sec_termino_sin_vacio",
    "sec_modo3_vacio_bajo", "sec_modo3_aire_alto",
)


class MotivoFase(str):
    """Texto en español del motivo, con su código y sus parámetros."""

    codigo: str
    valores: MappingProxyType

    def __new__(cls, codigo: str, texto: str, **valores):
        obj = super().__new__(cls, texto)
        obj.codigo = codigo
        obj.valores = MappingProxyType(dict(valores))
        return obj

    def __reduce__(self):              # copy/deepcopy/pickle
        return (_crear, (self.codigo, str(self), dict(self.valores)))


def _crear(codigo, texto, valores):
    return MotivoFase(codigo, texto, **valores)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _presentar(nombre: str, v, idioma: str, temperatura: str, presion: str, p_atm) -> str:
    if nombre.startswith("temp"):
        return u.formatear_temp(v, temperatura) if _num(v) else u.SIN_DATO
    if nombre.startswith("pres"):
        return u.formatear_pres(v, presion, p_atm) if _num(v) else u.SIN_DATO
    return "" if v is None else str(v)


def _armar(codigo: str, valores: dict, idioma: str, temperatura="C", presion="kPa",
           p_atm=None) -> str:
    params = {}
    for k, v in (valores or {}).items():
        if k.startswith("clave_"):
            params[k[len("clave_"):]] = i18n.t(str(v), idioma) if v else ""
        else:
            params[k] = _presentar(k, v, idioma, temperatura, presion, p_atm)
    return i18n.traducir(PREFIJO + codigo, idioma, params)


def motivo(codigo: str, **valores) -> MotivoFase:
    """El motivo, con su texto en español (°C y kPa) para el log y la base."""
    try:
        texto = _armar(codigo, valores, i18n.IDIOMA_BASE)
    except Exception:
        logger.exception("motivo de fase %s: no se pudo armar el texto", codigo)
        texto = codigo
    return MotivoFase(codigo, texto, **valores)


def codigo_de(m) -> str | None:
    c = getattr(m, "codigo", None)
    return c if isinstance(c, str) and c in CODIGOS else None


def a_valores(m) -> dict:
    """Valores para la alarma CIC-0x: {} si `m` no es un MotivoFase."""
    codigo = codigo_de(m)
    if not codigo:
        return {}
    salida = {CLAVE_CODIGO: codigo}
    for k, v in (getattr(m, "valores", None) or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            v = None
        elif not (isinstance(v, (int, float, str, bool)) or v is None):
            v = str(v)
        salida[PREFIJO_VALOR + k] = v
    return salida


def texto_desde_valores(valores: dict, idioma: str, temperatura="C", presion="kPa",
                        p_atm=None) -> str | None:
    """Texto del motivo guardado en los valores de una alarma, en `idioma` y
    las unidades dadas; None si los valores no traen un motivo de fase."""
    try:
        codigo = (valores or {}).get(CLAVE_CODIGO)
        if not isinstance(codigo, str) or codigo not in CODIGOS:
            return None
        if not i18n.existe(PREFIJO + codigo, idioma):
            return None
        propios = {k[len(PREFIJO_VALOR):]: v for k, v in valores.items()
                   if isinstance(k, str) and k.startswith(PREFIJO_VALOR)}
        return _armar(codigo, propios, idioma, temperatura, presion, p_atm)
    except Exception:
        logger.debug("motivo de fase: no se pudo armar en %s", idioma, exc_info=True)
        return None
