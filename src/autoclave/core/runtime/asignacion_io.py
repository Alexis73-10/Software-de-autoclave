# core/runtime/asignacion_io.py
#
# R8 (tanda 8, D8-5.12; planeacion_opciones.md v4 R-03 y OPC-03): reasignación
# de entradas y salidas ante el daño de un puerto del módulo E/S.
#
# Tres capas:
#   fábrica   `io_ports` del YAML de la instancia (config/instances/<activa>.yaml).
#             Si el YAML no la trae (un equipo instalado conserva su copia del
#             YAML de la compilación anterior), la de fábrica es la del código:
#             las posiciones de EstadoAutoclave tal como se importaron.
#   vigente   fábrica + los cambios guardados en la carpeta de datos persistente
#             (app_root()/data/asignacion_io.json, en %ProgramData% instalado),
#             NUNCA dentro del ejecutable. Sin archivo = fábrica.
#   memoria   la vigente se aplica UNA vez al arrancar el backend sobre los mapas
#             de EstadoAutoclave (en el mismo objeto, para que todo lector de
#             map_di/map_do/map_temp/map_pres la vea). Cambiarla exige reiniciar
#             el backend (R-03): nunca se aplica en caliente.
#
# Los puertos se numeran como en los módulos M31-U y en Entradas / Salidas,
# desde 1 (tanda 19, MOD-05; enlace único Modbus desde la tanda 20, T20-03):
#   DI 01-16   (módulo de 16 DI)
#   DO 01-32   (dos módulos de 16 relés)
#   RTD 01-06  temperatura, grupo AI_TEMP (posición 0-5 de la lista
#              convertida; raw_ai 0-5)
#   AI 01-16   presión, grupo AI_PRES (posición 0-15 de la lista de presión;
#              raw_ai 8-23)
# Ver puertos(). Tanda 23 (AIN-01/02): el tipo sigue siendo "AI", separado en
# dos grupos que comparten números (RTD 01 y AI 01 son puertos distintos);
# todo lo que compara o busca puertos analógicos lo hace POR GRUPO (AIN-R1).
# Antes (FORMATO 1) la presión se numeraba AI 09-16; un archivo FORMATO 1 se
# migra al cargarlo (AIN-05, migrar_formato_1()).
# Una función de temperatura solo va a un puerto de temperatura y una de
# presión a uno de presión: la conversión de cada grupo es distinta.
#
# Puro salvo `ArchivoAsignacion` (lee/escribe el JSON) y `aplicar_en_memoria`.

import copy
import json
import os
import logging
import threading
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

from autoclave.core.runtime.io_names import SALIDAS_RETIRADAS
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.utils.archivos import escribir_texto_atomico

logger = logging.getLogger(__name__)

# Tanda 23 (AIN-02): FORMATO 2 = presión numerada AI 01-16 (FORMATO 1: 09-16).
FORMATO = 2
FORMATO_ANTERIOR = 1
NOMBRE_ARCHIVO = "asignacion_io.json"

TIPOS = ("DI", "DO", "AI")
# Puertos físicos ofrecidos (1-indexados) de los módulos M31-U por Modbus TCP
# (tanda 19, MOD-05; enlace único desde la tanda 20, T20-03): DI 01-16
# (módulo de 16 DI), DO 01-32 (dos módulos de 16 relés), temperatura RTD 01-06
# (módulo de 6 PT100), presión AI 01-16 (AI 1-16 del principal; tanda 23,
# AIN-02, antes 09-16 con solo 8). Los rangos del enlace serial (DI 01-48,
# temperatura 01-08) se retiraron con él.
# Una asignación guardada (data/asignacion_io.json) con un puerto fuera de
# estos rangos da `puerto_inexistente` en validar(); al arrancar,
# backend/context.py la trata como cualquier asignación inválida: alarma
# CONFIGURACION_INVALIDA (bloqueante), fábrica en memoria solo para construir
# y control bloqueado (bloquear_por_configuracion) hasta corregirla.
_PUERTOS_MODBUS = {"DI": range(1, 17), "DO": range(1, 33),
                   "AI_TEMP": range(1, 7), "AI_PRES": range(1, 17)}
