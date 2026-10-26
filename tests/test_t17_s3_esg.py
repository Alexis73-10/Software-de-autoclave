"""Tanda 17 (s3) — ESG-01 y ESG-02 (decisiones de Cristian, 26-oct).

ESG-01: si el estado seguro no puede avanzar porque la presión de cámara no
tiene lectura, no se activa CIC-10 (y se resuelve si estaba activa); el motivo
va al log una vez por episodio; el protocolo sigue detenido y "NO ABRIR" se
mantiene. CIC-10 sigue para los demás motivos.

ESG-02 (reemplaza SAF-01 de S9): en modo prueba, con lectura vigente de
presión de cámara, se retiran los bloqueos propios del estado seguro; sin
ella, se mantienen todos. Siempre: puerta y desbloqueo rechazados con la
cámara presurizada, en vacío o sin lectura; vapor de cámara rechazado con una
puerta abierta o sin lectura, y apagado en el mismo tick si la puerta se abre
con la salida encendida (aviso en Entradas / Salidas). Aire atmosférico
(D8-3.19) intacto.
"""

import logging
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import camara_segura
from autoclave.core.runtime import salidas_prueba_seguridad as sps
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_10
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend
from tests.test_s9_estado_seguro_arranque import _CFG, _arrancar, _loop, _programa, _tick_es


def _canal(clave):
    return EstadoAutoclave.map_do[clave] + 1


def _cic10_activa(alarmas):
    return [i for i in alarmas.activas()
            if i.codigo == CIC_10 and i.estado is EstadoInstancia.ACTIVA]


# ══ ESG-01 ════════════════════════════════════════════════════════════════

@pytest.mark.req("ESG-01")
def test_sin_presion_no_activa_cic10_y_sigue_detenido(caplog):
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    es = loop.estado_seguro
    with caplog.at_level(logging.WARNING, logger="autoclave.state_machine.estado_seguro"):
        _tick_es(loop, 6)
    assert not _cic10_activa(alarmas)
    assert es.activo and es.detenido_sin_presion is True
    # el motivo, una sola vez por episodio en el log de desarrollo
    avisos = [r for r in caplog.records if "ESG-01" in r.getMessage()]
    assert len(avisos) == 1
    # NO ABRIR: sin presión la cámara no es segura (falla cerrada)
    segura, motivo = camara_segura.evaluar(loop.estado, _CFG, [None])
    assert segura is False and motivo.codigo == "sin_presion_camara"
    # sin presión no se abre ninguna válvula
    assert not {c[0] for c in loop.set_do.method_calls if c[0].endswith("_on")}


@pytest.mark.req("ESG-01")
def test_cic10_se_conserva_para_otros_motivos_al_perder_la_presion():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    # presión válida y Principal sin lectura: CIC-10 por el Principal
    _arrancar(loop, pres=250.0, temp=None)
    _tick_es(loop, 3)
    activas = _cic10_activa(alarmas)
    assert activas and "Principal" in activas[0].descripcion
    # se pierde la presión: CIC-10 sigue por el otro motivo (corrección R3
    # V17-s3-02: "CIC-10 se conserva para los demás motivos")
    loop.estado.sensores_pres["pres_camara"] = None
    _tick_es(loop, 3)
    activas = _cic10_activa(alarmas)
    assert activas and "Principal" in activas[0].descripcion
    assert "presión" not in activas[0].descripcion
    assert loop.estado_seguro.detenido_sin_presion is True
    # vuelve la presión: el flujo sigue igual (CIC-10 por el Principal otra vez)
    loop.estado.sensores_pres["pres_camara"] = 250.0
    _tick_es(loop, 3)
    activas = _cic10_activa(alarmas)
    assert activas and "Principal" in activas[0].descripcion
    assert loop.estado_seguro.detenido_sin_presion is False


def _es_con_protocolo_falso(alarmas, **motivos):
    """ProtocoloEstadoSeguro con un protocolo de fallo doble (motivos fijos)."""
    from types import SimpleNamespace
    from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _CFG, alarm_manager=alarmas)
    es._protocolo = SimpleNamespace(**motivos)
    return es


@pytest.mark.req("ESG-01")
@pytest.mark.parametrize("otro", [
    "Sensor Principal sin lectura con carga líquida: cámara sellada hasta que las sondas "
    "confirmen la temperatura o venza la espera",
    "Tiempo límite de descompresión con carga líquida caliente: no se usa el escape rápido"])
