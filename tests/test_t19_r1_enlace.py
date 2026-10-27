# Tanda 19, R1: correcciones de la revisión R del enlace Modbus TCP
# (V19-s1-01, 03, 04, 05, 06 y V19-s3-04), contra el simulador M31. Todo en
# 127.0.0.1 con un puerto libre; sin red real, puertos COM ni hardware.

import logging
import threading
import time

import pytest

from autoclave.protocols import modbus_link_config as mc
from autoclave.protocols.modbus_link import ModbusLink
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado, TickLazo, config_para, esperar

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)


@pytest.fixture
def sim():
    s = M31Simulado()
    s.iniciar()
    yield s
    s.detener()


@pytest.fixture
def crear(sim):
    creados = []

    def _crear(arrancar=True, **cambios):
        enlace = ModbusLink(config=config_para(sim, **cambios))
        enlace.MARGEN_TICK_CONTROL = 0.3
        creados.append(enlace)
        if arrancar:
            enlace.start()
        return enlace

    yield _crear
    for e in creados:
        e.stop()


def _eventos_hasta(enlace, predicado, timeout=5.0):
    acumulados = []

    def _hay():
        acumulados.extend(enlace.tomar_eventos())
        return any(predicado(ev) for ev in acumulados)

    esperar(_hay, timeout)
    return acumulados


def _alarmas(eventos):
    return [(e.origen, e.alarm_id) for e in eventos if e.alarm_id is not None]


def _conectado(enlace, timeout=5.0):
    eventos = _eventos_hasta(enlace, lambda e: e.origen == "conectada", timeout)
    assert enlace.is_connected(), eventos
    return eventos


def _del_paso_2(e):
    return e.alarm_id == "TARJETA_MODULOS_ORDEN" and "Reload" in e.motivo


