# Q1 / R1-P3 (tanda 7, decisión 1.3 de Cristian): `rango_calentamiento` se
# separa en `rango_calentamiento_temp` (°C, clase "diferencia") y
# `rango_calentamiento_pres` (kPa, clase "diferencia"), con el mismo defecto
# que hoy (2.0). Un archivo viejo se migra al cargar copiando el valor a los dos.

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.cycle_manager import Cycle, CycleManager, migrar_parametros
from autoclave.core.runtime import unidades as u
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase

RAIZ = Path(__file__).resolve().parents[1]
PERFILES = sorted((RAIZ / "src" / "autoclave" / "cycles").glob("*/*.json"))


def _viejo(valor=3.5):
    return {"calentamiento": {
        "factor_calentamiento": {"value": 50, "type": "int", "unit": "%", "min": 0, "max": 100},
        "rango_calentamiento": {"value": valor, "type": "float", "unit": "kPa",
                                "clase": "sin_conversion", "min": 0, "max": 30},
        "tasa_calentamiento": {"value": 50.0, "type": "float", "unit": "°C/min",
                               "clase": "diferencia", "min": 0, "max": 100},
    }}


# ── perfiles JSON ───────────────────────────────────────────────────────────

def test_hay_8_perfiles():
    assert len(PERFILES) == 8


@pytest.mark.parametrize("ruta", PERFILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_perfiles_traen_los_dos_rangos_y_no_el_viejo(ruta):
    cal = json.loads(ruta.read_text(encoding="utf-8"))["parameters"]["calentamiento"]
    assert "rango_calentamiento" not in cal
    t, p = cal["rango_calentamiento_temp"], cal["rango_calentamiento_pres"]
    assert (t["value"], t["unit"], t["clase"], t["type"]) == (2.0, "°C", "diferencia", "float")
    assert (p["value"], p["unit"], p["clase"], p["type"]) == (2.0, "kPa", "diferencia", "float")
    assert (t["min"], t["max"]) == (0, 30) and (p["min"], p["max"]) == (0, 30)


def test_clase_diferencia_convierte_como_banda():
    assert u.clase_de_unidad("°C", "rango_calentamiento_temp", "diferencia") == "dtemp"
    assert u.clase_de_unidad("kPa", "rango_calentamiento_pres", "diferencia") == "dpres"


# ── migración ───────────────────────────────────────────────────────────────

def test_migracion_copia_el_valor_a_los_dos_y_conserva_el_orden():
    params = _viejo(3.5)
    assert migrar_parametros(params) is True
    cal = params["calentamiento"]
    assert list(cal) == ["factor_calentamiento", "rango_calentamiento_temp",
                         "rango_calentamiento_pres", "tasa_calentamiento"]
    assert cal["rango_calentamiento_temp"]["value"] == 3.5
    assert cal["rango_calentamiento_temp"]["unit"] == "°C"
    assert cal["rango_calentamiento_temp"]["clase"] == "diferencia"
    assert cal["rango_calentamiento_pres"]["value"] == 3.5
    assert cal["rango_calentamiento_pres"]["unit"] == "kPa"
    assert cal["rango_calentamiento_pres"]["clase"] == "diferencia"
    assert (cal["rango_calentamiento_pres"]["min"], cal["rango_calentamiento_pres"]["max"]) == (0, 30)


def test_migracion_no_toca_un_programa_nuevo():
    params = _viejo()
    migrar_parametros(params)
    params["calentamiento"]["rango_calentamiento_temp"]["value"] = 1.0
    assert migrar_parametros(params) is False
    assert params["calentamiento"]["rango_calentamiento_temp"]["value"] == 1.0


def test_migracion_con_ambos_formatos_gana_el_nuevo():
    params = _viejo(9.0)
    params["calentamiento"]["rango_calentamiento_temp"] = {"value": 1.0, "unit": "°C"}
    params["calentamiento"]["rango_calentamiento_pres"] = {"value": 4.0, "unit": "kPa"}
    assert migrar_parametros(params) is True
    cal = params["calentamiento"]
    assert "rango_calentamiento" not in cal
    assert cal["rango_calentamiento_temp"]["value"] == 1.0
    assert cal["rango_calentamiento_pres"]["value"] == 4.0


def test_migracion_tolera_programas_sin_calentamiento():
    assert migrar_parametros({}) is False
    assert migrar_parametros({"calentamiento": None}) is False


def test_cycle_migra_al_construirse_y_desde_instantanea():
    c = Cycle("x", "X", _viejo(2.5))
    assert c.get_param("calentamiento", "rango_calentamiento_temp") == 2.5
    assert c.get_param("calentamiento", "rango_calentamiento_pres") == 2.5
    inst = c.instantanea()
    inst["parameters"] = _viejo(4.0)       # instantánea guardada por una versión anterior
    r = Cycle.desde_instantanea(inst)
    assert r.get_param("calentamiento", "rango_calentamiento_pres") == 4.0
    assert r.get_param("calentamiento", "rango_calentamiento") is None


def test_cycle_manager_migra_un_archivo_viejo(tmp_path):
    origen = json.loads((RAIZ / "src/autoclave/cycles/factory/instrumental_134.json")
                        .read_text(encoding="utf-8"))
    cal = origen["parameters"]["calentamiento"]
    nuevo = {}
    for k, v in cal.items():
        if k == "rango_calentamiento_temp":
            nuevo["rango_calentamiento"] = {"value": 3.0, "type": "float", "unit": "kPa",
                                            "clase": "sin_conversion", "min": 0, "max": 30}
        elif k != "rango_calentamiento_pres":
            nuevo[k] = v
    origen["parameters"]["calentamiento"] = nuevo
    (tmp_path / "cycles" / "factory").mkdir(parents=True)
    (tmp_path / "cycles" / "user").mkdir(parents=True)
    (tmp_path / "cycles" / "factory" / "instrumental_134.json").write_text(
        json.dumps(origen), encoding="utf-8")
    cm = CycleManager()
    cm.raiz = str(tmp_path)
    cm.load_all_cycles()
    c = cm.cycles[origen["cycle_id"]]
    assert not c.danado
    assert c.get_param("calentamiento", "rango_calentamiento_temp") == 3.0
    assert c.get_param("calentamiento", "rango_calentamiento_pres") == 3.0


# ── calentamiento.py usa cada rango con su magnitud ─────────────────────────

def _fase(rango_temp, rango_pres, temp, pres, viejo=None):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp}
    estado.sensores_pres = {"pres_camara": pres}
    estado.fase_en_sostenimiento = False
    estado.motivo_fallo = ""
    valores = {"temperatura_calentamiento": 134.0, "presion_add_calentamiento": 11.0,
               "timeout_calentamiento": 60, "factor_calentamiento": 50.0,
               "tasa_calentamiento": 0.0, "tasa_presion": 0.0,
               "tiempo_estable_preesterilizacion": 0, "intervalo_segmentos_calor": 2,
               "escape_lento_on": 1, "escape_lento_off": 0,
               "escape_rapido_on": 0, "escape_rapido_off": 10,
               "rango_temp_estabilizacion": 1.0, "timeout_recuperacion_estabilizacion": 5}
    if rango_temp is not None:
        valores["rango_calentamiento_temp"] = rango_temp
    if rango_pres is not None:
        valores["rango_calentamiento_pres"] = rango_pres
    if viejo is not None:
        valores["rango_calentamiento"] = viejo
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, p, default=None: valores.get(p, default)
    fase = CalentamientoFase(estado, MagicMock(), cycle, MagicMock(), MagicMock(), MagicMock())
    fase.reset()
    return fase


