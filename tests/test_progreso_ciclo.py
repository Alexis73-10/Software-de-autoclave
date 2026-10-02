# tests/test_progreso_ciclo.py
#
# Mapeo de fases backend -> UI, fases que aplican al programa y estimador de
# tiempo restante (planeacion_pantalla_ciclo_en_curso.md §6 B4 y §7).

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import progreso_ciclo as pc
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase

MIN = 60.0


class _Ciclo:
    def __init__(self, params):
        self._p = params

    def get_param(self, seccion, nombre, default=None):
        return self._p.get(seccion, {}).get(nombre, default)


def _ciclo(precal=0, pulsos=(4, 0, 0, 0), secado=15.0):
    a, b, c, d = pulsos
    return _Ciclo({
        "precalentamiento": {"tiempo_precalentamiento": precal},
        "prevacio": {"conteo_pulso_a": a, "conteo_pulso_b": b,
                     "conteo_pulso_c": c, "conteo_pulso_d": d},
        "secado": {"tiempo_secado": secado},
    })


def _cap(vacio=True):
    return SimpleNamespace(has_vacuum=vacio)


# ── mapeo ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("backend, ui", [
    ("PRECALENTAMIENTO", "precalentamiento"),
    ("PRE_VACIO", "vacio"),
    ("CALENTAMIENTO", "calentamiento"),
    ("ESTERILIZACION", "esterilizacion"),
    ("DESCOMPRESION", "descompresion"),
    ("SECADO", "secado"),
])
def test_fase_ui_mapea_las_fases_del_pipeline(backend, ui):
    assert pc.fase_ui(backend) == ui


@pytest.mark.parametrize("terminal", ["COMPLETADO", "CANCELADO", "EMERGENCIA",
                                      "FALLO_CALENTAMIENTO", "", None])
def test_fase_ui_de_estados_terminales_es_none(terminal):
    assert pc.fase_ui(terminal) is None


def test_orden_de_fases_ui():
    assert pc.FASES_UI == ("precalentamiento", "vacio", "calentamiento",
                           "esterilizacion", "descompresion", "secado")


# ── fases aplicables ────────────────────────────────────────────────────

