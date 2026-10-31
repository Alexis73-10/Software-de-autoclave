"""Huellas de la API y de los roles (tanda 15, A0 y comprobación posterior).

Uso (desde la raíz, con ``src`` y la raíz en sys.path):
    python docs/informes/tanda15/generar_huellas.py <carpeta_salida> <mod_roles> <mod_validacion>

Usa ``huella_rutas``/``openapi_ordenado`` de ``tests/test_t15_rutas_equivalentes.py``.
"""
import importlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]

from tests.test_t15_rutas_equivalentes import huella_rutas, openapi_ordenado  # noqa: E402


def _valor(v):
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    if isinstance(v, dict):
        return {k: _valor(x) for k, x in sorted(v.items())}
    if isinstance(v, (tuple, list)):
        return [_valor(x) for x in v]
    return v


def main(salida: str, mod_roles: str, mod_validacion: str) -> None:
    out = Path(salida)
    out.mkdir(parents=True, exist_ok=True)
    from autoclave.backend.server import app
    (out / "rutas.json").write_text(
        json.dumps(huella_rutas(app), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "openapi.json").write_text(openapi_ordenado(app), encoding="utf-8")
    roles = importlib.import_module(mod_roles)
    val = importlib.import_module(mod_validacion)
    huella = {
        "ROL_*": {k: getattr(roles, k) for k in sorted(dir(roles)) if k.startswith("ROL_")},
        "ROLES": _valor(roles.ROLES),
        "VALORES_ROL": _valor(roles.VALORES_ROL),
        "ROLES_CREABLES": _valor(roles.ROLES_CREABLES),
        "validacion_usuario": sorted(n for n in dir(val) if not n.startswith("_")
                                     and getattr(getattr(val, n), "__module__", mod_validacion)
                                     in (mod_validacion, None)
                                     and not isinstance(getattr(val, n), type(json))),
    }
    (out / "roles.json").write_text(json.dumps(huella, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:4])
