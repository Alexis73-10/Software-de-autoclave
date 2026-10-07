# services/domain/logging/historial_alarmas.py
#
# Oyente de AlarmManager que persiste aparición, resolución y reconocimiento
# en alarmas_historial (spec 2026-10-06-sistema-alarmas-parte-a §6). Una
# escritura fallida nunca se propaga al ControlLoop: queda en el log y activa
# SIS-02 una sola vez por arranque.
#
# El oyente corre en el hilo que cambió la alarma (ControlLoop o HTTP), así
# que no hace E/S: toma una foto inmutable de lo que hay que escribir y la
# encola. Un hilo escritor daemon procesa la cola en orden, de modo que un
# RECONOCIDA/RESUELTA siempre encuentra el id_historial que dejó su APARECIDA.

import json
import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime

from autoclave.state_machine.alarms.catalogo import SIS_02
from autoclave.state_machine.alarms.instancia import EventoAlarma, InstanciaAlarma

logger = logging.getLogger(__name__)

_FIN = object()


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _json(valores) -> str:
    return json.dumps(valores, ensure_ascii=False, default=str, sort_keys=True)


@dataclass(frozen=True)
class _Registro:
    """Lo que hay que escribir, tomado en el momento del evento."""
    evento: EventoAlarma
    inst: InstanciaAlarma          # solo para fijarle id_historial
    clave: str
    codigo: str
    nivel: str
    titulo: str
    origen: str | None
    valores: dict
    descripcion: str
    aparecida: datetime
    resuelta: datetime | None
    reconocida_por: str | None
    reconocida_en: datetime | None
    ciclo_id: int | None


class HistorialAlarmas:
    def __init__(self, db, alarm_manager, ciclo_actual=lambda: None):
        self._db = db
        self._am = alarm_manager
        self._ciclo_actual = ciclo_actual
        self._sis02_activada = False
        self._cola: queue.Queue = queue.Queue()
        self._hilo = threading.Thread(target=self._escritor, name="historial-alarmas",
                                      daemon=True)
        self._hilo.start()
        alarm_manager.suscribir(self)

    # ------------------------------------------------------------------
    # Oyente (hilo que cambió la alarma): solo encola, nunca hace E/S
    # ------------------------------------------------------------------

    def __call__(self, evento, inst):
        if inst.codigo == SIS_02:
            return
        try:
            ciclo_id = inst.ciclo_id
            if evento is EventoAlarma.APARECIDA:
                ciclo_id = self._ciclo_actual()
                inst.ciclo_id = ciclo_id
            self._cola.put(_Registro(
                evento=evento, inst=inst, clave=inst.clave, codigo=inst.codigo,
                nivel=inst.nivel.name, titulo=inst.titulo, origen=inst.origen,
                valores=dict(inst.valores), descripcion=inst.descripcion,
                aparecida=inst.aparecida, resuelta=inst.resuelta,
                reconocida_por=inst.reconocida_por, reconocida_en=inst.reconocida_en,
                ciclo_id=ciclo_id,
            ))
        except Exception as exc:
            self._fallo(evento, inst.clave, exc)

    # ------------------------------------------------------------------
    # Pruebas y apagado
    # ------------------------------------------------------------------

    def vaciar(self, timeout: float = 5.0) -> bool:
        """Espera a que todo lo encolado hasta ahora quede procesado."""
        if not self._hilo.is_alive():
            return self._cola.empty()
        listo = threading.Event()
        self._cola.put(listo)
        return listo.wait(timeout)

    def detener(self, timeout: float = 5.0) -> None:
        """Procesa lo pendiente y termina el hilo escritor de forma ordenada."""
        if self._hilo.is_alive():
            self._cola.put(_FIN)
            self._hilo.join(timeout)

    # ------------------------------------------------------------------
    # Hilo escritor
    # ------------------------------------------------------------------

    def _escritor(self):
        while True:
            item = self._cola.get()
            if item is _FIN:
                return
            if isinstance(item, threading.Event):
                item.set()
                continue
            try:
                self._escribir(item)
            except Exception as exc:
                self._fallo(item.evento, item.clave, exc)

    def _fallo(self, evento, clave, exc):
        try:
            logger.error("Historial de alarmas: no se pudo registrar %s de %s: %s",
                         evento.value, clave, exc)
            if not self._sis02_activada:
                self._sis02_activada = True
                self._am.activar(SIS_02, error=str(exc))
        except Exception:
            logger.exception("Historial de alarmas: no se pudo informar el fallo de escritura")

    def _escribir(self, reg: _Registro):
        if reg.evento is EventoAlarma.APARECIDA:
            reg.inst.id_historial = self._db.insertar_alarma(
                reg.codigo, reg.nivel, reg.titulo, reg.origen, reg.descripcion,
                _json(reg.valores), _iso(reg.aparecida), _iso(reg.resuelta), reg.ciclo_id,
            )
            return
        id_historial = reg.inst.id_historial
        if id_historial is None:
            return
        if reg.evento is EventoAlarma.RESUELTA:
            self._db.marcar_alarma_resuelta(
                id_historial, _iso(reg.resuelta), reg.descripcion, _json(reg.valores))
        elif reg.evento is EventoAlarma.RECONOCIDA:
            self._db.marcar_alarma_reconocida(
                id_historial, reg.reconocida_por, _iso(reg.reconocida_en))
