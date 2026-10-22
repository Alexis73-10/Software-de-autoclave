# tests/test_r8_asignacion_io.py
#
# R8 (tanda 8, D8-5.12): núcleo de la reasignación de E/S — fábrica del YAML o
# del código, validación (conflictos y puertos inexistentes), archivo de la
# vigente en la carpeta de datos y aplicación en memoria.

import json
import shutil
from pathlib import Path

import pytest

from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.utils.resources import resource_path


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _config(tmp_path, io_ports=None):
    origen = Path(resource_path("autoclave/config"))
    destino = tmp_path / "config"
    (destino / "instances").mkdir(parents=True)
    shutil.copy(origen / "active_instances.yaml", destino / "active_instances.yaml")
    texto = (origen / "instances" / "ACV-2026-001.yaml").read_text(encoding="utf-8")
    if io_ports is not None:
        # reemplaza la sección io_ports (o la agrega) con la dada
        texto = texto.split("\nio_ports:")[0] + "\n" + io_ports
    (destino / "instances" / "ACV-2026-001.yaml").write_text(texto, encoding="utf-8")
    return destino


def test_fabrica_del_codigo_coincide_con_estado():
    f = aio.fabrica_codigo()
    assert f["DO"]["vapor_camara"] == 4 and f["DO"]["buzer_alarma"] == 24
    assert f["DI"]["paro_emergencia"] == 11
    assert f["AI"]["temp_camara"] == 1 and f["AI"]["temp_referencia"] == 3
    assert f["AI"]["pres_camara"] == 9 and f["AI"]["pres_empaque_2"] == 12
    assert f["DO"]["aire_atmosferico_camara"] == 15
    assert aio.validar(f) == []


def test_fabrica_del_yaml_del_repo_igual_a_la_del_codigo():
    """El YAML de la instancia trae io_ports y coincide con el código."""
    assert aio.fabrica() == aio.fabrica_codigo()
    assert aio.fabrica_desde_yaml(Path(resource_path("autoclave/config"))) is not None


def test_fabrica_sin_io_ports_usa_el_codigo(tmp_path):
    cfg = _config(tmp_path, io_ports="")
    assert aio.fabrica_desde_yaml(cfg) is None
    assert aio.fabrica(cfg) == aio.fabrica_codigo()


def test_fabrica_del_yaml_invalida_se_rechaza(tmp_path):
    cfg = _config(tmp_path, io_ports="io_ports:\n  DO:\n    vapor_camara: 3\n")   # = vapor_chaqueta
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.fabrica(cfg)
    assert e.value.errores[0]["codigo"] == "conflicto"


@pytest.mark.parametrize("cambios,codigo", [
    ({"vapor_camara": 3}, "conflicto"),               # DO 03 es vapor_chaqueta
    ({"paro_emergencia": 1}, "conflicto"),            # DI 01 es aire_comprimido
    ({"vapor_camara": 33}, "puerto_inexistente"),     # solo 32 salidas
    ({"vapor_camara": 0}, "puerto_inexistente"),
    ({"puerta_1_cerrada": 49}, "puerto_inexistente"), # DI 49-56 no se ofrecen (FW-07)
    ({"pres_camara": 5}, "puerto_inexistente"),       # presión en puerto de temperatura
    ({"temp_camara": 13}, "puerto_inexistente"),      # temperatura en puerto de presión
    ({"vapor_camara": "25"}, "puerto_inexistente"),   # no entero
    ({"vapor_camara": True}, "puerto_inexistente"),
])
def test_validacion(cambios, codigo):
    asignacion = aio.combinar(aio.fabrica_codigo(), cambios)
    errores = aio.validar(asignacion)
    assert errores and errores[0]["codigo"] == codigo


def test_conflicto_indica_la_funcion_que_ocupa():
    asignacion = aio.combinar(aio.fabrica_codigo(), {"vapor_camara": 3})
    e = aio.validar(asignacion)[0]
    assert {e["funcion"], e["ocupado_por"]} == {"vapor_camara", "vapor_chaqueta"}
    assert e["tipo"] == "DO" and e["puerto"] == 3


def test_intercambio_de_dos_funciones_es_valido():
    asignacion = aio.combinar(aio.fabrica_codigo(), {"vapor_camara": 3, "vapor_chaqueta": 4})
    assert aio.validar(asignacion) == []


def test_funcion_desconocida():
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.combinar(aio.fabrica_codigo(), {"no_existe": 25})
    assert e.value.errores[0]["codigo"] == "funcion_desconocida"


def test_aplicar_en_memoria_cambia_los_mapas_en_el_mismo_objeto():
    mapa_do = EstadoAutoclave.map_do
    asignacion = aio.combinar(aio.fabrica_codigo(),
                              {"vapor_camara": 25, "paro_emergencia": 30, "pres_camara": 13,
                               "temp_camara": 6, "aire_atmosferico_camara": 26})
    aio.aplicar_en_memoria(asignacion)
    assert EstadoAutoclave.map_do is mapa_do
    assert EstadoAutoclave.map_do["vapor_camara"] == 24
    assert EstadoAutoclave.map_do["aire_admosferico_camara"] == 25
    assert EstadoAutoclave.map_di["paro_emergencia"] == 29
    assert EstadoAutoclave.map_pres["pres_camara"] == 4
    assert EstadoAutoclave.map_temp["temp_camara"] == 5
    assert aio.en_memoria() == asignacion
    assert aio.canal_do("vapor_camara") == 25


