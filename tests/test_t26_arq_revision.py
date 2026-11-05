# Tanda 26 (ARQ): pruebas de las correcciones pedidas por el revisor de
# seguridad (H3 a H7) y de sus pruebas adicionales.
#
# - H3: ControlLoop sin `arranque_liberado` nace RETENIDO (falla cerrada) y el
#   punto 2f solo libera con is_set() is True; construir_control entrega el
#   evento sin fijar.
# - H4: el ALL_OFF de la retención se marca hecho solo si se confirmó; si no,
#   se reintenta cada 1 s mientras siga retenido; una reconexión lo reenvía.
# - H5: dos POST /arranque/iniciar concurrentes crean un solo vigilante del
#   dueño del modo prueba.
# - H6: con la trama AI vencida, la retención no evalúa los sensores.
# - H7: POST /arranque/interfaz-lista antes de /arranque/iniciar se rechaza
#   (409 arranque_no_iniciado) sin enclavar.
# - Adicionales: el latido se renueva en cada tick retenido aunque
#   verificar_sensores lance; /system/shutdown estando retenido y un
#   interfaz-lista posterior no reactivan nada.

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cargar_servidor, modulo_backend
from tests.test_t26_arq_retencion import (_alguna_bobina_on, _esperar,  # noqa: F401
                                          planta_m31)

_MODULO = "autoclave.services.domain.loop.control_loop"


def _link(edad_ai=0.1):
    link = MagicMock()
    link.is_connected.return_value = True
    link.edad_ultima_di.return_value = 0.1
    link.edad_ultima_ai.return_value = edad_ai
    link.expansor_fuera_de_linea.return_value = False
    link.tomar_eventos.return_value = []
    return link


def _loop(sm, **kw):
    """ControlLoop con la máquina de estados de doble (patch activo en `sm`)."""
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = MagicMock()
    estado.get_machine_state.return_value = GlobalState.PREPARACION
    estado.get_flag.return_value = False
    estado.sensores_di = {"paro_emergencia": 1}
    puerta = MagicMock()
    params = dict(units=MagicMock(), door_service=MagicMock(), doors=[puerta], estado=estado,
                  link=kw.pop("link", None) or _link(), set_do=MagicMock(),
                  alarm_manager=MagicMock(), cycle_manager=MagicMock(),
                  config_manager=MagicMock())
    params.update(kw)
    loop = ControlLoop(**params)
    loop._conectado_desde = time.monotonic() - 10
    return loop, puerta


def _nada_actua(sm, loop, puerta):
    sm.return_value.update.assert_not_called()
    puerta.update.assert_not_called()
    loop.set_do.buzer.update.assert_not_called()
    assert not any(c.args[1:] == (True,) for c in loop.set_do.set_output.call_args_list)


# ── H3 ────────────────────────────────────────────────────────────────────

@pytest.mark.req("ARQ-D2")
def test_h3_control_loop_sin_argumento_nace_retenido():
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm)
        assert loop.arranque_liberado.is_set() is False
        for _ in range(3):
            loop._tick()
        _nada_actua(sm, loop, puerta)
        loop.set_do.reset_all_outputs.assert_called()      # retenido: solo apaga


@pytest.mark.req("ARQ-D2")
def test_h3_un_evento_que_no_devuelve_true_cuenta_como_retenido():
    """Punto 2f con `is_set() is True`, como la compuerta del backend."""
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm, arranque_liberado=MagicMock())   # is_set() -> MagicMock
        for _ in range(3):
            loop._tick()
        _nada_actua(sm, loop, puerta)


@pytest.mark.req("ARQ-D2")
def test_h3_construir_control_entrega_el_evento_sin_fijar(monkeypatch):
    from autoclave.backend import context as ctx_mod
    vistos = {}

    def control_loop(**kw):
        ev = kw.get("arranque_liberado")
        vistos["evento"] = ev
        vistos["fijado"] = ev.is_set() if ev is not None else None
        return MagicMock()
    for nombre in ("build_enlace", "SetOutput", "create_door", "ServicioPuertas",
                   "RealtimePrinter", "CycleLogger", "EscritorBD", "HistorialAlarmas"):
        monkeypatch.setattr(ctx_mod, nombre, MagicMock())
    monkeypatch.setattr(ctx_mod, "build_doors_cfg", lambda perfil: [])
    monkeypatch.setattr(ctx_mod, "ControlLoop", control_loop)
    yo = MagicMock()
    yo.arranque_liberado = threading.Event()        # como BackendContext.__init__
    ctx_mod.BackendContext.construir_control(yo)
    assert vistos["evento"] is yo.arranque_liberado
    assert vistos["fijado"] is False


