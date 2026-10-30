# tests/test_t19_s2_puertos.py
#
# Tanda 19 (MOD-05): puertos ofrecidos por los módulos M31-U, asignación
# guardada fuera de su rango (tanda 20, T20-03: los casos del enlace serial se
# borraron; el enlace es único), buzzer en DO 25 (decisión 4 de
# Cristian) y apagado individual de DO 1-32.

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ruamel.yaml import YAML

from autoclave.backend.context import BackendContext
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.utils.resources import resource_path
from tests.test_r8_reasignacion_api import CLAVE, _aplicar, api  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


# ── puertos según el enlace ────────────────────────────────────────────────

@pytest.mark.req("MOD-05")
def test_puertos_modbus():
    p = aio.puertos()
    assert list(p["DI"]) == list(range(1, 17))
    assert list(p["DO"]) == list(range(1, 33))
    assert list(p["AI_TEMP"]) == list(range(1, 7))
    assert list(p["AI_PRES"]) == list(range(1, 17))      # tanda 23 (AIN-02): AI 01-16
    assert aio.enlace() == "modbus"


@pytest.mark.req("MOD-05")
@pytest.mark.parametrize("tipo,funcion,puerto,valido", [
    ("DI", None, 16, True), ("DI", None, 17, False),
    ("DO", None, 32, True), ("DO", None, 33, False),
    ("AI", "temp_camara", 6, True), ("AI", "temp_camara", 7, False),
    ("AI", "temp_camara", 9, False),
    # tanda 23 (AIN-02): presión AI 01-16; AI 00 y AI 17 no existen
    ("AI", "pres_camara", 16, True), ("AI", "pres_camara", 1, True),
    ("AI", "pres_camara", 0, False), ("AI", "pres_camara", 17, False),
    ("AI", None, 6, True), ("AI", None, 7, True), ("AI", None, 17, False),
])
def test_puertos_validos_modbus(tipo, funcion, puerto, valido):
    assert (puerto in aio.puertos_validos(tipo, funcion)) is valido


@pytest.mark.req("MOD-05")
def test_fabrica_valida_en_los_dos_enlaces():
    # T20-03: queda solo el caso Modbus (el serial se retiró)
    assert aio.validar(aio.fabrica_codigo()) == []
    assert aio.fabrica() == aio.fabrica_codigo()        # YAML del repo, validado


@pytest.mark.req("MOD-05")
def test_asignacion_guardada_fuera_de_rango_bajo_modbus_es_invalida(tmp_path):
    ruta = tmp_path / "data" / "asignacion_io.json"
    aio.ArchivoAsignacion(ruta).guardar({"puerta_1_cerrada": 20, "temp_referencia": 8}, "ing", [])
    with pytest.raises(aio.ErrorAsignacion) as e:
        aio.vigente(aio.fabrica_codigo(), aio.ArchivoAsignacion(ruta))
    assert {x["codigo"] for x in e.value.errores} == {"puerto_inexistente"}
    assert {x["funcion"] for x in e.value.errores} == {"puerta_1_cerrada", "temp_referencia"}
    # (el caso «válida con el enlace serial» se borró: T20-03)


@pytest.mark.req("MOD-05")
def test_arranque_con_asignacion_fuera_de_rango_bloquea(tmp_path):
    """Mismo camino que cualquier asignación inválida (V-03): alarma
    CONFIGURACION_INVALIDA bloqueante, fábrica en memoria solo para construir."""
    ruta = tmp_path / "data" / "asignacion_io.json"
    aio.ArchivoAsignacion(ruta).guardar({"puerta_1_cerrada": 20}, "ing", [])
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    assert ctx.motivo_asignacion.startswith("Asignación de E/S inválida")
    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "CONFIGURACION_INVALIDA"
    assert alarma.definicion.bloquea_inicio is True
    assert aio.en_memoria() == aio.fabrica_codigo()


@pytest.mark.req("MOD-05")
def test_api_publica_los_puertos_del_enlace_activo(api):  # noqa: F811
    cliente, _srv, _ctx, cab, _p = api
    r = cliente.get("/io/assignment", headers=cab())
    assert r.status_code == 200
    d = r.json()
    assert d["enlace"] == "modbus"
    assert d["puertos"] == {"DI": list(range(1, 17)), "DO": list(range(1, 33)),
                            "AI_TEMP": list(range(1, 7)), "AI_PRES": list(range(1, 17))}


@pytest.mark.req("MOD-05")
def test_api_rechaza_un_puerto_fuera_del_enlace_modbus(api):  # noqa: F811
    cliente, _srv, ctx, cab, _p = api
    r = _aplicar(cliente, cab(), {"temp_referencia": 7})
    assert r.status_code == 422
    assert r.json()["errores"][0]["codigo"] == "puerto_inexistente"
    assert not ctx.archivo_asignacion.existe()


# ── buzzer en DO 25 ────────────────────────────────────────────────────────

@pytest.mark.req("MOD-05")
def test_buzzer_en_do_25():
    assert EstadoAutoclave.map_do["buzer_alarma"] == 24       # posición 0-indexada
    assert aio.canal_do("buzer_alarma") == 25
    assert aio.fabrica_codigo()["DO"]["buzer_alarma"] == 25
    assert 24 not in aio.fabrica_codigo()["DO"].values()      # DO 24 queda libre


@pytest.mark.req("MOD-05")
def test_buzzer_en_do_25_en_el_yaml_de_la_instancia():
    datos = YAML(typ="safe").load(
        Path(resource_path("autoclave/config/instances/ACV-2026-001.yaml")).read_text(encoding="utf-8"))
    assert datos["io_ports"]["DO"]["buzer_alarma"] == 25


@pytest.mark.req("MOD-05")
def test_buzzer_enciende_el_canal_25():
    # T20-03: queda solo el caso Modbus (el serial se retiró)
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.buzer_on()
    s.buzer_off()
    assert [(c.args[0], c.args[1]) for c in io.set_output.call_args_list] == [(25, True), (25, False)]


# ── apagado individual ─────────────────────────────────────────────────────

@pytest.mark.req("MOD-05")
def test_apagado_individual_cubre_do_1_a_32():
    io = MagicMock()
    io.all_off.return_value = False
    s = SetOutput(io, estado=MagicMock())
    assert s.reset_all_outputs() is False
    apagados = [c.args for c in io.set_output.call_args_list]
    assert apagados == [(canal, False) for canal in range(1, 33)]
