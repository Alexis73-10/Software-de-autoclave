"""Paso A2 — hilo lector endurecido del enlace serial (PC-02, PC-04).

Ver docs/mis_plans/planeacion_protocolo_serial_esp32.md, secciones 4.4 y 6."""

import json
import threading
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from autoclave.protocols import serial_link as sl_mod
from autoclave.protocols.serial_link import SerialLink
from autoclave.protocols.serial_link_config import (
    SerialLinkConfig, cargar_config, config_desde_dict,
)
from tests.serial_doble import AI_OK, DI_OK, DO_OK, PuertoDoble, esperar, linea


def _link(**cfg):
    link = SerialLink(config=SerialLinkConfig(**cfg))
    puerto = PuertoDoble()
    link._rx_buf = bytearray()
    link.serial = puerto
    link.data["port_open"] = True
    return link, puerto


# ---------------------------------------------------------------------------
# Parser con CRC
# ---------------------------------------------------------------------------

def test_linea_valida_actualiza_datos_y_vida():
    link, _ = _link()
    link._alimentar(linea(AI_OK) + linea("DI:" + "1" + "0" * 55) + linea("DO:" + "0" * 31 + "1"))

    st = link.get_state()
    assert st["ai"] == [100 + i for i in range(16)]
    assert st["di"][0] == 1
    assert st["do"][31] == 1
    assert st["data_alive"] is True
    assert isinstance(st["last_update"], datetime)
    assert link.get_diagnostico()["lineas_invalidas_total"] == 0


def test_linea_con_crc_erroneo_se_descarta_y_cuenta():
    link, _ = _link()
    buena = linea(AI_OK)
    mala = buena[:-3] + (b"0" if buena[-3:-2] != b"0" else b"1") + buena[-2:]
    link._alimentar(mala)

    assert link.get_state()["ai"] == [0] * 16
    assert link.get_state()["data_alive"] is False
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_linea_sin_crc_formato_v2_es_invalida():
    link, _ = _link()
    link._alimentar(("AI:" + ",".join(["1"] * 16) + "\n").encode())
    assert link.get_state()["data_alive"] is False
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_ai_no_numerico_con_crc_valido_no_mata_ni_actualiza():
    link, _ = _link()
    link._alimentar(linea(AI_OK))
    link._alimentar(linea("AI:" + ",".join(["12"] * 15 + ["xx"])))

    assert link.get_state()["ai"] == [100 + i for i in range(16)]  # sin cambio parcial
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_di_con_longitud_o_caracteres_invalidos():
    link, _ = _link()
    link._alimentar(linea("DI:" + "0" * 55))
    link._alimentar(linea("DI:" + "2" * 56))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 2


def test_tipo_desconocido_con_crc_valido_es_invalido():
    link, _ = _link()
    link._alimentar(linea("XYZ:1"))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_bytes_no_ascii_son_invalidos():
    link, _ = _link()
    link._alimentar(b"AI:\xff\xfe*0000\n")
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


def test_linea_partida_en_varios_fragmentos_se_reensambla():
    link, _ = _link()
    datos = linea(AI_OK)
    for i in range(len(datos)):
        link._alimentar(datos[i:i + 1])
    assert link.get_state()["ai"][0] == 100
    assert link.get_diagnostico()["lineas_invalidas_total"] == 0


def test_cr_final_se_tolera():
    link, _ = _link()
    link._alimentar(agregar := linea(DO_OK)[:-1] + b"\r\n")
    assert agregar.endswith(b"\r\n")
    assert link.get_diagnostico()["lineas_invalidas_total"] == 0


def test_linea_larga_sin_salto_se_descarta_y_cuenta_una_vez():
    link, _ = _link(longitud_max_linea=80)
    link._alimentar(b"A" * 120)
    link._alimentar(b"B" * 120)
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1
    assert len(link._rx_buf) == 0

    # El resto de la línea larga hasta el \n se descarta; la siguiente vale.
    link._alimentar(b"CCC\n" + linea(AI_OK))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1
    assert link.get_state()["ai"][0] == 100


