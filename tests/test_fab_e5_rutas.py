# tests/test_fab_e5_rutas.py
#
# Modo fábrica, Etapa 5: rutas del cierre de fabricación (GET/POST
# /fabrica/cierre), precondiciones (§6.1), bloqueo de las escrituras durante
# el cierre (409 cierre_en_curso) y P-05 (ENTREGADO: 409 solo_modo_fabrica
# para todos). El equipo es el de test_fab_e5_cierre (carpetas temporales).

import threading
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import cierre_fabrica as cf
from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend
from tests.test_fab_e5_cierre import Equipo, _Config

pytestmark = pytest.mark.req("DF-04", "DF-05", "FAB-01", "FAB-02")


class Api:
    def __init__(self, monkeypatch, equipo: Equipo, modo_fabrica: bool = True):
        self.equipo = equipo
        ctx = MagicMock()
        ctx.db = equipo.db
        ctx.sin_base_de_datos = False
        ctx.modo_fabrica.return_value = modo_fabrica
        ctx.cycle_manager = equipo.cm
        ctx.config_manager = _Config()
        ctx.profile.serial_number = "SN260001"
        ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
        ctx.estado.get_flag.return_value = False
        loop = ctx.control_loop
        loop.test_mode_active = False
        loop.apagando = False
        loop.datos_vigentes = True
        loop.salidas_sin_confirmar_pendiente = False
        loop.estado_seguro.requiere_confirmacion = False
        self.srv, self.ctx = cargar_servidor(ctx)
        self.fab = modulo_backend("rutas.fabrica")
        apagado = modulo_backend("rutas.apagado")
        from autoclave.backend import reinicio
        monkeypatch.setattr(reinicio, "disponible", lambda: True)
        self.motivos_camara_real = self.fab._motivos_camara
        monkeypatch.setattr(self.fab, "_motivos_camara", lambda: [])
        monkeypatch.setattr(self.fab, "_rutas", lambda: equipo.rutas)
        monkeypatch.setattr(self.fab, "_fuentes", equipo.fuentes)
        monkeypatch.setattr(self.fab, "_unidades_usb",
                            lambda: [{"ruta": str(equipo.usb), "libre_bytes": 50 * 10**9}])
        monkeypatch.setattr(self.fab, "ESPERA_ANTES_DE_REINICIAR_S", 0.0)
        self.reinicios = []
        self.reiniciado = threading.Event()
        self.bloqueos = []

        def bloquear(entidad, sesion=None, deshacer=None):
            self.bloqueos.append(entidad)
            return GlobalState.PREPARADO

        def lanzar(motivo, estado, sesion=None, entidad="", detalle=None):
            self.reinicios.append((motivo, detalle))
            self.reiniciado.set()
        monkeypatch.setattr(apagado, "bloquear_para_reinicio", bloquear)
        monkeypatch.setattr(apagado, "lanzar_reinicio", lanzar)
        self.reautenticaciones = []
        monkeypatch.setattr(self.fab, "reautenticar",
                            lambda clave, sesion, entidad, origen:
                            self.reautenticaciones.append((clave, origen)))
        self.client = TestClient(self.srv.app)
        self.h = cabecera(self.srv, "ingeniero", usuario="ana")

    def esperar(self, tope_s: float = 60.0) -> dict:
        limite = time.monotonic() + tope_s
        while time.monotonic() < limite:
            e = self.client.get("/fabrica/cierre", headers=self.h).json()["cierre"]
            if not e["en_curso"] or self.reiniciado.is_set():
                return e
            time.sleep(0.05)
        raise AssertionError("el cierre no terminó")


@pytest.fixture
def equipo(tmp_path):
    e = Equipo(tmp_path)
    yield e
    try:
        e.db.close()
    except Exception:
        pass


@pytest.fixture
def api(monkeypatch, equipo):
    a = Api(monkeypatch, equipo)
    yield a
    with a.fab._lock:
        a.fab._estado.update(en_curso=False, etapa="", error=None, resultado=None)


def _intacto(e: Equipo) -> None:
    assert not e.rutas.marca.exists() and not e.rutas.base_nueva.exists()
    assert not list(e.data.glob("*" + cf.SUFIJO_NUEVO)) and not e.rutas.defecto_nuevo.exists()
    assert e.db.conteos_cierre_fabrica()["ciclos"] == 2


