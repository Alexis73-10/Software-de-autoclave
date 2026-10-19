"""G1 (tanda 2): generador de códigos con usuarios individuales, sesiones con
expiración, bloqueo por intentos, carpeta de datos persistente, migración de
la base heredada, respaldo con integridad y arranque con el puerto ocupado."""

import os
import socket
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "generador"))
import datos_generador  # noqa: E402
import db as generador_db  # noqa: E402
import lanzador  # noqa: E402
import respaldo_generador  # noqa: E402
import seguridad_generador as seg  # noqa: E402
from autoclave.backend.contrasenas import hash_password  # noqa: E402

_IT = 1000   # iteraciones de PBKDF2 reducidas para las pruebas


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setattr(generador_db, "DB_PATH", tmp_path / "generador.db")
    generador_db.init_db()
    return tmp_path


def _crear(usuario, clave, rol="usuario", debe_cambiar=False):
    generador_db.crear_usuario(usuario, hash_password(clave, iteraciones=_IT), rol, debe_cambiar)


# ── base ─────────────────────────────────────────────────────────────────────

def test_base_en_wal_con_busy_timeout(datos):
    con = generador_db.conectar()
    assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert con.execute("PRAGMA busy_timeout").fetchone()[0] == generador_db.BUSY_TIMEOUT_MS
    con.close()


def test_migra_una_base_heredada_sin_tocar_los_registros(tmp_path, monkeypatch):
    vieja = tmp_path / "vieja.db"
    con = sqlite3.connect(vieja)
    con.execute("CREATE TABLE codigos_generados (id INTEGER PRIMARY KEY AUTOINCREMENT, serial TEXT NOT NULL,"
                " tipo TEXT NOT NULL CHECK(tipo IN ('instalacion','reinstalacion','fabrica')),"
                " fecha TEXT NOT NULL, usuario TEXT NOT NULL)")
    con.execute("INSERT INTO codigos_generados (serial,tipo,fecha,usuario) "
                "VALUES ('SN1','instalacion','2026-06-17','especifika')")
    con.commit()
    con.close()
    datos = tmp_path / "datos"
    destino = datos_generador.preparar_base(datos, heredadas=[vieja])
    assert vieja.exists() and destino.exists()            # copia, no mueve
    monkeypatch.setattr(generador_db, "DB_PATH", destino)
    generador_db.init_db()
    assert generador_db.get_history("SN1") == [
        {"tipo": "instalacion", "fecha": "2026-06-17", "usuario": "especifika"}]
    assert generador_db.hay_usuarios() is False


def test_no_pisa_una_base_ya_presente(tmp_path):
    datos = tmp_path / "datos"
    datos.mkdir()
    (datos / "generador.db").write_bytes(b"actual")
    otra = tmp_path / "otra.db"
    otra.write_bytes(b"heredada")
    datos_generador.preparar_base(datos, heredadas=[otra])
    assert (datos / "generador.db").read_bytes() == b"actual"


def test_config_por_defecto_y_valores_del_archivo(tmp_path):
    conf = datos_generador.cargar(tmp_path)
    assert conf["host"] == "0.0.0.0" and conf["puerto"] == 8080
    (tmp_path / "config.json").write_text('{"puerto": 9090, "ajeno": 1}', encoding="utf-8")
    conf = datos_generador.cargar(tmp_path)
    assert conf["puerto"] == 9090 and "ajeno" not in conf


def test_carpeta_de_datos_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERADOR_DATOS", str(tmp_path / "x"))
    assert datos_generador.carpeta_datos() == tmp_path / "x"


def test_sin_contrasena_por_defecto_en_el_codigo():
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "tools" / "generador" / "app.py").read_text(encoding="utf-8")
    assert "cambiar_esto_2026" not in fuente and "GENERADOR_PASS" not in fuente


# ── usuarios y sesiones ──────────────────────────────────────────────────────

def test_admin_inicial_con_clave_temporal_una_vez(datos):
    clave = seg.crear_admin_inicial(datos, iteraciones=_IT)
    assert clave and (datos / seg.ARCHIVO_CLAVE_INICIAL).exists()
    assert clave in (datos / seg.ARCHIVO_CLAVE_INICIAL).read_text(encoding="utf-8")
    fila = generador_db.obtener_usuario("admin")
    assert fila["rol"] == "admin" and fila["debe_cambiar"] == 1
    assert fila["hash"].startswith("pbkdf2$") and clave not in fila["hash"]
    assert seg.crear_admin_inicial(datos, iteraciones=_IT) is None   # ya hay usuarios


