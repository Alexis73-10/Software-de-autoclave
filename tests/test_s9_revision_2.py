"""S9 (tanda 9) — correcciones de la revisión ★ pasada 2
(C:/Users/tecni/Documents/_suites_t9/s9_revision_2.md).

- R2-A1: el ProtocoloFallo del ciclo (CicloState) también lee la vigencia de
  la trama AI (proveedor común en el estado, fijado por el ControlLoop); con
  la AI vencida no reabre el aire comprimido. La fase DESCOMPRESION (modos
  4/5) tampoco lo abre con la AI vencida.
- R2-M1: AI vencida = datos no vigentes: no se abre nada nuevo, no cuenta
  para el Principal perdido ni para pasar a solo_lenta (enclavamiento solo
  con el transductor que manda tramas sin lectura), CIC-10 informativo.
- R2-M2: las lecturas de vacío cuentan tramas AI distintas.
- R2-M3: la apertura de puertas (ServicioPuertas) evalúa la cámara con la
  vigencia de la presión.
- R2-B1: /io/test/output falla cerrada si la evaluación no da un dict.
- R2-B2: la espera de la primera AI se mide desde la primera DI vigente.
- R2-B3: ejecutar() usa la presión vigente y no abre el aire con una sola
  lectura de vacío.
- R2-B4: vigencia y número de la trama AI en una sola toma del enlace.
- P-a: con estado seguro o recuperación, el modo prueba tampoco enciende
  aire comprimido de cámara ni el vapor de generador o caldera.
"""

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import salidas_prueba_seguridad as sps
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend
from tests.test_s9_estado_seguro_arranque import _CFG, _Config, _abiertas, _programa
from tests.test_s9_revision_1 import _loop_vivo


def _protocolo(pres=250.0, temp=120.0, modo=2, tipo="solido", ai=(True, None),
               proveedor_en_estado=False):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=modo, tipo=tipo), _Config(_CFG))
    lectura = {"v": ai}
    if proveedor_en_estado:
        estado.lectura_ai = lambda: lectura["v"]
    else:
        prot.lectura_ai = lambda: lectura["v"]
    return prot, estado, set_do, lectura


# ── R2-A1: el protocolo del ciclo usa el proveedor del estado ──────────────

def test_control_loop_publica_el_proveedor_en_el_estado():
    loop = _loop_vivo()
    assert callable(loop.estado.lectura_ai)
    loop.link.edad_ultima_ai.return_value = 10.0
    assert loop.estado.lectura_ai()[0] is False


def test_protocolo_del_ciclo_sin_lectura_propia_usa_el_del_estado():
    prot, _, _, lectura = _protocolo(proveedor_en_estado=True)
    lectura["v"] = (False, None)
    assert prot._leer_ai() == (False, None)


def test_estado_sin_proveedor_es_vigente():
    prot = ProtocoloFallo(MagicMock(), MagicMock(), _programa(), _Config(_CFG))
    assert prot._leer_ai() == (True, None)


def test_fallo_modo4_presurizado_confirmacion_pendiente_ai_vencida_no_abre_aire():
    """Escenario de la revisión: FALLO en DESCOMPRESION modo 4 con líquido,
    confirmación pendiente (el CicloState llama update()), DI viva y AI
    muerta con la presión congelada bajo la contrapresión."""
    prot, estado, set_do, lectura = _protocolo(pres=250.0, temp=120.0, modo=4, tipo="liquido",
                                              proveedor_en_estado=True)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 150.0          # congelada
    lectura["v"] = (False, None)
    set_do.reset_mock()
    for _ in range(10):
        prot.update()
    assert "aire_comprimido_camara_on" not in _abiertas(set_do)
    assert "aire_comprimido_camara_off" in [c[0] for c in set_do.method_calls]


def test_fase_descompresion_modo4_no_abre_aire_comprimido_con_ai_vencida():
    from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 150.0
    estado.sensores_temp["temp_camara"] = 120.0
    estado.lectura_ai = lambda: (False, None)
    set_do = MagicMock()
    fase = DescompresionFase.__new__(DescompresionFase)
    fase.estado, fase.set_do = estado, set_do
    fase.cycle = _programa(modo=4, tipo="liquido")
    fase.config = _Config(_CFG)
    fase._t_aire_comprimido = None
    fase._t_pulso_chaqueta = None
    fase._chaqueta_abierta = False
    fase._lecturas_enfriada = 0
    fase._sub_etapa = "enfriamiento"
    fase._tick_sub_enfriamiento("modo_4", use_lenta=False)
    assert "aire_comprimido_camara_on" not in _abiertas(set_do)
    estado.lectura_ai = lambda: (True, None)
    fase._tick_sub_enfriamiento("modo_4", use_lenta=False)
    assert "aire_comprimido_camara_on" in _abiertas(set_do)


