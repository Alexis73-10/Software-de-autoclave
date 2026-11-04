"""FASE 6 (P1): códigos de rechazo de las rutas que pasan a OperacionCritica.

(a) `codigos_conocidos(ruta)` deja pasar cada código propio en su ruta y
    fuera de ella `interpretar` da "error_generico";
(b) cada código (propio o global) que emiten esas rutas tiene texto en es y
    en vía `clave_mensaje(codigo, ruta)` (no el genérico);
(c) control por AST: todo código literal de RechazoApi/_rechazar/_Rechazo en
    los manejadores de esas rutas se reconoce en su ruta.
"""
import ast
from pathlib import Path

import pytest

from autoclave import i18n
from autoclave.ui_qml import sesion_backend as sb

RAIZ = Path(__file__).resolve().parents[1]
_RUTAS_DIR = RAIZ / "src" / "autoclave" / "backend" / "rutas"

# ruta -> códigos propios (no globales), extraídos de backend/rutas/*.py
PROPIOS = {
    "/io/test": {"modo_prueba_dueno_vigente", "confirmacion_requerida"},
    "/maintenance/atm-calibration": {
        "calibracion_en_curso", "precondicion", "puerta_abierta", "temp_baja",
        "fuera_de_ciclo", "lecturas_validas", "sin_calibracion", "sin_pendiente",
        "no_aplicada", "no_existe", "tipo_invalido", "fuera_de_rango", "incoherente"},
    "/backup/restore": {
        "usb_no_detectada", "demasiado_grande", "sin_manifiesto", "manifiesto_invalido",
        "manifiesto_alterado", "archivo_faltante", "hash_invalido", "ilegible", "formato",
        "otra_serie", "version", "parametros_invalidos", "calibracion_invalida",
        "calibracion_implausible", "calibracion_otro_enlace", "asignacion_io_invalida",
        "archivo_invalido", "confirmacion_requerida"},
    "/theme": {"ARCHIVO_NO_ESCRIBIBLE"},
}
EXCLUIDOS: dict = {}     # ningún código emitido queda sin reconocer

# códigos ya globales que emiten estas rutas: deben tener texto propio
GLOBALES = {
    "/io/test": {"sesion_invalida", "clave_pendiente", "rol_sin_permiso", "estado_no_permitido",
                 "sin_conexion_modulo_es", "configuracion_invalida", "modo_prueba_otra_sesion",
                 "modo_prueba_rechazado", "modo_prueba_inactivo", "modo_prueba_no_dueno",
                 "paro_emergencia", "apagado_en_curso", "fuente_vapor_no_instalada",
                 "aire_atmosferico_sin_presion", "aire_atmosferico_sin_referencia",
                 "aire_atmosferico_con_presion", "salida_prueba_camara_no_segura",
                 "salida_prueba_estado_seguro", "salida_prueba_camara_presurizada",
                 "salida_prueba_puerta_abierta"},
    "/calibration": {"sesion_invalida", "rol_sin_permiso", "estado_no_permitido",
                     "CALIBRACION_IMPLAUSIBLE", "CALIBRACION_REQUIERE_CONFIRMACION",
                     "sin_base_de_datos", "auditoria_no_disponible", "sin_calibracion_previa"},
    "/cycle/sensor-roles": {"programa_de_fabrica", "ASIGNACION_INVALIDA", "ROL_SONDA_NO_ACTIVA",
                            "estado_no_permitido", "asignacion_desfasada",
                            "SENSOR_NO_DISPONIBLE"},
    "/maintenance/atm-calibration": {"estado_no_permitido", "sin_base_de_datos"},
    "/backup/restore": {"estado_no_permitido"},
}
# responden con HTTPException sin "codigo": nada propio que reconocer
SIN_CODIGO = ("/printer/test-page", "/maintenance/print/calibration")

CASOS = sorted((r, c) for r, cs in PROPIOS.items() for c in cs)
_RECHAZOS = {"RechazoApi", "_rechazar", "_Rechazo"}


@pytest.mark.parametrize("ruta,codigo", CASOS)
def test_pasa_en_su_ruta(ruta, codigo):
    for r in (ruta, ruta + "/x", ruta + "?a=1"):
        assert codigo in sb.codigos_conocidos(r)
        assert sb.interpretar(409, {"codigo": codigo}, r).causa == codigo


