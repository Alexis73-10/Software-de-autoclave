# tests/test_t23_ain_migracion.py
#
# Tanda 23 (AIN-05, AIN-R2): asignacion_io.json FORMATO 1 (presión AI 09-16)
# se migra al cargar a FORMATO 2 (AI 01-16, p -> p - 8 solo en presión), con
# .bak, una fila de bitácora (sin perderla ni duplicarla) e idempotencia. La
# misma migración al restaurar un respaldo. Equivalencia: el canal crudo ai[]
# de cada función es el mismo antes y después.

import itertools
import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from autoclave.backend.context import BackendContext
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime import bitacora
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.utils.resources import resource_path
from tests.test_r8_reasignacion_api import (CLAVE, _auditoria, api, respaldo)  # noqa: F401  (fixtures)

PRESION = ("pres_camara", "pres_chaqueta", "pres_empaque_1", "pres_empaque_2")


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _escribir_f1(ruta: Path, cambios: dict, pendiente=None) -> str:
    texto = json.dumps({"formato": 1, "cambios": cambios,
                        "verificacion_pendiente": pendiente or [],
                        "modificado_por": "ing", "modificado_en": "2026-10-20T10:00:00"},
                       ensure_ascii=False, indent=2)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return texto


# ── cálculo FORMATO 1 viejo, escrito explícito (AIN-R2) ─────────────────────

_FABRICA_F1 = {"temp_camara": 1, "temp_2_camara": 2, "temp_referencia": 3, "temp_drenaje": 5,
               "pres_camara": 9, "pres_chaqueta": 10, "pres_empaque_1": 11, "pres_empaque_2": 12}
_TEMP = {"temp_camara", "temp_2_camara", "temp_referencia", "temp_drenaje"}


def _canal_crudo_f1(funcion: str, puerto: int) -> int:
    """Como lo hacía el código de la tanda 19-22: temperatura AI 01-06 ->
    map_temp = puerto - 1 -> raw_ai[puerto - 1]; presión AI 09-16 -> map_pres
    = puerto - 1 - 8 -> raw_ai[8 + map_pres] = raw_ai[puerto - 1]."""
    if funcion in _TEMP:
        return puerto - 1
    map_pres = puerto - 1 - 8
    return 8 + map_pres


def _canales_despues(asignacion_f2: dict) -> dict:
    """Canal crudo de cada función analógica con el código nuevo: se aplica
    en memoria y se lee map_temp / map_pres como lo hace Units/EstadoAutoclave."""
    aio.aplicar_en_memoria(asignacion_f2)
    salida = {}
    for f in asignacion_f2["AI"]:
        n = aio.nombre_estado(f)
        if n in EstadoAutoclave.map_temp:
            salida[f] = EstadoAutoclave.map_temp[n]
        else:
            salida[f] = 8 + EstadoAutoclave.map_pres[n]
    return salida


def _equivalente(cambios_f1: dict) -> None:
    ai_f1 = {**_FABRICA_F1, **{f: p for f, p in cambios_f1.items() if f in _FABRICA_F1}}
    antes = {f: _canal_crudo_f1(f, p) for f, p in ai_f1.items()}
    nuevos, _movidos = aio.migrar_formato_1(cambios_f1)
    asignacion = aio.combinar(aio.fabrica_codigo(), nuevos)
    assert aio.validar(asignacion) == [], cambios_f1
    assert _canales_despues(asignacion) == antes, cambios_f1
    for f, p in asignacion["AI"].items():
        assert aio.canal_crudo(f, p) == antes[f]


@pytest.mark.req("AIN-R2")
def test_equivalencia_fabrica_y_ejemplo():
    # fábrica: sin cambios (FORMATO 1 vacío)
    _equivalente({})
    # la fábrica del código en FORMATO 2 es el mismo canal que la de FORMATO 1
    f = aio.fabrica_codigo()
    for funcion, puerto in _FABRICA_F1.items():
        assert aio.canal_crudo(funcion, f["AI"][funcion]) == _canal_crudo_f1(funcion, puerto)
    # la de ejemplo (config/instances): io_ports del YAML de la instancia
    yaml = YAML(typ="safe")
    datos = yaml.load(Path(resource_path("autoclave/config/instances/ACV-2026-001.yaml"))
                      .read_text(encoding="utf-8"))
    ai = datos["io_ports"]["AI"]
    for funcion, puerto in _FABRICA_F1.items():
        assert aio.canal_crudo(funcion, ai[funcion]) == _canal_crudo_f1(funcion, puerto), funcion
    assert aio.fabrica() == aio.fabrica_codigo()


