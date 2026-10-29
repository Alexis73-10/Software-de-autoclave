# Tanda 19, P-s1: ModbusLink contra el simulador M31 (MOD-02, MOD-03,
# MOD-06 a MOD-11, MOD-14). Todo en 127.0.0.1 con un puerto libre; sin red
# real, puertos COM ni hardware.

import inspect
import logging
import threading
import time

import pytest

from autoclave.protocols import enlace as enlace_mod
from autoclave.protocols.modbus_link import ModbusLink
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado, TickLazo, config_para, esperar

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sim():
    s = M31Simulado()
    s.iniciar()
    yield s
    s.detener()


@pytest.fixture
def crear(sim):
    """Fábrica de enlaces apuntando al simulador; los detiene al final."""
    creados = []

    def _crear(arrancar=True, on_update=None, **cambios):
        enlace = ModbusLink(on_update=on_update, config=config_para(sim, **cambios))
        # Margen del tick corto para que las pruebas sean rápidas; el
        # mecanismo es el mismo que con 1,5 s.
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
    """Espera la conexión verificada Y su evento "conectada" (se encola justo
    después de verificarla)."""
    eventos = _eventos_hasta(enlace, lambda e: e.origen == "conectada", timeout)
    assert enlace.is_connected(), eventos
    assert "conectada" in [e.origen for e in eventos], eventos
    return eventos


# ---------------------------------------------------------------------------
# MOD-02 · Interfaz
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-02")
def test_cumple_la_interfaz_y_las_firmas_de_enlace_es():
    # Tanda 20 (T20-03): serial_link.py se retira; las firmas se comparan con
    # la interfaz EnlaceES (protocols/enlace.py), con la misma aserción.
    enlace = ModbusLink(config=config_para(M31Simulado()))
    assert isinstance(enlace, enlace_mod.EnlaceES)
    for nombre in enlace_mod.MIEMBROS_ENLACE:
        assert hasattr(enlace, nombre), nombre
        if nombre in ("on_update", "al_conectar"):
            assert getattr(enlace, nombre) is None
            continue
        a = inspect.getattr_static(ModbusLink, nombre)
        b = inspect.getattr_static(enlace_mod.EnlaceES, nombre)
        if isinstance(b, property):
            assert isinstance(a, property), nombre
            continue
        pa = [(p.name, p.default) for p in inspect.signature(a).parameters.values()]
        pb = [(p.name, p.default) for p in inspect.signature(b).parameters.values()]
        assert pa == pb, nombre


@pytest.mark.req("MOD-02")
def test_estado_inicial_falla_cerrada():
    enlace = ModbusLink(config=config_para(M31Simulado()))
    st = enlace.get_state()
    assert set(st) == {"ai", "ai_seq", "di", "do", "port_open", "data_alive", "last_update"}
    assert len(st["ai"]) == 24 and len(st["di"]) == 56     # tanda 23 (AIN-03) and len(st["do"]) == 32
    assert st["ai_seq"] == 0 and not st["port_open"] and not st["data_alive"]
    assert not enlace.is_connected() and not enlace.puerto_presente()
    assert enlace.handshake_completo is False
    assert enlace.edad_ultima_di() is None and enlace.edad_ultima_ai() is None
    assert enlace.secuencia_ultima_di() is None and enlace.secuencia_ultima_ai() is None
    assert enlace.estado_ultima_ai() == (None, None)
    assert enlace.tarjeta() == {"version": None, "protocolo": None, "id": None}
    assert enlace.set_output(1, True) is False
    assert enlace.all_off(0.1) is False
    diag = enlace.get_diagnostico()
    assert set(diag) == {"lineas_invalidas_total", "lineas_invalidas_consecutivas",
                         "handshake_completo", "tarjeta_st", "modulos"}
    assert diag["tarjeta_st"] is None
    # Tanda 20: se agregan "registro_0c37" (ADB-05, valor crudo de 0x0C37) y
    # "reinicios_modulo" (ADB-04 / decisión 8) a las claves anteriores.
    assert set(diag["modulos"]) == {"modelos", "firmware", "mac", "codigo_error",
                                    "mascara_expansores", "falla_salidas", "registro_0c37",
                                    "reinicios_modulo", "enlace"}
    assert diag["modulos"]["enlace"] == "modbus"


