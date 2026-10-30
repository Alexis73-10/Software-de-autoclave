# Tanda 19, P-s1: configuración del enlace Modbus (MOD-06), validada como
# serial_link_config: un valor malo da advertencia y el valor interno.

import json
import logging

import pytest

from autoclave.protocols import modbus_link_config as mc
from autoclave.utils.resources import resource_path

DEFECTOS = {
    "ip": "192.168.3.7", "puerto": 502, "unit_id": 1, "periodo_sondeo_s": 0.1,
    "timeout_s": 0.3, "fallos_para_desconexion": 3, "reintento_conexion_s": 3.0,
    "presupuesto_conexion_s": 15.0, "tiempo_desconexion_modulo_ds": 10,
    "intentos_escritura_config": 3, "filtro_pt100": 1, "filtro_ai": 0,
    "composicion_esperada": {"principal": "XAXX0A00G",
                             # ADB-01 (adenda_tanda_19_banco.md / decisiones_tanda_20.md T20-02):
                             # el principal figura como esclavo 0 (GXAXX0A00).
                             "expansiones": ["GXAXX0A00", "GAXXXA000", "GXXAX00A0",
                                             "GXXAX00A0", "GXDXX0600"]},
    "tramas_discrepancia": 2, "discrepancia_dispara_fallo": True,
}


def _como_dict(cfg):
    return {k: getattr(cfg, k) for k in DEFECTOS}


@pytest.mark.req("MOD-06")
def test_defectos_internos():
    assert _como_dict(mc.ModbusLinkConfig()) == DEFECTOS


@pytest.mark.req("MOD-06")
def test_archivo_del_producto_es_valido_y_sin_advertencias(caplog):
    ruta = resource_path(mc.CONFIG_RELATIVE_PATH)
    with open(ruta, encoding="utf-8") as f:
        assert json.load(f) == DEFECTOS
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.cargar_config(ruta)
    assert _como_dict(cfg) == DEFECTOS
    assert "modbus_link" not in caplog.text


@pytest.mark.req("MOD-06")
def test_archivo_ausente_o_invalido_da_defectos(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        assert mc.cargar_config(str(tmp_path / "no.json")) == mc.ModbusLinkConfig()
        malo = tmp_path / "malo.json"
        malo.write_text("{no es json", encoding="utf-8")
        assert mc.cargar_config(str(malo)) == mc.ModbusLinkConfig()
        assert mc.config_desde_dict(["x"]) == mc.ModbusLinkConfig()
    assert caplog.text.count("modbus_link") >= 3


@pytest.mark.req("MOD-06")
@pytest.mark.parametrize("clave,valor", [
    ("ip", "192.168.3"), ("ip", "300.1.1.1"), ("ip", 1921683), ("ip", "localhost"),
    ("puerto", 0), ("puerto", 65536), ("puerto", "502"), ("puerto", 502.5), ("puerto", True),
    ("unit_id", 0), ("unit_id", 248),
    ("periodo_sondeo_s", 0.01), ("periodo_sondeo_s", 2.0),
    ("timeout_s", 0.0), ("timeout_s", 3.0),
    ("fallos_para_desconexion", 0), ("fallos_para_desconexion", 21),
    ("tiempo_desconexion_modulo_ds", 4), ("tiempo_desconexion_modulo_ds", 101),
    ("intentos_escritura_config", 0),
    ("filtro_pt100", 0), ("filtro_pt100", 17), ("filtro_ai", -1), ("filtro_ai", 5),
    ("tramas_discrepancia", 0),
    ("discrepancia_dispara_fallo", 1), ("discrepancia_dispara_fallo", "true"),
    ("composicion_esperada", None),
    ("composicion_esperada", ["XAXX0A00G"]),
    ("composicion_esperada", {"principal": "XAXX0A00G"}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": []}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": "GAXXXA000"}),
    ("composicion_esperada", {"principal": "", "expansiones": ["GAXXXA000"]}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": ["NONE"]}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": [5]}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": ["G-A"]}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": ["A"] * 33}),
    ("composicion_esperada", {"principal": "XAXX0A00G", "expansiones": ["A"], "otra": 1}),
])
def test_valor_invalido_da_advertencia_y_valor_interno(clave, valor, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.config_desde_dict({clave: valor, "reintento_conexion_s": 1.5})
    assert getattr(cfg, clave) == getattr(mc.ModbusLinkConfig(), clave)
    assert cfg.reintento_conexion_s == 1.5   # las demás claves se conservan
    assert f"{clave}=" in caplog.text


@pytest.mark.req("MOD-06")
def test_valores_validos_se_aceptan():
    cfg = mc.config_desde_dict({
        "ip": " 127.0.0.1 ", "puerto": 1502, "unit_id": 247, "periodo_sondeo_s": 0.05,
        # V19-s1-04: timeout_s < 0,5 s; la conversión de un entero a float se
        # comprueba con reintento_conexion_s.
        "timeout_s": 0.45, "reintento_conexion_s": 2,
        "tiempo_desconexion_modulo_ds": 100, "filtro_ai": 4,
        "filtro_pt100": 16, "discrepancia_dispara_fallo": False,
        "composicion_esperada": {"principal": "m31-xaxx0a00g-u",
                                 "expansiones": ["M31-GAXXXA000-U", "gxdxx0600"]},
    })
    assert cfg.ip == "127.0.0.1" and cfg.puerto == 1502 and cfg.unit_id == 247
    assert cfg.timeout_s == 0.45 and isinstance(cfg.timeout_s, float)
    assert cfg.reintento_conexion_s == 2.0 and isinstance(cfg.reintento_conexion_s, float)
    assert cfg.periodo_sondeo_s == 0.05
    assert cfg.tiempo_desconexion_modulo_ds == 100 and cfg.filtro_ai == 4
    assert cfg.discrepancia_dispara_fallo is False
    assert cfg.composicion_esperada == {"principal": "XAXX0A00G",
                                        "expansiones": ["GAXXXA000", "GXDXX0600"]}


@pytest.mark.req("MOD-06")
def test_clave_desconocida_se_ignora_con_advertencia(caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave"):
        cfg = mc.config_desde_dict({"desconocida": 1})
    assert cfg == mc.ModbusLinkConfig()
    assert "desconocida" in caplog.text


@pytest.mark.req("MOD-06")
@pytest.mark.parametrize("texto,esperado", [
    ("M31-XAXX0A00G-U", "XAXX0A00G"), (" m31-gxdxx0600-u ", "GXDXX0600"),
    ("GAXXX A000", "GAXXXA000"), ("NONE", "NONE"),
])
def test_normalizar_modelo(texto, esperado):
    assert mc.normalizar_modelo(texto) == esperado
