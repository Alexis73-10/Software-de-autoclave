"""Fase 6 (UI de Opciones sin HTTP síncrono): ningún controlador de la UI llama
a `SesionBackend.enviar(...)` (bloquea el hilo de la GUI). Se usa
`enviar_async`, `OperacionCritica` o `CambioOptimista`.

Excepciones explícitas (archivo, función):
- entradas_salidas_controller.py::accionar: salidas momentáneas del modo
  prueba; decisión de Cristian, siguen síncronas.
`enviar_al_cerrar` (cierre de sesión) es otro atributo y no cuenta.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_SRC = RAIZ / "src" / "autoclave"

EXCEPCIONES = {
    ("entradas_salidas_controller.py", "accionar"),
}


def _archivos():
    arch = sorted((_SRC / "ui_qml" / "controllers").glob("*.py"))
    arch.append(_SRC / "ui_pyside" / "views" / "nuevo_usuario" / "puente.py")
    return arch


def _llamadas_enviar(ruta: Path):
    """(linea, funcion_contenedora) de cada `<x>.enviar(...)`."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    hallazgos = []

    def visitar(nodo, funcion):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcion = nodo.name
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "enviar"):
            hallazgos.append((nodo.lineno, funcion))
        for hijo in ast.iter_child_nodes(nodo):
            visitar(hijo, funcion)

    visitar(arbol, "<modulo>")
    return hallazgos


def test_controladores_sin_enviar_sincrono():
    archivos = _archivos()
    assert len(archivos) > 5
    for a in archivos:
        assert a.exists(), a
    indebidas = [f"{a.name}:{lin} ({fn})"
                 for a in archivos
                 for lin, fn in _llamadas_enviar(a)
                 if (a.name, fn) not in EXCEPCIONES]
    assert not indebidas, (
        "llamadas .enviar( síncronas en la UI (usar enviar_async / "
        "OperacionCritica / CambioOptimista): " + ", ".join(indebidas))


def test_excepciones_siguen_vigentes():
    """Una excepción que ya no se usa debe retirarse de la lista."""
    usadas = set()
    for a in _archivos():
        for _lin, fn in _llamadas_enviar(a):
            usadas.add((a.name, fn))
    assert EXCEPCIONES <= usadas, f"excepciones sin uso: {EXCEPCIONES - usadas}"


# ── Forma completa de aplicarPuntos / restaurar (3.er ciclo de corrección) ──
# EntradasSalidasController.aplicarPuntos(..., confirmar, segmento, sensor) y
# restaurar(destino, segmento, sensor): la forma corta (sin segmento y sensor)
# no comprueba que la pantalla sea la del sensor cargado (C1). Ningún llamador
# en src la usa: Python por AST y QML por texto (no hay AST de QML).

_N_APLICAR, _N_RESTAURAR = 9, 3


def _llamadas_py(nombre: str):
    """(archivo, línea, n.º de argumentos) de cada `<x>.nombre(...)` en src."""
    hallazgos = []
    for ruta in sorted(_SRC.rglob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == nombre):
                hallazgos.append((ruta.name, nodo.lineno, len(nodo.args) + len(nodo.keywords)))
    return hallazgos


def _args_qml(texto: str, inicio: int) -> int:
    """N.º de argumentos de la llamada cuyo '(' está en `inicio` (comas de
    primer nivel; sin cadenas con comas en estas llamadas)."""
    nivel, n, hay = 0, 1, False
    for c in texto[inicio:]:
        if c in "([{":
            nivel += 1
            if nivel == 1:
                continue
        elif c in ")]}":
            nivel -= 1
            if nivel == 0:
                return n if hay else 0
        elif c == "," and nivel == 1:
            n += 1
        if nivel >= 1 and not c.isspace():
            hay = True
    raise AssertionError("paréntesis sin cerrar")


def _llamadas_qml(patron: str):
    import re
    hallazgos = []
    for ruta in sorted((_SRC / "ui_qml").rglob("*.qml")):
        texto = ruta.read_text(encoding="utf-8")
        for m in re.finditer(patron, texto):
            linea = texto.count("\n", 0, m.start()) + 1
            hallazgos.append((ruta.name, linea, m.group(1), _args_qml(texto, m.end() - 1)))
    return hallazgos


def test_aplicar_puntos_y_restaurar_solo_en_forma_completa():
    cortas = [f"{a}:{l} aplicarPuntos({n})" for a, l, n in _llamadas_py("aplicarPuntos")
              if n != _N_APLICAR]
    # restaurar(destino) de 1 argumento: la forma corta de E/S (la de
    # RespaldoController no lleva argumentos)
    cortas += [f"{a}:{l} restaurar({n})" for a, l, n in _llamadas_py("restaurar") if n == 1]
    qml_aplicar = _llamadas_qml(r"(\w+)\.aplicarPuntos\(")
    cortas += [f"{a}:{l} aplicarPuntos({n})" for a, l, _r, n in qml_aplicar if n != _N_APLICAR]
    qml_restaurar = _llamadas_qml(r"(\w+)\.restaurar\(")
    cortas += [f"{a}:{l} {r}.restaurar({n})" for a, l, r, n in qml_restaurar
               if (r == "controlador" and n != _N_RESTAURAR) or n == 1]
    assert qml_aplicar, "no se encontró ningún llamador de aplicarPuntos (¿cambió el patrón?)"
    assert any(r == "controlador" for _a, _l, r, _n in qml_restaurar)
    assert not cortas, "forma corta de aplicarPuntos/restaurar: " + ", ".join(cortas)
