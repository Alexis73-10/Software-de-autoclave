# services/domain/logging/historial_alarmas.py
#
# Oyente de AlarmManager que persiste aparición, resolución y reconocimiento
# en alarmas_historial (spec 2026-10-06-sistema-alarmas-parte-a §6). Una
# escritura fallida nunca se propaga al ControlLoop: queda en el log y activa
# SIS-02 una sola vez por arranque.

import json
import logging

from autoclave.state_machine.alarms.catalogo import SIS_02
from autoclave.state_machine.alarms.instancia import EventoAlarma

logger = logging.getLogger(__name__)


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _json(valores) -> str:
    return json.dumps(valores, ensure_ascii=False, default=str, sort_keys=True)


class HistorialAlarmas:
    def __init__(self, db, alarm_manager, ciclo_actual=lambda: None):
        self._db = db
        self._am = alarm_manager
        self._ciclo_actual = ciclo_actual
        self._sis02_activada = False
        alarm_manager.suscribir(self)

    def __call__(self, evento, inst):
        if inst.codigo == SIS_02:
            return
        try:
            self._escribir(evento, inst)
        except Exception as exc:
            logger.error("Historial de alarmas: no se pudo registrar %s de %s: %s",
                         evento.value, inst.clave, exc)
            if not self._sis02_activada:
                self._sis02_activada = True
                self._am.activar(SIS_02, error=str(exc))

    def _escribir(self, evento, inst):
        if evento is EventoAlarma.APARECIDA:
            inst.ciclo_id = self._ciclo_actual()
            inst.id_historial = self._db.insertar_alarma(
                inst.codigo, inst.nivel.name, inst.titulo, inst.origen, inst.descripcion,
                _json(inst.valores), _iso(inst.aparecida), _iso(inst.resuelta), inst.ciclo_id,
            )
            return
        if inst.id_historial is None:
            return
        if evento is EventoAlarma.RESUELTA:
            self._db.marcar_alarma_resuelta(
                inst.id_historial, _iso(inst.resuelta), inst.descripcion, _json(inst.valores))
        elif evento is EventoAlarma.RECONOCIDA:
            self._db.marcar_alarma_reconocida(
                inst.id_historial, inst.reconocida_por, _iso(inst.reconocida_en))
        elif evento is EventoAlarma.REACTIVADA:
            self._db.reabrir_alarma(inst.id_historial)
