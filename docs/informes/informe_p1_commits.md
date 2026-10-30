# Informe — P1 (F0): commits del cierre de la fase B

Fecha: 12-oct-2026 · Rama `dev`, **sin push**. Plan aprobado: `plan_commits_p1.md` (C-1 a C-5).

## Commits

| # | Commit | Contenido | Suite del árbol del commit |
|---|---|---|---|
| (a) | `dd4a672` | E0/E1, adenda y buzzer | 2577 pasan, 0 fallos |
| (b) | `a9de029` | Fase B: backend por etapas y `GET /arranque` | 2637 pasan, 0 fallos |
| (b2) | `be201a8` | Intro de arranque (C-1) | 2656 pasan, 0 fallos |
| (c) | `efab1b3` | Renombrado ARR-01 `Arranque.qml` → `Reposo.qml` | 2656 pasan, 0 fallos |
| (d) | (este) | Documentación | 2656 pasan, 0 fallos (ninguna prueba lee `docs/`) |

## Cómo se separó y se probó
- **Prueba de cada commit (C-3).** Antes de cada commit armé un commit temporal suelto con el índice (`git write-tree` + `git commit-tree`, sin mover la rama) y lo abrí en un `git worktree` aislado. La suite completa corrió ahí con `PYTHONPATH=<worktree>/src`; antes comprobé que `autoclave.__file__` apuntaba al worktree. Tras cada commit verifiqué que su árbol fuera idéntico al probado. El árbol de trabajo principal no se tocó y no hubo stash.
- **Versiones intermedias (C-4).** Para (a), `context.py` y `server.py` se armaron sobre HEAD, aplicando solo los bloques E0/E1. Sus blobs (`0f4c659` y `2e01f5e`) coinciden exactamente con los que había antes de la fase B. Para (b2) se armaron `Main.qml` sin ARR-01, `es.json` solo con la sección `arranque`, `Arranque.qml` solo con el token y `test_intro_arranque_qml.py` con `hay("Arranque")`. Todos se pasaron al índice con `git hash-object -w` + `git update-index --cacheinfo`, sin tocar los archivos en disco.
- **Incidente sin consecuencias.** El primer intento con `server.py` aplicó al índice un parche `-U0` con los hunks elegidos, pero los números de línea quedaron desplazados y los bloques cayeron en lugares equivocados. Lo detecté al revisar el diff indexado y saqué el archivo del índice con `git restore --staged`, que no toca el disco. Luego lo armé con reemplazos de texto. No llegó a ningún commit.

## Hallazgo: trabajo en paralelo de otra sesión
Durante P1 aparecieron en el árbol de trabajo archivos que no son de esta sesión: `qml/Pantallas/Instalacion.qml`, `qml/Pruebas/PruebaInstalacion.qml`, 6 componentes (`BotonFormulario`, `CampoFormulario`, `FilaInterruptor`, `IndicadorPasos`, `OpcionTarjeta`, `SelectorSegmentos`), `ui_qml/prueba_instalacion.py` y una sección `instalacion` en `es.json`. Parece el asistente de instalación en QML (F1b/P2b), que en este flujo todavía no está aprobado. **Quedó fuera de todos los commits.** La sección `instalacion` de `es.json` sigue en el árbol de trabajo, sin commit.

## Fuera de los commits (a propósito)
- **Otros trabajos (C-5):** `instruccion_claude_code_e6_firmware.md`, `planeacion_firmware_1_5.md`, `planeacion_fin_de_ciclo_y_puertas.md`, `informe_verificaciones_fin_de_ciclo.md`, `analisis_sistema_alarmas.md` y la spec y el plan de la Parte A de alarmas.
- **No versionables:** `.claude/`, `docs/catalogo_alarmas.2026-09-18.bak.md` y `src/autoclave/images/icono autoclave.jpg`.
- **El asistente QML de la otra sesión** (ver hallazgo arriba).
