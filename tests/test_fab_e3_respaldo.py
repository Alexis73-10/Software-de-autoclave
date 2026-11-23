# tests/test_fab_e3_respaldo.py
#
# Modo fábrica, Etapa 3: el respaldo USB lleva copia de la base de fábrica del
# equipo (carpeta fabrica_equipo/ del ZIP) y la restauración no la restaura.

import json

import pytest

from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.core.runtime import respaldo as rp
from tests.test_o2h_respaldo import api  # noqa: F401  (fixture)

_RUTA_PAR = f"{fe.CARPETA_EN_RESPALDO}/{fe.NOMBRE_PARAMETROS}"
_RUTA_CAL = f"{fe.CARPETA_EN_RESPALDO}/{fe.NOMBRE_CALIBRACION}"


@pytest.fixture
def datos(tmp_path, monkeypatch):
    d = tmp_path / "datos_equipo"
    d.mkdir()
    monkeypatch.setattr(fe, "carpeta_datos", lambda: d)
    return d


def test_contenido_respaldo(datos):
    assert fe.contenido_respaldo(True, True) == {}
    (datos / fe.NOMBRE_PARAMETROS).write_text('{"timeout_puerta": 90}', encoding="utf-8")
    (datos / fe.NOMBRE_CALIBRACION).write_text("formato: 1\n", encoding="utf-8")
    assert set(fe.contenido_respaldo(True, True)) == {_RUTA_PAR, _RUTA_CAL}
    assert set(fe.contenido_respaldo(True, False)) == {_RUTA_CAL}
    assert set(fe.contenido_respaldo(False, True)) == {_RUTA_PAR}
    assert fe.contenido_respaldo(False, False) == {}


def test_exporta_copia_y_no_restaura(api, datos):  # noqa: F811
    client, srv, ctx, cab, usb, programas, calib = api
    h = cab(srv, "tecnico")
    par = datos / fe.NOMBRE_PARAMETROS
    cal = datos / fe.NOMBRE_CALIBRACION
    par.write_text('{"timeout_puerta": 90}', encoding="utf-8")
    cal.write_bytes(b"formato: 1\n")
    r = client.post("/backup/export", json={"unidad": str(usb)}, headers=h)
    assert r.status_code == 200, r.text
    m, contenido = rp.leer(usb / rp.CARPETA / r.json()["archivo"])
    assert contenido[_RUTA_PAR] == b'{"timeout_puerta": 90}'
    assert contenido[_RUTA_CAL] == b"formato: 1\n"
    # cambios locales: la restauración no los toca
    par.write_text('{"timeout_puerta": 100}', encoding="utf-8")
    cal.unlink()
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": r.json()["archivo"],
                                            "confirmar": True}, headers=h)
    assert r.status_code == 200, r.text
    assert json.loads(par.read_text(encoding="utf-8")) == {"timeout_puerta": 100}
    assert not cal.exists()


def test_sin_archivos_el_respaldo_no_cambia(api, datos):  # noqa: F811
    client, srv, ctx, cab, usb, *_ = api
    r = client.post("/backup/export", json={"unidad": str(usb)}, headers=cab(srv, "tecnico"))
    assert r.status_code == 200
    _, contenido = rp.leer(usb / rp.CARPETA / r.json()["archivo"])
    assert not any(k.startswith(fe.CARPETA_EN_RESPALDO + "/") for k in contenido)
