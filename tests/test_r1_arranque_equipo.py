"""R1 (tanda 2): al retirar la UI anterior, el latido de apagado y el ticket de
arranque (que solo hacía su ventana principal) pasan al backend, el
proceso de larga vida tanto con ui_qml/lanzar.py como con el ejecutable único."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.devices.printer import arranque_equipo


def _perfil():
    return SimpleNamespace(model_id="M1", serial_number="S1",
                           equipment_class=SimpleNamespace(value="piso_lab"))


def test_lee_el_ultimo_apagado_antes_de_arrancar_el_latido():
    orden = []
    ultimo = datetime(2026, 10, 18, 22, 0, 0)
    arranque_equipo.iniciar(
        _perfil(), leer_ultimo=lambda: orden.append("leer") or ultimo,
        arrancar_latido=lambda: orden.append("latido"),
        lanzar=lambda tarea: orden.append("ticket"))
    assert orden == ["leer", "latido", "ticket"]


def test_ticket_con_backend_y_tarjeta_ok():
    impreso = []
    estado = iter([{"card_connected": False}, {"card_connected": True}])
    arranque_equipo.imprimir_ticket(
        _perfil(), datetime(2026, 10, 18, 22, 0, 0), datetime(2026, 10, 19, 7, 0, 0),
        consultar_estado=lambda: next(estado), imprimir=lambda t: impreso.append(t) or True,
        dormir=lambda s: None, plazo_s=5, version="1.0")
    texto = impreso[0]
    assert "Backend:" in texto and "Módulo E/S:" in texto and "Sistema listo" in texto
    assert "2026-10-18" in texto


def test_ticket_marca_falla_si_la_tarjeta_no_responde():
    impreso = []
    reloj = iter(range(0, 100))
    arranque_equipo.imprimir_ticket(
        _perfil(), None, datetime(2026, 10, 19, 7, 0, 0),
        consultar_estado=lambda: {"card_connected": False},
        imprimir=lambda t: impreso.append(t) or True, dormir=lambda s: None,
        plazo_s=3, version="1.0", reloj=lambda: next(reloj))
    assert "FALLO EN ARRANQUE" in impreso[0] and "Primer encendido" in impreso[0]


def test_sin_perfil_no_imprime_ni_falla():
    lanzados = []
    arranque_equipo.iniciar(None, leer_ultimo=lambda: None, arrancar_latido=MagicMock(),
                            lanzar=lanzados.append)
    assert lanzados == []


def test_backend_main_lo_inicia_tras_el_arranque():
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "backend" / "main.py") \
        .read_text(encoding="utf-8")
    assert "arranque_equipo" in fuente


def test_latido_y_ticket_espera_el_contexto_operable(monkeypatch):
    import threading
    from autoclave.backend import main
    llamadas = []
    monkeypatch.setattr(arranque_equipo, "iniciar", llamadas.append)
    operable = threading.Event()
    operable.set()
    server = SimpleNamespace(_contexto_operable=operable, context=SimpleNamespace(profile="P"))
    main.latido_y_ticket(server, plazo_s=0.1)
    assert llamadas == ["P"]
    server = SimpleNamespace(_contexto_operable=threading.Event(), context=SimpleNamespace(profile="P"))
    main.latido_y_ticket(server, plazo_s=0.05)
    assert llamadas == ["P", None]           # sin arranque operable: latido sin ticket
