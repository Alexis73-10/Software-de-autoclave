# tests/test_preparacion_sum02_electrico.py
#
# 2026-11-04 (decisión del usuario): PREPARACION emite SUM-02 (sin suministro
# eléctrico) con el mismo patrón que PREPARADO.verificar_suministros (A-9:
# sin la DI = sin suministro). El supervisor falla, run() queda en False y la
# chaqueta sigue OFF. Con el suministro de vuelta, SUM-02 se resuelve.

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import SUM_02
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state


def _make(clase, *, flags=None, **di_overrides):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0,
                            "temp_ref": 25.0, "temp_drenaje": 25.0}
    estado.sensores_di = {"paro_emergencia": 1, "agua_bomba": 1, "agua_generador": 1,
                          "aire_comprimido": 1, "vapor_suministro": 1,
                          "suministro_electrico": 1, "agua_camara": 0,
                          "puerta_1_cerrada": 1, "puerta_2_cerrada": 1, **di_overrides}
    flags = flags or {}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    cfg_vals = {"presion_admosferica": 101.3, "rango_presion_atm": 20.0,
                "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
                "tiempo_estable_alarma": 0, "temp_max_apertura": 80.0}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, *a: cfg_vals.get(k)
    params = {"presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
              "tipo_carga": "solido"}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: params.get(n)
    alarmas = AlarmManager()
    set_do = MagicMock()
    return clase(alarmas, estado, set_do, cycle, cfg), alarmas, set_do


def _sum02(alarmas):
    return [i for i in alarmas.activas() if i.codigo == SUM_02]


def _caer(obj, modo):
    if modo == "cero":
        obj.estado.sensores_di["suministro_electrico"] = 0
    else:
        del obj.estado.sensores_di["suministro_electrico"]


@pytest.mark.parametrize("modo", ["cero", "ausente"])
def test_electrico_caido_activa_sum02_y_no_avanza(modo):
    obj, alarmas, set_do = _make(preparacion_state)
    _caer(obj, modo)
    assert obj.run() is False
    assert len(_sum02(alarmas)) == 1
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_flag_y_di_en_cero_activa_sum02():
    obj, alarmas, set_do = _make(preparacion_state,
                                 flags={"FALLO_SUMINISTRO_ELECTRICO": True},
                                 suministro_electrico=0)
    assert obj.run() is False
    assert len(_sum02(alarmas)) == 1
    set_do.vapor_chaqueta_on.assert_not_called()


def test_supervisor_falla_con_electrico_caido():
    obj, _, _ = _make(preparacion_state, suministro_electrico=0)
    assert obj.supervisor() is False
    assert obj.verificar_suministros() is False


def test_sin_duplicados_en_varios_ticks():
    obj, alarmas, _ = _make(preparacion_state, suministro_electrico=0)
    for _ in range(5):
        obj.run()
    assert len(_sum02(alarmas)) == 1


def test_sin_duplicados_entre_preparacion_y_preparado():
    # Misma clave (sin origen): PREPARADO reusa la instancia de PREPARACION
    prep, alarmas, _ = _make(preparacion_state, suministro_electrico=0)
    prep.run()
    listo = preparado_state(alarmas, prep.estado, MagicMock(), prep.cycle, prep.config)
    listo.run()
    assert len(_sum02(alarmas)) == 1


def test_restablecido_resuelve_sum02_y_termina():
    obj, alarmas, _ = _make(preparacion_state, suministro_electrico=0)
    obj.run()
    assert len(_sum02(alarmas)) == 1
    assert alarmas.has_blocking_alarm()
    obj.estado.sensores_di["suministro_electrico"] = 1
    assert obj.run() is True
    # Igual que en PREPARADO: despeje automático al volver la señal (AVISO,
    # sin reconocimiento obligatorio: sale de las activas)
    assert _sum02(alarmas) == []
    assert not alarmas.has_blocking_alarm()


def test_sin_entrada_en_el_perfil_no_vigila():
    obj, alarmas, _ = _make(preparacion_state, suministro_electrico=0)
    obj.profile = {"io_enabled": {}}
    import autoclave.state_machine.states.preparacion as mod
    original = mod.entrada_requerida
    mod.entrada_requerida = lambda p, n: n != "suministro_electrico" and original(None, n)
    try:
        assert obj.verificar_suministros() is True
        assert _sum02(alarmas) == []
    finally:
        mod.entrada_requerida = original


# 2026-11-04 (usuario): SUM-02 también mira el flag FALLO_SUMINISTRO_ELECTRICO,
# con la misma condición que corta la chaqueta (_sin_suministro_electrico)

_AMBOS = [preparacion_state, preparado_state]


@pytest.mark.parametrize("clase", _AMBOS)
def test_flag_con_di_en_uno_activa_sum02_y_corta_chaqueta(clase):
    obj, alarmas, set_do = _make(clase, flags={"FALLO_SUMINISTRO_ELECTRICO": True},
                                 suministro_electrico=1)
    assert obj.run() is False
    assert len(_sum02(alarmas)) == 1
    assert obj.verificar_suministros() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _AMBOS)
def test_sin_flag_y_di_en_uno_sin_alarma(clase):
    obj, alarmas, _ = _make(clase, flags={"FALLO_SUMINISTRO_ELECTRICO": False},
                            suministro_electrico=1)
    obj.run()
    assert _sum02(alarmas) == []
    assert obj.verificar_suministros() is True


@pytest.mark.parametrize("clase", _AMBOS)
def test_flag_sin_duplicados_y_despeje_al_restablecer_ambos(clase):
    flags = {"FALLO_SUMINISTRO_ELECTRICO": True}
    obj, alarmas, _ = _make(clase, flags=flags, suministro_electrico=0)
    for _ in range(5):
        obj.run()
    assert len(_sum02(alarmas)) == 1
    # Solo la DI vuelve: el flag sigue y la alarma también
    obj.estado.sensores_di["suministro_electrico"] = 1
    obj.run()
    assert len(_sum02(alarmas)) == 1
    # Ambos restablecidos: despeje automático
    flags["FALLO_SUMINISTRO_ELECTRICO"] = False
    obj.run()
    assert _sum02(alarmas) == []


@pytest.mark.parametrize("di", [{"suministro_electrico": 0}, {}])
def test_misma_decision_que_preparado(di):
    resultados = []
    for clase in (preparacion_state, preparado_state):
        obj, alarmas, _ = _make(clase, **di)
        if not di:
            del obj.estado.sensores_di["suministro_electrico"]
        ok = obj.verificar_suministros()
        resultados.append((ok, len(_sum02(alarmas))))
    assert resultados[0] == resultados[1]
