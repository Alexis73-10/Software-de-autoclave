"""Vaciado de chaqueta tras un ciclo de líquidos con enfriamiento modo 4/5:
armado al confirmar el COMPLETADO, pulsos de descompresion_chaqueta 5/5 s
durante 30 s desde la primera puerta abierta, cancelaciones y limpieza."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.catalogo import SUM_06
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states import preparado as preparado_mod
from autoclave.state_machine.states import vaciado_chaqueta as vc
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from autoclave.state_machine.states.preparado import preparado_state


class _SetDo:
    """Registra el último valor ordenado a cada salida (`<nombre>_on/_off`).
    El apagado por paro es un mock que no toca `salidas`: así las pruebas
    ven las órdenes propias del vaciado."""

    def __init__(self):
        self.salidas = {}
        self.apagar_por_paro = MagicMock()
        self._otros = {}

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        for sufijo, valor in (("_on", True), ("_off", False)):
            if nombre.endswith(sufijo) and not nombre.startswith("buzer"):
                salida = nombre[: -len(sufijo)]
                return lambda: self.salidas.__setitem__(salida, valor)
        return self._otros.setdefault(nombre, MagicMock())


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


@pytest.fixture
def reloj(monkeypatch):
    """Reloj monotónico falso solo para preparado.py (no reemplaza
    time.monotonic del proceso)."""
    t = [1000.0]
    monkeypatch.setattr(preparado_mod, "time", SimpleNamespace(monotonic=lambda: t[0]))
    return t


def _preparado(puertas=(1, 1), pres_chaqueta=250.0, vapor=1, flags=None, estado_vaciado=vc.PENDIENTE):
    flags = flags if flags is not None else {}
    di = {f"puerta_{n}_cerrada": v for n, v in enumerate(puertas, start=1)}
    di["vapor_suministro"] = vapor
    estado = SimpleNamespace(sensores_di=di, sensores_pres={"pres_chaqueta": pres_chaqueta},
                             get_flag=lambda f: flags.get(f, False))
    estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    if estado_vaciado == vc.PENDIENTE:
        estado.vaciado_chaqueta.armar()
    set_do = _SetDo()
    p = preparado_state(MagicMock(), estado, set_do, MagicMock(), _Config())
    p.supervisor = MagicMock(return_value=True)
    p.mantener_chaqueta = MagicMock(return_value=True)
    p.mantener_presion_camara = MagicMock(return_value=True)
    p.mantener_drenaje = MagicMock(return_value=True)
    p.puertas_cerradas = MagicMock(return_value=True)
    p.camara_segura = MagicMock(return_value=True)
    p._alarma_bloquea_inicio = MagicMock(return_value=False)
    return p, estado, set_do, flags


# ── Función pura del temporizador ─────────────────────────────────────────

@pytest.mark.parametrize("e,abierta", [(0.0, True), (4.9, True), (5.0, False), (9.9, False),
                                       (10.0, True), (19.0, False), (24.9, True),
                                       (29.9, False), (30.0, False), (45.0, False)])
def test_valvula_abierta_pulsos_5_5_hasta_30(e, abierta):
    assert vc.valvula_abierta(e) is abierta
    assert vc.terminado(e) is (e >= 30.0)


# ── Armado en CicloState ──────────────────────────────────────────────────

def _ciclo(tipo_carga="liquido", modo=4):
    flags = {"CICLO_CONFIRMADO": True}
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 25.0}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    params = {("globals", "tipo_carga"): tipo_carga, ("descompresion", "modo"): modo}

    def get_param(*a, default=None):
        if tipo_carga is _ILEGIBLE and a == ("globals", "tipo_carga"):
            raise ValueError("ilegible")
        return params.get(a, default)
    cycle.get_param.side_effect = get_param
    ciclo = CicloState(estado, set_do, cycle, MagicMock(), MagicMock())
    ciclo.reset()
    set_do.reset_mock()
    return ciclo, estado, set_do, flags


_ILEGIBLE = object()


@pytest.mark.parametrize("tipo_carga,modo", [("liquido", 4), ("liquido", 5), (_ILEGIBLE, 4)])
def test_completado_liquido_4_5_arma_y_apaga_chaqueta(tipo_carga, modo):
    ciclo, estado, set_do, _ = _ciclo(tipo_carga, modo)
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    assert ciclo.run() == CicloResultado.COMPLETADO
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    set_do.vapor_chaqueta_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()


@pytest.mark.parametrize("tipo_carga,modo", [("solido", 4), ("solido", 5),
                                             ("liquido", 2), ("liquido", 3), ("liquido", 0)])
def test_solido_u_otros_modos_no_arman(tipo_carga, modo):
    ciclo, estado, set_do, _ = _ciclo(tipo_carga, modo)
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    assert ciclo.run() == CicloResultado.COMPLETADO
    assert estado.vaciado_chaqueta.estado == vc.INACTIVO


@pytest.mark.parametrize("resultado", [CicloResultado.FALLO, CicloResultado.CANCELADO])
def test_fallo_o_cancelado_no_arman(resultado):
    ciclo, estado, _, _ = _ciclo("liquido", 4)
    ciclo._resultado_pendiente = resultado
    assert ciclo.run() == resultado
    assert estado.vaciado_chaqueta.estado == vc.INACTIVO


def test_apertura_automatica_confirma_y_arma():
    ciclo, estado, _, flags = _ciclo("liquido", 5)
    flags["CICLO_CONFIRMADO"] = False
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    ciclo._mantener_valvula_reposo = MagicMock()
    ciclo._mantener_apertura_automatica = lambda: flags.__setitem__("CICLO_CONFIRMADO", True)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert ciclo.run() == CicloResultado.COMPLETADO
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE


def test_ciclo_nuevo_lo_limpia():
    ciclo, estado, _, _ = _ciclo("liquido", 4)
    estado.vaciado_chaqueta.armar()
    ciclo.reset()
    assert estado.vaciado_chaqueta.estado == vc.INACTIVO


# ── PREPARADO ─────────────────────────────────────────────────────────────

def _abrir(p):
    """Tres ticks seguidos de puerta abierta (BAJO 3): el tercero arranca."""
    for _ in range(vc._TICKS_APERTURA):
        p.run()


def test_pendiente_con_puertas_cerradas_salidas_off_y_no_listo(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 1))
    assert p.run() is False
    assert set_do.salidas["vapor_chaqueta"] is False
    assert set_do.salidas["descompresion_chaqueta"] is False
    p.mantener_chaqueta.assert_not_called()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE


def test_tres_ticks_de_puerta_abierta_para_arrancar(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 0))
    p.run()
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    assert set_do.salidas["descompresion_chaqueta"] is False
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO
    assert set_do.salidas["descompresion_chaqueta"] is True
    assert set_do.salidas["vapor_chaqueta"] is True


def test_parpadeo_de_di_no_arranca(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 1))
    di = estado.sensores_di
    for v in [0, 1, 0, 0, None, 0, 0, 1]:        # nunca 3 seguidos
        di["puerta_1_cerrada"] = v
        p.run()
        assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    di["puerta_1_cerrada"] = 0
    p.run()
    p.run()
    p.run(datos_vigentes=False)                  # no vigente: reinicia la cuenta
    p.run()
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    assert set_do.salidas["descompresion_chaqueta"] is False
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO


def test_secuencia_5_5_hasta_30_s(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 0))
    p.run()
    p.run()                                      # t0 = tercer tick
    esperado, obtenido = [], []
    for s in range(0, 31):
        reloj[0] = 1000.0 + s
        p.run()
        obtenido.append(set_do.salidas["descompresion_chaqueta"])
        esperado.append(s < 30 and (s // 5) % 2 == 0)
        assert set_do.salidas["vapor_chaqueta"] is (s < 30)
    assert obtenido == esperado
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    # el tick del fin deja el vapor en OFF sin mantener_chaqueta; desde el
    # siguiente vuelve la lógica normal
    p.mantener_chaqueta.assert_not_called()
    p.run()
    p.mantener_chaqueta.assert_called_once()


def test_cierre_de_puerta_antes_de_30_s_corta(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    assert set_do.salidas["descompresion_chaqueta"] is True
    reloj[0] += 12
    estado.sensores_di["puerta_1_cerrada"] = 1
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False
    p.run()
    p.mantener_chaqueta.assert_called_once()


def test_fin_deja_vapor_off_sin_esperar_al_confirmador(reloj):
    """BAJO 5: con mantener_chaqueta real y la presión sobre el objetivo, el
    vapor queda en OFF desde el tick del fin."""
    p, estado, set_do, _ = _preparado(puertas=(0, 1), pres_chaqueta=320.0)
    del p.mantener_chaqueta                      # la real
    p.cycle.get_param.side_effect = lambda s, k: {"presion_chaqueta": 300.0,
                                                  "rango_presion_chaqueta": 30.0}[k]
    _abrir(p)
    assert set_do.salidas["vapor_chaqueta"] is True
    estado.sensores_di["puerta_1_cerrada"] = 1
    for _ in range(3):
        p.run()
        assert set_do.salidas["vapor_chaqueta"] is False


def test_una_sola_vez_por_ciclo(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    estado.sensores_di["puerta_1_cerrada"] = 1
    p.run()
    estado.sensores_di["puerta_1_cerrada"] = 0
    for _ in range(5):
        reloj[0] += 1
        p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert p.mantener_chaqueta.call_count == 5


@pytest.mark.parametrize("puertas,vigentes", [((None, 1), True), ((None, None), True),
                                              ((0, 1), False)])
def test_di_sin_dato_o_no_vigente_no_dispara(reloj, puertas, vigentes):
    p, estado, set_do, _ = _preparado(puertas=puertas)
    for _ in range(5):
        p.run(datos_vigentes=vigentes)
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    assert set_do.salidas["descompresion_chaqueta"] is False


def test_di_no_vigente_en_curso_cancela(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    reloj[0] += 2
    p.run(datos_vigentes=False)
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


def test_di_none_en_curso_con_otra_puerta_en_cero_sigue(reloj):
    """Una puerta abierta explícita (0) basta para seguir aunque la otra no
    tenga dato; con todas sin dato se cancela."""
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    estado.sensores_di["puerta_2_cerrada"] = None
    reloj[0] += 1
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO
    estado.sensores_di["puerta_1_cerrada"] = None
    reloj[0] += 1
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


@pytest.mark.parametrize("pres", [375.0, 380.0, None, float("nan"), 0.0, -5.0])
def test_vapor_off_en_corte_o_sin_lectura_y_los_pulsos_siguen(reloj, pres):
    p, estado, set_do, _ = _preparado(puertas=(0, 1), pres_chaqueta=pres)
    _abrir(p)
    assert set_do.salidas["vapor_chaqueta"] is False
    assert set_do.salidas["descompresion_chaqueta"] is True
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO


def test_error_al_evaluar_el_vapor_falla_cerrada(reloj, monkeypatch):
    def boom(_config):
        raise RuntimeError("x")
    monkeypatch.setattr(preparado_mod.limites_equipo, "presion_max_chaqueta_control", boom)
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO
    assert set_do.salidas["vapor_chaqueta"] is False
    assert set_do.salidas["descompresion_chaqueta"] is True


def test_sum06_durante_el_vaciado(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 1), vapor=0)
    p.run()                                      # PENDIENTE
    p.alarm_manager.activar.assert_any_call(SUM_06, estado="Preparado")
    estado.sensores_di["puerta_1_cerrada"] = 0
    _abrir(p)
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO
    assert set_do.salidas["vapor_chaqueta"] is False
    assert set_do.salidas["descompresion_chaqueta"] is True
    estado.sensores_di["vapor_suministro"] = 1
    reloj[0] += 1
    p.run()
    p.alarm_manager.resolver.assert_any_call(SUM_06)
    assert set_do.salidas["vapor_chaqueta"] is True


def test_paro_cancela_y_apaga_las_salidas(reloj):
    p, estado, set_do, flags = _preparado(puertas=(0, 1))
    _abrir(p)
    assert set_do.salidas["vapor_chaqueta"] is True
    assert set_do.salidas["descompresion_chaqueta"] is True
    flags["PARO_EMERGENCIA"] = True
    assert p.run() is False
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["vapor_chaqueta"] is False
    assert set_do.salidas["descompresion_chaqueta"] is False
    set_do.apagar_por_paro.assert_called()


def test_supervisor_en_falla_cancela(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    p.supervisor.return_value = False
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


def test_estado_seguro_en_curso_cancela(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1))
    _abrir(p)
    p.estado_seguro_activo = lambda: True
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


def test_estado_seguro_con_puerta_abierta_cancela_el_pendiente(reloj):
    p, estado, set_do, _ = _preparado(puertas=(1, 1))
    p.estado_seguro_activo = lambda: True
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    estado.sensores_di["puerta_2_cerrada"] = 0
    p.run()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False


def test_inactivo_no_cambia_la_logica_normal(reloj):
    p, estado, set_do, _ = _preparado(puertas=(0, 1), estado_vaciado=vc.INACTIVO)
    p.run()
    p.mantener_chaqueta.assert_called_once()
    assert "descompresion_chaqueta" not in set_do.salidas


# ── StateMachine, set_active_cycle y modo prueba ──────────────────────────

def _sm(estado):
    from autoclave.state_machine.state_machine import StateMachine
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    return StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                        config=MagicMock(), estado_seguro=MagicMock())


def test_reconstruir_state_machine_conserva_el_vaciado():
    from autoclave.core.runtime.status import EstadoAutoclave
    estado = EstadoAutoclave()
    _sm(estado)
    estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    estado.vaciado_chaqueta.armar()
    _sm(estado)                         # lo que hace set_active_cycle
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE


@pytest.mark.parametrize("destino", [GlobalState.CICLO, GlobalState.FALLA,
                                     GlobalState.PREPARACION])
def test_entrada_a_ciclo_falla_o_preparacion_limpia(destino):
    from autoclave.core.runtime.status import EstadoAutoclave
    estado = EstadoAutoclave()
    sm = _sm(estado)
    estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    estado.vaciado_chaqueta.armar()
    sm.on_state_entry(destino)
    assert estado.vaciado_chaqueta.estado == vc.INACTIVO


def test_entrar_a_modo_prueba_cancela():
    from tests.test_control_loop_test_mode import _make_control_loop
    loop, _, estado = _make_control_loop()
    estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    estado.vaciado_chaqueta.armar()
    ok, _ = loop.enter_test_mode()
    assert ok is True
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    loop.set_do.reset_all_outputs.assert_called_once()


# ── Punta a punta por StateMachine.update ─────────────────────────────────

def _maquina(set_do):
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.state_machine.state_machine import StateMachine
    estado = EstadoAutoclave()
    for f in ("PARO_EMERGENCIA", "PARO_REAL", "FALLO_SUMINISTRO_ELECTRICO"):
        estado.set_flag(f, False)
    estado.sensores_di.update({"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                               "vapor_suministro": 1})
    estado.sensores_pres["pres_chaqueta"] = 250.0
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    params = {("globals", "tipo_carga"): "liquido", ("descompresion", "modo"): 4}
    cycle.get_param.side_effect = lambda *a, default=None: params.get(a, default)
    es = MagicMock()
    es.activo = False
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=cycle,
                      config=_Config(), estado_seguro=es)
    p = sm.preparado
    p.supervisor = MagicMock(return_value=True)
    p.mantener_chaqueta = MagicMock(return_value=True)
    p.mantener_presion_camara = MagicMock(return_value=True)
    p.mantener_drenaje = MagicMock(return_value=True)
    p.camara_segura = MagicMock(return_value=True)
    p._alarma_bloquea_inicio = MagicMock(return_value=False)
    # ciclo terminado COMPLETADO y confirmado
    sm.ciclo._protocolo = MagicMock()
    sm.ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.set_flag("CICLO_CONFIRMADO", True)
    estado.set_machine_state(GlobalState.CICLO)
    sm.prev_state = GlobalState.CICLO
    return sm, estado, es


def test_punta_a_punta_completado_preparado_puerta_abierta(reloj):
    set_do = _SetDo()
    sm, estado, _ = _maquina(set_do)
    sm._camara_segura_tras_ciclo = lambda vigentes: True
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    sm.update()
    assert estado.get_flag("LISTO_PARA_CICLO") is False
    assert set_do.salidas["vapor_chaqueta"] is False
    estado.sensores_di["puerta_2_cerrada"] = 0
    for _ in range(vc._TICKS_APERTURA):
        sm.update()
    assert estado.vaciado_chaqueta.estado == vc.EN_CURSO
    assert set_do.salidas["vapor_chaqueta"] is True
    assert set_do.salidas["descompresion_chaqueta"] is True
    reloj[0] += 30
    sm.update()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


def test_completado_con_camara_no_segura_y_puerta_abierta_cancela(reloj):
    set_do = _SetDo()
    sm, estado, es = _maquina(set_do)
    sm._camara_segura_tras_ciclo = lambda vigentes: False
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
    es.iniciar.assert_called_once()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    es.activo = True
    sm.update()
    assert estado.vaciado_chaqueta.estado == vc.PENDIENTE
    estado.sensores_di["puerta_1_cerrada"] = 0
    sm.update()
    assert estado.vaciado_chaqueta.estado == vc.HECHO
    assert set_do.salidas["descompresion_chaqueta"] is False
    assert set_do.salidas["vapor_chaqueta"] is False


# ── /status ───────────────────────────────────────────────────────────────

from tests.test_t21_fin_de_ciclo_backend import entorno  # noqa: E402,F401


def test_status_publica_el_vaciado(entorno):
    cliente, _, estado, _, _ = entorno
    assert cliente.get("/status").json()["vaciado_chaqueta"] == vc.INACTIVO
    estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    estado.vaciado_chaqueta.armar()
    assert cliente.get("/status").json()["vaciado_chaqueta"] == vc.PENDIENTE
    estado.vaciado_chaqueta.iniciar(0.0)
    assert cliente.get("/status").json()["vaciado_chaqueta"] == vc.EN_CURSO
    estado.vaciado_chaqueta.terminar("x")
    assert cliente.get("/status").json()["vaciado_chaqueta"] == vc.HECHO