# ── H4 ────────────────────────────────────────────────────────────────────

@pytest.mark.req("ARQ-D2")
def test_h4_all_off_fallido_se_reintenta_cada_segundo_hasta_confirmar():
    with patch(f"{_MODULO}.StateMachine"):
        loop, _ = _loop(MagicMock())
    resultados = iter([False, RuntimeError("enlace"), None, True])

    def reset():
        r = next(resultados)
        if isinstance(r, Exception):
            raise r
        return r
    loop.set_do.reset_all_outputs.side_effect = reset
    llamadas = []
    for t in (100.0, 100.5, 101.0, 101.2, 102.0, 103.0, 104.0, 110.0):
        with patch(f"{_MODULO}.time.monotonic", return_value=t):
            loop._tick_retenido()
        llamadas.append(loop.set_do.reset_all_outputs.call_count)
    # 100 False, 100.5 espera, 101 excepción, 102 None (no confirma), 103 True, luego nada
    assert llamadas == [1, 1, 2, 2, 3, 4, 4, 4]
    assert loop._retencion_apagado is True


@pytest.mark.req("ARQ-D2")
def test_h4_reconexion_del_modulo_durante_la_retencion_reenvia_all_off():
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm)
        loop.set_do.reset_all_outputs.return_value = True
        for _ in range(3):
            loop._tick()
        assert loop.set_do.reset_all_outputs.call_count == 1
        loop.link.is_connected.return_value = False
        loop._tick()
        loop.link.is_connected.return_value = True
        loop._conectado_desde = None
        loop._tick()
        assert loop.set_do.reset_all_outputs.call_count == 2
        loop._tick()
        assert loop.set_do.reset_all_outputs.call_count == 2
        _nada_actua(sm, loop, puerta)


# ── H6 ────────────────────────────────────────────────────────────────────

@pytest.mark.req("ARQ-D2")
@pytest.mark.parametrize("edad_ai, evalua", [(0.1, True), (5.0, False), (None, False)])
def test_h6_sensores_en_la_retencion_solo_con_ai_vigente(edad_ai, evalua):
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm, link=_link(edad_ai=edad_ai))
        for _ in range(2):
            loop._tick()
        verificar = sm.return_value.preparacion.verificar_sensores
        assert verificar.called is evalua
        _nada_actua(sm, loop, puerta)


# ── adicionales: latido y apagado ─────────────────────────────────────────

@pytest.mark.req("ARQ-D2")
def test_latido_se_renueva_en_cada_tick_retenido_aunque_verificar_sensores_lance():
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm)
        sm.return_value.preparacion.verificar_sensores.side_effect = RuntimeError("sensor")
        loop._running.set()
        pausas = []

        def dormir(_s):
            pausas.append(1)
            if len(pausas) >= 4:
                loop._running.clear()
        with patch(f"{_MODULO}.time.sleep", dormir):
            loop.run()
        assert sm.return_value.preparacion.verificar_sensores.call_count == 4
        assert loop.link.marcar_tick_control.call_count == 4
        assert loop._excepciones_seguidas == 0
        _nada_actua(sm, loop, puerta)


@pytest.mark.req("ARQ-D2")
def test_apagado_retenido_y_liberacion_posterior_no_reactivan_nada():
    with patch(f"{_MODULO}.StateMachine") as sm:
        loop, puerta = _loop(sm, arranque_liberado=threading.Event())
        loop._tick()
        loop.iniciar_apagado()
        loop.arranque_liberado.set()           # interfaz-lista tras el apagado
        for _ in range(3):
            loop._tick()
        _nada_actua(sm, loop, puerta)


