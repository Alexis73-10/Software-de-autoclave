# tests/test_t23_sin_tarjeta.py
#
# Tanda 23 (MES-01..04), prueba de regla: el hardware de E/S se llama
# «módulo E/S» («I/O module»). Falla si «tarjeta»/«targeta» aparece en:
#   - valores de i18n/*.json;
#   - literales de texto de los .qml;
#   - plantillas de ticket, PDF y correo;
#   - tools/instalador/autoclave.iss;
#   - textos del rol configurar-modulo;
#   - mensajes de log de src/;
# si un valor de en.json contiene la palabra «board»; y si aparece en
# identificadores de src/ fuera de la lista blanca de abajo (códigos de
# alarma TARJETA_*, nombres persistidos y recuadros de interfaz, MES-03).
# También prueba codigo_visible() (MES-04).

import ast
import io
import json
import re
import tokenize
from pathlib import Path

import pytest

from autoclave.state_machine.alarms.catalogo import (CATALOGO, CODIGOS_TARJETA,
                                                     codigo_visible)

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"
PALABRA = re.compile(r"tarjeta|targeta", re.IGNORECASE)
BOARD = re.compile(r"\bboards?\b", re.IGNORECASE)

# ── lista blanca (MES-03) ───────────────────────────────────────────────────

# MES-03.1: códigos de alarma guardados en el historial (y la tupla que los
# agrupa). Se muestran como MODULO_ES_* con codigo_visible().
_CODIGO = re.compile(r"^TARJETA_[A-Z_]+$")
CODIGOS = {"CODIGOS_TARJETA"}

# MES-03.2: nombres persistidos en datos de campo (audit_log). Aparecen como
# literales, no como identificadores; se listan para los literales de log.
PERSISTIDOS = {"tarjeta_conectada", "tarjeta_es"}

# MES-03.3: «tarjeta» con sentido de recuadro de interfaz (inventario (b)).
RECUADROS = {
    "TarjetaMenu", "TarjetaContenido", "TarjetaResumen", "OpcionTarjeta", "TarjetaCanal",
    "TarjetaGrupo", "TarjetaSensor",
    "tarjeta", "tarjetas", "fondoTarjeta", "bordeTarjeta", "altoTarjeta", "aroTarjeta",
    "tarjetaSalida", "tarjetaEntrada", "tarjetaSensor", "tarjetaValor", "valorTarjeta",
    "tituloTarjeta", "descripcionTarjeta", "tarjetaPrincipal", "tarjetaContenido",
    "tarjetaOpciones", "tarjetaVentana", "tarjetaTextoLargo", "tarjetaSeguridadCiclo",
    "tarjetaSecadoValorLargo", "tarjetaSecadoSinValor", "tarjetaReportes", "tarjetaPresionada",
    "tarjetaPreciclo", "tarjetaPanelFinCiclo", "tarjetaNuevoUsuario", "tarjetaNormal",
    "tarjetaModalConfirmacion", "tarjetaLogin", "tarjetaIniciarSesion", "tarjetaInformacion",
    "tarjetaHistorial", "tarjetaDetalleAlarma", "tarjetaDesplegable", "tarjetaDeshabilitada",
    "tarjetaCicloEnCurso", "tarjetaCambioClave", "tarjetaCalendario", "relleno_tarjeta",
    "tarjeta_titulo", "tarjeta_descripcion", "tarjeta_",
}

# Frases de autoclave.iss donde «tarjeta» no es el módulo E/S.
OTRO_SENTIDO_ISS = re.compile(r"tarjetas? de red|lector(es)? de tarjetas", re.IGNORECASE)


def _permitido(nombre: str) -> bool:
    return bool(_CODIGO.match(nombre)) or nombre in CODIGOS or nombre in RECUADROS


def _archivos(carpeta: Path, patron: str):
    return sorted(p for p in carpeta.rglob(patron) if "__pycache__" not in p.parts)


# ── i18n ────────────────────────────────────────────────────────────────────

