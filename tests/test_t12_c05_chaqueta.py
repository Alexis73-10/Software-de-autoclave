"""J12 (tanda 12, C-05): chaqueta acoplada al programa en CICLO.

consigna = max(Psat(T_est + delta_temp_chaqueta),
               Psat(T_est) + presion_add_esterilizacion + margen_flujo_chaqueta),
banda fija ±10 kPa (ON bajo consigna−10, OFF sobre consigna+10, sin cambio
dentro). Rechazo al guardar si consigna+10 >= 385 (alivio de chaqueta);
advertencia no bloqueante si consigna+10 > 350 (suministro). C-05.9: la misma
regla para presion_chaqueta + rango_presion_chaqueta, que siguen rigiendo
PREPARACION/PREPARADO."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.alarms.catalogo import SUM_06
from autoclave.state_machine.cycle_phases.secado import SecadoFase
from autoclave.state_machine.states.ciclo import CicloState
from tests.alarmas_helpers import ultima_activacion

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"


def _params(nombre="factory/instrumental_134.json", **valores):
    datos = json.loads((CICLOS / nombre).read_text(encoding="utf-8"))
    p = datos["parameters"]
    for ruta, valor in valores.items():
        fase, clave = ruta.split("__")
        p[fase][clave]["value"] = valor
    return p


# ── consigna ───────────────────────────────────────────────────────────────

def test_constantes_de_limites_fisicos():
    assert cp.PRESION_FONDO_ESCALA == 400
    assert cp.PRESION_SUMINISTRO == 350
    assert cp.PRESION_ALIVIO_CAMARA == 385 and cp.PRESION_ALIVIO_CHAQUETA == 385
    assert cp.BANDA_CHAQUETA_KPA == 10


def test_consigna_134_con_9():
    c = cp.consigna_chaqueta(134.0, 9.0, 1.5, 15.0)
    assert c == pytest.approx(328.2, abs=0.2)   # tanda 13 (IF97); antes 326.3
    assert c == pytest.approx(p_saturacion_kpa(134.0) + 9.0 + 15.0)


def test_consigna_121_con_11():
    assert cp.consigna_chaqueta(121.0, 11.0, 1.5, 15.0) == pytest.approx(231.0, abs=0.2)   # tanda 13 (IF97); antes 230.3


def test_consigna_toma_el_delta_de_temperatura_si_es_mayor():
    # sin margen ni presion_add, manda Psat(T_est + delta)
    assert cp.consigna_chaqueta(134.0, 0.0, 1.5, 0.0) == pytest.approx(p_saturacion_kpa(135.5))


def test_consigna_sin_datos_y_defectos():
    assert cp.consigna_chaqueta(None, 9.0) is None
    assert cp.consigna_chaqueta(134.0, None) is None
    assert cp.consigna_chaqueta(134.0, True) is None
    assert cp.consigna_chaqueta(134.0, 9.0) == pytest.approx(cp.consigna_chaqueta(134.0, 9.0, 1.5, 15.0))


# ── control en CICLO ───────────────────────────────────────────────────────

def _ciclo(pres, vapor=1, params=None):
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": pres}
    estado.sensores_di = {"vapor_suministro": vapor}
    set_do = MagicMock()
    cycle = Cycle("p", "Programa", params or _params(esterilizacion__presion_add_esterilizacion=9.0), 2)
    config = MagicMock()
    config.get.return_value = None
    am = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, am)
    return ciclo, set_do, am


def test_on_bajo_consigna_menos_10():
    ciclo, set_do, _ = _ciclo(328.2 - 10.5)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called_once()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_off_sobre_consigna_mas_10():
    ciclo, set_do, _ = _ciclo(328.2 + 10.5)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("pres", [328.2 - 9.5, 300.0 + 28.2, 328.2 + 9.5])
def test_sin_cambio_dentro_de_la_banda(pres):
    ciclo, set_do, _ = _ciclo(pres)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_en_ciclo_no_rige_presion_chaqueta():
    # presion_chaqueta 300 ± 50 abriría a 249 y cerraría a 351; con la
    # consigna 328.2 ± 10, a 340 kPa el vapor se cierra
    ciclo, set_do, _ = _ciclo(340.0)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_se_conserva_secado_excluido():
    ciclo, set_do, _ = _ciclo(100.0)
    ciclo._fase_idx = next(i for i, f in enumerate(ciclo._fases) if isinstance(f, SecadoFase))
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_se_conserva_enfriamiento_4_5_apaga():
    ciclo, set_do, _ = _ciclo(100.0)
    ciclo._fases[ciclo._fase_idx].chaqueta_en_enfriamiento = True
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("pres", [None, float("nan")])
def test_se_conserva_sin_dato_off(pres):
    ciclo, set_do, _ = _ciclo(pres)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_se_conserva_sum_06_sin_vapor():
    ciclo, set_do, am = _ciclo(100.0, vapor=0)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    assert ultima_activacion(am)[0] == SUM_06


def test_programa_sin_datos_de_consigna_usa_presion_chaqueta():
    """DECISIÓN SIN CONFIRMAR (J12): sin T_est / presion_add_esterilizacion
    se conserva el control anterior (presion_chaqueta ± rango)."""
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": 245.0}
    estado.sensores_di = {"vapor_suministro": 1}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 50.0}.get(n)
    ciclo = CicloState(estado, set_do, cycle, MagicMock(), MagicMock())
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called_once()


def test_la_consigna_se_registra_en_el_log_al_iniciar(caplog):
    params = _params(esterilizacion__presion_add_esterilizacion=9.0,
                     globals__presion_chaqueta=350, globals__rango_presion_chaqueta=25)
    ciclo, _, _ = _ciclo(300.0, params=params)
    with caplog.at_level(logging.INFO, logger="autoclave.state_machine.states.ciclo"):
        ciclo.reset()
    texto = caplog.text
    assert "consigna de chaqueta 328.2 kPa" in texto
    # la advertencia no bloqueante del programa (C-05.9) también queda en el log
    assert "advertencia del programa" in texto and "375" in texto


# ── PREPARADO sigue con presion_chaqueta (C-05.8) ──────────────────────────

def test_preparado_sigue_usando_presion_chaqueta():
    from autoclave.state_machine.states.preparado import preparado_state
    estado = MagicMock()
    estado.sensores_di = {"vapor_suministro": 1}
    estado.sensores_pres = {"pres_chaqueta": 340.0}
    set_do = MagicMock()
    cycle = Cycle("p", "Programa", _params(esterilizacion__presion_add_esterilizacion=9.0,
                                           globals__presion_chaqueta=350,
                                           globals__rango_presion_chaqueta=25), 2)
    config = MagicMock()
    config.get.return_value = 5
    p = preparado_state(MagicMock(), estado, set_do, cycle, config)
    p.mantener_chaqueta()
    # 340 < presion_chaqueta (350): la válvula abre en PREPARADO (en CICLO,
    # con la consigna 328.2 ± 10, se cerraría)
    set_do.vapor_chaqueta_on.assert_called()


# ── validación al guardar / cargar (C-05.5, C-05.9) ────────────────────────

def test_consigna_mas_10_igual_o_sobre_385_se_rechaza():
    # T_est 140, presion_add 11, margen 15 → consigna ≈ 385.0; +10 ≥ 385
    c = Cycle("p", "P", _params(globals__presion_chaqueta=300, globals__rango_presion_chaqueta=50), 2)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("esterilizacion", ["temperatura_esterilizacion"], 140.0)
    assert e.value.codigo == cp.CODIGO_LIMITE_CONSIGNA
    consigna = cp.consigna_chaqueta(140.0, 11.0, 1.5, 15.0)
    assert e.value.valor == pytest.approx(round(consigna, 1))
    assert f"{consigna:.1f}" in str(e.value)
    assert c.get_param("esterilizacion", "temperatura_esterilizacion") == 134.0


def test_consigna_justo_bajo_el_alivio_se_guarda_con_advertencia():
    # T_est 138.7 → consigna ≈ 374.40; +10 = 384.40 < 385: se acepta con advertencia
    # (tanda 13, IF97: antes 139 → 384.95; con IF97, 139 da 387.39 y se rechaza)
    c = Cycle("p", "P", _params(), 2)
    c.set_param("esterilizacion", ["temperatura_esterilizacion"], 138.7)
    assert c.get_param("esterilizacion", "temperatura_esterilizacion") == 138.7
    assert cp.ADVERTENCIA_CHAQUETA_ABIERTA in [a for a, _ in c.advertencias(
        "esterilizacion", ["temperatura_esterilizacion"])]


def test_consigna_mas_10_entre_350_y_385_se_guarda_con_advertencia():
    # margen 30: consigna = 315.2 + 30 = 345.2; +10 = 355.2 (sobre el suministro)
    c = Cycle("p", "P", _params(), 2)
    c.set_param("globals", ["margen_flujo_chaqueta"], 30.0)
    assert c.get_param("globals", "margen_flujo_chaqueta") == 30.0
    adv = c.advertencias("globals", ["margen_flujo_chaqueta"])
    assert [a for a, _ in adv] == [cp.ADVERTENCIA_CHAQUETA_ABIERTA]
    assert "quedará abierta durante el ciclo" in adv[0][1]
    assert cp.errores_programa(c.parameters) == []


def test_c_05_9_presion_chaqueta_mas_rango_385_se_rechaza():
    c = Cycle("p", "P", _params(), 2)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("globals", ["presion_chaqueta"], 335)      # 335 + 50 = 385
    assert e.value.codigo == cp.CODIGO_LIMITE_CHAQUETA
    assert c.get_param("globals", "presion_chaqueta") == 300


def test_c_05_9_350_25_se_guarda_con_advertencia_y_sin_migrar():
    params = _params(globals__presion_chaqueta=350, globals__rango_presion_chaqueta=25)
    c = Cycle("p", "P", params, 2)
    assert c.migraciones_correctivas == []
    assert c.get_param("globals", "presion_chaqueta") == 350
    assert c.get_param("globals", "rango_presion_chaqueta") == 25
    assert cp.errores_programa(c.parameters) == []
    assert [a for a, _ in c.advertencias("globals", ["rango_presion_chaqueta"])] == \
        [cp.ADVERTENCIA_CHAQUETA_ABIERTA]
    # editar otro parámetro no repite la advertencia de chaqueta
    assert c.advertencias("esterilizacion", ["tiempo_esterilizacion"]) == []


@pytest.mark.parametrize("nombre", ["user/instrumental_134.json", "user/bowe_dick.json"])
def test_programas_de_usuario_350_25_validos_con_advertencia(nombre):
    datos = json.loads((CICLOS / nombre).read_text(encoding="utf-8"))
    g = datos["parameters"]["globals"]
    assert (g["presion_chaqueta"]["value"], g["rango_presion_chaqueta"]["value"]) == (350, 25)
    assert cp.errores_programa(datos["parameters"]) == []
    assert cp.ADVERTENCIA_CHAQUETA_ABIERTA in [a for a, _ in cp.advertencias_programa(datos["parameters"])]


def test_catalogo_de_delta_y_margen():
    hoja = {"type": "float"}
    assert cp.coercionar(hoja, "globals", ["delta_temp_chaqueta"], 5) == 5
    assert cp.coercionar(hoja, "globals", ["margen_flujo_chaqueta"], 40) == 40
    for fase_ruta, malo in ((["delta_temp_chaqueta"], 5.1), (["margen_flujo_chaqueta"], 40.5),
                            (["delta_temp_chaqueta"], -0.1)):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "globals", fase_ruta, malo)
