"""E1 (tanda 8), D8-3.17: los canales de Entradas / Salidas se derivan del
perfil de instalación (`temperature_probes`, `supply_inputs`,
`door_count`/`door_type`, `vapor_source`). El YAML de la instancia queda como
máximo físico y un canal que el perfil no declara no aparece."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import io_names
from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend


def _perfil(**cambios) -> InstallationProfile:
    """Equipo de pruebas del 22-oct: cámara 1, cámara 2, referencia y drenaje;
    solo aire comprimido; generador interno; 2 puertas abatibles simples."""
    datos = dict(
        machine_id="ACV-2026-001", model_id="SPK-SAT", serial_number="ACV-2026-001",
        equipment_class=EquipmentClass.PISO, door_count=2, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT, created_at=datetime.now(),
        supply_inputs={"agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
                       "vapor_suministro": False, "suministro_electrico": False},
        temperature_probes={"temp_camara": True, "temp_2_camara": True,
                            "temp_ref": True, "temp_drenaje": True},
        vapor_source="generator",
    )
    datos.update(cambios)
    return InstallationProfile(**datos)


# ── El YAML del repo es el máximo físico ────────────────────────────────────

def test_yaml_de_la_instancia_lista_todos_los_canales_fisicos():
    from autoclave.core.runtime.status import EstadoAutoclave as E
    io = io_names.leer_io_enabled()
    nombres = {io_names.clave_estado(n) for n in io["DI"] + io["DO"] + io["AI"]}
    for mapa in (E.map_di, E.map_do, E.map_temp, E.map_pres):
        assert set(mapa) <= nombres, set(mapa) - nombres


# ── Equipo de pruebas ───────────────────────────────────────────────────────

def test_equipo_de_pruebas_temperatura_y_presion():
    p = _perfil()
    temp = [s["name"] for s in io_names.sensores("temperature", profile=p)]
    pres = [s["name"] for s in io_names.sensores("pressure", profile=p)]
    assert temp == ["temp_camara", "temp_2_camara", "temp_referencia", "temp_drenaje"]
    assert pres == ["pres_camara", "pres_chaqueta"]          # puertas simples: sin empaque
    ai = io_names.leer_io_enabled(profile=p)["AI"]
    assert "temp_drenaje_camara" not in ai                   # canal sin posición ni sonda


def test_equipo_de_pruebas_entradas():
    di = [c["name"] for c in io_names.canales_digitales("DI", profile=_perfil())]
    assert di == ["aire_comprimido", "presion_agua", "puerta_1_cerrada", "puerta_1_abierta",
                  "puerta_2_cerrada", "puerta_2_abierta", "paro_emergencia", "agua_camara"]


def test_equipo_de_pruebas_salidas():
    do = [c["name"] for c in io_names.canales_digitales("DO", profile=_perfil())]
    # generador interno: ni vapor_generador ni vapor_caldera (S1, tanda 2);
    # puertas simples: sin motor ni cerrojo
    assert do == ["vapor_chaqueta", "vapor_camara", "descompresion_rapida",
                  "descompresion_lenta", "descompresion_chaqueta", "vacio_camara",
                  "aire_comprimido_camara",
                  "aire_atmosferico_camara", "agua_chaqueta", "agua_intercambiador",
                  "agua_bomba", "bomba_vacio", "buzer_alarma"]


# ── Cada fuente del perfil ──────────────────────────────────────────────────

def test_sonda_no_instalada_no_aparece():
    p = _perfil(temperature_probes={"temp_camara": True, "temp_2_camara": False,
                                    "temp_ref": True, "temp_drenaje": False})
    assert [s["name"] for s in io_names.sensores("temperature", profile=p)] == [
        "temp_camara", "temp_referencia"]


def test_entradas_de_suministro_segun_perfil():
    p = _perfil(supply_inputs={k: True for k in ("agua_bomba", "agua_generador",
                                                 "aire_comprimido", "vapor_suministro",
                                                 "suministro_electrico")})
    di = {c["name"] for c in io_names.canales_digitales("DI", profile=p)}
    assert {"agua_bomba", "agua_generador", "vapor_suministro", "suministro_electrico"} <= di


@pytest.mark.parametrize("fuente, esperadas", [
    ("generator", set()), ("boiler", {"vapor_caldera"}),
    ("mixed", {"vapor_generador", "vapor_caldera"})])
def test_salidas_de_fuente_de_vapor(fuente, esperadas):
    do = {c["name"] for c in io_names.canales_digitales("DO", profile=_perfil(vapor_source=fuente))}
    assert do & {"vapor_generador", "vapor_caldera"} == esperadas


def test_una_puerta_avanzada():
    p = _perfil(door_count=1, door_type=DoorType.ADVANCED)
    di = {c["name"] for c in io_names.canales_digitales("DI", profile=p)}
    do = {c["name"] for c in io_names.canales_digitales("DO", profile=p)}
    pres = [s["name"] for s in io_names.sensores("pressure", profile=p)]
    assert {"puerta_1_cerrada", "puerta_1_abierta", "atrapamiento_puerta_1"} <= di
    assert not any(n.endswith("_2") for n in di | do)
    assert {"abrir_puerta_1", "cerrar_puerta_1", "bloqueo_puerta_1",
            "desbloqueo_puerta_1"} <= do
    assert pres == ["pres_camara", "pres_chaqueta", "pres_empaque_1"]


def test_puertas_motorizadas_sin_cerrojo():
    p = _perfil(door_type=DoorType.MOTORIZED)
    do = {c["name"] for c in io_names.canales_digitales("DO", profile=p)}
    assert {"abrir_puerta_1", "cerrar_puerta_2"} <= do
    assert not do & {"bloqueo_puerta_1", "desbloqueo_puerta_2"}


def test_sin_perfil_lista_el_maximo_fisico():
    """Antes de instalar (sin perfil) se ve todo el YAML, como antes."""
    assert io_names.leer_io_enabled(profile=None) == io_names.leer_io_enabled()


# ── /io/channels y /cycle/display-inputs usan el perfil del equipo ─────────

@pytest.fixture
def servidor():
    ctx = MagicMock()
    ctx.profile = _perfil()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.setdo.salida_bloqueada.return_value = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app, headers=cabecera(srv, "tecnico", "tec1")), srv


def test_io_channels_usa_el_perfil(servidor):
    client, _ = servidor
    r = client.get("/io/channels")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [s["name"] for s in d["temperature"]] == [
        "temp_camara", "temp_2_camara", "temp_referencia", "temp_drenaje"]
    assert [s["name"] for s in d["pressure"]] == ["pres_camara", "pres_chaqueta"]
    nombres_do = {c["name"] for c in d["DO"]}
    assert "descompresion_lenta" in nombres_do
    assert "vapor_generador" not in nombres_do and "abrir_puerta_1" not in nombres_do


def test_entradas_habilitadas_usan_el_perfil(servidor):
    _, srv = servidor
    assert modulo_backend("rutas._comun")._ai_habilitadas() == ["temp_camara", "temp_2_camara", "temp_referencia",
                                     "temp_drenaje", "pres_camara", "pres_chaqueta"]
