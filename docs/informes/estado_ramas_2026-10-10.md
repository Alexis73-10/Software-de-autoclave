# Estado de las ramas vivas con worktree (2026-10-10)

Informe de solo lectura. No se hizo merge, rebase ni cambio en ninguna rama. Medido contra `dev` en `e9affa1` (dos commits por encima de `origin/dev` = `77477f5`: protocolo serial v2 y la línea de §5.8). Por esos dos commits, los conteos "atrás" son 2 más que los del prompt.

Conflictos obtenidos con `git merge-tree --write-tree --name-only dev <rama>` (git 2.53), sin tocar el árbol.

## Tabla

| Rama | Worktree | Delante / atrás de dev | Base común | Archivos en conflicto | Cambios sin commit en el worktree | Plan que la gobierna | Estado del plan |
|---|---|---|---|---|---|---|---|
| `alarmas-parte-a` | `.worktrees/alarmas-parte-a` | 20 / 16 | `9a94de4` (2026-10-06) | `backend/server.py`, `services/domain/logging/db_manager.py`, `services/domain/loop/control_loop.py`, `tests/test_io_test_mode_endpoints.py` | Ninguno de fuente. Solo `docs/informes/lotes_auditoria/lote_1_proceso_seguridad.md` sin seguimiento (idéntico al de dev). | Spec `docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md`, plan `docs/superpowers/plans/2026-10-07-sistema-alarmas-parte-a.md`, informe `docs/informes/sistema_alarmas_parte_a.md` (solo en la rama) | Parte A terminada: el informe de la rama dice "lista para unir a `dev` cuando la apruebes" (1799 pruebas en verde en la rama). Partes B y C sin empezar. |
| `feature/roles-sensor-temperatura` | `.worktrees/roles-sensor-temperatura` | 16 / 49 | `3a2e51c` (2026-09-02) | `core/managers/cycle_manager.py`, `ui_pyside/main_window.py` | Ninguno de fuente. Solo `.pyc` y `src/autoclave.egg-info/*` (artefactos de instalación; con `--ignore-space-at-eol` queda 1 archivo con 3 líneas en `SOURCES.txt`). | Spec y plan `docs/superpowers/{specs,plans}/2026-09-02-roles-sensor-temperatura-ciclos-liquidos*.md` (versionados en dev) | **Reemplazado** por `docs/mis_plans/planeacion_sensores_ciclo.md` (borrador rev. 2, sin aprobar), decisión S-7: "La rama no se integra: se rehace sobre `dev` tomándola como referencia". El plan nuevo cambia la semántica (Principal obligatorio, sin caída silenciosa a `temp_camara`, `PUT` todo-o-nada con auditoría y permisos). |
| `worktree-anuncios-voz` | `.claude/worktrees/anuncios-voz` | 17 / 56 | `e0fea30` (2026-08-12) | `ui_pyside/main_window.py` | Ninguno de fuente. `.pyc`, `src/autoclave.egg-info/*`, `.claude/settings.local.json` modificado, y `docs/superpowers/plans/2026-08-12-anuncios-voz.md` sin seguimiento (difiere en 1 línea de la versión ya versionada en dev). | `docs/mis_plans/planeacion_anuncios_voz.md` y `docs/superpowers/plans/2026-08-12-anuncios-voz.md` (versionados en dev) | Implementado en la rama (17 commits, último: revisión final), pero el diseño figura "pendiente de aprobación" y los checkboxes del plan están sin marcar. `planeacion_i18n.md` D-16 prevé un plan propio de cierre: unir esta rama, locuciones reales con Piper en es y en-US. |

## Observaciones por rama

### `alarmas-parte-a`
- Los cuatro conflictos vienen de trabajo posterior en dev (autenticación etapas 2-4 y el protocolo serial v2 de hoy). `server.py` es el más delicado: la rama cambia `/status` (contrato nuevo de alarmas, `_hardware_connected` con COM-01) y dev acaba de cambiar `card_connected` y añadir `comunicacion` en el mismo diccionario. La rama también tiene el commit `7260947` ("main usa card_connected"), que toca el mismo tema.
- `control_loop.py` y `db_manager.py` son Clase C (ControlLoop, historial en BD). Conviene resolverlos con revisión `safety-reviewer` y `timing-auditor` (la rama mueve la escritura del historial a un hilo propio).
- **Ojo con el commit C (documentación):** dev tiene sin seguimiento copias de `analisis_sistema_alarmas.md` y del plan de la Parte A idénticas a las de la rama, y una copia **vieja** de la spec (le faltan las 12 líneas de correcciones del commit `f1b0e0b`). Si se versionan en dev antes de unir la rama, la spec dará un conflicto add/add y la versión vieja podría ganar por descuido. Recomendado: dejar esos tres archivos fuera del commit C y que lleguen con la rama.

### `feature/roles-sensor-temperatura`
- Tocaba control Clase C (CALENTAMIENTO, ESTERILIZACION, F0, ticket) con una semántica que la planeación nueva descarta explícitamente.
- Base de hace 5 semanas; dev ya tiene 49 commits encima (autenticación, OPCIONES QML, endpoints de parámetros con guardas).

### `worktree-anuncios-voz`
- Un solo conflicto (`ui_pyside/main_window.py`, la tarjeta de acceso y el `notify_ui_ready`). El resto es código nuevo (`audio/`, endpoints `/audio/*`, vista PySide6) más un paso 8 no bloqueante en `ControlLoop._tick()` y un atributo informativo nuevo en `EstadoAutoclave`/`ProtocoloFallo`.
- Base de hace 2 meses: aunque solo hay un conflicto textual, `control_loop.py` y el estado han cambiado mucho en dev; un merge limpio en texto no garantiza que la integración en el `_tick()` siga siendo correcta.
- Hay dependencias nuevas (`sounddevice`, `soundfile`) que no están en `requirements.lock.txt` de dev.
- `main` tiene dos mp3 (`src/autoclave/audio/abriendo puerta.mp3`, `cerrando puerta.mp3`) que no están en dev; pueden tener relación con esta rama.

## Recomendación

| Rama | Recomendación | Motivo |
|---|---|---|
| `alarmas-parte-a` | **Rebasar primero** (o merge con resolución manual) y luego integrar | Trabajo terminado y probado, pero con 4 conflictos en archivos Clase C y en el `/status` que se acaba de cambiar. Resolver en el worktree, correr la suite completa con `PYTHONPATH=src`, pasar `safety-reviewer`/`timing-auditor` y entonces unir. Antes, decidir si se quiere unir ya o esperar a B/C (memoria: "pausado; faltan decidir la rama"). |
| `feature/roles-sensor-temperatura` | **Archivar** (tag, p. ej. `archivo/roles-sensor-temperatura-2026-09`, y borrar la rama y el worktree cuando lo apruebes) | `planeacion_sensores_ciclo.md` S-7 decide no integrarla y rehacerla sobre dev. El tag la conserva como referencia que el plan nuevo cita. |
| `worktree-anuncios-voz` | **Rebasar primero**, pero solo cuando se apruebe `planeacion_anuncios_voz.md` y se abra el plan de cierre de D-16 | Implementación completa y con un solo conflicto, pero el diseño sigue sin aprobar, el plan nuevo de i18n le pide manifiesto por idioma y textos desde catálogo, y la base es muy vieja. Mientras tanto, dejarla como está. |