# ── GET ──────────────────────────────────────────────────────────────────
def test_get_resumen_usb_y_precondiciones(api):
    r = api.client.get("/fabrica/cierre", headers=api.h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["resumen"]["conteos"]["ciclos"] == 2
    assert d["resumen"]["conteos"]["usuarios_prueba"] == 2
    assert d["usb"]["unidad"] == str(api.equipo.usb) and d["usb"]["estimado_bytes"] > 0
    assert d["precondiciones"] == {"ok": True, "motivos": []}
    assert d["cierre"]["en_curso"] is False and d["cierre"]["etapas"] == list(cf.ETAPAS)


def test_get_sin_usb_lo_dice(api, monkeypatch):
    monkeypatch.setattr(api.fab, "_unidades_usb", lambda: [])
    d = api.client.get("/fabrica/cierre", headers=api.h).json()
    assert d["precondiciones"]["ok"] is False
    assert [m["codigo"] for m in d["precondiciones"]["motivos"]] == ["usb_ausente"]


def test_get_tecnico_403(api):
    assert api.client.get("/fabrica/cierre",
                          headers=cabecera(api.srv, "tecnico")).status_code == 403


# ── P-05: ENTREGADO ──────────────────────────────────────────────────────
@pytest.mark.req("P-05")
def test_p05_entregado_409_para_todos(monkeypatch, equipo):
    a = Api(monkeypatch, equipo, modo_fabrica=False)
    for h in ({}, a.h, cabecera(a.srv, "tecnico"), cabecera(a.srv, "admin")):
        r = a.client.get("/fabrica/cierre", headers=h)
        assert r.status_code == 409 and r.json()["codigo"] == "solo_modo_fabrica"
        r = a.client.post("/fabrica/cierre", headers=h, json={"clave": "x"})
        assert r.status_code == 409 and r.json()["codigo"] == "solo_modo_fabrica"
    assert a.reautenticaciones == []
    _intacto(equipo)


# ── POST ─────────────────────────────────────────────────────────────────
@pytest.mark.req("P-04")
def test_post_cierre_completo_hasta_el_reinicio(api):
    r = api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "secreta"})
    assert r.status_code == 202, r.text
    assert api.reautenticaciones == [("secreta", "cierre_fabrica")]
    assert api.reiniciado.wait(60)
    e = api.client.get("/fabrica/cierre", headers=api.h).json()["cierre"]
    assert e["etapa"] == "reiniciando" and e["error"] is None and e["progreso"] == 1.0
    res = e["resultado"]
    assert res["nombre_paquete"].startswith("liberacion_SN260001_")
    assert pl.verificar_paquete(res["ruta_paquete"]) == res["hash_paquete"]
    assert api.equipo.rutas.marca.exists() and api.equipo.rutas.base_nueva.exists()
    assert api.bloqueos == ["/fabrica/cierre"]
    assert api.reinicios == [("cierre de fabricación", {"paquete": res["nombre_paquete"]})]
    # durante el reinicio el cierre sigue «en curso»: las escrituras se rechazan
    r = api.client.post("/cycle/start", json={})
    assert r.status_code == 409 and r.json()["codigo"] == "cierre_en_curso"
    # la fase 2 al arrancar deja el equipo entregado
    api.equipo.db.close()
    assert cf.completar_cierre_si_pendiente(api.equipo.rutas)["completado"] is True


def test_post_sin_clave_403(monkeypatch, equipo):
    a = Api(monkeypatch, equipo)
    from autoclave.backend import dependencias
    monkeypatch.setattr(a.fab, "reautenticar", dependencias.reautenticar)
    r = a.client.post("/fabrica/cierre", headers=a.h, json={})
    assert r.status_code == 403 and r.json()["codigo"] == "reautenticacion_requerida"
    _intacto(equipo)


@pytest.mark.parametrize("caso, motivo", [
    ("ciclo", "ciclo"), ("falla", "falla"), ("modo_prueba", "modo_prueba"),
    ("paro", "paro"), ("confirmacion", "confirmacion_pendiente"),
    ("camara", "camara_no_segura"), ("sin_base", "sin_base"),
    ("reinicio", "reinicio_no_disponible")])
def test_post_precondiciones_409(api, monkeypatch, caso, motivo):
    ctx = api.ctx
    if caso == "ciclo":
        ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    elif caso == "falla":
        ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    elif caso == "modo_prueba":
        ctx.control_loop.test_mode_active = True
    elif caso == "paro":
        ctx.estado.get_flag.return_value = True
    elif caso == "confirmacion":
        ctx.control_loop.estado_seguro.requiere_confirmacion = True
    elif caso == "camara":
        monkeypatch.setattr(api.fab, "_motivos_camara", lambda: ["Temperatura 92 °C"])
    elif caso == "sin_base":
        ctx.sin_base_de_datos = True
    else:
        from autoclave.backend import reinicio
        monkeypatch.setattr(reinicio, "disponible", lambda: False)
    r = api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "x"})
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == "cierre_estado_no_permitido" and r.json()["motivo"] == motivo
    d = api.client.get("/fabrica/cierre", headers=api.h).json()
    assert motivo in [m["codigo"] for m in d["precondiciones"]["motivos"]]
    _intacto(api.equipo)
    assert list(api.equipo.usb.iterdir()) == []


