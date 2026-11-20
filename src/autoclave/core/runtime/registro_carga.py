# core/runtime/registro_carga.py
#
# Registro de la carga con lector de código de barras (RCB, 19-nov;
# docs/mis_plans/planeacion_registro_carga.md). Reglas puras, sin base ni
# interfaz: las usan el backend (inicio del ciclo y catálogo) y la UI (la
# ventana «Carga del ciclo» valida otra vez lo mismo antes de enviar).
#
# - Lectura (RCB-01.3): se quitan los espacios de los extremos; de 1 a 64
#   caracteres ASCII imprimibles (0x20–0x7E), sin `|`.
# - Nombre del catálogo (RCB-08.2): de 1 a 60 caracteres, sin caracteres de
#   control ni `|`.
# - Límites (RCB-02.4, DECISIÓN SIN CONFIRMAR): 200 códigos distintos y 999 de
#   cantidad por código.
# - Carga del inicio (RCB-04.1/04.2): {"lote": str, "elementos": [{"codigo",
#   "cantidad", "manual"}]}; elementos exigen lote; sin lote ni elementos =
#   sin carga.
# - CSV del catálogo (RCB-08.3): UTF-8 (con o sin BOM), encabezado
#   `codigo;nombre` o `codigo,nombre`, hasta 5000 filas.
# Nada aquí toca el control del ciclo.

import csv
import hashlib
import io
import unicodedata

LONGITUD_MAX_CODIGO = 64
LONGITUD_MAX_NOMBRE = 60
MAX_CODIGOS = 200
MAX_CANTIDAD = 999
MAX_FILAS_CSV = 5000
MAX_BYTES_CSV = 2 * 1024 * 1024
CARACTER_PROHIBIDO = "|"

# Motivos (claves `registro_carga.motivo_<motivo>` en i18n)
MOTIVO_VACIO = "vacio"
MOTIVO_LARGO = "largo"
MOTIVO_CARACTER = "caracter"
MOTIVO_TIPO = "tipo"
MOTIVO_SIN_LOTE = "sin_lote"
MOTIVO_MAX_CODIGOS = "max_codigos"
MOTIVO_MAX_CANTIDAD = "max_cantidad"
MOTIVO_CANTIDAD = "cantidad"
MOTIVO_DUPLICADO = "duplicado"
MOTIVO_COLUMNAS = "columnas"


def validar_codigo(texto) -> tuple[str | None, str | None]:
    """(código normalizado, None) o (None, motivo). RCB-01.3."""
    if not isinstance(texto, str):
        return None, MOTIVO_TIPO
    codigo = texto.strip(" \t\r\n")
    if not codigo:
        return None, MOTIVO_VACIO
    if len(codigo) > LONGITUD_MAX_CODIGO:
        return None, MOTIVO_LARGO
    if CARACTER_PROHIBIDO in codigo or any(not (0x20 <= ord(c) <= 0x7E) for c in codigo):
        return None, MOTIVO_CARACTER
    return codigo, None


def validar_nombre(texto) -> tuple[str | None, str | None]:
    """(nombre normalizado, None) o (None, motivo). RCB-08.2: los espacios de
    los extremos se quitan y los internos repetidos se reducen a uno."""
    if not isinstance(texto, str):
        return None, MOTIVO_TIPO
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn") and c not in " \t"
           for c in texto):
        return None, MOTIVO_CARACTER
    nombre = " ".join(texto.split())
    if not nombre:
        return None, MOTIVO_VACIO
    if len(nombre) > LONGITUD_MAX_NOMBRE:
        return None, MOTIVO_LARGO
    if CARACTER_PROHIBIDO in nombre:
        return None, MOTIVO_CARACTER
    return nombre, None


class CargaInvalida(ValueError):
    """La carga del inicio no cumple las reglas (422 carga_invalida)."""

    def __init__(self, motivo: str, campo: str = ""):
        super().__init__(motivo)
        self.motivo = motivo
        self.campo = campo


def validar_carga(carga) -> dict | None:
    """Carga del cuerpo de /cycle/start, validada (RCB-04.2). None si no hay
    carga (ausente, None, o sin lote ni elementos). Lanza CargaInvalida.
    Devuelve {"lote": str, "elementos": [{"codigo", "cantidad", "manual"}]}
    en el orden recibido."""
    if carga is None:
        return None
    if not isinstance(carga, dict):
        raise CargaInvalida(MOTIVO_TIPO, "carga")
    lote_crudo = carga.get("lote")
    elementos_crudos = carga.get("elementos")
    if elementos_crudos is None:
        elementos_crudos = []
    if not isinstance(elementos_crudos, list):
        raise CargaInvalida(MOTIVO_TIPO, "elementos")
    if lote_crudo in (None, "") and not elementos_crudos:
        return None
    if lote_crudo in (None, ""):
        raise CargaInvalida(MOTIVO_SIN_LOTE, "lote")
    lote, motivo = validar_codigo(lote_crudo)
    if motivo:
        raise CargaInvalida(motivo, "lote")
    if len(elementos_crudos) > MAX_CODIGOS:
        raise CargaInvalida(MOTIVO_MAX_CODIGOS, "elementos")
    elementos, vistos = [], set()
    for e in elementos_crudos:
        if not isinstance(e, dict):
            raise CargaInvalida(MOTIVO_TIPO, "elementos")
        codigo, motivo = validar_codigo(e.get("codigo"))
        if motivo:
            raise CargaInvalida(motivo, "codigo")
        if codigo in vistos:
            raise CargaInvalida(MOTIVO_DUPLICADO, "codigo")
        vistos.add(codigo)
        cantidad = e.get("cantidad")
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
            raise CargaInvalida(MOTIVO_CANTIDAD, "cantidad")
        if cantidad > MAX_CANTIDAD:
            raise CargaInvalida(MOTIVO_MAX_CANTIDAD, "cantidad")
        manual = e.get("manual", False)
        if not isinstance(manual, bool):
            raise CargaInvalida(MOTIVO_TIPO, "manual")
        elementos.append({"codigo": codigo, "cantidad": cantidad, "manual": manual})
    return {"lote": lote, "elementos": elementos}


