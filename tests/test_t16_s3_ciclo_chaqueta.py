# tests/test_t16_s3_ciclo_chaqueta.py
#
# s3 (tanda 16): CicloState y la chaqueta.
#   - VCH §4.7 (VCH Q): _mantener_chaqueta no actúa sobre vapor_chaqueta
#     mientras la fase tenga controla_vapor_chaqueta; SUM-06 y el corte siguen;
#     retoma la consigna cuando la fase ya no la controla.
#   - D-CHQ / SAF-09: corte único pres_chaqueta >= presion_max_chaqueta_control
#     (375 kPa abs por defecto) en los dos modos; CIC-18 solo en modo chaqueta
#     en CALENTAMIENTO y ESTERILIZACION; sin lectura en modo chaqueta -> OFF;
#     el corte gana a la orden de la fase en el mismo tick.
#   - P8 (SAF-09): _registrar_consigna_chaqueta dentro de try.
#   - V-02 (a): la tolerancia de DI vencida apaga también las fuentes de vapor.

import time
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import limites_equipo as le
from autoclave.core.runtime import presion_sin_lectura
from autoclave.installation.profile import MODO_CAMARA, MODO_CHAQUETA
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_18, SUM_06, Nivel
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from tests.helpers.alarmas_helpers import ultima_activacion

pytestmark = pytest.mark.req("T16-S3")


class FaseDoble:
    """Fase mínima: nombre, resultado configurable y, opcionalmente, una orden
    propia a vapor_chaqueta en update() (como PRECALENTAMIENTO o SECADO, o
    CALENTAMIENTO/ESTERILIZACION en modo chaqueta)."""

    def __init__(self, name, set_do=None, estado=None, controla=None, enciende=False):
        self.name = name
        self.resultado = FaseResult.EN_CURSO
        self._set_do = set_do
        self._estado = estado
        self._enciende = enciende
        self.inhibir_visto = []
        if controla is not None:
            self.controla_vapor_chaqueta = controla

    def reset(self):
        pass

    def update(self):
        if self._estado is not None:
            self.inhibir_visto.append(self._estado.inhibir_vapor_chaqueta)
        if self._enciende and self._estado.inhibir_vapor_chaqueta is not True:
            self._set_do.vapor_chaqueta_on()
        elif self._enciende:
            self._set_do.vapor_chaqueta_off()
        return self.resultado


class FaseQueEnciendeSiempre(FaseDoble):
    """Fase que ignora el corte y enciende la chaqueta (PRECALENTAMIENTO y
    SECADO no leen inhibir_vapor_chaqueta)."""

    def update(self):
        self._set_do.vapor_chaqueta_on()
        return self.resultado


def _ciclo(pres_chaqueta=300.0, modo=MODO_CAMARA, vapor=1, flags=None):
    flags = {} if flags is None else flags
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 120.0}
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": pres_chaqueta,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": vapor}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    estado.motivo_fallo = ""
    cycle = MagicMock()
    cycle.get_param.return_value = None
    cycle.copia.return_value = cycle
    cycle.sensores = None
    config = MagicMock()
    config.get.return_value = None
    am = AlarmManager()
    set_do = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, am)
    ciclo.reset()
    estado.modo_vapor = modo
    # la chaqueta sin lectura se prueba aquí como corte, no como SEN-xx
    ciclo._pres_vigilados = [presion_sin_lectura.CAMARA]
    ciclo._protocolo = MagicMock()
    return ciclo, estado, set_do, am


def _con_fases(ciclo, *fases):
    ciclo._fases = list(fases)
    ciclo._fase_idx = 0
    return ciclo


def _ordenes_chaqueta(set_do):
    return [c[0] for c in set_do.mock_calls
            if c[0] in ("vapor_chaqueta_on", "vapor_chaqueta_off")]


def _cic18(am):
    return [i for i in am.activas() if i.codigo == CIC_18]


# ── VCH §4.7: _mantener_chaqueta con la fase que controla la chaqueta ──────

def test_cic18_es_aviso_no_bloqueante():
    d = CATALOGO[CIC_18]
    assert d.nivel is Nivel.AVISO and d.bloquea_inicio is False


def test_no_actua_si_la_fase_controla_la_chaqueta():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=150.0, modo=MODO_CHAQUETA)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    estado.inhibir_vapor_chaqueta = False
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == []          # bajo la consigna, pero no la toca
    ciclo._mantener_chaqueta()
    estado.sensores_pres["pres_chaqueta"] = 360.0   # sobre la banda: tampoco
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == []


def test_controla_debe_ser_true_estricto():
    # un MagicMock (doble de fase) no cuenta como "controla"
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=150.0)
    fase = MagicMock()
    fase.name = "CALENTAMIENTO"
    _con_fases(ciclo, fase)
    estado.inhibir_vapor_chaqueta = False
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_on"]


