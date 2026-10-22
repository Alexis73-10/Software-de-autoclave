# D2 — Depuración del repositorio (tanda 7)

Rama: `tanda-7-d2` (desde `e8e42d7`). Fecha: 22-oct-2026, madrugada.
Se une a `dev` SOLO después de K2 (regla 8). Cambios mínimos: solo borrados de archivos, sin editar código vivo.

## Resumen

| Grupo | Commit | Qué se retiró |
|---|---|---|
| 1 | `08e7624` | `generar_iconos_emoji.py`, `listar_puertos.py`, `src/autoclave/ui_qml/main.py` |
| 2 | `0596f8b` | `ui_qml/controllers/ciclo_controller.py`, `ui_qml/controllers/reloj_splash_controller.py`, `ui_qml/domain/reloj_splash.py` y sus 3 archivos de prueba (23 pruebas) |
| 3 | `3f277a8` | `service.conf.lock`, `system.conf.lock` (vacíos) |
| Informe | (este commit) | `docs/informes/tanda7/D2_depuracion.md` |

Ramas: se empujaron 6 ramas de respaldo a `origin` (todas aceptadas) y se borraron 5 ramas locales ya contenidas en `dev`. No se quitó ningún worktree (ninguno estaba `prunable`; ver b).

Pruebas: línea base 5020 passed / 2 skipped / 3 xfailed. Con D2 se retiran 23 pruebas de código muerto, así que lo esperado es 4997 passed / 2 skipped / 3 xfailed. Resultado real: ver "Suite completa" al final.

Archivos de choque (`i18n/*.json`, `Instalacion.qml`, `db_manager.py`): NO tocados. Zonas de otros agentes (`installation/`, correo, mantenimiento, control de ciclo): NO tocadas.

---

## a) Código muerto

### Método

1. Grafo de imports con `ast` (script fuera del repo, `C:\Users\tecni\t7tmp\d2\grafo.py`): sigue `import`, `from … import` (absolutos y relativos, también los diferidos dentro de funciones) y cadenas `"autoclave.x.y"` (cubre `uvicorn.run("autoclave.backend.server:app")` e `importlib`). Puntos de entrada:
   - `Autoclave.spec` → `src/autoclave/exe_unico.py` + hiddenimports `autoclave.backend.main`, `autoclave.backend.server`, `autoclave.ui_qml.app`, `autoclave.ui_pyside.app`;
   - `AutoclaveBackend.spec` → `backend/main.py`; `AutoclaveSettings.spec` → `ui_pyside/app.py`;
   - `GeneradorCodigos.spec` → `tools/generador/lanzador.py` (+ `app.py`);
   - `pyproject.toml` → `autoclave.ui_qml.lanzar:main`; `instalador_exe.py`.
2. `git grep` de cada candidato en `src/`, `tools/`, `tests/`, `.spec` y `.ps1`.
3. `vulture` 2.x (instalado con `python -m pip install --user vulture`, solo en el Python del usuario) sobre `src/autoclave`, `tools` y `tests`, confianza 60 % y 90 %.
4. QML: cada `.qml` buscado por nombre de tipo en `.qml`/`.py`/`qmldir`. Recursos de `images/` y `ui_qml/assets/` buscados por nombre y raíz.

### Elementos de la lista de la instrucción

