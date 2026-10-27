# Tanda 20, corrector r1 · reinicio del módulo (ADB-04, decisión 8) en
# ModbusLink: V20-s1-01 (evidencia del reinicio), V20-s1-02 (reinicio
# pendiente tras una escritura parcial), V20-s1-03 (reinicios acotados),
# V20-s1-04 (salidas confirmadas en 0 y permiso de reinicio; contexto en
# CICLO), V20-s1-05 (stop() durante la conexión). Contra el simulador M31
# (solo 127.0.0.1, puerto libre). Las conexiones se hacen síncronas
# (_conectar_verificado sin hilo) para que el orden de los intentos sea
# determinista. DECISIONES SIN CONFIRMAR hasta M-5b.

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.protocols import modbus_link as ml
from autoclave.protocols.modbus_link import ModbusLink
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado, config_para

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

    def _crear(**kw):
        cambios = {k: v for k, v in kw.items() if k != "reinicio_permitido"}
        enlace = ModbusLink(config=config_para(sim, **cambios),
                            reinicio_permitido=kw.get("reinicio_permitido"))
        creados.append(enlace)
        return enlace

    yield _crear
    for e in creados:
        e.stop()


def _conectar(enlace):
    """Un intento de conexión síncrono: (ok, alarmas [(origen, id, motivo)])."""
    ok = enlace._conectar_verificado()
    alarmas = [(e.origen, e.alarm_id, e.motivo) for e in enlace.tomar_eventos()
               if e.alarm_id is not None]
    return ok, alarmas


def _ordenes_reinicio(sim):
    return [w for w in sim.escrituras if w[1] == m31.REINICIO]


# ---------------------------------------------------------------------------
# V20-s1-01 · El reinicio exige evidencia
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-01")
def test_respuesta_de_excepcion_a_la_orden_de_reinicio(sim, crear):
    sim.rechaza_reinicio = True
    enlace = crear()
    ok, alarmas = _conectar(enlace)
    assert ok is False and not enlace.is_connected()
    assert [(o, a) for o, a, _ in alarmas] == [("handshake", "TARJETA_CONFIG_SEGURIDAD")]
    assert "rechazó la orden de reinicio" in alarmas[0][2]
    assert sim.reinicios == 0
    assert enlace.get_diagnostico()["modulos"]["reinicios_modulo"] == 0
    assert enlace._reinicio_pendiente is True


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-01")
def test_modulo_que_acepta_la_orden_y_no_se_reinicia(sim, crear):
    sim.ignora_reinicio = True
    enlace = crear()
    ok, alarmas = _conectar(enlace)
    assert ok is False and not enlace.is_connected()
    assert [(o, a) for o, a, _ in alarmas] == [("handshake", "TARJETA_CONFIG_SEGURIDAD")]
    assert "no se reinició" in alarmas[0][2]
    assert len(_ordenes_reinicio(sim)) == 1          # la orden sí se envió
    assert sim.reinicios == 0
    assert enlace.get_diagnostico()["modulos"]["reinicios_modulo"] == 0
    assert enlace._reinicio_pendiente is True


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-01")
def test_simulador_valor_distinto_de_la_clave_no_reinicia(sim):
    from pymodbus.client import ModbusTcpClient
    c = ModbusTcpClient(sim.host, port=sim.puerto, timeout=0.2, retries=0)
    assert c.connect()
    try:
        r = c.write_register(m31.REINICIO, 0x1234, device_id=sim.unit_id)
        assert not r.isError()
        import time
        time.sleep(0.3)
        assert sim.reinicios == 0
        assert not c.read_holding_registers(m31.CODIGO_ERROR, count=1,
                                            device_id=sim.unit_id).isError()
        # Con rechaza_reinicio, la clave correcta recibe una excepción Modbus
        sim.rechaza_reinicio = True
        r = c.write_register(m31.REINICIO, m31.CLAVE_REINICIO, device_id=sim.unit_id)
        assert r.isError()
        time.sleep(0.3)
        assert sim.reinicios == 0
    finally:
        c.close()


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-01")
def test_reinicio_con_evidencia_cuenta_y_conecta(sim, crear):
    enlace = crear()
    ok, alarmas = _conectar(enlace)
    assert ok is True and alarmas == []
    assert sim.reinicios == 1 and len(_ordenes_reinicio(sim)) == 1
    assert enlace.get_diagnostico()["modulos"]["reinicios_modulo"] == 1
    assert enlace._reinicio_pendiente is False and enlace._reinicios_sin_verificar == 0


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-01")
def test_orden_sin_respuesta_se_tolera_si_hay_evidencia(sim, crear, monkeypatch):
    # Timeout de la orden (el módulo se reinicia antes de responder): se sigue
    # y la evidencia la da el cierre de la conexión.
    enlace = crear()
    original = enlace._orden_reinicio

    def _sin_respuesta():
        original()
        return "sin_respuesta"

    monkeypatch.setattr(enlace, "_orden_reinicio", _sin_respuesta)
    ok, alarmas = _conectar(enlace)
    assert ok is True and alarmas == [] and sim.reinicios == 1