def test_retoma_la_consigna_cuando_la_fase_ya_no_la_controla():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=150.0, modo=MODO_CHAQUETA)
    est = FaseDoble("ESTERILIZACION", controla=True)
    desc = FaseDoble("DESCOMPRESION")
    _con_fases(ciclo, est, desc)
    estado.inhibir_vapor_chaqueta = False
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == []
    ciclo._fase_idx = 1                             # terminó ESTERILIZACION
    ciclo._mantener_chaqueta()
    # sin consigna del programa (doble): presion_chaqueta 320 ± 50 -> ON a 150
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_on"]


def test_retoma_en_run_al_completar_esterilizacion():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=150.0, modo=MODO_CHAQUETA)
    est = FaseDoble("ESTERILIZACION", controla=True)
    desc = FaseDoble("DESCOMPRESION")
    _con_fases(ciclo, est, desc)
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert _ordenes_chaqueta(set_do) == []
    est.resultado = FaseResult.COMPLETADO
    ciclo.run()                                     # avanza a DESCOMPRESION
    assert ciclo._fase_idx == 1
    ciclo.run()
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_on"]


def test_sum06_sigue_con_la_fase_que_controla():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=150.0, modo=MODO_CHAQUETA, vapor=0)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    ciclo.am_mock = MagicMock()
    ciclo.alarm_manager = ciclo.am_mock
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_off"]
    assert ultima_activacion(ciclo.am_mock)[0] == SUM_06


def test_sin_dato_off_con_la_fase_que_controla():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=None, modo=MODO_CHAQUETA)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_off"]


def test_con_el_corte_apaga_aunque_la_fase_controle():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    estado.inhibir_vapor_chaqueta = True
    ciclo._mantener_chaqueta()
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_off"]


# ── D-CHQ / SAF-09: corte único ────────────────────────────────────────────

def test_el_corte_usa_el_parametro_del_equipo():
    assert le.presion_max_chaqueta_control(MagicMock()) == 375.0


@pytest.mark.parametrize("modo", [MODO_CAMARA, MODO_CHAQUETA])
@pytest.mark.parametrize("pres,corta", [(374.9, False), (375.0, True), (390.0, True)])
def test_corte_en_los_dos_modos(modo, pres, corta):
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=pres, modo=modo)
    assert ciclo._actualizar_corte_chaqueta() is corta
    assert estado.inhibir_vapor_chaqueta is corta


def test_corte_modo_camara_sin_cic18_y_off_en_el_tick():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CAMARA)
    fase = FaseQueEnciendeSiempre("CALENTAMIENTO", set_do=set_do)
    _con_fases(ciclo, fase)
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_off"
    assert _cic18(am) == []


def test_corte_modo_chaqueta_activa_cic18_y_se_resuelve():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    fase = FaseDoble("CALENTAMIENTO", set_do=set_do, estado=estado, controla=True,
                     enciende=True)
    _con_fases(ciclo, fase)
    ciclo.run()
    activas = _cic18(am)
    assert len(activas) == 1
    assert activas[0].valores["pres"] == pytest.approx(380.0)
    assert activas[0].valores["maximo"] == pytest.approx(375.0)
    assert activas[0].valores["fase"]
    assert fase.inhibir_visto == [True]             # la fase lo vio antes de update()
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_off"
    ciclo.run()
    assert len(_cic18(am)) == 1                     # una sola instancia
    estado.sensores_pres["pres_chaqueta"] = 360.0
    ciclo.run()
    assert _cic18(am) == []
    assert estado.inhibir_vapor_chaqueta is False
    assert fase.inhibir_visto[-1] is False
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"


@pytest.mark.parametrize("nombre", ["PRECALENTAMIENTO", "PRE_VACIO", "DESCOMPRESION", "SECADO"])
def test_corte_modo_chaqueta_fuera_de_cal_est_sin_cic18(nombre):
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    _con_fases(ciclo, FaseQueEnciendeSiempre(nombre, set_do=set_do))
    ciclo.run()
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_off"
    assert _cic18(am) == []


def test_cic18_se_resuelve_al_salir_de_la_fase():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    est = FaseDoble("ESTERILIZACION", controla=True)
    desc = FaseDoble("DESCOMPRESION")
    _con_fases(ciclo, est, desc)
    ciclo.run()
    assert len(_cic18(am)) == 1
    est.resultado = FaseResult.COMPLETADO
    ciclo.run()
    ciclo.run()                                     # primer tick de DESCOMPRESION
    assert _cic18(am) == []
    assert estado.inhibir_vapor_chaqueta is True    # el corte sigue (sin aviso)


def test_cic18_se_resuelve_al_terminar_el_ciclo():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    fase = FaseDoble("CALENTAMIENTO", controla=True)
    _con_fases(ciclo, fase)
    ciclo.run()
    assert len(_cic18(am)) == 1
    fase.resultado = FaseResult.FALLO
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo.run()                                     # resultado pendiente
    assert _cic18(am) == []


