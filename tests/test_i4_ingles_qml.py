"""I4 (tanda 6), parte QML: textos que Python entrega a QML en el idioma y la
unidad vigentes, idioma seguido desde el backend en cada ventana y ninguna
pantalla QML con literales visibles fuera del catálogo (lista blanca justificada)."""

import re
from pathlib import Path

import pytest

from autoclave import i18n

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


@pytest.fixture
def ingles():
    i18n.fijar_idioma("en")
    yield
    i18n.fijar_idioma("es")


# ── Literales QML: TODA cadena entre comillas, no solo ciertas propiedades ──

_CADENA = re.compile(r'"((?:[^"\\]|\\.)*)"')

# archivo -> {literal: justificación}
_LISTA_BLANCA = {
    "Pantallas/IntroArranque.qml": {
        "Tecnología para esterilizar.": "D-06/ARR-02: eslogan de marca, siempre en español",
        "Ingeniería para responder.": "D-06/ARR-02: eslogan de marca, siempre en español",
        "Software v": "rótulo de versión, igual en es y en",
    },
    "Pantallas/Opciones.qml": {
        "abandono de la sección": "motivo de auditoría enviado a /io/test/exit; no se muestra",
    },
    "Pantallas/OpcionesEntradasSalidas.qml": {
        "abandono de la sección": "motivo de auditoría enviado a /io/test/exit; no se muestra",
        "inactividad de la interfaz": "motivo de auditoría enviado a /io/test/exit; no se muestra",
        "salida solicitada": "motivo de auditoría enviado a /io/test/exit; no se muestra",
        " kPa": "E/S muestra unidades crudas del sensor (regla 0.5: exenta de U1)",
    },
    "Pantallas/OpcionesFechaHora.qml": {
        "dddd d MMMM yyyy": "patrón de Qt.formatDate; el idioma lo pone el locale",
    },
    "Pantallas/OpcionesParametrosEquipo.qml": {
        "Español": "endónimo: cada idioma se nombra en su propia lengua",
        "English": "endónimo: cada idioma se nombra en su propia lengua",
    },
    "Pantallas/OpcionesBitacora.qml": {
        "&amp;": "escape HTML", "&lt;": "escape HTML",
    },
    "Pantallas/OpcionesParametrosCiclo.qml": {
        " <font color='#808080'>": "marcado HTML", "</font>": "marcado HTML",
    },
}
_EXCLUIDOS = ("Pruebas/",)


def _es_texto(t: str) -> bool:
    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,}", t):
        return False
    if re.fullmatch(r"[A-Za-z0-9_]+", t):          # identificadores, objectName, claves
        return False
    if re.fullmatch(r"[a-z0-9_.:/#\-]+", t):       # claves de catálogo, rutas, colores
        return False
    if re.fullmatch(r"#[0-9A-Fa-f]{3,8}|[A-Z0-9_-]+", t):   # colores, códigos de alarma
        return False
    if re.fullmatch(r"\{[a-z_]+\}", t):            # marcadores {minimo}
        return False
    return True


def _literales():
    for ruta in sorted(QML.rglob("*.qml")):
        rel = ruta.relative_to(QML).as_posix()
        if rel.startswith(_EXCLUIDOS):
            continue
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            codigo = re.sub(r"(^|\s)//.*$", "", linea)
            if codigo.strip().startswith(("import ", "console.")):
                continue
            for m in _CADENA.finditer(codigo):
                t = m.group(1)
                if not _es_texto(t) or t in _LISTA_BLANCA.get(rel, {}):
                    continue
                if re.search(r"I18n\.\w+\(\s*$", codigo[:m.start()]):
                    continue
                yield f"{rel}:{n}: {t}"


def test_ninguna_cadena_qml_visible_fuera_del_catalogo():
    encontrados = list(_literales())
    assert encontrados == [], "\n".join(encontrados)


def test_la_lista_blanca_no_tiene_entradas_muertas():
    for rel, permitidos in _LISTA_BLANCA.items():
        texto = (QML / rel).read_text(encoding="utf-8")
        for literal in permitidos:
            assert f'"{literal}"' in texto, f"{rel}: '{literal}' ya no existe; quítalo de la lista"


def test_ninguna_cadena_qml_tiene_saltos_de_linea_crudos():
    for ruta in QML.rglob("*.qml"):
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            assert not re.search(r'\?\s*"\s*$', linea), f"{ruta.name}:{n}"


def test_toda_clave_qml_existe_en_es_y_en():
    claves = set()
    for ruta in QML.rglob("*.qml"):
        claves |= set(re.findall(r'I18n\.t\("([a-z0-9_.]+)"', ruta.read_text(encoding="utf-8")))
    claves = {c for c in claves if not c.endswith((".", "_"))}      # prefijos concatenados
    faltan = [(c, l) for c in sorted(claves) for l in i18n.IDIOMAS if not i18n.existe(c, l)]
    assert faltan == []


def test_seguir_editando_del_catalogo(ingles):
    texto = (QML / "Pantallas" / "NuevoUsuario.qml").read_text(encoding="utf-8")
    assert 'I18n.t("usuarios.seguir_editando", I18n.lang)' in texto
    assert i18n.t("usuarios.seguir_editando") == "Keep editing"


# ── Nombres de programa en el idioma vigente ───────────────────────────