def test_linea_valida_resetea_consecutivas():
    link, _ = _link()
    link._alimentar(b"basura\n" * 3)
    assert link.get_diagnostico()["lineas_invalidas_consecutivas"] == 3
    link._alimentar(linea(DO_OK))
    assert link.get_diagnostico()["lineas_invalidas_consecutivas"] == 0
    assert link.get_diagnostico()["lineas_invalidas_total"] == 3


def test_diez_invalidas_consecutivas_declaran_perdida_de_comunicacion():
    link, puerto = _link()
    link._alimentar(linea(DO_OK))
    link._alimentar(b"basura\n" * 9)
    assert link.data["port_open"] is True

    link._alimentar(b"basura\n")
    assert link.data["port_open"] is False
    assert link.is_connected() is False
    assert puerto.is_open is False


def test_umbral_de_invalidas_viene_de_la_configuracion():
    link, _ = _link(lineas_invalidas_max=3)
    link._alimentar(b"x\n" * 3)
    assert link.data["port_open"] is False


def test_excepcion_inesperada_no_se_propaga():
    link, _ = _link()
    with patch.object(link, "_procesar_payload", side_effect=RuntimeError("boom")):
        link._alimentar(linea(AI_OK))
    assert link.get_diagnostico()["lineas_invalidas_total"] == 1


# ---------------------------------------------------------------------------
# Hilo lector real: sobrevive al ruido
# ---------------------------------------------------------------------------

def test_hilo_lector_sobrevive_a_ruido_inyectado():
    link, puerto = _link()
    link.running = True
    hilo = threading.Thread(target=link._read_loop, daemon=True)
    hilo.start()
    try:
        puerto.inyectar(linea("AI:" + ",".join(["5"] * 15 + ["abc"])))   # no numérico
        buena = linea(AI_OK)
        puerto.inyectar(buena[:-3] + b"Z" + buena[-2:])                    # CRC dañado
        puerto.inyectar(b"X" * 1000)                                        # larga sin \n
        puerto.inyectar(b"\n")
        puerto.inyectar(linea(AI_OK))

        assert esperar(lambda: link.get_state()["ai"][0] == 100)
        assert hilo.is_alive()
        assert link.get_diagnostico()["lineas_invalidas_total"] == 3
    finally:
        link.running = False
        puerto.close()
        hilo.join(1)


def test_hilo_lector_sobrevive_al_cierre_del_puerto():
    link, puerto = _link()
    link.running = True
    hilo = threading.Thread(target=link._read_loop, daemon=True)
    hilo.start()
    try:
        puerto.close()
        assert esperar(lambda: link.data["port_open"] is False)
        assert hilo.is_alive()
    finally:
        link.running = False
        hilo.join(1)


# ---------------------------------------------------------------------------
# Vida de la comunicación con time.monotonic()
# ---------------------------------------------------------------------------

def test_silencio_total_declara_timeout_por_monotonic():
    link, _ = _link()
    link._ultima_valida_mono = 1000.0
    link._check_timeout(1000.0 + SerialLink.DATA_TIMEOUT - 0.1)
    assert link.data["port_open"] is True
    link._check_timeout(1000.0 + SerialLink.DATA_TIMEOUT + 0.1)
    assert link.data["port_open"] is False


def test_lineas_invalidas_no_renuevan_la_vida():
    link, _ = _link()
    link._alimentar(linea(DO_OK))
    t0 = link._ultima_valida_mono
    link._alimentar(b"basura\n")
    assert link._ultima_valida_mono == t0


def test_timeout_ignora_saltos_del_reloj_de_pared():
    """Un salto del reloj del sistema (hacia atrás o adelante) no altera la
    vida de la comunicación: _check_timeout solo mira time.monotonic()."""
    link, _ = _link()
    link._alimentar(linea(DO_OK))
    base = link._ultima_valida_mono

    class _DTSalto(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2000, 1, 1) + timedelta(days=365 * 30)

    with patch.object(sl_mod, "datetime", _DTSalto), \
         patch.object(sl_mod.time, "time", side_effect=AssertionError("no debe usarse time.time")):
        link._check_timeout(base + 1.0)
    assert link.data["port_open"] is True