| Elemento | Quién lo usaba | Evidencia | Decisión |
|---|---|---|---|
| UI tkinter `src/autoclave/ui/` (`main.py`, `layout.py`, `cycle/`, `window/`, `components/`) | UI original | Ya retirada en `ece51e9` (R1, tanda 2). Solo queda `ui/service_ui/` (cliente HTTP y `SessionManager`), que SÍ está en uso por `ui_qml/app.py`, controladores QML y vistas PySide. | Nada que hacer. `ui/service_ui/` se conserva. |
| `installation/wizard.py` y `installation/factory_dialog.py` | Asistente tkinter | Ya retirados en `ece51e9` (decisión del 19-oct cumplida antes de esta tanda). | Nada que hacer. |
| `generar_iconos_emoji.py` (raíz) | Script de un solo uso para exportar 2 emojis a PNG | Sin referencias; los PNG que producía (`icono-herramientas`, `icono-login`) no están en el repo ni se usan. | **Eliminado** (`08e7624`). |
| `listar_puertos.py` (raíz) | Ayuda manual para ver puertos COM | 4 líneas, sin referencias. Equivale a `python -m serial.tools.list_ports`. | **Eliminado** (`08e7624`). |
| `src/autoclave/ui_qml/main.py` | Entrada antigua de la UI QML (alias de `app.main`) | Sin llamadores en código, `.spec`, `.ps1`, `.bat` ni `pyproject` (que apunta a `ui_qml.lanzar`). | **Eliminado** (`08e7624`). |
| `.bak` versionados | — | `git ls-files` no tiene ningún `.bak`/`.orig`/`~`. | Nada que hacer. |
| Vistas PySide sin llamador | — | Todas las vistas de `ui_pyside/views/` son alcanzables desde `ui_pyside/app.py` salvo `_email_dialog.py` (ver abajo). | Se conservan. |
| Pantallas QML de prueba `qml/Pruebas/*.qml` (7) + lanzadores `ui_qml/prueba_*.py` (4) + `ui_qml/historial_ejemplo.py` | Arneses de revisión visual y capturas (`python -m autoclave.ui_qml.prueba_…`) | No entran en producción (las excluyen `test_i2`/`test_i4`), pero se mantienen al día (último cambio 20-oct, U5 tanda 3) y sirven para capturas con `--captura`. | **Conservar — PREGUNTA P1.** |

### Otros módulos sin llamador en producción

| Módulo | Quién lo usa | Evidencia | Decisión |
|---|---|---|---|
| `ui_qml/controllers/ciclo_controller.py` (`CicloController`) | Solo `tests/test_ciclo_controller.py` | `controllers/__init__.py` solo importa `parametros_ciclo_controller`; ninguna pantalla QML instancia `CicloController`; la pantalla de preciclo usa `ui_bridge` + `bridge/progreso_ciclo` (que siguen usando `domain/pantalla_ciclo.py`). | **Eliminado** con su prueba (`0596f8b`). |
| `ui_qml/controllers/reloj_splash_controller.py` + `ui_qml/domain/reloj_splash.py` | Solo sus pruebas | Ninguna pantalla QML usa `RelojSplashController`; la fecha/hora del encabezado se arma en QML con `I18n.valor("fecha.meses")`. La clave `fecha.meses` sigue en uso. | **Eliminados** con sus 2 pruebas (`0596f8b`). |
| `ui_pyside/views/_email_dialog.py` | Solo `tests/test_email_dialog.py` y `test_c1a_teclado_pyside.py`; `ciclos.py` tiene su propia `_EmailDialog` interna | Sin importadores en producción. Pero está en la zona de C2 (correo), que lo revisa esta misma noche. | **Conservar — PREGUNTA P2** (que C2 o Cristian decidan). |
| `ui_qml/domain/alarmas.py`, `domain/reconexion.py`, `domain/telemetria.py` | Solo sus pruebas | Lógica pura del plan de interfaz dual (severidad de alarmas, retroceso de WebSocket, validación de telemetría) sin cablear todavía; el sistema de alarmas está pausado (rama `alarmas-parte-a`). | **Conservar — PREGUNTA P3.** |
| `installation/cambio_perfil.py` | `tools/declarar_entradas_suministro.py`, `declarar_sondas_temperatura.py`, `emparejar_tarjeta.py` | Herramienta "declarar" en uso. | Conservar. |
| `simulador/` | `python -m autoclave.simulador`, pruebas de contrato | Herramienta de desarrollo; excluida del exe a propósito. | Conservar. |

### Recursos (imágenes)

El análisis por nombre NO es fiable: las pantallas arman rutas dinámicas (`imagenes + "open_door_" + puerta + ".png"`, `iconosColor + nombre`, fuentes cargadas por carpeta). Por eso no se borró ningún recurso. Candidatos que parecen material de diseño y no de producción (se empaquetan en el exe porque `images/` entera va en `datas`):

