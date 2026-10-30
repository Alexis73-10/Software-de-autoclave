# tests/test_v8b_textos.py
#
# V8b (tanda 8; D8-5.4, D8-5.5 y D8-5.11): textos visibles completos, en un
# solo idioma y sin literales fuera del catálogo. Las pruebas son GENÉRICAS:
# recorren todo es.json / en.json y todo el QML y el Python de la UI, para que
# los textos que agreguen otras ramas también queden cubiertos al unir.
#
#   - D8-5.11: toda clave de es existe en en y al revés (lista explícita de
#     faltantes en cada sentido).
#   - D8-5.4: ninguna abreviatura conocida ("Temp.", "Ester.", "Add"...) ni un
#     punto de abreviatura en medio de un texto; en QML ningún texto se recorta
#     con puntos suspensivos (elide) ni se corta en silencio (maximumLineCount).
#   - D8-5.5: es.json sin anglicismos y en.json sin palabras en español
#     (excepciones: nombres propios, unidades, marcas y siglas técnicas).
#   - D8-5.11: ningún literal visible en QML ni en el Python de la UI.
#
# Excepciones en QML: una línea puede llevar el comentario
# `// v8b-permitido: <razón>` para justificar un caso puntual (p. ej. el eco
# de lo que el usuario teclea, que muestra el final).

import ast
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"
QML = SRC / "ui_qml" / "qml"
IDIOMAS = ("es", "en")
CATALOGOS = {i: json.loads((SRC / "i18n" / f"{i}.json").read_text(encoding="utf-8")) for i in IDIOMAS}
_EXCLUIDOS_QML = ("Pruebas/",)         # galerías y pruebas manuales: no son pantallas del equipo
_MARCA = "v8b-permitido:"


