"""I2 (tanda 5): ninguna pantalla QML conserva textos visibles fijos en español
fuera del catálogo i18n. Lista blanca justificada abajo."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

# Propiedades que se muestran en pantalla
_VISIBLES = r"(text|texto|placeholderText|marcador|titulo|mensaje|descripcion|rotulo|textoConfirmar|textoCancelar)"
_LITERAL = re.compile(_VISIBLES + r"\s*:\s*\"([^\"]*[A-Za-zÁÉÍÓÚáéíóúñÑ¿¡]{3,}[^\"]*)\"")

# archivo -> literales permitidos y por qué
_LISTA_BLANCA = {
    # D-06 / ARR-02: el eslogan es marca y va siempre en español
    "Pantallas/IntroArranque.qml": {"Tecnología para esterilizar.", "Ingeniería para responder."},
    # "LOGIN" ya no es literal; se deja vacía por si aparece de nuevo
}
# Directorios de galerías y pruebas manuales: no son pantallas del equipo
_EXCLUIDOS = ("Pruebas/",)


def _literales():
    for ruta in sorted(QML.rglob("*.qml")):
        rel = ruta.relative_to(QML).as_posix()
        if rel.startswith(_EXCLUIDOS):
            continue
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linea.split("//", 1)[0]
            for m in _LITERAL.finditer(codigo):
                texto = m.group(2)
                if texto in _LISTA_BLANCA.get(rel, set()):
                    continue
                # identificadores (claves, nombres de campo): sin espacios ni mayúsculas iniciales de frase
                if re.fullmatch(r"[a-z0-9_.]+", texto):
                    continue
                yield f"{rel}:{n}: {texto}"


def test_ninguna_pantalla_qml_tiene_literales_visibles_en_espanol():
    encontrados = list(_literales())
    assert encontrados == [], "\n".join(encontrados)


def test_la_barra_superior_toma_los_meses_del_catalogo():
    texto = (QML / "Componentes" / "BarraSuperior.qml").read_text(encoding="utf-8")
    assert 'I18n.valor("fecha.meses", I18n.lang)' in texto
