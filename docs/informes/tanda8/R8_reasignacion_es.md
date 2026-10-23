# R8 — Opciones avanzadas: reasignación de entradas y salidas (tanda 8, D8-5.12) ★

Rama `tanda-8-r8` (worktree `agent-a4c98b7bda15d252c`). Sin push. Etapa ★ (seguridad).

## Qué se hizo, punto por punto de D8-5.12

| Requisito D8-5.12 | Estado | Dónde |
|---|---|---|
| Solo el ingeniero (§3.5) | Hecho. Antes técnico e ingeniero. **DECISIÓN SIN CONFIRMAR** | `ui_qml/domain/permisos_opciones.py`; backend `requiere_rol(ROL_INGENIERO)` en las 4 rutas |
| Solo fuera de ciclo (R-01) | Hecho: solo PREPARACION o PREPARADO, sin modo prueba, sin apagado en curso, sin estado seguro actuando (409). En FALLA tampoco (**DECISIÓN SIN CONFIRMAR**). Se revalida bajo `_sm_lock` justo antes de detener el lazo; si cambió, se deshace la escritura | `backend/server_reasignacion.py` |
| Reautenticación | Hecho: contraseña del usuario de la sesión; los fallos suman al bloqueo del login (429) | `_reautenticar` |
| Doble confirmación con alerta de criticidad | Hecho: `confirmar` (428 si falta) + alerta en la UI con las funciones críticas y aviso de calibración para las analógicas | API y `OpcionesReasignacion.qml` |
| Conflictos y puertos inexistentes rechazados en el backend | Hecho (422): dos funciones en el mismo puerto (incluidas las que el equipo no usa), puerto fuera de la tarjeta, analógica de temperatura en grupo de presión o al revés y, tras la revisión, **puerto analógico sin calibración** | `core/runtime/asignacion_io.py` (`validar`, `puertos_sin_calibracion`) |
| Confirmación reforzada (nombre escrito) para interlock de puerta, paro y finales de carrera | Hecho: se acepta el nombre en español o en inglés, sin distinguir mayúsculas ni tildes. Lista de reforzadas y críticas: **DECISIÓN SIN CONFIRMAR** (`REFORZADAS`/`CRITICAS`) | `nombre_coincide` |
| Tabla función / puerto actual / puerto nuevo / tipo / crítica | Hecho; lista todas las funciones con puerto (las que el equipo no usa, marcadas «sin uso en este equipo», porque igual ocupan su puerto) | pantalla |
| Restaurar asignación de fábrica, con confirmación | Hecho (confirmación + contraseña + reinicio). Funciona también con el archivo dañado (bytes no UTF-8) | `POST /io/assignment/factory` |
| Vigente en la carpeta de datos (ProgramData), fábrica en el YAML; respaldo O2h | Hecho: `data/asignacion_io.json` bajo `app_root()` (solo los cambios respecto de fábrica), escritura atómica con `.bak`; fábrica en `io_ports` del YAML de la instancia (o el código). Va en el respaldo con la parte de calibración; al restaurar solo la aplica un ingeniero, validada antes de escribir | commits 44f95af, f835669 |
| Bitácora: función, puerto anterior, puerto nuevo, usuario | Hecho: `reasignacion_io`, `reasignacion_io_fabrica`, `reasignacion_io_rechazada`, `reasignacion_io_verificada`, `reinicio_control` | `core/runtime/bitacora.py` |
| Reinicio con «Se reiniciará el control» y verificación en el puerto nuevo | Hecho: el lazo se detiene (ALL_OFF) y el backend sale con código 75; el lanzador lo relanza. Al arrancar se aplica la asignación antes de construir SetOutput, puertas y lazo. Verificación: ver «Cambios de la revisión» | commits 34c3660, 24bffee, effcd5a |
| Estilo de Entradas/Salidas, barra flotante, textos es/en, capturas | Hecho. Diseño PROVISIONAL sin mockup | `docs/informes/tanda8/capturas/R8_{es,en}_1..10_*.png` |
| Pruebas: conflictos, permisos, en ciclo, persistencia, restauración, lectura/accionamiento en el puerto nuevo con la planta simulada | Hecho | ver «Pruebas» |