- `images/DISEÑO INTERFAZ -P1 mockup.jpg`, `DISEÑO INTERFAZespera.jpg`, `DISEÑO INTERFAZ_menu.jpg`, `fondo_800x1280.pdf`, `opciones_*_comparativo.png`, `nuevo_usuario.png`, `pantalla_ciclo_*.png` (referencias citadas en comentarios QML);
- `images/*_icon.png`, `stop_cycle.png` e `images/Icons/*.svg` (los usaba la UI tkinter, retirada en `ece51e9`).

**PREGUNTA P4.**

### Código muerto a nivel de función (vulture)

- Confianza 90 %: 1 import sin uso (`state_machine/states/preparacion.py:2`, `parametros_globales`) y 4 variables `checked` de slots PySide. No se tocan: `preparacion.py` es zona de control de ciclo (Q1) y los `checked` son la firma de la señal.
- Confianza 60 %: 239 avisos de funciones/métodos/clases. La gran mayoría son falsos positivos: rutas FastAPI registradas por decorador (`server.py`, 79; `simulador/servidor.py`, 12; `tools/generador/app.py` y `tools/registro_pruebas/app_registro.py`, 13 cada uno), `Slot`/`Property` de Qt llamados desde QML (controladores y puentes) y métodos de interfaz de dispositivos (`set_io.py`, 19).
- Posibles verdaderos positivos, todos en zonas de seguridad o autenticación, así que se conservan: `hal/measures/converters.py: MovingAverage`; `services/domain/puertas/ser_puertas.py: Rules`, `can_open`, `can_close`; `state_machine/alarms/alarm_manager.py: has_failure`, `has_alert`; `ui_pyside/views/login.py: _hash_pw`; `devices/puertas/*: is_closed`, `unlock`. **PREGUNTA P5.**

### Otros archivos de la raíz

| Archivo | Evidencia | Decisión |
|---|---|---|
| `service.conf.lock`, `system.conf.lock` | 0 bytes, agregados el 07-jul con artefactos generados, sin ninguna referencia. | **Eliminados** (`3f277a8`). |
| `estudio/UI/` (ejercicios QML) | Ya se sacaron del paquete en `e5f9200`; sin referencias. | Conservar — PREGUNTA P6 (son material de estudio). |
| `parametros_software.accdb`, `data_base/*.xlsx`, `Documentacion/`, `Hardware/` | Material de referencia, no código. | Conservar. |

---

## b) Ramas y worktrees

Estado tomado después de `git fetch origin` (22-oct, ~00:50). "Propios" = commits de la rama que no están en `dev`.

| Rama | Último commit | En `dev` | Propios | En `origin` | Acción / recomendación |
|---|---|---|---|---|---|
| `dev` | `18eb429` 22-oct | — | 0 | sí, al día | Nada (no se empuja en D2). |
| `main` | `5fe9e1c` 24-sep | no | 31 (4 sin merge) | `origin/main` = `37bbc1b` (local atrasada) | No se toca (regla). Ver PREGUNTA P7. |
| `tanda-7`, `tanda-7-*` (c2, d2, l1, m1, m2, p1, q1) | 22-oct | no | — | no | Activas; no se tocan ni se empujan. |
| `worktree-agent-*` (7) | `e8e42d7` | no | — | no | Ramas automáticas de los worktrees de agentes de esta tanda; no se tocan. |
| `tanda-6` | `1d6cf98` 22-oct | sí | 0 | sí | **Conservada** localmente (DECISIÓN SIN CONFIRMAR: R6 puede referirse a ella esta noche). Borrable con `git branch -d tanda-6` después de Z. |
| `tanda-5` | `02323a0` 20-oct | sí | 0 | **empujada** ahora | **Borrada** local (`git branch -d`). |
| `tanda-4` | `0683c4a` 20-oct | sí | 0 | sí | **Borrada** local. |
| `tanda-3` | `c5307b5` 20-oct | sí | 0 | sí | **Borrada** local. |
| `tanda-2` | `35a1a5d` 20-oct | sí | 0 | sí | **Borrada** local. |
| `dev-noche` | `d5b7afb` 16-oct | sí | 0 | **empujada** ahora | **Borrada** local. |
| `alarmas-parte-a` | `f1b0e0b` 07-oct | **sí** (ya contenida en `dev`) | 0 | **empujada** ahora | No se borra (lo pide la instrucción y está en uso por el worktree `.worktrees/alarmas-parte-a`). PREGUNTA P8. |
| `audit/62304-snapshot` | `8d1884c` 07-oct | no | 1 | **empujada** ahora | PREGUNTA P9. |
| `feature/roles-sensor-temperatura` | `87fca2f` 08-sep | no | 16 | **empujada** ahora | PREGUNTA P10. |
| `worktree-anuncios-voz` | `786c735` 13-ago | no | 17 | **empujada** ahora | PREGUNTA P11. |
| `origin/fix/orden-descompresion-secado` (solo remota) | `d97ba15` 05-ago | sí | 0 | sí | Contenida en `dev`. Nunca se borran remotas: se deja. |