# Canal crudo de la lista "ai" del enlace: RTD n -> ai[n-1], AI n -> ai[8+n-1]
# (tanda 23, AIN-03). Ya NO se suma al número de puerto (AIN-02).
OFFSET_RAW_PRESION = 8
# Desplazamiento del número de puerto de presión de FORMATO 1 (AI 09-16).
_OFFSET_PUERTO_FORMATO_1 = 8
GRUPOS = ("DI", "DO", "AI_TEMP", "AI_PRES")
# Prefijo visible por grupo (tanda 23, AIN-01): RTD 01-06 y AI 01-16.
_PREFIJO = {"DI": "DI", "DO": "DO", "AI_TEMP": "RTD", "AI_PRES": "AI"}


def enlace() -> str:
    """Enlace de E/S (constante "modbus" desde la tanda 20, T20-03; se
    conserva la función para /status y la API de reasignación)."""
    return "modbus"


def puertos() -> dict:
    """{"DI", "DO", "AI_TEMP", "AI_PRES": range} de los módulos M31-U."""
    return dict(_PUERTOS_MODBUS)

# Fábrica del código: copia de las posiciones de EstadoAutoclave tomada UNA
# vez por proceso, antes de que nada las cambie (solo este módulo las cambia).
# Se guarda en la propia clase para que recargar este módulo (pruebas) no tome
# como fábrica una asignación ya aplicada.
if "_fabrica_codigo_io" not in EstadoAutoclave.__dict__:
    EstadoAutoclave._fabrica_codigo_io = {
        "map_di": dict(EstadoAutoclave.map_di),
        "map_do": dict(EstadoAutoclave.map_do),
        "map_temp": dict(EstadoAutoclave.map_temp),
        "map_pres": dict(EstadoAutoclave.map_pres),
    }
_FABRICA_CODIGO = EstadoAutoclave._fabrica_codigo_io

# Nombre de EstadoAutoclave -> nombre canónico (el del YAML y del catálogo).
# El inverso de io_names._ALIAS_ESTADO.
_CANONICO = {"aire_admosferico_camara": "aire_atmosferico_camara", "temp_ref": "temp_referencia"}
_ESTADO = {v: k for k, v in _CANONICO.items()}

# Criticidad (D8-5.12): las de confirmación reforzada (escribir el nombre de la
# función) son el interlock de puerta, el paro de emergencia y los finales de
# carrera. Las críticas, además, todo lo que decide presión, temperatura, vapor,
# venteo o movimiento de puerta. DECISIÓN SIN CONFIRMAR (lista propuesta).
REFORZADAS = frozenset({
    "paro_emergencia",
    "puerta_1_cerrada", "puerta_1_abierta", "puerta_2_cerrada", "puerta_2_abierta",
    "atrapamiento_puerta_1", "atrapamiento_puerta_2",
    "bloqueo_puerta_1", "bloqueo_puerta_2", "desbloqueo_puerta_1", "desbloqueo_puerta_2",
})
CRITICAS = REFORZADAS | frozenset({
    "temp_camara", "temp_2_camara", "temp_referencia", "temp_drenaje",
    "pres_camara", "pres_chaqueta", "pres_empaque_1", "pres_empaque_2",
    "vapor_generador", "vapor_caldera", "vapor_chaqueta", "vapor_camara",
    "descompresion_rapida", "descompresion_lenta", "descompresion_chaqueta",
    "aire_atmosferico_camara", "aire_comprimido_camara",
    "abrir_puerta_1", "abrir_puerta_2", "cerrar_puerta_1", "cerrar_puerta_2",
    "suministro_electrico",
})


# D11-2 (tanda 11): funciones retiradas del equipo. Su puerto de fábrica queda
# libre (no se corre ninguna otra). Un YAML de instancia (`io_ports`), una
# asignación guardada (data/asignacion_io.json) o un respaldo de antes que aún
# las traiga se acepta: se ignoran con una advertencia en el log, sin impedir
# el arranque. Un cambio nuevo por la API sí las rechaza (función desconocida).
RETIRADAS = SALIDAS_RETIRADAS


def es_retirada(clave_: str) -> bool:
    return base(clave_) in RETIRADAS


def quitar_retiradas(cambios: dict, origen: str) -> dict:
    """`cambios` ({clave de función: puerto}) sin las funciones retiradas,
    avisando en el log de cada una que se ignora."""
    salida = {}
    for funcion, puerto in (cambios or {}).items():
        if es_retirada(str(funcion)):
            logger.warning("Asignación de E/S (%s): la función %s fue retirada del equipo "
                           "(tanda 11, D11-2); se ignora su puerto %r", origen, funcion, puerto)
            continue
        salida[funcion] = puerto
    return salida


