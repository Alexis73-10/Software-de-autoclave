# tests/test_t21_textos_caben_qml.py
#
# T21 (FC-10, planeacion_fin_de_ciclo.md): ningún texto se recorta ni se sale
# de su botón (D8-5.4), en es y en, a 1024 px de ancho (la pantalla real más
# angosta). En la línea de test_u10a/test_u10b (tests/helpers/textos_caben_qml.py),
# cubre lo que esas pruebas no ven porque está oculto o depende del estado:
#
#   1. Componentes de ancho fijo cargados solos con TODOS los textos reales que
#      reciben (sacados del QML de cada uso): botones de DialogoConfirmacion,
#      botón de cierre de PanelModal (y PanelEquipo / PanelNotificaciones),
#      BotonFormulario con ancho fijo y los botones de SeccionEstadoSeguro en
#      el contenedor más angosto (tarjeta de Ciclo en curso). Se aceptan la
#      reducción de letra (HorizontalFit) si no baja de Escala.fuenteMinima y
#      nada más.
#   2. Cada pantalla con diálogos: cada DialogoConfirmacion y PanelModal oculto
#      se abre y se revisa solo, sin ningún problema (ni siquiera reducción).
#   3. «Confirmar y llevar a estado seguro» (el caso que motivó FC-10) cabe a
#      su tamaño de letra, sin reducir, en el ModalConfirmacion que reemplazó
#      al diálogo en Ciclo en curso (FC-09, ola 2), como título; y en el botón
#      de SeccionEstadoSeguro.
#   Los ModalConfirmacion (título, acción y «Volver») se cargan con cada uso.

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from tests.helpers.textos_caben_qml import RAIZ, revisar, revisar_componentes  # noqa: E402

IDIOMAS = ("es", "en")
ANCHO = 1024
QML_DIR = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


# ── extracción de los textos reales desde el QML ───────────────────────────

def _bloques(tipo: str):
    """(archivo, texto del bloque) de cada `tipo {` en el QML de la aplicación."""
    for qml in sorted(QML_DIR.rglob("*.qml")):
        if qml.parent.name == "Pruebas":
            continue
        src = qml.read_text(encoding="utf-8")
        for m in re.finditer(r"\b" + tipo + r"\s*\{", src):
            i, prof, en_cadena = m.end(), 1, False
            while i < len(src) and prof:
                c = src[i]
                if c == '"' and src[i - 1] != "\\":
                    en_cadena = not en_cadena
                elif not en_cadena and c == "{":
                    prof += 1
                elif not en_cadena and c == "}":
                    prof -= 1
                i += 1
            yield qml.relative_to(QML_DIR).as_posix(), src[m.start():i]


def _expresion(bloque: str, propiedad: str) -> str:
    """Expresión de `propiedad:` (puede seguir en las líneas siguientes)."""
    m = re.search(r"^\s*" + re.escape(propiedad) + r"\s*:(.*)$", bloque, re.M)
    if not m:
        return ""
    lineas = [m.group(1)]
    for linea in bloque[m.end():].splitlines()[1:]:
        if re.match(r"^\s*([\w.]+\s*:|on\w+|\}|[A-Z]\w*\s*\{|function\b)", linea):
            break
        lineas.append(linea)
    return "\n".join(lineas)


def _claves(expr: str) -> list[str]:
    return re.findall(r'(?:I18n\.t|raiz\.texto)\("([\w.]+)"', expr)


def _texto(clave: str, idioma: str) -> str:
    from autoclave import i18n
    i18n.cargar()
    return i18n.t(clave, idioma)


