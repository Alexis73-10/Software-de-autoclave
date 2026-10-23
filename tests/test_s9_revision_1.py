"""S9 (tanda 9) — correcciones de la revisión ★ pasada 1
(C:/Users/tecni/Documents/_suites_t9/s9_revision_1.md).

- SAF-01: en modo prueba, con el estado seguro activo, la recuperación de
  arranque pendiente o la cámara NO segura, no se encienden las salidas de
  apertura/desbloqueo de puertas; con estado seguro o recuperación tampoco
  rápida, descompresión de chaqueta ni vapor de cámara. El lazo las fuerza a
  cero en cada tick.
- SAF-02 / TMG-01: con la puerta cerrada la coherencia no es evaluable; SEN-10
  solo se despeja con 3 lecturas coherentes con una puerta ABIERTA.
- TMG-02: la trama AI vencida cuenta como presión perdida en el protocolo y
  en el estado seguro (no se abre aire comprimido ni se cuentan ticks seguros).
- SAF-03: con presión sobre atm + brecha el aire atmosférico se cierra
  siempre; la rama de vacío exige 3 lecturas.
- TMG-03: los debounces nuevos cuentan tramas AI distintas.
- TMG-04: la espera sin sonda se reinicia al reanudar tras un modo prueba.
- TMG-05: reanudar() pone a cero los contadores; enter_test_mode() también
  los ticks seguros de la recuperación.
- TMG-06: un error en la coherencia no aborta el tick.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import salidas_prueba_seguridad as sps
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor
from tests.test_s9_estado_seguro_arranque import (
    _CFG, _Config, _abiertas, _arrancar, _coherencia, _estado_puerta, _loop, _programa,
    _sen10, _tick_es)


def _canal(clave):
    return EstadoAutoclave.map_do[clave] + 1


# ── SAF-01: regla pura ─────────────────────────────────────────────────────

def test_regla_camara_no_segura_bloquea_solo_puertas():
    b = sps.bloqueadas(estado_seguro_activo=False, recuperacion_pendiente=False,
                       camara_segura=False)
    assert set(b) == set(sps.SALIDAS_PUERTA)
    assert set(b.values()) == {sps.CAMARA_NO_SEGURA}


def test_regla_estado_seguro_bloquea_puertas_y_vapor():
    for es, rec in ((True, False), (False, True)):
        b = sps.bloqueadas(estado_seguro_activo=es, recuperacion_pendiente=rec,
                           camara_segura=True)
        assert set(b) == set(sps.SALIDAS_PUERTA) | set(sps.SALIDAS_VAPOR)
        assert all(b[k] == sps.ESTADO_SEGURO for k in sps.SALIDAS_VAPOR)


def test_regla_todo_seguro_no_bloquea_nada():
    assert sps.bloqueadas(estado_seguro_activo=False, recuperacion_pendiente=False,
                          camara_segura=True) == {}


def test_salidas_de_puerta_y_vapor():
    assert set(sps.SALIDAS_PUERTA) == {"abrir_puerta_1", "abrir_puerta_2",
                                       "desbloqueo_puerta_1", "desbloqueo_puerta_2"}
    assert set(sps.SALIDAS_VAPOR) == {"descompresion_rapida", "descompresion_chaqueta",
                                      "vapor_camara"}
    for k in (*sps.SALIDAS_PUERTA, *sps.SALIDAS_VAPOR):
        assert k in EstadoAutoclave.map_do
    # la lenta y el bloqueo (cerrar el cerrojo) nunca se bloquean
    assert "descompresion_lenta" not in sps.SALIDAS_VAPOR
    assert "bloqueo_puerta_1" not in sps.SALIDAS_PUERTA


# ── SAF-01: ControlLoop ────────────────────────────────────────────────────

def _loop_vivo(alarmas=None):
    loop = _loop(alarmas)
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.units.get_all.return_value = {}
    loop.estado.sensores_di["paro_emergencia"] = 1
    return loop


def test_control_loop_con_estado_seguro_bloquea_puertas_y_vapor():
    loop = _loop_vivo()
    _arrancar(loop, pres=250.0)
    b = loop.salidas_prueba_bloqueadas()
    assert set(b) == set(sps.SALIDAS_PUERTA) | set(sps.SALIDAS_VAPOR)


def test_control_loop_con_recuperacion_pendiente_bloquea():
    loop = _loop_vivo()
    loop.recuperar_ciclo_interrumpido(_programa())
    assert set(loop.salidas_prueba_bloqueadas()) >= set(sps.SALIDAS_VAPOR)


def test_control_loop_camara_segura_sin_protocolo_no_bloquea():
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 30.0
    loop._estado_publicado_mono = __import__("time").monotonic()
    assert loop.salidas_prueba_bloqueadas() == {}


@pytest.mark.parametrize("pres", [None, 250.0])
def test_control_loop_camara_no_segura_bloquea_puertas(pres):
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = pres
    loop.estado.sensores_temp["temp_camara"] = 30.0
    loop._estado_publicado_mono = __import__("time").monotonic()
    assert set(loop.salidas_prueba_bloqueadas()) == set(sps.SALIDAS_PUERTA)


def test_control_loop_sin_ai_vigente_la_camara_no_es_segura():
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 30.0
    loop._estado_publicado_mono = __import__("time").monotonic()
    loop.link.edad_ultima_ai.return_value = 10.0
    assert set(loop.salidas_prueba_bloqueadas()) == set(sps.SALIDAS_PUERTA)


def test_control_loop_error_al_evaluar_bloquea_todo():
    loop = _loop_vivo()
    loop.programas_para_seguridad = MagicMock(side_effect=RuntimeError("roto"))
    assert set(loop.salidas_prueba_bloqueadas()) == set(sps.SALIDAS_PUERTA) | set(sps.SALIDAS_VAPOR)


def test_lazo_fuerza_a_cero_las_bloqueadas_en_modo_prueba():
    """Arranque a 200 kPa, el técnico entra a prueba: en cada tick el lazo
    manda apagar apertura/desbloqueo de puertas, rápida, chaqueta y vapor."""
    loop = _loop_vivo()
    _arrancar(loop, pres=200.0)
    ok, motivo = loop.enter_test_mode()
    assert ok, motivo
    loop.set_do.reset_mock()
    loop.estado.sensores_pres["pres_camara"] = 200.0
    loop._tick()
    apagadas = {c.args[0] for c in loop.set_do.set_output.call_args_list if c.args[1] is False}
    for k in (*sps.SALIDAS_PUERTA, *sps.SALIDAS_VAPOR):
        assert _canal(k) in apagadas, k
    assert _canal("descompresion_lenta") not in apagadas
    encendidas = [c for c in loop.set_do.set_output.call_args_list if c.args[1] is True]
    assert encendidas == []


def test_lazo_registra_una_vez_la_salida_cortada():
    loop = _loop_vivo()
    _arrancar(loop, pres=200.0)
    loop.enter_test_mode()
    eventos = []
    loop.al_evento_seguridad = lambda e, d: eventos.append((e, d))
    loop.estado.salidas_do["abrir_puerta_1"] = 1          # la tarjeta la reporta encendida
    loop.units.get_all.return_value = {}
    loop.estado.update = lambda _d: None                  # no pisar salidas_do
    loop._tick()
    loop._tick()
    cortadas = [d for e, d in eventos if e == "salida_prueba_cortada"]
    assert len(cortadas) == 1 and cortadas[0]["salida"] == "abrir_puerta_1"


def test_fuera_de_modo_prueba_el_lazo_no_fuerza_nada():
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop._tick()
    apagadas = {c.args[0] for c in loop.set_do.set_output.call_args_list if c.args[1] is False}
    assert _canal("abrir_puerta_1") not in apagadas


# ── SAF-01: PATCH /io/test/output ──────────────────────────────────────────

@pytest.fixture
def prueba():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_di = {}
    ctx.estado.sensores_pres = {"pres_camara": 200.0}
    ctx.doors = []
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = False
    ctx.setdo.salida_bloqueada.return_value = False
    ctx.control_loop.salidas_prueba_bloqueadas.return_value = sps.bloqueadas(
        estado_seguro_activo=True, recuperacion_pendiente=False, camara_segura=False)
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    srv._token_modo_prueba = cab["Authorization"].split()[1]
    return TestClient(srv.app, headers=cab), ctx


@pytest.mark.parametrize("nombre, codigo", [
    ("abrir_puerta_1", sps.CAMARA_NO_SEGURA), ("desbloqueo_puerta_1", sps.CAMARA_NO_SEGURA),
    ("abrir_puerta_2", sps.CAMARA_NO_SEGURA), ("desbloqueo_puerta_2", sps.CAMARA_NO_SEGURA),
    ("descompresion_rapida", sps.ESTADO_SEGURO), ("descompresion_chaqueta", sps.ESTADO_SEGURO),
    ("vapor_camara", sps.ESTADO_SEGURO)])
def test_patch_rechaza_encender_las_bloqueadas(prueba, nombre, codigo):
    client, ctx = prueba
    r = client.patch(f"/io/test/output/{nombre}", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == codigo
    ctx.setdo.set_output.assert_not_called()


def test_patch_apagar_las_bloqueadas_si_se_permite(prueba):
    client, ctx = prueba
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": False})
    assert r.status_code == 200, r.text
    ctx.setdo.set_output.assert_called_once_with(_canal("abrir_puerta_1"), False)


@pytest.mark.parametrize("nombre", ["descompresion_lenta", "bloqueo_puerta_1", "cerrar_puerta_1"])
def test_patch_otras_salidas_siguen_permitidas(prueba, nombre):
    client, _ = prueba
    assert client.patch(f"/io/test/output/{nombre}", json={"value": True}).status_code == 200


def test_patch_error_al_evaluar_rechaza_las_de_puerta(prueba):
    client, ctx = prueba
    ctx.control_loop.salidas_prueba_bloqueadas.side_effect = RuntimeError("roto")
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    assert r.status_code == 409
    ctx.setdo.set_output.assert_not_called()


def test_patch_atrapamiento_no_invierte_a_abrir_si_esta_bloqueada(prueba):
    """D-ES-16 convertiría el cierre en apertura: con la apertura bloqueada,
    solo se suelta el cierre y se rechaza."""
    client, ctx = prueba
    d = MagicMock()
    d.name = "Puerta 1"
    d.di = {"cerrada": "puerta_cerrada_1", "atrapamiento": "atrapamiento_puerta_1"}
    d.do = {"abrir": _canal("abrir_puerta_1"), "cerrar": _canal("cerrar_puerta_1")}
    ctx.doors = [d]
    ctx.estado.sensores_di = {"atrapamiento_puerta_1": 0}
    r = client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert r.status_code == 409, r.text
    llamadas = [(c.args[0], c.args[1]) for c in ctx.setdo.set_output.call_args_list]
    assert (_canal("abrir_puerta_1"), True) not in llamadas
    assert (_canal("cerrar_puerta_1"), True) not in llamadas


def test_codigos_nuevos_con_texto_en_los_dos_idiomas():
    from autoclave import i18n
    from autoclave.ui_qml import sesion_backend
    for codigo in (sps.CAMARA_NO_SEGURA, sps.ESTADO_SEGURO):
        clave = sesion_backend.clave_mensaje(codigo)
        assert clave.startswith("io.err_"), clave
        assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


# ── SAF-02 / TMG-01: coherencia con la puerta cerrada ──────────────────────

def test_sen10_no_se_despeja_al_cerrar_la_puerta_y_sigue_bloqueando():
    v, alarmas = _coherencia()
    estado = _estado_puerta(abierta=True, pres=150.0)
    for _ in range(3):
        v.update(estado)
    assert _sen10(alarmas)
    primera = next(iter(estado.estado_puertas))
    estado.estado_puertas[primera] = DoorState.CERRADO
    for _ in range(10):
        v.update(estado)
    assert _sen10(alarmas)
    assert alarmas.has_blocking_alarm() is True


def test_sen10_se_despeja_con_tres_coherentes_con_la_puerta_abierta():
    v, alarmas = _coherencia()
    estado = _estado_puerta(abierta=True, pres=150.0)
    for _ in range(3):
        v.update(estado)
    estado.sensores_pres["pres_camara"] = 101.0
    for _ in range(3):
        v.update(estado)
    assert not _sen10(alarmas)


def test_puerta_cerrada_entre_lecturas_reinicia_el_conteo():
    v, alarmas = _coherencia()
    estado = _estado_puerta(abierta=True, pres=150.0)
    v.update(estado); v.update(estado)
    primera = next(iter(estado.estado_puertas))
    estado.estado_puertas[primera] = DoorState.CERRADO
    v.update(estado)
    estado.estado_puertas[primera] = DoorState.ABIERTO
    v.update(estado)
    assert not _sen10(alarmas)


# ── TMG-03: la coherencia cuenta tramas AI distintas ───────────────────────

def test_coherencia_misma_trama_ai_cuenta_una_vez():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    for _ in range(5):
        v.update(estado, seq_ai=7)
    assert not _sen10(alarmas)
    v.update(estado, seq_ai=8)
    v.update(estado, seq_ai=9)
    assert _sen10(alarmas)


def test_coherencia_sin_datos_vigentes_reinicia_el_conteo():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    v.update(estado); v.update(estado)
    v.update(estado, vigentes=False)
    v.update(estado)
    assert not _sen10(alarmas)


def test_coherencia_reiniciar_conteo_en_pausa():
    v, alarmas = _coherencia()
    estado = _estado_puerta(pres=150.0)
    v.update(estado); v.update(estado)
    v.reiniciar_conteo()
    v.update(estado)
    assert not _sen10(alarmas)


# ── TMG-06: un error en la coherencia no aborta el tick ────────────────────

def test_error_en_la_coherencia_no_aborta_el_tick():
    loop = _loop_vivo()
    loop.coherencia_puerta_presion.update = MagicMock(side_effect=RuntimeError("roto"))
    loop.coherencia_puerta_presion.reiniciar_conteo = MagicMock()
    loop.cycle_logger = MagicMock()
    loop._tick()                              # no lanza
    loop.cycle_logger.update.assert_called_once()
    loop.coherencia_puerta_presion.reiniciar_conteo.assert_called()


def test_en_pausa_el_lazo_reinicia_la_coherencia():
    loop = _loop_vivo()
    loop.coherencia_puerta_presion.reiniciar_conteo = MagicMock()
    loop.enter_test_mode()
    loop._tick()
    loop.coherencia_puerta_presion.reiniciar_conteo.assert_called()


# ── TMG-02: trama AI vencida = presión perdida ─────────────────────────────

def _protocolo(pres=250.0, temp=120.0, modo=2, tipo="solido", ai=(True, None)):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=modo, tipo=tipo), _Config(_CFG))
    lectura = {"v": ai}
    prot.lectura_ai = lambda: lectura["v"]
    return prot, estado, set_do, lectura


def test_ai_vencida_activa_el_motivo_de_presion_perdida():
    prot, _, _, lectura = _protocolo()
    prot.ejecutar()
    lectura["v"] = (False, None)
    prot.update()
    assert (prot.bloqueado_motivo or "").startswith("Sensor de presión de cámara sin lectura")


def test_ai_vencida_en_modos_4_5_no_abre_aire_comprimido():
    prot, estado, set_do, lectura = _protocolo(pres=250.0, temp=120.0, modo=4, tipo="liquido")
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 150.0     # congelada bajo la contrapresión
    set_do.reset_mock()
    lectura["v"] = (False, None)
    for _ in range(3):
        prot.update()
    assert "aire_comprimido_camara_on" not in _abiertas(set_do)


def test_ai_vigente_en_modos_4_5_si_abre_aire_comprimido():
    """Contraprueba: con la AI al día el enfriamiento con contrapresión sigue igual."""
    prot, estado, set_do, _ = _protocolo(pres=150.0, temp=120.0, modo=4, tipo="liquido")
    estado.sensores_pres["pres_camara"] = 250.0
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 150.0
    set_do.reset_mock()
    prot.update()
    assert "aire_comprimido_camara_on" in _abiertas(set_do)


def test_ai_vencida_el_estado_seguro_no_cuenta_ticks_seguros():
    loop = _loop()
    _arrancar(loop, pres=250.0)
    es = loop.estado_seguro
    lectura = {"v": (True, None)}
    es.lectura_ai = lambda: lectura["v"]
    loop.estado.sensores_pres["pres_camara"] = 101.3      # congelada en "segura"
    loop.estado.sensores_temp["temp_camara"] = 30.0
    lectura["v"] = (False, None)
    _tick_es(loop, 6)
    assert es.activo


def test_ai_vigente_el_estado_seguro_termina():
    loop = _loop()
    _arrancar(loop, pres=250.0)
    es = loop.estado_seguro
    es.lectura_ai = lambda: (True, None)
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 30.0
    _tick_es(loop, 6)
    assert not es.activo


def test_control_loop_entrega_su_lectura_ai_al_estado_seguro():
    loop = _loop_vivo()
    assert loop.estado_seguro.lectura_ai is not None
    loop.link.edad_ultima_ai.return_value = 10.0
    assert loop.estado_seguro.lectura_ai()[0] is False
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.link.secuencia_ultima_ai.return_value = 42
    assert loop.estado_seguro.lectura_ai() == (True, 42)


def test_recuperacion_no_cuenta_ticks_seguros_con_ai_vencida():
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 30.0
    loop.recuperar_ciclo_interrumpido(_programa())
    loop.link.edad_ultima_ai.return_value = 10.0
    for _ in range(5):
        loop._procesar_recuperacion()
    # nunca se da por segura con la trama AI vencida: arranca el protocolo
    assert loop.estado_seguro.activo


def test_recuperacion_espera_la_primera_ai_de_la_conexion():
    """Pregunta 7 de la revisión: la primera DI puede llegar antes que la
    primera AI (pres_camara None): no se arranca el protocolo por eso."""
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = None
    loop.recuperar_ciclo_interrumpido(_programa())
    loop.link.edad_ultima_ai.return_value = None
    loop._conectado_desde = __import__("time").monotonic()
    loop._procesar_recuperacion()
    assert not loop.estado_seguro.activo and loop._recuperacion_pendiente is not None


def test_recuperacion_sin_ai_pasada_la_vigencia_arranca_el_protocolo():
    loop = _loop_vivo()
    loop.estado.sensores_pres["pres_camara"] = None
    loop.recuperar_ciclo_interrumpido(_programa())
    loop.link.edad_ultima_ai.return_value = None
    loop._conectado_desde = __import__("time").monotonic() - 10.0
    loop._procesar_recuperacion()
    assert loop.estado_seguro.activo


# ── TMG-03: _seguir_presion_perdida cuenta tramas AI distintas ─────────────

def test_presion_perdida_misma_trama_cuenta_una_vez():
    prot, estado, _, lectura = _protocolo()
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    lectura["v"] = (True, 5)
    for _ in range(5):
        prot.update()
    assert not (prot.bloqueado_motivo or "").startswith("Sensor de presión")
    lectura["v"] = (True, 6)
    prot.update()
    lectura["v"] = (True, 7)
    prot.update()
    assert (prot.bloqueado_motivo or "").startswith("Sensor de presión")


def test_presion_vuelve_misma_trama_no_despeja():
    prot, estado, _, lectura = _protocolo()
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    for s in (1, 2, 3):
        lectura["v"] = (True, s)
        prot.update()
    assert (prot.bloqueado_motivo or "").startswith("Sensor de presión")
    estado.sensores_pres["pres_camara"] = 250.0
    lectura["v"] = (True, 4)
    for _ in range(5):
        prot.update()
    assert (prot.bloqueado_motivo or "").startswith("Sensor de presión")


# ── SAF-03: aire atmosférico ───────────────────────────────────────────────

def test_aire_se_cierra_con_presion_aunque_estuviera_presurizada_al_disparo():
    """Arranque en vacío (aire abierto) y la presión sube sobre atm + brecha
    con el protocolo solo_lenta y presurizado al disparo."""
    prot, estado, set_do, _ = _protocolo(pres=250.0)
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    assert prot._presurizado_al_disparo is True
    set_do.reset_mock()
    estado.sensores_pres["pres_camara"] = 250.0
    prot.update()
    nombres = [c[0] for c in set_do.method_calls]
    assert "aire_admosferico_camara_off" in nombres
    assert "aire_admosferico_camara_on" not in nombres


@pytest.mark.parametrize("modo", [1, 2, 3])
def test_aire_se_cierra_con_presion_en_todos_los_modos(modo):
    prot, estado, set_do, _ = _protocolo(pres=250.0, modo=modo)
    prot.ejecutar()
    set_do.reset_mock()
    prot.update()
    assert "aire_admosferico_camara_off" in [c[0] for c in set_do.method_calls]


def test_vacio_exige_tres_lecturas_antes_de_abrir_el_aire():
    prot, estado, set_do, _ = _protocolo(pres=101.3, temp=30.0)
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    estado.sensores_pres["pres_camara"] = 20.0
    set_do.reset_mock()
    prot.update(); prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)
    prot.update()
    assert "aire_admosferico_camara_on" in _abiertas(set_do)


def test_vacio_una_lectura_fuera_reinicia_el_conteo():
    prot, estado, set_do, _ = _protocolo(pres=101.3, temp=30.0)
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    estado.sensores_pres["pres_camara"] = 20.0
    prot.update(); prot.update()
    estado.sensores_pres["pres_camara"] = 101.3
    prot.update()
    estado.sensores_pres["pres_camara"] = 20.0
    set_do.reset_mock()
    prot.update(); prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)


# ── TMG-04: espera sin sonda tras el modo prueba ───────────────────────────

def test_reanudar_tras_modo_prueba_reinicia_la_espera_sin_sonda():
    prot, _, _, _ = _protocolo()
    prot.ejecutar()
    prot._sin_sonda_desde = 123.0
    prot.reanudar(tras_modo_prueba=True)
    assert prot._sin_sonda_desde is None


def test_reanudar_tras_un_paro_conserva_la_espera_sin_sonda():
    prot, _, _, _ = _protocolo()
    prot.ejecutar()
    prot._sin_sonda_desde = 123.0
    prot.reanudar()
    assert prot._sin_sonda_desde == 123.0


def test_estado_seguro_reanuda_tras_modo_prueba_con_el_indicador():
    loop = _loop()
    _arrancar(loop, pres=250.0)
    _tick_es(loop)
    prot = loop.estado_seguro._protocolo
    prot.reanudar = MagicMock()
    loop.estado_seguro.pausar("modo_prueba")
    _tick_es(loop)
    prot.reanudar.assert_called_once_with(tras_modo_prueba=True)
    # la siguiente pausa (paro) ya no lleva el indicador
    loop.estado.set_flag("PARO_EMERGENCIA", True)
    _tick_es(loop)
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    _tick_es(loop)
    assert prot.reanudar.call_args_list[-1].kwargs.get("tras_modo_prueba", False) is False


# ── TMG-05: contadores a cero ──────────────────────────────────────────────

def test_reanudar_pone_a_cero_los_contadores_de_debounce():
    prot, _, _, _ = _protocolo()
    prot.ejecutar()
    prot._lecturas_enfriada = 2
    prot._lecturas_presion_perdida = 2
    prot._lecturas_presion_vuelta = 2
    prot._lecturas_principal_perdido = 2
    prot._lecturas_vacio = 2
    prot.reanudar()
    assert (prot._lecturas_enfriada, prot._lecturas_presion_perdida,
            prot._lecturas_presion_vuelta, prot._lecturas_principal_perdido,
            prot._lecturas_vacio) == (0, 0, 0, 0, 0)


def test_enter_test_mode_pone_a_cero_los_ticks_seguros_de_la_recuperacion():
    loop = _loop()
    loop.recuperar_ciclo_interrumpido(_programa())
    loop._ticks_seguros_recuperacion = 2
    ok, _ = loop.enter_test_mode()
    assert ok and loop._ticks_seguros_recuperacion == 0


def test_estado_seguro_tiene_lectura_ai_por_defecto_none():
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _Config(_CFG))
    assert es.lectura_ai is None
