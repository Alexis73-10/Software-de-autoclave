"""E6 — Fase B recortada del enlace serial, lado PC (planeacion_firmware_1_5.md §5).

Handshake de conexión (§4.6 del plan de protocolo), parseo de BOOT/VER/ST/WD,
órdenes de salida bloqueadas hasta completar el handshake y latido atado al
tick del lazo de control (FW-D6). Todo con el serial doble (sin hardware)."""

import threading
import time

import pytest

from autoclave.protocols.serial_link import SerialLink
from autoclave.protocols.serial_link_config import SerialLinkConfig
from tests.serial_doble import (
    AI_OK, DI_OK, ID_TARJETA, PuertoDoble, TarjetaSimulada, esperar, linea, st,
)


def _entorno(**cfg):
    """Enlace con el puerto doble ya "abierto", la tarjeta simulada
    publicando y el hilo lector corriendo (el handshake espera respuestas)."""
    base = dict(handshake_presupuesto_s=1.5, all_off_timeout_s=0.2, all_off_intentos=3)
    base.update(cfg)
    link = SerialLink(config=SerialLinkConfig(**base))
    puerto = PuertoDoble()
    tarjeta = TarjetaSimulada(puerto)
    link._rx_buf = bytearray()
    link.serial = puerto
    link.data["port_open"] = True
    link.running = True
    lector = threading.Thread(target=link._read_loop, daemon=True)
    lector.start()
    return link, puerto, tarjeta, lector


@pytest.fixture
def entorno():
    creados = []

    def crear(arrancar=True, **cfg):
        link, puerto, tarjeta, lector = _entorno(**cfg)
        if arrancar:
            tarjeta.arrancar()
        creados.append((link, puerto, tarjeta, lector))
        return link, puerto, tarjeta

    yield crear
    for link, puerto, tarjeta, lector in creados:
        tarjeta.detener()
        link.running = False
        puerto.close()
        lector.join(1)


def _ids(link):
    return [e.alarm_id for e in link.tomar_eventos()]


# ---------------------------------------------------------------------------
# Handshake completo
# ---------------------------------------------------------------------------

def test_handshake_completo_conecta_y_guarda_version_e_id(entorno):
    link, puerto, _ = entorno()
    assert link.is_connected() is False

    assert link._ejecutar_handshake() is True

    assert link.is_connected() is True
    assert link.tarjeta() == {"version": "1.0.0", "protocolo": 2, "id": ID_TARJETA}
    cmds = puerto.comandos()
    # TMG-02: ALL_OFF de mejor esfuerzo antes de los pasos del §4.6
    assert cmds[:4] == ["ALL_OFF", "VER", "HB", "ALL_OFF"]


def test_handshake_ok_emite_evento_de_conexion_y_llama_al_conectar(entorno):
    link, _, _ = entorno()
    recibidos = []
    link.al_conectar = recibidos.append
    link._ejecutar_handshake()
    assert recibidos == [{"version": "1.0.0", "protocolo": 2, "id": ID_TARJETA}]
    eventos = link.tomar_eventos()
    assert [e.origen for e in eventos] == ["conectada"]


def test_sin_handshake_is_connected_es_false_aunque_lleguen_tramas_validas(entorno):
    link, _, tarjeta = entorno()
    assert esperar(lambda: link.data["data_alive"] is True)
    assert link.is_connected() is False


# ---------------------------------------------------------------------------
# Fallos del handshake: cada uno con su alarma
# ---------------------------------------------------------------------------

def test_sin_trama_valida(entorno):
    link, _, tarjeta = entorno(arrancar=False)
    tarjeta.mudo = True
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_SIN_TRAMA_VALIDA"]
    assert link.is_connected() is False


def test_firmware_v2_sin_crc_se_rechaza_como_version_incompatible(entorno):
    link, _, tarjeta = entorno(arrancar=False)
    tarjeta.sin_crc = True
    tarjeta.arrancar()
    assert link._ejecutar_handshake() is False
    eventos = link.tomar_eventos()
    assert [e.alarm_id for e in eventos] == ["TARJETA_VERSION_INCOMPATIBLE"]
    assert "CRC" in eventos[0].motivo


def test_protocolo_distinto_de_2(entorno):
    link, _, tarjeta = entorno()
    tarjeta.protocolo = 1
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_VERSION_INCOMPATIBLE"]


