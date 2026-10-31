## CONTEXTO COMÚN (tanda 10, 23-oct-2026, sin supervisión; Cristian NO está — no preguntes, decide y documenta)
Repositorio: Software de Autoclave (Especifika), IEC 62304 Clase C. Todo informe en ESPAÑOL.
Estás en un worktree aislado que debe partir de la rama `tanda-10` (contiene `dev` 748337a con la tanda 9 unida, más e391ffe). Lee COMPLETOS antes de empezar:
- tu sección de `docs/mis_plans/decisiones_tanda_10.md` (FUENTE DE VERDAD; tu etapa cita sus puntos D10-x);
- tu etapa en la sección 1 de `docs/mis_plans/instruccion_claude_code_tanda_10.md` y sus reglas §0;
- `CLAUDE.md` del repo;
- de la tanda 9, solo los informes que necesites (`docs/informes/tanda9/*.md`; CAP9 para el banco de capturas).
Contexto mínimo: no leas otras secciones ni otros informes sin necesidad.

### Reglas obligatorias
1. Primero: `git log -1 --oneline`; si tu worktree no parte de `tanda-10` (debe contener e391ffe), haz `git checkout -b tanda-10-<id> tanda-10`; si sí, `git checkout -b tanda-10-<id>` (id en minúsculas, indicado abajo). Todo commit va en esa rama.
2. Git: NUNCA `main`, `--force`, `git add -A`, `git push --delete`, ni rebase/merge a otras ramas. Agrega archivos por nombre. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, logs ni fotos (las capturas que pida tu etapa sí, en `docs/informes/tanda10/capturas/<id>/`). NO hagas push.
3. Prohibido: tocar hardware/puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. No compiles con PyInstaller/ISCC.
4. El paquete `autoclave` está instalado en modo editable apuntando al repo PRINCIPAL. En tu worktree corre SIEMPRE con `PYTHONPATH=<ruta absoluta de tu worktree>/src` y comprueba `python -c "import autoclave;print(autoclave.__file__)"` antes de dar por buena cualquier prueba.
5. Todo texto visible nuevo va al catálogo i18n (es y en, `src/autoclave/i18n/`), sin anglicismos en es. Abreviaturas: solo las que autoriza D10-1 (claves de abreviatura); fuera de ellas sigue D8-5.4.
6. Ante ambigüedad: lo más seguro y reversible, marcado "DECISIÓN SIN CONFIRMAR" en tu informe. Si tu cambio termina tocando la lógica de estado seguro, ciclo o puertas: NO lo cambies, va como "PREGUNTA PARA CRISTIAN". Ninguna etapa de esta tanda es ★.
7. TDD: prueba primero, luego código. Commits pequeños con mensaje `tipo(tanda10-<id>): ...` terminando con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
8. NO corras la suite completa (la corre solo la sesión principal al unir). Corre ÚNICAMENTE las pruebas de los módulos que tocas y de los que los importan (`grep -rl` en `tests/`). Si falla alguna prueba QML por temporización ajena a tu cambio, repítela aislada y documéntalo.
9. ANTES DE TERMINAR: escribe tu informe en `docs/informes/tanda10/<ID>_<nombre>.md` (qué se hizo por punto D10, commits, pruebas nuevas y su resultado EXACTO con la ruta de `autoclave.__file__`, DECISIONES SIN CONFIRMAR, PREGUNTAS PARA CRISTIAN, pendientes) y COMMITÉALO EN TU RAMA. Nada sin commit al terminar.
10. Tu respuesta final (para la sesión principal): rama, último commit, pruebas corridas y resultado, archivos "puntos de choque" que tocaste (i18n, QML compartidos, `app.py`, `doble_pantalla.py`, `test_v8b_textos.py`), y preguntas abiertas. Breve.