Para recuperar una rama borrada: `git branch tanda-4 origin/tanda-4` (todas las borradas están en `origin`).

### Evaluación de las ramas con trabajo propio

- **`alarmas-parte-a`**: ya está completamente contenida en `dev` (0 commits propios). Su worktree solo tiene sin commit `docs/informes/lotes_auditoria/` (sin seguimiento). Recomendación: copiar o commitear esa carpeta si vale, luego `git worktree remove .worktrees/alarmas-parte-a` y `git branch -d alarmas-parte-a` (queda en `origin`).
- **`audit/62304-snapshot`**: un commit que congela `dev e7bccf2` + los cambios sin commit del 08-oct (106 archivos, +13 742/−692) para la auditoría 62304. Comparado con `dd8f107` (etapa 1 de autenticación, 07-oct), la diferencia se reduce a 41 archivos, casi todo documentos: el código ya se commiteó en `dev` en `dd8f107` y siguientes. No es para unir (conflictos con `dev` en docs y en `backend/`). Recomendación: dejarla solo como archivo en `origin`; borrar la local con `git branch -D` cuando Cristian lo apruebe.
- **`feature/roles-sensor-temperatura`** (16 commits, 29 archivos, +2 092): roles de sensor principal/referencia por ciclo, F0 contra el sensor principal, endpoints `PATCH /cycle/sensor-roles` y `/display-slots`, pantallas PySide de sensores y entradas exhibidas. En `dev` NO está reimplementado (solo hay 2 menciones sueltas de `sensor_roles`). Unir hoy da conflictos en `cycle_manager.py`, `cycle_logger.py`, `control_loop.py`, `calentamiento.py`, `esterilizacion.py`, `ui_pyside/main_window.py` y `tests/test_control_loop_f0.py`, todo código de seguridad muy cambiado desde septiembre. Su worktree solo tiene artefactos generados sin commit (`build/`, `egg-info`). Recomendación: no unir. Si se quiere la función, reimplementarla sobre `dev` con un plan nuevo (y los tres revisores), usando la rama como referencia. Es el "pendiente compartido" de sensor de líquido de CLAUDE.md.
- **`worktree-anuncios-voz`** (17 commits, 64 archivos, +2 033): anuncios por voz (`Announcer`, manifiesto de audios, endpoints `/audio/*`, vista PySide). En `dev` no hay nada de audio. Conflictos con `backend/context.py`, `backend/server.py`, `control_loop.py`, `protocolo_fallo.py`, `ui_pyside/main_window.py` y un modificar/borrar de `src/autoclave/main.py` (retirado en `dev`). Agrega dependencias `sounddevice`/`soundfile`. Su worktree tiene sin commit un plan `docs/superpowers/plans/2026-08-12-anuncios-voz.md` (sin seguimiento) y artefactos (`data/*.db`, `egg-info`, `.claude/settings.local.json`). Recomendación: no unir. Archivarla (ya está en `origin`) y, si se retoma, rehacer la integración con el `ControlLoop` actual.