def test_latido_usa_monotonic_y_no_se_detiene_con_cambio_de_hora():
    # E6 (FW-D6): el HB exige handshake completo y un tick reciente del lazo
    link, puerto = _link()
    link._handshake_ok = True
    with patch.object(sl_mod.time, "time", side_effect=AssertionError("no debe usarse time.time")):
        link._ultima_valida_mono = 0.0
        link._ultimo_tick_control = 0.0
        hb, scan = link._watchdog_tick(0.0, None, None)
        link._ultimo_tick_control = 1.0
        hb, scan = link._watchdog_tick(1.0, hb, scan)
        link._ultima_valida_mono = 2.0
        link._ultimo_tick_control = 2.0
        hb, scan = link._watchdog_tick(2.0, hb, scan)
        link._ultima_valida_mono = 4.0
        link._ultimo_tick_control = 4.0
        hb, scan = link._watchdog_tick(4.0, hb, scan)
    assert puerto.comandos().count("HB") == 3


def test_latido_lleva_crc():
    link, puerto = _link()
    link._handshake_ok = True
    link._ultima_valida_mono = 0.0
    link._ultimo_tick_control = 0.0
    link._watchdog_tick(0.0, None, None)
    assert puerto.escrito == ["HB*" + format(sl_mod.agregar_crc("HB").split("*")[1]) + "\n"]


def test_desconexion_notifica_on_update():
    recibidos = []
    link, _ = _link()
    link.on_update = recibidos.append
    link._alimentar(linea(DO_OK))
    link._disconnect()
    assert recibidos[-1]["port_open"] is False
    assert recibidos[-1]["data_alive"] is False


def test_disconnect_condicional_no_cierra_conexion_nueva():
    link, puerto_nuevo = _link()
    viejo = PuertoDoble()
    link._disconnect(solo_si=viejo)
    assert link.serial is puerto_nuevo
    assert link.data["port_open"] is True


# ---------------------------------------------------------------------------
# Comandos con CRC
# ---------------------------------------------------------------------------

def test_set_output_envia_comando_con_crc():
    link, puerto = _link()
    link._handshake_ok = True
    assert link.set_output(4, True) is True
    assert puerto.escrito[-1].startswith("SET DO4 ON*")
    assert sl_mod.validar_linea(puerto.escrito[-1].rstrip("\n")) == "SET DO4 ON"


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def test_config_por_defecto_igual_a_la_especificacion():
    c = SerialLinkConfig()
    assert c.lineas_invalidas_max == 10
    assert c.handshake_presupuesto_s == 15.0
    assert c.all_off_intentos == 3
    assert c.all_off_timeout_s == 1.0
    assert c.tramas_discrepancia == 2
    assert c.reintento_handshake_s == 3.0
    assert c.disc_do_dispara_fallo is False


def test_archivo_del_repositorio_coincide_con_los_internos():
    c = cargar_config()
    assert c == SerialLinkConfig()


def test_config_archivo_faltante_usa_internos(tmp_path, caplog):
    c = cargar_config(str(tmp_path / "no_existe.json"))
    assert c == SerialLinkConfig()


def test_config_json_invalido_usa_internos(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{no json", encoding="utf-8")
    assert cargar_config(str(p)) == SerialLinkConfig()


def test_config_valor_fuera_de_rango_se_rechaza(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"lineas_invalidas_max": 0, "all_off_intentos": 5,
                             "disc_do_dispara_fallo": "si"}), encoding="utf-8")
    c = cargar_config(str(p))
    assert c.lineas_invalidas_max == 10
    assert c.all_off_intentos == 5
    assert c.disc_do_dispara_fallo is False


@pytest.mark.parametrize("valor", [True, 2.5, "3"])
def test_config_tipo_incorrecto_en_entero(valor):
    assert config_desde_dict({"all_off_intentos": valor}).all_off_intentos == 3


def test_config_raiz_no_objeto():
    assert config_desde_dict([1, 2]) == SerialLinkConfig()
