# A9 — Niveles de alarma y bitácora (tanda 9)

Rama: `tanda-9-a9` (desde `tanda-9`, 090a8bf). Puntos: D9-2 y D9-6 de `docs/mis_plans/decisiones_tanda_9.md`.

## D9-2. Niveles de alarma (H3)

SEN-01, SEN-03, SEN-06, SEN-07 y CIC-10 pasan de AVISO a ALARMA en `src/autoclave/state_machine/alarms/catalogo.py`.
Se conserva su `bloquea_inicio` (SEN-01, SEN-06, SEN-07: sí; SEN-03, CIC-10: no) y su despeje automático.

Efecto observable (sin cambiar código fuera del catálogo):
- En `/status` el nivel compatible pasa de `ALERTA` a `FALLA` (panel de notificaciones: prioridad "media", estilo de alarma).
- Al ser ALARMA requieren reconocimiento: si la condición desaparece sin reconocerlas quedan como
  "resuelta sin reconocer" hasta que alguien las reconozca. Esa instancia NO bloquea el inicio
  (`condiciones_bloqueo` y PREPARADO solo miran instancias ACTIVA), así que el gate de inicio no cambia.
- Textos es/en: no cambian. Los títulos, plantillas y acciones de `alarmas.<código>` no nombran el nivel; el
  rótulo del nivel sale de `Nivel.nombre_compat`. No hubo textos visibles nuevos.

Documentación: `docs/catalogo_alarmas.md` (§3 `ERROR_AI_<SENSOR>`, tabla de correspondencia §9 con SEN-01, SEN-03,
SEN-06/07 y CIC-10, y nota D9-2).

Pruebas: `tests/test_alarmas_catalogo.py` — `test_niveles_migrados_iguales_a_hoy` con los 5 códigos en ALARMA y nueva
`test_d9_2_alarma_conserva_bloqueo_y_despeje` (5 casos: nivel, reconocimiento, `FALLA`, bloqueo y despeje).
Primero en rojo (6 fallos), luego en verde.

No se crearon códigos de alarma nuevos (SEN-10 la crea S9).

## D9-6. Bitácora solo con lo necesario (H18)

Retirados de `audit_log` (siguen en el log de desarrollo con `logger.info`, función nueva
`_log_desarrollo(evento, sesion, usuario=..., **campos)` en `src/autoclave/backend/server.py`):
- `rechazo_401/403/409` y cualquier `rechazo_<status>` de `_rechazar` (también los 422/503 que pasaban por ahí);
- `suspension_entra` / `suspension_sale` (el endpoint `/ui/standby` sigue existiendo y respondiendo 200);
- `puerta_orden`, `puerta_orden_rechazada`;
- `PROGRAMA_SELECCIONADO`, `PROGRAMA_SELECCION_RECHAZADA`;
- `correo_prueba`, `impresora_prueba`, `impresion_ganancias`.

`core/runtime/bitacora.py::EVENTOS` ya no los lista; se borraron sus textos `bitacora.ev.*` y `bitacora.tipo.*`
en `es.json` y `en.json` (12 claves × 2 secciones × 2 idiomas). El resto de eventos no cambia (seguridad,
configuración, sesión, `correo_enviado`, `atrapamiento_orden_invertida`, reasignación de E/S).

Pruebas:
- Nueva `tests/test_a9_bitacora_d9_6.py` (10 pruebas): retirados fuera de `EVENTOS` y sin `_auditar(...)` en el
  backend; `/ui/standby`, 401 (sin sesión), 403 (operador) y 409 (`/units` en CICLO) no escriben en `audit_log`
  y sí en el log; conservados con base real: `unidades_configuradas` (configuración), `login_fallido` y
  `login_ok` (sesión), `falla_reconocida` (seguridad).
- Ajustadas para el nuevo destino (ahora comprueban que NO están en la bitácora y, donde aplica, que sí están en
  el log): `test_s2_cycle_select.py`, `test_s3_source_door.py`, `test_o2e_bitacora.py`, `test_o2f_calibracion_atm.py`,
  `test_o2g_conectividad.py`, `test_puertas_fallas_endpoints.py`, `test_backend_autenticacion.py`,
  `test_io_endpoints.py`, `test_b7_caducidad_tokens.py`. Las pruebas del "Hallazgo D" (registro del rechazo
  con `_sm_lock` libre) siguen y ahora miden `_log_desarrollo`.

## Commits

- `8117089` feat(tanda9-a9): D9-2 SEN-01/03/06/07 y CIC-10 pasan a ALARMA
- `1f1e622` feat(tanda9-a9): D9-6 bitacora solo con lo necesario
- (este informe)

## Resultado de pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-af8b29bbc4b319d85\src\autoclave\__init__.py`
(`PYTHONPATH=<worktree>/src`).

- D9-2: los 87 archivos de `tests/` que usan el gestor de alarmas o estos códigos → `1920 passed, 4 skipped`.
- D9-6 (primera pasada, 88 archivos que usan el backend, la bitácora o i18n): `2 failed, 2202 passed, 3 xfailed`;
  los 2 fallos eran pruebas que esperaban `rechazo_*` en la bitácora (`test_b7_caducidad_tokens.py`,
  `test_backend_autenticacion.py::test_rechazo_por_estado_se_registra_con_el_lock_libre`), ajustadas →
  `99 passed` en esos archivos más la prueba nueva.
- Pasada final (corrida por la sesión principal al reanudar tras el corte de uso, mismo `autoclave.__file__`): los 11 archivos de prueba tocados más `test_t7_avisos_qml.py` → `435 passed in 47.76s`.

## DECISIONES SIN CONFIRMAR

1. **Filas viejas de la bitácora.** En equipos que ya tienen filas de los eventos retirados, esas filas se siguen
   mostrando, pero con el texto genérico (`bitacora.ev_generico` + código) porque sus textos se borraron del
   catálogo (la prueba de i18n exige que `bitacora.tipo.*` coincida con `EVENTOS`). No se borran filas de
   `audit_log` (registro de auditoría: no se toca). Reversible restituyendo las claves.
2. **`_rechazar` con 422/503.** D9-6 dice "todo `rechazo_*` de `_rechazar`": se retiran todos los status, no solo
   401/403/409 (p. ej. `reautenticacion_fallida` de la reasignación de E/S o `ARCHIVO_NO_ESCRIBIBLE`). Los
   intentos de inicio de sesión fallidos o bloqueados siguen en la bitácora (`login_fallido`, `login_bloqueado`,
   que no pasan por `_rechazar`).
3. **Reconocimiento de SEN-01/03/06/07 y CIC-10.** Al ser ALARMA, una instancia resuelta sin reconocer queda en la
   lista de alarmas hasta reconocerla (comportamiento estándar de ALARMA en `AlarmManager`). SEN-01 tiene una
   instancia por sensor: con varias sondas desconectadas y reconectadas habrá que reconocer una por una.

## PREGUNTAS PARA CRISTIAN

- `tests/test_b9b_puertas_permisos_por_rol_diferido.py::test_la_orden_de_servicio_queda_auditada_con_el_usuario`
  (xfail estricto, B9b diferido) espera `puerta_orden` en la bitácora con el usuario. Con D9-6 la orden de puerta
  ya no va a la bitácora. Sigue en xfail (no se tocó); cuando se implementen los permisos por rol de puertas,
  ¿la orden de servicio con sesión de técnico debe volver a la bitácora o basta el log?

## Pendientes

- Ninguno de la etapa. Sin Altos/Críticos (etapa no ★; revisores no requeridos).