# ---------------------------------------------------------------------------
# V20-s1-02 · Escritura parcial sin reinicio
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-02")
def test_escritura_parcial_fuerza_el_reinicio_en_el_intento_siguiente(sim, crear):
    # Bloque A (estado de falla de las DO) se escribe; bloque B (tiempo de
    # desconexión) no queda: la conexión falla sin reiniciar.
    sim.registros_ignorados.add(m31.TIEMPO_DESCONEXION)
    enlace = crear()
    ok, alarmas = _conectar(enlace)
    assert ok is False
    assert alarmas[0][1] == "TARJETA_CONFIG_SEGURIDAD"
    assert "tiempo de desconexión" in alarmas[0][2]
    assert sim.holding[m31.DO_FALLA] == 1            # A sí quedó escrito
    assert sim.reinicios == 0 and _ordenes_reinicio(sim) == []
    assert enlace._reinicio_pendiente is True
    # Alguien deja el resto igual: todo coincide, pero A no está activo sin
    # reinicio. El intento siguiente reinicia aunque no escriba nada.
    sim.registros_ignorados.clear()
    sim.precargar_configuracion()
    n = len(sim.escrituras)
    ok, alarmas = _conectar(enlace)
    assert ok is True and alarmas == []
    assert not [w for w in sim.escrituras[n:] if w[0] == 16]      # no escribió config
    assert sim.reinicios == 1 and len(_ordenes_reinicio(sim)) == 1
    assert enlace._reinicio_pendiente is False


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-02")
def test_sin_escritura_ni_pendiente_no_reinicia(sim, crear):
    sim.precargar_configuracion()
    enlace = crear()
    for _ in range(2):
        ok, alarmas = _conectar(enlace)
        assert ok is True and alarmas == []
        enlace.solicitar_handshake()
    assert sim.reinicios == 0 and _ordenes_reinicio(sim) == []


# ---------------------------------------------------------------------------
# V20-s1-03 · Reinicios acotados
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-03")
def test_reinicios_sin_verificar_acotados(sim, crear):
    sim.ignora_reinicio = True
    enlace = crear()
    motivos = []
    for _ in range(5):
        ok, alarmas = _conectar(enlace)
        assert ok is False
        assert [a for _, a, _ in alarmas] == ["TARJETA_CONFIG_SEGURIDAD"]
        motivos.append(alarmas[0][2])
    assert ModbusLink.MAX_REINICIOS_SIN_VERIFICAR == 2
    assert len(_ordenes_reinicio(sim)) == 2
    assert all("no se reinició" in m for m in motivos[:2])
    assert all("no se vuelve a escribir ni a reiniciar" in m for m in motivos[2:])
    assert "reiniciar el equipo" in motivos[-1]
    # En el estado acotado no se escribe la configuración
    n = len(sim.escrituras)
    _conectar(enlace)
    assert not [w for w in sim.escrituras[n:] if w[0] in (6, 16)]


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-03")
def test_verificacion_correcta_reinicia_el_contador(sim, crear):
    sim.ignora_reinicio = True
    enlace = crear()
    ok, _ = _conectar(enlace)
    assert ok is False and enlace._reinicios_sin_verificar == 1
    sim.ignora_reinicio = False
    ok, alarmas = _conectar(enlace)
    assert ok is True and alarmas == []
    assert enlace._reinicios_sin_verificar == 0 and enlace._reinicio_pendiente is False
    assert sim.reinicios == 1


