"""Tanda 17, F2 (BIT-01 a BIT-05): bitácora central.

- Filtro central en el escritor de audit_log: los eventos retirados van al log
  de desarrollo; las filas viejas no se borran pero la vista las oculta.
- Nada en audit_log mientras la instalación no termine; una sola fila
  `equipo_instalado` al terminar el asistente.
- El bloqueo de usuario no depende de las filas `login_fallido` (BIT-03).
- Categorías del filtro «Tipo» (BIT-05).
"""
import json
import logging
import re
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import contrasenas
from autoclave.core.runtime import bitacora
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cargar_servidor

pytestmark = pytest.mark.req("BIT-01", "BIT-02", "BIT-03", "BIT-04", "BIT-05")

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"


def _filas(db, evento=None):
    return db.get_auditoria(evento=evento, limite=1000)


@pytest.fixture
def db(tmp_path):
    base = DbManager(db_path=tmp_path / "t.db")
    yield base
    base.close()


# ── BIT-01/03/04: filtro central ─────────────────────────────────────────────

@pytest.mark.parametrize("evento", ["salida_prueba", "modo_prueba_sale", "login_fallido", "logout",
                                    "entradas_mostradas", "salida_prueba_cortada",
                                    "contrasena_fijada_instalacion",
                                    "inicio_descartado_por_modo_prueba"])