class ErrorAsignacion(Exception):
    """Asignación rechazada. `errores`: lista de {codigo, funcion, puerto, ...}."""
    def __init__(self, errores: list[dict]):
        super().__init__("; ".join(texto_error(e) for e in errores))
        self.errores = errores


def canonico(nombre_estado: str) -> str:
    return _CANONICO.get(nombre_estado, nombre_estado)


def nombre_estado(canonico_: str) -> str:
    return _ESTADO.get(canonico_, canonico_)


def es_temperatura(funcion: str) -> bool:
    return nombre_estado(base(funcion)) in _FABRICA_CODIGO["map_temp"]


def grupo(tipo: str, funcion: str | None = None) -> str:
    """Grupo de puertos de una función (tanda 23, AIN-02): "DI", "DO",
    "AI_TEMP" o "AI_PRES". Un grupo ya dado ("AI_TEMP"/"AI_PRES") se
    devuelve tal cual. "AI" sin función: "AI_PRES" (solo para etiquetas
    de compatibilidad; las comprobaciones siempre pasan la función)."""
    if tipo in ("AI_TEMP", "AI_PRES"):
        return tipo
    if tipo != "AI":
        return tipo
    if funcion is not None and es_temperatura(funcion):
        return "AI_TEMP"
    return "AI_PRES"


def etiqueta_grupo(grupo_: str, puerto: int) -> str:
    """"RTD 01", "AI 16", "DO 04" del grupo y el puerto (tanda 23, AIN-01)."""
    return f"{_PREFIJO.get(grupo_, grupo_)} {int(puerto):02d}"


def etiqueta(tipo: str, puerto: int, funcion: str | None = None) -> str:
    """"DO 04", "RTD 01", "AI 09": como se muestra en Entradas / Salidas.
    En AI hace falta la función para saber el grupo (tanda 23, AIN-01)."""
    return etiqueta_grupo(grupo(tipo, funcion), puerto)


def canal_crudo(funcion: str, puerto: int) -> int:
    """Índice en la lista cruda "ai" del enlace de la función analógica en
    `puerto` (tanda 23, AIN-03): RTD n -> n-1, AI n -> 8+n-1."""
    if es_temperatura(funcion):
        return int(puerto) - 1
    return OFFSET_RAW_PRESION + int(puerto) - 1


def puertos_validos(tipo: str, funcion: str | None = None) -> tuple:
    """Puertos válidos del tipo (y, en AI, del grupo de la función) de los
    módulos M31-U (tanda 19, MOD-05). AI sin función: los números que
    existen en algún grupo (1-16); no sirve para comprobar una función."""
    p = puertos()
    if tipo == "DI":
        return tuple(p["DI"])
    if tipo == "DO":
        return tuple(p["DO"])
    if funcion is not None:
        return tuple(p[grupo("AI", funcion)])
    return tuple(sorted(set(p["AI_TEMP"]) | set(p["AI_PRES"])))


# ── fábrica ────────────────────────────────────────────────────────────────

def fabrica_codigo() -> dict:
    """{tipo: {funcion_canonica: puerto}} de las posiciones del código."""
    m = _FABRICA_CODIGO
    return {
        "DI": {canonico(n): i + 1 for n, i in m["map_di"].items()},
        "DO": {canonico(n): i + 1 for n, i in m["map_do"].items()},
        "AI": {**{canonico(n): i + 1 for n, i in m["map_temp"].items()},
               **{canonico(n): i + 1 for n, i in m["map_pres"].items()}},
    }


# Un mismo nombre puede estar en dos tipos (agua_bomba: DI 09 retorno y DO 18
# mando). Esos nombres se identifican con el tipo delante ("DI:agua_bomba") en
# los cambios, el archivo, la API, la bitácora y la UI; los demás conservan su
# nombre (un archivo ya guardado sigue valiendo).
def _repetidas() -> frozenset:
    m = _FABRICA_CODIGO
    nombres = [canonico(n) for n in m["map_di"]] + [canonico(n) for n in m["map_do"]]         + [canonico(n) for n in (*m["map_temp"], *m["map_pres"])]
    return frozenset(n for n in nombres if nombres.count(n) > 1)


_AMBIGUAS = _repetidas()


def clave(tipo: str, funcion: str) -> str:
    """Identificador único de una función: su nombre, o "TIPO:nombre" si el
    nombre está en más de un tipo."""
    return f"{tipo}:{funcion}" if funcion in _AMBIGUAS else funcion


