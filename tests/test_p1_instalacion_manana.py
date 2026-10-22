"""P1 (tanda 7): recorrido de la instalación del 22-oct (asistente, E/S,
calibración, apagado) con el backend doble, sin hardware. Cada prueba cubre
un bloqueo encontrado en el recorrido."""

import threading
import time
from unittest.mock import MagicMock

from autoclave.services.domain.logging.db_manager import DbManager
from tests.backend_doble import cargar_servidor


# ── Paso 5 (E/S): el vigilante del dueño del modo prueba no debe morir ──────
# `from datetime import time` en server.py tapaba el módulo `time`: el hilo
# hacía una sola pasada y caía en `time.sleep` (AttributeError). Después,
# una sesión dueña que caducara o cerrara NO sacaba del modo prueba.

def test_vigilante_del_modo_prueba_sigue_vivo_tras_varias_pasadas(tmp_path, monkeypatch):
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    pasadas = []
    listo = threading.Event()

    def revisar():
        pasadas.append(1)
        if len(pasadas) >= 3:
            listo.set()
        return False

    monkeypatch.setattr(srv, "_revisar_dueno_modo_prueba", revisar)
    hilo = threading.Thread(target=srv._vigilar_dueno_modo_prueba, args=(0.01,), daemon=True)
    hilo.start()
    assert listo.wait(3.0), f"el vigilante se detuvo tras {len(pasadas)} pasada(s)"
    assert hilo.is_alive()


def test_server_conserva_el_modulo_time():
    import autoclave.backend.server as s
    assert s.time is time