# ---------------------------------------------------------------------------
# MOD-06 · Conexión verificada
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-06")
@pytest.mark.req("MOD-07")
def test_conexion_correcta(sim, crear):
    orden = []
    enlace = crear(arrancar=False)
    enlace.al_conectar = lambda t: orden.append(("al_conectar", t, list(enlace._eventos)))
    enlace.start()
    eventos = _conectado(enlace)
    assert [(e.origen, e.alarm_id) for e in eventos] == [("conectada", None)]
    # FW-INF (corrige ADB-02, 28-oct): texto 0x0C2C del principal y «vX.Y»
    # de cada esclavo según 0x0D80 (valores reales del equipo de pruebas).
    modulo_es = {"version": "9232-0-13 / v1.0,v1.0,v1.0,v1.0,-", "protocolo": "modbus-tcp",
               "id": "A1B2C3D4E5F6"}
    assert enlace.tarjeta() == modulo_es
    # al_conectar corre antes de que se encole "conectada"
    assert len(orden) == 1 and orden[0][1] == modulo_es and orden[0][2] == []
    assert enlace.puerto_presente() and enlace.handshake_completo
    # Configuración de seguridad escrita
    h = sim.holding
    assert h[m31.TIEMPO_DESCONEXION] == 5 and h[m31.MODO_FALLA] == 1
    assert all(h[m31.DO_FALLA + i] == 1 for i in range(32))
    assert all(h[m31.DO_ENCENDIDO + i] == 0 for i in range(32))
    assert all(h[m31.DO_MODO + i] == 0 for i in range(32))
    assert all(h[m31.RANGO_AI + i] == 1 for i in range(16))
    assert h[m31.FILTRO_AI] == 0
    assert all(h[m31.PT_FILTRO + i] == 1 for i in range(6))
    assert all(h[m31.PT_UNIDAD + i] == 0 and h[m31.PT_COMPENSACION + i] == 0
               and h[m31.PT_DESHABILITADA + i] == 0 for i in range(6))
    # V19-s1-07 exigía la función 16 en cada bloque SIEMPRE. Su intención
    # cambia por decisiones_tanda_20.md, decisión 8 / ADB-04: cada bloque se
    # lee antes; los que difieren de fábrica se escriben con 16 (no basta con
    # leerlos), los que ya coinciden no se escriben, y todos quedan verificados
    # (valores arriba). Como hubo escritura, el módulo se reinició una vez.
    distintos = [
        (m31.DO_FALLA, [1] * 32), (m31.TIEMPO_DESCONEXION, [5]), (m31.MODO_FALLA, [1]),
        (m31.RANGO_AI, [1] * 16), (m31.PT_FILTRO, [1] * 6),
    ]
    iguales = [m31.DO_ENCENDIDO, m31.DO_MODO, m31.FILTRO_AI, m31.PT_UNIDAD,
               m31.PT_COMPENSACION, m31.PT_DESHABILITADA]
    for direccion, valores in distintos:
        assert (16, direccion, valores) in sim.escrituras, hex(direccion)
    for direccion in iguales:
        assert not [w for w in sim.escrituras if w[1] == direccion], hex(direccion)
    assert sim.reinicios == 1
    # Apagado de todo con 0F
    assert (15, 0, [False] * 32) in sim.escrituras
    diag = enlace.get_diagnostico()
    assert diag["handshake_completo"] is True
    assert diag["modulos"]["mac"] == "A1B2C3D4E5F6"
    # ADB-02: solo la parte de versión, con los crudos (antes
    # {"principal": "1.5", "expansiones": ["1.5"] * 4}).
    # FW-INF (28-oct): versión «vX.Y» en registros, solo informativa.
    assert diag["modulos"]["firmware"] == {
        "principal": "9232-0-13", "registro_principal": "v1.3",
        "expansiones": ["v1.0", "v1.0", "v1.0", "v1.0", "-"],
        "crudo_principal": 0x0103,
        "crudo_expansiones": [0x0100, 0x0100, 0x0100, 0x0100, 0x0000],
        "texto_principal": "9232-0-13", "compatible": None}
    assert diag["modulos"]["modelos"]["principal"] == "M31-XAXX0A00G-U"


