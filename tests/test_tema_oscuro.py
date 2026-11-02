# tests/test_tema_oscuro.py
#
# Modo oscuro (docs/mis_plans/prompt_claude_code_modo_oscuro.md, paso 6):
#   (a) ningún literal de color en QML fuera de Tema/ (lista de pendientes
#       explícita mientras los conjuntos B, C y D migran sus archivos);
#   (b) cada propiedad de color de Colores.qml tiene valor claro y oscuro (o un
#       valor único, igual en los dos temas, solo en la lista justificada);
#   (c) los claros son los de hoy (contra la rama base c43b9d0b) y los oscuros
#       los de paleta_modo_oscuro.md (se lee la paleta; no se copian valores);
#   (d) alarmas IEC iguales en los dos temas;
#   (e) contraste WCAG de los pares de la §8 de la paleta en oscuro;
#   más la persistencia (config_tema, GET/PUT /theme sin bitácora), el
#   singleton Apariencia, el slot fijarTema y el cambio en vivo en QML.

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.config_tema import ConfigTema

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
COLORES = QML / "Tema" / "Colores.qml"
PALETA = RAIZ / "docs" / "diseno" / "mockups" / "modo_oscuro" / "paleta_modo_oscuro.md"
MOCKUPS = PALETA.parent
PLAN = RAIZ / "docs" / "informes" / "modo_oscuro" / "plan.md"
BASE = "c43b9d0b"     # dev de donde salió la rama modo-oscuro (tema claro de referencia)

_HEX = r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?"


# ───────────────────────────── lectura de Colores ─────────────────────────────

def _norm(h: str) -> str:
    h = h.upper()
    return h if len(h) == 9 else "#FF" + h[1:]        # #AARRGGBB


def _colores() -> dict:
    """{nombre: (claro, oscuro)} de Colores.qml, en #AARRGGBB."""
    props = {}
    for linea in COLORES.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*readonly property color (\w+):\s*(.*)$", linea)
        if not m:
            continue
        cuerpo = m.group(2).split("//")[0].strip()
        dos = re.fullmatch(rf'oscuro \? "({_HEX})" : "({_HEX})"', cuerpo)
        uno = re.fullmatch(rf'"({_HEX})"', cuerpo)
        assert dos or uno, f"formato no reconocido en Colores.{m.group(1)}: {cuerpo}"
        props[m.group(1)] = ((_norm(dos.group(2)), _norm(dos.group(1))) if dos
                             else (_norm(uno.group(1)),) * 2)
    return props


def _unicos() -> set:
    return {n for n, (c, o) in _colores().items()
            if re.search(rf'property color {n}:\s*"', COLORES.read_text(encoding="utf-8"))}


# ───────────────────────────── lectura de la paleta ───────────────────────────

def _paleta_texto() -> str:
    return PALETA.read_text(encoding="utf-8")


def _al(hexa: str, resto: str) -> str:
    """'#2DBE66' + ' al 45 %' → #732DBE66."""
    m = re.match(r"\s*\(?al (\d+) %", resto)
    if not m:
        return _norm(hexa)
    return "#%02X%s" % (round(int(m.group(1)) * 255 / 100), hexa[1:].upper())


def _paleta_pares() -> dict:
    """Líneas `- \\`nombre\\` — #claro → #oscuro[ al NN %]` → {nombre: (claro, oscuro)}."""
    pares = {}
    for m in re.finditer(rf"^- `(\w+)` — (?:claro )?({_HEX}) → (?:oscuro )?({_HEX})(.*)$",
                         _paleta_texto(), re.M):
        pares[m.group(1)] = (_norm(m.group(2)), _al(m.group(3), m.group(4)))
    return pares


def _paleta_buscar(patron: str) -> str:
    """Primer color del patrón (grupo 1; grupo 2 opcional = porcentaje de alfa)."""
    m = re.search(patron, _paleta_texto(), re.S)
    assert m, f"la paleta ya no dice: {patron}"
    h = m.group(1)
    if m.lastindex and m.lastindex >= 2:
        return "#%02X%s" % (round(int(m.group(2)) * 255 / 100), h[1:].upper())
    return _norm(h)