Corrección propia: `agua_bomba` existe como DI 09 y DO 18; el núcleo indexaba por nombre y cualquier cambio de `agua_bomba` movía siempre la DO (la DI no se podía reasignar). Ahora los nombres repetidos se identifican con el tipo delante (`DI:agua_bomba`); los demás conservan su nombre, así que un archivo ya guardado sigue valiendo (65c5e9e).

## Cambios por la revisión ★

Revisores lanzados en paralelo sobre `git diff tanda-8...tanda-8-r8`: `safety-reviewer`, `timing-auditor`, `sensor-role-auditor`.

Primera vuelta: 1 Crítico (SEN-01), 4 Altos (SAF-01, SAF-02, SEN-02, SEN-03) y varios medios. Corregidos en effcd5a y 164a023:

- **SEN-01 (Crítico)** — `calibration.yaml` trae 7 entradas de presión de usuario: una función en AI 16 se habría leído sin calibrar y no se habría podido calibrar. Ahora un puerto analógico sin calibración de fábrica y de usuario se rechaza (422), también al restaurar un respaldo.
- **SAF-01 / SEN-02 (Altos)** — la calibración es por puerto: una analógica reasignada usa la del puerto nuevo. Ahora no se puede verificar (ni iniciar ciclos) sin un `calibracion_cambio` de ese sensor posterior a la reasignación.
- **SAF-02 / SEN-03 / SEN-04** — la verificación automática daba «ok» en DI/DO siempre (la trama trae todos los puertos) y nada bloqueaba el inicio de ciclo. Ahora:
  - la comprobación automática solo registra `trama_presente` / `sin_respuesta`;
  - toda función reasignada queda **sin verificar**: alarma nueva **SEN-04** (AVISO, bloquea el inicio) y una condición en `AlarmManager.condiciones_bloqueo` que mantiene bloqueado el inicio aunque la alarma se resuelva al reconocer una FALLA (un hilo la reactiva);
  - el ingeniero verifica cada función (`POST /io/assignment/verify`, contraseña y, si es reforzada, nombre escrito) y el backend exige evidencia: entrada digital con un cambio de estado observado en el puerto nuevo; salida encendida en modo prueba después de reasignar (`salida_prueba` en la bitácora); analógica con lectura válida y calibrada después de reasignar.
- **SAF-03** — lo pendiente de verificar no se pierde con otra reasignación ni al restaurar un respaldo (pendientes = diferencias contra lo que usa el proceso ∪ pendientes previos).
- **SEN-06** — se listan todas las funciones. **SEN-07** — tipo correcto en la bitácora para `agua_bomba`.
- **TMG-01** lock de escritura y rechazo con un reinicio en curso; **TMG-05** lectura del archivo previo en bytes; **TMG-07** deshacer ante cualquier error; **TMG-06/SAF-05** la verificación automática ya no borra la marca.
- **SAF-06 / TMG-03** — solo se reinicia el backend que el lanzador vigila (variable `AUTOCLAVE_RELANZABLE`); si no, la asignación se guarda y rige al próximo arranque. **TMG-04** — el lanzador no relanza tras cerrar las pantallas.

Segunda vuelta: ver «Resultado de la re-revisión».

## Resultado de la re-revisión

**Segunda vuelta** (`safety-reviewer`, `timing-auditor`, `sensor-role-auditor` sobre el diff corregido). Corregido en 4492a94:
- **SAF-01 / TMG-11** — la evidencia (salida encendida en modo prueba, calibración a dos puntos) ya no se busca en la bitácora ordenada por el reloj de pared: se guarda en memoria del proceso (`ctx.asignacion_evidencia`), solo cuenta la hecha EN ESTE ARRANQUE y en el puerto vigente.
- **SAF-02** — fuera de ciclo, PREPARACION/PREPARADO accionan salidas solos: el control automático no enciende las salidas reasignadas sin verificar ni, con una analógica pendiente, las de energía (vapor, aire comprimido). El modo prueba sí (para verificarlas).
- **SAF-03 / TMG-10** — no se verifica con una asignación guardada que aún no rige (reinicio pendiente).
- **SEN-02** — restaurar «último» solo copia un registro de calibración del mismo puerto.
- **TMG-12** — SEN-04 bajo lock propio, leyendo los pendientes dentro de él.

