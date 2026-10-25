# tests/test_a9_bitacora_d9_6.py
#
# D9-6 (tanda 9, H18): la bitácora (audit_log) guarda solo lo necesario.
# Se retiran los rechazos de `_rechazar` (rechazo_*), la suspensión de
# pantalla, las órdenes de puerta, la selección de programa y las pruebas de
# correo/impresora; siguen en el log de desarrollo (`logger`). Se conservan
# los eventos de seguridad, los cambios de configuración y la sesión.

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import bitacora
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import fuente_backend

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"

RETIRADOS = (
    "rechazo_401", "rechazo_403", "rechazo_409",
    "suspension_entra", "suspension_sale",
    "puerta_orden", "puerta_orden_rechazada",
    "PROGRAMA_SELECCIONADO", "PROGRAMA_SELECCION_RECHAZADA",
    "correo_prueba", "impresora_prueba", "impresion_ganancias",
)

# Muestra de cada grupo conservado de D9-6
CONSERVADOS = (
    # seguridad
    "falla_reconocida", "ciclo_interrumpido", "apagar_equipo", "modo_prueba_entra",
    "modo_prueba_sale", "salida_prueba", "aire_atmosferico_cortado_prueba",
    # cambios de configuración
    "param_ciclo_cambio", "param_sistema_cambio", "ROLES_SENSOR", "unidades_configuradas",
    "idioma_configurado", "impresora_configurada", "correo_configurado",
    "mantenimiento_registrado", "usuario_creado", "operador_creado",
    "respaldo_exportado", "respaldo_restaurado", "reasignacion_io",
    # sesión
    "login_ok", "logout", "login_fallido", "login_bloqueado",
)


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.core.runtime.unidades import ConfigUnidades
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager()
    c.load_config()
    c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.config_unidades = ConfigUnidades(tmp_path / "u.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def _eventos(db) -> set[str]:
    return {f["evento"] for f in db.get_auditoria()}


# ── Catálogo y fuente ────────────────────────────────────────────────────────

def test_eventos_retirados_fuera_del_catalogo():
    assert set(RETIRADOS) & set(bitacora.EVENTOS) == set()
    assert not any(e.startswith("rechazo_") for e in bitacora.EVENTOS)


def test_eventos_conservados_siguen_en_el_catalogo():
    assert set(CONSERVADOS) <= set(bitacora.EVENTOS)


def test_el_backend_no_audita_los_retirados():
    fuente = fuente_backend() + (RAIZ / "backend" / "server_reasignacion.py").read_text(
        encoding="utf-8")
    auditados = set(re.findall(r'_auditar\(\s*"([A-Za-z_]+)"', fuente))
    assert auditados & set(RETIRADOS) == set()
    assert '_auditar(f"rechazo_' not in fuente
    assert '"suspension_entra" if' not in fuente.split("def registrar_suspension")[1].split(
        "\ndef ")[0] or "_auditar(" not in fuente.split("def registrar_suspension")[1].split(
        "\ndef ")[0]


# ── Retirados: no se escriben en audit_log, sí en el log de desarrollo ──────

def test_suspension_solo_en_el_log(api, caplog):
    client, srv, ctx, cab = api
    with caplog.at_level(logging.INFO):
        assert client.post("/ui/standby", json={"activa": True, "pantalla": "p1"}).status_code == 200
        assert client.post("/ui/standby", json={"activa": False}).status_code == 200
    assert not ({"suspension_entra", "suspension_sale"} & _eventos(ctx.db))
    assert "suspension_entra" in caplog.text and "suspension_sale" in caplog.text


def test_rechazo_401_solo_en_el_log(api, caplog):
    client, srv, ctx, cab = api
    with caplog.at_level(logging.INFO):
        assert client.get("/audit_log").status_code == 401
    assert not any(e.startswith("rechazo_") for e in _eventos(ctx.db))
    assert "rechazo_401" in caplog.text


def test_rechazo_403_solo_en_el_log(api, caplog):
    client, srv, ctx, cab = api
    with caplog.at_level(logging.INFO):
        assert client.get("/audit_log", headers=cab(srv, "operador")).status_code == 403
    assert not any(e.startswith("rechazo_") for e in _eventos(ctx.db))
    assert "rechazo_403" in caplog.text


def test_rechazo_409_solo_en_el_log(api, caplog):
    client, srv, ctx, cab = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    with caplog.at_level(logging.INFO):
        assert client.put("/units", json={"temperatura": "F", "presion": "psi"},
                          headers=cab(srv, "ingeniero")).status_code == 409
    assert not any(e.startswith("rechazo_") for e in _eventos(ctx.db))
    assert "rechazo_409" in caplog.text


# ── Conservados: sí se escriben ─────────────────────────────────────────────

def test_cambio_de_configuracion_queda_en_bitacora(api):
    client, srv, ctx, cab = api
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    assert client.put("/units", json={"temperatura": "F", "presion": "psi"},
                      headers=cab(srv, "ingeniero")).status_code == 200
    (fila,) = ctx.db.get_auditoria(evento="unidades_configuradas")
    assert fila["usuario"] and fila["valor_nuevo"]


def test_inicio_de_sesion_y_fallido_quedan_en_bitacora(api):
    from autoclave.backend import contrasenas
    client, srv, ctx, cab = api
    ctx.db.crear_usuario("Ana", "ana1", contrasenas.hash_password("Clave-Segura-1", 1000), "admin")
    assert client.post("/auth/login", json={"usuario": "ana1", "clave": "mala"}).status_code == 401
    assert client.post("/auth/login",
                       json={"usuario": "ana1", "clave": "Clave-Segura-1"}).status_code == 200
    assert {"login_fallido", "login_ok"} <= _eventos(ctx.db)


def test_evento_de_seguridad_queda_en_bitacora(api):
    client, srv, ctx, cab = api
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.estado.get_flag.return_value = False
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    assert client.post("/fault/reset").status_code == 200
    assert "falla_reconocida" in _eventos(ctx.db)