def test_sin_respuesta_a_ver(entorno):
    link, _, tarjeta = entorno()
    tarjeta.responde_ver = False
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_VERSION_INCOMPATIBLE"]


def test_sin_ack_al_hb(entorno):
    link, _, tarjeta = entorno()
    tarjeta.responde_ack = False
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_SIN_ACK"]


def test_all_off_sin_confirmar_tras_tres_intentos(entorno):
    link, puerto, tarjeta = entorno()
    tarjeta.responde_all_off = False
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_ALL_OFF_SIN_CONFIRMAR"]
    # 1 de mejor esfuerzo (TMG-02) + 3 intentos del paso 5
    assert puerto.comandos().count("ALL_OFF") == 4


def test_salidas_no_apagadas(entorno):
    link, _, tarjeta = entorno()
    tarjeta.do_forzado = [1] + [0] * 31
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_SALIDAS_NO_APAGADAS"]
    assert link.is_connected() is False


def test_expansor_fuera_de_linea(entorno):
    link, _, tarjeta = entorno()
    tarjeta.pcf_ok = "3B"
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_EXPANSOR_FUERA_DE_LINEA"]


def test_sync_en_cero_tras_all_off_no_completa(entorno):
    link, _, tarjeta = entorno()
    tarjeta.sync_forzado = 0
    assert link._ejecutar_handshake() is False
    assert _ids(link) == ["TARJETA_ALL_OFF_SIN_CONFIRMAR"]


# ---------------------------------------------------------------------------
# Órdenes de salida bloqueadas sin handshake
# ---------------------------------------------------------------------------

def test_set_output_no_envia_sin_handshake(entorno):
    link, puerto, _ = entorno()
    assert link.set_output(4, True) is False
    assert not any(c.startswith("SET") for c in puerto.comandos())


def test_all_off_no_envia_sin_handshake(entorno):
    link, puerto, _ = entorno()
    assert link.all_off(timeout=0.05) is False
    assert "ALL_OFF" not in puerto.comandos()


def test_set_output_envia_tras_handshake(entorno):
    link, puerto, tarjeta = entorno()
    link._ejecutar_handshake()
    assert link.set_output(4, True) is True
    assert puerto.comandos()[-1] == "SET DO4 ON"


# ---------------------------------------------------------------------------
# Reconexión: el handshake se repite
# ---------------------------------------------------------------------------

def test_desconexion_invalida_el_handshake(entorno):
    link, _, _ = entorno()
    link._ejecutar_handshake()
    link._disconnect()
    assert link.handshake_completo is False


def test_watchdog_tick_ejecuta_handshake_tras_conectar(entorno, monkeypatch):
    link, _, _ = entorno()
    link._handshake_pendiente = True
    link._watchdog_tick(0.0, None, None)
    assert link.is_connected() is True


def test_handshake_fallido_se_reintenta_tras_el_intervalo(entorno):
    link, _, tarjeta = entorno(reintento_handshake_s=3.0)
    tarjeta.responde_ack = False
    link._handshake_pendiente = True
    t0 = time.monotonic()
    link._watchdog_tick(t0, None, None)
    assert link.is_connected() is False
    link.tomar_eventos()

    tarjeta.responde_ack = True
    link._watchdog_tick(t0 + 1.0, None, None)        # antes del reintento: no intenta
    assert link.is_connected() is False
    link._watchdog_tick(t0 + 3.1, None, None)
    assert link.is_connected() is True


# ---------------------------------------------------------------------------
# Latido atado al tick del lazo de control (FW-D6)
# ---------------------------------------------------------------------------

def _conectado_sin_hilos():
    link = SerialLink(config=SerialLinkConfig())
    puerto = PuertoDoble()
    link._rx_buf = bytearray()
    link.serial = puerto
    link.data["port_open"] = True
    link._handshake_ok = True
    link._handshake_pendiente = False
    link._ultima_valida_mono = 0.0
    return link, puerto


def test_hb_se_envia_si_el_lazo_hizo_tick_reciente(monkeypatch):
    link, puerto = _conectado_sin_hilos()
    monkeypatch.setattr("autoclave.protocols.serial_link.time.monotonic", lambda: 10.0)
    link.marcar_tick_control()
    link._ultima_valida_mono = 10.0
    link._watchdog_tick(10.5, None, None)
    assert puerto.comandos() == ["HB"]