@pytest.mark.req("ARQ-D2")
@pytest.mark.req("ARQ-D3")
def test_simulador_shutdown_retenido_e_interfaz_lista_no_reactivan(planta_m31):  # noqa: F811
    sim, srv, ctx, client = planta_m31
    assert client.post("/arranque/iniciar").status_code == 200
    assert _esperar(lambda: client.get("/arranque").json()["terminado"] is True, 30)
    assert client.get("/arranque").json()["liberado"] is False
    with patch("autoclave.backend.rutas.apagado._apagado_windows_habilitado", lambda: False):
        r = client.post("/system/shutdown", json={"ventana": "principal"})
        assert r.status_code == 200, r.text
        assert _esperar(lambda: ctx.control_loop.apagando is True, 5)
        client.post("/arranque/interfaz-lista")
        time.sleep(1.5)
    assert ctx.control_loop.state_machine.prev_state is None      # la máquina nunca corrió
    assert _alguna_bobina_on(sim) == []
    assert not any(sim.bobinas)


# ── H5 y H7: rutas ────────────────────────────────────────────────────────

@pytest.fixture
def servidor():
    ctx = MagicMock()
    ctx.arranque_liberado = threading.Event()
    srv, ctx = cargar_servidor(ctx)
    return srv, ctx, TestClient(srv.app)


@pytest.mark.req("ARQ-D1")
def test_h5_iniciar_concurrente_crea_un_solo_vigilante(servidor, monkeypatch):
    srv, _, client = servidor
    io = modulo_backend("rutas.io")
    monkeypatch.setattr(io, "_hilo_vigilancia_dueno", None)
    vigilantes = []
    monkeypatch.setattr(io, "_vigilar_dueno_modo_prueba", lambda *a: vigilantes.append(1))
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: None)
    barrera = threading.Barrier(8)

    def iniciar():
        barrera.wait()
        client.post("/arranque/iniciar")
    hilos = [threading.Thread(target=iniciar) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(5)
    io._hilo_vigilancia_dueno.join(2)
    assert vigilantes == [1]


@pytest.mark.req("ARQ-D1")
def test_h5_la_funcion_del_vigilante_es_unica_entre_hilos(servidor, monkeypatch):
    io = modulo_backend("rutas.io")
    monkeypatch.setattr(io, "_hilo_vigilancia_dueno", None)
    vigilantes = []
    monkeypatch.setattr(io, "_vigilar_dueno_modo_prueba", lambda *a: vigilantes.append(1))
    barrera = threading.Barrier(16)

    def lanzar():
        barrera.wait()
        io._iniciar_vigilancia_dueno_prueba()
    hilos = [threading.Thread(target=lanzar) for _ in range(16)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(5)
    io._hilo_vigilancia_dueno.join(2)
    assert vigilantes == [1]


@pytest.mark.req("ARQ-D3")
def test_h7_interfaz_lista_antes_de_iniciar_se_rechaza_sin_enclavar(servidor, monkeypatch):
    srv, _, client = servidor
    srv.preparar_arranque()
    monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: None)
    r = client.post("/arranque/interfaz-lista")
    assert r.status_code == 409 and r.json()["codigo"] == "arranque_no_iniciado"
    assert not srv.registro_arranque.interfaz_lista.is_set()
    etapas = {e["clave"]: e["estado"] for e in client.get("/arranque").json()["etapas"]}
    assert etapas["preparando_interfaz"] == "pendiente"
    # tras iniciar (etapas aún en curso) el aviso se acepta y queda enclavado
    assert client.post("/arranque/iniciar").status_code == 200
    r = client.post("/arranque/interfaz-lista")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert srv.registro_arranque.interfaz_lista.is_set()
    assert client.post("/arranque/interfaz-lista").status_code == 200     # idempotente


@pytest.mark.req("ARQ-D5")
def test_h7_backend_reiniciado_exige_iniciar_otra_vez(monkeypatch):
    """ARQ-D5: el backend nuevo (registro nuevo) no acepta el aviso hasta que
    la UI, al ver la instancia nueva, vuelva a pedir iniciar."""
    for _ in range(2):
        ctx = MagicMock()
        ctx.arranque_liberado = threading.Event()
        srv, _ = cargar_servidor(ctx)
        monkeypatch.setattr(srv, "ejecutar_arranque", lambda *a, **k: None)
        client = TestClient(srv.app)
        assert client.get("/arranque").json()["esperandoIniciar"] is True
        assert client.post("/arranque/interfaz-lista").status_code == 409
        assert client.post("/arranque/iniciar").status_code == 200
        assert client.post("/arranque/interfaz-lista").status_code == 200