from autoclave.ui_qml.domain.nombres_ciclo import nombre_programa  # noqa: E402


def test_nombre_programa_usa_nombres_del_backend(ingles):
    assert nombre_programa("Líquidos", {"es": "Líquidos", "en": "Liquids"}) == "Liquids"


def test_nombre_programa_reconoce_el_de_fabrica_guardado_en_espanol(ingles):
    assert nombre_programa("Líquidos") == "Liquids"
    assert nombre_programa("LÍQUIDOS") == "LIQUIDS"


def test_nombre_programa_renombrado_queda_igual(ingles):
    assert nombre_programa("Mi programa") == "Mi programa"
    assert nombre_programa(None) is None
    assert nombre_programa("") == ""


def test_nombre_programa_en_espanol_no_cambia():
    assert nombre_programa("Líquidos", {"es": "Líquidos", "en": "Liquids"}) == "Líquidos"
    assert nombre_programa("Líquidos") == "Líquidos"


def test_pantalla_ciclo_muestra_el_programa_en_ingles(ingles):
    from autoclave.ui_qml.domain.pantalla_ciclo import parametros_de_ciclo
    d = parametros_de_ciclo({"name": "Líquidos", "nombres": {"es": "Líquidos", "en": "Liquids"},
                             "parameters": {}})
    assert d["programa"] == "LIQUIDS"


def test_historial_muestra_el_programa_de_fabrica_en_ingles(ingles):
    from autoclave.ui_qml.domain.resumen_sistema import ciclo_presentable
    assert ciclo_presentable({"id": 1, "programa_nombre": "Líquidos"})["programa_nombre"] == "Liquids"


def test_selector_nombre_e_idioma_y_temperatura_en_unidad_vigente(ingles, monkeypatch):
    from autoclave.ui_qml.bridge import selector_ciclo
    from autoclave.ui_qml.domain import pantalla_ciclo
    fila = {"cycle_id": "liquidos", "nombre": "Líquidos",
            "nombres": {"es": "Líquidos", "en": "Liquids"}, "temperatura": 121, "tiempo": 15}
    assert selector_ciclo.fila_presentable(fila)["nombre"] == "Liquids"
    assert selector_ciclo.fila_presentable(fila)["parametros"].startswith("121 °C")
    monkeypatch.setattr(pantalla_ciclo, "_vigentes", lambda: ("F", "psi", None))
    assert selector_ciclo.fila_presentable(fila)["parametros"].startswith("249.8 °F")


# ── Motivo de NO ABRIR en el idioma vigente ────────────────────────────

def test_motivo_no_abrir_toma_el_texto_del_idioma_vigente(ingles):
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    s = UiBridge._seguridad_de({"no_abrir": True, "motivo": "Temperatura alta",
                                "motivo_textos": {"es": "Temperatura alta", "en": "High temperature"}})
    assert s["motivo_textos"]["en"] == "High temperature"
    s2 = UiBridge._seguridad_de({"no_abrir": True, "motivo": "Temperatura alta",
                                 "motivo_textos": "basura"})
    assert s2["motivo_textos"] == {} and s2["motivo"] == "Temperatura alta"


def test_motivo_no_abrir_sin_conexion_queda_vacio():
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    s = UiBridge._seguridad_de({})
    assert s["no_abrir"] is True and s["motivo_textos"] == {}


# ── Cada ventana sigue el idioma del backend (GET /language) ───────────

def test_i18n_qml_aplica_el_idioma_del_backend():
    from autoclave.ui_qml.bridge.i18n_qml import I18nQml
    q = I18nQml(consultar=lambda: {"idioma": "en"})
    try:
        q.aplicar({"idioma": "en"}, "es")
        assert i18n.idioma() == "en"
        q.aplicar(None, "en")                       # sin respuesta: se conserva
        assert i18n.idioma() == "en"
        q.aplicar({"idioma": "fr"}, "en")           # inválido: se conserva
        assert i18n.idioma() == "en"
    finally:
        i18n.fijar_idioma("es")


def test_i18n_qml_descarta_respuesta_vieja_si_cambio_localmente():
    from autoclave.ui_qml.bridge.i18n_qml import I18nQml
    q = I18nQml()
    try:
        i18n.fijar_idioma("en")                     # PUT local mientras la consulta volaba
        q.aplicar({"idioma": "es"}, "es")
        assert i18n.idioma() == "en"
    finally:
        i18n.fijar_idioma("es")


def test_i18n_qml_no_sondea_hasta_que_lo_pide_un_motor():
    from autoclave.ui_qml.bridge import i18n_qml
    assert i18n_qml.I18nQml()._timer.isActive() is False
    assert i18n_qml.INTERVALO_MS == 3000


def test_bloqueo_por_sonda_sigue_leyendo_el_texto_en_espanol():
    """SAF-01 (I4 QML): SeccionEstadoSeguro decide el botón de sondas con
    indexOf("Principal") sobre el motivo de bloqueo; ese motivo NO se traduce
    hasta que el backend exponga un código."""
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    s = UiBridge._seguridad_de({"estado_seguro": {"bloqueado_motivo": "Sonda Principal sin lectura"}})
    assert "Principal" in s["es_bloqueado"]
    qml = (QML / "Componentes" / "SeccionEstadoSeguro.qml").read_text(encoding="utf-8")
    assert 'bloqueoMotivo.indexOf("Principal")' in qml