def separar(clave_: str) -> tuple[str | None, str]:
    """(tipo o None, nombre) de una clave de función."""
    tipo, sep, nombre = str(clave_).partition(":")
    return (tipo, nombre) if sep and tipo in TIPOS else (None, str(clave_))


def base(clave_: str) -> str:
    """Nombre de la función sin el tipo."""
    return separar(clave_)[1]


def es_critica(clave_: str) -> bool:
    return base(clave_) in CRITICAS


def es_reforzada(clave_: str) -> bool:
    return base(clave_) in REFORZADAS


def funciones() -> dict:
    """{clave de función: tipo} de todas las funciones conocidas."""
    return {clave(t, f): t for t, filas in fabrica_codigo().items() for f in filas}


def fabrica_desde_yaml(config_dir: Path) -> dict | None:
    """`io_ports` del YAML de la instancia activa; None si no la trae. Lanza
    ErrorAsignacion si la trae mal (fábrica inválida: no se usa en silencio)."""
    yaml = YAML(typ="safe")
    try:
        activa = yaml.load((Path(config_dir) / "active_instances.yaml").read_text(encoding="utf-8"))
        nombre = activa["active_instance"]
        datos = yaml.load((Path(config_dir) / "instances" / f"{nombre}.yaml").read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError):
        return None
    puertos = (datos or {}).get("io_ports")
    if puertos is None:
        return None
    if not isinstance(puertos, dict):
        raise ErrorAsignacion([{"codigo": "fabrica_invalida", "funcion": "", "puerto": None}])
    base = fabrica_codigo()
    salida = {t: dict(base[t]) for t in TIPOS}
    errores = []
    for tipo in TIPOS:
        filas = puertos.get(tipo) or {}
        if not isinstance(filas, dict):
            errores.append({"codigo": "fabrica_invalida", "funcion": tipo, "puerto": None})
            continue
        for funcion, puerto in quitar_retiradas(filas, "io_ports del YAML de la instancia").items():
            if funcion not in base[tipo]:
                errores.append({"codigo": "funcion_desconocida", "funcion": str(funcion),
                                "puerto": puerto, "tipo": tipo})
                continue
            salida[tipo][funcion] = puerto
    errores += validar(salida)
    if errores:
        raise ErrorAsignacion(errores)
    return salida


def fabrica(config_dir: Path | None = None) -> dict:
    """La de fábrica: la del YAML si la trae, si no la del código."""
    if config_dir is None:
        from autoclave.core.runtime.io_names import _config_dir
        config_dir = _config_dir()
    desde_yaml = fabrica_desde_yaml(config_dir)
    return desde_yaml if desde_yaml is not None else fabrica_codigo()


# ── validación y combinación ───────────────────────────────────────────────

def _es_entero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validar(asignacion: dict) -> list[dict]:
    """Errores de una asignación COMPLETA {tipo: {funcion: puerto}}: puerto
    inexistente en el módulo E/S (o del grupo analógico equivocado) y dos
    funciones en el mismo puerto físico. Vacía si es válida. Los puertos
    ocupados se cuentan POR GRUPO (tanda 23, AIN-R1): RTD 01 y AI 01 son
    puertos distintos."""
    errores = []
    for tipo in TIPOS:
        ocupados: dict[tuple[str, int], str] = {}
        for funcion, puerto in sorted((asignacion.get(tipo) or {}).items()):
            if not _es_entero(puerto) or puerto not in puertos_validos(tipo, funcion):
                errores.append({"codigo": "puerto_inexistente", "funcion": clave(tipo, funcion),
                                "puerto": puerto, "tipo": tipo, "grupo": grupo(tipo, funcion)})
                continue
            lugar = (grupo(tipo, funcion), puerto)
            if lugar in ocupados:
                errores.append({"codigo": "conflicto", "funcion": clave(tipo, funcion), "puerto": puerto,
                                "tipo": tipo, "grupo": lugar[0],
                                "ocupado_por": clave(tipo, ocupados[lugar])})
                continue
            ocupados[lugar] = funcion
    return errores


