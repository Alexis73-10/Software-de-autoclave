"""P4 (tanda 16, D-14.4), backend: NO CONFORME visible.

Tanda 21 (FC-08): el NO CONFORME del ciclo en curso se retiró (ver la sección
correspondiente abajo); solo queda la lectura histórica. Texto original:

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
from tests.helpers.backend_doble import cargar_servidor

pytestmark = pytest.mark.req("T16-S5")

CLAVE = "ticket_ciclo.no_conforme_referencia"


class _Estado:
    """Estado del autoclave con atributos reales (los de F4) y banderas."""

    def __init__(self):
        self.flags = {}
        self.maquina = GlobalState.CICLO
        self.fase_ciclo = "COMPLETADO"
        self.codigo_fallo = ""
        self.valores_fallo = {}
        self.motivo_fallo = ""
        self.cancelado_por = None
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


# ── Tanda 21 (FC-08): NO CONFORME del ciclo en curso retirado ──────────────
# /status y el progreso ya no exponen no_conforme; /cycle/acknowledge no exige
# reconocimiento y POST /cycle/acknowledge-no-conforme ya no existe. El
# historial sigue mostrando los ciclos guardados NO CONFORME tal cual.

def _status(cliente):
    r = cliente.get("/status")
    assert r.status_code == 200, r.text
    return r.json()


def test_status_ya_no_expone_no_conforme(entorno):
    cliente, _, estado, _, _ = entorno
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})
    s = _status(cliente)
    for campo in ("no_conforme", "motivo_no_conforme", "no_conforme_reconocido"):
        assert campo not in s


def test_progreso_ya_no_expone_no_conforme(entorno):
    cliente, ctx, estado, db, _ = entorno
    cid = _ciclo_guardado(db)
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 100.0
    ctx.cycle_logger.hora_fin_pantalla = None
    ctx.control_loop.programa_en_ejecucion.return_value = MagicMock()
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})
    r = cliente.get("/cycle/current/progress").json()
    assert r["activo"] is True
    for campo in ("no_conforme", "motivo_no_conforme", "no_conforme_reconocido"):
        assert campo not in r


@pytest.mark.parametrize("fase", ["COMPLETADO", "FALLO_ESTERILIZACION", "CANCELADO"])
def test_confirmar_con_aviso_viejo_ya_no_se_bloquea(entorno, fase):
    cliente, _, estado, _, _ = entorno
    estado.fase_ciclo = fase
    estado.avisos_ciclo.append({"clave": CLAVE, "sensor": "Referencia 1"})
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 200, r.text
    assert estado.get_flag("CICLO_CONFIRMADO") is True


def test_ruta_de_reconocimiento_retirada(entorno):
    cliente, _, _, db, srv = entorno
    assert cliente.post("/cycle/acknowledge-no-conforme").status_code == 404
    assert all(getattr(r, "path", "") != "/cycle/acknowledge-no-conforme"
               for r in srv.app.routes)
    assert _eventos(db, "ciclo_no_conforme_reconocido") == []


def test_evento_viejo_sigue_reconocido_en_la_bitacora():
    from autoclave.core.runtime import bitacora
    assert "ciclo_no_conforme_reconocido" in bitacora.EVENTOS
    assert bitacora.categoria_de("ciclo_no_conforme_reconocido") == "seguridad"


def test_confirmar_ciclo_conforme_no_cambia(entorno):
    cliente, _, estado, db, _ = entorno
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 200 and r.json() == {"ok": True, "action": "CICLO_CONFIRMADO"}
    assert estado.get_flag("CICLO_CONFIRMADO") is True


def test_confirmar_con_paro_sigue_rechazado_por_paro(entorno):
    cliente, _, estado, _, _ = entorno
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