@pytest.mark.req("AIN-R2")
def test_equivalencia_en_todas_las_combinaciones_validas_de_presion():
    """Todas las asignaciones FORMATO 1 válidas de las 4 funciones de presión
    a AI 09-16 (permutaciones sin repetir: 8·7·6·5 = 1680), con la temperatura
    de fábrica y con un cambio de temperatura."""
    n = 0
    for puertos in itertools.permutations(range(9, 17), len(PRESION)):
        cambios = dict(zip(PRESION, puertos))
        _equivalente(cambios)
        n += 1
    assert n == 1680
    for puertos in [(9, 10, 11, 12), (16, 15, 14, 13), (13, 9, 16, 10)]:
        _equivalente({**dict(zip(PRESION, puertos)), "temp_camara": 6, "temp_drenaje": 4})


def test_presion_formato_1_fuera_de_rango_no_se_inventa():
    for malo in (5, 8, 17, 0, "9", True):
        with pytest.raises(aio.ErrorAsignacion) as e:
            aio.migrar_formato_1({"pres_camara": malo})
        assert e.value.errores[0]["codigo"] == "puerto_inexistente"
    # DI, DO y temperatura no cambian
    nuevos, movidos = aio.migrar_formato_1({"vapor_camara": 26, "paro_emergencia": 16,
                                            "temp_camara": 6, "pres_chaqueta": 16})
    assert nuevos == {"vapor_camara": 26, "paro_emergencia": 16, "temp_camara": 6,
                      "pres_chaqueta": 8}
    assert movidos == {"pres_chaqueta": (16, 8)}


# ── migración del archivo al cargar ────────────────────────────────────────

