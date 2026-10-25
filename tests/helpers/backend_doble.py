# tests/helpers/backend_doble.py
#
# Utilidades para probar backend/server.py sin hardware: lo importa de nuevo
# con un BackendContext falso (cada importación trae su propio almacén de
# tokens y contadores de intentos) y emite tokens de sesión por rol
# (planeacion_backend_autenticacion.md §5.1-5.2).
#
# ORG-12 (tanda 15): server.py se partió en dependencias.py y rutas/<área>.py.
# Un nombre que antes vivía solo en server.py puede estar ahora enlazado (al
# mismo objeto) en varios módulos: el que lo define y los que lo importan.
# `modulo_backend` da el módulo donde se busca un nombre; `fijar_en_backend` y
# `parchear_en_backend` equivalen al `srv.<nombre> = valor` de antes: lo
# cambian en todos los módulos del backend donde está enlazado.

import importlib
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch


def cargar_servidor(ctx=None):
    """Importa autoclave.backend.server con `ctx` (MagicMock por defecto) como
    contexto. Devuelve (módulo, ctx)."""
    ctx = ctx if ctx is not None else MagicMock()
    # S9 (revisión ★ pasada 2 R2-B1): /io/test/output falla cerrada si la
    # evaluación de salidas bloqueadas no es un dict; el doble no bloquea nada
    # salvo que la prueba lo configure
    loop = getattr(ctx, "control_loop", None)
    funcion = getattr(loop, "salidas_prueba_bloqueadas", None)
    if (isinstance(funcion, MagicMock) and funcion.side_effect is None
            and not isinstance(funcion.return_value, dict)):
        funcion.return_value = {}
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    return srv, ctx


def cabecera(srv, rol: str = "ingeniero", usuario: str | None = None,
             debe_cambiar_clave: bool = False) -> dict:
    """Emite un token en el almacén del servidor y devuelve la cabecera HTTP."""
    sesion = modulo_backend("dependencias").tokens.emitir(
        usuario or f"usuario_{rol}", rol.capitalize(), rol, debe_cambiar_clave)
    return {"Authorization": f"Bearer {sesion.token}"}


_PREFIJOS_BACKEND = ("autoclave.backend.server", "autoclave.backend.dependencias",
                     "autoclave.backend.rutas")


def modulo_backend(nombre: str):
    """Módulo ya cargado del backend partido: "server", "dependencias",
    "rutas.io", "rutas._comun"..."""
    return sys.modules[f"autoclave.backend.{nombre}"]


def _enlaces(nombre: str) -> list:
    mods = [m for k, m in list(sys.modules.items())
            if k.startswith(_PREFIJOS_BACKEND) and m is not None and nombre in vars(m)]
    if not mods:
        raise AttributeError(f"ningún módulo del backend define {nombre!r}")
    if len({id(vars(m)[nombre]) for m in mods}) != 1:
        raise AssertionError(f"{nombre!r} no es el mismo objeto en {[m.__name__ for m in mods]}")
    return mods


def fijar_en_backend(nombre: str, valor) -> None:
    """`srv.<nombre> = valor` de antes de partir server.py (ORG-12)."""
    for m in _enlaces(nombre):
        setattr(m, nombre, valor)


def parchear_en_backend(monkeypatch, nombre: str, valor) -> None:
    """`monkeypatch.setattr(srv, nombre, valor)` de antes de partir server.py."""
    for m in _enlaces(nombre):
        monkeypatch.setattr(m, nombre, valor)


@contextmanager
def parche_en_backend(nombre: str, nuevo):
    """`with patch.object(srv, nombre, ...)` de antes de partir server.py: pone
    el mismo objeto `nuevo` en todos los módulos donde está enlazado y lo
    devuelve (para `as`)."""
    with ExitStack() as pila:
        for m in _enlaces(nombre):
            pila.enter_context(patch.object(m, nombre, nuevo))
        yield nuevo


def archivos_backend() -> list:
    """ORG-12: los archivos en que se partió server.py (server.py,
    dependencias.py y rutas/*.py), para las pruebas que leen el código."""
    raiz = Path(__file__).resolve().parents[2] / "src" / "autoclave" / "backend"
    return [raiz / "server.py", raiz / "dependencias.py", *sorted((raiz / "rutas").glob("*.py"))]


def fuente_backend() -> str:
    """Texto de `archivos_backend()`, uno tras otro (lo que antes era server.py)."""
    return "".join(p.read_text(encoding="utf-8") for p in archivos_backend())
