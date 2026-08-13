import heapq
import itertools
import logging
import threading
import time

import sounddevice as sd

logger = logging.getLogger(__name__)

_MAX_COLA = 10


class Announcer:
    def __init__(self, eventos, get_volume, get_enabled, on_fallo_persistente=None):
        self._eventos = eventos
        self._get_volume = get_volume
        self._get_enabled = get_enabled
        self._on_fallo_persistente = on_fallo_persistente

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._cola = []
        self._encolados = set()
        self._contador = itertools.count()
        self._ultimo_reproducido = {}
        self._prioridad_sonando = None
        self._fallos_consecutivos = 0

        self._detener = threading.Event()
        self._worker = threading.Thread(target=self._run, name="Announcer", daemon=True)

    def start(self):
        self._worker.start()

    def stop(self):
        self._detener.set()
        with self._cond:
            self._cond.notify_all()
        sd.stop()
        if self._worker.is_alive():
            self._worker.join(timeout=2)

    def say(self, event_id: str) -> None:
        evento = self._eventos.get(event_id)
        if evento is None or not self._get_enabled():
            return

        now = time.monotonic()
        with self._cond:
            ultimo = self._ultimo_reproducido.get(event_id)
            if ultimo is not None and now - ultimo < evento.cooldown_s:
                return
            if event_id in self._encolados:
                return

            if self._prioridad_sonando is not None and evento.prioridad < self._prioridad_sonando:
                sd.stop()

            if len(self._cola) >= _MAX_COLA:
                peor = max(self._cola)
                if evento.prioridad < peor[0]:
                    self._cola.remove(peor)
                    self._encolados.discard(peor[2])
                    heapq.heapify(self._cola)
                    logger.warning("Announcer: cola llena, se descarta %s", peor[2])
                else:
                    logger.warning("Announcer: cola llena, se descarta %s", event_id)
                    return

            heapq.heappush(self._cola, (evento.prioridad, next(self._contador), event_id))
            self._encolados.add(event_id)
            self._cond.notify_all()

    def disable_now(self) -> None:
        with self._cond:
            for _, _, event_id in self._cola:
                self._encolados.discard(event_id)
            self._cola.clear()
        sd.stop()

    def _run(self):
        while not self._detener.is_set():
            with self._cond:
                while not self._cola and not self._detener.is_set():
                    self._cond.wait()
                if self._detener.is_set():
                    return
                prioridad, _, event_id = heapq.heappop(self._cola)
                self._encolados.discard(event_id)
                self._prioridad_sonando = prioridad
                self._ultimo_reproducido[event_id] = time.monotonic()

            evento = self._eventos[event_id]
            try:
                volumen = max(0, min(100, self._get_volume()))
                ganancia = (volumen / 100) ** 2.0
                sd.play(evento.samples * ganancia, evento.sample_rate)
                sd.wait()
                self._fallos_consecutivos = 0
            except Exception as exc:
                self._fallos_consecutivos += 1
                logger.warning("Announcer: fallo de reproduccion (%s): %s", event_id, exc)
                if self._fallos_consecutivos >= 3 and self._on_fallo_persistente:
                    self._on_fallo_persistente()
            finally:
                with self._cond:
                    self._prioridad_sonando = None