@pytest.mark.req("MOD-06")
def test_bandera_de_falla_en_la_conexion_inicial_solo_log(sim, crear, caplog):
    sim.holding[m31.BANDERA_FALLA] = 1
    # ADB-05 (adenda_tanda_19_banco.md): 0x0C37 no es bandera; solo se
    # registra su valor crudo (log INFO, antes WARNING) y ya no se borra
    # (antes: sim.bandera_falla() == 0 tras escribir 0).
    with caplog.at_level(logging.INFO, logger="autoclave"):
        enlace = crear()
        eventos = _conectado(enlace)
    assert _alarmas(eventos) == []
    assert "0x0C37" in caplog.text
    assert not [w for w in sim.escrituras if w[1] == m31.BANDERA_FALLA]


@pytest.mark.req("MOD-06")
def test_sin_socket_no_hay_evento_y_puerto_ausente(sim):
    puerto = sim.puerto
    sim.detener()
    enlace = ModbusLink(config=config_para(sim, puerto=puerto, reintento_conexion_s=0.1))
    enlace.start()
    try:
        time.sleep(0.5)
        assert not enlace.puerto_presente() and not enlace.is_connected()
        assert enlace.tomar_eventos() == []
    finally:
        enlace.stop()


@pytest.mark.req("MOD-06")
def test_sin_respuesta_modbus_da_sin_trama_valida(sim, crear):
    sim.silencio = True
    enlace = crear()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    assert ("handshake", "TARJETA_SIN_TRAMA_VALIDA") in _alarmas(eventos)
    assert enlace.puerto_presente() and not enlace.is_connected()


@pytest.mark.req("MOD-06")
@pytest.mark.parametrize("preparar,alarma", [
    (lambda s: s.orden_incorrecto(codigo=True), "TARJETA_MODULOS_ORDEN"),
    (lambda s: s.orden_incorrecto(codigo=False, negociacion=True), "TARJETA_MODULOS_ORDEN"),
    (lambda s: s.holding.__setitem__(m31.CODIGO_ERROR, 7), "TARJETA_MODULOS_ORDEN"),
    (lambda s: s.expansor_sin_respuesta(2), "TARJETA_EXPANSOR_FUERA_DE_LINEA"),
    (lambda s: s.holding.__setitem__(m31.MASCARA, 1), "TARJETA_EXPANSOR_FUERA_DE_LINEA"),
    (lambda s: s.fijar_modelos("M31-XAXX0A00G-U", list(m31.MODELOS_ESCLAVOS_DEFECTO[:3])),
     "TARJETA_VERSION_INCOMPATIBLE"),
    (lambda s: s.fijar_modelos("M31-XAXX0A00G-U", list(m31.MODELOS_ESCLAVOS_DEFECTO)
                               + ["M31-GXXAX00A0-U"]), "TARJETA_VERSION_INCOMPATIBLE"),
    (lambda s: s.fijar_modelos("M31-XAAA0A00G-U", list(m31.MODELOS_ESCLAVOS_DEFECTO)),
     "TARJETA_VERSION_INCOMPATIBLE"),
    # ADB-01: 5 esclavos (ID 0 = E/S del principal); otro orden de los mismos
    # 5 (antes los 4 sin el ID 0).
    (lambda s: s.fijar_modelos("M31-XAXX0A00G-U", ["M31-GXAXX0A00-U", "M31-GAXXXA000-U",
                                                   "M31-GXDXX0600-U", "M31-GXXAX00A0-U",
                                                   "M31-GXXAX00A0-U"]),
     "TARJETA_VERSION_INCOMPATIBLE"),
    (lambda s: s.holding.__setitem__(m31.MODELO_PRINCIPAL, 0x0001),
     "TARJETA_VERSION_INCOMPATIBLE"),
    # FW-INF (28-oct): el firmware ya no bloquea (solo informativo); se
    # retiraron los casos de esclavo más nuevo y de versión 0.
    (lambda s: s.registros_ignorados.add(m31.MODO_FALLA), "TARJETA_CONFIG_SEGURIDAD"),
    (lambda s: s.registros_ignorados.add(m31.PT_FILTRO + 5), "TARJETA_CONFIG_SEGURIDAD"),
])
def test_cada_paso_fallido_con_su_alarma(sim, crear, preparar, alarma):
    preparar(sim)
    enlace = crear()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    assert _alarmas(eventos)[0] == ("handshake", alarma)
    assert not enlace.is_connected() and not enlace.handshake_completo
    # TMG-02: el ControlLoop descarta los eventos "handshake" sin puerto
    # presente; con el socket abierto deben verse.
    assert enlace.puerto_presente() is True
    # Reintento cada reintento_conexion_s (0,2 s): la misma alarma otra vez
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id == alarma)
    assert ("handshake", alarma) in _alarmas(eventos)