# ---------------------------------------------------------------------------
# V19-s1-01 · 0F de mejor esfuerzo cuando la conexión falla con socket abierto
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-06")
@pytest.mark.req("MOD-08")
def test_conexion_fallida_apaga_las_salidas(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(3, True) is True
        assert esperar(lambda: sim.bobinas[2] and enlace.get_state()["do"][2] == 1)
        n_antes = len(sim.escrituras)
        # La reconexión fallará en el paso 2 (orden incorrecto)
        sim.orden_incorrecto(codigo=True)
        enlace.solicitar_handshake()
        eventos = _eventos_hasta(enlace, _del_paso_2)
        assert any(_del_paso_2(e) for e in eventos), eventos
        assert esperar(lambda: sim.bobinas[2] is False, 2)
        nuevas = sim.escrituras[n_antes:]
        assert (15, 0, [False] * 32) in nuevas
        # Lo comandado queda todo en OFF (sin confirmar con lectura)
        with enlace.data_lock:
            assert all(est is False for est, _ in enlace._comandado.values())
            assert len(enlace._comandado) == 32
        assert not enlace.is_connected()
        # Mientras falla, los reintentos mantienen vivo el temporizador del
        # módulo: la bobina no la apagó el módulo sino el 0F.
        assert sim.bandera_falla() == 0


@pytest.mark.req("MOD-06")
def test_conexion_fallida_en_el_paso_3_tambien_apaga(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(1, True) is True
        assert esperar(lambda: sim.bobinas[0])
        sim.holding[m31.MODO_FALLA] = 0
        sim.registros_ignorados.add(m31.MODO_FALLA)
        enlace.solicitar_handshake()
        eventos = _eventos_hasta(enlace, lambda e: e.alarm_id == "TARJETA_CONFIG_SEGURIDAD")
        assert ("operacion", "TARJETA_CONFIG_SEGURIDAD") in _alarmas(eventos)
        assert esperar(lambda: sim.bobinas[0] is False, 2)


@pytest.mark.req("MOD-06")
def test_conexion_fallida_sin_socket_no_intenta_0f(sim):
    puerto = sim.puerto
    sim.detener()
    enlace = ModbusLink(config=config_para(sim, puerto=puerto, reintento_conexion_s=0.1))
    llamadas = []
    original = enlace._tx
    enlace._tx = lambda *a, **k: (llamadas.append(a[0]), original(*a, **k))[1]
    enlace.start()
    try:
        time.sleep(0.4)
        assert "write_coils" not in llamadas
        assert not enlace.puerto_presente()
    finally:
        enlace.stop()


# ---------------------------------------------------------------------------
# V19-s1-03 · Diagnóstico de 0x0C35-0x0C37
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-07")
@pytest.mark.req("MOD-10")
def test_reload_sin_reinicio_detectado_en_operacion(sim, crear):
    enlace = crear()
    _conectado(enlace)
    lecturas = []
    original = enlace._leer_holding
    enlace._leer_holding = lambda d, n: (lecturas.append((d, n)), original(d, n))[1]
    # Reload 5-10 s sin reinicio: la conexión TCP sigue y la configuración
    # vuelve a fábrica (0x0C35=100, 0x0C36=0).
    sim.restablecer_fabrica(reiniciar=False)
    assert sim.holding[m31.MODO_FALLA] == 0
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None, 3)
    assert _alarmas(eventos)[0] == ("operacion", "TARJETA_CONFIG_SEGURIDAD")
    assert "0x0C35=100" in [e.motivo for e in eventos if e.alarm_id][0]
    # El diagnóstico lee 0x0C35-0x0C37 en una sola transacción
    assert (m31.TIEMPO_DESCONEXION, 3) in lecturas
    assert (m31.BANDERA_FALLA, 1) not in lecturas[:lecturas.index((m31.TIEMPO_DESCONEXION, 3))]
    # La reconexión reescribe la configuración
    _conectado(enlace)
    assert sim.holding[m31.MODO_FALLA] == 1 and sim.holding[m31.TIEMPO_DESCONEXION] == 5
    assert all(sim.holding[m31.DO_FALLA + i] == 1 for i in range(32))


@pytest.mark.req("MOD-10")
def test_solo_tiempo_de_desconexion_distinto_invalida(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.holding[m31.TIEMPO_DESCONEXION] = 7
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None, 3)
    assert _alarmas(eventos)[0] == ("operacion", "TARJETA_CONFIG_SEGURIDAD")
    _conectado(enlace)
    assert sim.holding[m31.TIEMPO_DESCONEXION] == 5


@pytest.mark.req("MOD-10")
def test_configuracion_correcta_no_invalida(sim, crear):
    enlace = crear()
    _conectado(enlace)
    time.sleep(2.3)       # al menos dos diagnósticos
    assert _alarmas(enlace.tomar_eventos()) == []
    assert enlace.is_connected()


# ---------------------------------------------------------------------------
# V19-s1-05 · set_output frente al paso 4
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-11")
def test_paso_4_se_hace_bajo_cmd_lock(sim, crear):
    enlace = crear(arrancar=False)
    libre_durante_apagado = []
    original = enlace._tx

    def _tx(nombre, *a, **k):
        if nombre == "write_coils" and not k.get("forzar"):
            r = []
            t = threading.Thread(
                target=lambda: r.append(enlace._cmd_lock.acquire(blocking=False)))
            t.start()
            t.join()
            if r[0]:
                enlace._cmd_lock.release()     # no lo tenía el hilo de sondeo (falla)
            libre_durante_apagado.append(r[0])
        return original(nombre, *a, **k)

    enlace._tx = _tx
    enlace.start()
    _conectado(enlace)
    assert libre_durante_apagado and not any(libre_durante_apagado)


@pytest.mark.req("MOD-11")
def test_set_output_recomprueba_la_conexion_dentro_del_candado(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        resultado = []
        enlace._cmd_lock.acquire()
        try:
            t = threading.Thread(target=lambda: resultado.append(enlace.set_output(6, True)))
            t.start()
            time.sleep(0.1)     # set_output pasó la primera comprobación y espera
            assert t.is_alive()
            enlace._handshake_ok = False     # invalidación mientras espera
        finally:
            enlace._cmd_lock.release()
        t.join(2.0)
        assert resultado == [False]
        assert not [w for w in sim.escrituras if w[0] == 5 and w[1] == 5]
        assert sim.bobinas[5] is False


# ---------------------------------------------------------------------------
# V19-s1-06 · Bandera 0x0C37 que no se puede borrar
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-06")
def test_bandera_que_no_se_borra_falla_con_config_seguridad(sim, crear):
    sim.holding[m31.BANDERA_FALLA] = 1
    sim.registros_ignorados.add(m31.BANDERA_FALLA)
    enlace = crear()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    alarmas = _alarmas(eventos)
    assert alarmas[0] == ("handshake", "TARJETA_CONFIG_SEGURIDAD")
    assert "no se pudo borrar la bandera de falla 0x0c37" in \
        [e.motivo for e in eventos if e.alarm_id][0].lower()
    assert ("operacion", "TARJETA_WATCHDOG") not in alarmas
    assert not enlace.is_connected()
    # Se borra en cuanto el registro vuelve a aceptar la escritura
    sim.registros_ignorados.discard(m31.BANDERA_FALLA)
    _conectado(enlace)
    assert sim.bandera_falla() == 0


@pytest.mark.req("MOD-06")
@pytest.mark.req("MOD-08")
def test_bandera_que_no_se_borra_tras_suspension_no_es_bucle_de_watchdog(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(2, True)
        assert esperar(lambda: sim.bobinas[1])
    sim.registros_ignorados.add(m31.BANDERA_FALLA)
    # Sin tick: el módulo vence su tiempo de desconexión y pone la bandera
    assert esperar(lambda: sim.bandera_falla() == 1, 3)
    with TickLazo(enlace):
        eventos = _eventos_hasta(
            enlace, lambda e: e.alarm_id == "TARJETA_CONFIG_SEGURIDAD", 3)
        time.sleep(0.6)       # varios reintentos
        eventos += enlace.tomar_eventos()
    alarmas = _alarmas(eventos)
    assert ("operacion", "TARJETA_CONFIG_SEGURIDAD") in alarmas
    assert alarmas.count(("operacion", "TARJETA_CONFIG_SEGURIDAD")) >= 2   # reintentos
    # El corte se informa una sola vez, no en cada reintento
    assert alarmas.count(("operacion", "TARJETA_WATCHDOG")) == 1
    assert not enlace.is_connected()


# ---------------------------------------------------------------------------
# V19-s3-04 · TARJETA_MODULOS_ORDEN del paso 2 en una reconexión en operación
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-06")
@pytest.mark.req("MOD-10")
def test_modulos_orden_en_reconexion_tras_operacion_sale_en_operacion(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.orden_incorrecto(codigo=False, negociacion=True)
    enlace.solicitar_handshake()
    eventos = _eventos_hasta(enlace, _del_paso_2)
    del_paso_2 = [e for e in eventos if _del_paso_2(e)]
    assert del_paso_2 and all(e.origen == "operacion" for e in del_paso_2)
    # Al quitar la falla se conecta y la siguiente falla del paso 2 en una
    # conexión que NO viene de operación vuelve a ser "handshake".
    sim.orden_incorrecto(codigo=False, negociacion=False)
    _conectado(enlace)


@pytest.mark.req("MOD-06")
def test_modulos_orden_en_la_conexion_inicial_sigue_en_handshake(sim, crear):
    sim.orden_incorrecto(codigo=True)
    enlace = crear()
    eventos = _eventos_hasta(enlace, _del_paso_2)
    assert [e.origen for e in eventos if _del_paso_2(e)][0] == "handshake"


# ---------------------------------------------------------------------------
# V19-s1-04 · Validación cruzada de la configuración
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-06")
@pytest.mark.parametrize("datos", [
    {"periodo_sondeo_s": 0.3, "tiempo_desconexion_modulo_ds": 5},     # 0,3 >= 0,25
    {"periodo_sondeo_s": 0.25, "tiempo_desconexion_modulo_ds": 5},    # igual: no es menor
    {"periodo_sondeo_s": 0.5},                                       # con 10 ds: 0,5 >= 0,5
    {"tiempo_desconexion_modulo_ds": 5, "periodo_sondeo_s": 1.0},
])
def test_periodo_no_menor_que_media_desconexion(datos, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.config_desde_dict(dict(datos, reintento_conexion_s=1.5))
    defecto = mc.ModbusLinkConfig()
    assert cfg.periodo_sondeo_s == defecto.periodo_sondeo_s
    assert cfg.tiempo_desconexion_modulo_ds == defecto.tiempo_desconexion_modulo_ds
    assert cfg.reintento_conexion_s == 1.5
    assert "periodo_sondeo_s" in caplog.text and "tiempo_desconexion_modulo_ds" in caplog.text


@pytest.mark.req("MOD-06")
@pytest.mark.parametrize("timeout", [0.5, 0.8, 2.0])
def test_timeout_no_menor_que_medio_segundo(timeout, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.config_desde_dict({"timeout_s": timeout, "periodo_sondeo_s": 0.2})
    assert cfg.timeout_s == mc.ModbusLinkConfig().timeout_s
    assert cfg.periodo_sondeo_s == 0.2       # la otra clave se conserva
    assert "timeout_s=" in caplog.text


@pytest.mark.req("MOD-06")
def test_combinacion_valida_sin_advertencia(caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.config_desde_dict({"periodo_sondeo_s": 0.2, "tiempo_desconexion_modulo_ds": 5,
                                    "timeout_s": 0.45})
    assert (cfg.periodo_sondeo_s, cfg.tiempo_desconexion_modulo_ds, cfg.timeout_s) == \
        (0.2, 5, 0.45)
    assert "modbus_link" not in caplog.text


@pytest.mark.req("MOD-06")
def test_defectos_internos_cumplen_la_validacion_cruzada():
    d = mc.ModbusLinkConfig()
    assert d.periodo_sondeo_s < d.tiempo_desconexion_modulo_ds / 20.0
    assert d.timeout_s < mc.TIMEOUT_MAXIMO_CRUZADO_S
