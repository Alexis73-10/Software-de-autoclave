# tests/test_config_correo.py
#
# Configuración provisional del envío de ciclos por correo
# (ui_qml/exportacion/config_correo.py + config/correo.json).

import json

import pytest

from autoclave.ui_qml.exportacion import config_correo as cc


def _archivo(tmp_path, **datos):
    base = {"remitente": "equipo@gmail.com", "servidor_smtp": "smtp.gmail.com", "puerto": 587,
            "destinos": [{"nombre": "Mantenimiento", "correo": "mant@x.com"}]}
    base.update(datos)
    ruta = tmp_path / "correo.json"
    ruta.write_text(json.dumps(base), encoding="utf-8")
    return ruta


def test_carga_el_archivo_del_repo():
    c = cc.cargar(contrasena=lambda remitente: None)
    assert [d["nombre"] for d in c.destinos] == ["Administrativo", "Mantenimiento"]
    assert c.servidor == "smtp.gmail.com" and c.puerto == 587


def test_configurado_con_remitente_y_contrasena(tmp_path):
    pedidas = []
    c = cc.cargar(_archivo(tmp_path), contrasena=lambda r: pedidas.append(r) or "clave")
    assert c.configurado and c.contrasena == "clave" and pedidas == ["equipo@gmail.com"]


def test_sin_remitente_no_esta_configurado(tmp_path):
    c = cc.cargar(_archivo(tmp_path, remitente=""), contrasena=lambda r: "clave")
    assert not c.configurado


def test_sin_contrasena_no_esta_configurado(tmp_path):
    assert not cc.cargar(_archivo(tmp_path), contrasena=lambda r: None).configurado


def test_contrasena_inaccesible_no_esta_configurado(tmp_path):
    def falla(r):
        raise RuntimeError("sin almacén de credenciales")
    assert not cc.cargar(_archivo(tmp_path), contrasena=falla).configurado


def test_archivo_ausente_o_danado(tmp_path):
    assert not cc.cargar(tmp_path / "no.json", contrasena=lambda r: "x").configurado
    roto = tmp_path / "roto.json"
    roto.write_text("{", encoding="utf-8")
    c = cc.cargar(roto, contrasena=lambda r: "x")
    assert not c.configurado and c.destinos == []


def test_descarta_destinos_invalidos(tmp_path):
    ruta = _archivo(tmp_path, destinos=[
        {"nombre": "Bien", "correo": "a@b.co"}, {"nombre": "Sin arroba", "correo": "ab.co"},
        {"correo": "c@d.co"}, "texto"])
    assert cc.cargar(ruta, contrasena=lambda r: "x").destinos == [{"nombre": "Bien", "correo": "a@b.co"}]


@pytest.mark.parametrize("correo, valido", [
    ("ingenieria.ccubides@gmail.com", True), ("a@b.co", True),
    ("", False), ("sin-arroba.com", False), ("a@b", False), ("a b@c.com", False), ("a@@b.com", False),
])
def test_correo_valido(correo, valido):
    assert cc.correo_valido(correo) is valido