def test_presion_perdida_mas_otro_motivo_activa_cic10_con_el_otro(otro):
    """Corrección R3 V17-s3-02: con la presión perdida, CIC-10 sigue por los
    demás motivos simultáneos (cámara sellada, líquidos calientes)."""
    alarmas = AlarmManager()
    es = _es_con_protocolo_falso(alarmas, presion_perdida=True,
                                 bloqueado_motivo="Sensor de presión de cámara sin lectura",
                                 bloqueado_motivo_sin_presion=otro)
    es._actualizar_alarma_bloqueo()
    [cic10] = _cic10_activa(alarmas)
    assert otro.split(":")[0] in cic10.descripcion
    assert "presión de cámara" not in cic10.descripcion


@pytest.mark.req("ESG-01")
def test_solo_presion_perdida_sin_cic10():
    alarmas = AlarmManager()
    es = _es_con_protocolo_falso(alarmas, presion_perdida=True,
                                 bloqueado_motivo="Sensor de presión de cámara sin lectura",
                                 bloqueado_motivo_sin_presion=None)
    es._actualizar_alarma_bloqueo()
    assert not _cic10_activa(alarmas)


@pytest.mark.req("ESG-01")
def test_motivo_sin_presion_del_protocolo_real():
    """ProtocoloFallo: con la presión perdida bloqueado_motivo sigue dando la
    presión (prioridad de S9) y bloqueado_motivo_sin_presion el siguiente."""
    from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 250.0
    estado.sensores_temp["temp_camara"] = 120.0
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=2), _CFG)
    prot.ejecutar()
    prot._presion_perdida = True
    prot._aviso_no_escala = True
    assert prot.bloqueado_motivo.startswith("Sensor de presión de cámara")
    assert prot.bloqueado_motivo_sin_presion.startswith("Tiempo límite de descompresión")
    prot._aviso_no_escala = False
    assert prot.bloqueado_motivo_sin_presion is None


@pytest.mark.req("ESG-01")
def test_al_volver_la_presion_el_protocolo_sigue_igual():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=120.0)
    _tick_es(loop, 3)
    assert loop.estado_seguro.detenido_sin_presion
    loop.estado.sensores_pres["pres_camara"] = 250.0
    _tick_es(loop, 3)
    assert not loop.estado_seguro.detenido_sin_presion
    assert "descompresion_lenta_on" in {c[0] for c in loop.set_do.method_calls}
    assert not _cic10_activa(alarmas)


@pytest.mark.req("ESG-01")
def test_status_publica_detenido_sin_presion():
    ctx = MagicMock()
    srv, _ = cargar_servidor(ctx)
    es = ctx.control_loop.estado_seguro
    es.activo = True
    es.detenido_sin_presion = True
    es.bloqueado_motivo = "Sensor de presión de cámara sin lectura"
    es.causa = "arranque"
    d = modulo_backend("rutas.sistema")._estado_seguro_status()
    assert d["detenido_sin_presion"] is True
    es.activo = False
    assert modulo_backend("rutas.sistema")._estado_seguro_status()["detenido_sin_presion"] is False


# ══ ESG-02: regla pura ════════════════════════════════════════════════════

@pytest.mark.req("ESG-02")
def test_regla_con_presion_vigente_retira_los_bloqueos_del_estado_seguro():
    for es, rec in ((True, False), (False, True)):
        b = sps.bloqueadas(es, rec, camara_segura=True, presion_vigente=True,
                           presion_segura=True, puertas_cerradas=True)
        assert b == {}


@pytest.mark.req("ESG-02")
def test_regla_sin_presion_vigente_mantiene_todos_los_bloqueos():
    b = sps.bloqueadas(True, False, camara_segura=False, presion_vigente=False,
                       presion_segura=False, puertas_cerradas=True)
    assert set(b) == set(sps.SALIDAS_PUERTA) | set(sps.SALIDAS_VAPOR)
    assert {b[k] for k in sps.SALIDAS_VAPOR} == {sps.ESTADO_SEGURO}
    assert {b[k] for k in sps.SALIDAS_PUERTA} == {sps.CAMARA_PRESURIZADA}


@pytest.mark.req("ESG-02")
@pytest.mark.parametrize("es", [True, False])
def test_regla_protecciones_siempre(es):
    b = sps.bloqueadas(es, False, camara_segura=False, presion_vigente=True,
                       presion_segura=False, puertas_cerradas=False)
    assert {b[k] for k in sps.SALIDAS_PUERTA} == {sps.CAMARA_PRESURIZADA}
    assert b["vapor_camara"] == sps.PUERTA_ABIERTA
    assert set(b) == set(sps.SALIDAS_PUERTA) | {"vapor_camara"}
    # sin dato de puertas: falla cerrada
    assert sps.bloqueadas(es, False, True, True, True, None)["vapor_camara"] == sps.PUERTA_ABIERTA


