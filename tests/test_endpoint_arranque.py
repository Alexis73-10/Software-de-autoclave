# tests/test_endpoint_arranque.py
#
# GET /arranque, compuerta 503 mientras el control no está construido, 503 sin
# base de datos, /cycle/start bloqueado sin BD, y disparo del arranque desde
# backend/main.py solo con el puerto enlazado (fase B, planeacion_barra_arranque_real.md §5).

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.arranque.sin_bd import BdNoDisponible
from tests.backend_doble import cargar_servidor


@pytest.fixture
def servidor():
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    srv, ctx = cargar_servidor(ctx)
    return srv, ctx, TestClient(srv.app)


def _completar(reg, claves):
    for c in claves:
        reg.iniciar(c)
        reg.completar(c)


def test_arranque_responde_sin_token_antes_de_correr_las_etapas(servidor):
    srv, _, client = servidor
    srv.preparar_arranque()
    r = client.get("/arranque")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["terminado"] is False
    assert cuerpo["falloBloqueante"] is False
    assert cuerpo["etapaActual"] == "verificando_instalacion"
    assert len(cuerpo["etapas"]) == 9
    assert cuerpo["etapas"][0] == {"clave": "verificando_instalacion", "estado": "pendiente",
                                   "codigo": None, "peso": 1.0}


def test_compuerta_503_hasta_que_el_contexto_es_operable(servidor):
    srv, ctx, client = servidor
    ctx.estado.get_machine_state.return_value = None
    srv.preparar_arranque()
    r = client.get("/status")
    assert r.status_code == 503
    assert r.json() == {"detail": "Arranque en curso", "codigo": "arranque_en_curso"}
    assert client.post("/cycle/start").status_code == 503
    assert client.post("/ui/activity").status_code == 200    # exenta: no usa context
    srv._contexto_operable.set()
    assert client.get("/cycle").status_code == 200
    assert client.get("/arranque").status_code == 200


def test_con_fallo_bloqueante_el_resto_responde_arranque_fallido(servidor):
    srv, _, client = servidor
    srv.preparar_arranque()
    reg = srv.registro_arranque
    _completar(reg, ["verificando_instalacion", "liberando_procesos", "iniciando_servicios"])
    reg.iniciar("cargando_configuracion")
    reg.fallar("cargando_configuracion", "ARR_CICLO_DEFECTO")
    cuerpo = client.get("/arranque").json()
    assert cuerpo["falloBloqueante"] is True
    assert cuerpo["etapaActual"] == "cargando_configuracion"
    assert cuerpo["etapas"][3]["codigo"] == "ARR_CICLO_DEFECTO"
    r = client.get("/global_params")
    assert r.status_code == 503
    assert r.json()["codigo"] == "arranque_fallido"


def test_sin_compuerta_las_rutas_responden_como_antes(servidor):
    # quien importa server.py sin pasar por main.py (pruebas) no tiene compuerta
    _, _, client = servidor
    assert client.get("/cycle").status_code == 200


def test_bd_no_disponible_responde_503_sin_base_de_datos(servidor):
    srv, ctx, client = servidor
    ctx.db = BdNoDisponible()
    r = client.get("/cycle/history")
    assert r.status_code == 503
    assert r.json() == {"detail": "Base de datos no disponible", "codigo": "sin_base_de_datos"}


def test_sin_bd_no_se_puede_iniciar_ciclo(servidor):
    srv, ctx, client = servidor
    ctx.db = BdNoDisponible()
    ctx.sin_base_de_datos = True
    ctx.control_loop.bloqueo_configuracion = None
    ctx.estado.get_flag.return_value = True     # LISTO_PARA_CICLO
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "sin_base_de_datos"
    ctx.estado.set_flag.assert_not_called()     # START_CICLO nunca se levanta


def test_apagado_antes_de_construir_el_control_no_toca_la_tarjeta(servidor):
    srv, ctx, _ = servidor
    ctx.control_loop = None
    with TestClient(srv.app):
        pass
    assert srv._detener_arranque.is_set()


def test_iniciar_arranque_lanza_un_solo_hilo(servidor, monkeypatch):
    srv, _, _ = servidor
    llamadas = []
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: llamadas.append(k))
    srv.iniciar_arranque()
    srv._hilo_arranque.join(2)
    srv.iniciar_arranque()
    assert len(llamadas) == 1
    assert llamadas[0]["al_cancelar_prueba"] is srv._prueba_cancelada_por_paro
    assert llamadas[0]["detener"] is srv._detener_arranque


def test_importar_server_no_construye_hardware():
    from autoclave.backend import context as ctx_mod
    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]
    prohibidos = {n: MagicMock(side_effect=AssertionError(n))
                  for n in ("build_serial", "DbManager", "SensorCalibrationAuditDB",
                            "Units", "ControlLoop", "get_installation_profile")}
    with patch.multiple(ctx_mod, **prohibidos):
        srv = importlib.import_module("autoclave.backend.server")
        assert TestClient(srv.app).get("/arranque").status_code == 200
    assert srv.context.control_loop is None
    assert srv._hilo_arranque is None


# ── backend/main.py ───────────────────────────────────────────────────────────

class _Servidor:
    def __init__(self, enlaza_tras=None):
        self.enlaza_tras = enlaza_tras    # None = nunca enlaza
        self.vueltas = 0
        self.should_exit = False

    @property
    def started(self):
        return self.enlaza_tras is not None and self.vueltas >= self.enlaza_tras


def test_el_arranque_se_dispara_solo_con_el_puerto_enlazado():
    from autoclave.backend import main
    servidor = _Servidor(enlaza_tras=3)
    iniciar = MagicMock()

    def dormir(_s):
        assert not iniciar.called        # nada antes de enlazar
        servidor.vueltas += 1
    assert main.arrancar_cuando_escuche(servidor, iniciar, dormir=dormir) is True
    iniciar.assert_called_once()


def test_si_el_puerto_no_enlaza_el_arranque_no_empieza():
    from autoclave.backend import main
    servidor = _Servidor(enlaza_tras=None)
    iniciar = MagicMock()

    def dormir(_s):
        servidor.vueltas += 1
        if servidor.vueltas == 5:
            servidor.should_exit = True    # uvicorn no pudo enlazar (puerto ocupado)
    assert main.arrancar_cuando_escuche(servidor, iniciar, dormir=dormir) is False
    iniciar.assert_not_called()


def test_main_activa_la_compuerta_antes_de_abrir_el_puerto():
    from autoclave.backend import main
    orden = []
    srv = MagicMock()
    srv.preparar_arranque.side_effect = lambda: orden.append("compuerta")
    servidor = MagicMock()
    servidor.run.side_effect = lambda: orden.append("puerto")
    with patch.dict(sys.modules, {"autoclave.backend.server": srv}), \
            patch("autoclave.backend.server", srv, create=True), \
            patch.object(main.uvicorn, "Server", return_value=servidor), \
            patch.object(main.threading, "Thread") as hilo:
        main.main()
    assert orden == ["compuerta", "puerto"]
    assert hilo.call_args.kwargs["args"] == (servidor, srv.iniciar_arranque)
