"""AJ-02 (ajustes 28-oct): agua_intercambiador = OR de dos peticiones
independientes (vacío de la cámara y drenaje), con una sola orden al canal.

Antes, con drenaje frío, CicloState._mantener_drenaje la apagaba (paso 5) y la
fase de vacío la volvía a encender (paso 7) en cada tick de 0,5 s: la
solenoide recibía OFF→ON cada tick. Se cuentan las escrituras al canal con el
EnlaceRegistrador (SetOutput real) y el orden real del tick (drenaje y luego
la fase)."""

from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.asignacion_io import canal_do
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.state_machine.cycle_phases import prevacio as prevacio_mod
from autoclave.state_machine.cycle_phases import secado as secado_mod
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase
from autoclave.state_machine.states.ciclo import CicloState
from tests.helpers.enlace_doble import EnlaceRegistrador

AGUA = canal_do("agua_intercambiador")
VACIO = canal_do("vacio_camara")
TEMP_SEGURA = 40.0
FRIO, CALIENTE = 25.0, 60.0


@pytest.fixture
def equipo(monkeypatch):
    reloj = [1000.0]
    for mod in (prevacio_mod, secado_mod):
        monkeypatch.setattr(mod.time, "monotonic", lambda: reloj[0])
    estado = EstadoAutoclave()
    registro = []
    link = EnlaceRegistrador(reloj, registro)
    set_do = SetOutput(link, estado, profile=None)
    # CicloState solo para su control de drenaje (paso 5 del tick)
    est_ciclo = MagicMock()
    est_ciclo.sensores_temp = {"temp_drenaje": FRIO}
    est_ciclo.get_flag.return_value = False
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = TEMP_SEGURA
    ciclo = CicloState(est_ciclo, set_do, cycle, config, MagicMock())
    return dict(reloj=reloj, estado=estado, link=link, registro=registro,
                set_do=set_do, ciclo=ciclo, drenaje=est_ciclo.sensores_temp)


def _crudas(eq, canal, desde=0):
    """Todas las órdenes que llegaron al enlace para el canal (con las
    reafirmaciones de cada tick) y los ALL_OFF."""
    return [o for (_, o, _) in eq["registro"][desde:] if o.startswith(f"SET DO{canal} ")
            or o == "ALL_OFF"]


def _ordenes(eq, canal, desde=0):
    """Escrituras efectivas al canal: ModbusLink.set_output solo escribe los
    cambios (fc05), así que una reafirmación del mismo valor no cuenta. Se
    exige además, aparte, que ninguna orden OFF cruda llegue durante el vacío."""
    out, previo = [], None
    for o in _crudas(eq, canal, desde):
        if o != previo:
            out.append(o)
        previo = o
    return out


def _desde_primer_on(eq, canal, desde):
    """Índice del registro de la primera orden ON al canal desde `desde` (el
    vacío empieza ahí; antes, en el mismo tick, el drenaje frío reafirma OFF
    sobre un canal ya apagado)."""
    for i in range(desde, len(eq["registro"])):
        if eq["registro"][i][1] == f"SET DO{canal} ON":
            return i
    return len(eq["registro"])


def _estabilizar_drenaje(eq, ticks=4):
    """Ticks con solo el control de drenaje (debounce de 3 lecturas)."""
    for _ in range(ticks):
        eq["ciclo"]._mantener_drenaje()
        eq["reloj"][0] += 0.5


def _pines(eq, canal):
    return eq["link"].pines[canal - 1]


# ── PREVACIO ────────────────────────────────────────────────────────────────

def _prevacio(tiempo_hold=3):
    params = {
        "conteo_pulso_a": 1, "conteo_pulso_b": 0, "conteo_pulso_c": 0, "conteo_pulso_d": 0,
        "presion_baja_pulso_a": 15, "tiempo_adicional_bajo_a": tiempo_hold,
        "presion_alta_pulso_a": 180, "tiempo_adicional_alto_a": 0,
        "timeout_bajo": 10, "timeout_alto": 10,
    }
    est = MagicMock()
    est.sensores_pres = {"pres_camara": 101.3}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: params.get(key)
    config = MagicMock()
    config.get.return_value = None
    cap = MagicMock()
    cap.has_vacuum = True
    return est, cycle, config, cap


def _correr_prevacio(eq):
    est, cycle, config, cap = _prevacio()
    fase = PrevacioFase(est, eq["set_do"], cycle, config, MagicMock(), cap)
    fase.reset()

    def tick():
        eq["ciclo"]._mantener_drenaje()   # paso 5
        fase.update()                     # paso 7
        eq["reloj"][0] += 0.5

    tick()                                 # DECOMPRESION -> VACIO_BAJO
    assert fase._paso == "VACIO_BAJO"
    inicio = len(eq["registro"])
    for _ in range(8):
        tick()                             # VACIO_BAJO, cámara a 101 kPa
    est.sensores_pres["pres_camara"] = 10
    tick()                                 # -> HOLD_BAJO
    assert fase._paso == "HOLD_BAJO"
    while fase._paso == "HOLD_BAJO":
        tick()
    assert fase._paso == "APAGANDO_VACIO"
    inicio = _desde_primer_on(eq, AGUA, inicio)
    durante = _ordenes(eq, AGUA, inicio)
    assert f"SET DO{AGUA} OFF" not in _crudas(eq, AGUA, inicio)
    while fase._paso == "APAGANDO_VACIO":
        tick()
    return inicio, durante