# ── R2-M1: AI vencida = datos no vigentes ──────────────────────────────────

def test_ai_vencida_no_pasa_a_solo_lenta():
    prot, _, set_do, lectura = _protocolo(pres=250.0, modo=1)
    prot.ejecutar()
    lectura["v"] = (False, None)
    for _ in range(10):
        prot.update()
    assert prot.solo_lenta is False
    assert prot._lecturas_principal_perdido == 0


def test_ai_vencida_liquido_sellado_con_contrapresion_no_ventea():
    """D8-2.10: carga líquida enfriando con contrapresión; un corte de AI de
    unos segundos no la ventea por la lenta."""
    prot, estado, set_do, lectura = _protocolo(pres=250.0, temp=120.0, modo=4, tipo="liquido")
    prot.ejecutar()
    set_do.reset_mock()
    lectura["v"] = (False, None)
    for _ in range(8):
        prot.update()
    assert "descompresion_lenta_on" not in _abiertas(set_do)
    assert prot.solo_lenta is False
    lectura["v"] = (True, None)
    prot.update()
    assert prot.solo_lenta is False


def test_ai_vencida_no_abre_aire_atmosferico_en_vacio():
    prot, estado, set_do, lectura = _protocolo(pres=101.3, temp=30.0)
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    estado.sensores_pres["pres_camara"] = 20.0
    lectura["v"] = (False, None)
    set_do.reset_mock()
    for _ in range(5):
        prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)


def test_ai_vencida_mantiene_lo_ya_abierto():
    prot, estado, set_do, lectura = _protocolo(pres=250.0, modo=2)
    prot.ejecutar()
    prot.update()
    set_do.reset_mock()
    lectura["v"] = (False, None)
    for _ in range(3):
        prot.update()
    assert "descompresion_lenta_off" not in [c[0] for c in set_do.method_calls]


def test_ai_vencida_sellado_no_decide_con_temperaturas_congeladas():
    prot, estado, set_do, lectura = _protocolo(pres=250.0, temp=120.0, modo=4, tipo="liquido")
    prot.ejecutar()
    prot._iniciar_sellado()
    estado.sensores_temp["temp_ref"] = 20.0       # Referencia fría, congelada
    estado.sensores_temp["temp_camara"] = None    # Principal sin lectura, congelado
    prot.cycle.sensores["temp_ref"] = "referencia"
    lectura["v"] = (False, None)
    for _ in range(5):
        prot.update()
    assert prot.sellado is True


def test_ai_vencida_sostenida_activa_el_motivo_cic10():
    prot, _, _, lectura = _protocolo()
    prot.ejecutar()
    lectura["v"] = (False, None)
    prot.update()
    assert (prot.bloqueado_motivo or "").startswith("Sensor de presión de cámara")


def test_transductor_sin_lectura_con_ai_vigente_si_enclava_solo_lenta():
    prot, estado, _, lectura = _protocolo(pres=250.0, modo=1)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    for s in (1, 2, 3):
        lectura["v"] = (True, s)
        prot.update()
    assert prot.solo_lenta is True


# ── R2-M2: vacío por tramas AI distintas ───────────────────────────────────

def test_vacio_misma_trama_cuenta_una_vez():
    prot, estado, set_do, lectura = _protocolo(pres=101.3, temp=30.0)
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    estado.sensores_pres["pres_camara"] = 20.0
    lectura["v"] = (True, 5)
    set_do.reset_mock()
    for _ in range(5):
        prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)
    lectura["v"] = (True, 6)
    prot.update()
    lectura["v"] = (True, 7)
    prot.update()
    assert "aire_admosferico_camara_on" in _abiertas(set_do)


# ── R2-B3: ejecutar() ──────────────────────────────────────────────────────

def test_ejecutar_en_vacio_no_abre_el_aire_con_una_lectura():
    prot, estado, set_do, _ = _protocolo(pres=20.0, temp=30.0)
    prot.ejecutar()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)
    prot.update(); prot.update(); prot.update()
    assert "aire_admosferico_camara_on" in _abiertas(set_do)