def test_retirados_van_al_log_y_no_a_audit_log(db, evento, caplog):
    with caplog.at_level(logging.INFO):
        assert db.registrar_auditoria(evento, usuario="tec1", entidad="x") == 0
    assert _filas(db, evento) == []
    assert any(evento in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("evento", ["modo_prueba_entra", "modo_prueba_salida_forzada",
                                    "aire_atmosferico_cortado_prueba", "login_bloqueado", "login_ok",
                                    "salidas_sin_confirmar", "arranque_camara_no_segura"])
def test_permitidos_se_registran(db, evento):
    assert db.registrar_auditoria(evento, usuario="tec1") > 0
    assert len(_filas(db, evento)) == 1


def test_evento_desconocido_se_registra_con_aviso(db, caplog):
    with caplog.at_level(logging.WARNING):
        assert db.registrar_auditoria("evento_nuevo_x") > 0
    assert len(_filas(db, "evento_nuevo_x")) == 1
    assert any("evento_nuevo_x" in r.getMessage() for r in caplog.records)


def test_lote_omite_los_retirados_y_guarda_el_resto(db):
    ids = db.registrar_auditoria_lote([
        {"evento": "param_ciclo_cambio", "usuario": "a"},
        {"evento": "salida_prueba", "usuario": "a"},
        {"evento": "param_ciclo_cambio", "usuario": "b"},
    ])
    assert len(ids) == 2
    assert len(_filas(db, "param_ciclo_cambio")) == 2 and _filas(db, "salida_prueba") == []
    assert db.registrar_auditoria_lote([{"evento": "logout"}]) == []


def test_tras_cierre_tambien_filtra(db):
    db.registrar_auditoria_tras_cierre("logout")
    db.registrar_auditoria_tras_cierre("apagado_windows_rechazado")
    assert _filas(db, "logout") == [] and len(_filas(db, "apagado_windows_rechazado")) == 1


def test_la_vista_oculta_filas_viejas_de_eventos_retirados(db):
    # filas guardadas antes de la tanda 17 (insertadas como lo hacía el escritor)
    with db._lock:
        for ev in ("salida_prueba", "login_fallido", "login_ok"):
            db._conn.execute("INSERT INTO audit_log (ts, usuario, rol, evento, entidad) "
                             "VALUES ('2026-10-20T10:00:00','viejo','','" + ev + "','')")
        db._conn.commit()
    filas, total = db.consultar_auditoria()
    assert total == 1 and [f["evento"] for f in filas] == ["login_ok"]
    usuarios, tipos = db.valores_auditoria()
    assert tipos == ["login_ok"] and usuarios == ["viejo"]
    assert len(_filas(db)) == 3            # no se borró nada (solo agregar)


# ── BIT-02: instalación ──────────────────────────────────────────────────────

def test_durante_la_instalacion_no_se_escribe_nada(db):
    db.instalacion_en_curso = lambda: True
    for ev in ("idioma_configurado", "unidades_configuradas", "impresora_configurada",
               "param_sistema_cambio", "param_ciclo_cambio", "programa_creado", "login_ok"):
        db.registrar_auditoria(ev, usuario="admin")
    db.registrar_auditoria_lote([{"evento": "param_ciclo_cambio"}])
    db.registrar_auditoria_tras_cierre("apagado_windows_rechazado")
    assert _filas(db) == []
    db.instalacion_en_curso = lambda: False
    db.registrar_auditoria("idioma_configurado")
    assert len(_filas(db)) == 1


def test_si_no_se_sabe_si_termino_se_registra(db):
    def falla():
        raise RuntimeError("perfil ilegible")
    db.instalacion_en_curso = falla
    db.registrar_auditoria("idioma_configurado")
    assert len(_filas(db)) == 1


def test_contexto_instalacion_en_curso_sigue_el_perfil(monkeypatch):
    from autoclave.backend import context as ctx_mod
    from autoclave.installation.clock_guard import ClockTamperedError
    monkeypatch.setattr(ctx_mod, "get_installation_profile", lambda: None)
    assert ctx_mod.instalacion_en_curso() is True
    monkeypatch.setattr(ctx_mod, "get_installation_profile", lambda: object())
    assert ctx_mod.instalacion_en_curso() is False

    def alterado():
        raise ClockTamperedError("reloj")
    monkeypatch.setattr(ctx_mod, "get_installation_profile", alterado)
    assert ctx_mod.instalacion_en_curso() is False


def test_el_backend_conecta_la_supresion_a_la_base():
    fuente = (SRC / "backend" / "context.py").read_text(encoding="utf-8")
    assert "self.db.instalacion_en_curso = instalacion_en_curso" in fuente   # dentro de abrir_base_datos


VALIDAS = {"clave_admin": "admin-nueva-1", "confirmacion_admin": "admin-nueva-1",
           "clave_ingeniero": "inge-nueva-1", "confirmacion_ingeniero": "inge-nueva-1"}


def _datos_instalacion(**cambios):
    d = {"serial_number": "ab-123", "equipment_class": "piso_lab",
         "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
         "vapor_source": "generator", "supply_inputs": {}, "temperature_probes": {},
         "capacidad_litros": 45, "tipo_carga": "V", "contrasenas": VALIDAS}
    d.update(cambios)
    return d


@pytest.fixture
def asistente(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.installation import storage
    from autoclave.ui_qml.bridge import puente_instalacion as pi
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "installation_profile.json")
    monkeypatch.setattr(pi, "zona_horaria_windows", lambda: "SA Pacific Standard Time")
    return pi, tmp_path


def test_al_terminar_el_asistente_una_sola_fila_equipo_instalado(asistente):
    pi, tmp = asistente
    p = pi.PuenteInstalacion(validar_codigo=lambda s, c: True,
                             abrir_bd=lambda: DbManager(tmp / "autoclave.db"),
                             es_semilla=lambda _c: False)
    assert p.validarCodigo("ab-123", "X")
    # la zona horaria se lee al llamar: la función por defecto está parcheada
    assert p.instalar(_datos_instalacion()) == {"ok": True, "error": ""}
    db = DbManager(tmp / "autoclave.db")
    try:
        filas = _filas(db)
    finally:
        db.close()
    assert [f["evento"] for f in filas] == ["equipo_instalado"]
    detalle = filas[0]["detalle"]
    from autoclave._version import version_completa
    assert detalle["serie"] == "AB-123" and detalle["modelo"]
    assert detalle["version"] == version_completa()
    assert "zona_horaria" in detalle


def test_registrar_equipo_instalado_con_zona(tmp_path):
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge import puente_instalacion as pi
    perfil = MagicMock(serial_number="S-1", model_id="AE-45")
    pi.registrar_equipo_instalado(perfil, abrir_bd=lambda: DbManager(tmp_path / "a.db"),
                                  zona=lambda: "SA Pacific Standard Time")
    db = DbManager(tmp_path / "a.db")
    try:
        filas = _filas(db, "equipo_instalado")
    finally:
        db.close()
    assert len(filas) == 1 and filas[0]["detalle"]["zona_horaria"] == "SA Pacific Standard Time"


def test_registrar_equipo_instalado_no_lanza_si_falla_la_base():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge import puente_instalacion as pi

    def falla():
        raise RuntimeError("bd")
    pi.registrar_equipo_instalado(MagicMock(serial_number="S", model_id="M"), abrir_bd=falla,
                                  zona=lambda: "")


# ── BIT-03: el bloqueo no cambia al retirar login_fallido ────────────────────

def _h(clave):
    return contrasenas.hash_password(clave, 1000)


@pytest.fixture
def api(db):
    db.crear_usuario("Tec Uno", "tec1", _h("clave1234"), "tecnico")
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app)