@pytest.mark.req("ESG-02")
def test_regla_temperatura_alta_sigue_bloqueando_puertas():
    """DECISIÓN SIN CONFIRMAR: la regla de puertas con la cámara no segura por
    temperatura (S9) se conserva."""
    b = sps.bloqueadas(False, False, camara_segura=False, presion_vigente=True,
                       presion_segura=True, puertas_cerradas=True)
    assert b == {k: sps.CAMARA_NO_SEGURA for k in sps.SALIDAS_PUERTA}


@pytest.mark.req("ESG-02")
def test_salidas_que_no_se_tocan():
    for k in ("descompresion_lenta", "bloqueo_puerta_1", "bloqueo_puerta_2", "bomba_vacio",
              "aire_admosferico_camara"):
        assert k not in sps.bloqueadas(True, True, False, False, False, False)


@pytest.mark.req("ESG-02")
def test_codigos_con_texto_propio():
    from autoclave import i18n
    for codigo, clave in ((sps.CAMARA_PRESURIZADA, "io.err_puerta_camara_presurizada"),
                          (sps.PUERTA_ABIERTA, "io.err_vapor_puerta_abierta")):
        assert codigo in sps.MOTIVOS
        assert i18n.existe(clave, "es") and i18n.existe(clave, "en")
    for clave in sps.AVISOS_CORTE.values():
        assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


# ══ ESG-02: ControlLoop ═══════════════════════════════════════════════════

def _loop_vivo(alarmas=None, pres=101.3, temp=30.0, puertas=(1, 1)):
    loop = _loop(alarmas)
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.units.get_all.return_value = {}
    loop.estado.sensores_di["paro_emergencia"] = 1
    for n, v in enumerate(puertas, start=1):
        loop.estado.sensores_di[f"puerta_{n}_cerrada"] = v
    loop.estado.sensores_pres["pres_camara"] = pres
    loop.estado.sensores_temp["temp_camara"] = temp
    loop._estado_publicado_mono = time.monotonic()
    return loop


@pytest.mark.req("ESG-02")
def test_loop_estado_seguro_con_presion_vigente_solo_quedan_las_protecciones():
    loop = _loop_vivo()
    _arrancar(loop, pres=250.0)
    loop._estado_publicado_mono = time.monotonic()
    assert loop.estado_seguro.activo
    b = loop.salidas_prueba_bloqueadas()
    assert b == {k: sps.CAMARA_PRESURIZADA for k in sps.SALIDAS_PUERTA}


@pytest.mark.req("ESG-02")
def test_loop_estado_seguro_sin_presion_mantiene_todo():
    loop = _loop_vivo()
    _arrancar(loop, pres=None)
    loop._estado_publicado_mono = time.monotonic()
    assert loop.estado_seguro.activo
    b = loop.salidas_prueba_bloqueadas()
    assert set(b) == set(sps.SALIDAS_PUERTA) | set(sps.SALIDAS_VAPOR)
    assert {b[k] for k in sps.SALIDAS_VAPOR} == {sps.ESTADO_SEGURO}


@pytest.mark.req("ESG-02")
def test_loop_estado_seguro_con_presion_congelada_mantiene_todo():
    loop = _loop_vivo()
    _arrancar(loop, pres=250.0)
    loop._estado_publicado_mono = time.monotonic()
    loop.link.edad_ultima_ai.return_value = 10.0          # trama AI vencida
    b = loop.salidas_prueba_bloqueadas()
    assert set(b) >= set(sps.SALIDAS_VAPOR) | set(sps.SALIDAS_PUERTA)


@pytest.mark.req("ESG-02")
@pytest.mark.parametrize("pres", [150.0, 60.0, None])       # presurizada, vacío, sin lectura
def test_loop_puertas_rechazadas_sin_estado_seguro(pres):
    loop = _loop_vivo(pres=pres)
    assert not loop.estado_seguro.activo
    b = loop.salidas_prueba_bloqueadas()
    assert {k: b.get(k) for k in sps.SALIDAS_PUERTA} == {
        k: sps.CAMARA_PRESURIZADA for k in sps.SALIDAS_PUERTA}
    assert set(b) == set(sps.SALIDAS_PUERTA)


