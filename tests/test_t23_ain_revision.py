# tests/test_t23_ain_revision.py
#
# Tanda 23, revisión R de la parte AIN (SAF-01..06): YAML de instancia sin
# marca de numeración (se lee migrado, mismo canal físico), migración que no
# se pudo escribir al arrancar (la anotación no se pierde), copia única del
# FORMATO 1 original, marca de formato desconocida en registros de
# calibración y `grupo` en los errores del 422.

import json
from pathlib import Path

import pytest

import autoclave.backend.server  # noqa: F401  (server_reasignacion lee sus nombres de server)
from autoclave.backend import server_reasignacion as sr
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.hal.measures import converters
from tests.test_r8_asignacion_io import _config


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _yaml_sin_marca(tmp_path, ai: str) -> Path:
    """Copia del YAML de la instancia sin `io_ports_formato` (numeración vieja)."""
    cfg = _config(tmp_path, io_ports="io_ports:\n  AI:\n" + ai)
    ruta = cfg / "instances" / "ACV-2026-001.yaml"
    texto = ruta.read_text(encoding="utf-8").replace("io_ports_formato: 2\n", "")
    assert "\n" + aio.CLAVE_FORMATO_YAML + ":" not in texto
    ruta.write_text(texto, encoding="utf-8")
    return cfg


def _canal_crudo(asignacion: dict, funcion: str) -> int:
    aio.aplicar_en_memoria(asignacion)
    n = aio.nombre_estado(funcion)
    if n in EstadoAutoclave.map_temp:
        return EstadoAutoclave.map_temp[n]
    return converters.OFFSET_RAW_PRESION + EstadoAutoclave.map_pres[n]


def test_yaml_del_repo_lleva_la_marca_y_coincide_con_el_codigo():
    from autoclave.utils.resources import resource_path
    cfg = Path(resource_path("autoclave/config"))
    texto = (cfg / "instances" / "ACV-2026-001.yaml").read_text(encoding="utf-8")
    assert "\nio_ports_formato: 2\n" in texto
    assert aio.fabrica_desde_yaml(cfg) == aio.fabrica_codigo()


def test_saf01_yaml_viejo_se_lee_migrado_al_mismo_canal(tmp_path, caplog):
    cfg = _yaml_sin_marca(tmp_path, "    temp_camara: 1\n    pres_camara: 9\n"
                                    "    pres_chaqueta: 10\n    pres_empaque_1: 11\n"
                                    "    pres_empaque_2: 12\n")
    fabrica = aio.fabrica(cfg)
    assert fabrica["AI"]["pres_camara"] == 1 and fabrica["AI"]["pres_empaque_2"] == 4
    assert fabrica["AI"]["temp_camara"] == 1
    # mismo canal físico que con la numeración vieja: raw_ai[puerto viejo - 1]
    assert _canal_crudo(fabrica, "pres_camara") == 8
    assert _canal_crudo(fabrica, "pres_empaque_2") == 11
    assert _canal_crudo(fabrica, "temp_camara") == 0
    assert "io_ports_formato" in caplog.text


def test_saf01_yaml_viejo_con_presion_fuera_de_9_16_es_invalido(tmp_path):
    cfg = _yaml_sin_marca(tmp_path, "    pres_camara: 4\n")
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.fabrica(cfg)
    assert e.value.errores[0]["codigo"] == "puerto_inexistente"


def test_saf01_marca_desconocida_es_fabrica_invalida(tmp_path):
    cfg = _config(tmp_path, io_ports="io_ports:\n  AI:\n    pres_camara: 1\n")
    ruta = cfg / "instances" / "ACV-2026-001.yaml"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("io_ports_formato: 2", "io_ports_formato: 3"),
                    encoding="utf-8")
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.fabrica(cfg)
    assert e.value.errores[0]["codigo"] == "fabrica_invalida"


def _f1(ruta: Path, cambios: dict, pendiente=None) -> str:
    texto = json.dumps({"formato": 1, "cambios": cambios, "verificacion_pendiente": pendiente or []},
                       indent=2)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return texto


def test_saf02_guardar_sobre_un_formato_1_conserva_la_anotacion_y_la_copia(tmp_path):
    ruta = tmp_path / "asignacion_io.json"
    original = _f1(ruta, {"pres_camara": 10})
    arch = aio.ArchivoAsignacion(ruta)
    # la migración al arrancar no se pudo escribir: se lee migrado en memoria
    assert arch.leer()["cambios"] == {"pres_camara": 2}
    arch.guardar({"pres_camara": 2, "vapor_camara": 30}, "ing", [])
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["formato"] == aio.FORMATO
    assert datos["migracion"]["registrada"] is False
    assert datos["migracion"]["movidos"] == {"pres_camara": [10, 2]}
    copia = ruta.with_name(ruta.name + aio.SUFIJO_ORIGINAL_FORMATO_1)
    assert copia.read_text(encoding="utf-8") == original
    # un segundo guardado no pisa la copia del original
    arch.guardar({"pres_camara": 3}, "ing", [])
    assert copia.read_text(encoding="utf-8") == original
    assert arch.migracion_sin_registrar()["movidos"] == {"pres_camara": [10, 2]}


def test_saf02_quitar_pendiente_sobre_un_formato_1_conserva_la_anotacion(tmp_path):
    ruta = tmp_path / "asignacion_io.json"
    _f1(ruta, {"pres_camara": 10}, pendiente=["pres_camara", "vapor_camara"])
    arch = aio.ArchivoAsignacion(ruta)
    assert arch.quitar_pendiente(["vapor_camara"]) == ["pres_camara"]
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["formato"] == aio.FORMATO and datos["cambios"] == {"pres_camara": 2}
    assert datos["migracion"]["registrada"] is False


def test_saf03_migrar_formato_deja_la_copia_unica_del_original(tmp_path):
    ruta = tmp_path / "asignacion_io.json"
    original = _f1(ruta, {"pres_camara": 12})
    arch = aio.ArchivoAsignacion(ruta)
    assert arch.migrar_formato() is not None
    arch.guardar({"pres_camara": 1}, "ing", [])
    arch.guardar({"pres_camara": 2}, "ing", [])
    copia = ruta.with_name(ruta.name + aio.SUFIJO_ORIGINAL_FORMATO_1)
    assert copia.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("detalle,esperado", [
    ({"puerto": 9}, 1),                                  # registro viejo de presión
    ({"puerto": 13, "formato": aio.FORMATO}, 13),        # registro nuevo
    ({"puerto": 13, "formato": aio.FORMATO + 1}, None),  # marca desconocida: no se interpreta
])
def test_saf04_puerto_de_registro(detalle, esperado):
    assert sr.puerto_de_registro("pres_camara", detalle) == esperado


def test_saf04_temperatura_vieja_no_cambia():
    assert sr.puerto_de_registro("temp_camara", {"puerto": 3}) == 3


def test_saf05_el_422_conserva_el_grupo():
    errores = [{"codigo": "conflicto", "funcion": "AI:pres_camara", "puerto": 1, "tipo": "AI",
                "grupo": "AI_PRES", "ocupado_por": "AI:pres_chaqueta", "otro": 1}]
    with pytest.raises(Exception) as e:
        sr._rechazo_validacion(errores)
    extra = getattr(e.value, "extra", None) or {}
    limpio = extra["errores"][0]
    assert limpio["grupo"] == "AI_PRES" and "otro" not in limpio