@pytest.mark.parametrize("ruta,codigo", CASOS)
def test_error_generico_fuera_de_su_ruta(ruta, codigo):
    otras = ["/status", "/cycle/start", ruta + "x", "/x" + ruta] + [r for r in PROPIOS if r != ruta]
    for r in otras:
        if any(r == p or r.startswith(p + "/") for p, cs in sb._CODIGOS_POR_RUTA if codigo in cs):
            continue          # el mismo código también es propio de esa otra ruta
        assert sb.interpretar(409, {"codigo": codigo}, r).causa == sb.ERROR_GENERICO, (codigo, r)


def test_no_son_globales():
    assert not (set().union(*PROPIOS.values()) & sb.codigos_conocidos(""))


def _textos():
    for ruta, cs in list(PROPIOS.items()) + list(GLOBALES.items()):
        for c in sorted(cs):
            yield pytest.param(ruta, c, id=f"{ruta}-{c}")


@pytest.mark.parametrize("ruta,codigo", list(_textos()))
def test_cada_codigo_tiene_texto_es_en(ruta, codigo):
    clave = sb.clave_mensaje(codigo, ruta)
    assert clave != sb.clave_mensaje(sb.ERROR_GENERICO), (ruta, codigo)
    for idioma in ("es", "en"):
        assert i18n.existe(clave, idioma), (clave, idioma)


@pytest.mark.parametrize("clave", [
    "operacion.procesando", "operacion.verificando", "operacion.sin_confirmar",
    "operacion.confirmada_tarde", "respaldo.restaurar_sin_confirmar",
    "io.prueba_sin_confirmar", "opciones.equipo_reinicio_sin_confirmar"])
def test_claves_nuevas_es_en(clave):
    assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


def test_clave_mensaje_sin_ruta_no_cambia():
    assert sb.clave_mensaje("precondicion") == sb.clave_mensaje(sb.ERROR_GENERICO)
    assert sb.clave_mensaje("sesion_invalida") == "sesion.sesion_invalida"


# ── control por AST ─────────────────────────────────────────────────────────

def _ruta_de(dec) -> str | None:
    if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
            and dec.args and isinstance(dec.args[0], ast.Constant)
            and isinstance(dec.args[0].value, str)):
        return dec.args[0].value
    return None


def _emitidos(nodo) -> set:
    """Literales que puede valer el argumento: "x", `a if c else b` (sin la
    condición) y `v or "x"`."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return {nodo.value}
    if isinstance(nodo, ast.IfExp):
        return _emitidos(nodo.body) | _emitidos(nodo.orelse)
    if isinstance(nodo, ast.BoolOp):
        return set().union(*(_emitidos(v) for v in nodo.values))
    return set()


def literales_por_ruta() -> dict:
    """Ruta del manejador -> códigos literales de sus RechazoApi/_rechazar/_Rechazo."""
    salida = {}
    for archivo in _RUTAS_DIR.glob("*.py"):
        for f in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in f.decorator_list:
                ruta = _ruta_de(dec)
                if ruta is None:
                    continue
                cods = salida.setdefault(ruta, set())
                for n in ast.walk(f):
                    if not isinstance(n, ast.Call) or len(n.args) < 2:
                        continue
                    nombre = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                    if nombre in _RECHAZOS:
                        cods |= _emitidos(n.args[1])
    return salida


_OBJETIVO = tuple(PROPIOS) + ("/calibration", "/cycle/sensor-roles") + SIN_CODIGO


def test_ast_encuentra_manejadores_y_codigos():
    lit = literales_por_ruta()
    for prefijo in _OBJETIVO:
        assert any(r == prefijo or r.startswith(prefijo + "/") for r in lit), prefijo
    todos = set().union(*lit.values())
    for esperado in ("modo_prueba_dueno_vigente", "sin_calibracion", "sin_pendiente",
                     "ARCHIVO_NO_ESCRIBIBLE", "confirmacion_requerida"):
        assert esperado in todos, esperado


def test_ast_todo_literal_se_reconoce_en_su_ruta():
    faltan = []
    for ruta, cods in literales_por_ruta().items():
        base = ruta.split("{", 1)[0].rstrip("/")
        if not any(base == p or base.startswith(p + "/") for p in _OBJETIVO):
            continue
        for c in cods:
            excluido = any(base == p or base.startswith(p + "/")
                           for p, cs in EXCLUIDOS.items() if c in cs)
            if not excluido and c not in sb.codigos_conocidos(base):
                faltan.append((ruta, c))
    assert faltan == []