@pytest.mark.req("AIN-05")
def test_migra_al_cargar_con_bak_bitacora_e_idempotencia(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    original = _escribir_f1(ruta, {"pres_camara": 13, "pres_chaqueta": 9, "temp_camara": 6,
                                   "vapor_camara": 26}, ["pres_camara"])
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    assert ctx.motivo_asignacion == ""
    # valores: p - 8 solo en presión
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["formato"] == 2
    assert datos["cambios"] == {"pres_camara": 5, "pres_chaqueta": 1, "temp_camara": 6,
                                "vapor_camara": 26}
    assert datos["verificacion_pendiente"] == ["pres_camara"]
    assert datos["migracion"]["registrada"] is False          # la base aún no está
    # .bak con el contenido original
    assert (ruta.parent / "asignacion_io.json.bak").read_text(encoding="utf-8") == original
    # mismo canal físico
    assert EstadoAutoclave.map_pres["pres_camara"] == 4 and EstadoAutoclave.map_pres["pres_chaqueta"] == 0
    assert EstadoAutoclave.map_temp["temp_camara"] == 5
    assert ctx.asignacion_pendiente == ["pres_camara"]

    # con la base abierta: una fila
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    try:
        ctx.registrar_migracion_asignacion()
        filas, total = ctx.db.consultar_auditoria(evento="asignacion_io_migrada", limite=10)
        assert total == 1
        assert filas[0]["usuario"] == "sistema"
        assert filas[0]["valor_anterior"] == "pres_camara AI 13, pres_chaqueta AI 09"
        assert filas[0]["valor_nuevo"] == "pres_camara AI 05, pres_chaqueta AI 01"
        assert bitacora.categoria_de("asignacion_io_migrada") in bitacora.CATEGORIAS
        assert json.loads(ruta.read_text(encoding="utf-8"))["migracion"]["registrada"] is True
        bak = (ruta.parent / "asignacion_io.json.bak").read_text(encoding="utf-8")
        assert bak == original                       # marcarla no pisa el .bak

        # idempotencia: segunda carga (= otro arranque) no cambia nada ni escribe otra fila
        texto = ruta.read_text(encoding="utf-8")
        aio.restablecer_memoria_fabrica_codigo()
        ctx2 = BackendContext()
        ctx2.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
        ctx2.db = ctx.db
        ctx2.registrar_migracion_asignacion()
        assert ruta.read_text(encoding="utf-8") == texto
        assert (ruta.parent / "asignacion_io.json.bak").read_text(encoding="utf-8") == original
        assert ctx.db.consultar_auditoria(evento="asignacion_io_migrada", limite=10)[1] == 1
        assert EstadoAutoclave.map_pres["pres_camara"] == 4
    finally:
        ctx.db.close()


def test_la_fila_no_se_pierde_si_la_base_no_estaba_o_la_instalacion_no_termino(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    _escribir_f1(ruta, {"pres_camara": 10})
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    ctx.registrar_migracion_asignacion()          # sin base: nada, sin error
    # arranque siguiente: el archivo ya es FORMATO 2 pero la fila sigue pendiente
    aio.restablecer_memoria_fabrica_codigo()
    ctx2 = BackendContext()
    ctx2.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    assert ctx2.archivo_asignacion.migracion_sin_registrar() is not None
    db = DbManager(db_path=tmp_path / "t.db")
    try:
        ctx2.db = db
        db.instalacion_en_curso = lambda: True         # SupresionInstalacion
        ctx2.registrar_migracion_asignacion()
        assert db.consultar_auditoria(evento="asignacion_io_migrada", limite=10)[1] == 0
        assert ctx2.archivo_asignacion.migracion_sin_registrar() is not None
        # un guardado del ingeniero conserva la anotación pendiente
        ctx2.archivo_asignacion.guardar({"pres_camara": 3}, "ines", [])
        assert ctx2.archivo_asignacion.migracion_sin_registrar() is not None
        db.instalacion_en_curso = None
        ctx2.registrar_migracion_asignacion()
        ctx2.registrar_migracion_asignacion()
        assert db.consultar_auditoria(evento="asignacion_io_migrada", limite=10)[1] == 1
        assert ctx2.archivo_asignacion.migracion_sin_registrar() is None
    finally:
        db.close()


def test_formato_2_y_desconocido_no_se_tocan(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    arch = aio.ArchivoAsignacion(ruta)
    arch.guardar({"pres_camara": 9}, "ines", [])            # FORMATO 2: AI 09
    texto = ruta.read_text(encoding="utf-8")
    assert arch.migrar_formato() is None
    assert ruta.read_text(encoding="utf-8") == texto
    assert arch.leer()["cambios"] == {"pres_camara": 9}
    ruta.write_text(json.dumps({"formato": 7, "cambios": {"pres_camara": 9}}), encoding="utf-8")
    assert arch.migrar_formato() is None
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=arch)
    assert ctx.motivo_asignacion.startswith("Asignación de E/S inválida")


def test_formato_1_con_presion_fuera_de_rango_queda_invalida(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    original = _escribir_f1(ruta, {"pres_camara": 5})      # inválido también en FORMATO 1
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    assert ctx.motivo_asignacion.startswith("Asignación de E/S inválida")
    assert ctx.errores_asignacion[0]["codigo"] == "puerto_inexistente"
    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "CONFIGURACION_INVALIDA"
    assert ruta.read_text(encoding="utf-8") == original     # no se reescribe
    assert not (ruta.parent / "asignacion_io.json.bak").exists()


# ── respaldo FORMATO 1 ──────────────────────────────────────────────────────

@pytest.mark.req("AIN-05")
def test_respaldo_formato_1_restaurado_queda_migrado(respaldo):  # noqa: F811
    from autoclave.core.runtime import respaldo as rp
    cliente, _srv, ctx, cab, usb = respaldo
    contenido = {"perfil.json": b"{}", "asignacion_io.json":
                 json.dumps({"formato": 1, "cambios": {"pres_camara": 14, "vapor_camara": 27}}).encode()}
    datos = rp.crear({"serie": "ACV-2026-001", "modelo": "M-1"}, {"perfil_calibracion": True},
                     contenido, "ines", "1.2.0")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir()
    (carpeta / "respaldo_ACV-2026-001_f1.zip").write_bytes(datos)
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_ACV-2026-001_f1.zip",
                                              "confirmar": True}, headers=cab())
    assert r.status_code == 200, r.text
    guardado = json.loads(ctx.archivo_asignacion.ruta.read_text(encoding="utf-8"))
    assert guardado["formato"] == 2
    assert guardado["cambios"] == {"pres_camara": 6, "vapor_camara": 27}
    filas = {f["entidad"]: f for f in _auditoria(ctx, "reasignacion_io")}
    assert filas["pres_camara"]["valor_nuevo"] == "AI 06"


def test_respaldo_formato_1_con_presion_fuera_de_rango_se_rechaza(respaldo):  # noqa: F811
    from autoclave.core.runtime import respaldo as rp
    cliente, _srv, ctx, cab, usb = respaldo
    contenido = {"perfil.json": b"{}", "asignacion_io.json":
                 json.dumps({"formato": 1, "cambios": {"pres_camara": 4}}).encode()}
    datos = rp.crear({"serie": "ACV-2026-001", "modelo": "M-1"}, {"perfil_calibracion": True},
                     contenido, "ines", "1.2.0")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir()
    (carpeta / "respaldo_ACV-2026-001_f1.zip").write_bytes(datos)
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_ACV-2026-001_f1.zip",
                                              "confirmar": True}, headers=cab())
    assert r.status_code == 422 and r.json()["codigo"] == "asignacion_io_invalida"
    assert not ctx.archivo_asignacion.existe()