def _valores(nodo, ruta=""):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from _valores(v, f"{ruta}.{k}" if ruta else str(k))
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from _valores(v, f"{ruta}[{i}]")
    elif isinstance(nodo, str):
        yield ruta, nodo


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_i18n_sin_tarjeta(idioma):
    datos = json.loads((SRC / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
    malos = [(r, v) for r, v in _valores(datos) if PALABRA.search(v)]
    assert malos == []


def test_en_sin_board():
    datos = json.loads((SRC / "i18n" / "en.json").read_text(encoding="utf-8"))
    malos = [(r, v) for r, v in _valores(datos) if BOARD.search(v)]
    assert malos == []


def test_claves_de_texto_configurar_modulo_sin_tarjeta():
    for idioma in ("es", "en"):
        datos = json.loads((SRC / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        textos = list(_valores(datos.get("configurar_modulo", {}), "configurar_modulo"))
        assert textos, f"sin textos configurar_modulo.* en {idioma}.json"
        assert [(r, v) for r, v in textos if PALABRA.search(v)] == []


# ── QML ─────────────────────────────────────────────────────────────────────

_LITERAL_QML = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'')
_COMENTARIO_QML = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _sin_comentarios_qml(texto: str) -> str:
    """Quita comentarios sin tocar el contenido de los literales."""
    salida, i = [], 0
    for m in re.finditer(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|//[^\n]*|/\*.*?\*/', texto, re.DOTALL):
        salida.append(texto[i:m.start()])
        s = m.group(0)
        salida.append(s if s[0] in "\"'" else " " * 0)
        i = m.end()
    salida.append(texto[i:])
    return "".join(salida)


def _literales_qml(texto: str):
    for m in _LITERAL_QML.finditer(_sin_comentarios_qml(texto)):
        yield m.group(1) if m.group(1) is not None else m.group(2)


def test_literales_qml_sin_tarjeta():
    malos = []
    for p in _archivos(SRC / "ui_qml" / "qml", "*.qml"):
        for lit in _literales_qml(p.read_text(encoding="utf-8")):
            if not PALABRA.search(lit):
                continue
            # un literal-identificador (objectName, idAlarma, estilo) de la lista blanca
            if _IDENT.fullmatch(lit) and _permitido(lit):
                continue
            malos.append((p.relative_to(RAIZ).as_posix(), lit))
    assert malos == []


def test_identificadores_qml_fuera_de_la_lista_blanca():
    malos = set()
    for p in _archivos(SRC / "ui_qml" / "qml", "*.qml"):
        codigo = _LITERAL_QML.sub('""', _sin_comentarios_qml(p.read_text(encoding="utf-8")))
        for ident in _IDENT.findall(codigo):
            if PALABRA.search(ident) and not _permitido(ident):
                malos.add((p.relative_to(RAIZ).as_posix(), ident))
    assert sorted(malos) == []


# ── Python: identificadores, plantillas y log ───────────────────────────────

def _cadenas_py(arbol):
    """Constantes de texto de un módulo, sin docstrings (son comentarios)."""
    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = getattr(nodo, "body", [])
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant):
                docstrings.add(id(cuerpo[0].value))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in docstrings:
            yield nodo.value


def _literal_permitido(texto: str) -> bool:
    if _IDENT.fullmatch(texto):
        return _permitido(texto) or texto in PERSISTIDOS
    # un texto con espacios solo puede citar códigos TARJETA_* (no la palabra suelta)
    return not PALABRA.search(re.sub(r"TARJETA_[A-Z_]+", "", texto))


PLANTILLAS = [
    "services/domain/logging/ticket_formatter.py",
    "services/domain/logging/ticket_mantenimiento.py",
    "services/domain/logging/cycle_logger.py",
    "devices/printer/connectivity_ticket.py",
    "devices/printer/startup_ticket.py",
    "devices/printer/arranque_equipo.py",
    "devices/printer/realtime_printer.py",
    "ui_qml/exportacion/correo.py",
    "ui_qml/exportacion/pdf_ciclo.py",
    "ui_qml/exportacion/pdf_consolidado.py",
    "ui_qml/exportacion/pdf_resumen.py",
    "ui_qml/exportacion/textos.py",
    "backend/rutas/reportes.py",
    "estacion/configurar_modulo.py",
]


@pytest.mark.parametrize("rel", PLANTILLAS)
def test_plantillas_y_configurar_modulo_sin_tarjeta(rel):
    arbol = ast.parse((SRC / rel).read_text(encoding="utf-8"))
    malos = [c for c in _cadenas_py(arbol) if PALABRA.search(c) and not _literal_permitido(c)]
    assert malos == []


_METODOS_LOG = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


def _textos_de_log(arbol):
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in _METODOS_LOG):
            for arg in nodo.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        yield nodo.lineno, sub.value


def test_mensajes_de_log_sin_tarjeta():
    malos = []
    for p in _archivos(SRC, "*.py"):
        arbol = ast.parse(p.read_text(encoding="utf-8"))
        for linea, texto in _textos_de_log(arbol):
            if PALABRA.search(texto) and not _literal_permitido(texto):
                malos.append(f"{p.relative_to(RAIZ).as_posix()}:{linea}: {texto!r}")
    assert malos == []


def test_identificadores_python_fuera_de_la_lista_blanca():
    malos = set()
    for p in _archivos(SRC, "*.py"):
        texto = p.read_text(encoding="utf-8")
        for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
            if tok.type == tokenize.NAME and PALABRA.search(tok.string) and not _permitido(tok.string):
                malos.add((p.relative_to(RAIZ).as_posix(), tok.string))
    assert sorted(malos) == []


# ── Setup ───────────────────────────────────────────────────────────────────

def test_autoclave_iss_sin_tarjeta():
    texto = (RAIZ / "tools" / "instalador" / "autoclave.iss").read_text(encoding="utf-8-sig")
    malos = [(n, l.strip()) for n, l in enumerate(texto.splitlines(), 1)
             if PALABRA.search(OTRO_SENTIDO_ISS.sub("", l))]
    assert malos == []
    assert "Red del módulo E/S" in texto


# ── MES-04 ──────────────────────────────────────────────────────────────────

def test_codigo_visible():
    assert codigo_visible("TARJETA_SIN_ACK") == "MODULO_ES_SIN_ACK"
    assert codigo_visible("TARJETA_CONFIG_SEGURIDAD") == "MODULO_ES_CONFIG_SEGURIDAD"
    for otro in ("COM-01", "SEN-02", "DISCREPANCIA_SALIDAS", "", None, 3):
        assert codigo_visible(otro) == otro


def test_codigos_guardados_no_cambian():
    # MES-03.1: los códigos siguen en el catálogo con su nombre de siempre
    for codigo in CODIGOS_TARJETA:
        assert codigo in CATALOGO
    assert all(codigo_visible(c).startswith("MODULO_ES_") for c in CODIGOS_TARJETA
               if c.startswith("TARJETA_"))


def test_titulos_del_catalogo_sin_tarjeta():
    malos = [(c, d.titulo) for c, d in CATALOGO.items()
             if PALABRA.search(d.titulo) or PALABRA.search(d.descripcion) or PALABRA.search(d.accion)]
    assert malos == []