def _casos():
    casos = []
    # DialogoConfirmacion: cada combinación de sus textos de botón por uso
    for archivo, b in _bloques("DialogoConfirmacion"):
        confirmar = _claves(_expresion(b, "textoConfirmar")) or [None]
        cancelar = _claves(_expresion(b, "textoCancelar")) or [None]
        for c in confirmar:
            for k in cancelar:
                props = [f'textoConfirmar: I18n.t("{c}", I18n.lang)' if c else "",
                         f'textoCancelar: I18n.t("{k}", I18n.lang)' if k else ""]
                casos.append({"id": f"DialogoConfirmacion {archivo} {c} / {k}",
                              "claves": [x for x in (c, k) if x],
                              "qml": "DialogoConfirmacion { visible: true; mensaje: \"?\"; "
                                     + "; ".join(p for p in props if p) + " }",
                              "ancho": ANCHO, "alto": 520})
    # ModalConfirmacion (FC-09): título y botón de acción de cada uso
    for archivo, b in _bloques("ModalConfirmacion"):
        titulo = _claves(_expresion(b, "titulo"))
        accion = _claves(_expresion(b, "textoAccion")) or [None]
        for t in titulo or [None]:
            for a in accion:
                props = [f'titulo: I18n.t("{t}", I18n.lang)' if t else "",
                         f'textoAccion: I18n.t("{a}", I18n.lang)' if a else ""]
                casos.append({"id": f"ModalConfirmacion {archivo} {t} / {a}",
                              "claves": [x for x in (t, a) if x],
                              "qml": "ModalConfirmacion { visible: true; cuerpo: \"?\"; "
                                     + "; ".join(p for p in props if p) + " }",
                              "ancho": ANCHO, "alto": 1638})
    # botón de cierre de PanelModal y de los paneles que lo usan
    vistos = set()
    for tipo in ("PanelModal", "PanelEquipo", "PanelNotificaciones"):
        for archivo, b in _bloques(tipo):
            for c in _claves(_expresion(b, "textoCerrar")):
                if c in vistos:
                    continue
                vistos.add(c)
                casos.append({"id": f"PanelModal {archivo} {c}", "claves": [c],
                              "qml": f'PanelModal {{ visible: true; altoTarjeta: Escala.px(360); '
                                     f'textoCerrar: I18n.t("{c}", I18n.lang) }}',
                              "ancho": ANCHO, "alto": 520})
    # BotonFormulario con ancho fijo de diseño
    for archivo, b in _bloques("BotonFormulario"):
        w = re.fullmatch(r"\s*Escala\.px\((\d+)\)\s*", _expresion(b, "width"))
        if not w:
            continue
        for c in _claves(_expresion(b, "texto")):
            casos.append({"id": f"BotonFormulario {archivo} {c} ({w.group(1)})", "claves": [c],
                          "qml": f'BotonFormulario {{ width: Escala.px({w.group(1)}); '
                                 f'texto: I18n.t("{c}", I18n.lang) }}',
                          "ancho": ANCHO, "alto": 100})
    # SeccionEstadoSeguro en la tarjeta de Ciclo en curso (920 de diseño, la
    # más angosta de sus tres usos): confirmación pendiente, en curso con el
    # indicador, y detenido por la sonda (botón de asignar sonda)
    puente = ('QtObject { property bool connected: true; property string estadoTarjeta: "ok"; '
              'property bool paroActivo: false; property bool estadoSeguroRequiereConfirmacion: %s; '
              'property bool estadoSeguroActivo: %s; property bool noAbrir: false; '
              'property bool modoPrueba: false; property string estadoSeguroCausa: ""; '
              'property string estadoSeguroBloqueadoMotivo: %s; property string estadoSeguroBloqueadoClave: ""; '
              'property bool estadoSeguroBloqueoPorSonda: %s }')
    comandos = 'QtObject { property bool ocupado: false; property string mensaje: "" }'
    for nombre, args, claves in (
            ("confirmar", ("true", "false", '""', "false"), ["sistema.confirmar_estado_seguro"]),
            ("en_curso", ("false", "true", '"x"', "true"),
             ["sistema.estado_seguro_en_curso_boton", "sistema.asignar_sonda_principal"])):
        casos.append({"id": f"SeccionEstadoSeguro {nombre}", "claves": claves,
                      "qml": f"SeccionEstadoSeguro {{ width: Escala.px(920); grupo: \"emergencia\"\n"
                             f"puente: {puente % args}\ncomandos: {comandos}\n}}",
                      "ancho": ANCHO, "alto": 700})
    return casos