def test_camara_sin_datos_vigentes_no_es_segura(api):
    # la evaluación real con datos no vigentes da su motivo (o falla cerrada)
    api.ctx.control_loop.datos_vigentes = False
    assert api.motivos_camara_real() != []


@pytest.mark.req("P-07")
@pytest.mark.parametrize("caso, codigo", [("sin_usb", "usb_ausente"),
                                          ("no_escribible", "usb_no_escribible"),
                                          ("sin_espacio", "usb_sin_espacio")])
def test_p07_post_usb_rechazada_y_nada_cambia(api, monkeypatch, caso, codigo):
    if caso == "sin_usb":
        monkeypatch.setattr(api.fab, "_unidades_usb", lambda: [])
    elif caso == "no_escribible":
        monkeypatch.setattr(pl, "_probar_escritura",
                            lambda c: (_ for _ in ()).throw(PermissionError("protegida")))
    else:
        monkeypatch.setattr(pl, "_espacio_libre", lambda c: 1024)
    r = api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "x"})
    assert r.status_code == 409 and r.json()["codigo"] == codigo
    assert api.client.get("/fabrica/cierre", headers=api.h).json()["cierre"]["en_curso"] is False
    _intacto(api.equipo)
    assert list(api.equipo.usb.iterdir()) == []


def test_post_dos_veces_409_cierre_en_curso(api):
    with api.fab._lock:
        api.fab._estado.update(en_curso=True, etapa="paquete")
    r = api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "x"})
    assert r.status_code == 409 and r.json()["codigo"] == "cierre_en_curso"
    assert api.reautenticaciones == []


def test_fallo_en_la_fase1_publica_el_error_y_no_cambia_nada(api, monkeypatch):
    def falla(*_a, **_k):
        raise OSError("disco")
    monkeypatch.setattr(cf, "_crear_tablas_auditoria", falla)
    assert api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "x"}).status_code == 202
    e = api.esperar()
    assert e["en_curso"] is False and e["error"]["codigo"] == "error_cierre"
    assert api.reinicios == [] and api.bloqueos == []
    _intacto(api.equipo)


def test_rechazo_al_detener_el_lazo_borra_los_temporales(api, monkeypatch):
    from autoclave.backend.dependencias import RechazoApi
    apagado = modulo_backend("rutas.apagado")

    def bloquear(entidad, sesion=None, deshacer=None):
        deshacer()
        raise RechazoApi(409, "modo_prueba_activo", "modo prueba")
    monkeypatch.setattr(apagado, "bloquear_para_reinicio", bloquear)
    assert api.client.post("/fabrica/cierre", headers=api.h, json={"clave": "x"}).status_code == 202
    e = api.esperar()
    assert e["error"]["codigo"] == "modo_prueba_activo" and api.reinicios == []
    _intacto(api.equipo)


# ── bloqueo de escrituras durante el cierre ──────────────────────────────
@pytest.mark.parametrize("metodo, ruta, bloqueada", [
    ("POST", "/cycle/start", True), ("POST", "/io/test/enter", True),
    ("POST", "/doors/Puerta 1/open", True), ("PATCH", "/global_params/x", True),
    ("POST", "/usuarios", True), ("DELETE", "/fabrica/programas/x", True),
    ("GET", "/status", False), ("POST", "/auth/logout", False), ("POST", "/ui/activity", False),
    ("POST", "/alarms/CIC-04/acknowledge", False), ("POST", "/system/shutdown", False),
    ("POST", "/fabrica/cierre", False)])
def test_rutas_bloqueadas_durante_el_cierre(api, metodo, ruta, bloqueada):
    assert api.fab.ruta_bloqueada_por_cierre(metodo, ruta) is False      # sin cierre
    with api.fab._lock:
        api.fab._estado["en_curso"] = True
    assert api.fab.ruta_bloqueada_por_cierre(metodo, ruta) is bloqueada


def test_middleware_responde_409_cierre_en_curso(api):
    with api.fab._lock:
        api.fab._estado["en_curso"] = True
    for metodo, ruta in (("post", "/io/test/enter"), ("post", "/doors/Puerta 1/open")):
        r = getattr(api.client, metodo)(ruta, headers=api.h, json={})
        assert r.status_code == 409 and r.json()["codigo"] == "cierre_en_curso"