def puertos_sin_calibracion(asignacion: dict, largos: dict) -> list[dict]:
    """Errores de las entradas analógicas en un puerto sin calibración (SEN-01
    de la revisión R8): la calibración de fábrica y la de usuario son listas
    por puerto; un puerto sin entrada en alguna de las dos se leería sin
    corregir y no se podría calibrar. `largos`: {"temperatura": n, "presion":
    m}, el menor de los largos de fábrica y de usuario de cada grupo."""
    errores = []
    for funcion, puerto in sorted((asignacion.get("AI") or {}).items()):
        if not _es_entero(puerto):
            continue
        if es_temperatura(funcion):
            indice, largo = puerto - 1, largos.get("temperatura", 0)
        else:
            indice, largo = puerto - 1, largos.get("presion", 0)
        if not 0 <= indice < largo:
            errores.append({"codigo": "puerto_sin_calibracion", "funcion": clave("AI", funcion),
                            "puerto": puerto, "tipo": "AI", "grupo": grupo("AI", funcion)})
    return errores


def combinar(base: dict, cambios: dict) -> dict:
    """base + cambios ({clave de función: puerto}, el tipo sale de la clave).
    Lanza ErrorAsignacion si una función no existe (o es un nombre repetido
    en dos tipos sin el tipo delante)."""
    salida = {t: dict(base.get(t) or {}) for t in TIPOS}
    tipo_de = {clave(t, f): (t, f) for t, filas in salida.items() for f in filas}
    errores = []
    for funcion, puerto in (cambios or {}).items():
        destino = tipo_de.get(funcion)
        if destino is None:
            errores.append({"codigo": "funcion_desconocida", "funcion": str(funcion), "puerto": puerto})
            continue
        salida[destino[0]][destino[1]] = puerto
    if errores:
        raise ErrorAsignacion(errores)
    return salida


def diferencias(base: dict, otra: dict) -> dict:
    """{clave de función: (tipo, puerto_base, puerto_otra)} donde difieren."""
    salida = {}
    for tipo in TIPOS:
        for funcion, puerto in (otra.get(tipo) or {}).items():
            anterior = (base.get(tipo) or {}).get(funcion)
            if anterior != puerto:
                salida[clave(tipo, funcion)] = (tipo, anterior, puerto)
    return salida


def texto_error(e: dict) -> str:
    """Texto técnico (log y bitácora); la UI usa el código y el catálogo."""
    codigo = e.get("codigo")
    puerto = e.get("puerto")
    grupo_ = e.get("grupo") or grupo(e.get("tipo", "?"), base(str(e.get("funcion") or "")))
    visible = etiqueta_grupo(grupo_, puerto) if _es_entero(puerto) else repr(puerto)
    if codigo == "conflicto":
        return f"{e.get('funcion')} y {e.get('ocupado_por')} en el mismo puerto {visible}"
    if codigo == "puerto_sin_calibracion":
        return f"{e.get('funcion')}: el puerto {visible} no tiene calibración"
    if codigo == "puerto_inexistente":
        return f"puerto inexistente para {e.get('funcion')}: {visible}"
    if codigo == "funcion_desconocida":
        return f"función desconocida: {e.get('funcion')}"
    return str(codigo)


# ── migración FORMATO 1 -> 2 (tanda 23, AIN-05) ─────────────────────────────

def migrar_formato_1(cambios: dict) -> tuple[dict, dict]:
    """(cambios en FORMATO 2, movidos {clave: (puerto FORMATO 1, puerto nuevo)})
    de los `cambios` de un archivo FORMATO 1. Solo las funciones de presión
    (grupo AI_PRES) cambian: p -> p - 8 (AI 09-16 -> AI 01-16, el MISMO canal
    físico, raw_ai 8+p-9; AIN-R2). Temperatura, DI y DO no cambian. Un nombre
    desconocido se deja como está (la validación de siempre lo rechaza).
    Un puerto de presión FORMATO 1 fuera de 09-16 (o no entero) no se
    inventa: lanza ErrorAsignacion `puerto_inexistente`, como antes."""
    tipos = funciones()
    nuevos, movidos, errores = {}, {}, []
    for funcion, puerto in (cambios or {}).items():
        funcion = str(funcion)
        tipo = separar(funcion)[0] or tipos.get(funcion)
        if tipo == "AI" and not es_temperatura(funcion):
            if _es_entero(puerto) and 1 + _OFFSET_PUERTO_FORMATO_1 <= puerto <= 16:
                nuevos[funcion] = puerto - _OFFSET_PUERTO_FORMATO_1
                movidos[funcion] = (puerto, nuevos[funcion])
                continue
            errores.append({"codigo": "puerto_inexistente", "funcion": funcion, "puerto": puerto,
                            "tipo": "AI", "grupo": "AI_PRES", "formato": FORMATO_ANTERIOR})
            continue
        nuevos[funcion] = puerto
    if errores:
        raise ErrorAsignacion(errores)
    return nuevos, movidos