# ---------------------------------------------------------------------------
# V20-s1-04 · Salidas confirmadas en 0 y permiso de reinicio
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-04")
def test_salida_que_no_apaga_impide_el_reinicio(sim, crear):
    sim.bobinas[4] = True
    sim.bobinas_no_apagan = True
    enlace = crear()
    ok, alarmas = _conectar(enlace)
    assert ok is False
    assert alarmas[0][1] == "TARJETA_SALIDAS_NO_APAGADAS"
    assert "antes del reinicio" in alarmas[0][2] and "DO5" in alarmas[0][2]
    assert sim.reinicios == 0 and _ordenes_reinicio(sim) == []
    assert enlace._reinicio_pendiente is True and enlace._reinicios_sin_verificar == 0


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-04")
def test_lectura_de_salidas_fallida_impide_el_reinicio(sim, crear, monkeypatch):
    enlace = crear()
    original = enlace._tx
    escrito = {"config": False}

    def _tx(nombre, *args, **kw):
        if nombre == "write_registers":
            escrito["config"] = True
        if nombre == "read_coils" and escrito["config"]:
            raise ml._FalloTransaccion("sin respuesta (prueba)")
        return original(nombre, *args, **kw)

    monkeypatch.setattr(enlace, "_tx", _tx)
    ok, alarmas = _conectar(enlace)
    assert ok is False
    assert alarmas[0][1] == "TARJETA_SALIDAS_NO_APAGADAS"
    assert "No se pudo confirmar el apagado" in alarmas[0][2]
    assert sim.reinicios == 0 and _ordenes_reinicio(sim) == []


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-04")
@pytest.mark.parametrize("permiso", [lambda: False, lambda: 1 / 0])
def test_reinicio_no_permitido_queda_diferido(sim, crear, permiso):
    estado = {"permitido": permiso}
    enlace = crear(reinicio_permitido=lambda: estado["permitido"]())
    ok, alarmas = _conectar(enlace)
    assert ok is False and not enlace.is_connected()
    assert [a for _, a, _ in alarmas] == ["TARJETA_CONFIG_SEGURIDAD"]
    # V20-rr-05 (re-revisión R): sin permiso de reinicio (CICLO) tampoco se
    # escribe la configuración en el módulo (antes se escribía y el reinicio
    # quedaba diferido); la conexión falla igual, sin escribir nada.
    assert "diferidos hasta salir del ciclo" in alarmas[0][2]
    assert sim.holding[m31.MODO_FALLA] == 0           # fábrica: no se escribió
    assert not [w for w in sim.escrituras if w[0] in (6, 16)]
    assert sim.reinicios == 0 and _ordenes_reinicio(sim) == []
    assert enlace._reinicio_pendiente is False and enlace._reinicios_sin_verificar == 0
    # Mientras siga sin permiso no reinicia (ni cuenta reinicios)
    ok, alarmas = _conectar(enlace)
    assert ok is False and "diferido" in alarmas[0][2] and sim.reinicios == 0
    # Al salir del ciclo, el intento siguiente reinicia y verifica
    estado["permitido"] = lambda: True
    ok, alarmas = _conectar(enlace)
    assert ok is True and alarmas == [] and sim.reinicios == 1
    assert sim.holding[m31.MODO_FALLA] == 1


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-rr-05")
def test_sin_permiso_con_reinicio_pendiente_no_escribe_ni_reinicia(sim, crear):
    estado = {"permitido": True}
    enlace = crear(reinicio_permitido=lambda: estado["permitido"])
    enlace._reinicio_pendiente = True       # escritura previa sin reinicio verificado
    sim.precargar_configuracion()
    estado["permitido"] = False
    n = len(sim.escrituras)
    ok, alarmas = _conectar(enlace)
    assert ok is False and [a for _, a, _ in alarmas] == ["TARJETA_CONFIG_SEGURIDAD"]
    assert "diferidos" in alarmas[0][2]
    assert not [w for w in sim.escrituras[n:] if w[0] in (6, 16)]
    assert sim.reinicios == 0 and enlace._reinicio_pendiente is True


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-04")
def test_contexto_niega_el_reinicio_en_ciclo():
    from autoclave.backend.context import BackendContext
    from autoclave.core.runtime.status import EstadoAutoclave
    estado = EstadoAutoclave()
    falso = SimpleNamespace(estado=estado)
    for st in GlobalState:
        estado.set_machine_state(st)
        assert BackendContext.reinicio_modulo_permitido(falso) is (st != GlobalState.CICLO)
    roto = SimpleNamespace(estado=MagicMock(get_machine_state=MagicMock(side_effect=RuntimeError)))
    assert BackendContext.reinicio_modulo_permitido(roto) is False


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-s1-04")
def test_construir_control_conecta_el_permiso(tmp_path, monkeypatch):
    from autoclave.backend import context as ctx_mod
    from autoclave.backend.context import BackendContext
    from autoclave.core.runtime import asignacion_io as aio
    aio.restablecer_memoria_fabrica_codigo()
    try:
        enlace = MagicMock()
        monkeypatch.setattr(ctx_mod, "build_enlace", lambda units, al_conectar=None: enlace)
        monkeypatch.setattr(ctx_mod, "build_doors_cfg", lambda profile: [])
        for nombre in ("SetOutput", "ServicioPuertas", "RealtimePrinter", "CycleLogger",
                       "ControlLoop"):
            monkeypatch.setattr(ctx_mod, nombre, MagicMock())
        ctx = BackendContext()
        ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(tmp_path / "asig.json"))
        ctx.construir_control(object())
        assert enlace.reinicio_permitido == ctx.reinicio_modulo_permitido
        ctx.estado.set_machine_state(GlobalState.CICLO)
        assert enlace.reinicio_permitido() is False
        ctx.estado.set_machine_state(GlobalState.PREPARADO)
        assert enlace.reinicio_permitido() is True
    finally:
        aio.restablecer_memoria_fabrica_codigo()


