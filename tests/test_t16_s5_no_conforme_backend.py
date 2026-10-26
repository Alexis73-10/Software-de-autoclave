"""P4 (tanda 16, D-14.4), backend: NO CONFORME visible.

- /status y GET /cycle/current/progress exponen no_conforme, su motivo y si
  el operador ya reconoció que la carga no es liberable;
- POST /cycle/acknowledge se rechaza (409 no_conforme_sin_reconocer) con un
  ciclo NO CONFORME sin reconocer, y se acepta después del reconocimiento;
- POST /cycle/acknowledge-no-conforme pone estado.no_conforme_reconocido y se
  audita con el usuario de la sesión;
- el historial (/cycle/list, /cycle/summary, /cycle/history, ticket y
  lecturas) expone no_conforme derivado de avisos_ticket;
- un ciclo conforme no cambia.
"""

import json
import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor

pytestmark = pytest.mark.req("T16-S5")

CLAVE = "ticket_ciclo.no_conforme_referencia"


class _Estado:
    """Estado del autoclave con atributos reales (los de F4) y banderas."""

    def __init__(self):
        self.flags = {}
        self.maquina = GlobalState.CICLO
        self.fase_ciclo = "COMPLETADO"
        self.no_conforme = False
        self.motivo_no_conforme = ""
        self.no_conforme_reconocido = False
        self.avisos_ciclo = []
        self.operador_inicio = "ana"
        self.estado_puertas = {}
        self.sensores_temp = {}
        self.sensores_pres = {}
        self.sensores_di = {}
        self.salidas_do = {}
        self.exposicion_restante_s = None

    def get_machine_state(self):
        return self.maquina

    def get_flag(self, nombre):
        return self.flags.get(nombre, False)

    def set_flag(self, nombre, valor):
        self.flags[nombre] = valor


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    estado = _Estado()
    ctx = MagicMock()
    ctx.db = db
    ctx.estado = estado
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.test_mode_active = False
    ctx.cycle_logger.ciclo_id_pantalla = None
    ctx.cycle_logger.transcurrido_s.return_value = None
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), ctx, estado, db, srv
    db.close()


def _marcar_no_conforme(estado):
    estado.no_conforme = True
    estado.motivo_no_conforme = CLAVE
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})


def _eventos(db, evento):
    return db.get_auditoria(evento=evento, limite=100)


def _detalle(fila) -> dict:
    d = fila["detalle"]
    return json.loads(d) if isinstance(d, str) else d


def _ciclo_guardado(db, avisos=None, resultado="COMPLETADO"):
    i = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo="t", nombre="N",
                       temp_ester=134, tiempo_ester=4, modelo="M", serie="S", version_sw="1")
    extra = {"avisos_ticket": {"sin_datos_s": None, "avisos": avisos}} if avisos else {}
    db.cerrar_ciclo(i, resultado, **extra)
    return i


# ── /status ─────────────────────────────────────────────────────────────────

def _status(cliente):
    r = cliente.get("/status")
    assert r.status_code == 200, r.text
    return r.json()


def test_status_ciclo_conforme(entorno):
    cliente, _, _, _, _ = entorno
    s = _status(cliente)
    assert s["no_conforme"] is False
    assert s["motivo_no_conforme"] == ""
    assert s["no_conforme_reconocido"] is False


def test_status_ciclo_no_conforme_y_reconocido(entorno):
    cliente, _, estado, _, _ = entorno
    _marcar_no_conforme(estado)
    s = _status(cliente)
    assert (s["no_conforme"], s["motivo_no_conforme"], s["no_conforme_reconocido"]) == \
        (True, CLAVE, False)
    estado.no_conforme_reconocido = True
    assert _status(cliente)["no_conforme_reconocido"] is True


def test_status_reconocido_sin_no_conforme_no_cuenta(entorno):
    """Falla cerrada: un reconocimiento suelto no se publica sin NO CONFORME."""
    cliente, _, estado, _, _ = entorno
    estado.no_conforme_reconocido = True
    assert _status(cliente)["no_conforme_reconocido"] is False


def test_status_no_conforme_por_aviso_aunque_falte_la_bandera(entorno):
    """Defensa en profundidad: el aviso en avisos_ciclo basta."""
    cliente, _, estado, _, _ = entorno
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})
    s = _status(cliente)
    assert s["no_conforme"] is True and s["motivo_no_conforme"] == CLAVE


# ── progreso ────────────────────────────────────────────────────────────────