### Worktrees

`git worktree prune --dry-run` no lista nada: **ningún worktree está `prunable`**, y ya no quedan worktrees de la tanda 6. No se quitó ninguno.

| Worktree | Rama | Estado | Acción |
|---|---|---|---|
| carpeta principal | `tanda-7` | sesión principal | no se toca |
| `C:/Users/tecni/Documents/_build_a` | — | compilación K1 | no se toca |
| `.claude/worktrees/agent-*` (8) | `tanda-7-*` | agentes activos (bloqueados) | no se tocan |
| `…/AppData/Local/Temp/claude/…/scratchpad/wt_rc` | HEAD separado en `c238757` (en `dev`) | solo `data/` sin seguimiento | No quitado: `git worktree remove` exige `--force` por los archivos sin seguimiento. PREGUNTA P12. |
| `.worktrees/alarmas-parte-a` | `alarmas-parte-a` | `docs/informes/lotes_auditoria/` sin seguimiento | ver P8 |
| `.worktrees/roles-sensor-temperatura` | `feature/roles-sensor-temperatura` | solo artefactos generados | ver P10 |
| `.claude/worktrees/anuncios-voz` | `worktree-anuncios-voz` | plan sin seguimiento + artefactos | ver P11 |

---

## c) Commits sin push

Antes de D2 faltaban en `origin`: `tanda-5`, `dev-noche`, `alarmas-parte-a`, `audit/62304-snapshot`, `feature/roles-sensor-temperatura` y `worktree-anuncios-voz` (ninguna existía en el remoto). `dev`, `tanda-2`, `tanda-3`, `tanda-4` y `tanda-6` ya estaban al día en `origin`. `tanda-7` y `tanda-7-*` no se empujan (lo hace la sesión principal en Z).

Resultado exacto de cada `git push origin <rama>` (sin `--force`), todos con código de salida 0:

```
git push origin tanda-5                          ->  * [new branch]      tanda-5 -> tanda-5
git push origin dev-noche                        ->  * [new branch]      dev-noche -> dev-noche
git push origin alarmas-parte-a                  ->  * [new branch]      alarmas-parte-a -> alarmas-parte-a
git push origin audit/62304-snapshot             ->  * [new branch]      audit/62304-snapshot -> audit/62304-snapshot
git push origin feature/roles-sensor-temperatura ->  * [new branch]      feature/roles-sensor-temperatura -> feature/roles-sensor-temperatura
git push origin worktree-anuncios-voz            ->  * [new branch]      worktree-anuncios-voz -> worktree-anuncios-voz
```

(GitHub respondió además con el aviso habitual "Create a pull request for '<rama>'…"; no se creó ningún PR.)

## d) PR

`gh` está autenticado (cuenta `Alexis73-10`, alcance `repo`). `gh pr list --state open` no devuelve nada: **no hay PR abiertos**. No se creó ninguno.

---

## DECISIONES SIN CONFIRMAR

1. **Retiro de `CicloController`, `RelojSplashController` y `domain/reloj_splash.py` con sus pruebas** (`0596f8b`). Motivo: código sin ningún uso en producción. Alternativa: conservarlos como base para la futura pantalla con WebSocket. Para revertir: `git revert 0596f8b`.
2. **Retiro de `ui_qml/main.py`** (`08e7624`). Motivo: alias sin llamadores. Alternativa: conservarlo por si alguien lo lanza a mano con `python -m autoclave.ui_qml.main`; el reemplazo es `python -m autoclave.ui_qml.lanzar` o `python -m autoclave.ui_qml.app`. Para revertir: `git revert 08e7624`.
3. **`tanda-6` se conserva localmente** aunque ya está en `dev`, porque R6 trabaja esta noche con lo pendiente de la tanda 6. Borrarla después de Z: `git branch -d tanda-6`.

## PREGUNTAS PARA CRISTIAN