def migrar_datos(datos):
    """`datos` (contenido de asignacion_io.json o de un respaldo) en FORMATO 2.
    (datos, movidos): FORMATO 2 (o cualquier otro) se devuelve tal cual con
    movidos None (idempotente); FORMATO 1 con `cambios` dict se devuelve
    migrado en una copia. Lanza ErrorAsignacion si no se puede migrar."""
    if (not isinstance(datos, dict) or datos.get("formato") != FORMATO_ANTERIOR
            or not isinstance(datos.get("cambios"), dict)):
        return datos, None
    nuevos, movidos = migrar_formato_1(datos["cambios"])
    salida = dict(datos)
    salida["formato"] = FORMATO
    salida["cambios"] = dict(sorted(nuevos.items()))
    return salida, movidos


def texto_movidos(movidos: dict, formato: int) -> str:
    """"pres_camara AI 09, pres_chaqueta AI 10" (formato 1: el puerto viejo)
    o "pres_camara AI 01, …" (formato 2), para la bitácora."""
    i = 0 if formato == FORMATO_ANTERIOR else 1
    return ", ".join(f"{f} AI {int(v[i]):02d}" for f, v in sorted(movidos.items()))


# ── aplicación en memoria ──────────────────────────────────────────────────

def aplicar_en_memoria(asignacion: dict) -> None:
    """Fija los mapas de EstadoAutoclave (en el mismo objeto dict) según una
    asignación COMPLETA y válida. Solo al arrancar el backend (y en pruebas)."""
    errores = validar(asignacion)
    if errores:
        raise ErrorAsignacion(errores)
    nuevos = {"map_di": {}, "map_do": {}, "map_temp": {}, "map_pres": {}}
    for funcion, puerto in asignacion["DI"].items():
        nuevos["map_di"][nombre_estado(funcion)] = puerto - 1
    for funcion, puerto in asignacion["DO"].items():
        nuevos["map_do"][nombre_estado(funcion)] = puerto - 1
    for funcion, puerto in asignacion["AI"].items():
        if es_temperatura(funcion):
            nuevos["map_temp"][nombre_estado(funcion)] = puerto - 1
        else:
            nuevos["map_pres"][nombre_estado(funcion)] = puerto - 1
    for atributo, mapa in nuevos.items():
        destino = getattr(EstadoAutoclave, atributo)
        # mismas claves y mismo orden que la fábrica del código
        orden = list(_FABRICA_CODIGO[atributo])
        destino.clear()
        destino.update({k: mapa[k] for k in orden if k in mapa})


def restablecer_memoria_fabrica_codigo() -> None:
    """Vuelve los mapas de EstadoAutoclave a la fábrica del código (pruebas)."""
    for atributo, mapa in _FABRICA_CODIGO.items():
        destino = getattr(EstadoAutoclave, atributo)
        destino.clear()
        destino.update(copy.deepcopy(mapa))


def en_memoria() -> dict:
    """La asignación que usa este proceso, {tipo: {funcion: puerto}}."""
    return {
        "DI": {canonico(n): i + 1 for n, i in EstadoAutoclave.map_di.items()},
        "DO": {canonico(n): i + 1 for n, i in EstadoAutoclave.map_do.items()},
        "AI": {**{canonico(n): i + 1 for n, i in EstadoAutoclave.map_temp.items()},
               **{canonico(n): i + 1 for n, i in EstadoAutoclave.map_pres.items()}},
    }


def canal_do(nombre_estado_: str) -> int:
    """Canal físico 1-indexado de una salida, según la asignación en memoria."""
    return EstadoAutoclave.map_do[nombre_estado_] + 1


# ── archivo de la vigente ──────────────────────────────────────────────────

def ruta_por_defecto() -> Path:
    from autoclave.utils.paths import app_root
    return app_root() / "data" / NOMBRE_ARCHIVO


