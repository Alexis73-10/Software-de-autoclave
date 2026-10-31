"""S11 (tanda 11, D11-3): en PREPARACION y PREPARADO la alerta SEN-03 solo
vigila los sensores de temperatura del ciclo EN USO (Principal + Referencias)
de los programas de `programas_seguridad()` (la misma lista que ya usa
PREPARACION); un sensor "No en uso" en todos ellos no se vigila y su SEN-03,
si estaba activa, se resuelve. verificar_inicio (RS-06) no cambia."""

from types import SimpleNamespace

import pytest

from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.installation.equipment import EquipmentClass
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from tests.test_adenda_estados import _ESTADOS, _make

_FABRICA = None   # programa sin `sensores`: Principal = temp_camara
_USA_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_USA_C2 = {"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "no_en_uso"}
_PRINCIPAL_REF = {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso",
                  "temp_ref": "principal"}


def _prog(asignacion):
    return SimpleNamespace(sensores=asignacion)


def _perfil_lab():
    return SimpleNamespace(equipment_class=EquipmentClass.PISO_LAB, temperature_probes=None,
                           supply_inputs=None, door_count=2, door_type=None)


def _estado(clase, programas, perfil=None, **lecturas):
    """Estado con AlarmManager real; `programas` es una lista mutable que
    devuelve programas_seguridad() (simula cambiar de programa entre ticks)."""
    obj, _, _ = _make(clase, perfil, **lecturas)
    am = AlarmManager()
    obj.alarm_manager = am
    obj.programas_seguridad = lambda: list(programas)
    return obj, am


def _sen03_activas(am) -> set:
    return {i.origen for i in am.activas()
            if i.codigo == "SEN-03" and i.estado is EstadoInstancia.ACTIVA}


# ── Función pura ────────────────────────────────────────────────────────────

def test_sensores_vigilados_union_de_los_programas():
    assert sc.sensores_vigilados_fuera_de_ciclo([_prog(_USA_REF), _prog(_USA_C2)]) == {
        "temp_camara", "temp_ref", "temp_2_camara"}


def test_sensores_vigilados_fabrica_solo_principal():
    assert sc.sensores_vigilados_fuera_de_ciclo([_prog(_FABRICA)]) == {"temp_camara"}


@pytest.mark.parametrize("programas", [[], [None], None])
def test_sin_programa_regla_del_principal_de_fabrica(programas):
    assert sc.sensores_vigilados_fuera_de_ciclo(programas) == {"temp_camara"}


def test_asignacion_invalida_vigila_los_marcados_en_uso_y_el_de_fabrica():
    invalida = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "principal"}
    assert sc.sensores_vigilados_fuera_de_ciclo([_prog(invalida)]) == {
        "temp_camara", "temp_2_camara", "temp_ref"}


# ── PREPARACION / PREPARADO ─────────────────────────────────────────────────

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", ["temp_2_camara", "temp_ref"])
def test_sensor_no_en_uso_desconectado_no_da_sen03(clase, sensor):
    obj, am = _estado(clase, [_prog(_FABRICA)], _perfil_lab(), **{sensor: None})
    obj.verificar_sensores()
    assert _sen03_activas(am) == set()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_al_pasar_a_programa_que_lo_usa_aparece_y_al_volver_se_resuelve(clase):
    programas = [_prog(_FABRICA)]
    obj, am = _estado(clase, programas, _perfil_lab(), temp_ref=None)
    obj.verificar_sensores()
    assert _sen03_activas(am) == set()
    programas[:] = [_prog(_USA_REF)]           # se selecciona un programa que la usa
    obj.verificar_sensores()                   # siguiente tick
    assert _sen03_activas(am) == {"Referencia"}
    programas[:] = [_prog(_FABRICA)]           # se vuelve al programa que no la usa
    obj.verificar_sensores()
    assert _sen03_activas(am) == set()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_principal_no_en_uso_en_ningun_programa_tampoco_se_vigila(clase):
    obj, am = _estado(clase, [_prog(_PRINCIPAL_REF)], _perfil_lab(), temp_camara=None)
    obj.verificar_sensores()
    assert _sen03_activas(am) == set()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_dos_pantallas_vigila_la_union_de_los_programas(clase):
    obj, am = _estado(clase, [_prog(_USA_REF), _prog(_USA_C2)], _perfil_lab(),
                      temp_ref=None, temp_2_camara=0)
    obj.verificar_sensores()
    assert _sen03_activas(am) == {"Referencia", "Cámara 2"}


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sin_programas_aplica_el_principal_de_fabrica(clase):
    obj, am = _estado(clase, [], _perfil_lab(), temp_camara=None, temp_ref=None)
    obj.verificar_sensores()
    assert _sen03_activas(am) == {"Cámara 1"}


@pytest.mark.parametrize("clase", _ESTADOS)
def test_fallo_al_obtener_programas_vigila_todos(clase):
    """Falla segura: si programas_seguridad() lanza, se vigilan los tres
    (comportamiento anterior a S11)."""
    obj, am = _estado(clase, [], _perfil_lab(), temp_ref=None, temp_2_camara=None)

    def _falla():
        raise RuntimeError("x")
    obj.programas_seguridad = _falla
    obj.verificar_sensores()
    assert _sen03_activas(am) == {"Referencia", "Cámara 2"}


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sin_programas_seguridad_usa_el_programa_del_estado(clase):
    obj, am = _estado(clase, [], _perfil_lab(), temp_ref=None)
    obj.programas_seguridad = None
    obj.cycle.sensores = dict(_USA_REF)
    obj.verificar_sensores()
    assert _sen03_activas(am) == {"Referencia"}


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sen03_sigue_sin_bloquear(clase):
    obj, am = _estado(clase, [_prog(_USA_REF)], _perfil_lab(), temp_ref=None)
    assert obj.verificar_sensores() is True


# ── RS-06 no cambia ─────────────────────────────────────────────────────────

def test_verificar_inicio_sigue_bloqueando_el_programa_que_lo_usa():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_2_camara": 25.0,
                                            "temp_ref": None})
    codigo, detalle = sc.verificar_inicio(_prog(_USA_REF), _perfil_lab(), estado)
    assert codigo == sc.SENSOR_NO_DISPONIBLE and "temp_ref" in detalle
    assert sc.verificar_inicio(_prog(_FABRICA), _perfil_lab(), estado) is None
