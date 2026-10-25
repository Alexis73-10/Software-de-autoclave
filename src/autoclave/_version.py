# src/autoclave/_version.py
"""Fuente única de la versión del autoclave (VER-01, etapa VER).

`VERSION_SEMVER` es la última entrega (`1.0.0-alpha.N`, D-VER-1) y es lo que se
muestra; `__version__` es la misma en PEP 440 (`1.0.0a1`), la que lee
`pyproject.toml` (`[tool.setuptools.dynamic]`). Las dos líneas de asignación las
reescribe solo `tools/entrega/compilar_entrega.py` en el commit de la entrega;
nadie más escribe la versión a mano. `alpha.0` = todavía no hay entregas.

La identificación de la compilación (commit, etiqueta, fecha, árbol sucio) está
en `_build_info.py`, que genera cada `.spec` al compilar (VER-04, no versionado).
"""

import re
import sys

__version__ = "1.0.0a1"
VERSION_SEMVER = "1.0.0-alpha.1"

ETAPAS = ("alpha", "beta", "rc")
_PEP440_ETAPA = {"alpha": "a", "beta": "b", "rc": "rc"}
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")
_PEP440 = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")


def partes_semver(v: str) -> tuple[int, int, int, str | None, int | None]:
    """'1.0.0-alpha.3' -> (1, 0, 0, 'alpha', 3); '1.0.0' -> (1, 0, 0, None, None)."""
    m = _SEMVER.match(v or "")
    if not m:
        raise ValueError(f"Versión fuera del esquema 1.0.0-alpha.N: {v!r}")
    mayor, menor, parche, etapa, n = m.groups()
    return int(mayor), int(menor), int(parche), etapa, (int(n) if n is not None else None)


def semver_a_pep440(v: str) -> str:
    """'1.0.0-alpha.1' -> '1.0.0a1'."""
    mayor, menor, parche, etapa, n = partes_semver(v)
    base = f"{mayor}.{menor}.{parche}"
    return base if etapa is None else f"{base}{_PEP440_ETAPA[etapa]}{n}"


def pep440_a_semver(v: str) -> str:
    """'1.0.0a1' -> '1.0.0-alpha.1'."""
    m = _PEP440.match(v or "")
    if not m:
        raise ValueError(f"Versión PEP 440 fuera del esquema 1.0.0aN: {v!r}")
    mayor, menor, parche, etapa, n = m.groups()
    base = f"{mayor}.{menor}.{parche}"
    if etapa is None:
        return base
    nombre = {"a": "alpha", "b": "beta", "rc": "rc"}[etapa]
    return f"{base}-{nombre}.{int(n)}"


def siguiente_desarrollo(v: str) -> str:
    """Versión de una compilación de verificación posterior a la entrega `v`:
    '1.0.0-alpha.3' -> '1.0.0-alpha.4.dev' (precede a la entrega siguiente)."""
    mayor, menor, parche, etapa, n = partes_semver(v)
    if etapa is None:
        return f"{mayor}.{menor}.{parche + 1}-dev"
    return f"{mayor}.{menor}.{parche}-{etapa}.{n + 1}.dev"


_LEER = object()   # por defecto: leer _build_info.py


def _info_compilacion() -> dict | None:
    """Datos de `_build_info.py` solo en el ejecutable compilado: desde fuente un
    `_build_info.py` que haya quedado de una compilación anterior no cuenta."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        from autoclave import _build_info
    except ImportError:
        return None
    return {"commit": getattr(_build_info, "COMMIT", None),
            "etiqueta": getattr(_build_info, "ETIQUETA", None),
            "fecha_utc": getattr(_build_info, "FECHA_UTC", None),
            "sucio": bool(getattr(_build_info, "SUCIO", True))}


def _es_entrega(info: dict, semver: str) -> bool:
    return info.get("etiqueta") == f"v{semver}" and not info.get("sucio") and bool(info.get("commit"))


def version_mostrada(info=_LEER, semver: str = VERSION_SEMVER) -> str:
    """Lo que se muestra (VER-04):
    - entrega (commit con la etiqueta `v<semver>`, árbol limpio): `1.0.0-alpha.N`;
    - compilación de verificación: `1.0.0-alpha.(N+1).dev+g<hash>` (`.sucio` si
      el árbol tenía cambios): nunca se confunde con una entrega;
    - desde fuente: `1.0.0-alpha.N+fuente`."""
    if info is _LEER:
        info = _info_compilacion()
    if info is None:
        return f"{semver}+fuente"
    if _es_entrega(info, semver):
        return semver
    commit = info.get("commit") or "desconocido"
    sucio = ".sucio" if info.get("sucio") else ""
    return f"{siguiente_desarrollo(semver)}+g{commit}{sucio}"


def version_completa(info=_LEER, semver: str = VERSION_SEMVER) -> str:
    """Versión con el commit (VER-05): la de entrega agrega `(<hash>)`; las demás
    ya lo llevan (o no lo tienen, desde fuente)."""
    if info is _LEER:
        info = _info_compilacion()
    mostrada = version_mostrada(info, semver)
    if info is not None and _es_entrega(info, semver):
        return f"{mostrada} ({info['commit']})"
    return mostrada
