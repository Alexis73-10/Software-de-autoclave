## CONTEXTO COMÚN (tanda 11, 23-oct-2026, sin supervisión; Cristian NO está — no preguntes, decide y documenta)
Repositorio: Software de Autoclave (Especifika), IEC 62304 Clase C. Todo informe en ESPAÑOL.
Estás en un worktree aislado que debe partir de la rama `tanda-11` (contiene `dev` c607dc4 con la tanda 10 unida). Lee COMPLETOS antes de empezar:
- tu sección de `docs/mis_plans/decisiones_tanda_11.md` (FUENTE DE VERDAD; tu etapa cita sus puntos D11-x);
- tu etapa en la sección 1 de `docs/mis_plans/instruccion_claude_code_tanda_11.md` y sus reglas §0;
- `CLAUDE.md` del repo.
Contexto mínimo: no leas otras secciones ni otros informes sin necesidad (para capturas, el banco de capturas está descrito en `docs/informes/tanda9/CAP9*.md` y se usó en `docs/informes/tanda10/U10b_barrido_abreviaturas.md`).

### Reglas obligatorias
1. Primero: `git log -1 --oneline`; si tu worktree no parte de `tanda-11` (o de lo que te indique la sesión principal), haz `git checkout -b tanda-11-<id> tanda-11`; si sí, `git checkout -b tanda-11-<id>` (id en minúsculas, indicado abajo). Todo commit va en esa rama.
2. Git: NUNCA `main`, `--force`, `git add -A`, `git push --delete`, ni rebase/merge a otras ramas. Agrega archivos por nombre. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, logs ni fotos (las capturas que pida tu etapa sí, en `docs/informes/tanda11/capturas/<id>/`). No toques `stash@{0}`. NO hagas push.
3. Prohibido: tocar hardware/puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. No compiles con PyInstaller (ISCC.exe solo si tu etapa lo dice).
4. El paquete `autoclave` está instalado en modo editable apuntando al repo PRINCIPAL. En tu worktree corre SIEMPRE con `PYTHONPATH=<ruta absoluta de tu worktree>/src` y comprueba `python -c "import autoclave;print(autoclave.__file__)"` antes de dar por buena cualquier prueba.
5. Todo texto visible nuevo va al catálogo i18n (es y en, `src/autoclave/i18n/`), sin anglicismos en es.
6. Ante ambigüedad: lo más seguro y reversible, marcado "DECISIÓN SIN CONFIRMAR" en tu informe. Si tu cambio termina tocando la lógica de estado seguro, ciclo o puertas fuera de lo que dicen las decisiones: NO lo cambies, va como "PREGUNTA PARA CRISTIAN".
7. TDD: prueba primero, luego código. Commits pequeños con mensaje `tipo(tanda11-<id>): ...` terminando con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
8. NO corras la suite completa (la corre solo la sesión principal al unir). Corre ÚNICAMENTE las pruebas de los módulos que tocas y de los que los importan (`grep -rl` en `tests/`); puedes usar `-n auto` (pytest-xdist está instalado). Si falla alguna prueba QML por temporización ajena a tu cambio, repítela aislada y en serie y documéntalo.
9. ANTES DE TERMINAR: escribe tu informe en `docs/informes/tanda11/<ID>_<nombre>.md` (qué se hizo por punto D11, commits, pruebas nuevas y su resultado EXACTO con la ruta de `autoclave.__file__`, DECISIONES SIN CONFIRMAR, PREGUNTAS PARA CRISTIAN, pendientes) y COMMITÉALO EN TU RAMA. Nada sin commit al terminar.
10. Tu respuesta final (para la sesión principal): rama, último commit, pruebas corridas y resultado, archivos "puntos de choque" que tocaste (i18n es/en, QML compartidos, `app.py`, `server.py`, `doble_pantalla.py`, `test_v8b_textos.py`, `hoja_pruebas_banco_equipo_pruebas.md`, `LEEME_INSTALACION.md`, `autoclave.iss`), y preguntas abiertas. Breve.
