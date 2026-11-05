# Tanda 27 (paso 3): no quedan rastros del ESP32 ni del enlace serial en el
# código, las pruebas, las herramientas, el empaquetado, CLAUDE.md ni los
# documentos vigentes. Equivale a
#   rg -i "esp32|pyserial|serial_link|\.ino\b"
# sobre esas rutas, con la lista EXPLÍCITA de excepciones de abajo
# (docs/informes/tanda27/inventario_esp32.md, sección 6). `serial_number`,
# la «trama AI vencida» del Modbus y los campos `adc_*` no coinciden con el
# patrón.

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PATRON = re.compile(r"esp32|pyserial|serial_link|\.ino\b", re.IGNORECASE)

# Rutas revisadas (carpetas y archivos sueltos de la raíz).
CARPETAS = ("src", "tests", "tools", "packaging", "docs")
ARCHIVOS_RAIZ = ("CLAUDE.md", "pyproject.toml")
PATRON_RAIZ = "requirements*"

# Excepciones explícitas (relativas a la raíz, con «/»).
ARCHIVOS_EXCEPTUADOS = {
    "tests/test_t27_sin_esp32.py",          # esta prueba
    "tests/test_t20_s2_retiro_serial.py",   # prueba del retiro: nombra lo retirado
    "docs/riesgos/registro_riesgos.md",     # entradas marcadas obsoletas
    "docs/riesgos/matriz_trazabilidad.md",
    "docs/riesgos/lista_soup.md",           # SOUP retirado
}
CARPETAS_EXCEPTUADAS = (
    "docs/informes/",            # históricos
    "docs/mis_plans/",
    "docs/superpowers/",
    "docs/referencia/obsoleto/",  # obsoletos con cabecera
    "docs/versiones/",            # historial de versiones y anomalías
    "src/logs/",                  # no versionado
)
# Generados y no versionados (también *.egg-info, ver _archivos).
PARTES_IGNORADAS = {"__pycache__", ".pytest_cache"}


def _exceptuado(rel: str) -> bool:
    return rel in ARCHIVOS_EXCEPTUADOS or rel.startswith(CARPETAS_EXCEPTUADAS)


def _archivos():
    for nombre in CARPETAS:
        for ruta in (RAIZ / nombre).rglob("*"):
            if (ruta.is_file() and not PARTES_IGNORADAS.intersection(ruta.parts)
                    and not any(p.endswith(".egg-info") for p in ruta.parts)):
                yield ruta
    for nombre in ARCHIVOS_RAIZ:
        ruta = RAIZ / nombre
        if ruta.is_file():
            yield ruta
    yield from (r for r in RAIZ.glob(PATRON_RAIZ) if r.is_file())


def _texto(ruta: Path):
    """Contenido de un archivo de texto; None si es binario (docx, pdf...)."""
    datos = ruta.read_bytes()
    for codificacion in ("utf-8", "utf-16"):
        if codificacion == "utf-16" and not datos.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            pass
    return None


def test_no_quedan_rastros_del_esp32_fuera_de_las_excepciones():
    hallazgos = []
    for ruta in _archivos():
        rel = ruta.relative_to(RAIZ).as_posix()
        if _exceptuado(rel):
            continue
        texto = _texto(ruta)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if PATRON.search(linea):
                hallazgos.append(f"{rel}:{n}: {linea.strip()[:120]}")
    assert not hallazgos, "Rastros del ESP32 / enlace serial:\n" + "\n".join(hallazgos)


def test_las_excepciones_de_archivo_existen():
    # Una excepción que ya no existe se quita de la lista (no se acumulan).
    faltan = [r for r in ARCHIVOS_EXCEPTUADOS if not (RAIZ / r).is_file()]
    assert not faltan, faltan