def test_hash_y_verificacion(datos):
    _crear("ana", "clave-larga-1")
    s = seg.Sesiones(900, 5, 900, reloj=Reloj())
    assert s.autenticar("ana", "clave-larga-1")[0]
    assert s.autenticar("ana", "otra")[0] is None
    assert s.autenticar("nadie", "x")[0] is None


def test_bloqueo_por_intentos_y_desbloqueo_por_tiempo(datos):
    _crear("ana", "clave-larga-1")
    reloj = Reloj()
    s = seg.Sesiones(900, 3, 600, reloj=reloj)
    for _ in range(3):
        assert s.autenticar("ana", "mala")[0] is None
    token, motivo = s.autenticar("ana", "clave-larga-1")
    assert token is None and "bloqueado" in motivo
    reloj.t += 601
    assert s.autenticar("ana", "clave-larga-1")[0]


def test_sesion_vence_por_inactividad_y_se_renueva_con_el_uso(datos):
    _crear("ana", "clave-larga-1")
    reloj = Reloj()
    s = seg.Sesiones(900, 5, 600, reloj=reloj)
    token, _ = s.autenticar("ana", "clave-larga-1")
    reloj.t += 800
    assert s.usuario(token)["usuario"] == "ana"          # uso: renueva
    reloj.t += 800
    assert s.usuario(token) is not None
    reloj.t += 901
    assert s.usuario(token) is None


def test_usuario_desactivado_pierde_la_sesion_y_no_entra(datos):
    _crear("ana", "clave-larga-1")
    s = seg.Sesiones(900, 5, 600, reloj=Reloj())
    token, _ = s.autenticar("ana", "clave-larga-1")
    generador_db.fijar_activo("ana", False)
    assert s.usuario(token) is None
    assert s.autenticar("ana", "clave-larga-1") == (None, "Usuario desactivado")


# ── app ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def cliente(datos):
    from fastapi.testclient import TestClient
    from app import create_app
    seg.crear_admin_inicial(datos, iteraciones=_IT)
    clave = (datos / seg.ARCHIVO_CLAVE_INICIAL).read_text(encoding="utf-8").split("temporal: ")[1].split()[0]
    conf = {**datos_generador.DEFECTO}
    app = create_app(datos, conf, sesiones=seg.Sesiones(900, 5, 600, reloj=Reloj()), iteraciones=_IT)
    return TestClient(app), clave, datos


def _entrar(client, usuario, clave):
    return client.post("/login", data={"username": usuario, "password": clave}, follow_redirects=False)


def test_primer_ingreso_exige_cambiar_la_clave_y_borra_el_archivo(cliente):
    client, clave, datos = cliente
    r = _entrar(client, "admin", clave)
    assert r.headers["location"] == "/cambiar_clave"
    assert client.get("/generar", follow_redirects=False).headers["location"] == "/cambiar_clave"
    r = client.post("/cambiar_clave", data={"actual": clave, "nueva": "nueva-clave-123",
                                            "confirmacion": "nueva-clave-123"}, follow_redirects=False)
    assert r.headers["location"] == "/generar"
    assert not (datos / seg.ARCHIVO_CLAVE_INICIAL).exists()
    assert client.get("/generar").status_code == 200


def _admin_listo(client, clave):
    _entrar(client, "admin", clave)
    client.post("/cambiar_clave", data={"actual": clave, "nueva": "nueva-clave-123",
                                        "confirmacion": "nueva-clave-123"})


def test_codigos_registran_el_usuario_real(cliente):
    client, clave, _ = cliente
    _admin_listo(client, clave)
    assert client.post("/generar", data={"serial": "sn9"}).status_code == 200
    assert generador_db.get_history("SN9")[0]["usuario"] == "admin"


def test_solo_admin_administra_usuarios(cliente):
    client, clave, _ = cliente
    _admin_listo(client, clave)
    r = client.post("/admin/crear", data={"usuario": "luis", "rol": "usuario"})
    assert "Contraseña temporal de <b>luis</b>" in r.text
    temporal = r.text.split("<code>")[1].split("</code>")[0]
    client.get("/logout")
    _entrar(client, "luis", temporal)
    client.post("/cambiar_clave", data={"actual": temporal, "nueva": "clave-de-luis-1",
                                        "confirmacion": "clave-de-luis-1"})
    assert client.get("/admin", follow_redirects=False).headers["location"] == "/generar"
    r = client.post("/admin/desactivar", data={"usuario": "admin"}, follow_redirects=False)
    assert r.status_code == 303 and generador_db.obtener_usuario("admin")["activo"] == 1


