# Tanda 31: estado (rama tanda31)

Paso 1 Lectura: Hecho. Pasos 2-3 (ENT-01/02/03/04/05/12): Hecho (e50a2a04). Paso 4 (logger/BD/respaldo): en curso. Paso 5 (pantalla): en curso. Paso 6: Pendiente.

## Mapa ENT (src/autoclave/)
- ENT-01/02/12: nuevo state_machine/states/entrega_camara.py (puro); lo crea CicloState (states/ciclo.py run paso 0, l.1050-1107; _mantener_apertura_automatica l.933); publica en estado.entrega_camara; backend/rutas/ciclo.py get_current_cycle_progress (l.149-200) agrega `entrega`.
- ENT-03/04/05: rutas/ciclo.py acknowledge_cycle (l.580); _reautenticar de server_reasignacion (l.254) a reutilizar; sesion_backend.codigos_conocidos; bitacora.CATEGORIAS seguridad; ack_confirma_estado_seguro (ciclo.py l.381).
- ENT-06/07/08/10: cycle_logger._on_fin (l.575) a partir en resultado/entrega; db_manager migración v14 fecha_resultado, cerrar_ciclos_interrumpidos (l.955), respaldo_ciclos (registro nuevo `resultado`), context._numeracion_y_ciclos_interrumpidos; ticket_formatter.format_footer; ENT-08 ya cumple (control_loop._acumular_f0), falta prueba.
- ENT-09/11: PantallaCicloEnCurso.qml (terminado l.86, botón l.885, modal l.1017), bridge/comandos_ciclo_en_curso.py, ui_qml/domain/; no hay PDF/correo automático al cierre: solo ocultar acciones de Historial sin fecha_fin (acciones_ciclos.py, rutas/historial.py).
## Decisiones
- CicloState crea el componente y publica estado.entrega_camara; CycleLogger lee estado.
- Respaldo: registro nuevo `resultado`; `cierre` solo en la entrega.