def _hojas(nodo, ruta=""):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from _hojas(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from _hojas(v, f"{ruta}[{i}]")
    else:
        yield ruta, nodo


def _textos(idioma):
    """(clave, texto sin placeholders) de cada hoja de texto del catálogo."""
    for clave, valor in _hojas(CATALOGOS[idioma]):
        if isinstance(valor, str):
            yield clave, re.sub(r"\{[^{}]*\}", " ", valor)


# Claves exentas de la regla de abreviaturas (D8-5.4):
#   - X9 (tanda 9, D9-13.4, DECISIÓN SIN CONFIRMAR): el ticket térmico
#     (ticket_ciclo.*, ancho fijo);
#   - U10a (tanda 10, D10-1.2): la sección `abrev`, donde viven SOLO las
#     abreviaturas de pantalla. Cada `abrev.<X>` es la abreviatura del texto
#     completo `<X>` (misma ruta) y solo se muestra con TextoAjustable.qml cuando
#     el completo no cabe (D10-1.1).
_PREFIJOS_CON_ABREVIATURAS = ("ticket_ciclo.", "abrev.")


def _textos_sin_ticket(idioma):
    """Textos sujetos a D8-5.4: todos menos el ticket y las abreviaturas."""
    for clave, texto in _textos(idioma):
        if not clave.startswith(_PREFIJOS_CON_ABREVIATURAS):
            yield clave, texto


# ── D8-5.11: paridad de claves ───────────────────────────────────────────

def _claves(idioma):
    return {c for c, _ in _hojas(CATALOGOS[idioma])}


@pytest.mark.parametrize("origen,destino", [("es", "en"), ("en", "es")])
def test_toda_clave_existe_en_ambos_idiomas(origen, destino):
    faltan = sorted(_claves(origen) - _claves(destino))
    assert faltan == [], f"claves de {origen}.json que faltan en {destino}.json: {faltan}"


# ── D8-5.4: sin abreviaturas ─────────────────────────────────────────────

# Abreviaturas conocidas (se buscan como palabra seguida de punto, sin
# distinguir mayúsculas). "min." no está: es la unidad al final de una frase.
_ABREVIATURAS = {
    "es": ["temp", "pres", "ester", "est", "esteril", "sec", "ref", "dren", "pág", "pag", "compl",
           "cancel", "abs", "máx", "max", "mín", "aprox", "núm", "num", "config", "param", "prog",
           "cant", "vol", "desc", "info", "admin", "téc", "tec", "oper", "seg", "hr", "hrs", "calib",
           "cal", "dif", "prom", "fab", "usr", "nro", "n.º", "nº", "no"],
    "en": ["temp", "pres", "press", "ster", "dry", "ref", "compl", "cancel", "abs", "max", "approx",
           "num", "no", "config", "param", "prog", "qty", "desc", "info", "admin", "tech", "sec",
           "hr", "hrs", "cal", "calib", "avg", "diff", "usr"],
}
# Palabras sueltas que solo aparecen como abreviatura (p. ej. "Presion add").
_ABREVIATURAS_SIN_PUNTO = {
    "es": ["add", "info", "config", "param", "params", "temp", "pres", "ester", "est"],
    "en": ["info", "config", "param", "params", "temp", "pres", "ster"],   # "Add" es verbo en inglés
}
# "N.º", "Nº", "No. 5": número abreviado
_NUMERO_ABREVIADO = re.compile(r"(?<!\w)(N\.?\s?º|No\.\s*\d)")


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_catalogo_sin_abreviaturas_conocidas(idioma):
    con_punto = re.compile(r"(?<![\w.])(%s)\.(?!\w)" % "|".join(map(re.escape, _ABREVIATURAS[idioma])),
                           re.I)
    sin_punto = re.compile(r"(?<![\w\-_])(%s)(?![\w\-_.])" % "|".join(_ABREVIATURAS_SIN_PUNTO[idioma]),
                           re.I)
    hallados = [f"{c}: {m.group(0)!r} en {t!r}" for c, t in _textos_sin_ticket(idioma)
                for m in list(con_punto.finditer(t)) + list(sin_punto.finditer(t))
                + list(_NUMERO_ABREVIADO.finditer(t))]
    assert hallados == [], "\n".join(hallados)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_catalogo_sin_punto_de_abreviatura_en_medio_del_texto(idioma):
    # una palabra corta con punto seguida de minúscula no es fin de frase: es
    # una abreviatura ("Temp. cámara", "Temp. dren. cámara")
    patron = re.compile(r"(?<![\w.])([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{1,7})\.\s+(?=[a-záéíóúüñ])")
    unidades = {"kPa", "bar", "mbar", "psi", "psig", "inHg", "mmHg", "min", "s", "h"}
    hallados = [f"{c}: {m.group(0)!r} en {t!r}" for c, t in _textos_sin_ticket(idioma)
                for m in patron.finditer(t)
                if m.group(1) not in unidades]
    assert hallados == [], "\n".join(hallados)


# ── D10-1.2: toda abreviatura tiene su texto completo ────────────────────

def _abreviaturas(idioma):
    return [(c, t) for c, t in _hojas(CATALOGOS[idioma]) if c.startswith("abrev.")]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_toda_abreviatura_tiene_su_texto_completo(idioma):
    malos = []
    for clave, abreviado in _abreviaturas(idioma):
        completo = _texto(CATALOGOS[idioma], clave[len("abrev."):])
        if not isinstance(abreviado, str) or not abreviado.strip():
            malos.append(f"{clave}: abreviatura vacía o no es texto")
        elif not completo:
            malos.append(f"{clave}: falta el texto completo {clave[len('abrev.'):]!r}")
        elif len(abreviado) > len(completo):
            malos.append(f"{clave}: {abreviado!r} es más largo que {completo!r}")
    assert malos == [], "\n".join(malos)


def test_las_abreviaturas_usan_una_sola_convencion():
    # solo la sección abrev.*: ninguna clave "<algo>_abrev" ni "abrev" anidada en otra sección
    otras = [c for i in IDIOMAS for c, _ in _hojas(CATALOGOS[i])
             if not c.startswith("abrev.") and re.search(r"(^|[._])abrev([._]|$)", c)]
    assert otras == []
    assert _abreviaturas("es"), "la sección abrev existe"


# ── D8-5.5: sin mezclar idiomas ──────────────────────────────────────────

# Anglicismos prohibidos en es.json (palabra completa, sin distinguir mayúsculas).
# Permitidos como término técnico sin equivalente de uso común (DECISIÓN SIN
# CONFIRMAR, ver informe V8b): software, firmware, hardware y siglas (USB, PDF,
# CSV, PWM, SMTP, IP, PC, E/S), además de nombres propios y marcas
# (SPK-SAT, F0, Bowie & Dick, Especifika).
_ANGLICISMOS = [
    "timeout", "time-out", "time out", "setpoint", "set point", "set-point", "ok", "okay", "reset",
    "resetear", "reseteo", "reseteado", "log", "logs", "login", "logout", "log in", "password",
    "backup", "backups", "duty", "buffer", "display", "check", "checklist", "chequear", "delay",
    "default", "status", "offset", "test", "testear", "update", "upload", "download", "email",
    "e-mail", "mail", "online", "offline", "click", "start", "stop", "on", "off", "ready",
    "standby", "stand-by", "hold", "plateau", "reboot", "boot", "token", "input", "output",
    "feedback", "trigger", "tick", "flag", "warning", "enable", "disable", "watchdog", "ack",
    "frame", "driver", "setup", "switch", "link", "router", "host", "socket", "slot", "dashboard",
    "user", "username", "save", "cancel", "done", "loading", "settings", "overshoot", "ramp",
]
# Palabras en español prohibidas en en.json (las ambiguas, como "no" o "a", no están).
_ESPANOL = [
    "de", "del", "la", "las", "los", "el", "que", "con", "para", "por", "una", "uno", "sin", "y",
    "ciclo", "ciclos", "puerta", "puertas", "cámara", "camara", "presión", "presion",
    "temperatura", "fallo", "falla", "sí", "equipo", "usuario", "usuarios", "contraseña",
    "programa", "parámetro", "parámetros", "guardar", "cancelar", "aceptar", "salir", "volver",
    "tiempo", "fecha", "hora", "esterilización", "esterilizacion", "secado", "calentamiento",
    "precalentamiento", "prevacío", "prevacio", "vacío", "chaqueta", "drenaje", "empaque", "sonda",
    "tarjeta", "bitácora", "respaldo", "impresora", "correo", "agua", "aire", "también", "está",
    "desde", "hasta", "entre", "sobre", "bajo", "según", "debe", "cuando", "escape", "lento",
    "rápido", "brecha", "rango", "alta", "baja", "conteo", "pulso", "modo", "espera", "apertura",
]
# Textos que sí pueden llevar letras del español en en.json (nombre del idioma en su propio idioma)
_EN_PERMITIDOS = {"Español"}


def test_es_sin_anglicismos():
    patron = re.compile(r"(?<![\w\-])(%s)(?![\w\-])" % "|".join(map(re.escape, _ANGLICISMOS)), re.I)
    hallados = [f"{c}: {m.group(0)!r} en {t!r}" for c, t in _textos("es") for m in patron.finditer(t)]
    assert hallados == [], "\n".join(hallados)


def test_en_sin_palabras_en_espanol():
    patron = re.compile(r"(?<![\w\-/])(%s)(?![\w\-/])" % "|".join(map(re.escape, _ESPANOL)), re.I)
    hallados = []
    for c, t in _textos("en"):
        if t in _EN_PERMITIDOS or re.fullmatch(r"[a-z0-9_]+", t):
            continue                   # nombre del idioma, o identificador interno (sensores[].clave)
        hallados += [f"{c}: {m.group(0)!r} en {t!r}" for m in patron.finditer(t)]
        hallados += [f"{c}: letra {m.group(0)!r} en {t!r}" for m in re.finditer(r"[áéíóúñÁÉÍÓÚÑ¿¡]", t)]
    assert hallados == [], "\n".join(hallados)


# ── D8-5.4: nada se recorta en QML ───────────────────────────────────────

def _lineas_qml():
    for ruta in sorted(QML.rglob("*.qml")):
        rel = ruta.relative_to(QML).as_posix()
        if rel.startswith(_EXCLUIDOS_QML):
            continue
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            yield rel, n, linea


def test_qml_no_recorta_textos_con_puntos_suspensivos():
    patron = re.compile(r"\belide\s*:\s*Text\.Elide(Right|Left|Middle)")
    hallados = [f"{r}:{n}: {l.strip()}" for r, n, l in _lineas_qml()
                if patron.search(l.split("//", 1)[0]) and _MARCA not in l]
    assert hallados == [], "\n".join(hallados)


def test_qml_no_corta_lineas_en_silencio():
    # maximumLineCount sin elide oculta las líneas que sobran sin avisar
    hallados = [f"{r}:{n}: {l.strip()}" for r, n, l in _lineas_qml()
                if re.search(r"\bmaximumLineCount\s*:", l.split("//", 1)[0]) and _MARCA not in l]
    assert hallados == [], "\n".join(hallados)


# ── D8-5.11: ningún literal visible en QML ───────────────────────────────

# Literales que no son texto para el operador: códigos internos que se
# comparan, motivos que se envían al backend (bitácora), nombres de fuentes,
# formatos de fecha, marcado HTML y el eslogan de marca (D-06, siempre en
# español). Se listan por texto, no por línea, para que no dependan de la
# posición en el archivo.
_LITERALES_PERMITIDOS = {
    # estados y resultados que se comparan con lo que manda el backend
    "DESCONOCIDO", "FALLA", "CICLO", "PREPARADO", "PREPARACION", "HIBERNACION", "ARRANQUE",
    "FALLO", "COMPLETADO", "CANCELADO", "INFORMATIVO", "ALERTA", "Pantallas", "Componentes",
    # estado de puerta del backend (IndicadorPuerta, FC-11 de la tanda 21)
    "CERRADO",
    # tipo de puerto de la reasignación (R8), que se compara con el del backend
    "DI", "DO", "AI",
    # motivos de salida del modo prueba de E/S: van a la bitácora, no a la pantalla
    "abandono de la sección", "inactividad de la interfaz", "salida solicitada",
    # fuentes y formatos
    "Arial", "Tahoma", "Montserrat", "dddd d MMMM yyyy", "Tipografia.estilo: estilo desconocido",
    # nombre de cada idioma en su propio idioma (selector de idioma)
    "Español", "English",
    # D-06 / ARR-02: eslogan de marca
    "Tecnología para esterilizar.", "Ingeniería para responder.",
    # pie del arranque "<modelo>  ·  Software v<versión>" (planeacion_animacion_arranque.md):
    # notación de versión, igual en es y en (DECISIÓN SIN CONFIRMAR, informe V8b)
    "Software v",
}
_CADENA = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _residuo_visible(texto: str) -> str:
    """Lo que queda de un literal tras quitar marcado HTML, placeholders y unidades."""
    t = re.sub(r"<[^>]*>|&\w+;|\{\w*\}", " ", texto)
    t = re.sub(r"(?<!\w)(°C|°F|kPa|bar|psi|inHg|mmHg|min|s|%)(?!\w)", " ", t)
    return t.strip()


def test_qml_sin_literales_visibles_fuera_del_catalogo():
    hallados = []
    for rel, n, linea in _lineas_qml():
        s = linea.strip()
        if s.startswith(("//", "*", "/*")) or _MARCA in linea:
            continue
        codigo = re.sub(r"(?<![:\\])//.*$", "", linea)
        for m in _CADENA.finditer(codigo):
            texto = m.group(1)
            if texto in _LITERALES_PERMITIDOS:
                continue
            residuo = _residuo_visible(texto)
            if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,}", residuo):
                continue
            # identificadores, claves del catálogo, rutas, colores, nombres de objetos
            if " " not in residuo and not re.fullmatch(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,}", residuo):
                continue
            hallados.append(f"{rel}:{n}: {texto!r}")
    assert hallados == [], "\n".join(hallados)