**Tercera vuelta** (corregido en d41822f):
- **SAF-01** — el venteo y el alivio (`descompresion_rapida/lenta/chaqueta`, aire atmosférico de cámara) nunca se inhiben, aunque estén pendientes: sin ellos no habría venteo automático ni estado seguro.
- **SAF-02** — las puertas mandan por canal, no por nombre: `SetOutput` publica `canales_inhibidos` y `AdvancedDoor._accionar` no enciende un canal inhibido (apagar siempre pasa). Abrir o cerrar pendiente inhibe los dos de esa puerta (no queda un cierre sin reapertura).
- **SEN** — restaurar calibración guarda el puerto físico en la bitácora y anula la evidencia de calibración de ese sensor.

**Cuarta vuelta** (re-revisión rápida `safety-reviewer` + `timing-auditor` solo sobre el diff de la tercera): **0 Críticos, 0 Altos**, 3 Medios, corregidos también en d41822f:
- **SAF-01 / TMG-01 (Medio)** — carrera entre verificar y restaurar calibración: la evidencia se miraba fuera del lock de archivos y se anulaba después de escribir. Ahora restaurar anula la evidencia ANTES de escribir y dentro de `_lock_archivos`; el PATCH la registra dentro del lock; `POST /io/assignment/verify` vuelve a mirar la evidencia con `_lock_escritura` y `_lock_archivos` tomados (orden de locks comprobado: nadie toma `_lock_escritura` con `_lock_archivos` tomado). Además, restaurar un respaldo con calibración anula toda evidencia AI.
- **TMG-02 (Medio)** — dos verificaciones simultáneas podían dejar como último escrito un conjunto de inhibidas viejo (lado seguro, pero equipo sin vapor y sin alarma hasta reiniciar). Ahora `inhibir_salidas_sin_verificar` corre bajo el mismo lock que SEN-04 y lee los pendientes dentro.

Respuestas del `safety-reviewer` a las preguntas de la cuarta vuelta: inhibir desbloquear lleva la puerta a ERROR cerrada (seguro); inhibir bloquear deja la puerta en ERROR o sin sellar, pero ningún ciclo puede iniciar mientras haya pendientes (SEN-04 + `condiciones_bloqueo`) y fuera de ciclo nada mete vapor a la cámara; ninguna salida de energía queda enclavada (la inhibición solo bloquea encendidos y el conjunto solo se achica tras arrancar).

**Altos/Críticos abiertos: 0.**

## Commits (rama `tanda-8-r8`)

| Commit | Contenido |
|---|---|
| 44f95af | Núcleo de asignación de E/S (fábrica, vigente en data/, validación) |
| a5d5d06 | SetOutput y puertas toman el canal de la asignación |
| 34c3660 | El backend aplica la asignación al arrancar, bloquea si está dañada, verifica tras reasignar |
| 24bffee | Reinicio ordenado del backend y relanzamiento desde el lanzador |
| 4f77a25 | Opciones avanzadas solo para el ingeniero |
| f835669 | API de reasignación |
| a03aafe | Pantalla de Opciones avanzadas |
| 290a501 | Prueba con la planta simulada (4 programas) |
| 65c5e9e | Nombres repetidos en dos tipos (`agua_bomba`) |
| effcd5a | Correcciones de la primera revisión ★ |
| 164a023 | Verificación por función en la pantalla, banco QML y capturas es/en |
| cdbeabf | Riesgos HAZ-IO-01 a 04, hoja de banco, SEN-04 en el catálogo |
| 4492a94 | Correcciones de la segunda vuelta |
| d41822f | Correcciones de la tercera y cuarta vuelta |
| (este) | Informe |

