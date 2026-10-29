"""TEC-ACC-07 (tanda 22, PRB-T22-01): regla del teclado en pantalla.

El modo en vivo del `PanelTeclado` (`abrirAlfanumerico`/`abrirNumerico`)
entrega lo escrito con cada tecla, al abrir otro campo y al cancelar (con
""). Solo sirve para asignar texto a una propiedad. Un callback que ejecuta
una acción (llama a un controlador que envía al backend, abre un diálogo u
otro teclado, difiere trabajo con `Qt.callLater` o pide la contraseña) debe
usar `abrirAlfanumericoAccion`, que entrega una sola vez al Confirmar.

La prueba recorre los `.qml`, toma el argumento `alConfirmar` de cada
llamada en vivo (5.º de `abrirAlfanumerico`, 7.º de `abrirNumerico`) y falla
si su cuerpo contiene una acción. Si el argumento es un identificador (un
parámetro de la función que envuelve la llamada, como `editar(titulo, valor,
alConfirmar)`), se revisan los argumentos con que se llama a esa función en
el mismo archivo."""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_EXCLUIDOS = ("Pruebas/",)
# Lo que delata una acción dentro del callback
_ACCIONES = ("control.", ".abrir(", "abrirAlfanumerico", "Qt.callLater", "_pedirClave")
# posición (0-based) del argumento alConfirmar
_POSICION = {"abrirAlfanumerico": 4, "abrirNumerico": 6}
# archivo -> fragmentos permitidos y por qué (vacía: no apareció ningún falso positivo)
_LISTA_BLANCA: dict[str, set[str]] = {}

_LLAMADA = re.compile(r"\b(abrirAlfanumerico|abrirNumerico)\s*\(")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(linea.split("//", 1)[0] for linea in texto.splitlines())


def _argumentos(texto: str, abre: int) -> list[str]:
    """Argumentos de nivel superior de la llamada cuyo «(» está en `abre`."""
    args, actual, nivel, i, cadena = [], [], 0, abre + 1, None
    while i < len(texto):
        c = texto[i]
        if cadena:
            actual.append(c)
            if c == "\\":
                actual.append(texto[i + 1]); i += 2; continue
            if c == cadena:
                cadena = None
        elif c in "\"'`":
            cadena = c; actual.append(c)
        elif c in "([{":
            nivel += 1; actual.append(c)
        elif c in ")]}":
            if nivel == 0:
                args.append("".join(actual).strip())
                return args
            nivel -= 1; actual.append(c)
        elif c == "," and nivel == 0:
            args.append("".join(actual).strip()); actual = []
        else:
            actual.append(c)
        i += 1
    raise AssertionError("llamada sin cerrar")


def _funcion_que_envuelve(texto: str, pos: int):
    """Nombre y parámetros de la última `function nombre(...)` antes de `pos`."""
    ultimas = list(re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)", texto[:pos]))
    if not ultimas:
        return None, []
    m = ultimas[-1]
    return m.group(1), [p.strip() for p in m.group(2).split(",")]


def _callbacks(rel: str, texto: str):
    """(línea, cuerpo del callback) de cada llamada en vivo del archivo."""
    for m in _LLAMADA.finditer(texto):
        abre = m.end() - 1
        args = _argumentos(texto, abre)
        pos = _POSICION[m.group(1)]
        if len(args) <= pos:
            continue
        cb = args[pos]
        linea = texto.count("\n", 0, m.start()) + 1
        if re.fullmatch(r"[A-Za-z_]\w*", cb):
            nombre, params = _funcion_que_envuelve(texto, m.start())
            if nombre and cb in params:
                i = params.index(cb)
                for llamada in re.finditer(r"\b" + nombre + r"\s*\(", texto):
                    if texto[max(0, llamada.start() - 9):llamada.start()].endswith("function "):
                        continue
                    sub = _argumentos(texto, llamada.end() - 1)
                    if len(sub) > i:
                        yield texto.count("\n", 0, llamada.start()) + 1, sub[i]
                continue
        yield linea, cb


def _violaciones():
    for ruta in sorted(QML.rglob("*.qml")):
        rel = ruta.relative_to(QML).as_posix()
        if rel.startswith(_EXCLUIDOS) or rel == "Componentes/PanelTeclado.qml":
            continue
        texto = _sin_comentarios(ruta.read_text(encoding="utf-8"))
        for linea, cb in _callbacks(rel, texto):
            if any(f in cb for f in _LISTA_BLANCA.get(rel, ())):
                continue
            hallado = [a for a in _ACCIONES if a in cb]
            if hallado:
                yield f"{rel}:{linea}: {hallado} en {' '.join(cb.split())[:120]}"


def test_ningun_callback_en_vivo_ejecuta_una_accion():
    encontrados = list(_violaciones())
    assert encontrados == [], "usar abrirAlfanumericoAccion:\n" + "\n".join(encontrados)


@pytest.mark.parametrize("cuerpo, acciona", [
    ("texto => raiz[nombre] = texto", False),
    ("(v) => control.crear(raiz.baseElegida, String(v))", True),
    ("function (n) { raiz._n = n; Qt.callLater(f) }", True),
    ("clave => raiz._pedirClave(x)", True),
])
def test_el_detector_distingue_asignar_de_accionar(cuerpo, acciona):
    texto = f'teclado.abrirAlfanumerico("t", "", 40, false, {cuerpo}, siguiente ? () => raiz.teclado.abrirAlfanumerico("u", "", 1, false, x => y = x) : null)'
    cbs = [cb for _, cb in _callbacks("x.qml", texto)]
    assert cbs[0] == cuerpo
    assert any(a in cbs[0] for a in _ACCIONES) is acciona


def test_el_detector_sigue_un_callback_pasado_por_parametro():
    texto = """
    function editar(titulo, valor, alConfirmar) {
        teclado.abrirNumerico(titulo, "u", valor, 0, 1, 0, alConfirmar)
    }
    onA: raiz.editar("t", 1, (v) => raiz.x = v)
    onB: raiz.editar("t", 1, (v) => control.guardar(v))
    """
    cbs = [cb for _, cb in _callbacks("x.qml", texto)]
    assert cbs == ["(v) => raiz.x = v", "(v) => control.guardar(v)"]


def test_las_pantallas_de_accion_usan_el_modo_accion():
    for archivo, minimo in (("Pantallas/OpcionesReasignacion.qml", 3),
                            ("Pantallas/OpcionesConectividad.qml", 2),
                            ("Pantallas/OpcionesManejoCiclos.qml", 2)):
        texto = (QML / archivo).read_text(encoding="utf-8")
        assert texto.count("abrirAlfanumericoAccion(") >= minimo, archivo