def tiene_lote_y_elementos(carga: dict | None) -> bool:
    """RCB-04.2: lo que exige `registro_carga_obligatorio`."""
    return bool(carga and carga.get("lote") and carga.get("elementos"))


def resolver(carga: dict | None, catalogo_activo: dict, impresion: str) -> dict | None:
    """RCB-04.3/02.6: la carga validada con el nombre del catálogo activo
    copiado (None y `en_catalogo` False si el código no está) y el modo de
    impresión del programa. None sin carga."""
    if not carga:
        return None
    elementos = []
    for orden, e in enumerate(carga.get("elementos") or []):
        nombre = catalogo_activo.get(e["codigo"]) if isinstance(catalogo_activo, dict) else None
        elementos.append({"codigo": e["codigo"], "nombre": nombre,
                          "en_catalogo": nombre is not None, "cantidad": e["cantidad"],
                          "manual": bool(e.get("manual")), "orden": orden})
    return {"lote": carga["lote"], "elementos": elementos, "impresion": impresion}


def total_elementos(carga: dict | None) -> int:
    """Suma de cantidades (para la bitácora y el resumen)."""
    if not carga:
        return 0
    return sum(int(e.get("cantidad") or 0) for e in carga.get("elementos") or [])


def huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def analizar_csv(datos: bytes, catalogo: dict) -> dict:
    """RCB-08.3: vista previa de la importación de un CSV contra el catálogo
    actual (`catalogo`: {codigo: {"nombre", "activo"}}). Devuelve
    {"ok": bool, "error": motivo|None, "altas": [{codigo, nombre}],
     "cambios": [{codigo, anterior, nombre, reactivado}],
     "reactivados": [{codigo, nombre}] (mismo nombre, estaba de baja),
     "sin_cambio": n, "rechazadas": [{linea, motivo, texto}], "huella": sha256}.
    Con `ok` False (archivo ilegible, sin encabezado o con más de 5000
    filas) no se aplica nada. Nunca lanza."""
    vacio = {"ok": False, "error": None, "altas": [], "cambios": [], "reactivados": [],
             "sin_cambio": 0, "rechazadas": [], "huella": huella(datos or b"")}
    if not isinstance(datos, (bytes, bytearray)):
        return {**vacio, "error": "ilegible"}
    if len(datos) > MAX_BYTES_CSV:
        return {**vacio, "error": "muy_grande"}
    try:
        texto = bytes(datos).decode("utf-8-sig")
    except UnicodeDecodeError:
        return {**vacio, "error": "codificacion"}
    lineas = texto.splitlines()
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    if not lineas:
        return {**vacio, "error": "sin_encabezado"}
    encabezado = lineas[0].strip().lower().replace(" ", "")
    if encabezado in ("codigo;nombre", '"codigo";"nombre"'):
        separador = ";"
    elif encabezado in ("codigo,nombre", '"codigo","nombre"'):
        separador = ","
    else:
        return {**vacio, "error": "sin_encabezado"}
    filas = [(i + 2, l) for i, l in enumerate(lineas[1:]) if l.strip()]
    if len(filas) > MAX_FILAS_CSV:
        return {**vacio, "error": "muchas_filas"}
    altas, cambios, reactivados, rechazadas = [], [], [], []
    sin_cambio, vistos = 0, set()
    for numero, linea in filas:
        try:
            campos = next(csv.reader(io.StringIO(linea), delimiter=separador))
        except (csv.Error, StopIteration):
            campos = []
        if len(campos) != 2:
            rechazadas.append({"linea": numero, "motivo": MOTIVO_COLUMNAS, "texto": linea[:80]})
            continue
        codigo, motivo = validar_codigo(campos[0])
        if motivo is None:
            nombre, motivo = validar_nombre(campos[1])
        if motivo:
            rechazadas.append({"linea": numero, "motivo": motivo, "texto": linea[:80]})
            continue
        if codigo in vistos:
            rechazadas.append({"linea": numero, "motivo": MOTIVO_DUPLICADO, "texto": linea[:80]})
            continue
        vistos.add(codigo)
        actual = catalogo.get(codigo) if isinstance(catalogo, dict) else None
        if actual is None:
            altas.append({"codigo": codigo, "nombre": nombre})
        elif actual.get("nombre") != nombre:
            cambios.append({"codigo": codigo, "anterior": actual.get("nombre"), "nombre": nombre,
                            "reactivado": not actual.get("activo")})
        elif not actual.get("activo"):
            reactivados.append({"codigo": codigo, "nombre": nombre})
        else:
            sin_cambio += 1
    return {**vacio, "ok": True, "altas": altas, "cambios": cambios, "reactivados": reactivados,
            "sin_cambio": sin_cambio, "rechazadas": rechazadas}


def filas_a_aplicar(vista: dict) -> list[tuple[str, str]]:
    """(código, nombre) de las altas, cambios y reactivaciones de una vista
    previa válida, en el orden del archivo por tipo."""
    if not vista or not vista.get("ok"):
        return []
    return ([(a["codigo"], a["nombre"]) for a in vista["altas"]]
            + [(c["codigo"], c["nombre"]) for c in vista["cambios"]]
            + [(r["codigo"], r["nombre"]) for r in vista["reactivados"]])