- **P1.** ¿Se conservan los arneses de prueba visual (`qml/Pruebas/*.qml`, `ui_qml/prueba_*.py`, `historial_ejemplo.py`)? Recomendación: conservarlos mientras se ajusten pantallas; no entran en el exe como pantallas de navegación, aunque los `.qml` sí se copian en `datas`.
- **P2.** `ui_pyside/views/_email_dialog.py` no lo importa ninguna vista (`ciclos.py` tiene su propio diálogo). ¿Se retira después de C2? Recomendación: decidirlo con el resultado de C2.
- **P3.** `ui_qml/domain/alarmas.py`, `reconexion.py` y `telemetria.py` son lógica pura sin cablear (plan dual-pantalla, sistema de alarmas pausado). ¿Se conservan para las partes B/C de alarmas y el WebSocket? Recomendación: conservar.
- **P4.** ¿Se sacan de `src/autoclave/images/` los mockups (`DISEÑO INTERFAZ*.jpg`, `fondo_800x1280.pdf`, `*_comparativo.png`, `pantalla_ciclo_*.png`, `nuevo_usuario.png`) y los iconos de la UI tkinter, por ejemplo a `docs/diseno/`? Hoy se empaquetan en el exe. Recomendación: moverlos en una tanda sin compilación, revisando una por una las rutas dinámicas.
- **P5.** Posible código muerto en zonas de seguridad (`MovingAverage`, `Rules`/`can_open`/`can_close` de puertas, `has_failure`/`has_alert`, `_hash_pw`, `is_closed`/`unlock` de puertas). ¿Se revisa con el `safety-reviewer`? Recomendación: sí, en una etapa aparte.
- **P6.** ¿`estudio/UI/` se queda en el repositorio? Recomendación: moverlo fuera del repo (material personal de estudio).
- **P7.** La `main` local (`5fe9e1c`) está atrasada respecto a `origin/main` (`37bbc1b`), y `origin/main` tiene 4 commits sin merge que no están en `dev`. En contenido neto solo agregan `src/autoclave/audio/abriendo puerta.mp3` y `cerrando puerta.mp3`. Recomendación: no tocar `main` hasta que se decida el flujo de publicación; si los mp3 hacen falta, traerlos a `dev` aparte.
- **P8.** `alarmas-parte-a` ya está contenida en `dev`. ¿Se quita su worktree (tras guardar `docs/informes/lotes_auditoria/`) y se borra la rama local? Recomendación: sí.
- **P9.** ¿`audit/62304-snapshot` queda solo como archivo en `origin` y se borra la local (`-D`)? Recomendación: sí.
- **P10.** ¿`feature/roles-sensor-temperatura` se reimplementa sobre `dev` con plan propio o se archiva? Recomendación: archivar y reimplementar con plan nuevo cuando se aborde el sensor de líquido.
- **P11.** ¿`worktree-anuncios-voz` se archiva? Recomendación: archivar (ya está en `origin`). Si se retoma, rehacer la integración.
- **P12.** El worktree temporal `wt_rc` (en `AppData/Local/Temp/…/scratchpad/`, HEAD en `c238757` de la tanda 4) solo tiene `data/` sin seguimiento. ¿Se quita con `git worktree remove --force`? Recomendación: sí, después de confirmar que `data/` no tiene nada que guardar.

## Comprobaciones manuales para Cristian

- Abrir el exe compilado desde `dev` con D2 unida (en una compilación posterior a K2) y verificar que arrancan backend, las dos pantallas y el menú de ajustes (D2 no toca ningún punto de entrada de los `.spec`).
- `git branch -a` para ver las ramas nuevas de respaldo en `origin`.

## Suite completa

- En la rama `tanda-7-d2`: 4997 passed, 2 skipped, 3 xfailed (17 min 40 s; corrida por la sesión principal el 22-oct, 06:05). Coincide con lo esperado.
- Unida a `tanda-7` después de K2 (fbd181c): 5382 passed, 3 skipped, 3 xfailed (20 min 29 s) = 5405 − 23.
