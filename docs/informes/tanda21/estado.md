# Tanda 21 — estado

Rama `tanda-21` (desde `dev` 92abead). Spec: `docs/mis_plans/planeacion_fin_de_ciclo.md`.

| Paso | Estado | Commit / nota |
|---|---|---|
| A0 | Hecha | 86b0752 (spec, prompt y mockups); verificaciones abajo |
| Ola 1 P1 backend | Pendiente | |
| Ola 1 P2 panel | Pendiente | |
| Ola 1 P3 puerta | Pendiente | |
| Ola 1 P4 textos | Pendiente | |
| Ola 1 V | Pendiente | |
| Ola 2 | Pendiente | |
| G capturas | Pendiente | |
| R revisión | Pendiente | |
| Suite | Pendiente | |
| K entrega | Pendiente | |

## Verificaciones de A0

### FC-03: dónde se escribe `alarmas_historial` y `ciclo_id`
- Escritor único: `services/domain/logging/historial_alarmas.py` (`HistorialAlarmas`, oyente de `AlarmManager`; hilo escritor → `DbManager.insertar_alarma`). El `ciclo_id` se toma en el hilo que activa la alarma, en `APARECIDA`, con `ciclo_actual()`, que en `backend/context.py:683` es `lambda: self.cycle_logger.ciclo_id`.
- `CycleLogger.ciclo_id` = `self._reg.id` y **deja huecos** (alarmas en CICLO con `ciclo_id` NULL):
  1. Al iniciar: `_reg.id` lo fija la tarea asíncrona de `EscritorBD` que crea el ciclo; hasta que corre, `ciclo_id` es None.
  2. Al terminar: `_on_fin` (fallo/cancelación/emergencia/COMPLETADO, inmediato) pone `_reg = None`; mientras la máquina sigue en CICLO esperando la confirmación, toda alarma nueva queda sin ciclo. La causa del fallo aparece en el tick del FALLO (paso 5, máquina de estados) antes de `cycle_logger.update()` (paso 6), así que esa sí lleva ciclo; las posteriores no.
  - Corrección (P1, en el escritor): usar el ciclo de pantalla (`ciclo_id_pantalla`, que cubre el ciclo cerrado aún en CICLO) y resolver el id pendiente de creación en el hilo escritor (el registro `_RegistroBD` se resuelve al escribir, con espera acotada).

### FC-06: fase en la que terminó el ciclo
- Hoy no se publica. `progreso_ciclo.armar_progreso` deriva `fase_activa` de `estado.fase_ciclo`; al terminar, `fase_ciclo` es terminal (`FALLO_<FASE>`, `CANCELADO`, `EMERGENCIA`, `SENSOR_AUSENTE`, `FALLO_PUERTA_*`, `COMPLETADO`...), `activa` = None y la fase cortada, cuyo registro de `ciclo_fases` cerró `_on_fin` (`cerrar_fase_abierta`), aparece como `completada`.
- Fuente para `fase_terminacion`: la última fila de `ciclo_fases` del ciclo (la que estaba abierta al terminar), o `FALLO_<FASE>` cuando aplica.

### FC-08: SEN-11 y NO CONFORME
- `state_machine/states/ciclo.py`: `_marcar_referencias_sin_lectura` (l. 842, llamada en l. 1185) pone `_no_conforme`, publica `estado.no_conforme`/`motivo_no_conforme` (`_publicar_no_conforme`), anota `avisos_ciclo` con `ticket_ciclo.no_conforme_referencia` y activa `SEN_11`. Apertura automática bloqueada por `no_conforme`; confirmación ignorada sin `no_conforme_reconocido` (l. ~1007).
- Backend: `rutas/ciclo.py` (409 en `acknowledge` l. 530, `POST /cycle/acknowledge-no-conforme` l. 555), `rutas/_comun.py` (`_no_conforme_status`...), `core/runtime/status.py` l. 180-188, `bitacora.py` (`ciclo_no_conforme_reconocido`), ticket `ticket_formatter.py` (`avisos_no_conforme`, `ciclo_no_conforme`), `cycle_logger.py` l. 523.

### FC-11: `tiene_actuador`
- Clase de puerta: `devices/puertas/base_puertas.py` (`tiene_actuador = True`), `simple_door.py` (`False`); `door_factory.tipo_tiene_actuador(door_type)`; servicio `services/domain/puertas/ser_puertas.py:112` `tiene_actuador(door_name)` (puerta desconocida → True). El endpoint de puertas (`rutas/puertas.py:85`) publica `sin_actuador`. `/status` no lo publica todavía.