def test_prevacio_drenaje_frio_una_sola_escritura_on_y_ninguna_off(equipo):
    _estabilizar_drenaje(equipo)
    assert _pines(equipo, AGUA) is False
    inicio, durante = _correr_prevacio(equipo)
    assert durante == [f"SET DO{AGUA} ON"]
    # al terminar el vacío, el drenaje frío no la pide: se apaga una vez
    assert _ordenes(equipo, AGUA, inicio) == [f"SET DO{AGUA} ON", f"SET DO{AGUA} OFF"]
    assert _pines(equipo, AGUA) is False


def test_prevacio_el_agua_se_apaga_junto_con_vacio_camara(equipo):
    """El escalonado (_STAGGER_APAGADO_VACIO) se conserva: agua y
    vacio_camara salen en el mismo grupo, después de la bomba."""
    _estabilizar_drenaje(equipo)
    inicio, _ = _correr_prevacio(equipo)
    ordenes = [o for (_, o, _) in equipo["registro"][inicio:]]
    i_vacio = ordenes.index(f"SET DO{VACIO} OFF")
    assert ordenes[i_vacio + 1] == f"SET DO{AGUA} OFF"
    i_bomba = ordenes.index(f"SET DO{canal_do('bomba_vacio')} OFF")
    assert i_bomba < i_vacio
    t = {o: tt for (tt, o, _) in equipo["registro"][inicio:]}
    assert t[f"SET DO{VACIO} OFF"] > t[f"SET DO{canal_do('bomba_vacio')} OFF"]


def test_prevacio_drenaje_caliente_el_agua_no_se_apaga(equipo):
    equipo["drenaje"]["temp_drenaje"] = CALIENTE
    _estabilizar_drenaje(equipo)
    assert _pines(equipo, AGUA) is True
    inicio, _ = _correr_prevacio(equipo)
    assert set(_crudas(equipo, AGUA, inicio)) == {f"SET DO{AGUA} ON"}
    assert _pines(equipo, AGUA) is True


# ── SECADO modos 1, 2 y 3 ───────────────────────────────────────────────────

def _secado(eq, modo):
    params = {
        "modo": modo, "tiempo_secado": 1.0,
        "presion_chaqueta_secado": 200, "rango_chaqueta_secado": 30,
        "presion_baja_secado": 20.0, "presion_alta_secado": 80.0, "timeout_pulso": 10,
    }
    est = MagicMock()
    est.sensores_pres = {"pres_camara": 10.0, "pres_chaqueta": 200.0}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, param, default=None: params.get(param, default)
    config = MagicMock()
    config.get.return_value = None
    fase = SecadoFase(est, eq["set_do"], cycle, config, MagicMock(), MagicMock())
    fase.cap.has_vacuum = True
    fase.reset()
    return fase, est


def _tick(eq, fase):
    eq["ciclo"]._mantener_drenaje()
    r = fase.update()
    eq["reloj"][0] += 0.5
    return r


@pytest.mark.parametrize("modo", [1, 2])
def test_secado_modos_1_y_2_drenaje_frio(equipo, modo):
    _estabilizar_drenaje(equipo)
    fase, _ = _secado(equipo, modo)
    inicio = len(equipo["registro"])
    for _ in range(20):
        assert _tick(equipo, fase) == FaseResult.EN_CURSO
    inicio = _desde_primer_on(equipo, AGUA, inicio)
    assert _ordenes(equipo, AGUA, inicio) == [f"SET DO{AGUA} ON"]
    assert f"SET DO{AGUA} OFF" not in _crudas(equipo, AGUA, inicio)
    equipo["reloj"][0] = fase._timer_fin + 1
    assert _tick(equipo, fase) == FaseResult.COMPLETADO
    assert _ordenes(equipo, AGUA, inicio) == [f"SET DO{AGUA} ON", f"SET DO{AGUA} OFF"]


def test_secado_modo_3_drenaje_frio(equipo):
    _estabilizar_drenaje(equipo)
    fase, est = _secado(equipo, 3)
    est.sensores_pres["pres_camara"] = 50.0
    inicio = len(equipo["registro"])
    for _ in range(10):
        _tick(equipo, fase)                # VACIO_BAJO
    assert fase._sub_estado == "VACIO_BAJO"
    inicio = _desde_primer_on(equipo, AGUA, inicio)
    assert _ordenes(equipo, AGUA, inicio) == [f"SET DO{AGUA} ON"]
    assert f"SET DO{AGUA} OFF" not in _crudas(equipo, AGUA, inicio)
    est.sensores_pres["pres_camara"] = 15.0
    _tick(equipo, fase)                    # -> AIRE_ALTO: fin de este vacío
    assert fase._sub_estado == "AIRE_ALTO"
    assert _ordenes(equipo, AGUA, inicio) == [f"SET DO{AGUA} ON", f"SET DO{AGUA} OFF"]


