# installation/identidad.py
#
# Identidad que se MUESTRA del equipo (instalación por automatización). Puro:
# sin interfaz ni acceso a disco.
#
# Un equipo instalado por fabricación muestra su serie y su modelo internos
# (SNAANNNN y el modelo calculado). Uno instalado por automatización muestra
# como principal la serie y el modelo ORIGINALES del equipo (los que firmó el
# código) y, aparte, el serial Especifika (la serie interna SNAANNNN). Esto solo
# afecta a lo que se imprime o se ve: el manifiesto del respaldo (`otra_serie`),
# la bitácora y las claves internas siguen con la serie interna.
#
# Regla única: hay identidad original solo si AMBOS originales son texto no
# vacío. Cualquier otra cosa (None, vacío, un MagicMock, una sola de las dos)
# se muestra como siempre, con `serial_especifika` None.

from __future__ import annotations

_ROTULO_RESPALDO = {"es": "Serial Especifika", "en": "Especifika serial"}
CLAVE_ROTULO = "equipo.serial_especifika"


def _texto(valor) -> str | None:
    """El texto si es un str no vacío; si no, None (un MagicMock no cuenta)."""
    return valor if isinstance(valor, str) and valor.strip() else None


def identidad_visible(serie, modelo, serie_original=None, modelo_original=None) -> dict:
    """{"modelo", "serie", "serial_especifika"}. Con originales: modelo y serie
    son los originales y `serial_especifika` la serie interna recibida; sin
    ellos: `serie` y `modelo` tal cual (el mismo objeto) y `serial_especifika`
    None."""
    so, mo = _texto(serie_original), _texto(modelo_original)
    if so is not None and mo is not None:
        interna = serie if isinstance(serie, str) and serie else None
        return {"modelo": mo, "serie": so, "serial_especifika": interna}
    return {"modelo": modelo, "serie": serie, "serial_especifika": None}


def originales_de_perfil(perfil) -> tuple:
    """(serial_original, modelo_original) del perfil; None donde no haya."""
    if perfil is None:
        return None, None
    return (getattr(perfil, "serial_original", None),
            getattr(perfil, "modelo_original", None))


def identidad_de_perfil(perfil) -> dict:
    """Identidad visible del perfil vigente. Sin perfil: serie y modelo None."""
    if perfil is None:
        return identidad_visible(None, None)
    so, mo = originales_de_perfil(perfil)
    return identidad_visible(getattr(perfil, "serial_number", None),
                             getattr(perfil, "model_id", None), so, mo)


def _campo(fila, clave):
    try:
        return fila[clave]
    except (KeyError, IndexError, TypeError):
        return None


def identidad_de_ciclo(ciclo) -> dict:
    """Identidad visible de un ciclo guardado (fila de `ciclos` o su dict).
    Un ciclo histórico, sin las columnas, o de fabricación (NULL), se muestra
    como siempre."""
    return identidad_visible(_campo(ciclo, "serie"), _campo(ciclo, "modelo"),
                             _campo(ciclo, "serie_original"), _campo(ciclo, "modelo_original"))


def meta_con_originales(meta: dict, perfil) -> dict:
    """Copia de `meta` ({"serie", "modelo"}, serie interna) con `serie_original`
    y `modelo_original` del perfil cuando los hay. Sin originales devuelve el
    mismo `meta` sin cambios."""
    so, mo = originales_de_perfil(perfil)
    if _texto(so) is None or _texto(mo) is None:
        return meta
    return {**meta, "serie_original": so, "modelo_original": mo}


def identidad_de_meta(meta) -> dict:
    """Identidad visible de un `meta` con `serie`/`modelo` y, opcionales,
    `serie_original`/`modelo_original`."""
    meta = meta if isinstance(meta, dict) else {}
    return identidad_visible(meta.get("serie", ""), meta.get("modelo", ""),
                             meta.get("serie_original"), meta.get("modelo_original"))


def rotulo_serial_especifika(idioma: str | None = None) -> str:
    """«Serial Especifika» / «Especifika serial» (clave `equipo.serial_especifika`;
    texto propio si el catálogo aún no la trae)."""
    try:
        from autoclave import i18n
        if i18n.existe(CLAVE_ROTULO, idioma):
            return i18n.t(CLAVE_ROTULO, idioma)
    except Exception:
        pass
    return _ROTULO_RESPALDO["en" if idioma == "en" else "es"]


def partir(texto, ancho: int) -> list[str]:
    """`texto` en trozos de `ancho` columnas (sin perder caracteres)."""
    texto = "" if texto is None else str(texto)
    if ancho <= 0 or not texto:
        return [texto]
    return [texto[i:i + ancho] for i in range(0, len(texto), ancho)]