def test_el_corte_gana_a_la_fase_en_el_mismo_tick():
    """La fase (PRECALENTAMIENTO/SECADO no leen el corte) enciende la chaqueta
    en update(); CICLO la vuelve a apagar después, en el mismo tick."""
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=376.0, modo=MODO_CAMARA)
    _con_fases(ciclo, FaseQueEnciendeSiempre("PRECALENTAMIENTO", set_do=set_do))
    set_do.reset_mock()
    ciclo.run()
    # paso 5 (_mantener_chaqueta) apaga, la fase enciende, CICLO vuelve a apagar
    assert _ordenes_chaqueta(set_do) == ["vapor_chaqueta_off", "vapor_chaqueta_on",
                                         "vapor_chaqueta_off"]


def test_sin_corte_la_fase_conserva_su_orden():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=300.0, modo=MODO_CAMARA)
    _con_fases(ciclo, FaseQueEnciendeSiempre("PRECALENTAMIENTO", set_do=set_do))
    set_do.reset_mock()
    ciclo.run()
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"


@pytest.mark.parametrize("pres", [None, float("nan")])
def test_sin_lectura_en_modo_chaqueta_off_e_inhibe(pres):
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=pres, modo=MODO_CHAQUETA)
    fase = FaseDoble("CALENTAMIENTO", set_do=set_do, estado=estado, controla=True,
                     enciende=True)
    _con_fases(ciclo, fase)
    ciclo.run()
    assert estado.inhibir_vapor_chaqueta is True
    assert fase.inhibir_visto == [True]
    assert "vapor_chaqueta_on" not in _ordenes_chaqueta(set_do)
    assert _cic18(am) == []                         # el aviso es solo por presión


def test_sin_lectura_en_modo_camara_no_es_corte():
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=None, modo=MODO_CAMARA)
    assert ciclo._actualizar_corte_chaqueta() is False
    assert estado.inhibir_vapor_chaqueta is False


def test_error_al_evaluar_el_corte_es_falla_segura(monkeypatch):
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=300.0, modo=MODO_CHAQUETA)

    def falla(_config):
        raise RuntimeError("config rota")
    monkeypatch.setattr(le, "presion_max_chaqueta_control", falla)
    assert ciclo._actualizar_corte_chaqueta() is True
    assert estado.inhibir_vapor_chaqueta is True


def test_el_corte_se_recalcula_antes_de_un_retorno_temprano():
    """Cancelación en el mismo tick: inhibir ya refleja este tick."""
    flags = {}
    ciclo, estado, set_do, _ = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA, flags=flags)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    ciclo.run()
    assert estado.inhibir_vapor_chaqueta is True
    estado.sensores_pres["pres_chaqueta"] = 300.0
    flags["CICLO_CANCELADO"] = True
    ciclo.run()
    assert estado.inhibir_vapor_chaqueta is False


def test_reset_limpia_el_corte_y_el_aviso():
    ciclo, estado, set_do, am = _ciclo(pres_chaqueta=380.0, modo=MODO_CHAQUETA)
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO", controla=True))
    ciclo.run()
    assert len(_cic18(am)) == 1
    ciclo.reset()
    assert _cic18(am) == [] and estado.inhibir_vapor_chaqueta is False


# ── P8 (SAF-09): _registrar_consigna_chaqueta dentro de try ────────────────

def test_registrar_consigna_que_lanza_no_rompe_reset(caplog):
    ciclo, estado, set_do, _ = _ciclo()

    def falla():
        raise RuntimeError("consigna rota")
    ciclo._registrar_consigna_chaqueta = falla
    ciclo.reset()
    assert ciclo._fase_idx == 0
    assert estado.fase_ciclo == ciclo._fases[0].name
    assert "no se pudo registrar la consigna de chaqueta" in caplog.text


# ── V-02 (a): tolerancia de DI vencida ─────────────────────────────────────

def test_di_vencida_apaga_tambien_las_fuentes_de_vapor(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    ciclo, estado, set_do, _ = _ciclo(flags={"PARO_EMERGENCIA": True})
    fase = FaseDoble("CALENTAMIENTO")
    _con_fases(ciclo, fase)
    assert ciclo.run() == CicloResultado.EN_CURSO
    for orden in ("vapor_camara_off", "vapor_chaqueta_off", "vapor_generador_off",
                  "vapor_caldera_off"):
        getattr(set_do, orden).assert_called()
    for orden in ("vapor_generador_on", "vapor_caldera_on", "vapor_camara_on",
                  "vapor_chaqueta_on"):
        getattr(set_do, orden).assert_not_called()


def test_di_vencida_con_setoutput_sin_fuentes_no_lanza(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    ciclo, estado, _, _ = _ciclo(flags={"PARO_EMERGENCIA": True})

    class SetDoSinFuentes:
        def __init__(self):
            self.ordenes = []

        def vapor_camara_off(self):
            self.ordenes.append("vapor_camara_off")

        def vapor_chaqueta_off(self):
            self.ordenes.append("vapor_chaqueta_off")

    ciclo.set_do = SetDoSinFuentes()
    _con_fases(ciclo, FaseDoble("CALENTAMIENTO"))
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert ciclo.set_do.ordenes == ["vapor_camara_off", "vapor_chaqueta_off"]


def test_modulo_conserva_la_tolerancia():
    assert modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG == 4.0
