# B-ES-6 (P-ES-4): salida automática del modo prueba sin actividad de la sesión
# dueña. Tanda 27 (A4, HAZ-IO-07): ya no hay salidas momentáneas (P-ES-3 y su
# caducidad se retiraron); puertas y bomba de vacío son interruptor, con el
# enclavamiento abrir/cerrar (DECISIÓN SIN CONFIRMAR).
import time

import pytest

from tests.test_io_endpoints import entorno, io_client, _canal, _llamadas  # noqa: F401
from tests.helpers.backend_doble import modulo_backend


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
    modulo_backend("rutas.io").INACTIVIDAD_MODO_PRUEBA_S = 0.3
    yield client, ctx, srv
    modulo_backend("rutas.io")._cancelar_vigilancias_prueba()


# ── A4: interruptor sin tope ───────────────────────────────────────────────

def test_caducidad_momentanea_retirada(entorno):
    io = modulo_backend("rutas.io")
    for nombre in ("CADUCIDAD_MOMENTANEA_S", "_timers_momentaneas", "_armar_momentanea",
                   "_caducar_momentanea", "_desarmar_momentanea"):
        assert not hasattr(io, nombre), nombre


@pytest.mark.parametrize("salida", ["bomba_vacio", "abrir_puerta_1", "cerrar_puerta_1"])
def test_encendida_sin_renovar_sigue_encendida(entorno, salida):
    client, ctx, _ = entorno
    r = client.patch(f"/io/test/output/{salida}", json={"value": True})
    assert r.status_code == 200, r.text
    time.sleep(1.8)          # más que la antigua caducidad de 1,5 s
    assert (_canal(salida), False) not in _llamadas(ctx)
    assert (_canal(salida), True) in _llamadas(ctx)


def test_momentanea_en_el_cuerpo_se_acepta_y_se_ignora(entorno, caplog):
    client, ctx, _ = entorno
    r = client.patch("/io/test/output/vapor_camara", json={"value": True, "momentanea": True})
    assert r.status_code == 200, r.text
    assert (_canal("vapor_camara"), True) in _llamadas(ctx)
    assert "se ignora" in caplog.text


# ── A4: enclavamiento abrir/cerrar (DECISIÓN SIN CONFIRMAR) ─────────────────

@pytest.mark.parametrize("orden,opuesta", [("abrir_puerta_1", "cerrar_puerta_1"),
                                           ("cerrar_puerta_1", "abrir_puerta_1"),
                                           ("abrir_puerta_2", "cerrar_puerta_2"),
                                           ("cerrar_puerta_2", "abrir_puerta_2")])
def test_encender_un_sentido_apaga_antes_el_otro(entorno, orden, opuesta):
    client, ctx, _ = entorno
    r = client.patch(f"/io/test/output/{orden}", json={"value": True})
    assert r.status_code == 200, r.text
    assert r.json()["apagada_por_enclavamiento"] == opuesta
    assert _llamadas(ctx) == [(_canal(opuesta), False), (_canal(orden), True)]


def test_apagar_no_toca_el_sentido_contrario(entorno):
    client, ctx, _ = entorno
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": False})
    assert r.status_code == 200
    assert "apagada_por_enclavamiento" not in r.json()
    assert _llamadas(ctx) == [(_canal("abrir_puerta_1"), False)]


def test_bomba_vacio_sin_enclavamiento(entorno):
    client, ctx, _ = entorno
    r = client.patch("/io/test/output/bomba_vacio", json={"value": True})
    assert "apagada_por_enclavamiento" not in r.json()
    assert _llamadas(ctx) == [(_canal("bomba_vacio"), True)]


def test_enclavamiento_no_actua_si_esg02_rechaza(entorno):
    """ESG-02 sigue rechazando la apertura con la cámara presurizada: ni se
    enciende abrir ni se apaga el cierre."""
    client, ctx, _ = entorno
    ctx.control_loop.salidas_prueba_bloqueadas.return_value = {
        "abrir_puerta_1": "salida_prueba_camara_presurizada"}
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    assert r.status_code == 409
    assert "salida_prueba_camara_presurizada" in r.text
    ctx.setdo.set_output.assert_not_called()


def test_vapor_camara_sigue_rechazado_con_puerta_no_cerrada(entorno):
    client, ctx, _ = entorno
    ctx.control_loop.salidas_prueba_bloqueadas.return_value = {
        "vapor_camara": "salida_prueba_puerta_abierta"}
    r = client.patch("/io/test/output/vapor_camara", json={"value": True})
    assert r.status_code == 409
    ctx.setdo.set_output.assert_not_called()


def test_orden_de_abrir_termina_la_inversion_por_atrapamiento(entorno):
    """D-ES-16 con interruptor: tras la inversión (cerrar -> abrir), una orden
    propia de abrir la da por terminada; el siguiente cerrar con la señal
    liberada cierra (antes la terminaba soltar el botón momentáneo)."""
    from tests.test_io_endpoints import _puerta_avanzada, _DI_ATRAP, _DI_CERRADA, _DI_ABIERTA
    client, ctx, _ = entorno
    ctx.doors = [_puerta_avanzada()]
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0, _DI_ATRAP: 0}
    r = client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert r.json().get("invertida") is True
    ctx.estado.sensores_di[_DI_ATRAP] = 1                     # se libera
    client.patch("/io/test/output/abrir_puerta_1", json={"value": False})
    ctx.setdo.set_output.reset_mock()
    r = client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert "invertida" not in r.json()
    assert _llamadas(ctx) == [(_canal("abrir_puerta_1"), False), (_canal("cerrar_puerta_1"), True)]


def test_salir_del_modo_prueba_apaga_todo_con_una_puerta_encendida(entorno):
    client, ctx, _ = entorno
    client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    r = client.post("/io/test/exit")
    assert r.status_code == 200
    ctx.control_loop.exit_test_mode.assert_called_once()   # ALL_OFF del ControlLoop


# ── P-ES-4: inactividad del modo prueba (sin cambio) ───────────────────────

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
    from tests.helpers.backend_doble import cabecera
    client, ctx, srv = entorno
    assert client.post("/io/test/keepalive",
                       headers=cabecera(srv, "ingeniero", "otro")).status_code == 409


def test_temporizador_de_otra_generacion_no_saca_a_la_sesion_nueva(rapido):
    """Revisión P1 (TMG-03/TMG-07): un plazo armado antes de una nueva entrada
    al modo prueba no actúa sobre la sesión que entró después."""
    client, ctx, srv = rapido
    client.post("/io/test/keepalive")
    modulo_backend("rutas.io")._generacion_prueba += 1          # otra entrada mientras el plazo corría
    try:
        time.sleep(0.5)
        assert not ctx.control_loop.exit_test_mode.called
    finally:
        modulo_backend("rutas.io")._generacion_prueba -= 1
