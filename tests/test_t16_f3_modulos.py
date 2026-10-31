# tests/test_t16_f3_modulos.py
#
# F3 (tanda 16): módulos compartidos de la etapa P.
#   - DebounceAcumulado (P6 / D-14.6): 5 s acumulados en una ventana de 10 s.
#   - AislamientoCamara (VCH-AIS §4.4/§4.5): entrada inmediata en el techo,
#     salida con histéresis y 3 s sostenidos, duración e historial.
#   - profile.modo_vapor (VCH-SEL §4.1, V-01).

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import (
    InstallationProfile, MODO_CAMARA, MODO_CHAQUETA, Role, modo_vapor)
from autoclave.state_machine.cycle_phases.aislamiento_camara import (
    AislamientoCamara, SALIDA_SOSTENIDA_S)
from autoclave.state_machine.cycle_phases.debounce_acumulado import DebounceAcumulado

pytestmark = pytest.mark.req("T16-F3")


# ── DebounceAcumulado ─────────────────────────────────────────────────────

def _serie(deb, valores, paso=0.5, t0=0.0):
    """Llama `actualizar` con cada valor; devuelve el instante del primer True o None."""
    for i, v in enumerate(valores):
        t = t0 + i * paso
        if deb.actualizar(v, t):
            return t
    return None


def test_continuo_confirma_a_los_5_s_como_antes():
    deb = DebounceAcumulado()
    assert _serie(deb, [True] * 20) == 5.0


def test_lectura_dentro_no_reinicia_lo_acumulado():
    """P6: con el debounce continuo, 4.5 s fuera + 0.5 s dentro reiniciaba."""
    deb = DebounceAcumulado()
    valores = [True] * 9 + [False] + [True] * 10      # 4.5 s fuera, 0.5 dentro, ...
    t = _serie(deb, valores)
    # acumula 4.5 s (0 a 4.5); el tramo 4.5-5.0 no cuenta (empezó dentro);
    # desde 5.0 vuelve a contar y suma 5 s a los 5.5 s
    assert t == 5.5


def test_oscilacion_confirma_desde_la_mitad_del_tiempo():
    """La PT100 oscilando alrededor del umbral: con el debounce continuo
    nunca confirmaba. 40 % del tiempo fuera no confirma; 50 % (5 s de 10,
    el borde) sí."""
    deb = DebounceAcumulado()
    assert _serie(deb, [True, False, False, True, False] * 40) is None   # 40 %
    deb = DebounceAcumulado()
    assert _serie(deb, [True, False] * 40) is not None                   # 50 %


def test_fuera_de_la_ventana_se_olvida():
    deb = DebounceAcumulado()
    assert _serie(deb, [True] * 8 + [False] * 30 + [True] * 9) is None
    assert deb.acumulado(23.0) == pytest.approx(4.0)


def test_solo_confirma_con_la_condicion_activa_y_en_conteo():
    deb = DebounceAcumulado()
    for i in range(10):
        deb.actualizar(True, i * 0.5)
    assert deb.en_conteo
    assert deb.actualizar(False, 5.0) is False          # 5 s acumulados, pero ahora dentro
    assert not deb.en_conteo
    assert deb.actualizar(True, 5.5) is True


def test_reset_y_parametros():
    deb = DebounceAcumulado()
    _serie(deb, [True] * 9)
    deb.reset()
    assert deb.acumulado(4.5) == 0.0 and not deb.en_conteo
    with pytest.raises(ValueError):
        DebounceAcumulado(acumulado_s=11, ventana_s=10)


# ── AislamientoCamara ─────────────────────────────────────────────────────

TECHO, HIST = 313.2, 3.0


def test_entrada_inmediata_en_el_techo():
    a = AislamientoCamara()
    assert a.actualizar(313.1, TECHO, HIST, 0.0) is False
    assert a.actualizar(313.2, TECHO, HIST, 0.5) is True
    assert a.duracion(10.5) == pytest.approx(10.0)


