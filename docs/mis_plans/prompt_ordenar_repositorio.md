# Prompt para Claude Code: ordenar el repositorio (10-oct-2026)

Contexto: el plan de autenticación (T-1 a T-21) está implementado y en origin/dev. Quedan cabos sueltos de orden en el repositorio. Esta tarea NO implementa funcionalidad nueva. Reglas: no hagas push, no borres ramas remotas, no hagas `git worktree prune` (los worktrees tienen rutas de Windows), no uses `git add -A`, y si algo no coincide con lo descrito aquí, detente y pregunta.

## Paso 0. Verificar el punto de partida
- `git status -sb`, rama `dev`, sin archivos `.git/*.lock`.
- Ya hecho antes de este prompt (no repetir): se borró la rama `claude/competent-morse-801d88` y el `stash@{0}` de agosto, y se cambió en `planeacion_backend_autenticacion.md` §5.8 `aplica` (`actual`/`siguiente`) por `en_curso`/`siguiente`. Ese cambio de una línea está sin commitear.

## Paso 1. Suite de pruebas
- Corre la suite completa. Si hay fallos, detente y repórtalos; no commitees nada hasta que esté en verde (o hasta que yo apruebe los fallos preexistentes).

## Paso 2. Commit A: protocolo serial v2 con CRC (plan planeacion_protocolo_serial_esp32.md)
Archivos: `src/autoclave/protocols/serial_link.py`, `crc16.py`, `serial_link_config.py`, `src/autoclave/config/serial_link.json`, `tests/serial_doble.py`, `tests/test_crc16.py`, `tests/test_serial_link_v2_lector.py`, y en `src/autoclave/backend/server.py` solo el cambio de `card_connected` y `_diagnostico_comunicacion` (campo `comunicacion`).
- Antes de añadir `server.py` revisa `git diff --stat`: si muestra miles de líneas, es ruido de fin de línea (CRLF/LF). No commitees el archivo entero con ese ruido; compara con `--ignore-space-at-eol` y dime qué hacer.
- Revisa que `serial_link.json` no contenga datos de máquina (puerto COM propio) que no deban versionarse.
- Mensaje sugerido: `feat(serial): protocolo v2 con CRC-16, diagnóstico del enlace y card_connected desde el enlace serial`.

## Paso 3. Commit B: una línea de spec
- Solo `docs/mis_plans/planeacion_backend_autenticacion.md`. Verifica con `git diff --ignore-space-at-eol` que el cambio es una sola línea (§5.8, Registro). Mensaje: `docs(autenticacion): §5.8 aplica = en_curso | siguiente (alinea la spec con el código)`.

## Paso 4. Commit C: documentación sin versionar
- `docs/mis_plans/` (planes, instrucciones, inventarios, matriz `.xlsx`, `.skill`, `nuevo_usuario.png`), `docs/informes/`, `docs/mockups/`, `docs/superpowers/plans|specs/` y los 3 `INFORME_*.md` de la raíz.
- Muéstrame antes `git status --short` de esos archivos y el tamaño de los binarios; yo confirmo. Los INFORME_*.md de la raíz propón moverlos a `docs/informes/` (con `git mv` o mover antes de añadir).
- Aparte, commit D de imágenes: `src/autoclave/images/` (icono autoclave.jpg, icono_autoclave.svg, opciones_*_comparativo.png). Pregúntame si `icono autoclave.jpg` (con espacio) es duplicado de `icono_autoclave.svg`.
- Deja fuera: `.claude/agents/`, `.claude/settings.local.json` (está versionado pese a ser local; propón `git rm --cached` y entrada en .gitignore, pero no lo hagas sin que yo lo apruebe).

## Paso 5. Fines de línea
- Informe, sin cambiar nada: `git config core.autocrlf`, si existe `.gitattributes`, y cuántos archivos de `src/` tienen CRLF en el índice. Propón un `.gitattributes` (p. ej. `*.py text eol=lf`) y cuántos archivos cambiaría un `git add --renormalize`. No lo ejecutes.

## Paso 6. Ramas
- `fix/orden-descompresion-secado`: está dentro de dev. Bórrala solo local con `git branch -d`. Dame el comando de la remota sin ejecutarlo.
- `audit/62304-snapshot` (1 commit): dime qué contiene respecto a dev y si sus archivos ya están en dev o en los untracked; propón conservar con tag o borrar.
- `main`: 31 por delante y 55 por detrás de dev. Lista los commits exclusivos de main y dime si son solo merges.

## Paso 7. Stashes restantes (`stash@{0}` y `stash@{1}`)
- Para cada uno lista los archivos que no sean `.pyc`, `data/`, `src/logs/`. Si hay fuente `.py` o docs que no estén en dev, muéstrame el diff. No los borres.

## Paso 8. Tres ramas vivas con worktree
`alarmas-parte-a` (20 delante / 14 atrás), `feature/roles-sensor-temperatura` (16 / 47), `worktree-anuncios-voz` (17 / 54).
- No hagas merge ni rebase. Para cada una: `git merge-tree` en seco contra dev, lista de archivos en conflicto, si tiene cambios sin commit en su worktree, y qué plan en `docs/mis_plans` o `docs/superpowers` la gobierna y en qué estado está.
- Escribe el resultado en `docs/informes/estado_ramas_2026-10-10.md` (tabla + recomendación: integrar, rebasar primero o archivar). Esto es solo un informe.

## Paso 9. Cierre
- `git status -sb` final y lista de lo que quedó sin commitear y por qué.
- Lista corta de pendientes que NO son de esta tarea (para mí): §5.8 aún nombra `despresurizacion → DESCOMPRESION` (sección que ya no existe); tabla §7 con Estado sin marcar para T-4 a T-7, T-10 a T-13 y T-15 a T-21; hallazgos TMG-04, TMG-06, SAF-08/09/10, TMG-03, SAF-03; brechas de presión de ESTERILIZACION; chequeo muerto en factory.py:43; las cinco preguntas de hardware.