# ── D8-5.11: ningún texto visible armado en el Python de la UI ───────────

# Scripts de línea de órdenes y arneses de prueba: su texto va a la consola.
_PY_EXCLUIDOS = {"app.py", "doble_pantalla.py", "lanzar.py", "historial_ejemplo.py",
                 "prueba_ciclo_en_curso.py", "prueba_instalacion.py", "prueba_menu_principal.py",
                 "prueba_teclado_numerico.py", "exportacion/config_correo.py"}
# Constantes que no son texto para el operador
_PY_PERMITIDOS = {
    # filas del teclado alfanumérico (caracteres, no texto)
    "asdfghjklñ", "¿¡!:\"'", "¿?¡!:\"'",
    # motivos de salida del modo prueba de E/S: van a la bitácora
    "salida solicitada", "cierre de sesión",
    # respaldo si el catálogo no trae la lista de días o meses (i18n.valor)
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
    # marca en los metadatos del PDF
    "Especifika Autoclave",
    # mensaje interno de una aserción del PDF consolidado
    "el índice cambió de tamaño entre las dos pasadas",
}
_LLAMADAS_INTERNAS = {"debug", "info", "warning", "error", "exception", "critical", "log",
                      "print", "add_argument", "ArgumentParser", "_avisar_una_vez", "warn"}


