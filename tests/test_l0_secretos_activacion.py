"""LIC-01 (licencia L0): los secretos de activación salen del código. Se cargan
del recurso empaquetado (solo en el ejecutable) o del archivo fuera del
repositorio; sin secretos todo se rechaza (falla cerrada) con una sola
advertencia; la compilación se detiene sin archivo; el generador no arranca
sin archivo. Todo con secretos de PRUEBA (tests/conftest.py)."""

import json
import logging
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from autoclave.installation import activation, secretos
from conftest import SECRETO_PRUEBA_FABRICA, SECRETO_PRUEBA_INSTALACION

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools" / "generador"))
sys.path.insert(0, str(RAIZ / "tools" / "secretos"))

SERIE = "SN128745"
DIA = date(2026, 10, 24)
_IT = 1000


def _escribir(ruta: Path, instalacion: bytes, fabrica: bytes, version=1) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"version": version, "instalacion": instalacion.hex(),
                                "fabrica": fabrica.hex()}), encoding="utf-8")
    return ruta


@pytest.fixture
def sin_secretos(monkeypatch, tmp_path):
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(tmp_path / "no_existe" / "activacion.json"))
    activation.configurar_secretos()
    return tmp_path


# ── con secretos ─────────────────────────────────────────────────────────────

def test_generar_y_validar_con_secretos():
    codigo = activation.generate_installation_code(SERIE, DIA)
    assert activation.validate_installation_code(SERIE, codigo, DIA) is True
    clave = activation.generate_factory_key(SERIE, DIA)
    assert activation.validate_factory_key(SERIE, clave, DIA) is True


def test_rechaza_otro_serial_otro_dia_y_otro_secreto():
    codigo = activation.generate_installation_code(SERIE, DIA)
    assert activation.validate_installation_code("SN128746", codigo, DIA) is False
    assert activation.validate_installation_code(SERIE, codigo, date(2026, 10, 25)) is False
    activation.configurar_secretos(b"\x11" * 32, SECRETO_PRUEBA_FABRICA)
    assert activation.validate_installation_code(SERIE, codigo, DIA) is False


def test_clave_de_fabrica_de_otro_secreto_rechazada():
    clave = activation.generate_factory_key(SERIE, DIA)
    activation.configurar_secretos(SECRETO_PRUEBA_INSTALACION, b"\x22" * 32)
    assert activation.validate_factory_key(SERIE, clave, DIA) is False


# ── sin secretos: falla cerrada ──────────────────────────────────────────────

def test_sin_secretos_valida_falso_y_advierte_una_sola_vez(sin_secretos, caplog):
    caplog.set_level(logging.WARNING, logger=activation.__name__)
    for _ in range(3):
        assert activation.validate_installation_code(SERIE, "AAAAAAAAAAAA", DIA) is False
        assert activation.validate_factory_key(SERIE, "AAAAAAAAAAAA", DIA) is False
    avisos = [r for r in caplog.records if "sin secretos de activación" in r.getMessage()]
    assert len(avisos) == 1
    assert activation.secretos_disponibles() is False
    assert activation.huella_instalacion() is None


def test_sin_secretos_no_se_genera_ningun_codigo(sin_secretos):
    with pytest.raises(activation.SecretosNoDisponibles):
        activation.generate_installation_code(SERIE, DIA)
    with pytest.raises(activation.SecretosNoDisponibles):
        activation.generate_factory_key(SERIE, DIA)


@pytest.mark.parametrize("contenido", [
    "no es json",
    json.dumps({"version": 2, "instalacion": "ab" * 32, "fabrica": "cd" * 32}),
    json.dumps({"version": 1, "instalacion": "ab" * 31, "fabrica": "cd" * 32}),
    json.dumps({"version": 1, "instalacion": "zz" * 32, "fabrica": "cd" * 32}),
    json.dumps({"version": 1, "instalacion": "ab" * 32, "fabrica": "ab" * 32}),
])
def test_archivo_invalido_es_como_sin_secretos(monkeypatch, tmp_path, contenido):
    ruta = tmp_path / "activacion.json"
    ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(ruta))
    activation.configurar_secretos()
    assert activation.validate_installation_code(SERIE, "AAAAAAAAAAAA", DIA) is False
    assert activation.secretos_disponibles() is False