def test_aplicar_invalida_no_toca_nada():
    antes = dict(EstadoAutoclave.map_do)
    with pytest.raises(aio.ErrorAsignacion):
        aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), {"vapor_camara": 3}))
    assert EstadoAutoclave.map_do == antes


def test_estado_lee_la_entrada_en_su_puerto_nuevo():
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(),
                                        {"puerta_1_cerrada": 20, "pres_camara": 13}))
    e = EstadoAutoclave()
    di = [0] * 56
    di[19] = 1                       # DI 20
    pres = [0.0] * 8
    pres[4] = 210.0                  # AI 13
    pres[0] = 99.0                   # el puerto viejo (AI 09) ya no es la cámara
    e.update({"raw_di": di, "pressure": pres})
    assert e.sensores_di["puerta_1_cerrada"] == 1
    assert e.sensores_pres["pres_camara"] == 210.0


# ── archivo ────────────────────────────────────────────────────────────────

def test_archivo_ausente_es_fabrica(tmp_path):
    arch = aio.ArchivoAsignacion(tmp_path / "data" / "asignacion_io.json")
    asignacion, datos = aio.vigente(aio.fabrica_codigo(), arch)
    assert asignacion == aio.fabrica_codigo() and datos["cambios"] == {}


def test_archivo_guarda_solo_los_cambios_y_persiste(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    aio.ArchivoAsignacion(ruta).guardar({"vapor_camara": 25}, "ing", ["vapor_camara"])
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["cambios"] == {"vapor_camara": 25} and datos["modificado_por"] == "ing"
    asignacion, leidos = aio.vigente(aio.fabrica_codigo(), aio.ArchivoAsignacion(ruta))
    assert asignacion["DO"]["vapor_camara"] == 25
    assert leidos["verificacion_pendiente"] == ["vapor_camara"]
    aio.ArchivoAsignacion(ruta).limpiar_pendiente()
    assert aio.ArchivoAsignacion(ruta).leer()["verificacion_pendiente"] == []


@pytest.mark.parametrize("contenido,codigo", [
    ("{no es json", "archivo_ilegible"),
    ('{"formato": 99, "cambios": {}}', "archivo_invalido"),
    ('{"formato": 1, "cambios": []}', "archivo_invalido"),
    ('{"formato": 1, "cambios": {"vapor_camara": 3}}', "conflicto"),
    ('{"formato": 1, "cambios": {"vapor_camara": 40}}', "puerto_inexistente"),
    ('{"formato": 1, "cambios": {"inventada": 25}}', "funcion_desconocida"),
])
def test_archivo_danado_es_error_no_fabrica(tmp_path, contenido, codigo):
    ruta = tmp_path / "asignacion_io.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.vigente(aio.fabrica_codigo(), aio.ArchivoAsignacion(ruta))
    assert e.value.errores[0]["codigo"] == codigo


def test_ruta_por_defecto_en_la_carpeta_de_datos():
    from autoclave.utils.paths import app_root
    assert aio.ruta_por_defecto() == app_root() / "data" / "asignacion_io.json"


def test_criticas_y_reforzadas():
    assert aio.REFORZADAS <= aio.CRITICAS
    todas = aio.funciones()
    assert all(f in todas for f in aio.CRITICAS)
    for f in ("paro_emergencia", "puerta_1_cerrada", "atrapamiento_puerta_2", "bloqueo_puerta_1"):
        assert f in aio.REFORZADAS
    assert "vapor_camara" in aio.CRITICAS and "vapor_camara" not in aio.REFORZADAS


# ── nombres repetidos en dos tipos (agua_bomba es DI y DO) ─────────────────

def test_nombre_en_dos_tipos_se_identifica_con_el_tipo():
    f = aio.fabrica_codigo()
    assert "agua_bomba" in f["DI"] and "agua_bomba" in f["DO"]
    todas = aio.funciones()
    assert todas["DI:agua_bomba"] == "DI" and todas["DO:agua_bomba"] == "DO"
    assert "agua_bomba" not in todas
    assert todas["vapor_camara"] == "DO"                     # los únicos conservan su nombre
    libre_di = next(p for p in aio.PUERTOS_DI if p not in f["DI"].values())
    nueva = aio.combinar(f, {"DI:agua_bomba": libre_di})
    assert nueva["DI"]["agua_bomba"] == libre_di and nueva["DO"]["agua_bomba"] == f["DO"]["agua_bomba"]
    assert aio.diferencias(f, nueva) == {"DI:agua_bomba": ("DI", f["DI"]["agua_bomba"], libre_di)}
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.combinar(f, {"agua_bomba": libre_di})            # ambiguo: se rechaza
    assert e.value.errores[0]["codigo"] == "funcion_desconocida"


def test_conflicto_con_nombre_repetido_lo_identifica_con_el_tipo():
    f = aio.fabrica_codigo()
    nueva = aio.combinar(f, {"DO:agua_bomba": f["DO"]["vapor_camara"]})
    claves = {e["funcion"] for e in aio.validar(nueva)} | {e["ocupado_por"] for e in aio.validar(nueva)}
    assert claves == {"DO:agua_bomba", "vapor_camara"}


def test_responde_con_nombre_repetido():
    f = aio.fabrica_codigo()
    datos = {"connected": True, "raw_di": [0] * 48, "raw_do": [0] * 32}
    assert aio.responde("DI:agua_bomba", f, datos) is True
    assert aio.responde("DO:agua_bomba", f, {"connected": True, "raw_di": [0] * 48, "raw_do": [0] * 4}) is False
    assert aio.es_critica("vapor_camara") and not aio.es_critica("DI:agua_bomba")
    assert aio.es_reforzada("paro_emergencia")