def _cadenas_visibles_py(ruta: Path):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    ignorar = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if nodo.body and isinstance(nodo.body[0], ast.Expr) \
                    and isinstance(nodo.body[0].value, ast.Constant):
                ignorar.add(id(nodo.body[0].value))
        llamada = None
        if isinstance(nodo, ast.Call):
            f = nodo.func
            llamada = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if isinstance(nodo, (ast.Raise, ast.Assert)) or (
                llamada and (llamada in _LLAMADAS_INTERNAS or llamada.endswith(("Error", "Exception")))):
            ignorar.update(id(s) for s in ast.walk(nodo))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in ignorar:
            t = nodo.value
            if t in _PY_PERMITIDOS:
                continue
            if re.search(r"[A-Za-zÁÉÍÓÚáéíóúñ]{3,}\s+[A-Za-zÁÉÍÓÚáéíóúñ]{2,}", t) \
                    or re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", t):
                yield nodo.lineno, t


def test_python_de_la_ui_no_arma_textos_visibles_fuera_del_catalogo():
    hallados = []
    for ruta in sorted((SRC / "ui_qml").rglob("*.py")):
        rel = ruta.relative_to(SRC / "ui_qml").as_posix()
        if rel in _PY_EXCLUIDOS:
            continue
        hallados += [f"ui_qml/{rel}:{n}: {t[:100]!r}" for n, t in _cadenas_visibles_py(ruta)]
    assert hallados == [], "\n".join(hallados)