# ── orden de carga ───────────────────────────────────────────────────────────

def test_desarrollo_lee_el_archivo_de_la_variable(monkeypatch, tmp_path):
    ruta = _escribir(tmp_path / "s" / "activacion.json", b"\x01" * 32, b"\x02" * 32)
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(ruta))
    activation.configurar_secretos()
    codigo = activation._make_code(b"\x01" * 32, SERIE, DIA)
    assert activation.validate_installation_code(SERIE, codigo, DIA) is True
    assert activation.huella_instalacion() == secretos.huella(b"\x01" * 32)


def test_ruta_por_defecto_en_documentos_del_usuario(monkeypatch, tmp_path):
    monkeypatch.delenv(secretos.VARIABLE_ENTORNO, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert secretos.ruta_archivo_secretos() == tmp_path / "Documents" / "especifika_secretos" / "activacion.json"


def test_ejecutable_prefiere_el_recurso_empaquetado(monkeypatch, tmp_path):
    meipass = tmp_path / "meipass"
    _escribir(meipass / "config" / "activacion_secretos.json", b"\x05" * 32, b"\x06" * 32)
    archivo = _escribir(tmp_path / "s" / "activacion.json", b"\x07" * 32, b"\x08" * 32)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(archivo))
    activation.configurar_secretos()
    assert activation.huella_instalacion() == secretos.huella(b"\x05" * 32)
    # el recurso no es de autoclave/config: no se siembra en disco escribible
    assert not secretos.RECURSO_EMPAQUETADO.startswith("autoclave/")


def test_ejecutable_sin_recurso_usa_el_archivo(monkeypatch, tmp_path):
    archivo = _escribir(tmp_path / "s" / "activacion.json", b"\x07" * 32, b"\x08" * 32)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "vacio"), raising=False)
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(archivo))
    activation.configurar_secretos()
    assert activation.huella_instalacion() == secretos.huella(b"\x07" * 32)


def test_ningun_secreto_en_el_codigo_fuente():
    fuente = (RAIZ / "src" / "autoclave" / "installation" / "activation.py").read_text(encoding="utf-8")
    assert "_SECRET_" not in fuente
    assert not re.search(r"=\s*b['\"]", fuente)   # ningún literal de bytes asignado
    assert not re.search(r"[0-9a-fA-F]{64}", fuente)


# ── compilación ──────────────────────────────────────────────────────────────

def test_compilacion_se_detiene_sin_archivo(sin_secretos):
    with pytest.raises(SystemExit) as e:
        secretos.entrada_compilacion()
    assert "sin secretos" in str(e.value)


def test_compilacion_se_detiene_con_archivo_invalido(monkeypatch, tmp_path):
    ruta = _escribir(tmp_path / "activacion.json", b"\x01" * 32, b"\x02" * 32, version=9)
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(ruta))
    with pytest.raises(SystemExit):
        secretos.entrada_compilacion()


def test_compilacion_empaqueta_el_archivo_sin_imprimir_el_secreto(monkeypatch, tmp_path, capsys):
    ruta = _escribir(tmp_path / "activacion.json", b"\x0a" * 32, b"\x0b" * 32)
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO, str(ruta))
    destino, origen, tipo = secretos.entrada_compilacion()
    assert (destino, origen, tipo) == ("config/activacion_secretos.json", str(ruta), "DATA")
    salida = capsys.readouterr().out
    assert secretos.huella(b"\x0a" * 32) in salida
    assert (b"\x0a" * 32).hex() not in salida and (b"\x0b" * 32).hex() not in salida


@pytest.mark.parametrize("spec", ["Autoclave.spec", "AutoclaveBackend.spec"])
def test_specs_del_autoclave_empaquetan_los_secretos(spec):
    texto = (RAIZ / spec).read_text(encoding="utf-8")
    assert "a.datas.append(entrada_compilacion())" in texto
    assert texto.index("entrada_compilacion()") < texto.index("pyz = PYZ(a.pure)")


def test_spec_del_generador_no_empaqueta_secretos():
    texto = (RAIZ / "GeneradorCodigos.spec").read_text(encoding="utf-8")
    assert "entrada_compilacion" not in texto and "activacion_secretos" not in texto
    assert "datas=[]" in texto


def test_gitignore_cubre_el_archivo_de_secretos():
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "especifika_secretos/" in texto and "activacion.json" in texto