class ArchivoAsignacion:
    """data/asignacion_io.json: {"formato", "cambios": {funcion: puerto},
    "verificacion_pendiente": [funciones], "modificado_por", "modificado_en"}.
    Sin archivo = sin cambios (fábrica). Un archivo ilegible o inválido es un
    error (ErrorAsignacion), nunca "fábrica en silencio": el puerto dañado
    volvería a usarse sin aviso."""

    def __init__(self, ruta: Path | str | None = None):
        self.ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
        self._lock = threading.Lock()

    def existe(self) -> bool:
        return self.ruta.exists()

    def leer(self) -> dict:
        if not self.ruta.exists():
            return {"formato": FORMATO, "cambios": {}, "verificacion_pendiente": []}
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ErrorAsignacion([{"codigo": "archivo_ilegible", "funcion": "",
                                    "puerto": None, "detalle": type(e).__name__}])
        # AIN-05 (tanda 23): un FORMATO 1 aún no reescrito (p. ej. no se pudo
        # escribir al arrancar) se lee migrado: nunca con la numeración vieja
        datos, _ = migrar_datos(datos)
        if (not isinstance(datos, dict) or datos.get("formato") != FORMATO
                or not isinstance(datos.get("cambios"), dict)):
            raise ErrorAsignacion([{"codigo": "archivo_invalido", "funcion": "", "puerto": None}])
        pendiente = datos.get("verificacion_pendiente")
        datos["verificacion_pendiente"] = [str(f) for f in pendiente] if isinstance(pendiente, list) else []
        return datos

    def contenido(self, cambios: dict, usuario: str, pendiente: list,
                  ahora: datetime | None = None) -> str:
        datos = {"formato": FORMATO, "cambios": dict(sorted(cambios.items())),
                 "verificacion_pendiente": sorted(set(pendiente)),
                 "modificado_por": usuario,
                 "modificado_en": (ahora or datetime.now()).isoformat(timespec="seconds")}
        return json.dumps(datos, ensure_ascii=False, indent=2)

    def guardar(self, cambios: dict, usuario: str, pendiente: list) -> None:
        with self._lock:
            texto = self.contenido(cambios, usuario, pendiente)
            # AIN-05: una migración aún sin fila en la bitácora no se pierde
            migracion = self._migracion_sin_registrar()
            if migracion is not None:
                datos = json.loads(texto)
                datos["migracion"] = migracion
                texto = json.dumps(datos, ensure_ascii=False, indent=2)
            escribir_texto_atomico(self.ruta, texto, respaldo=True)

    # ── AIN-05 (tanda 23): migración del archivo FORMATO 1 ─────────────────

    def _json(self):
        """Contenido del archivo (None si no existe o no se puede leer)."""
        try:
            return json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def migrar_formato(self, ahora: datetime | None = None) -> dict | None:
        """Si el archivo es FORMATO 1, lo reescribe en FORMATO 2 (presión
        p -> p - 8) dejando el original en `.bak`, y anota la migración en el
        propio archivo ("migracion", con "registrada": false) hasta que la
        bitácora la registre (marcar_migracion_registrada). Devuelve esa
        anotación, o None si no había nada que migrar (idempotente: FORMATO 2
        y formatos desconocidos no se tocan). Lanza ErrorAsignacion si el
        archivo FORMATO 1 trae un puerto de presión fuera de 09-16 (el
        archivo no se toca) y OSError si no se puede escribir."""
        with self._lock:
            datos = self._json()
            nuevos, movidos = migrar_datos(datos)
            if movidos is None:
                return None
            migracion = {"desde_formato": FORMATO_ANTERIOR, "a_formato": FORMATO,
                         "en": (ahora or datetime.now()).isoformat(timespec="seconds"),
                         "movidos": {f: list(v) for f, v in sorted(movidos.items())},
                         "registrada": False}
            nuevos = dict(nuevos)
            nuevos["migracion"] = migracion
            escribir_texto_atomico(self.ruta, json.dumps(nuevos, ensure_ascii=False, indent=2),
                                   respaldo=True)
            logger.warning("Asignación de E/S: %s migrado de FORMATO %d a %d (presión AI 09-16 -> "
                           "AI 01-16, mismo canal físico): %s; original en %s.bak",
                           self.ruta.name, FORMATO_ANTERIOR, FORMATO,
                           texto_movidos(movidos, FORMATO) or "sin funciones de presión movidas",
                           self.ruta.name)
            return migracion

    def _migracion_sin_registrar(self) -> dict | None:
        datos = self._json()
        if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
            return None
        migracion = datos.get("migracion")
        if isinstance(migracion, dict) and migracion.get("registrada") is False:
            return migracion
        return None

    def migracion_sin_registrar(self) -> dict | None:
        """La anotación de una migración cuya fila de bitácora falta."""
        with self._lock:
            return self._migracion_sin_registrar()

    def marcar_migracion_registrada(self) -> None:
        """La fila de la bitácora ya está: no se vuelve a escribir (sin .bak
        nuevo: el .bak conserva el archivo FORMATO 1 original)."""
        with self._lock:
            datos = self._json()
            if not isinstance(datos, dict) or not isinstance(datos.get("migracion"), dict):
                return
            datos["migracion"]["registrada"] = True
            escribir_texto_atomico(self.ruta, json.dumps(datos, ensure_ascii=False, indent=2))

    def guardar_texto(self, texto: str) -> None:
        with self._lock:
            escribir_texto_atomico(self.ruta, texto, respaldo=True)

    def guardar_bytes(self, datos: bytes) -> None:
        """Vuelve a dejar el contenido exacto de antes (deshacer), aunque no
        sea UTF-8 válido (un archivo dañado debe seguir dañado)."""
        with self._lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.ruta.with_name(self.ruta.name + ".tmp")
            try:
                with open(tmp, "wb") as f:
                    f.write(datos)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.ruta)
            finally:
                tmp.unlink(missing_ok=True)

    def quitar_pendiente(self, funciones) -> list[str]:
        """Quita `funciones` de la verificación pendiente (verificadas por el
        ingeniero) sin tocar lo demás. Devuelve las que quedan. Lanza
        ErrorAsignacion/OSError si el archivo no se puede leer o escribir."""
        with self._lock:
            datos = self.leer()
            quitar = set(funciones)
            quedan = [f for f in datos["verificacion_pendiente"] if f not in quitar]
            if quedan != datos["verificacion_pendiente"]:
                datos["verificacion_pendiente"] = quedan
                escribir_texto_atomico(self.ruta, json.dumps(datos, ensure_ascii=False, indent=2),
                                       respaldo=True)
            return quedan

    def limpiar_pendiente(self) -> None:
        """Quita la marca de verificación pendiente (tras verificar)."""
        with self._lock:
            if not self.ruta.exists():
                return
            try:
                datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return
            if isinstance(datos, dict) and datos.get("verificacion_pendiente"):
                datos["verificacion_pendiente"] = []
                escribir_texto_atomico(self.ruta, json.dumps(datos, ensure_ascii=False, indent=2))