@pytest.mark.req("ESG-02")
def test_loop_camara_atmosferica_y_puertas_cerradas_no_bloquea_nada():
    assert _loop_vivo().salidas_prueba_bloqueadas() == {}


@pytest.mark.req("ESG-02")
@pytest.mark.parametrize("puertas", [(0, 1), (1, 0), (None, 1), (1, None)])
def test_loop_vapor_rechazado_con_una_puerta_abierta_o_sin_lectura(puertas):
    loop = _loop_vivo(puertas=puertas)
    if None in puertas:
        loop.estado.sensores_di.pop(f"puerta_{puertas.index(None) + 1}_cerrada")
    assert loop.salidas_prueba_bloqueadas() == {"vapor_camara": sps.PUERTA_ABIERTA}


@pytest.mark.req("ESG-02")
def test_loop_vapor_rechazado_con_la_trama_di_vencida():
    loop = _loop_vivo()
    loop.link.edad_ultima_di.return_value = 10.0
    assert loop.salidas_prueba_bloqueadas().get("vapor_camara") == sps.PUERTA_ABIERTA


@pytest.mark.req("ESG-02")
def test_loop_una_puerta_sola_cuenta_la_del_perfil():
    from types import SimpleNamespace
    loop = _loop_vivo(puertas=(1, 0))
    loop.profile = SimpleNamespace(door_count=1)
    assert loop.salidas_prueba_bloqueadas() == {}


def _en_prueba(loop):
    ok, motivo = loop.enter_test_mode()
    assert ok, motivo
    loop.estado.update = lambda _d: None                  # no pisar lo que fija la prueba
    loop.set_do.reset_mock()


def _apagadas(loop):
    return {c.args[0] for c in loop.set_do.set_output.call_args_list if c.args[1] is False}


@pytest.mark.req("ESG-02")
def test_lazo_apaga_el_vapor_en_el_mismo_tick_si_se_abre_una_puerta():
    loop = _loop_vivo()
    _en_prueba(loop)
    loop.estado.salidas_do["vapor_camara"] = 1            # la tarjeta lo reporta encendido
    loop._tick()
    assert _canal("vapor_camara") not in _apagadas(loop)
    assert loop.avisos_corte_prueba == []
    loop.estado.sensores_di["puerta_1_cerrada"] = 0        # se abre la puerta
    loop.set_do.reset_mock()
    loop._tick()
    assert _canal("vapor_camara") in _apagadas(loop)
    [aviso] = loop.avisos_corte_prueba
    assert aviso["salida"] == "vapor_camara" and aviso["codigo"] == sps.PUERTA_ABIERTA
    assert aviso["aviso"] == "io.ui.aviso_vapor_cortado_puerta" and aviso["n"] == 1
    loop._tick()                                           # una sola vez por corte
    assert len(loop.avisos_corte_prueba) == 1


@pytest.mark.req("ESG-02")
def test_lazo_apaga_puerta_y_desbloqueo_si_la_camara_se_presuriza():
    loop = _loop_vivo()
    _en_prueba(loop)
    loop.estado.salidas_do["abrir_puerta_1"] = 1
    loop.estado.salidas_do["desbloqueo_puerta_1"] = 1
    loop._tick()
    assert not {_canal("abrir_puerta_1"), _canal("desbloqueo_puerta_1")} & _apagadas(loop)
    loop.estado.sensores_pres["pres_camara"] = 160.0
    loop.set_do.reset_mock()
    loop._tick()
    assert {_canal("abrir_puerta_1"), _canal("desbloqueo_puerta_1")} <= _apagadas(loop)
    avisos = {a["salida"]: a for a in loop.avisos_corte_prueba}
    assert set(avisos) == {"abrir_puerta_1", "desbloqueo_puerta_1"}
    assert {a["aviso"] for a in avisos.values()} == {"io.ui.aviso_salida_cortada_presion"}


@pytest.mark.req("ESG-02")
def test_lazo_en_estado_seguro_con_presion_no_apaga_rapida_ni_chaqueta():
    loop = _loop_vivo()
    _arrancar(loop, pres=250.0)
    _en_prueba(loop)
    loop._tick()
    apagadas = _apagadas(loop)
    for k in ("descompresion_rapida", "descompresion_chaqueta", "aire_comprimido_camara",
              "vapor_generador", "vapor_caldera", "vapor_camara"):
        assert _canal(k) not in apagadas, k
    for k in sps.SALIDAS_PUERTA:
        assert _canal(k) in apagadas, k