P_OBJ = p_saturacion_kpa(134.0) + 11.0


def test_rango_de_presion_actua_sobre_la_presion():
    # temp lejos (100 °C), presión 10 kPa bajo P_obj. Con rango_pres=20 la
    # cercanía de presión es 0,5 -> duty = 0,5·1 + 0,5·0,5 = 0,75. El rango de
    # temperatura (2 °C) no participa.
    fase = _fase(2.0, 20.0, 100.0, P_OBJ - 10.0)
    fase.update()
    assert fase._duty_actual == pytest.approx(0.75)


def test_rango_de_temperatura_actua_sobre_la_temperatura():
    # presión lejos, temp 1 °C bajo T_obj. Con rango_temp=4: cercanía 0,25 ->
    # duty = 0,5 + 0,5·0,25 = 0,625. El rango de presión (2 kPa) no participa.
    fase = _fase(4.0, 2.0, 133.0, P_OBJ - 50.0)
    fase._en_sostenimiento = True      # sin el corte de calidad de vapor (97 % de T_obj)
    fase.update()
    assert fase._duty_actual == pytest.approx(0.625)


def test_sobrepaso_de_presion_usa_el_rango_de_presion():
    # temp justo en el objetivo; presión 5 kPa por encima de P_obj (bajo el
    # techo P_obj+11). Con rango_pres=10 el piso se escala a 0,5 -> duty 0,25.
    fase = _fase(2.0, 10.0, 134.0, P_OBJ + 5.0)
    fase._en_sostenimiento = True
    fase.update()
    assert fase._duty_actual == pytest.approx(0.25)


def test_sin_claves_nuevas_usa_la_vieja():
    # Defensa: un Cycle armado sin pasar por la migración sigue funcionando
    fase = _fase(None, None, 100.0, P_OBJ - 10.0, viejo=20.0)
    fase.update()
    assert fase._duty_actual == pytest.approx(0.75)
