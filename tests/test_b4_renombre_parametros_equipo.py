"""B4 (tanda 4): "Parámetros del sistema" pasa a "Parámetros del equipo"
("Equipment parameters"). Solo texto visible; las claves/rutas no cambian."""

import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ANTIGUO = re.compile(r"par[aá]metros del sistema|system parameters", re.IGNORECASE)


def test_texto_visible_en_es_y_en():
    base = RAIZ / "src" / "autoclave" / "i18n"
    es = json.loads((base / "es.json").read_text(encoding="utf-8"))
    en = json.loads((base / "en.json").read_text(encoding="utf-8"))
    assert es["opciones"]["secciones"]["parametros_sistema"] == "Parámetros del equipo"
    assert en["opciones"]["secciones"]["parametros_sistema"] == "Equipment parameters"


def test_la_clave_interna_no_cambia():
    # compatibilidad: identificadores y claves i18n siguen igual
    src = (RAIZ / "src" / "autoclave" / "ui_qml" / "domain" / "permisos_opciones.py").read_text(encoding="utf-8")
    assert "parametros_sistema" in src


def test_no_quedan_apariciones_del_nombre_antiguo_en_codigo_ni_vistas():
    sospechosos = []
    for carpeta in ("src", "tools"):
        for ruta in (RAIZ / carpeta).rglob("*"):
            if ruta.suffix in (".py", ".qml", ".json") and ruta.is_file():
                if ANTIGUO.search(ruta.read_text(encoding="utf-8", errors="ignore")):
                    sospechosos.append(str(ruta.relative_to(RAIZ)))
    assert not sospechosos, sospechosos


def test_el_menu_pyside_usa_el_nombre_nuevo():
    texto = (RAIZ / "src" / "autoclave" / "ui_pyside" / "views" / "admin_menu.py").read_text(encoding="utf-8")
    assert "Parámetros del equipo" in texto
