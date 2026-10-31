"""Tanda 15 (ORG-12): equivalencia de la API tras partir ``backend/server.py``.

Compara las rutas de ``autoclave.backend.server:app`` y su OpenAPI contra la
línea base tomada sobre ``dev`` antes de mover nada
(``docs/informes/tanda15/base/rutas.json`` y ``openapi.json``):

- mismo conjunto de rutas con los mismos métodos, ``name``, dependencias
  (recorridas recursivamente), ``status_code`` y ``response_model``;
- para cada par de rutas con un método en común cuyos paths pueden coincidir
  con la misma URL (alguno con parámetro), el mismo orden relativo;
- OpenAPI idéntico comparado con claves ordenadas;
- ninguna ruta pierde una dependencia.

La misma función ``huella_rutas`` generó la línea base.
"""
import json
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parents[1] / "docs" / "informes" / "tanda15" / "base"


def _nombre(obj) -> str | None:
    if obj is None:
        return None
    return getattr(obj, "__name__", None) or repr(obj)


def _simple(v):
    if isinstance(v, (frozenset, set)):
        return sorted(v)
    if isinstance(v, tuple):
        return [_simple(x) for x in v]
    return v


def _nombre_dependencia(call) -> str:
    """Nombre calificado más las variables capturadas simples (p. ej. los roles
    de ``requiere_rol``), para que un cambio de rol no pase inadvertido."""
    nombre = getattr(call, "__qualname__", None) or _nombre(call)
    codigo = getattr(call, "__code__", None)
    celdas = getattr(call, "__closure__", None) or ()
    if codigo is not None and celdas:
        capturas = []
        for var, celda in zip(codigo.co_freevars, celdas):
            try:
                v = celda.cell_contents
            except ValueError:
                continue
            if isinstance(v, (str, int, float, bool, tuple, frozenset, set)) or v is None:
                capturas.append(f"{var}={_simple(v)!r}")
        if capturas:
            nombre += "(" + ", ".join(capturas) + ")"
    return nombre


def _dependencias(dependant) -> list[str]:
    nombres: list[str] = []
    for sub in getattr(dependant, "dependencies", []) or []:
        nombres.append(_nombre_dependencia(sub.call))
        nombres.extend(_dependencias(sub))
    return nombres


def huella_rutas(app) -> list[dict]:
    huella = []
    for ruta in app.routes:
        dependant = getattr(ruta, "dependant", None)
        huella.append({
            "path": getattr(ruta, "path", None),
            "methods": sorted(getattr(ruta, "methods", None) or []),
            "name": getattr(ruta, "name", None),
            "dependencias": _dependencias(dependant) if dependant is not None else [],
            "status_code": getattr(ruta, "status_code", None),
            "response_model": _nombre(getattr(ruta, "response_model", None)),
        })
    return huella


def openapi_ordenado(app) -> str:
    return json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False, indent=1)


def _segmentos(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/")]


def _es_param(seg: str) -> bool:
    return seg.startswith("{") and seg.endswith("}")


def _pueden_coincidir(a: str, b: str) -> bool:
    """True si alguna URL concreta puede coincidir con los dos paths."""
    sa, sb = _segmentos(a), _segmentos(b)
    if any(s.endswith(":path}") for s in sa + sb):
        # convertidor ``path``: compara solo el prefijo anterior
        n = min(len(sa), len(sb))
        sa, sb = sa[:n], sb[:n]
    elif len(sa) != len(sb):
        return False
    return all(x == y or _es_param(x) or _es_param(y) for x, y in zip(sa, sb))


def _clave(r: dict) -> tuple:
    return (r["path"], tuple(r["methods"]), r["name"])


@pytest.fixture(scope="module")
def app():
    from autoclave.backend.server import app as aplicacion
    return aplicacion


@pytest.fixture(scope="module")
def base_rutas():
    return json.loads((_BASE / "rutas.json").read_text(encoding="utf-8"))


def test_mismo_conjunto_de_rutas(app, base_rutas):
    actual = huella_rutas(app)
    assert sorted(map(_clave, actual)) == sorted(map(_clave, base_rutas))
    por_clave = {_clave(r): r for r in actual}
    for r in base_rutas:
        assert por_clave[_clave(r)] == r, f"ruta distinta: {_clave(r)}"


def test_ninguna_ruta_pierde_dependencias(app, base_rutas):
    por_clave = {_clave(r): r for r in huella_rutas(app)}
    for r in base_rutas:
        assert set(r["dependencias"]) <= set(por_clave[_clave(r)]["dependencias"]), _clave(r)


def test_mismo_orden_relativo_de_rutas_solapadas(app, base_rutas):
    actual = [_clave(r) for r in huella_rutas(app)]
    posicion = {c: i for i, c in enumerate(actual)}
    base = [_clave(r) for r in base_rutas]
    for i, a in enumerate(base):
        for b in base[i + 1:]:
            if not set(a[1]) & set(b[1]):
                continue
            if not ("{" in a[0] or "{" in b[0]):
                continue
            if _pueden_coincidir(a[0], b[0]):
                assert posicion[a] < posicion[b], f"orden invertido: {a} / {b}"


def test_openapi_identico(app):
    # se comparan los JSON reserializados con claves ordenadas: no dependen de
    # los finales de línea con que git extraiga la línea base
    base = json.loads((_BASE / "openapi.json").read_text(encoding="utf-8"))
    actual = json.loads(openapi_ordenado(app))
    assert json.dumps(actual, sort_keys=True) == json.dumps(base, sort_keys=True)


def test_detector_de_solapes():
    """El chequeo de orden depende de `_pueden_coincidir`; hoy la API no tiene
    pares ambiguos (ninguna URL concreta coincide con dos rutas del mismo
    método), así que se comprueba el detector con casos conocidos."""
    assert _pueden_coincidir("/programas/{numero}", "/programas/seleccionables")
    assert _pueden_coincidir("/a/{x}/b", "/a/c/{y}")
    assert _pueden_coincidir("/f/{ruta:path}", "/f/a/b/c")
    assert not _pueden_coincidir("/cycle/history/{id}/graph", "/cycle/current/graph")
    assert not _pueden_coincidir("/programas/{numero}", "/programas/{numero}/habilitado")
