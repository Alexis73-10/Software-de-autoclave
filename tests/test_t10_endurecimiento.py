"""T10 (tanda 2026-10-14): endurecimiento remanente. Catálogo de límites
(Anexo B con §1.6), tipos estrictos (RB-05.3), validación al cargar (RB-05.5),
tipo_carga (1.2), auditoría atómica (RB-03.5), copia .bak (RB-04.2),
valor_anterior_esperado (RB-06) y permisos (1.6)."""

import glob
import json
import math
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from tests.backend_doble import modulo_backend

RAIZ = Path(__file__).resolve().parents[1]
PROGRAMAS = sorted(glob.glob(str(RAIZ / "src" / "autoclave" / "cycles" / "*" / "*.json")))


# ── Catálogo ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", PROGRAMAS, ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_ningun_valor_de_los_programas_actuales_se_rechaza(ruta):
    """§1.6: NUNCA rechazar un valor actual de los programas de fábrica."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    assert cp.errores_programa(datos["parameters"]) == []


def test_presion_1_a_400():
    hoja = {"type": "int", "value": 200, "min": 0, "max": 1000}
    assert cp.coercionar(hoja, "globals", ["presion_chaqueta"], 400) == 400
    for malo in (0, 401):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "globals", ["presion_chaqueta"], malo)


def test_temperatura_del_modelo():
    hoja = {"type": "float", "value": 80, "min": 0, "max": 150}
    ruta = ["modo_4", "temperatura_enfriamiento"]
    assert cp.coercionar(hoja, "descompresion", ruta, 1) == 1.0
    with pytest.raises(ValueError):
        cp.coercionar(hoja, "descompresion", ruta, 0)


def test_tiempos_minimo_1_y_ceros_validos():
    hoja = {"type": "float", "value": 4, "min": 0, "max": 9999}
    with pytest.raises(ValueError):
        cp.coercionar(hoja, "esterilizacion", ["tiempo_esterilizacion"], 0)
    assert cp.coercionar(hoja, "esterilizacion", ["tiempo_esterilizacion"], 1) == 1.0
    cero = {"type": "float", "value": 0, "min": 0, "max": 120}
    assert cp.coercionar(cero, "secado", ["tiempo_secado"], 0) == 0.0       # A.3


def test_el_json_mas_estrecho_prevalece():
    hoja = {"type": "float", "value": 134, "min": 100, "max": 140}
    assert cp.rango_efectivo(hoja, "esterilizacion", ["temperatura_esterilizacion"]) == (100, 140)


@pytest.mark.parametrize("hoja, valor", [
    ({"type": "bool", "value": False}, "false"),
    ({"type": "bool", "value": False}, 1),
    ({"type": "int", "value": 1, "min": 0, "max": 9}, 2.5),
    ({"type": "int", "value": 1, "min": 0, "max": 9}, "3"),
    ({"type": "int", "value": 1, "min": 0, "max": 9}, True),
    ({"type": "float", "value": 1.0, "min": 0, "max": 9}, math.nan),
    ({"type": "float", "value": 1.0, "min": 0, "max": 9}, math.inf),
    ({"type": "float", "value": 1.0, "min": 0, "max": 9}, "1.5"),
    ({"type": "enum", "value": "solido", "options": ["solido", "liquido"]}, "gas"),
])
def test_tipos_estrictos(hoja, valor):
    with pytest.raises(ValueError):
        cp.coercionar(hoja, "x", ["p"], valor)


def test_entero_con_flotante_exacto_y_enum():
    assert cp.coercionar({"type": "int", "min": 0, "max": 9}, "x", ["p"], 3.0) == 3
    hoja = {"type": "enum", "options": ["solido", "liquido"]}
    assert cp.coercionar(hoja, "globals", ["tipo_carga"], "liquido") == "liquido"


def test_carga_liquida_exige_modo_4_o_5():
    params = {"globals": {"tipo_carga": {"value": "liquido"}},
              "descompresion": {"modo": {"value": 1}}}
    assert cp.errores_coherencia(params)
    params["descompresion"]["modo"]["value"] = 4
    assert cp.errores_coherencia(params) == []


def test_todos_los_programas_traen_tipo_carga_solido():
    for ruta in PROGRAMAS:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        hoja = datos["parameters"]["globals"]["tipo_carga"]
        if datos.get("cycle_number") == 4:
            continue                                  # Líquidos (T11)
        assert hoja["value"] == "solido" and hoja["type"] == "enum"
        assert hoja["options"] == ["solido", "liquido"]


# ── Programa: set_param con el catálogo y carga ────────────────────────────

def _cycle(tmp_path, cambios=None):
    from autoclave.core.managers.cycle_manager import Cycle
    datos = json.loads(Path(PROGRAMAS[0]).read_text(encoding="utf-8"))
    for (fase, clave), valor in (cambios or {}).items():
        datos["parameters"][fase][clave]["value"] = valor
    return Cycle("prog", "Programa", datos["parameters"], 9)


def test_set_param_usa_el_catalogo_y_tipos_estrictos(tmp_path):
    c = _cycle(tmp_path)
    with pytest.raises(ValueError):
        c.set_param("globals", ["presion_chaqueta"], 450)
    with pytest.raises(ValueError):
        c.set_param("globals", ["F0"], "false")
    with pytest.raises(ValueError):
        c.set_param("globals", ["tipo_carga"], "liquido")   # modo 1: incoherente
    assert c.get_param("globals", "tipo_carga") == "solido"  # no muta si falla
    c.set_param("descompresion", ["modo"], 4)
    with pytest.raises(ValueError):                          # SAF-06 de T11: con prevacío
        c.set_param("globals", ["tipo_carga"], "liquido")
    assert c.get_param("globals", "tipo_carga") == "solido"


def test_liquidos_reglas_de_coherencia():
    """1.2 + SAF-05/06 de T11: modo 4/5, sin prevacío ni secado, sin apertura
    automática y contrapresión >= P_sat(t_est) + 30 kPa."""
    from autoclave.core.managers.cycle_manager import Cycle
    ruta = next(r for r in PROGRAMAS if r.endswith("liquidos.json"))
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    c = Cycle("liq", "Líquidos", datos["parameters"], 4)
    for fase, path, valor in (
            ("descompresion", ["modo"], 1),
            ("prevacio", ["conteo_pulso_a"], 2),
            ("secado", ["tiempo_secado"], 5.0),
            ("finalizacion", ["apertura_automatica"], True),
            ("descompresion", ["modo_4", "presion_camara_enfriamiento"], 200)):
        with pytest.raises(ValueError):
            c.set_param(fase, path, valor)
    assert cp.errores_programa(c.parameters) == []


def test_programa_fuera_de_catalogo_queda_danado(tmp_path, monkeypatch):
    from autoclave.core.managers.cycle_manager import CycleManager
    carpeta = tmp_path / "cycles" / "user"
    carpeta.mkdir(parents=True)
    datos = json.loads(Path(PROGRAMAS[0]).read_text(encoding="utf-8"))
    datos["parameters"]["globals"]["presion_chaqueta"]["value"] = 0
    (carpeta / "malo.json").write_text(json.dumps(datos), encoding="utf-8")
    cm = CycleManager()
    cm._load_from_folder(str(carpeta), source="user")
    malo = next(c for c in cm.cycles.values() if getattr(c, "_path", "").endswith("malo.json"))
    assert malo.danado and "presion_chaqueta" in malo.danado[0]
    assert any("malo.json" in e for e in cm.errores_carga)


# ── Endpoint PATCH /cycle/parameter ────────────────────────────────────────

@pytest.fixture
def cliente(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.managers.cycle_manager import Cycle
    from tests.backend_doble import cabecera, cargar_servidor
    datos = json.loads(Path(PROGRAMAS[0]).read_text(encoding="utf-8"))
    ruta = tmp_path / "prog.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    cycle = Cycle("prog", "Programa", datos["parameters"], 9)
    cycle.source, cycle._path = "user", str(ruta)
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    ctx.cycle_manager.cycles = {"prog": cycle}
    srv, _ = cargar_servidor(ctx)
    def con_rol(rol):
        return TestClient(srv.app, headers=cabecera(srv, rol))
    return con_rol, ctx, cycle, ruta


def _patch(client, valor, **extra):
    return client.patch("/cycle/parameter", json={
        "cycle_id": "prog", "fase": "globals", "path": ["presion_chaqueta"], "value": valor, **extra})


def test_tecnico_puede_editar_parametros(cliente):
    con_rol, ctx, cycle, ruta = cliente
    assert _patch(con_rol("tecnico"), 310).status_code == 200
    assert cycle.get_param("globals", "presion_chaqueta") == 310
    assert _patch(con_rol("admin"), 320).status_code == 403


def test_fuera_de_catalogo_es_valor_invalido(cliente):
    con_rol, *_ = cliente
    r = _patch(con_rol("ingeniero"), 450)
    assert r.status_code == 422 and r.json()["codigo"] == "VALOR_INVALIDO"


def test_valor_anterior_esperado(cliente):
    con_rol, ctx, cycle, _ = cliente
    actual = cycle.get_param("globals", "presion_chaqueta")
    r = _patch(con_rol("ingeniero"), 310, valor_anterior_esperado=actual + 1)
    assert r.status_code == 409 and r.json()["codigo"] == "VALOR_CAMBIO"
    assert r.json()["valor_actual"] == actual
    assert _patch(con_rol("ingeniero"), 310, valor_anterior_esperado=actual).status_code == 200


def test_sin_auditoria_el_cambio_se_revierte(cliente):
    """RB-03.5: memoria y archivo vuelven al valor previo."""
    con_rol, ctx, cycle, ruta = cliente
    previo = cycle.get_param("globals", "presion_chaqueta")
    # X9 (tanda 9, D9-13.3 SAF-01): las filas del cambio van en un lote
    ctx.db.registrar_auditoria_lote.side_effect = sqlite3.OperationalError("database is locked")
    r = _patch(con_rol("ingeniero"), 310)
    assert r.status_code == 503 and r.json()["codigo"] == "BASE_OCUPADA"
    assert cycle.get_param("globals", "presion_chaqueta") == previo
    en_disco = json.loads(ruta.read_text(encoding="utf-8"))
    assert en_disco["parameters"]["globals"]["presion_chaqueta"]["value"] == previo


def test_escritura_deja_copia_bak(cliente):
    con_rol, ctx, cycle, ruta = cliente
    original = ruta.read_text(encoding="utf-8")
    assert _patch(con_rol("ingeniero"), 310).status_code == 200
    assert ruta.with_name(ruta.name + ".bak").read_text(encoding="utf-8") == original


def test_programa_danado_no_se_edita_ni_selecciona(cliente):
    con_rol, ctx, cycle, _ = cliente
    cycle.danado = ["globals.presion_chaqueta: fuera de rango"]
    r = _patch(con_rol("ingeniero"), 310)
    assert r.status_code == 409 and r.json()["codigo"] == "PROGRAMA_NO_EDITABLE"
    r = con_rol("ingeniero").post("/cycle/select", json={"cycle_id": "prog"})
    assert r.status_code == 409
    ctx.control_loop.set_active_cycle.assert_not_called()


def test_sin_bd_no_se_edita(cliente):
    con_rol, ctx, cycle, _ = cliente
    ctx.sin_base_de_datos = True
    assert _patch(con_rol("ingeniero"), 310).status_code == 503


# ── Permisos de Opciones (1.6) ─────────────────────────────────────────────

def test_permisos_opciones():
    from autoclave.ui_qml.domain import permisos_opciones as po
    assert po.puede_ver("conectividad", "tecnico")
    assert po.puede_ver("conectividad", "admin") and po.puede_ver("conectividad", "ingeniero")
    assert po.puede_ver("usuarios", "admin") and po.puede_ver("usuarios", "ingeniero")
    assert po.puede_ver("usuarios", "tecnico")      # O2b (1.9): lo ve en solo lectura
    assert po.motivo_gestion_usuarios("tecnico") == "rol"
    assert po.puede_ver("parametros_ciclo", "tecnico") and not po.puede_ver("parametros_ciclo", "admin")
    # técnico: estado distinto de CICLO (igual que el backend); ingeniero siempre
    assert po.edicion_permitida("FALLA", "tecnico")
    assert po.edicion_permitida("PREPARADO", "tecnico")
    assert not po.edicion_permitida("CICLO", "tecnico")
    assert not po.edicion_permitida(None, "tecnico")
    assert po.edicion_permitida("CICLO", "ingeniero")


def test_audit_log_es_de_solo_anexar(tmp_path):
    """RB-03.7: triggers que bloquean UPDATE y DELETE."""
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(tmp_path / "a.db")
    db.registrar_auditoria("prueba", usuario="u", entidad="e")
    for sql in ("UPDATE audit_log SET evento='x'", "DELETE FROM audit_log"):
        with pytest.raises(sqlite3.DatabaseError, match="solo anexar"):
            with db._lock:
                db._conn.execute(sql)
    db.registrar_auditoria("otra", usuario="u")         # anexar sigue funcionando


def test_t11_liquidos_solo_en_equipos_con_liquidos(monkeypatch):
    from fastapi.testclient import TestClient
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.apagando = False
    ctx.control_loop.cycle.danado = []
    ctx.control_loop.cycle.get_param.side_effect = lambda *a, default=None: (
        "liquido" if a == ("globals", "tipo_carga") else default)
    ctx.estado.get_flag.return_value = True
    ctx.cap.has_liquids = False
    srv, _ = cargar_servidor(ctx)
    monkeypatch.setattr(modulo_backend("rutas.ciclo").sc, "verificar_inicio", lambda *a: None)
    client = TestClient(srv.app)
    r = client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == "carga_liquida_no_disponible"
    ctx.cap.has_liquids = True
    assert client.post("/cycle/start").status_code == 200