def test_progreso_expone_no_conforme(entorno):
    cliente, ctx, estado, db, _ = entorno
    cid = _ciclo_guardado(db)
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 120.0
    ctx.control_loop.programa_en_ejecucion.return_value = MagicMock(id="t")
    ctx.cap = MagicMock()
    r = cliente.get("/cycle/current/progress").json()
    assert r["activo"] is True
    assert (r["no_conforme"], r["no_conforme_reconocido"]) == (False, False)
    _marcar_no_conforme(estado)
    r = cliente.get("/cycle/current/progress").json()
    assert (r["no_conforme"], r["motivo_no_conforme"], r["no_conforme_reconocido"]) == \
        (True, CLAVE, False)


# ── acknowledge y reconocimiento ─────────────────────────────────────────────

def test_confirmar_no_conforme_sin_reconocer_409(entorno):
    cliente, _, estado, _, _ = entorno
    _marcar_no_conforme(estado)
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 409
    assert r.json()["codigo"] == "no_conforme_sin_reconocer"
    assert not estado.get_flag("CICLO_CONFIRMADO")


def test_confirmar_bloqueado_solo_con_el_aviso(entorno):
    cliente, _, estado, _, _ = entorno
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 409 and r.json()["codigo"] == "no_conforme_sin_reconocer"
    assert not estado.get_flag("CICLO_CONFIRMADO")


@pytest.mark.parametrize("fase", ["COMPLETADO", "FALLO_ESTERILIZACION", "CANCELADO"])
def test_confirmar_no_conforme_bloqueado_en_todo_resultado(entorno, fase):
    """DECISIÓN SIN CONFIRMAR: también si el ciclo NO CONFORME terminó en fallo
    o cancelado (lo más seguro: el reconocimiento no cuesta nada)."""
    cliente, _, estado, _, _ = entorno
    estado.fase_ciclo = fase
    _marcar_no_conforme(estado)
    assert cliente.post("/cycle/acknowledge").status_code == 409
    assert not estado.get_flag("CICLO_CONFIRMADO")
    assert cliente.post("/cycle/acknowledge-no-conforme").status_code == 200
    assert cliente.post("/cycle/acknowledge").status_code == 200
    assert estado.get_flag("CICLO_CONFIRMADO") is True


def test_reconocer_y_confirmar_se_audita_con_el_usuario(entorno):
    cliente, ctx, estado, db, srv = entorno
    cid = _ciclo_guardado(db)
    ctx.cycle_logger.ciclo_id_pantalla = cid
    _marcar_no_conforme(estado)
    r = cliente.post("/cycle/acknowledge-no-conforme",
                     headers=cabecera(srv, "operador", usuario="luis"))
    assert r.status_code == 200, r.text
    assert estado.no_conforme_reconocido is True
    filas = _eventos(db, "ciclo_no_conforme_reconocido")
    assert len(filas) == 1
    fila = dict(filas[0])
    assert fila["usuario"] == "luis" and fila["rol"] == "operador"
    detalle = _detalle(fila)
    assert detalle["motivo"] == CLAVE
    assert detalle["operador_ciclo"] == "ana"
    assert detalle["numero_ciclo"] == db.get_ciclo(cid)["numero_ciclo"]
    assert "sin_sesion" not in detalle
    # después del reconocimiento, CONFIRMAR se acepta
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 200
    assert estado.get_flag("CICLO_CONFIRMADO") is True


def test_reconocer_sin_sesion_queda_auditado_sin_usuario(entorno):
    cliente, _, estado, db, _ = entorno
    _marcar_no_conforme(estado)
    assert cliente.post("/cycle/acknowledge-no-conforme").status_code == 200
    fila = dict(_eventos(db, "ciclo_no_conforme_reconocido")[0])
    assert fila["usuario"] == ""
    assert _detalle(fila)["sin_sesion"] is True


def test_reconocer_dos_veces_audita_una(entorno):
    cliente, _, estado, db, _ = entorno
    _marcar_no_conforme(estado)
    assert cliente.post("/cycle/acknowledge-no-conforme").status_code == 200
    r = cliente.post("/cycle/acknowledge-no-conforme")
    assert r.status_code == 200 and r.json().get("ya_reconocido") is True
    assert len(_eventos(db, "ciclo_no_conforme_reconocido")) == 1


def test_reconocer_un_ciclo_conforme_409(entorno):
    cliente, _, estado, db, _ = entorno
    r = cliente.post("/cycle/acknowledge-no-conforme")
    assert r.status_code == 409 and r.json()["codigo"] == "ciclo_conforme"
    assert estado.no_conforme_reconocido is False
    assert _eventos(db, "ciclo_no_conforme_reconocido") == []