CASOS = _casos()


def test_se_encontraron_los_usos():
    tipos = {c["id"].split()[0] for c in CASOS}
    assert tipos == {"DialogoConfirmacion", "ModalConfirmacion", "PanelModal", "BotonFormulario",
                     "SeccionEstadoSeguro"}
    assert any("ciclo.modal_estado_seguro_titulo" in c["claves"] and c["id"].startswith("ModalConfirmacion")
               for c in CASOS)
    assert len(CASOS) > 30


@pytest.fixture(scope="module", params=IDIOMAS)
def componentes(request):
    return request.param, revisar_componentes(CASOS, request.param, ANCHO)


def test_componentes_cargan_sin_avisos(componentes):
    _, r = componentes
    assert r["avisos"] == []


def test_componentes_muestran_sus_textos_reales(componentes):
    idioma, r = componentes
    for caso, rc in zip(CASOS, r["casos"]):
        for c in caso["claves"]:
            assert _texto(c, idioma) in rc["vistos"], (caso["id"], rc["vistos"])


def test_ningun_texto_de_componente_se_sale_ni_se_recorta(componentes):
    # la reducción de letra («encogido») se acepta aquí; su mínimo, abajo
    _, r = componentes
    malos = [(rc["id"], p) for rc in r["casos"] for p in rc["problemas"] if p["tipo"] != "encogido"]
    assert malos == []


def test_la_letra_reducida_no_baja_del_minimo_legible(componentes):
    _, r = componentes
    minimo = r["fuenteMinima"]
    bajos = [(rc["id"], f) for rc in r["casos"] for f in rc["fuentes"] if f["px"] < minimo]
    assert bajos == []


def test_confirmar_y_llevar_a_estado_seguro_cabe_sin_reducir(componentes):
    # FC-10: en el modal de estado seguro (título) y en SeccionEstadoSeguro
    idioma, r = componentes
    revisados = 0
    for caso, rc in zip(CASOS, r["casos"]):
        clave = next((c for c in ("ciclo.modal_estado_seguro_titulo", "sistema.confirmar_estado_seguro")
                      if c in caso["claves"]), None)
        if clave is not None:
            texto = _texto(clave, idioma)
            revisados += 1
            f = next(f for f in rc["fuentes"] if f["texto"] == texto)
            assert f["px"] == f["pedido"], (caso["id"], f)
            assert rc["problemas"] == [], caso["id"]
    assert revisados


# ── pantallas: cada diálogo oculto, abierto y revisado solo ────────────────

PANTALLAS_CON_DIALOGOS = sorted({
    Path(archivo).stem for tipo in ("DialogoConfirmacion", "ModalConfirmacion", "PanelModal")
    for archivo, _ in _bloques(tipo) if archivo.startswith("Pantallas/")
} | {"MenuPrincipal"})
TIPOS_DIALOGO = ("DialogoConfirmacion", "ModalConfirmacion", "PanelModal", "PanelEquipo",
                 "PanelNotificaciones")


@pytest.fixture(scope="module", params=[(p, i) for p in PANTALLAS_CON_DIALOGOS for i in IDIOMAS],
                ids=lambda c: f"{c[0]}-{c[1]}")
def pantalla(request):
    nombre, idioma = request.param
    return nombre, revisar(nombre, idioma, ANCHO, 1638, sesion="ingeniero", dialogos=TIPOS_DIALOGO)


def test_dialogos_de_la_pantalla_sin_textos_fuera_ni_reducidos(pantalla):
    nombre, r = pantalla
    revisados = [d for d in r["dialogos"] if d["visible"]]
    assert revisados, nombre
    malos = [(d["dialogo"], d["nombre"], p) for d in revisados for p in d["problemas"]]
    assert malos == [], nombre
