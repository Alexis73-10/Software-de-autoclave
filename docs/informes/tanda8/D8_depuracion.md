# D8 — Depuración (tanda 8, D8-3.27)

Rama: `tanda-8-d8` (desde `23704cb`), worktree `.claude/worktrees/agent-a2648dd3cc2073724`. Fecha: 22-oct-2026.
Fuente: P1 a P12 de `docs/informes/tanda7/D2_depuracion.md`, aceptados en D8-3.27 de `docs/mis_plans/decisiones_tanda_8.md`.
La etapa se hizo en dos sesiones (la primera se cortó por límite de uso después de las etiquetas de archivo; la segunda terminó P5, revisó P8 a P12 y escribió este informe).

## Resumen

| Punto | Qué se hizo | Commit / comando |
|---|---|---|
| P1 | Se conservan los arneses QML de prueba (`qml/Pruebas/*.qml`, `ui_qml/prueba_*.py`, `historial_ejemplo.py`). | Nada que cambiar |
| P2 | `ui_pyside/views/_email_dialog.py` NO se toca aquí: lo retiró la etapa U8 (`b85ea57`, ya unida a `tanda-8`). | — (evita el choque con U8) |
| P3 | Se conservan `ui_qml/domain/{alarmas,reconexion,telemetria}.py`. | Nada que cambiar |
| P4 | 12 mockups e imágenes de diseño movidos de `src/autoclave/images/` a `docs/diseno/mockups/`. | `7f7a407` |
| P5 | Revisión aparte con `safety-reviewer`; se retiran 5 elementos confirmados muertos, se conservan 4 grupos. | `894eb09` |
| P6 | `estudio/` fuera del repositorio, copiado a `C:\Users\tecni\Documents\estudio_autoclave\` y en `.gitignore`. | `d918d5c` |
| P7 | `main` no se toca. | — |
| P8 | Worktree de `alarmas-parte-a` y su rama local ya no existen; `docs/informes/lotes_auditoria/` ya está en `tanda-8` y en `dev`. | Ver b) |
| P9 | Rama local `audit/62304-snapshot` ya no existe; sigue en `origin`. | Ver b) |
| P10 | Etiqueta `archivo/feature-roles-sensor-temperatura` creada y empujada. Worktree NO quitado (git se niega sin `--force`); rama local conservada. | Ver b) |
| P11 | Etiqueta `archivo/worktree-anuncios-voz` creada y empujada. Worktree NO quitado (git se niega sin `--force`); rama local conservada. | Ver b) |
| P12 | `wt_rc` ya no figura en `git worktree list` ni existe la carpeta. | Ver b) |

Puntos de choque: ninguno de los habituales (`i18n/*.json`, `db_manager.py`, QML compartidos) se tocó. P5 toca `hal/measures/converters.py` (también lo cambia S1) y `state_machine/alarms/alarm_manager.py` (también lo cambian `tanda-8`, R8 y S2b): son solo borrados en zonas sin solapamiento; se comprobó con `git merge-tree` (ver d).

---

## a) P4 y P6 (primera sesión)

- **P4** (`7f7a407`): `DISEÑO INTERFAZ -P1 mockup.jpg`, `DISEÑO INTERFAZ_menu.jpg`, `DISEÑO INTERFAZespera.jpg`, `fondo_800x1280.pdf`, `nuevo_usuario.png`, `nuevo_usuario_sin_codigo.png`, `opciones_{ajuste,cajon,flujo,sensor}_comparativo.png`, `pantalla_ciclo_con_grafica_editada.png`, `pantalla_ciclo_sin_grafica.png`. Antes de mover: `grep` en `src/`, `tests/`, `*.spec`, `.qml` y `.qrc`; solo aparecían en comentarios. Los iconos de la UI tkinter (`images/*_icon.png`, `stop_cycle.png`, `images/Icons/*.svg`) NO se movieron: D8-3.27 habla de "mockups e imágenes de diseño", y esos iconos podrían cargarse por rutas dinámicas (DECISIÓN SIN CONFIRMAR 1).
- **P6** (`d918d5c`): `estudio/UI/{ej1.qml,ej2.qml,run.py}` (3 archivos) retirados del índice y `estudio/` agregado a `.gitignore`. Verificado en esta sesión: `C:\Users\tecni\Documents\estudio_autoclave\UI\` contiene los mismos 3 archivos.
- Suite completa después de P4 y P6 (primera sesión, 12:45, `PYTHONPATH=<worktree>/src`, `autoclave.__file__` = `...\agent-a2648dd3cc2073724\src\autoclave\__init__.py`): **5382 passed, 3 skipped, 3 xfailed** (27 min 07 s), igual que la línea base. Log: `docs/informes/tanda8/suites/d8.log`.

## b) P5 — código muerto en zonas de seguridad

Revisión con `safety-reviewer` (solo lectura) de los candidatos de `vulture` que D2 dejó como P5, buscando en `src/`, `tests/`, `tools/`, `.qml`, `.spec`, `getattr` con cadenas, `Slot`/`Property` de Qt, endpoints FastAPI y contratos de interfaz. Regla: en la duda se conserva. Después, `git grep -w` propio confirmó 0 usos fuera de la definición.

| Candidato | Veredicto | Motivo |
|---|---|---|
| `hal/measures/converters.py: MovingAverage` | **Retirado** | El filtrado real es `MedianFilter` + `OneEuroFilter`; no es base de nada. |
| `services/domain/puertas/ser_puertas.py: Rules` (`TEMP_MAX_APERTURA = 120.0`) | **Retirado** | El tope real de apertura sale de `temp_max_apertura` (configuración) vía `camara_segura.evaluar`. La constante no participa en el interlock y confundía (parecía el tope). |
| `state_machine/alarms/alarm_manager.py: has_failure`, `has_alert` | **Retirados** | Consultas de solo lectura sin llamador ni duck typing; `has_blocking_alarm`/`has_emergency` siguen. |
| `ui_pyside/views/login.py: _hash_pw` (+ `import hashlib` huérfano) | **Retirado** | SHA-256 sin sal, distinto del esquema vigente `pbkdf2$600000$` de `backend/contrasenas.py`; sin uso. |
| `ServicioPuertas.can_open` / `can_close` | Conservado | Única implementación que junta permiso por rol (`can_*_from_context`) con la condición física; es la barrera de acceso pendiente de cablear (backend ignora `source_door`). |
| `Door.is_closed` / `unlock` (base) y `SimpleDoor.is_closed` / `unlock` | Conservado | Contrato de la interfaz de dispositivo de puerta. |

Ninguna prueba referenciaba los elementos retirados. Pruebas relacionadas: ver d).

## c) Ramas, etiquetas y worktrees (P8 a P12)

### Comprobación en `origin` antes de cualquier borrado

```
$ git ls-remote origin refs/heads/alarmas-parte-a 'refs/heads/audit/*' refs/heads/feature/roles-sensor-temperatura refs/heads/worktree-anuncios-voz 'refs/tags/archivo/*'
f1b0e0b8381ce445a6fcf0dfbe76652dae1a3066	refs/heads/alarmas-parte-a
8d1884cd9a8440d1b4d276647327e1c8609807b0	refs/heads/audit/62304-snapshot
87fca2fce65cf0ae7ff15ce36e4189da47423747	refs/heads/feature/roles-sensor-temperatura
786c73578e999fd710075c96b69fa1a8b497d769	refs/heads/worktree-anuncios-voz
08f20262182ef16d271ba67cc8f0a5140a4707bc	refs/tags/archivo/feature-roles-sensor-temperatura
87fca2fce65cf0ae7ff15ce36e4189da47423747	refs/tags/archivo/feature-roles-sensor-temperatura^{}
2dd1f1e9e9f4dadac59306452e1f9f071efb5175	refs/tags/archivo/worktree-anuncios-voz
786c73578e999fd710075c96b69fa1a8b497d769	refs/tags/archivo/worktree-anuncios-voz^{}
```

Las cuatro ramas siguen en `origin` y las dos etiquetas apuntan exactamente a la punta de su rama. Nunca se borró nada en `origin`.

### Etiquetas de archivo (P10, P11)

Creadas y empujadas en la primera sesión (22-oct 12:17, etiquetas anotadas). En el nombre, la `/` de `feature/roles-sensor-temperatura` se reemplazó por `-` para no crear un nivel más (`archivo/feature-roles-sensor-temperatura`). Solo se empujaron esas dos etiquetas (`git push origin archivo/<nombre>`). La salida exacta del `push` se perdió con el corte de la sesión; el `ls-remote` de arriba confirma que están en `origin`.

```
archivo/feature-roles-sensor-temperatura -> 87fca2f  "Archivo (tanda 8, D8-3.27 P10): rama feature/roles-sensor-temperatura, no unida a dev. ..."
archivo/worktree-anuncios-voz            -> 786c735  "Archivo (tanda 8, D8-3.27 P11): rama worktree-anuncios-voz, no unida a dev. ..."
```

### P8 y P9

Al retomar, `git branch --list 'alarmas*' 'audit*'` no devuelve nada, `.worktrees/alarmas-parte-a` ya no existe y `git worktree list` no lo incluye. Comprobado:
- `alarmas-parte-a` (`f1b0e0b`) está contenida en `tanda-8` (`git merge-base --is-ancestor f1b0e0b tanda-8` → sí) y existe en `origin`;
- `docs/informes/lotes_auditoria/` (5 lotes) ya está versionada en `dev` y en `tanda-8` desde `5ba9df6`, así que no hubo que copiarla;
- `audit/62304-snapshot` (`8d1884c`) existe en `origin`.

No hay registro de qué sesión hizo esos borrados (probablemente la primera sesión de D8 antes del corte, o la sesión principal). No queda nada pendiente de P8/P9. Para recuperar: `git branch alarmas-parte-a origin/alarmas-parte-a`, `git branch audit/62304-snapshot origin/audit/62304-snapshot`.

### P12

`wt_rc` no aparece en `git worktree list`, `git worktree prune --dry-run -v` no lista nada y no existe ninguna carpeta `wt_rc` bajo `AppData/Local/Temp` (búsqueda hasta 6 niveles). Ya estaba quitado al retomar; no hay constancia de quién revisó su `data/` (ver DECISIONES SIN CONFIRMAR 3).

### P10 y P11 — worktrees que git se niega a quitar

```
$ git worktree remove .worktrees/roles-sensor-temperatura
fatal: '.worktrees/roles-sensor-temperatura' contains modified or untracked files, use --force to delete it
$ git worktree remove .claude/worktrees/anuncios-voz
fatal: '.claude/worktrees/anuncios-voz' contains modified or untracked files, use --force to delete it
```

Por la regla, no se forzó. Como las ramas siguen en uso por esos worktrees, tampoco se borraron las locales (git no deja borrar una rama activa en un worktree). Qué hay en cada uno:

- `.worktrees/roles-sensor-temperatura` (`feature/roles-sensor-temperatura`): solo artefactos generados que la rama versionó por error: 5 `build/AutoclaveUI/localpycs/*.pyc` borrados, `src/autoclave.egg-info/*` modificados y `__pycache__` en `src/` y `tests/`. Ningún `.py`, `.md` ni dato propio. Se puede quitar con `--force` sin perder nada.
- `.claude/worktrees/anuncios-voz` (`worktree-anuncios-voz`): además de artefactos (`egg-info`, `__pycache__`), tiene `data/autoclave.db` (+ `-shm`, `-wal`) modificados, `.claude/settings.local.json` modificado, `data/preferences.json` sin seguimiento (solo `{"audio": {"enabled": false, "volume": 80}}`) y **`docs/superpowers/plans/2026-08-12-anuncios-voz.md` sin seguimiento, distinto de la versión que ya está en `tanda-8`** (la del worktree es posterior: en la línea 13 amplía las excepciones Clase C autorizadas con el `append` de `AlarmManager.report()` desde el hilo de `Announcer`). Antes de forzar hay que guardar esa versión del plan.

Comandos para cuando Cristian lo apruebe (desde la carpeta principal):

```
git worktree remove --force .worktrees/roles-sensor-temperatura
git branch -D feature/roles-sensor-temperatura          # queda en origin y en archivo/feature-roles-sensor-temperatura
# guardar antes el plan nuevo de anuncios-voz (copiarlo a docs/ o a la carpeta de archivo)
git worktree remove --force .claude/worktrees/anuncios-voz
git branch -D worktree-anuncios-voz                     # queda en origin y en archivo/worktree-anuncios-voz
```

## d) Pruebas

- `PYTHONPATH=<worktree>/src`; `python -c "import autoclave;print(autoclave.__file__)"` → `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a2648dd3cc2073724\src\autoclave\__init__.py`.
- Suite completa tras P4/P6: 5382 passed, 3 skipped, 3 xfailed (`suites/d8.log`).
- Tras P5, solo las pruebas relevantes (por orden, no la suite completa): los 84 archivos de `tests/` que mencionan `converters`, `ser_puertas`/`ServicioPuertas`, `alarm_manager`/`AlarmManager`, `views.login`/`LoginView`, `images`/`imagenes`, `Pruebas`, `exe_unico` o `.spec` (excluido `test_rutas.py`, que `pyproject.toml` ignora a propósito porque importa `autoclave.core.converters`, que ya no existe; pasado por ruta explícita, pytest lo recolecta igual y falla en la importación, sin relación con D8). Resultado: **1516 passed, 1 skipped** (2 min 32 s).
- `git merge-tree --write-tree` de `894eb09` contra `tanda-8`, `tanda-8-r8`, `tanda-8-s1` y `tanda-8-s2b`: sin conflictos (código de salida 0 en los cuatro).
- La única prueba que menciona `images` (`test_c2_programas_persistentes.py`) no carga ninguno de los archivos movidos.

## DECISIONES SIN CONFIRMAR

1. **Iconos de la UI tkinter no movidos** (`images/*_icon.png`, `stop_cycle.png`, `images/Icons/*.svg`). D8-3.27 nombra "mockups e imágenes de diseño"; los iconos no son de diseño y las pantallas arman rutas de imagen dinámicas. Siguen empaquetándose. Para moverlos haría falta revisar una por una las rutas dinámicas.
2. **`can_open`/`can_close` de puertas y `is_closed`/`unlock` conservados** pese a no tener llamador (contrato de interfaz y barrera de permisos por rol pendiente). Para revertir P5 completo: `git revert 894eb09`.
3. **P8, P9 y P12 encontrados ya hechos** al retomar. Se verificó que lo borrado sigue en `origin` y que `lotes_auditoria/` está en `tanda-8`, pero no hay constancia de la revisión del `data/` de `wt_rc` antes de quitarlo. Si alguien lo quitó con `--force`, ese `data/` se perdió (D2 decía que solo tenía `data/` sin seguimiento de la tanda 4, de pruebas).
4. **Nombre de etiqueta** `archivo/feature-roles-sensor-temperatura` (con `-` en lugar de `/`).

## PREGUNTAS PARA CRISTIAN

1. ¿Se autoriza `git worktree remove --force` para `.worktrees/roles-sensor-temperatura` (solo artefactos) y, tras guardar el plan nuevo, para `.claude/worktrees/anuncios-voz`, y luego `git branch -D` de ambas ramas? Comandos en c).
2. La versión del plan `2026-08-12-anuncios-voz.md` que está sin seguimiento en el worktree de anuncios-voz es más nueva que la de `tanda-8`. ¿Se reemplaza la de `tanda-8` con ella o se guarda aparte?
3. (Del revisor de P5) ¿Se piensa cablear `can_open`/`can_close` cuando se resuelva lo de permisos por rol (`source_door`)? Si no, pasarían a código muerto junto con `can_*_from_context`.
4. (Del revisor de P5) `AdvancedDoor` no implementa `is_closed()` (lanzaría `NotImplementedError`) y hereda un `unlock()` vacío aunque sí tiene desbloqueo real (`desbloquear_on`). Hoy nadie los llama. ¿Se completa el contrato de `Door` o se documenta que no aplican a `AdvancedDoor`?
5. ¿Se mueven también los iconos de la UI tkinter fuera de `images/` (DECISIÓN 1)?

## Pendientes

- P10/P11: quitar los dos worktrees y borrar las ramas locales, cuando se autorice `--force` (pregunta 1).
- Altos/Críticos abiertos: ninguno. El revisor de P5 no reportó hallazgos de severidad; solo las dos preguntas abiertas (3 y 4).