# ---------------------------------------------------------------------------
# V20-s1-05 · stop() durante la conexión
# ---------------------------------------------------------------------------

@pytest.mark.req("V20-s1-05")
def test_stop_al_final_de_la_conexion_no_la_verifica(sim, crear, monkeypatch):
    sim.precargar_configuracion()
    enlace = crear()
    original = enlace._pasos_conexion

    def _pasos(fin):
        tarjeta = original(fin)
        enlace._parar.set()             # stop() llega justo antes de verificar
        return tarjeta

    monkeypatch.setattr(enlace, "_pasos_conexion", _pasos)
    ok = enlace._conectar_verificado()
    assert ok is False
    assert enlace.handshake_completo is False and not enlace.is_connected()
    assert not [e for e in enlace.tomar_eventos() if e.origen == "conectada"]


@pytest.mark.req("V20-s1-05")
def test_stop_tras_la_reapertura_del_reinicio(sim, crear, monkeypatch):
    enlace = crear()
    original = enlace._abrir_socket
    llamadas = {"n": 0}

    def _abrir():
        llamadas["n"] += 1
        ok = original()
        if llamadas["n"] >= 2:          # la reapertura tras el reinicio
            enlace._parar.set()
        return ok

    monkeypatch.setattr(enlace, "_abrir_socket", _abrir)
    ok = enlace._conectar_verificado()
    assert ok is False and enlace.handshake_completo is False
    assert sim.reinicios == 1
    assert not [e for e in enlace.tomar_eventos() if e.origen == "conectada"]


# ---------------------------------------------------------------------------
# V20-rr-01 (re-revisión R) · Una orden no enviada o un cierre local no son
# evidencia de reinicio
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-rr-01")
def test_orden_sin_cliente_conectado_no_se_envia(sim, crear):
    enlace = crear()
    assert enlace._orden_reinicio() == "no_enviada"          # sin socket abierto
    assert _ordenes_reinicio(sim) == []


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-rr-01")
@pytest.mark.parametrize("orden,sondeo", [("no_enviada", "cerrado"), ("aceptada", "ajeno")])
def test_orden_no_enviada_o_cierre_local_dan_config_seguridad(sim, crear, monkeypatch,
                                                              orden, sondeo):
    enlace = crear()
    monkeypatch.setattr(enlace, "_orden_reinicio", lambda: orden)
    monkeypatch.setattr(enlace, "_sondeo_reinicio", lambda: sondeo)
    ok, alarmas = _conectar(enlace)
    assert ok is False and [a for _, a, _ in alarmas] == ["TARJETA_CONFIG_SEGURIDAD"]
    assert enlace._reinicio_pendiente is True
    assert enlace.get_diagnostico()["modulos"]["reinicios_modulo"] == 0


@pytest.mark.req("ADB-04")
@pytest.mark.req("V20-rr-01")
def test_sondeo_con_otro_cliente_es_ajeno(sim, crear):
    enlace = crear()
    assert enlace._abrir_socket()
    try:
        enlace._cliente_orden_reinicio = object()     # la orden se envió con otro cliente
        assert enlace._sondeo_reinicio() == "ajeno"
    finally:
        enlace._desconectar()