# Oscuro de las propiedades nuevas que la paleta da en texto libre (§2-§6).
_PALETA_LIBRE = {
    "fondoPanel": r"`fondoPanel` — oscuro (#\w{6})",
    "fondoElevado": r"`fondoElevado` — oscuro (#\w{6})",
    "fondoPista": r"`fondoPista` — oscuro (#\w{6})",
    "bordeTarjeta": r"`bordeTarjeta` — oscuro (#\w{6})",
    "estadoEjecucion": r"`estadoEjecucion` — oscuro (#\w{6})",
    "estadoEjecucionCirculo": r"`estadoEjecucion`.*?círculo (#\w{6})",
    "faseCompletadaInicio": r"completada gradiente (#\w{6})",
    "faseCompletadaFin": r"completada gradiente #\w{6} → (#\w{6})",
    "faseActiva": r"activa llenado (#\w{6})",
    "faseActivaFin": r"activa llenado (#\w{6})",                 # sólido en oscuro (OSC-16)
    "faseActivaAro": r"con aro (#\w{6}) al (\d+) %",
    "fasePendienteFondo": r"pendiente fondo (#\w{6})",
    "fasePendienteBorde": r"pendiente fondo #\w{6}, borde (#\w{6})",
    "fasePendienteIcono": r"pendiente fondo #\w{6}, borde #\w{6}, ícono (#\w{6})",
    "fasePendienteEtiqueta": r"ícono #\w{6}, etiqueta (#\w{6})",
    "faseEtiquetaActiva": r"etiqueta activa (#\w{6})",
    "faseChorro": r"con aro (#\w{6})",                           # OSC-16
    "conectorInicio": r"conector completado (#\w{6})",
    "conectorFin": r"conector completado #\w{6} → (#\w{6})",
    "conectorPendiente": r"línea de fases pendiente (#\w{6})",
    "progresoInicio": r"Barra de avance del ciclo: (#\w{6})",
    "progresoFin": r"Barra de avance del ciclo: #\w{6} → (#\w{6})",
    "serieGrafica1": r"Gráfica: cámara (#\w{6})",
    "serieGrafica2": r"Gráfica: cámara #\w{6}, referencia (#\w{6})",
    "serieGrafica3": r"Gráfica: .*?presión (#\w{6})",
    "graficaCuadricula": r"rejilla (#\w{6})",
    "graficaEje": r"ejes y líneas de fase (#\w{6})",
    "graficaDivisorFase": r"ejes y líneas de fase (#\w{6})",
    "graficaTextoEje": r"texto de ejes (#\w{6})",
    "graficaCursorFondo": r"recuadro del cursor (#\w{6})",
    "graficaCursorBorde": r"recuadro del cursor #\w{6} borde (#\w{6})",
    "valorTempCamara": r"tira de 6\): temperatura de cámara (#\w{6})",
    "valorTempReferencia": r"tira de 6\): temperatura de cámara #\w{6}, referencia (#\w{6})",
    "valorPresion": r"tira de 6\): .*?presión (#\w{6})",
    "abrirPuertaArriba": r"ABRIR PUERTA \(oscuro\): relleno (#\w{6})",
    "abrirPuertaAbajo": r"ABRIR PUERTA \(oscuro\): relleno (#\w{6})",
    "abrirPuertaBorde": r"ABRIR PUERTA \(oscuro\): relleno #\w{6}, borde (#\w{6})",
    "abrirPuertaTexto": r"ABRIR PUERTA \(oscuro\):.*?texto/ícono (#\w{6})",
    "cancelarArriba": r"CANCELAR CICLO \(oscuro\): gradiente vertical (#\w{6})",
    "cancelarAbajo": r"CANCELAR CICLO \(oscuro\): gradiente vertical #\w{6} → (#\w{6})",
    "cancelarBorde": r"CANCELAR CICLO \(oscuro\):.*?borde (#\w{6})",
    "insignia": r"insignia de la campana usa (#\w{6})",
    "textoInsignia": r"insignia de la campana usa #\w{6} con número (#\w{6})",
    "fondoReposoBorde": r"Reposo: radial.*?\(55 %\) → (#\w{6})",
}

# Sin valor en la paleta: el oscuro es el de otra propiedad (OSC-04, OSC-11, OSC-16).
_OSCURO_COMO = {
    "avatarFondo": "fondoElevado", "graficaBorde": "bordeTarjeta",
    "graficaTitulo": "textoPrimario", "graficaTexto": "textoPrimario",
    "graficaSeparador": "bordeDivisor", "graficaTituloEje": "textoSecundario",
    "graficaBordeBoton": "bordeCampo", "graficaIconoFase": "textoGuia",
    "graficaCursor": "textoGuia",
    "textoNegro": "textoPrimario", "textoPrograma": "textoPrimario",
    "textoTitulo": "textoPrimario", "textoReloj": "textoPrimario",
    "textoEtiqueta": "textoSecundario", "textoUnidad": "textoSecundario",
    "textoPie": "textoSecundario", "rotuloReloj": "textoSecundario",
    "textoVersion": "textoGuia", "textoVacio": "textoGuia",
    "bordeSuave": "bordeTarjeta", "divisorCiclo": "bordeDivisor",
    "divisorParam": "bordeDivisor", "divisorPie": "bordeDivisor",
    "lineaAlarmas": "bordeDivisor", "seleccionSutil": "accionFondoTenue",
    "puertaCerradaFondo": "fondoElevado", "fondoSeccion": "fondoSutil",
    "fondoCampo": "fondoElevado", "iconoCampo": "textoGuia",           # OSC-21 / OSC-18
    "puertaCerradaTexto": "accionPrimarioTexto", "puertaCerradaBorde": "abrirPuertaBorde",   # OSC-22
    "naranjaTexto": "advertenciaTexto", "naranjaEstado": "advertencia",
    "iconoBarraMenu": "iconoBarraInferior",
}