def test_aplicables_programa_tipico_sin_precalentamiento():
    assert pc.fases_aplicables(_ciclo(), _cap()) == [
        "vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]


def test_aplicables_con_todo():
    assert pc.fases_aplicables(_ciclo(precal=5), _cap()) == list(pc.FASES_UI)


def test_aplicables_sin_bomba_de_vacio_omite_vacio_y_secado():
    assert pc.fases_aplicables(_ciclo(precal=5), _cap(vacio=False)) == [
        "precalentamiento", "calentamiento", "esterilizacion", "descompresion"]


def test_aplicables_sin_pulsos_y_sin_secado():
    assert pc.fases_aplicables(_ciclo(pulsos=(0, 0, 0, 0), secado=0), _cap()) == [
        "calentamiento", "esterilizacion", "descompresion"]


def test_aplicables_cuenta_cualquier_tipo_de_pulso():
    assert "vacio" in pc.fases_aplicables(_ciclo(pulsos=(0, 0, 0, 2)), _cap())


# Coherencia con las fases reales: si fases_aplicables() dice que una fase NO
# aplica, su update() debe saltarla en el primer tick (COMPLETADO), y viceversa.
_FASES_CON_SALTO = [
    ("precalentamiento", PrecalentamientoFase),
    ("vacio", PrevacioFase),
    ("secado", SecadoFase),
]


@pytest.mark.parametrize("ciclo, vacio", [
    (_ciclo(), True),
    (_ciclo(precal=5), True),
    (_ciclo(precal=5), False),
    (_ciclo(pulsos=(0, 0, 0, 0), secado=0), True),
    (_ciclo(pulsos=(0, 0, 3, 0), secado=0.0), True),
])
@pytest.mark.parametrize("clave, clase", _FASES_CON_SALTO)
def test_aplicables_coincide_con_el_salto_real_de_la_fase(ciclo, vacio, clave, clase):
    estado = MagicMock()
    estado.sensores_temp = {}
    estado.sensores_pres = {}
    estado.sensores_di = {}
    config = MagicMock()
    config.get.return_value = None
    fase = clase(estado, MagicMock(), ciclo, config, MagicMock(), _cap(vacio))
    fase.reset()
    se_salta = fase.update() == FaseResult.COMPLETADO
    assert se_salta == (clave not in pc.fases_aplicables(ciclo, _cap(vacio)))


# ── restante de la fase activa (regla 2) ────────────────────────────────

def test_restante_fase_dentro_de_referencia():
    assert pc.restante_fase(e=4 * MIN, d_ref=15 * MIN) == 11 * MIN


def test_restante_fase_al_agotar_referencia_suma_extension():
    assert pc.restante_fase(e=15 * MIN, d_ref=15 * MIN) == 5 * MIN


def test_restante_fase_extension_se_consume():
    assert pc.restante_fase(e=18 * MIN, d_ref=15 * MIN) == 2 * MIN


def test_restante_fase_extension_se_renueva_varias_veces():
    assert pc.restante_fase(e=20 * MIN, d_ref=15 * MIN) == 5 * MIN
    assert pc.restante_fase(e=27 * MIN, d_ref=15 * MIN) == 3 * MIN


def test_extension_es_5_min():
    assert pc.EXTENSION_MIN == 5


# ── restante total (reglas 1, 3, 4, 6) ──────────────────────────────────

_APLICA = ["vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]
_REF = {"vacio": 12 * MIN, "calentamiento": 3 * MIN, "esterilizacion": 15 * MIN,
        "descompresion": 2 * MIN, "secado": 13 * MIN}


def test_restante_al_iniciar_es_suma_de_referencias():
    assert pc.tiempo_restante(_APLICA, "vacio", 0.0, _REF) == 45 * MIN


def test_restante_en_fase_intermedia():
    # esterilización lleva 5 de 15 min: 10 + 2 + 13
    assert pc.tiempo_restante(_APLICA, "esterilizacion", 5 * MIN, _REF) == 25 * MIN


def test_restante_con_fase_alargada():
    # calentamiento lleva 4 min (ref 3): 5 - 1 = 4 de extensión + 15 + 2 + 13
    assert pc.tiempo_restante(_APLICA, "calentamiento", 4 * MIN, _REF) == 34 * MIN


def test_restante_ignora_fases_que_no_aplican():
    aplica = ["calentamiento", "esterilizacion", "descompresion"]
    assert pc.tiempo_restante(aplica, "calentamiento", 0.0, _REF) == 20 * MIN


def test_restante_sin_referencia_es_none():
    assert pc.tiempo_restante(_APLICA, "vacio", 0.0, None) is None
    assert pc.tiempo_restante(_APLICA, "vacio", 0.0, {}) is None


def test_restante_con_referencia_incompleta_es_none():
    ref = dict(_REF)
    del ref["secado"]
    assert pc.tiempo_restante(_APLICA, "vacio", 0.0, ref) is None


def test_restante_no_necesita_referencia_de_fases_ya_pasadas():
    ref = dict(_REF)
    del ref["vacio"]
    assert pc.tiempo_restante(_APLICA, "esterilizacion", 0.0, ref) == 30 * MIN


def test_restante_con_fase_activa_desconocida_es_none():
    assert pc.tiempo_restante(_APLICA, None, 0.0, _REF) is None


# ── armado del progreso para la API (B1) ────────────────────────────────

def test_armar_progreso_estados_y_duraciones():
    filas = [
        {"fase": "PRECALENTAMIENTO", "inicio_s": 0.0, "fin_s": 0.0, "duracion_s": 0.0},
        {"fase": "PRE_VACIO", "inicio_s": 0.0, "fin_s": 700.0, "duracion_s": 700.0},
        {"fase": "CALENTAMIENTO", "inicio_s": 700.0, "fin_s": None, "duracion_s": None},
    ]
    p = pc.armar_progreso(_APLICA, filas, "CALENTAMIENTO", 760.0, _REF)
    assert p["fase_activa"] == "calentamiento"
    assert p["transcurrido_s"] == 760.0
    assert p["fases"] == [
        {"fase": "vacio", "estado": "completada", "duracion_s": 700.0},
        {"fase": "calentamiento", "estado": "activa", "duracion_s": 60.0},
        {"fase": "esterilizacion", "estado": "pendiente", "duracion_s": None},
        {"fase": "descompresion", "estado": "pendiente", "duracion_s": None},
        {"fase": "secado", "estado": "pendiente", "duracion_s": None},
    ]
    assert p["restante_s"] == (3 * MIN - 60.0) + 15 * MIN + 2 * MIN + 13 * MIN


def test_armar_progreso_ciclo_completado():
    filas = [{"fase": f, "inicio_s": 0.0, "fin_s": 1.0, "duracion_s": 1.0}
             for f in ("PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO")]
    p = pc.armar_progreso(_APLICA, filas, "COMPLETADO", 2700.0, _REF)
    assert p["fase_activa"] is None
    assert all(f["estado"] == "completada" for f in p["fases"])
    assert p["restante_s"] == 0.0


def test_armar_progreso_ciclo_cancelado_sin_restante():
    filas = [{"fase": "PRE_VACIO", "inicio_s": 0.0, "fin_s": 30.0, "duracion_s": 30.0}]
    p = pc.armar_progreso(_APLICA, filas, "CANCELADO", 30.0, _REF)
    assert p["fase_activa"] is None
    assert p["restante_s"] is None
    assert p["fases"][0] == {"fase": "vacio", "estado": "completada", "duracion_s": 30.0}
    assert p["fases"][1]["estado"] == "pendiente"