def test_ejecutar_con_ai_vencida_no_abre_nada():
    prot, estado, set_do, _ = _protocolo(pres=250.0, ai=(False, None))
    prot.ejecutar()
    assert not _abiertas(set_do)


# ── R2-M3: puertas con la presión vigente ──────────────────────────────────

def _servicio(vigente):
    from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 101.3
    estado.sensores_temp["temp_camara"] = 30.0
    puerta = MagicMock()
    puerta.name = "Puerta 1"
    for k in estado.estado_puertas:
        estado.estado_puertas[k] = DoorState.CERRADO
    estado.set_flag("PARO_EMERGENCIA", False)
    return ServicioPuertas([puerta], estado, None, _Config(_CFG), presion_vigente=vigente)


def test_puertas_no_abren_con_la_presion_no_vigente():
    ok, motivo = _servicio(lambda: False)._can_open_physical("Puerta 1")
    assert ok is False


def test_puertas_abren_con_la_presion_vigente():
    ok, motivo = _servicio(lambda: True)._can_open_physical("Puerta 1")
    assert ok is True, motivo


def test_puertas_error_de_vigencia_no_abren():
    def roto():
        raise RuntimeError("x")
    ok, _ = _servicio(roto)._can_open_physical("Puerta 1")
    assert ok is False


def test_contexto_entrega_la_vigencia_al_servicio_de_puertas():
    import inspect
    from autoclave.backend import context
    fuente = inspect.getsource(context)
    assert "presion_vigente=self.presion_vigente" in fuente


# ── R2-B1: falla cerrada en /io/test/output ────────────────────────────────

@pytest.fixture
def prueba():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_di = {}
    ctx.doors = []
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = False
    ctx.setdo.salida_bloqueada.return_value = False
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    modulo_backend("rutas.io")._token_modo_prueba = cab["Authorization"].split()[1]
    return TestClient(srv.app, headers=cab), ctx


def test_respuesta_que_no_es_dict_bloquea_todo(prueba):
    client, ctx = prueba
    ctx.control_loop.salidas_prueba_bloqueadas.return_value = None
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    assert r.status_code == 409
    ctx.setdo.set_output.assert_not_called()


# ── P-a: aire comprimido y vapor de generador/caldera ──────────────────────

def test_estado_seguro_bloquea_aire_comprimido_y_vapor_de_fuente():
    b = sps.bloqueadas(estado_seguro_activo=True, recuperacion_pendiente=False,
                       camara_segura=True)
    for k in ("aire_comprimido_camara", "vapor_generador", "vapor_caldera"):
        assert b.get(k) == sps.ESTADO_SEGURO, k
    assert "vapor_chaqueta" not in b


def test_sin_estado_seguro_no_se_bloquean():
    b = sps.bloqueadas(estado_seguro_activo=False, recuperacion_pendiente=False,
                       camara_segura=False)
    for k in ("aire_comprimido_camara", "vapor_generador", "vapor_caldera"):
        assert k not in b


# ── R2-B2: primera AI desde la primera DI vigente ──────────────────────────

def test_espera_de_la_primera_ai_se_mide_desde_la_primera_di():
    loop = _loop_vivo()
    loop.link.edad_ultima_ai.return_value = None
    loop._conectado_desde = time.monotonic() - 60.0      # conexión vieja
    loop._primera_di_mono = time.monotonic()             # DI recién llegada
    assert loop._esperando_primera_ai() is True
    loop._primera_di_mono = time.monotonic() - 10.0
    assert loop._esperando_primera_ai() is False


def test_tick_fija_la_primera_di_de_la_conexion():
    loop = _loop_vivo()
    loop._tick()
    assert loop._primera_di_mono is not None


# ── R2-B4: una sola toma del enlace ────────────────────────────────────────

def test_lectura_ai_usa_la_toma_atomica_del_enlace():
    loop = _loop_vivo()
    loop.link.estado_ultima_ai.return_value = (0.2, 17)
    loop.link.edad_ultima_ai.side_effect = AssertionError("no debe usarse")
    assert loop._lectura_ai() == (True, 17)
    loop.link.estado_ultima_ai.return_value = (None, None)
    assert loop._lectura_ai() == (False, None)