def vigente(base: dict, archivo: ArchivoAsignacion) -> tuple[dict, dict]:
    """(asignación vigente completa y validada, datos del archivo). Lanza
    ErrorAsignacion si el archivo es ilegible o deja la asignación inválida."""
    datos = archivo.leer()
    cambios = {}
    for funcion, puerto in quitar_retiradas(datos["cambios"], archivo.ruta.name).items():
        cambios[str(funcion)] = puerto
    asignacion = combinar(base, cambios)
    errores = validar(asignacion)
    if errores:
        raise ErrorAsignacion(errores)
    return asignacion, datos


def responde(funcion: str, asignacion: dict, datos: dict) -> bool:
    """True si la función responde en su puerto según una lectura de la
    módulo E/S (`Units.get_all()`): enlace activo y el puerto presente en la
    trama; en las analógicas, además, una lectura válida (presión absoluta
    mayor que 0: un lazo abierto se lee 0,0 kPa, SEN-01). Sin accionar nada."""
    from autoclave.core.runtime.lectura import lectura_valida
    if not datos or not datos.get("connected"):
        return False
    tipo, funcion = separar(funcion)
    if tipo is None:
        tipo = next((t for t in TIPOS if funcion in (asignacion.get(t) or {})), None)
    if tipo is None or funcion not in (asignacion.get(tipo) or {}):
        return False
    puerto = asignacion[tipo][funcion]
    if tipo == "DI":
        return len(datos.get("raw_di") or []) >= puerto
    if tipo == "DO":
        return len(datos.get("raw_do") or []) >= puerto
    if es_temperatura(funcion):
        lista = datos.get("temperature") or []
        i = puerto - 1
        return i < len(lista) and lectura_valida(lista[i])
    lista = datos.get("pressure") or []
    i = puerto - 1
    return i < len(lista) and lectura_valida(lista[i]) and float(lista[i]) > 0


def cambios_respecto_a(base: dict, asignacion: dict) -> dict:
    """{funcion: puerto} de lo que difiere de `base` (lo que se guarda)."""
    return {f: d[2] for f, d in diferencias(base, asignacion).items()}