# ── D8-5.4 / 5.11: cada parámetro de programa tiene nombre en el catálogo ─

def _parametros_de_perfiles():
    salida = set()

    def rec(n, ruta):
        if isinstance(n, dict) and "value" in n and not isinstance(n["value"], dict):
            salida.add(".".join(ruta))
            return
        if isinstance(n, dict):
            for k, v in n.items():
                rec(v, ruta + [k])
    for f in sorted((SRC / "cycles").glob("*/*.json")):
        for sec, v in json.loads(f.read_text(encoding="utf-8"))["parameters"].items():
            rec(v, [sec])
    return sorted(salida)


def _texto(cat, clave):
    nodo = cat
    for parte in clave.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return None
        nodo = nodo[parte]
    return nodo if isinstance(nodo, str) else None


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_todo_parametro_de_programa_tiene_nombre_visible(idioma):
    # sin nombre, OpcionesParametrosCiclo muestra la clave ("Presion add ester")
    faltan = [p for p in _parametros_de_perfiles() if not _texto(CATALOGOS[idioma], "parametros." + p)]
    assert faltan == []


def test_descripciones_citan_nombres_visibles_de_parametros():
    # «Nombre» en una descripción debe ser el nombre que el operador ve en pantalla
    nombres = {t for _, t in _hojas(CATALOGOS["es"].get("parametros", {})) if isinstance(t, str)}
    citados = {m for _, t in _textos("es") for m in re.findall(r"«([^»]+)»", t)}
    sin_nombre = sorted(c for c in citados if c not in nombres and c not in {"F0"})
    assert sin_nombre == []