def test_hb_se_detiene_si_el_lazo_no_hace_tick(monkeypatch):
    link, puerto = _conectado_sin_hilos()
    monkeypatch.setattr("autoclave.protocols.serial_link.time.monotonic", lambda: 10.0)
    link.marcar_tick_control()
    link._ultima_valida_mono = 11.6
    link._watchdog_tick(11.6, None, None)          # 1,6 s sin tick > 1,5 s
    assert puerto.comandos() == []


def test_hb_sin_ningun_tick_no_se_envia():
    link, puerto = _conectado_sin_hilos()
    link._watchdog_tick(0.5, None, None)
    assert puerto.comandos() == []


def test_hb_no_se_envia_sin_handshake(monkeypatch):
    link, puerto = _conectado_sin_hilos()
    link._handshake_ok = False
    link._handshake_pendiente = False
    link._proximo_handshake = 1e9
    monkeypatch.setattr("autoclave.protocols.serial_link.time.monotonic", lambda: 10.0)
    link.marcar_tick_control()
    link._ultima_valida_mono = 10.0
    link._watchdog_tick(10.2, None, None)
    assert "HB" not in puerto.comandos()


# ---------------------------------------------------------------------------
# Parseo de BOOT / VER / ST / WD
# ---------------------------------------------------------------------------

def _link_parser():
    link = SerialLink(config=SerialLinkConfig())
    link._rx_buf = bytearray()
    link.serial = PuertoDoble()
    link.data["port_open"] = True
    return link


def test_st_valido_se_parsea_y_expone_en_diagnostico():
    link = _link_parser()
    link._alimentar(linea(st(pcf_ok="3F", disc_do="00000001", ai_inv="0002",
                             crc_rx_err=5, i2c_err=7, wd=0, uptime_s=123, sync=1)))
    diag = link.get_diagnostico()
    assert diag["tarjeta_st"] == {
        "pcf_ok": "3F", "disc_do": "00000001", "ai_inv": "0002",
        "crc_rx_err": 5, "i2c_err": 7, "wd": 0, "uptime_s": 123, "sync": 1,
    }
    assert diag["lineas_invalidas_total"] == 0


@pytest.mark.parametrize("payload", [
    "ST:2,3F,00000000,0000,0,0,0,10",              # sin sync (formato del plan v2)
    "ST:2,3G,00000000,0000,0,0,0,10,1",            # hex inválido
    "ST:2,3f,00000000,0000,0,0,0,10,1",            # minúscula
    "ST:2,3F,0000000,0000,0,0,0,10,1",             # ancho de disc_do
    "ST:2,3F,00000000,0000,0,0,2,10,1",            # wd fuera de {0,1}
    "ST:2,3F,00000000,0000,0,0,0,10,2",            # sync fuera de {0,1}
    "ST:2,3F,00000000,0000,-1,0,0,10,1",           # contador negativo
    "ST:2,3F,00000000,0000,0,0,0,x,1",             # uptime no numérico
])
def test_st_malformado_es_invalido(payload):
    link = _link_parser()
    link._alimentar(linea(payload))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


@pytest.mark.parametrize("payload", [
    "BOOT 1.0.0 2 A1B2C3D4E5F6",
    "VER 1.0.0 2 A1B2C3D4E5F6",
    "WD: ALL_OFF",
])
def test_lineas_nuevas_del_protocolo_son_validas(payload):
    link = _link_parser()
    link._alimentar(linea(payload))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 0


@pytest.mark.parametrize("payload", [
    "BOOT 1.0.0",                                   # faltan campos
    "VER 1.0.0 2 a1b2c3d4e5f6",                     # id en minúscula
    "VER 1.0.0 x A1B2C3D4E5F6",                     # protocolo no numérico
    "BOOT 1.0.0 2 A1B2C3",                          # id corto
])
def test_boot_ver_malformados_son_invalidos(payload):
    link = _link_parser()
    link._alimentar(linea(payload))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_ok_do_se_acepta_como_linea_valida():
    link = _link_parser()
    link._alimentar(linea("OK DO4 ON"))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 0


# ---------------------------------------------------------------------------
# Eventos en operación (tras el handshake)
# ---------------------------------------------------------------------------

