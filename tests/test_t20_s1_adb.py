# Tanda 20, s1 · T20-02: adenda del banco (ADB-01 a ADB-05) en ModbusLink,
# contra el simulador M31 (solo 127.0.0.1, puerto libre; sin red real ni
# hardware). Ver docs/mis_plans/adenda_tanda_19_banco.md y
# docs/mis_plans/decisiones_tanda_20.md (decisión 8).

import logging
import time

import pytest

from autoclave.protocols import modbus_link_config as mc
from autoclave.protocols.modbus_link import (
    ModbusLink, texto_a_registros, version_registro, etiqueta_version, _registros_a_texto)
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado, TickLazo, config_para, esperar

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

COMPOSICION_REAL = ["M31-GXAXX0A00-U", "M31-GAXXXA000-U", "M31-GXXAX00A0-U",
                    "M31-GXXAX00A0-U", "M31-GXDXX0600-U"]


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


def _eventos_hasta(enlace, predicado, timeout=6.0):
    acumulados = []

    def _hay():
        acumulados.extend(enlace.tomar_eventos())
        return any(predicado(ev) for ev in acumulados)

    esperar(_hay, timeout)
    return acumulados


def _alarmas(eventos):
    return [(e.origen, e.alarm_id) for e in eventos if e.alarm_id is not None]


def _conectado(enlace, timeout=6.0):
    eventos = _eventos_hasta(enlace, lambda e: e.origen == "conectada", timeout)
    assert enlace.is_connected(), eventos
    return eventos


def _primera_alarma(enlace):
    eventos = _eventos_hasta(enlace, lambda e: e.alarm_id is not None)
    al = [e for e in eventos if e.alarm_id is not None]
    assert al, eventos
    return al[0]


# ---------------------------------------------------------------------------
# ADB-01 · Composición real de 5 esclavos (ID 0 = E/S del principal)
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-01")
def test_composicion_interna_y_del_archivo():
    esperada = ["GXAXX0A00", "GAXXXA000", "GXXAX00A0", "GXXAX00A0", "GXDXX0600"]
    assert list(mc.COMPOSICION_INTERNA["expansiones"]) == esperada
    assert mc.COMPOSICION_INTERNA["principal"] == "XAXX0A00G"
    assert mc.cargar_config().composicion_esperada == {"principal": "XAXX0A00G",
                                                       "expansiones": esperada}


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-01")
@pytest.mark.req("ADB-02")
def test_composicion_real_del_banco_conecta(sim, crear):
    sim.fijar_modelos("M31-XAXX0A00G-U", COMPOSICION_REAL)
    sim.fijar_firmware(0x0103, [0x0100, 0x0100, 0x0100, 0x0100, 0x0000])
    sim.fijar_firmware_texto("9232-0-13")
    lecturas = []
    enlace = crear(arrancar=False)
    original = enlace._leer_holding
    enlace._leer_holding = lambda d, n: (lecturas.append((d, n)), original(d, n))[1]
    enlace.start()
    _conectado(enlace)
    assert enlace.tarjeta()["version"] == "9232-0-13 / v1.0,v1.0,v1.0,v1.0,-"
    # Se leen los esclavos ID 0..5 (el 5 debe ser NONE) y no más
    leidos = {d for d, n in lecturas if n == 8 and d >= m31.MODELO_ESCLAVOS}
    assert leidos == {m31.MODELO_ESCLAVOS + 8 * i for i in range(6)}
    modelos = enlace.get_diagnostico()["modulos"]["modelos"]
    assert modelos["expansiones"] == COMPOSICION_REAL


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-01")
@pytest.mark.parametrize("esclavos,texto", [
    (COMPOSICION_REAL[1:], "falta el esclavo ID 4"),                       # sin el ID 0
    (COMPOSICION_REAL[:4], "falta el esclavo ID 4"),                       # ausente
    (COMPOSICION_REAL + ["M31-GXXAX00A0-U"], "esclavo ID 5 sobrante"),     # sobrante
    (["M31-GXAXX0A00-U", "M31-GAXXXA000-U", "M31-GXDXX0600-U", "M31-GXXAX00A0-U",
      "M31-GXXAX00A0-U"], "esclavo ID 2"),                                 # otro orden
    (["M31-GXAXX0A00-U", "M31-GAXXXA000-U", "M31-GXXAX00A0-U", "M31-GAXXXA000-U",
      "M31-GXDXX0600-U"], "esclavo ID 3"),                                 # distinto
])
def test_composicion_distinta_es_incompatible(sim, crear, esclavos, texto):
    sim.fijar_modelos("M31-XAXX0A00G-U", esclavos)
    enlace = crear()
    al = _primera_alarma(enlace)
    assert (al.origen, al.alarm_id) == ("handshake", "TARJETA_VERSION_INCOMPATIBLE")
    assert texto in al.motivo
    assert not enlace.is_connected()