def test_reconocer_a_mitad_de_ciclo_409(entorno):
    cliente, _, estado, _, _ = entorno
    estado.fase_ciclo = "ESTERILIZACION"
    _marcar_no_conforme(estado)
    r = cliente.post("/cycle/acknowledge-no-conforme")
    assert r.status_code == 409 and r.json()["codigo"] == "sin_resultado"
    assert estado.no_conforme_reconocido is False


def test_reconocer_fuera_de_ciclo_409(entorno):
    cliente, _, estado, _, _ = entorno
    estado.maquina = GlobalState.PREPARADO
    _marcar_no_conforme(estado)
    r = cliente.post("/cycle/acknowledge-no-conforme")
    assert r.status_code == 409 and r.json()["codigo"] == "estado_no_permitido"
    assert estado.no_conforme_reconocido is False


def test_reconocer_no_confirma_el_ciclo(entorno):
    cliente, _, estado, _, _ = entorno
    _marcar_no_conforme(estado)
    assert cliente.post("/cycle/acknowledge-no-conforme").status_code == 200
    assert not estado.get_flag("CICLO_CONFIRMADO")


def test_confirmar_ciclo_conforme_no_cambia(entorno):
    cliente, _, estado, db, _ = entorno
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 200 and r.json() == {"ok": True, "action": "CICLO_CONFIRMADO"}
    assert estado.get_flag("CICLO_CONFIRMADO") is True
    assert _eventos(db, "ciclo_no_conforme_reconocido") == []


def test_confirmar_no_conforme_con_paro_sigue_rechazado_por_paro(entorno):
    cliente, _, estado, _, _ = entorno
    _marcar_no_conforme(estado)
    estado.no_conforme_reconocido = True
    estado.set_flag("PARO_EMERGENCIA", True)
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"


# ── historial ───────────────────────────────────────────────────────────────

def test_historial_expone_no_conforme(entorno):
    cliente, _, estado, db, _ = entorno
    estado.maquina = GlobalState.PREPARADO
    conforme = _ciclo_guardado(db)
    nc = _ciclo_guardado(db, avisos=[{"clave": CLAVE, "sensor": "Referencia 1"}])
    otro_aviso = _ciclo_guardado(db, avisos=["Uniformidad termica fuera de rango"])

    lista = {c["id"]: c for c in cliente.get("/cycle/list").json()["ciclos"]}
    assert (lista[nc]["no_conforme"], lista[nc]["motivo_no_conforme"]) == (True, CLAVE)
    assert lista[nc]["resultado"] == "COMPLETADO"      # el resultado técnico no cambia
    # un ciclo conforme no cambia: sin los campos nuevos
    assert "no_conforme" not in lista[conforme] and "motivo_no_conforme" not in lista[conforme]
    assert "no_conforme" not in lista[otro_aviso]

    ultimo = cliente.get("/cycle/summary").json()["ultimo_ciclo"]
    assert ultimo["id"] == otro_aviso and "no_conforme" not in ultimo

    hist = {c["id"]: c for c in cliente.get("/cycle/history").json()}
    assert hist[nc]["no_conforme"] is True and "no_conforme" not in hist[conforme]

    for ruta in ("ticket", "readings"):
        c = cliente.get(f"/cycle/history/{nc}/{ruta}").json()["ciclo"]
        assert c["no_conforme"] is True and c["resultado"] == "COMPLETADO"
        assert "no_conforme" not in cliente.get(f"/cycle/history/{conforme}/{ruta}").json()["ciclo"]


def test_historial_avisos_danados_no_marcan(entorno):
    cliente, _, estado, db, _ = entorno
    estado.maquina = GlobalState.PREPARADO
    i = _ciclo_guardado(db)
    db._conn.execute("UPDATE ciclos SET avisos_ticket='{no es json' WHERE id=?", (i,))
    db._conn.commit()
    c = cliente.get("/cycle/list").json()["ciclos"][0]
    assert "no_conforme" not in c


def test_resumen_con_ultimo_ciclo_no_conforme(entorno):
    cliente, _, estado, db, _ = entorno
    estado.maquina = GlobalState.PREPARADO
    _ciclo_guardado(db)
    nc = _ciclo_guardado(db, avisos=[{"clave": CLAVE, "sensor": "Referencia 1"}])
    ultimo = cliente.get("/cycle/summary").json()["ultimo_ciclo"]
    assert ultimo["id"] == nc and ultimo["no_conforme"] is True
    assert ultimo["motivo_no_conforme"] == CLAVE and ultimo["resultado"] == "COMPLETADO"