@pytest.mark.req("ESG-02")
def test_entrar_al_modo_prueba_vacia_los_avisos():
    loop = _loop_vivo()
    loop._anotar_aviso_corte("vapor_camara", sps.PUERTA_ABIERTA)
    assert loop.avisos_corte_prueba
    _en_prueba(loop)
    assert loop.avisos_corte_prueba == []


@pytest.mark.req("ESG-02")
def test_aire_atmosferico_intacto():
    """D8-3.19: con la cámara presurizada el lazo sigue cerrando el aire
    atmosférico en modo prueba, igual que antes."""
    loop = _loop_vivo(pres=180.0)
    _en_prueba(loop)
    loop._tick()
    assert _canal("aire_admosferico_camara") in _apagadas(loop)
    assert "aire_admosferico_camara" not in loop.salidas_prueba_bloqueadas()


# ══ ESG-02: PATCH /io/test/output y /status ═══════════════════════════════

@pytest.fixture
def prueba_real():
    """PATCH con un ControlLoop real detrás de salidas_prueba_bloqueadas."""
    loop = _loop_vivo()
    ctx = MagicMock()
    ctx.estado = loop.estado
    ctx.doors = []
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = False
    ctx.control_loop.desconectado = False
    ctx.control_loop.datos_vigentes = True
    ctx.control_loop.salidas_prueba_bloqueadas = loop.salidas_prueba_bloqueadas
    ctx.setdo.salida_bloqueada.return_value = False
    loop.estado.set_machine_state(GlobalState.PREPARADO)
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    modulo_backend("rutas.io")._token_modo_prueba = cab["Authorization"].split()[1]
    return TestClient(srv.app, headers=cab), ctx, loop


@pytest.mark.req("ESG-02")
@pytest.mark.parametrize("pres", [160.0, 60.0, None])
@pytest.mark.parametrize("nombre", ["abrir_puerta_1", "desbloqueo_puerta_2"])
def test_patch_puerta_rechazada_con_la_camara_no_atmosferica(prueba_real, pres, nombre):
    client, ctx, loop = prueba_real
    loop.estado.sensores_pres["pres_camara"] = pres
    r = client.patch(f"/io/test/output/{nombre}", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == sps.CAMARA_PRESURIZADA
    ctx.setdo.set_output.assert_not_called()


@pytest.mark.req("ESG-02")
@pytest.mark.parametrize("puerta", [0, None])
def test_patch_vapor_rechazado_con_una_puerta_abierta_o_sin_lectura(prueba_real, puerta):
    client, ctx, loop = prueba_real
    loop.estado.sensores_di["puerta_2_cerrada"] = puerta
    r = client.patch("/io/test/output/vapor_camara", json={"value": True})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == sps.PUERTA_ABIERTA
    ctx.setdo.set_output.assert_not_called()


@pytest.mark.req("ESG-02")
def test_patch_con_estado_seguro_y_presion_vigente_permite_rapida_y_vapor(prueba_real):
    client, ctx, loop = prueba_real
    _arrancar(loop, pres=250.0)
    loop._estado_publicado_mono = time.monotonic()
    assert loop.estado_seguro.activo
    for nombre in ("descompresion_rapida", "descompresion_chaqueta", "vapor_camara",
                   "aire_comprimido_camara"):
        assert client.patch(f"/io/test/output/{nombre}",
                            json={"value": True}).status_code == 200, nombre
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    assert r.status_code == 409 and r.json()["codigo"] == sps.CAMARA_PRESURIZADA


@pytest.mark.req("ESG-02")
def test_patch_con_estado_seguro_sin_presion_mantiene_el_bloqueo(prueba_real):
    client, ctx, loop = prueba_real
    _arrancar(loop, pres=None)
    loop._estado_publicado_mono = time.monotonic()
    r = client.patch("/io/test/output/descompresion_rapida", json={"value": True})
    assert r.status_code == 409 and r.json()["codigo"] == sps.ESTADO_SEGURO


@pytest.mark.req("ESG-02")
def test_status_expone_los_avisos_de_corte():
    ctx = MagicMock()
    cargar_servidor(ctx)
    sistema = modulo_backend("rutas.sistema")
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.avisos_corte_prueba = [
        {"n": 1, "salida": "vapor_camara", "codigo": sps.PUERTA_ABIERTA,
         "aviso": "io.ui.aviso_vapor_cortado_puerta"}]
    assert sistema._avisos_corte_prueba() == ctx.control_loop.avisos_corte_prueba
    ctx.control_loop.test_mode_active = False
    assert sistema._avisos_corte_prueba() == []
