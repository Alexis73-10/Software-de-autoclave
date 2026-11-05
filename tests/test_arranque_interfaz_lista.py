"""Ticket de arranque tras la animación de la UI (4-nov): POST /arranque/interfaz-lista,
espera de latido_y_ticket con tope, y lanzador sin PySide6 para BACKEND_URL."""
import subprocess
import sys
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient

from autoclave.backend.arranque.registro import EstadoEtapa, RegistroArranque
from autoclave.backend import main as backend_main


def test_marcar_interfaz_lista_es_idempotente():
    r = RegistroArranque()
    assert not r.interfaz_lista.is_set()
    assert r.marcar_interfaz_lista() is True
    assert r.estado_de("preparando_interfaz") == EstadoEtapa.OK
    assert r.interfaz_lista.is_set()
    assert r.marcar_interfaz_lista() is False
    assert r.estado_de("preparando_interfaz") == EstadoEtapa.OK


def test_ruta_pasa_la_compuerta_y_completa_la_etapa(monkeypatch):
    from autoclave.backend import server
    from autoclave.backend.dependencias import registro_arranque
    registro = RegistroArranque()
    registro.marcar_iniciado()     # H7 (revisión ARQ, tanda 26): exige iniciar antes
    monkeypatch.setattr("autoclave.backend.rutas.sistema.registro_arranque", registro)
    monkeypatch.setattr(server, "_compuerta_arranque", True)
    assert not server._contexto_operable.is_set()
    cliente = TestClient(server.app)
    for _ in range(2):   # idempotente, incluso con la compuerta 503 activa
        r = cliente.post("/arranque/interfaz-lista")
        assert r.status_code == 200 and r.json() == {"ok": True}
    assert registro.estado_de("preparando_interfaz") == EstadoEtapa.OK
    assert registro_arranque is not registro


def _servidor(operable=True, perfil=object()):
    ev = threading.Event()
    if operable:
        ev.set()
    return SimpleNamespace(_contexto_operable=ev, context=SimpleNamespace(profile=perfil),
                           registro_arranque=RegistroArranque())


def _capturar_iniciar(monkeypatch):
    llamadas = []

    def falso(perfil, antes_de_imprimir=None, **kw):
        llamadas.append((perfil, antes_de_imprimir))
    monkeypatch.setattr("autoclave.devices.printer.arranque_equipo.iniciar", falso)
    return llamadas


def test_latido_y_ticket_espera_el_evento_de_la_interfaz(monkeypatch):
    srv = _servidor()
    llamadas = _capturar_iniciar(monkeypatch)
    backend_main.latido_y_ticket(srv, plazo_s=0.1, tope_interfaz_s=5.0)
    perfil, esperar = llamadas[0]
    assert perfil is srv.context.profile
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.setdefault("t", (esperar(), True)))
    hilo.start()
    hilo.join(0.3)
    assert hilo.is_alive()          # aún espera a la UI
    srv.registro_arranque.marcar_interfaz_lista()
    hilo.join(2)
    assert not hilo.is_alive()


def test_sin_ui_imprime_tras_el_tope(monkeypatch):
    srv = _servidor()
    llamadas = _capturar_iniciar(monkeypatch)
    backend_main.latido_y_ticket(srv, plazo_s=0.1, tope_interfaz_s=0.2)
    _, esperar = llamadas[0]
    esperar()   # vuelve solo, sin que nadie avise: el ticket no se pierde
    assert not srv.registro_arranque.interfaz_lista.is_set()


def test_iniciar_espera_antes_de_imprimir_y_sobrevive_a_un_error():
    from autoclave.devices.printer import arranque_equipo as ae
    orden = []
    imprime = lambda: orden.append("imprimir")

    def esperar():
        orden.append("esperar")
        raise RuntimeError("fallo")
    import autoclave.devices.printer.arranque_equipo as mod
    original = mod.imprimir_ticket
    mod.imprimir_ticket = lambda *a, **k: imprime()
    try:
        ae.iniciar(object(), leer_ultimo=lambda: None, arrancar_latido=lambda: orden.append("latido"),
                   lanzar=lambda t: t(), antes_de_imprimir=esperar)
    finally:
        mod.imprimir_ticket = original
    assert orden == ["latido", "esperar", "imprimir"]


def test_progreso_avisar_en_hilo_y_una_vez():
    from autoclave.ui_qml.bridge.progreso_arranque import ProgresoArranqueBackend
    llamadas = []
    hecho = threading.Event()

    def avisar():
        llamadas.append(1)
        hecho.set()
    # tanda 26 (ARQ-D3): el aviso sale solo con el backend terminado de verdad
    registro = RegistroArranque()
    for e in registro.instantanea()["etapas"]:
        if e["clave"] != "preparando_interfaz":
            registro.iniciar(e["clave"])
            registro.completar(e["clave"])
    p = ProgresoArranqueBackend(registro.instantanea, avisar=avisar, en_hilo=False)
    p.sondear()
    p.avisarInterfazLista()
    p.avisarInterfazLista()
    assert hecho.wait(2)
    p.sondear()
    assert llamadas == [1]
    # sin avisar (puerta 2): no hace nada y no falla
    ProgresoArranqueBackend(lambda: None).avisarInterfazLista()


def test_lanzador_no_importa_la_app_qml_y_la_url_coincide():
    from autoclave import exe_unico
    from autoclave.ui_qml import app
    assert exe_unico.BACKEND_URL == app.BACKEND_URL
    codigo = ("import sys, autoclave.exe_unico; "
              "sys.exit(1 if 'autoclave.ui_qml.app' in sys.modules else 0)")
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                       env={**__import__("os").environ})
    assert r.returncode == 0, r.stderr