## Pruebas

`PYTHONPATH=<worktree>/src`, `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a4c98b7bda15d252c\src\autoclave\__init__.py`. Por la regla 8 vigente (cambio de reglas de la tanda 8) **no se corrió la suite completa**: solo lo que toca la etapa y lo que la importa.

Pruebas nuevas:
- `tests/test_r8_asignacion_io.py` — fábrica, validación, conflictos, nombres repetidos, archivo, lectura en el puerto nuevo.
- `tests/test_r8_salidas_puertas.py` — SetOutput y puertas por asignación.
- `tests/test_r8_arranque.py` — persistencia tras reiniciar, archivo dañado, verificación automática, bloqueo de inicio que sobrevive al reconocimiento de una FALLA.
- `tests/test_r8_reinicio_backend.py` — reinicio, relanzamiento, sin lanzador.
- `tests/test_r8_reasignacion_api.py` — permisos, en ciclo/FALLA/modo prueba, carrera con inicio de ciclo, conflictos, confirmaciones, reautenticación y bloqueo, persistencia y bitácora, fábrica, respaldo, verificación con evidencia, SEN-01, escritura.
- `tests/test_r8_reasignacion_ui.py` — controlador y carga del QML; cableado en Opciones.
- `tests/test_r8_reasignacion_banco_qml.py` — recorrido de la pantalla en es y en (con `R8_CAPTURAS=1` genera las capturas).
- `tests/test_r8_planta_simulada.py` — con la planta simulada de T11/E1, el cableado de la planta movido a puertos libres (Vapor cámara DO 04→25, Presión cámara AI 09→13, Temperatura cámara AI 01→04, Paro DI 11→15): los 4 programas de fábrica terminan COMPLETADO sin tocar nunca el canal viejo; control negativo sin reasignar. Tabla en `docs/informes/tanda8/R8_ensayo_tabla.md`.

Resultados:

Tras d41822f (última corrida, en el worktree):

`python -m pytest tests/test_r8_*.py tests/test_backend_calibration_endpoints.py tests/test_es_controlador.py tests/test_o2h_respaldo.py tests/test_advanced_door.py tests/test_advanced_door_safe_mode.py tests/test_set_io_reset_outputs.py tests/test_comandos_puerta.py tests/test_servicio_puertas.py tests/test_puertas_fallas_endpoints.py` → **311 passed, 1 skipped** (137 s). Antes, sobre el diff de la tercera vuelta, además `test_door_from_profile.py` y `test_e1_puertas_perfil.py`: 276 passed, 1 skipped.

**Suite completa: no corrida** (la corre la sesión principal al unir).

## Registro de riesgos y hoja de banco

- `docs/riesgos/registro_riesgos.md`: HAZ-IO-01 (puerto equivocado), HAZ-IO-02 (calibración por puerto), HAZ-IO-03 (archivo dañado), HAZ-IO-04 (reinicio).
- Hoja de banco (`docs/mis_plans/hoja_pruebas_banco/pruebas.py`, regenerada): D-R8-01 a D-R8-05 y E-R8-01.
- `docs/catalogo_alarmas.md`: SEN-04.

## DECISIONES SIN CONFIRMAR