def _conectado(entorno):
    link, puerto, tarjeta = entorno()
    assert link._ejecutar_handshake() is True
    link.tomar_eventos()
    return link, puerto, tarjeta


def test_wd_tras_handshake_genera_evento_y_pide_nuevo_handshake(entorno):
    link, _, tarjeta = _conectado(entorno)
    tarjeta.disparar_watchdog()
    assert esperar(lambda: link.handshake_completo is False)
    assert link.is_connected() is False
    assert link._handshake_pendiente is True
    assert _ids(link) == ["TARJETA_WATCHDOG"]


def test_boot_inesperado_genera_evento_y_pide_nuevo_handshake(entorno):
    link, _, tarjeta = _conectado(entorno)
    tarjeta.boot()
    assert esperar(lambda: link.handshake_completo is False)
    assert _ids(link) == ["TARJETA_REINICIO"]


def test_uptime_que_retrocede_es_reinicio(entorno):
    link, _, tarjeta = _conectado(entorno)
    tarjeta.uptime_s = 500
    assert esperar(lambda: (link.get_diagnostico().get("tarjeta_st") or {}).get("uptime_s") == 500)
    tarjeta.uptime_s = 3
    assert esperar(lambda: link.handshake_completo is False)
    assert "TARJETA_REINICIO" in _ids(link)


def test_pcf_ok_distinto_sostenido_dos_tramas_genera_evento_sin_cortar(entorno):
    link, _, tarjeta = _conectado(entorno)
    tarjeta.detener()
    tarjeta.pcf_ok = "3E"
    tarjeta.publicar()
    assert esperar(lambda: link.get_diagnostico()["tarjeta_st"]["pcf_ok"] == "3E")
    assert _ids(link) == []                         # una trama: aún no
    tarjeta.publicar()
    assert esperar(lambda: "TARJETA_EXPANSOR_FUERA_DE_LINEA" in _ids(link))
    # la decisión (FALLO o handshake) es del lazo; el enlace sigue conectado
    assert link.is_connected() is True


def test_reinicio_durante_handshake_no_genera_evento_de_operacion(entorno):
    link, _, tarjeta = entorno()
    tarjeta.boot()
    assert link._ejecutar_handshake() is True
    assert [e.origen for e in link.tomar_eventos()] == ["conectada"]


# ---------------------------------------------------------------------------
# Comparación comandado vs DO reportado (plan de protocolo §6.5)
# ---------------------------------------------------------------------------

def _do(*encendidas):
    bits = ["0"] * 32
    for n in encendidas:
        bits[n - 1] = "1"
    return "DO:" + "".join(bits)


def _link_comparacion(monkeypatch, reloj):
    link = _link_parser()
    link._handshake_ok = True
    monkeypatch.setattr("autoclave.protocols.serial_link.time.monotonic", lambda: reloj[0])
    return link