@pytest.mark.req("MOD-06")
def test_firmware_principal_mas_nuevo_es_valido(sim, crear):
    # FW-INF: versión «vX.Y» en registros; un esclavo igual al principal es
    # válido y se marca compatible.
    sim.fijar_firmware(0x0200, [0x0100, 0x0105, 0x0200, 0x0105, 0x0100])
    sim.fijar_firmware_texto("9232-0-16")
    enlace = crear()
    _conectado(enlace)
    assert enlace.tarjeta()["version"] == "9232-0-16 / v1.0,v1.5,v2.0,v1.5,v1.0"
    assert enlace.get_diagnostico()["modulos"]["firmware"]["compatible"] is True


@pytest.mark.req("MOD-07")
def test_valor_fuera_de_rango_descartado_da_config_seguridad(sim, crear):
    # El módulo descarta en silencio un valor fuera de rango (0x0C36 admite
    # 0-1): solo la relectura lo detecta.
    enlace = crear(arrancar=False)
    enlace._bloques_configuracion = lambda: [("modo de falla", m31.MODO_FALLA, [5])]
    enlace.start()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    assert _alarmas(eventos)[0] == ("handshake", "TARJETA_CONFIG_SEGURIDAD")
    escritas = [w for w in sim.escrituras if w[1] == m31.MODO_FALLA]
    assert len(escritas) >= 3      # intentos_escritura_config


@pytest.mark.req("MOD-06")
def test_salidas_no_apagadas(sim, crear):
    # ADB-04: con la configuración ya escrita no hay reinicio (que pondría las
    # salidas en su estado de encendido) y la prueba sigue mirando el paso 4.
    sim.precargar_configuracion()
    sim.bobinas[6] = True
    sim.bobinas_no_apagan = True
    enlace = crear()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    alarma = _alarmas(eventos)[0]
    assert alarma == ("handshake", "TARJETA_SALIDAS_NO_APAGADAS")
    assert "DO7" in [e.motivo for e in eventos if e.alarm_id][0]


@pytest.mark.req("MOD-06")
def test_reconecta_tras_quitar_la_falla(sim, crear):
    sim.orden_incorrecto(codigo=True)
    enlace = crear()
    _eventos_hasta(enlace, lambda e: e.alarm_id == "TARJETA_MODULOS_ORDEN")
    sim.orden_incorrecto(codigo=False)
    eventos = _conectado(enlace)
    assert ("conectada", None) in [(e.origen, e.alarm_id) for e in eventos]