@pytest.mark.req("T20-02")
@pytest.mark.parametrize("codigo,negociacion", [(True, False), (False, True)])
def test_orden_o_negociacion_da_modulos_orden(sim, crear, codigo, negociacion):
    sim.orden_incorrecto(codigo=codigo, negociacion=negociacion)
    enlace = crear()
    al = _primera_alarma(enlace)
    assert al.alarm_id == "TARJETA_MODULOS_ORDEN"


# ---------------------------------------------------------------------------
# ADB-02 corregido (FW-INF, 28-oct): versión «vX.Y» en registros y
# comprobación de firmware solo informativa
# ---------------------------------------------------------------------------

@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_version_registro():
    # Manual del principal, tabla 4.10: byte alto antes del punto, bajo después
    assert version_registro(0x0103) == (1, 3)
    assert version_registro(0x0100) == (1, 0)
    assert version_registro(0) is None and version_registro(None) is None
    assert etiqueta_version((1, 3)) == "v1.3" and etiqueta_version(None) == "-"
    assert _registros_a_texto(texto_a_registros("9232-0-13", 8)) == "9232-0-13"


@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_valores_del_equipo_real_conectan(sim, crear):
    # Lo que leyó la alpha.4 en el equipo de pruebas el 28-oct, que antes
    # daba TARJETA_VERSION_INCOMPATIBLE «ilegible».
    sim.fijar_firmware(0x0103, [0x0100, 0x0100, 0x0100, 0x0100, 0x0000])
    enlace = crear()
    _conectado(enlace)
    assert enlace.tarjeta()["version"] == "9232-0-13 / v1.0,v1.0,v1.0,v1.0,-"
    fw = enlace.get_diagnostico()["modulos"]["firmware"]
    assert fw == {"principal": "9232-0-13", "registro_principal": "v1.3",
                  "expansiones": ["v1.0", "v1.0", "v1.0", "v1.0", "-"],
                  "crudo_principal": 0x0103,
                  "crudo_expansiones": [0x0100, 0x0100, 0x0100, 0x0100, 0x0000],
                  "texto_principal": "9232-0-13", "compatible": None}


@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_esclavo_mas_nuevo_solo_avisa(sim, crear, caplog):
    sim.fijar_firmware(0x0103, [0x0100, 0x0102, 0x0105, 0x0100, 0x0100])
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        enlace = crear()
        _conectado(enlace)
    assert "solo informativo" in caplog.text
    assert "TARJETA_VERSION_INCOMPATIBLE" not in caplog.text
    assert enlace.get_diagnostico()["modulos"]["firmware"]["compatible"] is False


@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_firmware_compatible(sim, crear):
    sim.fijar_firmware(0x0103, [0x0100, 0x0102, 0x0102, 0x0102, 0x0100])
    enlace = crear()
    _conectado(enlace)
    assert enlace.get_diagnostico()["modulos"]["firmware"]["compatible"] is True


@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_sin_texto_usa_el_registro(sim, crear):
    sim.fijar_firmware_texto("")
    enlace = crear()
    _conectado(enlace)
    assert enlace.tarjeta()["version"] == "v1.3 / v1.0,v1.0,v1.0,v1.0,-"