def test_salida_con_histeresis_y_3_s_sostenidos():
    a = AislamientoCamara()
    a.actualizar(320.0, TECHO, HIST, 0.0)
    # bajo el techo pero sobre techo - histéresis: sigue aislada
    assert a.actualizar(311.0, TECHO, HIST, 1.0) is True
    assert a.actualizar(310.2, TECHO, HIST, 2.0) is True             # = techo - 3: empieza a contar
    assert a.actualizar(310.0, TECHO, HIST, 4.0) is True             # 2 s
    assert a.actualizar(311.0, TECHO, HIST, 4.5) is True             # sube: reinicia
    assert a.actualizar(309.0, TECHO, HIST, 5.0) is True
    assert a.actualizar(309.0, TECHO, HIST, 5.0 + SALIDA_SOSTENIDA_S - 0.1) is True
    assert a.actualizar(309.0, TECHO, HIST, 5.0 + SALIDA_SOSTENIDA_S) is False
    assert a.duracion(9.0) == 0.0


def test_sin_lectura_no_cambia_ni_cuenta():
    a = AislamientoCamara()
    a.actualizar(320.0, TECHO, HIST, 0.0)
    a.actualizar(300.0, TECHO, HIST, 1.0)
    assert a.actualizar(None, TECHO, HIST, 3.0) is True
    assert a.actualizar(300.0, TECHO, HIST, 4.5) is True     # el conteo empezó de nuevo en 4.5
    assert a.actualizar(300.0, TECHO, HIST, 7.5) is False
    assert AislamientoCamara().actualizar(float("nan"), TECHO, HIST, 0.0) is False


def test_sostenido_y_recurrente():
    a = AislamientoCamara()
    a.actualizar(320.0, TECHO, HIST, 0.0)
    assert not a.sostenido(180.0, 180.0) and a.sostenido(180.5, 180.0)
    b = AislamientoCamara()
    t = 0.0
    for _ in range(6):
        b.actualizar(320.0, TECHO, HIST, t)
        b.actualizar(300.0, TECHO, HIST, t + 1)
        b.actualizar(300.0, TECHO, HIST, t + 4)
        t += 60.0
    assert b.entradas_en_ventana(t, 900.0) == 6
    assert b.recurrente(t, 6, 900.0) and not b.recurrente(t, 7, 900.0)
    assert b.entradas_en_ventana(t + 900.0, 900.0) == 0      # la ventana móvil olvida
    b.reset()
    assert not b.aislado and b.entradas_en_ventana(0.0, 900.0) == 0


# ── modo_vapor ───────────────────────────────────────────────────────────

def _perfil(clase):
    return InstallationProfile(
        machine_id="M", model_id="X", serial_number="S", equipment_class=clase,
        door_count=1, door_type=DoorType.SIMPLE, cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT, created_at=datetime(2026, 10, 26))


IO_CON = {"AI": ["temp_camara", "pres_camara", "pres_chaqueta"],
          "DO": ["vapor_camara", "vapor_chaqueta"]}


@pytest.mark.parametrize("clase,esperado", [
    (EquipmentClass.PISO, MODO_CHAQUETA), (EquipmentClass.PISO_LAB, MODO_CHAQUETA),
    (EquipmentClass.MESA_N, MODO_CAMARA), (EquipmentClass.MESA_B, MODO_CAMARA),
    (EquipmentClass.MESA_B_LAB, MODO_CAMARA),
])
def test_modo_por_clase(clase, esperado):
    assert modo_vapor(_perfil(clase), IO_CON) == esperado


@pytest.mark.parametrize("io", [
    {"AI": ["pres_camara"], "DO": ["vapor_camara", "vapor_chaqueta"]},
    {"AI": ["pres_chaqueta"], "DO": ["vapor_camara"]},
    {}, {"AI": None, "DO": None},
])
def test_sin_salida_o_sensor_de_chaqueta_es_camara(io):
    assert modo_vapor(_perfil(EquipmentClass.PISO), io) == MODO_CAMARA


@pytest.mark.parametrize("perfil", [None, MagicMock(), object()])
def test_sin_perfil_real_es_camara(perfil):
    """V-04: un MagicMock (dobles de prueba) no activa el modo chaqueta."""
    assert modo_vapor(perfil, IO_CON) == MODO_CAMARA


def test_io_ilegible_es_camara(monkeypatch):
    import autoclave.core.runtime.io_names as io_names
    monkeypatch.setattr(io_names, "leer_io_enabled",
                        lambda **k: (_ for _ in ()).throw(OSError("x")))
    assert modo_vapor(_perfil(EquipmentClass.PISO)) == MODO_CAMARA