@pytest.mark.req("MOD-07")
@pytest.mark.req("MOD-09")
def test_configuracion_reescrita_tras_restablecimiento_de_fabrica(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.restablecer_fabrica()      # Reload 5-10 s: config de fábrica y reinicio
    assert sim.holding[m31.MODO_FALLA] == 0 and sim.holding[m31.TIEMPO_DESCONEXION] == 100
    assert esperar(lambda: not enlace.is_connected(), 3)
    _conectado(enlace)
    assert sim.holding[m31.MODO_FALLA] == 1
    assert sim.holding[m31.TIEMPO_DESCONEXION] == 5
    assert all(sim.holding[m31.DO_FALLA + i] == 1 for i in range(32))
    assert all(sim.holding[m31.PT_FILTRO + i] == 1 for i in range(6))


@pytest.mark.req("MOD-07")
def test_config_seguridad_en_reconexion_tras_operacion_sale_en_operacion(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.holding[m31.MODO_FALLA] = 0
    sim.registros_ignorados.add(m31.MODO_FALLA)
    enlace.solicitar_handshake()
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    assert _alarmas(eventos)[0] == ("operacion", "TARJETA_CONFIG_SEGURIDAD")


# ---------------------------------------------------------------------------
# MOD-03 · Mapa de datos
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-03")
def test_mapa_de_datos_y_codigos_pt100(sim, crear):
    sim.temperaturas = [1340, m31.PT100_CORTO, m31.PT100_DESCONECTADA, -25,
                        m31.PT100_FALLA_CHIP, m31.PT100_DESHABILITADA]
    sim.corrientes = [4000, 20000, 12000, 3849, 3850, 0, 21000, 5000] + [7777] * 8
    sim.di = [i % 3 == 0 for i in range(16)]
    actualizaciones = []
    enlace = crear(on_update=actualizaciones.append)
    _conectado(enlace)
    st = enlace.get_state()
    assert st["ai"][:8] == [1340, None, None, -25, None, None, None, None]
    # Crudo en µA; el módulo entrega 0 por debajo de 3,85 mA (rango 4-20 mA)
    # tanda 23 (AIN-03): las 16 AI, en ai[8..23]
    assert st["ai"][8:] == [4000, 20000, 12000, 0, 3850, 0, 21000, 5000] + [7777] * 8
    assert st["di"] == [1 if i % 3 == 0 else 0 for i in range(16)] + [0] * 40
    assert st["do"] == [0] * 32
    assert st["port_open"] and st["data_alive"] and st["last_update"] is not None
    assert actualizaciones and set(actualizaciones[-1]) == set(st)
    # Los otros dos códigos de fuera de rango
    sim.temperaturas = [m31.PT100_FUERA_ALTO, m31.PT100_FUERA_BAJO, 0, 1, 2, 3]
    assert esperar(lambda: enlace.get_state()["ai"][:6] == [None, None, 0, 1, 2, 3])


@pytest.mark.req("MOD-03")
def test_codigo_pt100_se_registra_una_vez_por_episodio(sim, crear, caplog):
    sim.temperaturas[0] = m31.PT100_DESCONECTADA
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        enlace = crear()
        _conectado(enlace)
        seq = enlace.secuencia_ultima_ai()
        assert esperar(lambda: enlace.secuencia_ultima_ai() >= seq + 5)
        assert caplog.text.count("PT100 1 sin lectura") == 1
        sim.temperaturas[0] = 1210
        assert esperar(lambda: enlace.get_state()["ai"][0] == 1210)
        sim.temperaturas[0] = m31.PT100_DESCONECTADA
        assert esperar(lambda: enlace.get_state()["ai"][0] is None)
        time.sleep(0.2)
    assert caplog.text.count("PT100 1 sin lectura") == 2


@pytest.mark.req("MOD-03")
def test_secuencias_y_edades(sim, crear):
    enlace = crear()
    _conectado(enlace)
    a1, d1 = enlace.secuencia_ultima_ai(), enlace.secuencia_ultima_di()
    assert a1 >= 1 and d1 >= 1
    assert esperar(lambda: enlace.secuencia_ultima_ai() >= a1 + 3
                   and enlace.secuencia_ultima_di() >= d1 + 3)
    edad, seq = enlace.estado_ultima_ai()
    assert 0 <= edad < 1.0 and seq >= a1 + 3
    assert 0 <= enlace.edad_ultima_di() < 1.0


@pytest.mark.req("MOD-03")
def test_ai_seq_empieza_en_uno_y_no_se_reinicia(sim, crear):
    enlace = crear(arrancar=False)
    vistos = []
    enlace.on_update = lambda d: vistos.append(d["ai_seq"])
    enlace.start()
    _conectado(enlace)
    assert min(v for v in vistos if v) == 1
    antes = enlace.get_state()["ai_seq"]
    enlace.solicitar_handshake()
    _conectado(enlace)
    assert enlace.get_state()["ai_seq"] > antes


# ---------------------------------------------------------------------------
# MOD-08 · Vigilancia del lazo de control
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-08")
def test_sin_tick_con_salida_en_on_no_hay_trafico_y_el_modulo_apaga(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(3, True) is True
        assert esperar(lambda: sim.bobinas[2] and enlace.get_state()["do"][2] == 1)
    # Sin tick: pasado el margen, el enlace corta TODO el tráfico
    time.sleep(enlace.MARGEN_TICK_CONTROL + 0.2)
    antes = sim.contador()
    time.sleep(1.0)       # > tiempo_desconexion_modulo_ds (0,5 s)
    assert sim.contador() == antes
    # El módulo vence su tiempo de desconexión: salidas de falla (apagadas)
    assert sim.bobinas[2] is False
    # ADB-05: el corte ya no pone 0x0C37 en 1 (antes bandera_falla() == 1)
    assert sim.cortes >= 1
    # set_output desde otro hilo respeta la compuerta: sin tráfico
    assert enlace.set_output(4, True) is False
    assert enlace.set_output(3, False) is False
    assert sim.contador() == antes
    # Al volver el tick: conexión verificada de nuevo. ADB-05: sin
    # TARJETA_WATCHDOG por 0x0C37 y sin escribirlo (antes: WATCHDOG en
    # "operacion" y bandera_falla() == 0 tras borrarla).
    with TickLazo(enlace):
        eventos = _eventos_hasta(enlace, lambda e: e.origen == "conectada")
        assert ("operacion", "TARJETA_WATCHDOG") not in _alarmas(eventos)
        assert [e.origen for e in eventos][-1] == "conectada"
        assert enlace.is_connected()
        assert not [w for w in sim.escrituras if w[1] == m31.BANDERA_FALLA]
        assert sim.contador() > antes


@pytest.mark.req("MOD-08")
def test_con_todo_apagado_el_sondeo_sigue_sin_tick(sim, crear):
    enlace = crear()
    _conectado(enlace)
    antes = sim.contador()
    seq = enlace.secuencia_ultima_ai()
    time.sleep(1.0)
    assert sim.contador() > antes + 10
    assert enlace.secuencia_ultima_ai() > seq
    # ADB-05: el corte se mira en sim.cortes (antes bandera_falla() == 0)
    assert enlace.is_connected() and sim.cortes == 0


@pytest.mark.req("MOD-08")
def test_encender_sin_tick_se_rechaza_sin_trafico(sim, crear):
    enlace = crear()
    _conectado(enlace)
    escrituras = len(sim.escrituras)
    assert enlace.set_output(5, True) is False
    assert len(sim.escrituras) == escrituras and sim.bobinas[4] is False


@pytest.mark.req("MOD-08")
@pytest.mark.req("MOD-11")
def test_all_off_se_envia_aunque_no_haya_tick(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(1, True) and enlace.set_output(2, True)
        assert esperar(lambda: sim.bobinas[0] and sim.bobinas[1])
    time.sleep(enlace.MARGEN_TICK_CONTROL + 0.1)
    assert enlace.all_off(1.0) is True
    assert sim.bobinas[:2] == [False, False]
    assert enlace.get_state()["do"] == [0] * 32


@pytest.mark.req("MOD-08")
def test_watchdog_del_modulo_en_operacion(sim, crear):
    # ADB-05 (adenda_tanda_19_banco.md; decisiones_tanda_20.md T20-02):
    # 0x0C37 distinto de 0 en operación ya no da TARJETA_WATCHDOG ni invalida
    # (antes: una TARJETA_WATCHDOG en "operacion" y reconexión); solo se
    # registra su valor crudo.
    enlace = crear()
    _conectado(enlace)
    sim.fijar_0c37(1)       # el simulador lo sigue contando (+1 por segundo)
    assert esperar(lambda: enlace.get_diagnostico()["modulos"]["registro_0c37"] in (1, 2, 3), 3)
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None, 1.5)
    assert ("operacion", "TARJETA_WATCHDOG") not in _alarmas(eventos)
    assert _alarmas(eventos) == []
    assert enlace.is_connected()


# ---------------------------------------------------------------------------
# MOD-09 · Pérdida de comunicación
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-09")
def test_perdida_y_reconexion(sim, crear):
    estados = []
    enlace = crear(on_update=lambda d: estados.append((d["port_open"], d["data_alive"])))
    _conectado(enlace)
    sim.silencio = True
    assert esperar(lambda: not enlace.get_state()["port_open"], 3)
    st = enlace.get_state()
    assert not st["data_alive"] and not enlace.is_connected()
    assert enlace.edad_ultima_di() is None and enlace.edad_ultima_ai() is None
    assert enlace.secuencia_ultima_di() is None and enlace.secuencia_ultima_ai() is None
    assert (False, False) in estados
    diag = enlace.get_diagnostico()
    assert diag["lineas_invalidas_total"] >= 3
    sim.silencio = False
    eventos = _conectado(enlace)
    assert "conectada" in [e.origen for e in eventos]
    assert enlace.get_diagnostico()["lineas_invalidas_consecutivas"] == 0


@pytest.mark.req("MOD-09")
def test_simulador_parado_y_vuelto_a_arrancar(sim, crear):
    enlace = crear()
    _conectado(enlace)
    puerto = sim.puerto
    sim.detener()
    assert esperar(lambda: not enlace.get_state()["port_open"], 3)
    assert esperar(lambda: not enlace.puerto_presente(), 3)
    nuevo = M31Simulado()
    try:
        nuevo.iniciar(puerto)
    except RuntimeError:
        pytest.skip("el sistema no liberó el puerto a tiempo")
    try:
        eventos = _conectado(enlace)
        assert "conectada" in [e.origen for e in eventos]
        assert enlace.puerto_presente()
    finally:
        enlace.stop()
        nuevo.detener()


# ---------------------------------------------------------------------------
# MOD-10 · Diagnóstico en operación
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-10")
def test_expansor_fuera_de_linea_en_operacion(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.holding[m31.MASCARA + 1] = 0b100        # máscara distinta de 0
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None, 4)
    assert _alarmas(eventos) == [("operacion", "TARJETA_EXPANSOR_FUERA_DE_LINEA")]
    assert enlace.expansor_fuera_de_linea() is True
    assert enlace.get_diagnostico()["modulos"]["mascara_expansores"] == 0b100
    time.sleep(1.2)
    assert _alarmas(enlace.tomar_eventos()) == []      # una sola vez por episodio
    sim.holding[m31.MASCARA + 1] = 0
    assert esperar(lambda: enlace.expansor_fuera_de_linea() is False, 3)


@pytest.mark.req("MOD-10")
@pytest.mark.parametrize("codigo,negociacion", [(2, 0), (0, 1)])
def test_modulos_orden_en_operacion_invalida(sim, crear, codigo, negociacion):
    enlace = crear()
    _conectado(enlace)
    sim.orden_incorrecto(codigo=codigo == 2, negociacion=bool(negociacion))
    # La reconexión también falla (paso 2, su motivo pide negociar con
    # Reload) y, por rehacer una conexión en operación, sale en "operacion"
    # (V19-s3-04).
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id == "TARJETA_MODULOS_ORDEN"
                             and "Reload" in e.motivo, 4)
    alarmas = _alarmas(eventos)
    assert alarmas[0] == ("operacion", "TARJETA_MODULOS_ORDEN")
    del_paso_2 = [e for e in eventos if e.alarm_id == "TARJETA_MODULOS_ORDEN"
                  and "Reload" in e.motivo]
    assert del_paso_2 and all(e.origen == "operacion" for e in del_paso_2)
    assert all(origen == "operacion" for origen, _ in alarmas)
    assert not enlace.is_connected()


# ---------------------------------------------------------------------------
# MOD-11 · Salidas
# ---------------------------------------------------------------------------

def _escrituras_bobina(sim, indice):
    return [w for w in sim.escrituras if w[0] == 5 and w[1] == indice]


@pytest.mark.req("MOD-11")
def test_set_output_solo_escribe_en_cambios(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(0, True) is False and enlace.set_output(33, True) is False
        for _ in range(10):
            assert enlace.set_output(7, True) is True
        assert len(_escrituras_bobina(sim, 6)) == 1 and sim.bobinas[6]
        for _ in range(10):
            assert enlace.set_output(7, False) is True
        assert len(_escrituras_bobina(sim, 6)) == 2 and not sim.bobinas[6]
        # Apagar un canal ya apagado por la conexión no escribe
        assert enlace.set_output(8, False) is True
        assert _escrituras_bobina(sim, 7) == []


@pytest.mark.req("MOD-11")
def test_set_output_rechazado_sin_conexion_verificada(sim, crear):
    sim.orden_incorrecto(codigo=True)
    enlace = crear()
    _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    with TickLazo(enlace):
        assert enlace.set_output(1, True) is False
    assert _escrituras_bobina(sim, 0) == []


@pytest.mark.req("MOD-11")
def test_discrepancia_reenvio_unico_y_alarma(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.bobinas_atascadas[4] = False       # la DO5 no sigue la orden
    with TickLazo(enlace):
        assert enlace.set_output(5, True)
        eventos = _eventos_hasta(enlace, lambda e: e.alarm_id == "DISCREPANCIA_SALIDAS", 6)
        assert _alarmas(eventos) == [("operacion", "DISCREPANCIA_SALIDAS")]
        assert len(_escrituras_bobina(sim, 4)) == 2       # orden + reenvío único
        time.sleep(1.5)
        assert _alarmas(enlace.tomar_eventos()) == []      # se informa una vez
        assert len(_escrituras_bobina(sim, 4)) == 2


@pytest.mark.req("MOD-11")
def test_discrepancia_sin_disparo_solo_log(sim, crear, caplog):
    enlace = crear(discrepancia_dispara_fallo=False)
    _conectado(enlace)
    sim.bobinas_atascadas[4] = False
    with caplog.at_level(logging.WARNING, logger="autoclave"), TickLazo(enlace):
        assert enlace.set_output(5, True)
        assert esperar(lambda: "no siguen lo comandado" in caplog.text, 6)
        assert _alarmas(enlace.tomar_eventos()) == []
        assert len(_escrituras_bobina(sim, 4)) == 2


@pytest.mark.req("MOD-11")
def test_discrepancia_que_se_corrige_con_el_reenvio(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.bobinas_atascadas[4] = False
    with TickLazo(enlace):
        assert enlace.set_output(5, True)
        time.sleep(1.0)
        del sim.bobinas_atascadas[4]
        sim.bobinas[4] = False             # la orden original se perdió
        assert esperar(lambda: sim.bobinas[4], 4)     # el reenvío la deja en ON
        time.sleep(1.0)
        assert _alarmas(enlace.tomar_eventos()) == []


@pytest.mark.req("MOD-11")
def test_all_off_confirma_y_falla_si_no_apagan(sim, crear):
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(9, True)
        assert enlace.all_off(1.0) is True
        assert not any(sim.bobinas)
        assert enlace.set_output(9, True)
        sim.bobinas_atascadas[8] = True
        t0 = time.monotonic()
        assert enlace.all_off(0.3) is False
        assert time.monotonic() - t0 < 0.3 + 0.25


@pytest.mark.req("MOD-11")
def test_acceso_concurrente_set_output_mientras_sondea(sim, crear):
    enlace = crear()
    _conectado(enlace)
    errores = []

    def escritor(canales):
        try:
            for i in range(60):
                for ch in canales:
                    enlace.set_output(ch, i % 2 == 0)
        except Exception as e:      # noqa: BLE001
            errores.append(e)

    with TickLazo(enlace):
        hilos = [threading.Thread(target=escritor, args=([1, 2, 3],)),
                 threading.Thread(target=escritor, args=([10, 11],))]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(20)
        assert errores == []
        assert enlace.is_connected()
        # Última orden de cada canal: i=59 -> OFF
        assert esperar(lambda: enlace.get_state()["do"] == [0] * 32)
        assert not any(sim.bobinas)
    assert _alarmas(enlace.tomar_eventos()) == []


@pytest.mark.req("MOD-02")
def test_stop_no_deja_hilos(sim):
    antes = set(threading.enumerate())
    enlace = ModbusLink(config=config_para(sim))
    enlace.start()
    _conectado(enlace)
    enlace.stop()
    assert not enlace.get_state()["port_open"]
    assert esperar(lambda: not any(h.name == "modbus-link" and h.is_alive()
                                   for h in threading.enumerate()), 3)
    assert {h for h in threading.enumerate() if h.is_alive()} - antes == set()


# ---------------------------------------------------------------------------
# Requisitos del ControlLoop (s3)
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-02")
@pytest.mark.req("MOD-10")
def test_solicitar_handshake_es_barato_e_idempotente(sim, crear):
    enlace = crear()
    _conectado(enlace)
    for _ in range(200):          # el lazo puede llamarlo en cada tick
        enlace.solicitar_handshake()
    eventos = _conectado(enlace)
    time.sleep(0.5)
    eventos += enlace.tomar_eventos()
    assert [e.origen for e in eventos].count("conectada") == 1
    # Sin conexión verificada (fallo y reintento en espera) no adelanta el
    # reintento ni genera ráfagas.
    sim.orden_incorrecto(codigo=True)
    enlace.solicitar_handshake()
    _eventos_hasta(enlace, lambda e: e.alarm_id == "TARJETA_MODULOS_ORDEN")
    t0 = time.monotonic()
    vistos = []
    while time.monotonic() - t0 < 1.0:
        enlace.solicitar_handshake()
        vistos += _alarmas(enlace.tomar_eventos())
        time.sleep(0.01)
    # reintento_conexion_s = 0,2 s: unos 5 intentos en 1 s, no cientos
    assert 1 <= len(vistos) <= 7, vistos


@pytest.mark.req("MOD-11")
def test_all_off_sin_argumentos_termina_a_tiempo_sin_respuesta_ni_socket(sim, crear):
    enlace = crear()
    _conectado(enlace)
    sim.silencio = True
    for _ in range(2):            # el apagado del lazo lo llama hasta dos veces
        t0 = time.monotonic()
        assert enlace.all_off() is False
        assert time.monotonic() - t0 <= 1.0 + 0.5
    enlace.stop()
    t0 = time.monotonic()
    assert enlace.all_off() is False and enlace.all_off() is False
    assert time.monotonic() - t0 < 0.2