@pytest.mark.req("ADB-02")
@pytest.mark.req("FW-INF")
def test_firmware_en_cero_no_bloquea(sim, crear):
    # Antes «ilegible» -> TARJETA_VERSION_INCOMPATIBLE; ahora solo se informa.
    sim.fijar_firmware(0x0000, [0, 0, 0, 0, 0])
    enlace = crear()
    _conectado(enlace)
    assert enlace.tarjeta()["version"] == "9232-0-13 / -,-,-,-,-"


# ---------------------------------------------------------------------------
# ADB-03 · ID del equipo = MAC del principal
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-03")
def test_mac_del_banco_como_id(sim, crear):
    sim.fijar_mac("005404849DB1")
    enlace = crear()
    _conectado(enlace)
    assert enlace.tarjeta()["id"] == "005404849DB1"


# ---------------------------------------------------------------------------
# ADB-05 · 0x0C37 solo se registra
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-05")
def test_0c37_contador_no_impide_ni_invalida_y_no_se_escribe(sim, crear, caplog):
    sim.fijar_0c37(100)
    with caplog.at_level(logging.INFO, logger="autoclave"):
        enlace = crear()
        eventos = _conectado(enlace)
        assert "0x0C37 = 10" in caplog.text
    assert _alarmas(eventos) == []
    sim.fijar_0c37(105)
    assert esperar(lambda: enlace.get_diagnostico()["modulos"]["registro_0c37"] in
                   (105, 106, 107), 3)
    time.sleep(1.2)
    assert _alarmas(enlace.tomar_eventos()) == []
    assert enlace.is_connected()
    # V20-s1-07 (ADB-05: 0x0C37 no es bandera): falla_salidas queda en None
    # (clave conservada por la API) y el valor crudo solo en registro_0c37.
    modulos = enlace.get_diagnostico()["modulos"]
    assert modulos["falla_salidas"] is None
    assert modulos["registro_0c37"] >= 105
    assert not [w for w in sim.escrituras if w[1] == m31.BANDERA_FALLA]


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-05")
def test_0c37_en_operacion_no_inunda_el_log(sim, crear, caplog):
    enlace = crear()
    _conectado(enlace)
    with caplog.at_level(logging.INFO, logger="autoclave"):
        time.sleep(3.3)     # el contador cambia cada segundo
    assert caplog.text.count("0x0C37") <= 1


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-05")
def test_sin_codigo_de_suspension():
    assert not hasattr(ModbusLink(config=config_para(M31Simulado())), "_tras_suspension")