# Oscuro tomado del mockup aprobado (no está en el texto de la paleta).
_OSCURO_MOCKUP = {"faseEtiqueta": "03_ciclo_en_curso.html"}

# Valor único, igual en los dos temas, con su justificación (hallazgo).
_IGUALES = {
    "alarmaAlta": "decisión 2", "alarmaMedia": "decisión 2", "alarmaBaja": "decisión 2",
    "textoSobreAccion": "OSC-09", "textoSobreAlarmaMedia": "OSC-16",
    "velo": "OSC-03", "veloSuave": "OSC-03", "veloFuerte": "OSC-03",
    "sombra": "OSC-03", "sombraSuave": "OSC-03",
    "confirmarArriba": "OSC-10", "confirmarAbajo": "OSC-10",
    "botonNaranjaArriba": "OSC-10", "botonNaranjaAbajo": "OSC-10",
    "peligroFuerte": "OSC-10", "fondoReposoBorde": "§1 (solo se dibuja en oscuro)",
}


def _oscuro_esperado(nombre: str, props: dict):
    pares = _paleta_pares()
    if nombre in pares:
        return pares[nombre][1]
    if nombre in _PALETA_LIBRE:
        return _paleta_buscar(_PALETA_LIBRE[nombre])
    if nombre in _OSCURO_COMO:
        return props[_OSCURO_COMO[nombre]][1]
    if nombre in _OSCURO_MOCKUP:
        return None          # se comprueba aparte contra el HTML del mockup
    if nombre in _IGUALES:
        return props[nombre][0]
    raise AssertionError(f"Colores.{nombre}: sin origen del valor oscuro (paleta o hallazgo)")


# ───────────────────── tema claro de hoy (rama base) ─────────────────────

