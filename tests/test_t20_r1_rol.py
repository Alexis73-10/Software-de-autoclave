# Tanda 20, corrector r1 · rol `--rol configurar-modulo`
# (estacion/configurar_modulo.py): V20-s1-06 (pymodbus silenciado durante
# todo el rol) y V20-s1-08 (backend comprobado otra vez antes de escribir,
# presupuesto acotado al tiempo restante, RuntimeError con el hilo de
# sondeo en marcha). Contra el simulador M31 (solo 127.0.0.1, puerto libre).
# Solo contraseñas ficticias.

import json
import logging
import time

import pytest

from autoclave.estacion import configurar_modulo as cm
from autoclave.protocols.modbus_link import ModbusLink
from tests.helpers import m31_simulado as m31
from tests.helpers.m31_simulado import M31Simulado, config_para

CLAVE = "Pr1eba"          # ficticia
# La contraseña en hexadecimal, como la volcaría pymodbus (2 ASCII por registro)
CLAVE_HEX = " ".join(f"0x{b:02x}" for b in CLAVE.encode("ascii"))


@pytest.fixture
def sim():
    s = M31Simulado()
    s.iniciar()
    yield s
    s.detener()


def _argv(ruta, sim, *extra):
    return ["--resultado", str(ruta), "--ip", "127.0.0.1", "--puerto", str(sim.puerto),
            *extra]


# ---------------------------------------------------------------------------
# V20-s1-06 · pymodbus no escribe en el log del rol
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-04")
@pytest.mark.req("V20-s1-06")
def test_pymodbus_silenciado_durante_todo_el_rol(sim, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(cm, "backend_escuchando", lambda: False)
    logging.getLogger("pymodbus").setLevel(logging.DEBUG)
    hijo = logging.getLogger("pymodbus.logging")
    hijo.setLevel(logging.DEBUG)
    vistos = {}
    original = cm.ejecutar

    def _ejecutar(args, clave, hay_clave):
        # Como el cliente síncrono al cerrarse el socket a mitad de respuesta
        logging.getLogger("pymodbus.logging").warning("recv: %s (bytes crudos)", CLAVE_HEX)
        logging.getLogger("pymodbus").error("bytes %s", CLAVE_HEX)
        logging.getLogger("pymodbus.client.nuevo").critical("bytes %s", CLAVE_HEX)
        vistos["nivel"] = logging.getLogger("pymodbus").level
        vistos["nivel_hijo"] = hijo.level
        return original(args, clave, hay_clave)

    monkeypatch.setattr(cm, "ejecutar", _ejecutar)
    archivo = tmp_path / "clave.tmp"
    archivo.write_bytes(CLAVE.encode("ascii"))
    ruta = tmp_path / "r.json"
    with caplog.at_level(logging.DEBUG):
        codigo = cm.main(_argv(ruta, sim, "--clave-archivo", str(archivo)))
    assert codigo == 0
    assert vistos == {"nivel": logging.CRITICAL, "nivel_hijo": logging.CRITICAL}
    assert CLAVE_HEX not in caplog.text and CLAVE not in caplog.text
    assert not [r for r in caplog.records if r.name.startswith("pymodbus")]
    # Al terminar el rol se restauran los niveles y no quedan filtros
    assert logging.getLogger("pymodbus").level == logging.DEBUG
    assert hijo.level == logging.DEBUG and not hijo.filters
    assert not [f for h in logging.root.handlers for f in h.filters
                if isinstance(f, cm._SinPymodbus)]
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)
    hijo.setLevel(logging.NOTSET)


# ---------------------------------------------------------------------------
# V20-s1-08 · backend comprobado antes de escribir; presupuesto; hilo
# ---------------------------------------------------------------------------

@pytest.mark.req("T20-04")
@pytest.mark.req("V20-s1-08")
def test_backend_que_aparece_durante_la_lectura_impide_escribir(sim, tmp_path, monkeypatch):
    llamadas = []

    def _backend():
        llamadas.append(1)
        return len(llamadas) > 1        # libre al empezar; escuchando después

    monkeypatch.setattr(cm, "backend_escuchando", _backend)
    archivo = tmp_path / "clave.tmp"
    archivo.write_bytes(CLAVE.encode("ascii"))
    ruta = tmp_path / "r.json"
    codigo = cm.main(_argv(ruta, sim, "--clave-archivo", str(archivo)))
    res = json.loads(ruta.read_text(encoding="ascii"))
    assert codigo == 2 and res["codigo"] == "backend_activo"
    assert res["clave_cambiada"] is False and len(llamadas) == 2
    assert sim.escrituras == []
    assert sim.credenciales_web() == ("admin", m31.CLAVE_WEB_DEFECTO)
    assert not archivo.exists()


@pytest.mark.req("T20-04")
@pytest.mark.req("V20-s1-08")
def test_presupuesto_total_acotado(sim, tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "backend_escuchando", lambda: False)
    monkeypatch.setattr(cm, "PRESUPUESTO_S", 1.5)
    monkeypatch.setattr(cm, "PAUSA_REINTENTO_S", 0.3)
    presupuestos = []
    original = cm._crear_enlace

    def _crear(ip, puerto, presupuesto_s):
        enlace = original(ip, puerto, presupuesto_s)
        presupuestos.append(enlace.config.presupuesto_conexion_s)
        return enlace

    monkeypatch.setattr(cm, "_crear_enlace", _crear)
    sim.silencio = True
    ruta = tmp_path / "r.json"
    t0 = time.monotonic()
    codigo = cm.main(_argv(ruta, sim))
    duracion = time.monotonic() - t0
    assert codigo == 3
    assert duracion <= cm.PRESUPUESTO_S + cm.MARGEN_PRESUPUESTO_S
    assert len(presupuestos) >= 2
    # Cada intento recibe a lo sumo el tiempo restante (sin piso de 1 s)
    assert presupuestos[0] <= 1.5 and all(p < 1.0 for p in presupuestos[1:])


@pytest.mark.req("T20-04")
@pytest.mark.req("V20-s1-08")
def test_credenciales_e_identidad_rechazadas_con_el_hilo_en_marcha(sim):
    enlace = ModbusLink(config=config_para(sim))
    enlace.running = True               # sin arrancar el hilo de verdad
    try:
        with pytest.raises(RuntimeError):
            enlace.escribir_credenciales_web("admin", CLAVE)
        with pytest.raises(RuntimeError):
            enlace.leer_identidad()
    finally:
        enlace.running = False
    assert sim.escrituras == [] and sim.contador() == 0