def _login(c, usuario, clave):
    return c.post("/auth/login", json={"usuario": usuario, "clave": clave})


def test_bloqueo_identico_tras_n_intentos_sin_filas_login_fallido(api, db):
    from autoclave.backend.autenticacion import MAX_INTENTOS
    for _ in range(MAX_INTENTOS - 1):
        assert _login(api, "tec1", "mala").status_code == 401
    r = _login(api, "tec1", "mala")
    assert r.status_code == 429 and r.json()["segundos_restantes"] == 300
    assert _login(api, "tec1", "clave1234").status_code == 429     # bloqueado aunque sea correcta
    assert _filas(db, "login_fallido") == []                        # BIT-03: ya no se registra
    assert len(_filas(db, "login_bloqueado")) >= 1                  # sigue el evento de seguridad


def test_login_ok_se_registra_y_logout_no(api, db):
    r = _login(api, "tec1", "clave1234")
    assert r.status_code == 200
    token = r.json()["token"]
    api.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert len(_filas(db, "login_ok")) == 1 and _filas(db, "logout") == []


def test_el_contador_de_bloqueo_no_lee_audit_log():
    fuente = (SRC / "backend" / "autenticacion.py").read_text(encoding="utf-8")
    assert "audit_log" not in fuente and "get_auditoria" not in fuente


# ── clasificación de todo evento del código ──────────────────────────────────

_PATRONES = (
    r'(?:_auditar|registrar_auditoria|registrar_auditoria_tras_cierre|_evento_seguridad)\(\s*"([A-Za-z_]+)"',
    r'"evento"\s*:\s*"([A-Za-z_]+)"',
)


def _eventos_literales():
    eventos = set()
    for ruta in SRC.rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        for patron in _PATRONES:
            eventos |= set(re.findall(patron, texto))
    return eventos


def test_todo_evento_literal_del_codigo_esta_clasificado():
    eventos = _eventos_literales()
    assert {"salida_prueba", "login_ok", "salidas_sin_confirmar"} <= eventos   # el patrón ve el código
    sin_clasificar = eventos - bitacora.EVENTOS_REGISTRADOS - bitacora.EVENTOS_RETIRADOS
    assert sin_clasificar == set()


def test_bit01_del_modo_prueba_solo_tres_eventos():
    del_modo_prueba = {e for e in _eventos_literales() | set(bitacora.EVENTOS)
                       if "prueba" in e and e in bitacora.EVENTOS_REGISTRADOS}
    assert del_modo_prueba == {"modo_prueba_entra", "modo_prueba_salida_forzada",
                               "aire_atmosferico_cortado_prueba"}


# ── BIT-05: categorías ───────────────────────────────────────────────────────

def test_todo_evento_tiene_categoria():
    todos = set(bitacora.EVENTOS) | bitacora.EVENTOS_REGISTRADOS | bitacora.EVENTOS_RETIRADOS
    assert todos - set(bitacora.CATEGORIA_DE_EVENTO) == set()
    assert set(bitacora.CATEGORIA_DE_EVENTO.values()) == set(bitacora.CATEGORIAS)


def test_eventos_de_categoria_sin_retirados():
    seg = bitacora.eventos_de_categoria("seguridad")
    assert "modo_prueba_entra" in seg and "salida_prueba" not in seg
    assert "login_fallido" not in bitacora.eventos_de_categoria("usuarios_sesion")
    assert bitacora.eventos_de_categoria("no_existe") == []


def test_consulta_por_lista_de_eventos(db):
    for ev in ("login_ok", "param_sistema_cambio", "falla_reconocida"):
        db.registrar_auditoria(ev)
    filas, total = db.consultar_auditoria(eventos=bitacora.eventos_de_categoria("seguridad"))
    assert total == 1 and filas[0]["evento"] == "falla_reconocida"
    assert db.consultar_auditoria(eventos=[]) == ([], 0)


def test_textos_de_categorias_y_equipo_instalado():
    for lang in ("es", "en"):
        b = json.loads((SRC / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))["bitacora"]
        for cat in bitacora.CATEGORIAS:
            assert b["categoria"][cat], (lang, cat)
        assert b["ev"]["equipo_instalado"] and b["tipo"]["equipo_instalado"]