@pytest.mark.parametrize("modo", [1, 2])
def test_secado_drenaje_caliente_no_apaga_el_agua(equipo, modo):
    equipo["drenaje"]["temp_drenaje"] = CALIENTE
    _estabilizar_drenaje(equipo)
    fase, _ = _secado(equipo, modo)
    inicio = len(equipo["registro"])
    for _ in range(6):
        _tick(equipo, fase)
    equipo["reloj"][0] = fase._timer_fin + 1
    _tick(equipo, fase)
    assert set(_crudas(equipo, AGUA, inicio)) == {f"SET DO{AGUA} ON"}
    assert _pines(equipo, AGUA) is True


# ── SetOutput: peticiones ───────────────────────────────────────────────────

def test_vacio_off_con_drenaje_caliente_no_apaga_el_agua(equipo):
    s = equipo["set_do"]
    s.agua_intercambiador_on()        # drenaje caliente
    s.vacio_camara_on()
    s.vacio_camara_off()
    assert set(_crudas(equipo, AGUA)) == {f"SET DO{AGUA} ON"}
    assert s.peticiones_agua_intercambiador == {"vacio": False, "drenaje": True}


def test_drenaje_off_durante_el_vacio_no_apaga_el_agua(equipo):
    s = equipo["set_do"]
    s.vacio_camara_on()
    for _ in range(5):
        s.agua_intercambiador_off()   # drenaje frío, cada tick
        s.vacio_camara_on()
    assert set(_crudas(equipo, AGUA)) == {f"SET DO{AGUA} ON"}
    assert _pines(equipo, AGUA) is True


def test_sin_lectura_de_drenaje_pide_agua(equipo):
    equipo["drenaje"].pop("temp_drenaje")
    equipo["ciclo"]._mantener_drenaje()
    assert _pines(equipo, AGUA) is True
    equipo["set_do"].vacio_camara_on()
    equipo["set_do"].vacio_camara_off()
    assert _pines(equipo, AGUA) is True
    assert f"SET DO{AGUA} OFF" not in _crudas(equipo, AGUA)


def test_all_off_apaga_todo_y_borra_las_peticiones(equipo):
    s = equipo["set_do"]
    s.agua_intercambiador_on()
    s.vacio_camara_on()
    s.reset_all_outputs()
    assert not any(equipo["link"].pines)
    assert s.peticiones_agua_intercambiador == {"vacio": False, "drenaje": False}
    # nada vuelve a encender el agua por sí solo
    s.vacio_camara_off()
    assert _pines(equipo, AGUA) is False


def test_all_off_sin_confirmar_tambien_borra_las_peticiones(equipo):
    s = equipo["set_do"]
    equipo["link"].all_off_ok = False
    s.agua_intercambiador_on()
    s.vacio_camara_on()
    assert s.reset_all_outputs() is False
    assert _pines(equipo, AGUA) is False
    assert s.peticiones_agua_intercambiador == {"vacio": False, "drenaje": False}


def test_paro_sigue_apagando_todo(equipo):
    s = equipo["set_do"]
    s.agua_intercambiador_on()
    s.vacio_camara_on()
    equipo["estado"].set_flag("PARO_EMERGENCIA", True)
    equipo["estado"].set_flag("PARO_REAL", True)
    s.apagar_por_paro(inmediato=True)
    assert not any(equipo["link"].pines)
    # con el paro, ninguna petición enciende el agua
    s.agua_intercambiador_on()
    s.vacio_camara_on()
    assert _pines(equipo, AGUA) is False
    assert _pines(equipo, VACIO) is False


def test_inhibida_no_se_enciende_por_ninguna_peticion(equipo):
    s = equipo["set_do"]
    s.inhibidas = {"agua_intercambiador"}
    s.agua_intercambiador_on()
    s.vacio_camara_on()
    assert _pines(equipo, AGUA) is False
    assert _pines(equipo, VACIO) is True


def test_orden_directa_al_canal_deja_las_peticiones_coherentes(equipo):
    """Modo prueba / cortes por canal: OFF borra las dos; ON cuenta como
    petición del drenaje (ante duda, el agua queda pedida)."""
    s = equipo["set_do"]
    s.vacio_camara_on()
    s.agua_intercambiador_on()
    s.set_output(AGUA, False)
    assert _pines(equipo, AGUA) is False
    assert s.peticiones_agua_intercambiador == {"vacio": False, "drenaje": False}
    s.set_output(AGUA, True)
    assert s.peticiones_agua_intercambiador == {"vacio": False, "drenaje": True}
    s.vacio_camara_off()
    assert _pines(equipo, AGUA) is True