# ── generar_secretos.py ──────────────────────────────────────────────────────

def test_generar_secretos_crea_el_archivo_y_no_imprime_valores(tmp_path, capsys):
    import generar_secretos
    ruta = tmp_path / "especifika_secretos" / "activacion.json"
    assert generar_secretos.generar(ruta) == 0
    leidos = secretos.leer_archivo(ruta)
    salida = capsys.readouterr().out
    for valor in leidos.values():
        assert len(valor) == 32
        assert valor.hex() not in salida
        assert secretos.huella(valor) in salida
    assert str(ruta) in salida


def test_generar_secretos_se_niega_si_ya_existe(tmp_path):
    import generar_secretos
    ruta = _escribir(tmp_path / "activacion.json", b"\x01" * 32, b"\x02" * 32)
    antes = ruta.read_bytes()
    assert generar_secretos.generar(ruta) == 1
    assert ruta.read_bytes() == antes


def test_generar_secretos_produce_valores_distintos(tmp_path):
    import generar_secretos
    generar_secretos.generar(tmp_path / "a.json")
    generar_secretos.generar(tmp_path / "b.json")
    a, b = secretos.leer_archivo(tmp_path / "a.json"), secretos.leer_archivo(tmp_path / "b.json")
    assert a["instalacion"] != b["instalacion"] and a["fabrica"] != b["fabrica"]


# ── generador ────────────────────────────────────────────────────────────────

@pytest.fixture
def datos_gen(tmp_path, monkeypatch):
    import db as generador_db
    monkeypatch.setattr(generador_db, "DB_PATH", tmp_path / "generador.db")
    generador_db.init_db()
    return tmp_path


def test_generador_sin_archivo_no_arranca_y_muestra_el_motivo(datos_gen, sin_secretos):
    from fastapi.testclient import TestClient
    import datos_generador
    from app import create_app, motivo_sin_secretos
    assert "generar_secretos.py" in motivo_sin_secretos()
    client = TestClient(create_app(datos_gen, {**datos_generador.DEFECTO}))
    for ruta in ("/", "/login", "/generar"):
        r = client.get(ruta, follow_redirects=False)
        assert r.status_code == 503
        assert "no arrancó" in r.text and "activacion.json" in r.text
    assert client.post("/generar", data={"serial": "SN1"}).status_code == 503
    assert client.get("/salud").json()["sin_secretos"] is True


def test_lanzador_sin_archivo_lo_registra(datos_gen, sin_secretos, monkeypatch, caplog):
    import datos_generador
    import lanzador
    monkeypatch.setattr(datos_generador, "carpeta_datos", lambda: datos_gen)
    monkeypatch.setattr(lanzador, "puerto_en_uso", lambda p: False)
    monkeypatch.setattr(lanzador, "_configurar_log", lambda d: None)
    monkeypatch.setattr(lanzador.respaldo_generador, "iniciar_periodico", lambda *a, **k: None)
    servidas = []
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda app, **k: servidas.append(app))
    caplog.set_level(logging.ERROR, logger="generador")
    assert lanzador.main(["--sin-navegador"]) == 0
    assert any("no arranca" in r.getMessage() for r in caplog.records)
    from fastapi.testclient import TestClient
    assert TestClient(servidas[0]).get("/generar").status_code == 503


def test_admin_muestra_la_huella_del_secreto_de_instalacion(datos_gen):
    from fastapi.testclient import TestClient
    import datos_generador
    import seguridad_generador as seg
    from app import create_app
    seg.crear_admin_inicial(datos_gen, iteraciones=_IT)
    clave = (datos_gen / seg.ARCHIVO_CLAVE_INICIAL).read_text(encoding="utf-8").split("temporal: ")[1].split()[0]
    client = TestClient(create_app(datos_gen, {**datos_generador.DEFECTO}, iteraciones=_IT))
    client.post("/login", data={"username": "admin", "password": clave})
    client.post("/cambiar_clave", data={"actual": clave, "nueva": "nueva-clave-123",
                                        "confirmacion": "nueva-clave-123"})
    r = client.get("/admin")
    assert secretos.huella(SECRETO_PRUEBA_INSTALACION) in r.text
    assert SECRETO_PRUEBA_INSTALACION.hex() not in r.text