def test_no_queda_sin_admin_activo(cliente):
    client, clave, _ = cliente
    _admin_listo(client, clave)
    r = client.post("/admin/desactivar", data={"usuario": "admin"})
    assert "No puede desactivarse a sí mismo" in r.text


def test_restablecer_exige_cambio_y_cierra_sesiones(cliente):
    client, clave, _ = cliente
    _admin_listo(client, clave)
    client.post("/admin/crear", data={"usuario": "luis", "rol": "usuario"})
    r = client.post("/admin/restablecer", data={"usuario": "luis"})
    assert "Contraseña temporal de <b>luis</b>" in r.text
    assert generador_db.obtener_usuario("luis")["debe_cambiar"] == 1


def test_salud_identifica_al_generador(cliente):
    client, _, _ = cliente
    assert client.get("/salud").json() == {"app": "generador-especifika"}


def test_login_muestra_la_url_de_la_red(cliente):
    client, _, _ = cliente
    assert "Desde otro PC de la red" in client.get("/login").text


# ── respaldo ─────────────────────────────────────────────────────────────────

def test_respaldo_con_la_api_de_sqlite_y_verificado(datos):
    generador_db.log_codigo("SN1", "instalacion", "ana")
    ruta = respaldo_generador.respaldar(generador_db.DB_PATH, datos / "Respaldos")
    assert ruta is not None and ruta.exists()
    con = sqlite3.connect(ruta)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute("SELECT serial FROM codigos_generados").fetchone()[0] == "SN1"
    con.close()


def test_retencion_de_30_dias(tmp_path):
    carpeta = tmp_path / "Respaldos"
    carpeta.mkdir()
    ahora = datetime(2026, 10, 19, 12, 0, 0)
    viejo = carpeta / f"generador_{(ahora - timedelta(days=31)).strftime('%Y%m%d_%H%M%S')}.db"
    nuevo = carpeta / f"generador_{(ahora - timedelta(days=29)).strftime('%Y%m%d_%H%M%S')}.db"
    ajeno = carpeta / "otra_cosa.db"
    for f in (viejo, nuevo, ajeno):
        f.write_bytes(b"x")
    assert respaldo_generador.podar(carpeta, 30, ahora=ahora) == [viejo]
    assert nuevo.exists() and ajeno.exists()


# ── arranque ─────────────────────────────────────────────────────────────────

def test_puerto_ocupado_por_otro_programa_no_arranca(tmp_path, monkeypatch):
    import threading
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    srv.settimeout(0.2)
    puerto = srv.getsockname()[1]
    parar = threading.Event()

    def aceptar():                       # otro programa: acepta y no responde HTTP
        while not parar.is_set():
            try:
                c, _ = srv.accept()
                c.close()
            except OSError:
                pass
    hilo = threading.Thread(target=aceptar, daemon=True)
    hilo.start()
    try:
        monkeypatch.setenv("GENERADOR_DATOS", str(tmp_path))
        (tmp_path / "config.json").write_text(f'{{"puerto": {puerto}}}', encoding="utf-8")
        assert lanzador.puerto_en_uso(puerto) is True
        assert lanzador.es_el_generador(puerto) is False
        assert lanzador.main(["--sin-navegador"]) == 2
    finally:
        parar.set()
        hilo.join(2)
        srv.close()


def test_puerto_ocupado_por_el_generador_solo_abre_el_navegador(tmp_path, monkeypatch):
    monkeypatch.setenv("GENERADOR_DATOS", str(tmp_path))
    (tmp_path / "config.json").write_text('{"puerto": 18089}', encoding="utf-8")
    abiertos = []
    monkeypatch.setattr(lanzador, "puerto_en_uso", lambda p: True)
    monkeypatch.setattr(lanzador, "es_el_generador", lambda p: True)
    monkeypatch.setattr(lanzador.webbrowser, "open", abiertos.append)
    assert lanzador.main([]) == 0
    assert abiertos == ["http://localhost:18089"]