1. Opciones avanzadas solo para el ingeniero (el técnico la pierde).
2. Lista de funciones reforzadas (paro, puerta cerrada/abierta, atrapamiento, bloqueo/desbloqueo de puerta) y críticas (`asignacion_io.REFORZADAS`/`CRITICAS`).
3. No se reasigna en FALLA (el protocolo de fallo puede estar venteando).
4. Verificación final por el ingeniero con evidencia y alarma SEN-04 que bloquea el inicio de ciclo hasta verificar (va más allá del texto de D8-5.12, por la revisión ★).
5. La calibración sigue al puerto, no al sensor: una analógica reasignada se debe recalibrar.
6. El nombre escrito se acepta en español o en inglés, sin distinguir mayúsculas, tildes ni espacios repetidos.
7. Restaurar fábrica pide confirmación y contraseña, no el nombre escrito.
8. Un respaldo con asignación solo la aplica si restaura un ingeniero; con técnico se omite. No reinicia: rige al reiniciar.
9. Puertos ofrecidos: DI 1-48, DO 1-32, AI 1-8 (temperatura) y 9-16 (presión), sin consultar la versión de la tarjeta.
10. Sin lanzador que relance el backend, se guarda y no se reinicia.
11. Nombres en dos tipos con el tipo delante (`DI:agua_bomba`).

## PREGUNTAS PARA CRISTIAN

1. SAF-04 (preexistente, R8 le suma disparadores): con la asignación dañada el equipo queda bloqueado y no corre la recuperación de ciclo interrumpido ni el estado seguro; tras un corte con la cámara presurizada no habría venteo hasta restaurar. ¿Permitir el estado seguro con las salidas de descompresión de fábrica en ese bloqueo?
2. ¿Qué nivel lee un DI sin cablear en la tarjeta actual (0 o 1)? Decide la gravedad de un paro mal reasignado.
3. ¿La calibración de usuario debe moverse con la función (sensor) o quedarse en el puerto (hoy)?
4. ¿Están poblados DI 15-48 y DO 25-32 en todas las tarjetas en campo?
5. TMG-02 (primera vuelta): el reinicio no vacía historial de alarmas ni registro de ciclo antes de salir (sin ciclo en curso, el riesgo es perder un evento del último segundo). ¿Reutilizar la secuencia de «Apagar equipo»?

6. Dependencias entre salidas (pregunta del `safety-reviewer`, cuarta vuelta): solo se emparejan abrir/cerrar de cada puerta. Si `agua_bomba` (DO) queda pendiente e inhibida, la bomba de vacío podría correr sin agua de sello durante el movimiento de puerta (daño al equipo, no a personas). ¿Inhibir también `bomba_vacio` cuando `agua_bomba` está pendiente?
7. Una salida que pasa a inhibida no se apaga si ya estaba encendida (hoy no ocurre: el conjunto se fija al arrancar y luego solo se achica). ¿Se quiere un apagado explícito por si en el futuro se recalcula en caliente?

## Puntos de choque con otras etapas

- `src/autoclave/i18n/es.json` y `en.json`: sección nueva `reasignacion`, eventos de bitácora nuevos y alarma `SEN-04` (edición textual, sin reformatear).
- `src/autoclave/backend/server.py`: respaldo O2h (export/restore) y registro del módulo al final.
- `src/autoclave/ui_qml/qml/Pantallas/Opciones.qml` (Loader nuevo y `cambiosPendientes`), `ui_qml/controllers/__init__.py`, `ui_qml/domain/permisos_opciones.py` y sus pruebas.
- `state_machine/alarms/catalogo.py` (SEN-04) y `alarm_manager.py` (`condiciones_bloqueo`).
- `backend/context.py`, `backend/main.py`, `exe_unico.py`, `devices/io/set_io.py`, `devices/factory/factory.py`.
- `docs/riesgos/registro_riesgos.md`, `docs/mis_plans/hoja_pruebas_banco/*`, `docs/catalogo_alarmas.md`.
- `src/autoclave/devices/puertas/advanced_door.py` (`_accionar`, d41822f) y `server.py` restaurar calibración / restaurar respaldo (d41822f).
- `db_manager`: sin cambios; **sin migración de base de datos** (la evidencia vive en memoria y en `audit_log` con eventos nuevos).

## Pendientes

- Capturas con datos reales del equipo (las actuales usan el doble del backend).
- Mockup aprobado de la pantalla.
- La fecha de «última calibración» de la pantalla de calibración se busca por nombre de sensor: tras reasignar puede mostrar la del puerto viejo hasta recalibrar (informativo; el bloqueo exige la calibración nueva).