# ---------------------------------------------------------------------------
# ADB-04 · Reinicio tras escribir la configuración (decisión 8)
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_configuracion_distinta_escribe_reinicia_y_relee(sim, crear):
    n_antes = len(sim.escrituras)
    enlace = crear()
    _conectado(enlace)
    assert sim.reinicios == 1
    assert enlace.get_diagnostico()["modulos"]["reinicios_modulo"] == 1
    nuevas = sim.escrituras[n_antes:]
    i_reinicio = nuevas.index((6, m31.REINICIO, [m31.CLAVE_REINICIO]))
    # Antes del reinicio: la configuración escrita y el 0F de apagado
    assert (16, m31.MODO_FALLA, [1]) in nuevas[:i_reinicio]
    assert (15, 0, [False] * 32) in nuevas[:i_reinicio]
    # Después del reinicio no se vuelve a escribir la configuración
    despues = nuevas[i_reinicio + 1:]
    assert not [w for w in despues if w[0] == 16]
    assert sim.holding[m31.MODO_FALLA] == 1 and sim.holding[m31.TIEMPO_DESCONEXION] == 5
    # Solo reinicia una vez
    time.sleep(0.5)
    assert sim.reinicios == 1 and enlace.is_connected()


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_configuracion_igual_no_reinicia(sim, crear):
    sim.precargar_configuracion()
    enlace = crear()
    _conectado(enlace)
    assert sim.reinicios == 0
    assert not [w for w in sim.escrituras if w[0] in (6, 16)]
    # Una reconexión con la configuración ya escrita tampoco reinicia
    enlace.solicitar_handshake()
    _conectado(enlace)
    assert sim.reinicios == 0


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_config_que_no_persiste_tras_el_reinicio_da_config_seguridad(sim, crear):
    sim.config_no_persiste = True
    enlace = crear()
    al = _primera_alarma(enlace)
    assert (al.origen, al.alarm_id) == ("handshake", "TARJETA_CONFIG_SEGURIDAD")
    assert "no quedó tras el reinicio" in al.motivo
    assert not enlace.is_connected() and enlace.set_output(1, True) is False
    # V20-s1-03: tras varios reintentos (reintento_conexion_s = 0,2 s) el
    # número de reinicios queda acotado en MAX_REINICIOS_SIN_VERIFICAR (2) y
    # los intentos siguientes fallan sin escribir ni reiniciar.
    eventos = _eventos_hasta(
        enlace, lambda e: e.alarm_id == "TARJETA_CONFIG_SEGURIDAD"
        and "no se vuelve a escribir ni a reiniciar" in e.motivo, timeout=10.0)
    assert any("no se vuelve a escribir" in e.motivo for e in eventos)
    n_escrituras = len(sim.escrituras)
    time.sleep(1.5)
    assert 1 <= sim.reinicios <= 2
    assert len([w for w in sim.escrituras if w[1] == m31.REINICIO]) <= 2
    # Ya no se escribe nada (ni configuración ni orden de reinicio), solo el
    # 0F de apagado tras cada conexión fallida
    assert not [w for w in sim.escrituras[n_escrituras:] if w[0] in (6, 16)]
    assert not enlace.is_connected()


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_set_output_rechazado_durante_el_reinicio(sim, crear):
    sim.tiempo_reinicio_s = 0.6
    enlace = crear(espera_reinicio_s=0.3)
    assert esperar(lambda: sim.reinicios == 1, 5)
    with TickLazo(enlace):
        assert enlace.set_output(1, True) is False
        _conectado(enlace)
    assert not [w for w in sim.escrituras if w[0] == 5]


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_modulo_que_no_vuelve_da_sin_trama_valida(sim, crear):
    sim.tiempo_reinicio_s = 30.0
    enlace = crear(presupuesto_reinicio_s=0.8)
    al = _primera_alarma(enlace)
    assert al.alarm_id == "TARJETA_SIN_TRAMA_VALIDA" and "tras el reinicio" in al.motivo


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_stop_durante_la_espera_del_reinicio_no_bloquea(sim):
    enlace = ModbusLink(config=config_para(sim, espera_reinicio_s=20.0))
    enlace.start()
    try:
        assert esperar(lambda: sim.reinicios == 1, 5)
    finally:
        t0 = time.monotonic()
        enlace.stop()
        assert time.monotonic() - t0 < 2.5


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_corte_activo_tras_el_reinicio(sim, crear):
    # Modelo de ADB-04: el corte usa la configuración vigente al último
    # reinicio. Con el reinicio del enlace, el corte funciona.
    sim.config_activa_tras_reinicio = True
    enlace = crear()
    _conectado(enlace)
    with TickLazo(enlace):
        assert enlace.set_output(3, True)
        assert esperar(lambda: sim.bobinas[2])
    assert esperar(lambda: sim.cortes >= 1 and sim.bobinas[2] is False, 3)


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_claves_nuevas_de_configuracion():
    d = mc.ModbusLinkConfig()
    assert d.espera_reinicio_s == 5.0 and d.presupuesto_reinicio_s == 30.0
    cfg = mc.config_desde_dict({"espera_reinicio_s": 2, "presupuesto_reinicio_s": 10})
    assert cfg.espera_reinicio_s == 2.0 and cfg.presupuesto_reinicio_s == 10.0
    cfg = mc.config_desde_dict({"espera_reinicio_s": -1, "presupuesto_reinicio_s": 500})
    assert cfg.espera_reinicio_s == 5.0 and cfg.presupuesto_reinicio_s == 30.0