def _git_base(ruta: str) -> str:
    try:
        r = subprocess.run(["git", "show", f"{BASE}:{ruta}"], cwd=RAIZ, capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
    except Exception as e:                      # sin git: no se puede comparar
        pytest.skip(f"git no disponible: {e}")
    if r.returncode != 0:
        pytest.skip(f"sin la rama base {BASE}: {r.stderr.strip()}")
    return r.stdout


def _literales(texto: str) -> list:
    """Colores literales de un fragmento, en orden, como #AARRGGBB."""
    out = []
    for m in re.finditer(rf'"({_HEX})"|Qt\.rgba\(([^)]*)\)|"(white|black)"', texto):
        if m.group(1):
            out.append(_norm(m.group(1)))
        elif m.group(2):
            v = [float(eval(x, {"__builtins__": {}})) for x in m.group(2).split(",")]  # noqa: S307
            out.append("#%02X%02X%02X%02X" % tuple(round(c * 255) for c in (v[3], *v[:3])))
        else:
            out.append("#FFFFFFFF" if m.group(3) == "white" else "#FF000000")
    return out


_SIN_COLOR = "#00000000"
# Claro de cada propiedad nueva: dónde estaba el literal en la base.
#   (archivo, "nombre")  → `property color nombre: "<hex>"` del archivo
#   (archivo, línea[, i]) → i-ésimo literal de esa línea
#   ("Colores", nombre)  → valor de Colores.qml en la base
#   ("blanco",)          → "white"/SVG blanco de hoy; ("sin_color",) → hoy no se dibuja
#   ("paleta_claro",)    → sin literal en la base: el claro de la §7 (OSC-01)
_PRE = "Pantallas/PantallaPreciclo.qml"
_CIC = "Pantallas/PantallaCicloEnCurso.qml"
_GRA = "Componentes/GraficaCiclo.qml"
_LIQ = "Componentes/CirculoFaseLiquido.qml"
_CON = "Componentes/ConectorFase.qml"
_DES = "Componentes/DeslizadorInicio.qml"
_ORIGEN_CLARO = {
    "fondoPanel": ("Colores", "fondoTarjeta"), "fondoElevado": ("Colores", "fondoTarjeta"),
    "fondoPista": (_CIC, "pistaProgreso"), "bordeTarjeta": (_PRE, "bordeTarjeta"),
    "avatarFondo": (_PRE, "avatarFondo"),
    "estadoEjecucion": (_PRE, "verdeEjecutando"), "estadoEjecucionCirculo": (_CIC, "verdeEjecutando"),
    "faseCompletadaInicio": (_LIQ, "_liquidoInicio"), "faseCompletadaFin": (_LIQ, "_liquidoFin"),
    "faseActiva": (_LIQ, "_liquidoInicio"), "faseActivaFin": (_LIQ, "_liquidoFin"),
    "faseActivaAro": ("sin_color",), "fasePendienteFondo": (_LIQ, 66),
    "fasePendienteBorde": ("sin_color",), "fasePendienteIcono": ("blanco",),
    "fasePendienteEtiqueta": ("Componentes/BarraFases.qml", "etiqueta"),
    "faseEtiqueta": ("Componentes/BarraFases.qml", "etiqueta"),
    "faseEtiquetaActiva": ("Componentes/BarraFases.qml", "etiqueta"),
    "faseChorro": (_LIQ, "_chorro"),
    "conectorInicio": (_CON, 71), "conectorFin": (_CON, 72), "conectorPendiente": (_CON, 59),
    "progresoInicio": (_CIC, "progresoInicio"), "progresoFin": (_CIC, "progresoFin"),
    "serieGrafica1": (_GRA, 56), "serieGrafica2": (_GRA, 59), "serieGrafica3": (_GRA, 62),
    "graficaCuadricula": (_GRA, "cuadricula"), "graficaEje": (_GRA, "eje"),
    "graficaTextoEje": (_GRA, "etiquetaEje"), "graficaCursorFondo": ("Colores", "fondoTarjeta"),
    "graficaCursorBorde": (_GRA, "borde"), "graficaCursor": (_GRA, "cursor"),
    "graficaBorde": (_GRA, "borde"), "graficaTitulo": (_GRA, "titulo"),
    "graficaTexto": (_GRA, "texto"), "graficaSeparador": (_GRA, "separador"),
    "graficaDivisorFase": (_GRA, "divisorFase"), "graficaIconoFase": (_GRA, "iconoFase"),
    "graficaTituloEje": (_GRA, "tituloEje"), "graficaBordeBoton": (_GRA, "bordeBoton"),
    "valorTempCamara": (_PRE, "negro"), "valorTempReferencia": (_PRE, "negro"),
    "valorPresion": (_PRE, "negro"),
    "deslizadorPista": (_DES, 208, 0), "deslizadorPistaListo": (_DES, 208, 1),
    "deslizadorAcento": (_DES, "verdeReposo"), "deslizadorAcentoListo": (_DES, "verdeListo"),
    "deslizadorBrillo": (_DES, "brilloReposo"), "deslizadorBrilloListo": (_DES, "brilloListo"),
    "deslizadorTexto": (_DES, "verdeReposo"), "deslizadorSombraInterior": (_DES, 224),
    "deslizadorNucleo": ("paleta_claro",), "exitoFondo": ("paleta_claro",),
    "abrirPuertaArriba": (_PRE, 731), "abrirPuertaAbajo": (_PRE, 732),
    "abrirPuertaBorde": ("sin_color",), "abrirPuertaTexto": ("blanco",),
    "cancelarArriba": (_CIC, "cancelarArriba"), "cancelarAbajo": (_CIC, "cancelarAbajo"),
    "cancelarBorde": ("sin_color",),
    "confirmarArriba": (_CIC, "confirmarArriba"), "confirmarAbajo": (_CIC, "confirmarAbajo"),
    "botonNaranjaArriba": (_PRE, 814), "botonNaranjaAbajo": (_PRE, 815),
    "textoSobreAccion": ("blanco",), "textoSobreAlarmaMedia": ("Colores", "textoPrimario"),
    "velo": ("Componentes/PanelModal.qml", 40), "veloSuave": ("Pantallas/OpcionesParametrosCiclo.qml", 814),
    "veloFuerte": ("Pantallas/OpcionesParametrosEquipo.qml", 666),
    "sombra": (_PRE, 694), "sombraSuave": (_GRA, 527),
    "textoNegro": (_PRE, "negro"), "textoPrograma": (_PRE, "programa"),
    "textoTitulo": (_PRE, "tituloAlarmas"), "textoEtiqueta": (_PRE, "etiqueta"),
    "textoUnidad": (_PRE, "unidad"), "textoPie": (_PRE, "textoPie"),
    "textoVersion": (_PRE, "versionTexto"), "textoReloj": (_CIC, "reloj"),
    "rotuloReloj": (_CIC, "rotuloReloj"), "textoVacio": (_PRE, "textoVacio"),
    "bordeSuave": (_PRE, "bordeSuave"), "divisorCiclo": (_PRE, "divisorCiclo"),
    "divisorParam": (_PRE, "divisorParam"), "divisorPie": (_PRE, "divisorPie"),
    "lineaAlarmas": (_PRE, "lineaAlarmas"), "insignia": (_PRE, "insignia"),
    "textoInsignia": ("blanco",), "iconoBarraMenu": ("svg", "assets/iconos/color/back_icon.svg"),
    "fondoCampo": ("blanco",), "iconoCampo": ("Colores", "bordeCampo"),
    "puertaCerradaTexto": ("Colores", "fondoBarraSuperior"),
    "puertaCerradaBorde": ("Colores", "fondoBarraSuperior"),
    "seleccionSutil": (_PRE, 1000), "puertaCerradaFondo": ("Componentes/IndicadorPuerta.qml", 37),
    "fondoSeccion": ("Componentes/SeccionEstadoSeguro.qml", 79),
    "peligroFuerte": ("Componentes/PanelEquipo.qml", 120),
    "naranjaTexto": (_PRE, "naranjaTexto"), "naranjaEstado": (_PRE, "naranjaEstado"),
    "fondoReposoBorde": ("solo_oscuro",),
}


def _claro_base(nombre: str, colores_base: dict):
    origen = _ORIGEN_CLARO[nombre]
    tipo = origen[0]
    if tipo == "Colores":
        return colores_base[origen[1]][0]
    if tipo == "blanco":
        return "#FFFFFFFF"
    if tipo == "sin_color":
        return _SIN_COLOR
    if tipo == "paleta_claro":
        return _paleta_pares()[nombre][0]
    if tipo == "solo_oscuro":
        return None
    if tipo == "svg":
        texto = (RAIZ / "src" / "autoclave" / "ui_qml" / origen[1]).read_text(encoding="utf-8")
        trazos = set(re.findall(r'(?:stroke|fill)="(#[0-9A-Fa-f]{6})"', texto))
        assert len(trazos) == 1, trazos
        return _norm(trazos.pop())
    texto = _git_base("src/autoclave/ui_qml/qml/" + tipo)
    if isinstance(origen[1], str):
        m = re.search(rf'property color {origen[1]}:\s*"({_HEX})"', texto)
        assert m, f"{tipo}: sin `property color {origen[1]}` en la base"
        return _norm(m.group(1))
    linea = texto.splitlines()[origen[1] - 1]
    return _literales(linea)[origen[2] if len(origen) > 2 else 0]


# ────────────────────────────── (b) formato ──────────────────────────────

def test_b_cada_propiedad_tiene_claro_y_oscuro_o_es_unica_justificada():
    props = _colores()
    assert len(props) > 100
    unicos = _unicos()
    assert unicos == set(_IGUALES), unicos ^ set(_IGUALES)
    texto = COLORES.read_text(encoding="utf-8")
    assert re.search(r"^\s*property bool oscuro: false\s*$", texto, re.M)   # claro por defecto


def _nombres_plan() -> set:
    """Nombres de la §3 de plan.md, con abreviaturas `aX/Y/Z` desplegadas."""
    texto = PLAN.read_text(encoding="utf-8")
    seccion = texto.split("## 3.")[1].split("## 4.")[0]
    nombres = set()
    for tok in re.findall(r"`([a-z][\w/]*)`", seccion):
        partes = tok.split("/")
        base = partes[0]
        nombres.add(base)
        for suf in partes[1:]:
            if suf.isdigit():
                nombres.add(re.sub(r"\d+$", suf, base))
            else:
                trozos = re.findall(r"[A-Z]?[a-z0-9]+", base)
                nombres.add("".join(trozos[:-1]) + suf)
    return nombres


def test_b_estan_todas_las_propiedades_de_la_seccion_3_del_plan():
    banderas = set(re.findall(r"property bool (\w+)", COLORES.read_text(encoding="utf-8")))
    faltan = _nombres_plan() - set(_colores()) - banderas
    assert not faltan, faltan


# ────────────────────────── (c) claros y oscuros ──────────────────────────

def test_c_claros_existentes_son_los_de_la_base_y_los_de_la_paleta():
    props = _colores()
    base = {}
    for linea in _git_base("src/autoclave/ui_qml/qml/Tema/Colores.qml").splitlines():
        m = re.match(rf'\s*readonly property color (\w+):\s*"({_HEX})"', linea)
        if m:
            base[m.group(1)] = (_norm(m.group(2)),)
    assert base
    for nombre, (claro,) in base.items():
        assert props[nombre][0] == claro, nombre
    for nombre, (claro, _osc) in _paleta_pares().items():
        if nombre.startswith("deslizador") or nombre == "exitoFondo":
            continue                     # OSC-01: la §7 trae claros de dashboard-reportes
        assert props[nombre][0] == claro, nombre


def test_c_claros_nuevos_son_los_literales_de_hoy():
    props = _colores()
    base = {}
    for linea in _git_base("src/autoclave/ui_qml/qml/Tema/Colores.qml").splitlines():
        m = re.match(rf'\s*readonly property color (\w+):\s*"({_HEX})"', linea)
        if m:
            base[m.group(1)] = (_norm(m.group(2)),)
    nuevos = set(props) - set(base)
    assert nuevos == set(_ORIGEN_CLARO), nuevos ^ set(_ORIGEN_CLARO)
    for nombre in sorted(nuevos):
        esperado = _claro_base(nombre, base)
        if esperado is not None:
            assert props[nombre][0] == esperado, (nombre, props[nombre][0], esperado)


def test_c_oscuros_salen_de_la_paleta_o_de_un_hallazgo():
    props = _colores()
    for nombre, (_claro, oscuro) in props.items():
        esperado = _oscuro_esperado(nombre, props)
        if esperado is None:
            html = (MOCKUPS / _OSCURO_MOCKUP[nombre]).read_text(encoding="utf-8").upper()
            assert oscuro[3:] in html, nombre
        else:
            assert oscuro == esperado, (nombre, oscuro, esperado)


def test_c_los_hallazgos_citados_estan_en_el_plan():
    plan = PLAN.read_text(encoding="utf-8")
    citados = set(re.findall(r"OSC-\d+", COLORES.read_text(encoding="utf-8")))
    citados |= {v for v in _IGUALES.values() if v.startswith("OSC-")}
    for h in sorted(citados):
        assert f"**{h}" in plan, h


# ─────────────────────────────── (d) alarmas ───────────────────────────────

def test_d_alarmas_iguales_en_los_dos_temas_y_las_de_la_paleta():
    props = _colores()
    texto = _paleta_texto()
    for nombre in ("alarmaAlta", "alarmaMedia", "alarmaBaja"):
        claro, oscuro = props[nombre]
        assert claro == oscuro, nombre
        m = re.search(rf"`{nombre}` ({_HEX})", texto)
        assert m and _norm(m.group(1)) == claro, nombre


# ─────────────────────────────── (e) contraste ─────────────────────────────

def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (3, 5, 7)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contraste(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


_FONDOS_8 = ("fondoTarjeta", "fondoSutil", "fondoPanel", "fondoElevado")
_PARES_8 = (
    [(t, f, 4.5) for t in ("textoPrimario", "textoSecundario", "textoGuia") for f in _FONDOS_8]
    + [(t, "fondoTarjeta", 4.5) for t in ("accionPrimarioTexto", "peligroTexto", "advertenciaTexto",
                                          "menuVerdeTexto", "menuNaranjaTexto")]
    + [(t, "fondoTarjeta", 3.0) for t in ("accionPrimario", "menuVerde", "menuAzul", "menuNaranja",
                                          "menuMorado", "advertencia")]
    + [(a, "fondoElevado", 3.0) for a in ("alarmaAlta", "alarmaMedia", "alarmaBaja")]
)


@pytest.mark.parametrize("texto,fondo,minimo", _PARES_8)
def test_e_contraste_de_la_seccion_8_en_oscuro(texto, fondo, minimo):
    props = _colores()
    c = _contraste(props[texto][1], props[fondo][1])
    assert c >= minimo, f"{texto} sobre {fondo}: {c:.2f} < {minimo}"


def test_e_campos_de_formulario_y_puerta_cerrada_tienen_claro_y_oscuro_legibles():
    """OSC-21 / OSC-22: el fondo de campo ya no es el blanco implícito en oscuro."""
    props = _colores()
    for nombre in ("fondoCampo", "iconoCampo", "puertaCerradaTexto", "puertaCerradaBorde"):
        claro, oscuro = props[nombre]
        assert claro != oscuro, nombre                         # tiene los dos temas
    assert props["fondoCampo"][0] == "#FFFFFFFF"               # claro = el blanco de hoy
    for texto, minimo in (("textoPrimario", 4.5), ("textoGuia", 4.5), ("textoSecundario", 4.5),
                          ("iconoCampo", 3.0), ("bordeCampo", 1.0)):
        c = _contraste(props[texto][1], props["fondoCampo"][1])
        assert c >= minimo, f"{texto} sobre fondoCampo (oscuro): {c:.2f} < {minimo}"
    # el borde del campo activo (acción) y el de error también se ven
    for texto in ("accionPrimario", "peligroTexto"):
        assert _contraste(props[texto][1], props["fondoCampo"][1]) >= 3.0, texto
    # «PUERTA CERRADA» (IndicadorPuerta): texto e ícono legibles sobre su fondo
    assert _contraste(props["puertaCerradaTexto"][1], props["puertaCerradaFondo"][1]) >= 4.5
    assert _contraste(props["puertaCerradaBorde"][1], props["puertaCerradaFondo"][1]) >= 3.0


# ────────────────── (a) sin literales de color fuera de Tema/ ──────────────────

# Archivos de los conjuntos B, C y D (plan.md §4) que aún tienen literales: cada
# implementador quita los suyos de aquí al migrarlos. La lista debe quedar vacía.
_PENDIENTES = {
}
# Excepciones permanentes (justificadas): ninguna por ahora.
_EXCEPCIONES: dict = {}

_NOMBRES = r"white|black|red|blue|green|yellow|gray|grey|orange|purple|cyan|magenta"


def _sin_comentarios(linea: str) -> str:
    return re.sub(r"(^|\s)//.*$", r"\1", linea)


def _literales_en(ruta: Path) -> list:
    hallados = []
    for i, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        codigo = _sin_comentarios(linea)
        if (re.search(r'"#[0-9A-Fa-f]{3,8}"', codigo)
                or re.search(r"Qt\.(rgba|rgb|hsla|hsva|hsl|hsv)\(\s*[\d.]", codigo)
                or re.search(rf'"({_NOMBRES})"', codigo)):
            hallados.append(f"{i}: {linea.strip()}")
    return hallados


def _qml_fuera_de_tema():
    return sorted(p for p in QML.rglob("*.qml") if "Tema" not in p.relative_to(QML).parts)


def test_a_sin_literales_de_color_fuera_de_tema():
    errores = {}
    for ruta in _qml_fuera_de_tema():
        rel = ruta.relative_to(QML).as_posix()
        if rel in _PENDIENTES or rel in _EXCEPCIONES:
            continue
        lits = _literales_en(ruta)
        if lits:
            errores[rel] = lits
    assert not errores, json.dumps(errores, ensure_ascii=False, indent=1)


def test_a_la_lista_de_pendientes_no_tiene_archivos_ya_limpios():
    for rel in sorted(_PENDIENTES):
        ruta = QML / rel
        assert ruta.exists(), f"{rel} ya no existe: quitarlo de _PENDIENTES"
        assert _literales_en(ruta), f"{rel} ya no tiene literales: quitarlo de _PENDIENTES"


def test_r7_solo_colores_y_las_raices_nombran_el_tema():
    raices = {"Main.qml", "InstalacionVentana.qml", "ReposoInstalacionVentana.qml",
              "NuevoUsuarioHost.qml"}
    for ruta in QML.rglob("*.qml"):
        rel = ruta.relative_to(QML).as_posix()
        codigo = "\n".join(_sin_comentarios(l) for l in ruta.read_text(encoding="utf-8").splitlines())
        if rel in raices:
            assert 'Binding { target: Colores; property: "oscuro"; value: Apariencia.oscuro }' in codigo, rel
            continue
        if rel == "Tema/Colores.qml":
            continue
        assert "Apariencia" not in codigo, rel
        assert not re.search(r"Colores\.oscuro\b", codigo), rel


# ─────────────────────── persistencia y endpoint /theme ───────────────────────

def test_config_tema_por_defecto_invalido_y_guardado(tmp_path):
    ruta = tmp_path / "tema.json"
    c = ConfigTema(ruta)
    assert c.leer() == "claro"                      # ausente
    ruta.write_text("no es json", encoding="utf-8")
    assert c.leer() == "claro"                      # ilegible
    ruta.write_text(json.dumps({"tema": "azul"}), encoding="utf-8")
    assert c.leer() == "claro"                      # inválido
    assert c.guardar("oscuro") == "oscuro" and c.leer() == "oscuro"
    with pytest.raises(ValueError):
        c.guardar("azul")
    assert c.leer() == "oscuro"


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.config_tema = ConfigTema(tmp_path / "tema.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    return TestClient(srv.app), srv, ctx, cabecera


@pytest.mark.parametrize("rol", ["admin", "ingeniero"])
def test_theme_admin_e_ingeniero_aun_en_ciclo_sin_bitacora(api, rol):
    client, srv, ctx, cabecera = api
    assert client.get("/theme").json() == {"tema": "claro"}
    antes = len(ctx.db.get_auditoria(limite=50))
    r = client.put("/theme", headers=cabecera(srv, rol), json={"tema": "oscuro"})
    assert r.status_code == 200 and r.json() == {"ok": True, "tema": "oscuro"}
    assert client.get("/theme").json() == {"tema": "oscuro"}
    assert len(ctx.db.get_auditoria(limite=50)) == antes      # no va a la bitácora


def test_theme_sin_sesion_rol_o_valor_invalido(api):
    client, srv, ctx, cabecera = api
    assert client.put("/theme", json={"tema": "oscuro"}).status_code == 401
    assert client.put("/theme", headers=cabecera(srv, "ingeniero"),
                      json={"tema": "azul"}).status_code == 422
    assert client.put("/theme", headers=cabecera(srv, "tecnico"),
                      json={"tema": "oscuro"}).status_code == 403
    assert client.get("/theme").json() == {"tema": "claro"}


# ─────────────────────── singleton Apariencia y controlador ───────────────────────

def _app_qt():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def test_apariencia_claro_por_defecto_invalido_conserva_y_emite_senal():
    _app_qt()
    from autoclave.ui_qml.bridge.apariencia_qml import AparienciaQml
    a = AparienciaQml(consultar=lambda: None)
    senales = []
    a.temaChanged.connect(lambda: senales.append(a.tema))
    assert a.tema == "claro" and a.oscuro is False
    a.aplicar(None)
    a.aplicar({"tema": "azul"})
    a.aplicar("basura")
    assert a.tema == "claro" and senales == []
    a.aplicar({"tema": "oscuro"})
    assert a.oscuro is True and senales == ["oscuro"]
    a.aplicar({"tema": "oscuro"})
    assert senales == ["oscuro"]                     # sin cambio, sin señal
    a.aplicar({"tema": "claro"}, tema_al_pedir="claro")   # consulta vieja: se descarta
    assert a.tema == "oscuro"
    assert a.fijar("azul") is False and a.tema == "oscuro"


class _SesionTema:
    def __init__(self, tema="claro", ok=True):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.R, self.tema, self.ok, self.enviados = Resultado, tema, ok, []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            return self.R("ok", {"/theme": {"tema": self.tema}}.get(ruta, {}), 200)
        if ruta == "/theme" and self.ok:
            self.tema = cuerpo["tema"]
            return self.R("ok", {"ok": True, "tema": self.tema}, 200)
        return self.R("rol_sin_permiso", {}, 403)


def test_controlador_fija_el_tema_y_cambia_la_ventana_al_instante():
    _app_qt()
    from autoclave.ui_qml.bridge import apariencia_qml
    from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController
    apariencia_qml.instancia.fijar("claro")
    s = _SesionTema()
    c = ParametrosEquipoController(sesion=s, perfil=lambda: None)
    c.cargar()
    assert c.tema == "claro"
    try:
        assert c.fijarTema("oscuro") is True
        assert ("PUT", "/theme", {"tema": "oscuro"}) in s.enviados
        assert c.tema == "oscuro" and apariencia_qml.instancia.oscuro is True
        rechazo = _SesionTema(ok=False)
        c2 = ParametrosEquipoController(sesion=rechazo, perfil=lambda: None)
        apariencia_qml.instancia.fijar("claro")
        assert c2.fijarTema("oscuro") is False
        assert apariencia_qml.instancia.tema == "claro"     # rechazado: no cambia
    finally:
        apariencia_qml.instancia.fijar("claro")


def test_controlador_tema_invalido_del_backend_queda_desconocido():
    _app_qt()
    from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController
    c = ParametrosEquipoController(sesion=_SesionTema(tema="azul"), perfil=lambda: None)
    c.cargar()
    assert c.tema == ""


def test_textos_del_selector_en_los_dos_idiomas():
    from autoclave import i18n
    for lang, esperados in (("es", ("Tema", "Claro", "Oscuro")), ("en", ("Theme", "Light", "Dark"))):
        assert tuple(i18n.traducir(f"opciones.{k}", lang, None) for k in
                     ("equipo_tema", "equipo_tema_claro", "equipo_tema_oscuro")) == esperados
        assert "{opcion}" not in i18n.traducir("opciones.equipo_tema_confirmar", lang,
                                               {"opcion": "x"})


# ─────────────────────── QML: cambio en vivo y carga ───────────────────────

_SCRIPT_QML = textwrap.dedent(r'''
    import json, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge import apariencia_qml, i18n_qml, unidades_qml
    app = QGuiApplication(sys.argv)
    for m in (apariencia_qml, i18n_qml):
        m.instancia._consultar = lambda: None
    unidades_qml.instancia._consultar = lambda: None
    apariencia_qml.instancia.fijar("claro")
    motor = QQmlEngine()
    motor.addImportPath(str(QML_DIR))
    qml = b"""
    import QtQuick
    import Tema
    import Autoclave.Apariencia
    import "Componentes"
    import "Pantallas"
    Item {
        width: 600; height: 900
        Binding { target: Colores; property: "oscuro"; value: Apariencia.oscuro }
        property color fondo: Colores.fondoTarjeta
        property color alarma: Colores.alarmaAlta
        property bool gradiente: Colores.fondoGradiente
        FondoApp {}
        Reposo { anchors.fill: parent }
        BarraSuperior { width: 600; height: 120 }
        BarraInferiorMenu { escala: 0.5 }
        InsigniaCampana { width: 26; height: 25; conteo: 3 }
    }
    """
    comp = QQmlComponent(motor)
    comp.setData(qml, QUrl.fromLocalFile(str(QML_DIR) + "/prueba_tema.qml"))
    obj = comp.create()
    if obj is None:
        print("RESULTADO=" + json.dumps({"errores": [e.toString() for e in comp.errors()]}))
        sys.exit(0)
    r = {"claro": [obj.property("fondo").name(), obj.property("alarma").name(),
                   obj.property("gradiente")]}
    apariencia_qml.instancia.fijar("oscuro")
    app.processEvents()
    r["oscuro"] = [obj.property("fondo").name(), obj.property("alarma").name(),
                   obj.property("gradiente")]
    apariencia_qml.instancia.fijar("claro")
    app.processEvents()
    r["vuelta"] = [obj.property("fondo").name(), obj.property("alarma").name(),
                   obj.property("gradiente")]
    print("RESULTADO=" + json.dumps(r))
''')


def test_qml_el_tema_cambia_en_vivo_y_los_componentes_cargan():
    pytest.importorskip("PySide6")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_QML], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    r = json.loads(linea[len("RESULTADO="):])
    assert "errores" not in r, r
    props = _colores()
    hexa = lambda h: "#" + h[3:].lower()              # noqa: E731  (#AARRGGBB → #rrggbb)
    assert r["claro"] == [hexa(props["fondoTarjeta"][0]), hexa(props["alarmaAlta"][0]), False]
    assert r["oscuro"] == [hexa(props["fondoTarjeta"][1]), hexa(props["alarmaAlta"][1]), True]
    assert r["vuelta"] == r["claro"]