# ── D8-5.11: motivos del estado seguro detenido (CIC-10) en el idioma vigente ─

def test_motivos_de_estado_seguro_tienen_clave_en_ambos_idiomas():
    from autoclave.core.runtime import alarmas_i18n as ai
    for prefijo, clave in ai._MOTIVOS_BLOQUEO:
        for idioma in IDIOMAS:
            assert _texto(CATALOGOS[idioma], clave), (clave, idioma)
        if not prefijo.startswith("Timeout"):           # textos de antes de la tanda 8
            assert _texto(CATALOGOS["es"], clave).startswith(prefijo), clave


def test_todo_motivo_del_protocolo_de_fallo_se_reconoce():
    from autoclave.core.runtime.alarmas_i18n import clave_motivo_bloqueo
    ruta = SRC / "state_machine" / "cycle_phases" / "protocolo_fallo.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funcion = next(n for n in ast.walk(arbol)
                   if isinstance(n, ast.FunctionDef) and n.name == "bloqueado_motivo")
    motivos = [n.value.value for n in ast.walk(funcion)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
               and isinstance(n.value.value, str)]
    assert len(motivos) >= 3
    assert [m for m in motivos if not clave_motivo_bloqueo(m)] == []


def test_cic10_en_ingles_no_mezcla_el_motivo_en_espanol():
    from autoclave.core.runtime.alarmas_i18n import textos
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    motivo = CATALOGOS["es"]["estado_seguro_motivos"]["sonda_temperatura"]
    en = textos(CATALOGO["CIC-10"], {"motivo": motivo}, "en")["descripcion"]
    es = textos(CATALOGO["CIC-10"], {"motivo": motivo}, "es")["descripcion"]
    assert CATALOGOS["en"]["estado_seguro_motivos"]["sonda_temperatura"] in en and "Sensor" not in en
    assert motivo in es


def test_ui_bridge_entrega_clave_y_causa_del_bloqueo():
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    motivo = CATALOGOS["es"]["estado_seguro_motivos"]["sonda_enfriamiento"]
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True, "bloqueado_motivo": motivo}})
    assert d["es_bloqueado"] == motivo
    assert d["es_bloqueado_clave"] == "estado_seguro_motivos.sonda_enfriamiento"
    assert d["es_bloqueado_sonda"] is True
    liquido = CATALOGOS["es"]["estado_seguro_motivos"]["liquido_caliente"]
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True, "bloqueado_motivo": liquido}})
    assert d["es_bloqueado_clave"] == "estado_seguro_motivos.liquido_caliente"
    assert d["es_bloqueado_sonda"] is False
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True, "bloqueado_motivo": "otro"}})
    assert d["es_bloqueado_clave"] == "" and d["es_bloqueado_sonda"] is False
