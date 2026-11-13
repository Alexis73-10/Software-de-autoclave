# Tanda 31: entrega de la cámara antes de confirmar el ciclo (7-nov-2026)

Responde e informa SOLO en español. Prioridad: velocidad por tarea; cambio mínimo. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; 1 revisor de seguridad al final sobre el diff de ENT-01, ENT-03, ENT-04 y ENT-07. Especificación: `docs/mis_plans/planeacion_entrega_camara_fin_ciclo.md` (ENT-01 a ENT-12, decisiones de Cristian del 7-nov). Ante ambigüedad, lo seguro y `DECISIÓN SIN CONFIRMAR` en el informe.

## Requisito previo
Verifica que exista `docs/informes/tanda30/CERRADO.txt` sin `BLOQUEADO:`, que la rama actual sea `dev` y que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los archivos de `docs/`, `AJUSTES.md` y `habblaud/` de Cristian no cuentan; no los toques). Si no cuadra: `docs/informes/tanda31/CERRADO.txt` con `BLOQUEADO:` y el motivo, y termina.
Rama `tanda31` desde `dev`. Lleva `docs/informes/tanda31/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Pasos
1. **Lectura** (sin cambios): `services/domain/logging/cycle_logger.py` (`update`, `_on_fin`, `_seguir_pantalla`, `_seguir_secado_tras_fallo`), `ticket_formatter.format_footer`, `state_machine/states/ciclo.py` (`run` paso 0, `_mantener_apertura_automatica`, `ack_confirma_estado_seguro`), `cycle_phases/protocolo_fallo.py` (`_update`, buzzer), `core/runtime/camara_segura.py`, `backend/rutas/ciclo.py` (`acknowledge_cycle`), `server_reasignacion._reautenticar`, `services/domain/progreso_ciclo.py`, `PantallaCicloEnCurso.qml`, `bridge/comandos_ciclo_en_curso.py`, el respaldo de ciclos y el cierre de ciclos al arrancar. Anota en `estado.md` dónde va cada ENT.
2. **ENT-01/02/12** decisión de entrega (componente puro con pruebas) y publicación en `/cycle/current/progress`.
3. **ENT-03/04/05** compuerta de `/cycle/acknowledge`, confirmación forzada (ingeniero + reautenticación + bitácora `ciclo_confirmado_sin_entrega` en `bitacora.CATEGORIAS` seguridad) y excepción del paro; códigos en `sesion_backend.codigos_conocidos` con texto es/en.
4. **ENT-06/07/08/10** CycleLogger: separar «resultado» (fila E, «Error de ciclo», F0, guardado con `fecha_resultado`) de «cierre» (filas E periódicas durante la espera, pie y `fecha_fin` en la entrega o confirmación); migración de esquema; arranque tras corte con resultado y sin `fecha_fin`; respaldo y reimportación; reimpresión idéntica.
5. **ENT-09/11** pantalla (indicador en lugar de CONFIRMAR, botón de confirmación forzada solo con sesión de ingeniero, modal y reautenticación; textos en `ui_qml/domain/`), PDF y correo al cierre.
6. **Cierre**: pruebas por ENT (backend, CycleLogger con ticket simulado comparando contra el formato de §ENT-06, controlador y QML; incluir: fallo presurizado, cancelación, COMPLETADO con espera, sensor perdido + forzado, paro, corte durante la espera); suite completa en verde; `CLAUDE.md` (sección «Tanda 31»), riesgos HAZ-ENT-01..04 en `docs/riesgos/registro_riesgos.md`, trazabilidad REQ, banco (bloque T31) e informe `docs/informes/tanda31/R31_informe.md`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda31/CERRADO.txt` (fecha, commit del merge, suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.