def test_discrepancia_sostenida_reenvia_una_vez_y_luego_genera_evento(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 101.1                                 # pasado 1 s desde la orden
    link._alimentar(linea(_do()))
    assert link.serial.comandos().count("SET DO4 ON") == 1
    link._alimentar(linea(_do()))                    # 2 tramas: reenvío único
    assert link.serial.comandos().count("SET DO4 ON") == 2
    assert _ids(link) == []

    reloj[0] = 102.2
    link._alimentar(linea(_do()))
    link._alimentar(linea(_do()))
    assert _ids(link) == ["DISCREPANCIA_SALIDAS"]
    assert link.serial.comandos().count("SET DO4 ON") == 2


def test_canal_comandado_hace_menos_de_un_segundo_se_excluye(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 100.5
    for _ in range(4):
        link._alimentar(linea(_do()))
    assert link.serial.comandos().count("SET DO4 ON") == 1
    assert _ids(link) == []


def test_sin_discrepancia_no_reenvia(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 102.0
    for _ in range(4):
        link._alimentar(linea(_do(4)))
    assert link.serial.comandos().count("SET DO4 ON") == 1
    assert _ids(link) == []


def test_canal_no_comandado_desde_el_handshake_no_se_compara(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    reloj[0] = 105.0
    for _ in range(4):
        link._alimentar(linea(_do(7)))
    assert _ids(link) == []


def test_discrepancia_que_se_corrige_tras_el_reenvio_no_genera_evento(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 101.5
    link._alimentar(linea(_do()))
    link._alimentar(linea(_do()))                    # reenvío
    reloj[0] = 102.6
    for _ in range(4):
        link._alimentar(linea(_do(4)))
    assert _ids(link) == []


def test_comparacion_solo_con_handshake_completo(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    link._handshake_ok = False
    reloj[0] = 105.0
    for _ in range(4):
        link._alimentar(linea(_do()))
    assert _ids(link) == []


# ---------------------------------------------------------------------------
# Ruido en la línea sin matar el hilo lector, con el handshake ya hecho
# ---------------------------------------------------------------------------

def test_ruido_tras_handshake_no_mata_el_lector_ni_corta(entorno):
    link, puerto, _ = _conectado(entorno)
    puerto.inyectar(b"basura sin crc\n")
    puerto.inyectar(linea("ST:2,ZZ,0,0,0,0,0,0,1"))
    assert esperar(lambda: link.get_diagnostico()["lineas_invalidas_total"] >= 2)
    assert link.is_connected() is True


def test_reenviar_el_mismo_estado_no_renueva_la_exclusion(monkeypatch):
    # Las puertas reafirman su salida en cada tick: el canal debe compararse
    # igual (la exclusión de 1 s cuenta desde el último cambio de estado).
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(22, True)
    for t in (100.5, 101.0, 101.5, 102.0):
        reloj[0] = t
        link.set_output(22, True)
        link._alimentar(linea(_do()))
    assert link.serial.comandos().count("SET DO22 ON") >= 6     # 5 órdenes + reenvío


def test_cambio_de_estado_si_renueva_la_exclusion(monkeypatch):
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 101.5
    link.set_output(4, False)
    for _ in range(4):
        link._alimentar(linea(_do(4)))      # aún reporta ON: cambio reciente, se excluye
    assert link.serial.comandos().count("SET DO4 OFF") == 1


# ---------------------------------------------------------------------------
# TMG-02 / TMG-03 (revisión de temporización de la tanda 2026-10-14)
# ---------------------------------------------------------------------------

def test_handshake_que_falla_apaga_antes_las_salidas(entorno):
    # TMG-02: tarjeta todavía SINCRONIZADA con una salida en ON; el handshake
    # falla en VER. Sin el ALL_OFF previo, VER/HB alimentarían su watchdog
    # y la salida quedaría encendida sin límite.
    link, puerto, tarjeta = entorno()
    tarjeta.sync = 1
    tarjeta.do = [1] + [0] * 31
    tarjeta.responde_ver = False
    assert link._ejecutar_handshake() is False
    assert puerto.comandos()[0] == "ALL_OFF"
    assert tarjeta.do == [0] * 32


def test_reenvio_usa_el_estado_comandado_vigente(monkeypatch):
    # TMG-03: si el lazo comanda otro valor mientras el lector prepara el
    # reenvío, sale el valor nuevo (nunca uno rezagado que invierta la salida).
    reloj = [100.0]
    link = _link_comparacion(monkeypatch, reloj)
    link.set_output(4, True)
    reloj[0] = 101.1
    import autoclave.protocols.serial_link as modulo
    original = modulo.logger.warning

    def warning(msg, *args):
        if "reenvío único" in msg:
            link.set_output(4, False)          # orden del lazo "en medio"
        return original(msg, *args)

    monkeypatch.setattr(modulo.logger, "warning", warning)
    link._alimentar(linea(_do()))
    link._alimentar(linea(_do()))
    cmds = [c for c in link.serial.comandos() if c.startswith("SET DO4")]
    assert cmds == ["SET DO4 ON", "SET DO4 OFF", "SET DO4 OFF"]


def test_st_en_operacion_no_se_acumulan(entorno):
    # SAF-02: tras el handshake, las ST de operación no crecen _hs_st
    link, _, _ = entorno()
    assert link._ejecutar_handshake() is True
    time.sleep(0.6)
    assert link._hs_st == []
    assert link._hs_esperando_estado is False


def test_expansor_fuera_de_linea_tras_reportarse(monkeypatch):
    link = _link_parser()
    link._handshake_ok = True
    for _ in range(link.config.tramas_discrepancia):
        link._alimentar(linea(st(pcf_ok="3B")))
    assert link.expansor_fuera_de_linea() is True
    link._alimentar(linea(st()))
    assert link.expansor_fuera_de_linea() is False
