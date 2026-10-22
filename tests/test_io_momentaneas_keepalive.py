# B-ES-5 / B-ES-6 (P-ES-3, P-ES-4): salidas momentáneas con caducidad y
# salida automática del modo prueba sin actividad de la sesión dueña.
import time

import pytest

from tests.test_io_endpoints import entorno, io_client, _canal, _llamadas  # noqa: F401


def _esperar(cond, limite=2.0):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def rapido(entorno):
    client, ctx, srv = entorno
    srv.CADUCIDAD_MOMENTANEA_S = 0.15
    srv.INACTIVIDAD_MODO_PRUEBA_S = 0.3
    yield client, ctx, srv
    srv._cancelar_vigilancias_prueba()


def test_momentanea_sin_renovacion_se_apaga_sola(rapido):
    client, ctx, _ = rapido
    r = client.patch("/io/test/output/bomba_vacio", json={"value": True, "momentanea": True})
    assert r.status_code == 200
    assert _esperar(lambda: (_canal("bomba_vacio"), False) in _llamadas(ctx))


def test_momentanea_renovada_sigue_encendida(rapido):
    client, ctx, _ = rapido
    for _ in range(4):
        client.patch("/io/test/output/bomba_vacio", json={"value": True, "momentanea": True})
        time.sleep(0.08)
    assert (_canal("bomba_vacio"), False) not in _llamadas(ctx)


def test_momentanea_off_explicito_cancela_la_caducidad(rapido):
    client, ctx, _ = rapido
    client.patch("/io/test/output/bomba_vacio", json={"value": True, "momentanea": True})
    client.patch("/io/test/output/bomba_vacio", json={"value": False})
    n = len(_llamadas(ctx))
    time.sleep(0.3)
    assert len(_llamadas(ctx)) == n


def test_momentanea_solo_en_salidas_momentaneas_422(rapido):
    client, ctx, _ = rapido
    r = client.patch("/io/test/output/vapor_camara", json={"value": True, "momentanea": True})
    assert r.status_code == 422
    ctx.setdo.set_output.assert_not_called()


def test_sin_actividad_el_backend_sale_del_modo_prueba(rapido):
    client, ctx, _ = rapido
    client.post("/io/test/keepalive")
    assert _esperar(lambda: ctx.control_loop.exit_test_mode.called)
    eventos = [(c.args[0], c.kwargs.get("detalle")) for c in ctx.db.registrar_auditoria.call_args_list]
    assert ("modo_prueba_sale", {"motivo": "sin actividad de la sesión (keepalive)",
                                 "all_off_confirmado": False}) in eventos   # R1-P1


def test_keepalive_mantiene_el_modo_prueba(rapido):
    client, ctx, _ = rapido
    for _ in range(5):
        assert client.post("/io/test/keepalive").status_code == 200
        time.sleep(0.1)
    assert not ctx.control_loop.exit_test_mode.called


def test_keepalive_fuera_de_modo_prueba_409(entorno):
    client, ctx, _ = entorno
    ctx.control_loop.test_mode_active = False
    assert client.post("/io/test/keepalive").status_code == 409


def test_keepalive_de_otra_sesion_409(entorno):
    from tests.backend_doble import cabecera
    client, ctx, srv = entorno
    assert client.post("/io/test/keepalive",
                       headers=cabecera(srv, "ingeniero", "otro")).status_code == 409


def test_temporizador_de_otra_generacion_no_saca_a_la_sesion_nueva(rapido):
    """Revisión P1 (TMG-03/TMG-07): un plazo armado antes de una nueva entrada
    al modo prueba no actúa sobre la sesión que entró después."""
    client, ctx, srv = rapido
    client.post("/io/test/keepalive")
    srv._generacion_prueba += 1          # otra entrada mientras el plazo corría
    try:
        time.sleep(0.5)
        assert not ctx.control_loop.exit_test_mode.called
    finally:
        srv._generacion_prueba -= 1
